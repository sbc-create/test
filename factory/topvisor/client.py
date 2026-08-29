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
        Method("get/projects_2/projects", False, Cost.FREE, "список проектов"),
        Method("get/projects_2/searchers", False, Cost.FREE, "поисковые системы проекта"),
        Method("get/keywords_2/groups", False, Cost.FREE, "группы запросов"),
        Method("get/keywords_2/keywords", False, Cost.FREE, "запросы"),
        Method("add/projects_2/projects", True, Cost.FREE, "создать проект"),
        Method("edit/projects_2/projects", True, Cost.FREE, "изменить свойства проекта"),
        Method("add/projects_2/searchers", True, Cost.FREE, "добавить поисковую систему"),
        Method("add/keywords_2/groups", True, Cost.FREE, "создать группу запросов"),
        Method("add/keywords_2/keywords", True, Cost.FREE, "добавить запросы"),
        # Платные — присутствуют, чтобы плановщик мог назвать их и посчитать
        # стоимость, но исполнение закрыто отдельной проверкой ниже.
        Method("get/positions_2/checker/go", True, Cost.PAID, "запустить съём позиций"),
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

    #: Единственное значение `fields`, которое метод принимает. Проверено
    #: перебором по живому API: остальные имена дают код 2003.
    BANK_FIELDS = ("tariff",)

    def bank_info(self) -> dict:
        """Тариф и баланс — плоским словарём.

        Без `fields` метод отвечает `{"result": [], "total": 1}`: запись есть,
        но ни одна колонка не выбрана. Прошлая проверка печатала для этого
        «получено записей: 0» — надпись была буквально верна и потому особенно
        обманчива: выглядело как отсутствие доступа, хотя доступ был.

        Сведения приходят вложенными в `tariff`; разворачиваем их здесь, чтобы
        вызывающий не знал о форме ответа.
        """
        result = self.call("get/bank_2/info", {"fields": list(self.BANK_FIELDS)})
        if isinstance(result, list):
            result = result[0] if result else {}
        if not isinstance(result, dict):
            return {}
        tariff = result.get("tariff")
        if isinstance(tariff, dict):
            merged = {k: v for k, v in result.items() if k != "tariff"}
            merged.update(tariff)
            return merged
        return result

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
