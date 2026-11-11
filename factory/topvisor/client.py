"""Клиент Topvisor API v2.

Устройство слоя повторяет транспорт к API Яндекса и по той же причине: смысл
операций и работа с сетью не должны жить в одном месте.

Свойства, которые модуль обязан удержать:

* вызывается только метод из явного списка. Незнакомый метод не отправляется:
  у Topvisor есть платные маршруты, и «отправить и посмотреть» стоит денег;
* повторяются только читающие запросы. Повтор ``add`` создаёт второй проект,
  а не исправляет первый;
* ключ подставляется в заголовок в момент отправки и не хранится ни в объекте
  запроса, ни в журнале, ни в тексте исключения;
* платный метод не выполняется автоматически никогда, каким бы ни был флаг
  ``--apply``: разрешение на изменения и разрешение тратить деньги — разные
  разрешения.

Про ответ Topvisor. Успех приходит как ``{"result": …}``, ошибка — как
``{"errors": [{"code": …, "string": …}]}`` при HTTP 200. Поэтому судить об
успехе по коду HTTP нельзя: ошибка авторизации выглядит как удачный ответ.
"""
from __future__ import annotations

import json
import time
import urllib.error
import urllib.request
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from factory.errors import BlockedAccess, BlockedAuthorization, BlockedInput, TransientError
from factory.redaction import redact
from factory.retry import RetryPolicy, run_with_retry
from factory.topvisor.credentials import TopvisorCredentials

BASE_URL = "https://api.topvisor.com/v2/json"

DEFAULT_TIMEOUT = 30.0

#: Скромный темп между запросами. Документированного числа в контракте нет,
#: поэтому фабрика держит собственный: превысить неизвестный лимит проще,
#: чем узнать его.
DEFAULT_MIN_INTERVAL = 0.34

RETRY_POLICY = RetryPolicy(max_attempts=4, base_delay=1.0, max_delay=20.0)

RETRYABLE_STATUSES = frozenset({429, 500, 502, 503, 504})


class Cost:
    """Во что обходится вызов. Значения намеренно грубые.

    ``UNKNOWN`` — не «наверное бесплатно», а «неизвестно», и обращается с ним
    фабрика так же, как с платным: не выполняет.
    """

    FREE = "free"
    PAID = "paid"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class Method:
    name: str
    mutation: bool
    cost: str
    description: str


