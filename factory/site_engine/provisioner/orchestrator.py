"""Единый Integration Provisioner.

Он НЕ является ни вторым реестром, ни вторым журналом, ни второй машиной
состояний. Всё, что меняет мир, проходит через CORE-003: на каждый внешний
ресурс заводится набор изменений, и контур сам решает, валиден ли план,
одобрен ли он, кто вправе применить и что делать при неудаче.

Задача Provisioner — последовательность и связывание: какой ресурс за каким,
какой публичный идентификатор передать дальше и что считать готовым. Ответ на
вопрос «что сейчас происходит» он не хранит, а вычисляет.

Порядок шагов задан зависимостями, а не вкусом: TLS бессмысленен до DNS,
установка тега Метрики — до того, как счётчик существует, а передача SEO —
до того, как появился проект.
"""
from __future__ import annotations

import json
import random
import time
from dataclasses import dataclass
from typing import Any, Callable

from factory.site_engine.changeset import engine as E
from factory.site_engine.changeset import model as M
from factory.site_engine.changeset import store as S
from factory.site_engine.provisioner import readiness as R
from factory.site_engine.provisioner.changeset_adapter import ProviderTargetAdapter
from factory.site_engine.provisioner.mapping import Связи
from factory.site_engine.provisioner.providers.base import ProviderError

#: Шаги onboarding и ресурсы, которые их закрывают.
ШАГИ = (
    ("dns", "dns.record_set"),
    ("tls", "tls.certificate"),
    ("analytics", "analytics.counter"),
    ("seo_rank", "seo.project"),
)

ПРЕДЕЛ_ПОПЫТОК = 4
БАЗОВАЯ_ЗАДЕРЖКА = 0.2


class ProvisionerError(RuntimeError):
    def __init__(self, code: str, detail: str):
        super().__init__(detail)
        self.error_code, self.detail = code, detail


@dataclass
class Шаг:
    имя: str
    resource_type: str
    changeset_id: str | None = None
    статус: str | None = None
    external_id: str | None = None
    public: dict[str, Any] | None = None
    отказ: str | None = None


