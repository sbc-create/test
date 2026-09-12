"""Детерминированные провайдеры для испытаний.

Существуют ради одного: проверить поведение контура там, где реальный вызов
запрещён или невозможен. Поэтому они умеют не только «получаться», но и
отказывать ровно на нужном шаге — потерять ответ ПОСЛЕ эффекта, упасть между
эффектом и записью, исчерпать квоту, отдать недействительный credential.
Без этого «идемпотентность проверена» означало бы «повторов не случилось».

Каждый эффект считается. Счётчик — то, чем доказывается, что два вызова дали
один объект, а сухой прогон не дал ни одного.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from typing import Any

from .base import Наблюдение, ProviderError, проверить_запись

ПОТЕРЯ_ОТВЕТА = "lost_response"
ПАДЕНИЕ_ПОСЛЕ_ЭФФЕКТА = "crash_after_effect"
КВОТА = "quota_exceeded"
НЕДЕЙСТВИТЕЛЬНЫЙ_CREDENTIAL = "invalid_credential"
ТАЙМАУТ = "timeout"
#: Цель «уехала» сразу после записи: эффект случился, но состояние не то,
#: которое планировали. Так расхождение и возникает в жизни — между
#: применением и подтверждением, а не спустя сутки.
ИСКАЖЕНИЕ_ПОСЛЕ_ПРИМЕНЕНИЯ = "drift_after_apply"


def _отпечаток(данные: Any) -> str:
    # Служебная пометка провайдера в отпечаток не входит: она наша, а не
    # свойство ресурса.
    if isinstance(данные, dict):
        данные = {к: з for к, з in данные.items() if not к.startswith("_")}
    return "sha256:" + hashlib.sha256(
        json.dumps(данные, ensure_ascii=False, sort_keys=True,
                   separators=(",", ":")).encode()).hexdigest()[:32]


class Обрыв(RuntimeError):
    """Процесс «умер» после того, как эффект у провайдера уже случился."""


@dataclass
class Мир:
    """Общее состояние фейкового провайдера: объекты и счётчик эффектов."""
    объекты: dict[str, dict] = field(default_factory=dict)
    эффекты: list[dict] = field(default_factory=list)
    отказы: set[str] = field(default_factory=set)
    вызовов: int = 0
    стоимость: int = 0
    предел_стоимости: int = 1000

    def сломать(self, что: str) -> None:
        self.отказы.add(что)

    def починить(self, что: str | None = None) -> None:
        if что is None:
            self.отказы.clear()
        else:
            self.отказы.discard(что)

    def поместить(self, provider_type: str, external_id: str,
                  объект: dict) -> None:
        """Положить объект, существовавший ДО нас.

        Тип провайдера обязателен: без него объект невидим своему провайдеру
        и виден чужому — ровно та путаница, из-за которой Topvisor однажды
        нашёл счётчик Метрики.
        """
        self.объекты[external_id] = {**объект, "_provider": provider_type}

    def эффект(self, вид: str, ключ: str, external_id: str) -> None:
        self.эффекты.append({"kind": вид, "key": ключ, "external_id": external_id})

    def эффектов(self, вид: str | None = None) -> int:
        return sum(1 for э in self.эффекты if вид is None or э["kind"] == вид)


class _Базовый:
    provider_type = "fake"
    resource_kind = "fake"
    live_writes = False

    def __init__(self, мир: Мир | None = None) -> None:
        self.мир = мир or Мир()

    # --- общие предохранители --------------------------------------------
    def _перед_вызовом(self, стоимость: int = 0) -> None:
        self.мир.вызовов += 1
        if НЕДЕЙСТВИТЕЛЬНЫЙ_CREDENTIAL in self.мир.отказы:
            # Отдельный код: недействительный credential не повторяют — его
            # меняют. Ретраить такое значит стучаться, пока не заблокируют.
            raise ProviderError("CREDENTIAL_INVALID",
                                "provider отверг credential", retryable=False)
        if ТАЙМАУТ in self.мир.отказы:
            raise ProviderError("PROVIDER_TIMEOUT", "истекло время ожидания",
                                retryable=True)
        if стоимость:
            if self.мир.стоимость + стоимость > self.мир.предел_стоимости:
                raise ProviderError(
                    "QUOTA_EXCEEDED",
                    "предел стоимости операций исчерпан: выключатель разомкнут",
                    retryable=False)
            self.мир.стоимость += стоимость
        if КВОТА in self.мир.отказы:
            raise ProviderError("QUOTA_EXCEEDED", "квота провайдера исчерпана",
                                retryable=False)

    def _после_эффекта(self, external_id: str) -> None:
        """Эффект уже случился — дальше может не повезти."""
        if ПАДЕНИЕ_ПОСЛЕ_ЭФФЕКТА in self.мир.отказы:
            raise Обрыв(f"процесс прерван после создания {external_id}")
        if ПОТЕРЯ_ОТВЕТА in self.мир.отказы:
            raise ProviderError("RESPONSE_LOST",
                                "ответ провайдера не получен", retryable=True)

    def _ключ(self, site_id: str) -> str:
        return f"{self.provider_type}:{self.resource_kind}:{site_id}"

    def _свои(self):
        """Объекты ЭТОГО провайдера.

        Один общий словарь на всех провайдеров — удобная модель ровно до
        первого поиска по естественному ключу: у счётчика Метрики и у проекта
        Topvisor одинаковое поле `site`, и сканирование без учёта типа
        находило чужой объект и падало на его полях.
        """
        return {в: о for в, о in self.мир.объекты.items()
                if о.get("_provider") == self.provider_type}

    def reconcile(self, *, site_id: str, external_id: str) -> Наблюдение:
        self._перед_вызовом()
        о = self.мир.объекты.get(external_id)
        if о is None:
            return Наблюдение(существует=False)
        return Наблюдение(существует=True, external_id=external_id,
                          fingerprint=_отпечаток(о), подробности=dict(о),
                          владение_подтверждено=о.get("owner") == site_id)

    def retire(self, *, site_id: str, external_id: str) -> dict[str, Any]:
        """Вывод из обращения НЕ удаляет объект у провайдера."""
        self._перед_вызовом()
        о = self.мир.объекты.get(external_id)
        if о is not None:
            о["retired"] = True
        return {"retired": True, "deleted": False, "external_id": external_id}

    def удалить(self, *, external_id: str, создан_набором: str | None,
                changeset_id: str) -> dict[str, Any]:
        """Компенсация. Удаляет только то, что создал ЭТОТ набор изменений."""
        о = self.мир.объекты.get(external_id)
        if о is None:
            return {"deleted": False, "reason": "объекта нет"}
        if создан_набором != changeset_id:
            raise ProviderError(
                "COMPENSATION_REFUSED",
                f"{external_id} создан не этим набором изменений "
                f"({создан_набором!r}); компенсация чужого ресурса запрещена")
        del self.мир.объекты[external_id]
        self.мир.эффект("delete", external_id, external_id)
        return {"deleted": True, "external_id": external_id}


class ФейковыйDNS(_Базовый):
    provider_type = "dns"
    resource_kind = "record_set"

    def observe(self, *, site_id: str, intent: Any) -> Наблюдение:
        self._перед_вызовом()
        ключ = self._ключ(site_id)
        о = self.мир.объекты.get(ключ)
        if о is None:
            return Наблюдение(существует=False)
        # Владение доказывается TXT-меткой, а не совпадением имени: домен
        # может указывать куда угодно, и «он похож на наш» доказательством
        # не является.
        метка = о.get("records", {}).get(f"_site-verify.{intent.canonical_domain}")
        return Наблюдение(существует=True, external_id=ключ,
                          fingerprint=_отпечаток(о), подробности=dict(о),
                          владение_подтверждено=(метка == site_id))

    def plan(self, *, site_id: str, intent: Any, observed: Наблюдение) -> dict:
        записи = {intent.canonical_domain: ("A", "203.0.113.10")}
        for п in intent.aliases:
            записи[п] = ("CNAME", intent.canonical_domain)
        записи[f"_acme-challenge.{intent.canonical_domain}"] = ("TXT", "ожидается")
        for имя, (тип, значение) in записи.items():
            проверить_запись(тип, имя, значение)
        целевое = {"owner": site_id, "zone": intent.canonical_domain,
                   "records": {и: f"{т}:{з}" for и, (т, з) in записи.items()}}
        return {"resource_kind": self.resource_kind,
                "target": целевое, "expected_fingerprint": _отпечаток(целевое),
                "empty": bool(observed.существует
                              and observed.fingerprint == _отпечаток(целевое))}

    def apply(self, *, site_id: str, plan: dict, idempotency_key: str) -> dict:
        self._перед_вызовом()
        ключ = self._ключ(site_id)
        если_есть = self.мир.объекты.get(ключ)
        if если_есть is not None and _отпечаток(если_есть) == plan["expected_fingerprint"]:
            return {"external_id": ключ, "fingerprint": plan["expected_fingerprint"],
                    "created": False}
        self.мир.объекты[ключ] = {**plan["target"], "_provider": self.provider_type}
        self.мир.эффект("create", idempotency_key, ключ)
        self._после_эффекта(ключ)
        return {"external_id": ключ, "fingerprint": plan["expected_fingerprint"],
                "created": True}


class ФейковыйTLS(_Базовый):
    provider_type = "tls"
    resource_kind = "certificate"

    def observe(self, *, site_id: str, intent: Any) -> Наблюдение:
        self._перед_вызовом()
        ключ = self._ключ(site_id)
        о = self.мир.объекты.get(ключ)
        if о is None:
            return Наблюдение(существует=False)
        return Наблюдение(существует=True, external_id=ключ,
                          fingerprint=_отпечаток(о), подробности=dict(о),
                          владение_подтверждено=о.get("owner") == site_id)

    def plan(self, *, site_id: str, intent: Any, observed: Наблюдение) -> dict:
        целевое = {"owner": site_id, "subject": intent.canonical_domain,
                   "san": sorted({intent.canonical_domain, *intent.aliases}),
                   "issuer": "fake-acme"}
        return {"resource_kind": self.resource_kind, "target": целевое,
                "expected_fingerprint": _отпечаток(целевое),
                "empty": bool(observed.существует
                              and observed.fingerprint == _отпечаток(целевое))}

    def apply(self, *, site_id: str, plan: dict, idempotency_key: str) -> dict:
        self._перед_вызовом()
        ключ = self._ключ(site_id)
        если_есть = self.мир.объекты.get(ключ)
        if если_есть is not None and _отпечаток(если_есть) == plan["expected_fingerprint"]:
            return {"external_id": ключ, "fingerprint": plan["expected_fingerprint"],
                    "created": False}
        self.мир.объекты[ключ] = {**plan["target"], "_provider": self.provider_type}
        self.мир.эффект("create", idempotency_key, ключ)
        self._после_эффекта(ключ)
        return {"external_id": ключ, "fingerprint": plan["expected_fingerprint"],
                "created": True}


class ФейковаяМетрика(_Базовый):
    provider_type = "analytics"
    resource_kind = "counter"

    def observe(self, *, site_id: str, intent: Any) -> Наблюдение:
        self._перед_вызовом()
        # Поиск по домену: счётчик мог существовать до нас, и создать второй
        # значило бы разделить статистику одного сайта на две половины.
        for внешний, о in self._свои().items():
            if о.get("site") == intent.canonical_domain:
                return Наблюдение(существует=True, external_id=внешний,
                                  fingerprint=_отпечаток(о), подробности=dict(о),
                                  владение_подтверждено=о.get("owner") in
                                  (site_id, None))
        return Наблюдение(существует=False)

    def plan(self, *, site_id: str, intent: Any, observed: Наблюдение) -> dict:
        целевое = {"owner": site_id, "site": intent.canonical_domain,
                   "name": f"{intent.template_family}:{intent.canonical_domain}"}
        return {"resource_kind": self.resource_kind, "target": целевое,
                "expected_fingerprint": _отпечаток(целевое),
                "empty": bool(observed.существует)}

    def apply(self, *, site_id: str, plan: dict, idempotency_key: str) -> dict:
        self._перед_вызовом()
        # Счётчик ищется по естественному ключу ДО создания — это и есть
        # защита от второго объекта при потерянном ответе.
        for внешний, о in self._свои().items():
            if о.get("site") == plan["target"]["site"]:
                return {"external_id": внешний, "created": False,
                        "public_counter_id": о["public_counter_id"],
                        "fingerprint": _отпечаток(о)}
        номер = 90000000 + len(self.мир.объекты) + 1
        внешний = f"counter-{номер}"
        о = {**plan["target"], "public_counter_id": номер,
             "data_state": "WAITING_DATA", "_provider": self.provider_type}
        self.мир.объекты[внешний] = о
        self.мир.эффект("create", idempotency_key, внешний)
        self._после_эффекта(внешний)
        return {"external_id": внешний, "created": True,
                "public_counter_id": номер, "fingerprint": _отпечаток(о)}


class ФейковыйTopvisor(_Базовый):
    provider_type = "seo_rank"
    resource_kind = "project"
    #: Операции платные: каждая учитывается в предел стоимости.
    СТОИМОСТЬ_СОЗДАНИЯ = 100

    def observe(self, *, site_id: str, intent: Any) -> Наблюдение:
        self._перед_вызовом()
        for внешний, о in self._свои().items():
            if о.get("site") == intent.canonical_domain:
                return Наблюдение(существует=True, external_id=внешний,
                                  fingerprint=_отпечаток(о), подробности=dict(о),
                                  владение_подтверждено=о.get("owner") in
                                  (site_id, None))
        return Наблюдение(существует=False)

    def plan(self, *, site_id: str, intent: Any, observed: Наблюдение) -> dict:
        целевое = {"owner": site_id, "site": intent.canonical_domain,
                   "region": intent.region, "engines": ["yandex", "google"]}
        return {"resource_kind": self.resource_kind, "target": целевое,
                "expected_fingerprint": _отпечаток(целевое),
                "empty": bool(observed.существует),
                "estimated_cost": self.СТОИМОСТЬ_СОЗДАНИЯ}

    def apply(self, *, site_id: str, plan: dict, idempotency_key: str) -> dict:
        self._перед_вызовом(стоимость=self.СТОИМОСТЬ_СОЗДАНИЯ)
        for внешний, о in self._свои().items():
            if о.get("site") == plan["target"]["site"]:
                return {"external_id": внешний, "created": False,
                        "project_id": о["project_id"], "fingerprint": _отпечаток(о)}
        номер = 7000 + len(self.мир.объекты) + 1
        внешний = f"project-{номер}"
        о = {**plan["target"], "project_id": номер,
             "_provider": self.provider_type}
        self.мир.объекты[внешний] = о
        self.мир.эффект("create", idempotency_key, внешний)
        self._после_эффекта(внешний)
        return {"external_id": внешний, "created": True, "project_id": номер,
                "fingerprint": _отпечаток(о)}


class ФейковаяВитрина(_Базовый):
    """Витрина шаблона: сюда ставится тег счётчика.

    Существует ради одного вопроса, который иначе остаётся без ответа:
    создание счётчика и УСТАНОВКА тега — разные события. Успешный create
    возвращает идентификатор, но ничего не говорит о том, что витрина этот
    идентификатор отдаёт. Проверяется именно отдача.
    """

    provider_type = "template"
    resource_kind = "counter_tag"

    def __init__(self, мир: Мир | None = None, html: str | None = None) -> None:
        super().__init__(мир)
        self.html = html or "<html><head></head><body>витрина</body></html>"
        self._счётчик: int | None = None

    def установить_счётчик(self, номер: int | None) -> None:
        """Публичный идентификатор передаётся явно, а не дописывается в намерение.

        Намерение неизменяемо, и подсовывать в него служебное поле значило бы
        сделать «неизменяемое» условным — ровно то, на что потом никто не
        рассчитывает.
        """
        self._счётчик = int(номер) if номер else None

    def observe(self, *, site_id: str, intent: Any) -> Наблюдение:
        self._перед_вызовом()
        ключ = self._ключ(site_id)
        о = self.мир.объекты.get(ключ)
        if о is None:
            return Наблюдение(существует=False)
        return Наблюдение(существует=True, external_id=ключ,
                          fingerprint=_отпечаток(о), подробности=dict(о),
                          владение_подтверждено=о.get("owner") == site_id)

    def plan(self, *, site_id: str, intent: Any, observed: Наблюдение) -> dict:
        номер = self._счётчик
        if not номер:
            raise ProviderError(
                "COUNTER_ID_REQUIRED",
                "публичный идентификатор счётчика не передан: ставить тег "
                "нечем, а пустой тег выглядел бы установленным")
        целевое = {"owner": site_id, "counter_id": int(номер),
                   "placement": "head"}
        return {"resource_kind": self.resource_kind, "target": целевое,
                "expected_fingerprint": _отпечаток(целевое),
                "empty": bool(observed.существует
                              and (observed.подробности or {}).get("counter_id")
                              == int(номер))}

    def apply(self, *, site_id: str, plan: dict, idempotency_key: str) -> dict:
        self._перед_вызовом()
        ключ = self._ключ(site_id)
        номер = plan["target"]["counter_id"]
        существующий = self.мир.объекты.get(ключ)
        if существующий and существующий.get("counter_id") == номер:
            return {"external_id": ключ, "created": False,
                    "fingerprint": _отпечаток(существующий)}
        self.мир.объекты[ключ] = {**plan["target"], "_provider": self.provider_type}
        # Тег ставится в разметку — это и есть наблюдаемое следствие.
        self.html = self.html.replace(
            "</head>", f'<script data-counter="{номер}"></script></head>')
        if ИСКАЖЕНИЕ_ПОСЛЕ_ПРИМЕНЕНИЯ in self.мир.отказы:
            # Эффект durable, но состояние разошлось с планом.
            self.мир.объекты[ключ]["counter_id"] = int(номер) + 1
        self.мир.эффект("create", idempotency_key, ключ)
        self._после_эффекта(ключ)
        return {"external_id": ключ, "created": True,
                "fingerprint": _отпечаток(plan["target"])}

    def тег_установлен(self, номер: int) -> bool:
        return f'data-counter="{номер}"' in self.html