#: Явный список. Всё, чего здесь нет, не отправляется.
#:
#: Причина закрытого списка, а не чёрного: у Topvisor платные маршруты
#: (съём позиций, аудит, проверка индексации) выглядят синтаксически так же,
#: как бесплатные, и опечатка в имени метода не должна стоить денег.
ALLOWED: dict[str, Method] = {
    m.name: m
    for m in (
        Method("get/bank_2/info", False, Cost.FREE, "тариф, баланс и состояние счёта"),
        # С `show_searchers_and_regions: 2` метод отдаёт поисковые системы и
        # регионы проекта вместе с индексами регионов (документация
        # topvisor.com/ru/api/projects-2/projects/get/, прочитана 26.10.2026).
        # Прежнего `get/projects_2/searchers` у API нет — проверено 27.09.
        Method("get/projects_2/projects", False, Cost.FREE, "список проектов"),
        # Экспорт регионов проекта (CSV). Живой вызов — аудит seo-engine
        # 19.09.2026 (artifacts/evidence/topvisor-operations-audit-02 в
        # wt-seo-operator-v2-01): у шести проектов Яндекс и Google, «Россия».
        Method("get/positions_2/searchers/regions/export", False, Cost.FREE,
               "регионы проекта (CSV)"),
        # История позиций. Позиция — число или '--' («не найден в пределах
        # проверенной глубины»); по архивным проектам метод не работает.
        Method("get/positions_2/history", False, Cost.FREE, "история позиций"),
        # Стоимость одного съёма. Ничего не запускает: вызван 19.09 в
        # read-only аудите seo-engine без списаний (флаги billable = false).
        Method("get/positions_2/checker/price", False, Cost.FREE,
               "стоимость одного съёма позиций"),
        Method("get/system_2/common/regions", False, Cost.FREE, "справочник регионов"),
        Method("get/keywords_2/groups", False, Cost.FREE, "группы запросов"),
        Method("get/keywords_2/keywords", False, Cost.FREE, "запросы"),
        Method("add/projects_2/projects", True, Cost.FREE, "создать проект"),
        # `edit/projects_2/projects` убран: API отвечает на него
        # «Call to undefined method» (прогон 2026-09-27, отчёт
        # var/topvisor/connect-latest.txt). Метод в списке разрешённых
        # означает «проверено, что он существует и бесплатен», а этот не
        # существует. Заменять его угаданным именем нельзя: замороженной
        # документации Topvisor нет, а перебор имён у этого API платный.
        # Пока имя не подтверждено документом, правка свойств проекта
        # остаётся операцией владельца в интерфейсе.
        # Имена записи поисковых систем и регионов — по документации
        # topvisor.com/ru/api/positions-2/ (26.10.2026). Прежнее
        # `add/projects_2/searchers` документом не подтверждено и убрано.
        Method("add/positions_2/searchers", True, Cost.FREE, "добавить поисковую систему"),
        # Документация называет метод двояко: оглавление — `searchers/regions`
        # (как у живого `searchers/regions/export`), заголовок страницы метода
        # — `searchers_regions`. Оба написания взяты из документа, а не
        # подобраны; второе пробуется только при отказе «нет такого метода».
        Method("add/positions_2/searchers/regions", True, Cost.FREE, "добавить регион"),
        Method("add/positions_2/searchers_regions", True, Cost.FREE, "добавить регион"),
        # Обычный (0) или архивный (-1) проект. Архивный не проверяется и не
        # отдаёт историю.
        Method("edit/projects_2/projects/on", True, Cost.FREE, "архивировать или вернуть проект"),
        Method("add/keywords_2/groups", True, Cost.FREE, "создать группу запросов"),
        Method("add/keywords_2/keywords", True, Cost.FREE, "добавить запросы"),
        # Платные — присутствуют, чтобы плановщик мог назвать их и посчитать
        # стоимость, но исполнение закрыто отдельной проверкой ниже.
        Method("edit/positions_2/checker/go", True, Cost.PAID, "запустить съём позиций"),
        # Само расписание денег не списывает, но включает автоматические
        # платные съёмы — поэтому по допуску это платная операция.
        Method("edit/schedule_2", True, Cost.PAID, "расписание автоматических съёмов"),
        Method("add/audit_2/audit", True, Cost.PAID, "запустить технический аудит"),
    )
}

#: Коды авторизации: ключ или идентификатор не приняты.
AUTH_CODES = frozenset({30, 31, 32, 53, 54})

#: Коды, при которых повтор бессмыслен: вход не станет верным сам.
#: Мелкие исторические коды перечислены явно, а всё, что начиная с 1000, —
#: структурные ошибки Topvisor: «нет такого метода» (1003) и «не то значение
#: параметра» (2003). Их не было в первой версии этого набора, и клиент
#: добросовестно повторял четыре раза запрос, который не мог удаться никогда.
TERMINAL_CODES = frozenset({0, 1, 2, 3, 4}) | AUTH_CODES
STRUCTURAL_CODE_FLOOR = 1000


def _is_terminal(code: object) -> bool:
    if not isinstance(code, int):
        return False
    return code in TERMINAL_CODES or code >= STRUCTURAL_CODE_FLOOR


@dataclass
class Call:
    """След вызова для отчёта. Ни ключа, ни заголовков здесь нет."""

    method: str
    mutation: bool
    cost: str
    applied: bool
    ok: bool
    detail: str = ""