class Provisioner:
    """Сопровождает одно намерение до готовности."""

    def __init__(self, *, соед_наборов, связи: Связи, реестр,
                 провайдеры: dict[str, Any], одобряющий: Callable | None = None,
                 сон: Callable[[float], None] = time.sleep) -> None:
        self.соед = соед_наборов
        self.связи = связи
        self.реестр = реестр
        self.провайдеры = провайдеры
        self.сон = сон
        #: Одобрение выдаётся не Provisioner'ом: он PROPOSER и не более.
        self.одобряющий = одобряющий
        self.шаги: list[Шаг] = []

    # --- один ресурс ------------------------------------------------------
    def _провести(self, намерение, site_id: str, имя: str,
                  resource_type: str) -> Шаг:
        шаг = Шаг(имя=имя, resource_type=resource_type)
        провайдер = self.провайдеры.get(имя)
        if провайдер is None:
            шаг.отказ = "PROVIDER_NOT_CONNECTED"
            return шаг

        адаптер = ProviderTargetAdapter(провайдер, намерение, self.связи,
                                        resource_type=resource_type)
        заявка = {
            "resource_type": resource_type,
            "resource_id": f"{site_id}:{имя}",
            "operation_type": "create",
            "target_site_ids": [site_id],
            "idempotency_key": f"onboard:{намерение.idempotency_key}:{имя}",
            "correlation_id": намерение.correlation_id,
            "requested_change": {"canonical_domain": намерение.canonical_domain},
        }
        создано = S.создать(self.соед, заявка, producer_service="architect",
                            actor_id="service:architect", actor_type="SERVICE")
        cid = создано["changeset_id"]
        шаг.changeset_id = cid
        адаптер.changeset_id = cid
        движок = E.Engine(self.соед, адаптер=адаптер, реестр=self.реестр)

        try:
            движок.валидировать(cid, actor_id="service:control-plane",
                                служба="control-plane")
        except S.ChangeSetError as ош:
            шаг.отказ = ош.error_code
            шаг.статус = S.получить(self.соед, cid)["status"]
            return шаг

        движок.запросить_одобрение(cid, actor_id="service:architect",
                                   служба="architect",
                                   expires_at=_через_час())
        if self.одобряющий is None:
            шаг.отказ = "APPROVAL_REQUIRED"
            шаг.статус = S.получить(self.соед, cid)["status"]
            return шаг
        self.одобряющий(движок, cid)

        аренда = S.взять_аренду(self.соед, cid, "provisioner")
        итог = self._применить_с_повторами(движок, cid, аренда["fencing_token"])
        шаг.статус = итог.get("status")
        связь = self.связи.найти(*_ключ_связи(resource_type, site_id))
        if связь is not None:
            шаг.external_id = связь.external_id
        результаты = (итог.get("results") or {}).get(site_id) or {}
        шаг.public = (результаты.get("apply") or {}).get("public")
        return шаг

    def _применить_с_повторами(self, движок, cid: str, маркер: int) -> dict:
        """Повтор только для временных отказов и с ограниченным числом попыток.

        Недействительный credential и исчерпанная квота не ретраятся: они не
        «пройдут в следующий раз», а от повторов становится только хуже —
        провайдер начинает считать нас источником мусора.
        """
        задержка = БАЗОВАЯ_ЗАДЕРЖКА
        последняя = {}
        for попытка in range(1, ПРЕДЕЛ_ПОПЫТОК + 1):
            try:
                return движок.применить(cid, actor_id="service:control-plane",
                                        служба="control-plane",
                                        fencing_token=маркер)
            except S.ChangeSetError as ош:
                последняя = {"status": "APPLY_FAILED", "error": ош.error_code}
                временный = ош.error_code in ("PROVIDER_TIMEOUT", "RESPONSE_LOST",
                                              "DNS_RESOLVE_FAILED")
                if not временный or попытка >= ПРЕДЕЛ_ПОПЫТОК:
                    return последняя
                self.сон(задержка + random.uniform(0, задержка / 2))
                задержка *= 2
        return последняя

    # --- весь onboarding ---------------------------------------------------
    def провести(self, намерение, site_id: str) -> dict[str, Any]:
        self.шаги = []
        for имя, resource_type in ШАГИ:
            шаг = self._провести(намерение, site_id, имя, resource_type)
            self.шаги.append(шаг)
            if шаг.отказ and шаг.отказ != "PROVIDER_NOT_CONNECTED":
                # Дальше не идём: TLS без DNS и тег без счётчика не имеют
                # смысла, а «попробуем следующий шаг» превращает частичный
                # отказ в непредсказуемое полусостояние.
                break
        return self.свод(намерение, site_id)

    def свод(self, намерение, site_id: str) -> dict[str, Any]:
        запись = next((с for с in self.реестр.сайты()
                       if с.get("site_id") == site_id), None)
        наборы = [S.получить(self.соед, ш.changeset_id)
                  for ш in self.шаги if ш.changeset_id]
        шаблон = any(ш.имя == "template" and ш.статус == M.SUCCEEDED
                     for ш in self.шаги)
        готовность = R.вычислить(site_id=site_id, запись_реестра=запись,
                                 связи=self.связи.по_сайту(site_id),
                                 наборы=[н for н in наборы if н],
                                 шаблон_готов=шаблон)
        return {"site_id": site_id,
                "intent_fingerprint": намерение.отпечаток,
                "steps": [vars(ш) for ш in self.шаги],
                "readiness": готовность.в_словарь(),
                "links": [vars(с) for с in self.связи.по_сайту(site_id)]}

    # --- сверка после обрыва ------------------------------------------------
    def сверить_незавершённые(self) -> dict[str, Any]:
        """Довести до определённости действия, начатые и не подтверждённые.

        Начатое действие означает, что эффект МОГ случиться. Единственный
        честный способ узнать — посмотреть у провайдера, а не решить по
        отсутствию ответа, что ничего не было.
        """
        итог = {"checked": 0, "found_effect": 0, "no_effect": 0}
        for действие in self.связи.незавершённые():
            итог["checked"] += 1
            провайдер = next(
                (п for п in self.провайдеры.values()
                 if п.provider_type == действие["provider_type"]
                 and п.resource_kind == действие["resource_kind"]), None)
            if провайдер is None:
                continue
            # Домен берётся из реестра, а не выдумывается: провайдер ищет
            # объект по естественному ключу, и сверка с чужим доменом честно
            # не нашла бы ничего и записала «эффекта не было».
            запись = self.реестр.сайт(действие["site_id"]) or {}
            домен = запись.get("canonical_domain")
            if not домен:
                итог.setdefault("skipped_no_domain", 0)
                итог["skipped_no_domain"] += 1
                continue
            намерение = _намерение_для_сверки(действие["site_id"], домен)
            н = провайдер.observe(site_id=действие["site_id"], intent=намерение)
            if н.существует:
                итог["found_effect"] += 1
                self.связи.завершить_действие(
                    действие["idempotency_key"], состояние="SUCCEEDED",
                    external_id=н.external_id, detail="подтверждено сверкой")
            else:
                итог["no_effect"] += 1
                self.связи.завершить_действие(
                    действие["idempotency_key"], состояние="FAILED",
                    detail="эффекта у провайдера нет")
        return итог

    # --- вывод сайта --------------------------------------------------------
    def вывести(self, site_id: str) -> dict[str, Any]:
        """SiteRetired: связи помечаются, объекты провайдера остаются."""
        помечено = self.связи.вывести_сайт(site_id)
        for связь in self.связи.по_сайту(site_id):
            провайдер = next(
                (п for п in self.провайдеры.values()
                 if п.provider_type == связь.provider_type), None)
            if провайдер is not None:
                провайдер.retire(site_id=site_id, external_id=связь.external_id)
        return {"site_id": site_id, "links_retired": помечено, "deleted": 0}


def _ключ_связи(resource_type: str, site_id: str) -> tuple[str, str, str]:
    from factory.site_engine.provisioner.changeset_adapter import ТИПЫ
    provider_type, resource_kind = ТИПЫ[resource_type]
    return (site_id, provider_type, resource_kind)


def _через_час() -> str:
    import datetime as d
    return (d.datetime.now(d.timezone.utc)
            + d.timedelta(hours=1)).isoformat().replace("+00:00", "Z")


def _намерение_для_сверки(site_id: str, домен: str):
    """Намерение, достаточное, чтобы провайдер нашёл объект по своему ключу."""
    from factory.site_engine.provisioner.intent import OnboardingIntent
    return OnboardingIntent.разобрать({
        "requested_by": "reconciler", "canonical_domain": домен,
        "template_family": "reconcile", "template_profile": "reconcile",
        "language": "-", "region": "-",
        "correlation_id": f"reconcile-{site_id}",
        "idempotency_key": f"reconcile-{site_id}", "site_id": site_id})