@dataclass
class TopvisorClient:
    credentials: TopvisorCredentials
    timeout: float = DEFAULT_TIMEOUT
    #: По умолчанию клиент ничего не меняет. Изменения включаются явно.
    dry_run: bool = True
    min_interval: float = DEFAULT_MIN_INTERVAL
    opener: Callable[[urllib.request.Request, float], tuple[int, bytes]] | None = None
    sleep: Callable[[float], None] = time.sleep
    calls: list[Call] = field(default_factory=list)
    _last_sent: float = 0.0

    # -- отправка --------------------------------------------------------

    def _send(self, method: str, payload: dict) -> tuple[int, Any]:
        request = urllib.request.Request(
            f"{BASE_URL}/{method}",
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Content-Type": "application/json",
                "User-Id": self.credentials.user_id,
                # Собирается здесь и умирает вместе с запросом.
                "Authorization": self.credentials.authorization_header(),
            },
        )
        if self.opener is not None:
            status, body = self.opener(request, self.timeout)
        else:
            gap = self.min_interval - (time.monotonic() - self._last_sent)
            if gap > 0:
                self.sleep(gap)
            try:
                with urllib.request.urlopen(request, timeout=self.timeout) as response:
                    status, body = response.status, response.read()
            except urllib.error.HTTPError as error:
                status, body = error.code, error.read()
            except urllib.error.URLError as exc:
                raise TransientError(
                    f"Topvisor недоступен: {type(exc.reason).__name__}",
                    field="topvisor.network",
                    blocks_stage="topvisor",
                ) from exc
            finally:
                self._last_sent = time.monotonic()
        if status in RETRYABLE_STATUSES:
            raise TransientError(
                f"Topvisor ответил {status}",
                field="topvisor.http",
                blocks_stage="topvisor",
            )
        try:
            return status, json.loads(body.decode("utf-8"))
        except (ValueError, UnicodeDecodeError) as exc:
            # Тело в текст ошибки не кладём: оно может содержать эхо заголовков.
            raise BlockedAccess(
                f"Topvisor вернул неразбираемый ответ на {method} (HTTP {status})",
                field="topvisor.response",
                blocks_stage="topvisor",
            ) from exc

    # -- разбор ----------------------------------------------------------

    @staticmethod
    def _raise_for_errors(method: str, body: Any) -> None:
        errors = body.get("errors") if isinstance(body, dict) else None
        if not errors:
            return
        codes = [e.get("code") for e in errors if isinstance(e, dict)]
        # Текст ошибки пропускаем через redact: Topvisor повторяет в нём
        # присланные значения, а среди них бывает заголовок авторизации.
        texts = redact("; ".join(str(e.get("string", "")) for e in errors if isinstance(e, dict)))
        if any(c in AUTH_CODES for c in codes if isinstance(c, int)):
            raise BlockedAuthorization(
                f"Topvisor отклонил {method}: {texts or 'нет доступа'}",
                field="topvisor.credentials",
                required_input="проверить идентификатор и ключ в /etc/site-factory/secrets/topvisor",
                blocks_stage="topvisor",
            )
        if codes and all(_is_terminal(c) for c in codes):
            raise BlockedInput(
                f"Topvisor отклонил {method}: {texts or 'некорректный запрос'}",
                field="topvisor.request",
                blocks_stage="topvisor",
            )
        raise TransientError(
            f"Topvisor вернул ошибку на {method}: {texts or 'без текста'}",
            field="topvisor.request",
            blocks_stage="topvisor",
        )

    # -- публичный вызов -------------------------------------------------

    def call(self, method: str, payload: dict | None = None) -> Any:
        spec = ALLOWED.get(method)
        if spec is None:
            raise BlockedInput(
                f"Метод {method} не в списке разрешённых",
                field="topvisor.method",
                required_input="добавить метод в ALLOWED осознанно, вместе со стоимостью",
                blocks_stage="topvisor",
            )
        if spec.cost != Cost.FREE and spec.mutation:
            # Отдельная проверка, не зависящая от dry_run: флаг «применяй»
            # разрешает менять состояние, но не разрешает тратить деньги.
            self.calls.append(Call(method, spec.mutation, spec.cost, False, False, "платный метод не выполняется автоматически"))
            raise BlockedAccess(
                f"{method} — платный метод, автоматическое выполнение запрещено",
                field="topvisor.cost",
                required_input="получить расчёт стоимости и отдельное разрешение владельца",
                blocks_stage="topvisor",
            )
        if spec.mutation and self.dry_run:
            self.calls.append(Call(method, True, spec.cost, False, True, "запланировано, не отправлено"))
            return None

        body_payload = dict(payload or {})

        def attempt() -> Any:
            _, body = self._send(method, body_payload)
            self._raise_for_errors(method, body)
            return body.get("result") if isinstance(body, dict) else body

        # Повторяем только чтение. Повтор мутации создаёт дубль.
        if spec.mutation:
            result = attempt()
        else:
            result = run_with_retry(attempt, policy=RETRY_POLICY, sleep=self.sleep)
        self.calls.append(Call(method, spec.mutation, spec.cost, spec.mutation, True))
        return result

    # -- удобные обёртки -------------------------------------------------

    # Official bank_2/info contract: tariff.balance is only the plan account.
    # https://topvisor.com/ru/api/v2-services/bank_2/info/
    BANK_FIELDS = ("balance_all", "balance_personal", "balance_bonus", "balance_tariff", "tariff")

    def bank_info(self) -> dict:
        """Read total funds explicitly; never substitute the tariff balance."""
        import math
        result = self.call("get/bank_2/info", {"fields": list(self.BANK_FIELDS)})
        if isinstance(result, list):
            result = result[0] if result else {}
        if not isinstance(result, dict) or not result:
            return {}
        merged = dict(result)
        tariff = result.get("tariff")
        if isinstance(tariff, dict):
            # Preserve existing descriptive tariff fields and the original
            # nested account, but never let tariff values override totals.
            for key, value in tariff.items():
                if key != "balance":
                    merged.setdefault(key, value)
        total = result.get("balance_all")
        try:
            balance = float(total) if total is not None and not isinstance(total, bool) else None
        except (ValueError, TypeError):
            balance = None
        merged["balance"] = balance if balance is not None and math.isfinite(balance) else None
        return merged

    #: Колонки списка проектов. Проверено перебором по живому API: без явного
    #: `fields` метод возвращает только `id`, а `url` и `name` приходят пустыми.
    #: Именно на этом ломалась идемпотентность — план не узнавал существующие
    #: проекты и предлагал создать все шесть заново, то есть удвоить аккаунт.
    PROJECT_FIELDS = ("id", "name", "url", "site", "on")

    def projects(self) -> list[dict]:
        result = self.call(
            "get/projects_2/projects",
            {"limit": 500, "fields": list(self.PROJECT_FIELDS)},
        )
        return [p for p in (result or []) if isinstance(p, dict)]

    # -- фактические настройки проекта ------------------------------------
    #
    # Все три метода — ЧТЕНИЕ и объявлены бесплатными. Нужны они затем, что
    # «проект создан» и «проект настроен» — разные состояния: поисковые системы,
    # регион и семантика задаются отдельно, и запись в манифесте их наличия не
    # доказывает. Требование владельца — проверять результат повторным чтением
    # из сервиса.
    #
    # Про имя параметра. Форма запроса здесь не угадывается «по смыслу»: если
    # API ожидает другое имя, он отвечает ошибкой с указанием параметра — как
    # ответил на `fields[n].name` при пробе привязки счётчика, — и этот ответ
    # попадает в отчёт. Читающий метод ничего не стоит и ничего не меняет,
    # поэтому один точный запрос с разбором ответа — законный способ узнать
    # контракт, в отличие от перебора имён методов, который запрещён.

    def projects_with_regions(self) -> list[dict]:
        """Проекты вместе с поисковыми системами и ВСЕМИ регионами (2 —
        включённые и выключенные). У региона есть `index` — его и принимают
        история и съём. Без индекса проекта история читается по чужому
        региону и выглядит пустой (урок seo-engine, positions_snapshot)."""
        result = self.call(
            "get/projects_2/projects",
            {"limit": 500, "fields": list(self.PROJECT_FIELDS),
             "show_searchers_and_regions": 2},
        )
        return [p for p in (result or []) if isinstance(p, dict)]

    def history(self, project_id: int, regions_indexes: list[int],
                date1: str, date2: str) -> dict:
        """История позиций за период. Бесплатное чтение; съём не запускает."""
        result = self.call("get/positions_2/history", {
            "project_id": int(project_id),
            "regions_indexes": [int(i) for i in regions_indexes],
            "date1": date1, "date2": date2,
            "show_exists_dates": 1, "show_headers": 1,
            "positions_fields": ["position", "relevant_url"],
        })
        return result if isinstance(result, dict) else {}

    def checker_price(self, project_ids: list[int],
                      regions_indexes: list[int] | None = None) -> float | None:
        """Стоимость ОДНОГО съёма в рублях с учётом скидки тарифа.

        Ответ сгруппирован по владельцам, ключ группы — идентификатор
        владельца (половина учётных данных): здесь только суммируется и
        наружу не выходит. ``None`` — сервис цену не назвал."""
        payload: dict = {"filters": [{"name": "id", "operator": "EQUALS",
                                      "values": [int(i) for i in project_ids]}]}
        if regions_indexes:
            payload["regions_indexes"] = [int(i) for i in regions_indexes]
        result = self.call("get/positions_2/checker/price", payload)
        группы = (result or {}).get("pricesByUsers") if isinstance(result, dict) else None
        if not isinstance(группы, dict) or not группы:
            return None
        return round(sum(float((g or {}).get("price") or 0) for g in группы.values()
                         if isinstance(g, dict)), 2)

    def find_regions(self, search: str, searcher_key: int,
                     country_code: str | None = None) -> list[dict]:
        payload: dict = {"search": search, "searcher_key": int(searcher_key)}
        if country_code:
            payload["country_code"] = country_code
        result = self.call("get/system_2/common/regions", payload)
        return [r for r in (result or []) if isinstance(r, dict)]

    def call_paid(self, method: str, payload: dict, допуск: object) -> Any:
        """Единственная дверь для платного метода: только с бюджетным допуском.

        Допуск выдаёт `factory.topvisor.collect.допуск_съёма` — после чтения
        лимита владельца, цены съёма, расхода за месяц и проверки «сегодня
        ещё не снимали». Клиент проверяет, что допуск выдан на ЭТОТ вызов."""
        from factory.topvisor.collect import Допуск  # noqa: PLC0415

        spec = ALLOWED.get(method)
        if spec is None or spec.cost != Cost.PAID:
            raise BlockedInput(f"{method}: не платный метод из списка",
                               field="topvisor.method", blocks_stage="topvisor")
        if not isinstance(допуск, Допуск) or not допуск.покрывает(method, payload):
            self.calls.append(Call(method, True, spec.cost, False, False, "нет бюджетного допуска"))
            raise BlockedAccess(
                f"{method} — платный метод без бюджетного допуска",
                field="topvisor.cost",
                required_input="лимит владельца в config/topvisor-budget.json",
                blocks_stage="topvisor",
            )
        if self.dry_run:
            self.calls.append(Call(method, True, spec.cost, False, True, "запланировано, не отправлено"))
            return None
        _, body = self._send(method, dict(payload))
        self._raise_for_errors(method, body)
        self.calls.append(Call(method, True, spec.cost, True, True, f"допуск {допуск.сумма} ₽"))
        return body.get("result") if isinstance(body, dict) else body

    def keyword_groups(self, project_id: int) -> list[dict]:
        result = self.call("get/keywords_2/groups", {"project_id": int(project_id)})
        return [g for g in (result or []) if isinstance(g, dict)]

    def keywords(self, project_id: int) -> list[dict]:
        result = self.call("get/keywords_2/keywords", {"project_id": int(project_id)})
        return [k for k in (result or []) if isinstance(k, dict)]
