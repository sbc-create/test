"""Эталонный клиент контура изменений.

Зачем он в наборе контрактов, а не у каждого потребителя свой: клиент,
написанный по описанию, отличается от описания ровно в тех местах, где
описание неполно, — и расхождение обнаруживается у того, кто им пользуется.
Здесь клиент лежит рядом с контрактом и проверяется вместе с ним.

Без зависимостей: только стандартная библиотека. Клиент, который тянет за
собой пакеты, перестаёт быть эталонным — его не включают в тесную среду, и он
расходится молча.

Состояние клиент НЕ задаёт. В запросе нет поля `status`: клиент просит
выполнить ДЕЙСТВИЕ, а состояние — вывод сервера.
"""
from __future__ import annotations

import json
import urllib.error
import urllib.request
from typing import Any

#: Действия над набором изменений и путь каждого. Список объявлен здесь
#: отдельно, чтобы проверка паритета могла сверить его с OpenAPI, а не
#: угадывать по именам методов.
ДЕЙСТВИЯ: tuple[str, ...] = (
    "validate", "approve", "reject", "revoke-approval",
    "apply", "rollback", "cancel",
)

БАЗА = "/api/v1/changesets"


class ОшибкаКонтура(RuntimeError):
    """Отказ, разобранный из problem+json.

    Код ошибки вынесен отдельным полем намеренно: разбирать текст сообщения
    на стороне потребителя — значит зависеть от его формулировки.
    """

    def __init__(self, статус: int, error_code: str, detail: str,
                 тело: dict[str, Any] | None = None):
        super().__init__(f"{статус} {error_code}: {detail}")
        self.статус, self.error_code, self.detail = статус, error_code, detail
        self.тело = тело or {}

    @property
    def повторяем(self) -> bool:
        return bool(self.тело.get("retryable"))


class КлиентИзменений:
    def __init__(self, база: str, токен: str, *, таймаут: float = 20.0):
        self.база = база.rstrip("/")
        self._токен = токен
        self.таймаут = таймаут

    # --- низкий уровень ---------------------------------------------------

    def _зов(self, метод: str, путь: str, *, тело: dict | None = None,
             версия: int | None = None,
             request_id: str = "") -> tuple[dict[str, Any], dict[str, str]]:
        заг = {"Content-Type": "application/json",
               "Authorization": "Bearer " + self._токен}
        if версия is not None:
            # И заголовком, и полем тела — но никогда обоими сразу с разными
            # значениями: сервер такой запрос отклоняет, и правильно делает.
            заг["If-Match"] = f'"{версия}"'
        if request_id:
            # Заголовок HTTP кодируется latin-1. Без этой проверки клиент
            # падал бы глубоко внутри urllib с UnicodeEncodeError, и причина
            # — непригодный идентификатор — в отказе не упоминалась бы вовсе.
            try:
                request_id.encode("latin-1")
            except UnicodeEncodeError:
                raise ValueError(
                    "request_id передаётся заголовком и должен быть "
                    "представим в latin-1") from None
            заг["X-Request-Id"] = request_id
        данные = (json.dumps(тело, ensure_ascii=False).encode("utf-8")
                  if тело is not None else None)
        зап = urllib.request.Request(self.база + путь, method=метод,
                                     headers=заг, data=данные)
        try:
            with urllib.request.urlopen(зап, timeout=self.таймаут) as о:
                сырое = о.read() or b"{}"
                return json.loads(сырое), dict(о.headers)
        except urllib.error.HTTPError as e:
            сырое = e.read() or b"{}"
            try:
                т = json.loads(сырое)
            except ValueError:
                т = {}
            raise ОшибкаКонтура(
                e.code, str(т.get("error_code") or "UNKNOWN"),
                str(т.get("detail") or сырое[:200].decode("utf-8", "replace")),
                т) from e

    # --- чтение -----------------------------------------------------------

    def список(self, **фильтры) -> dict[str, Any]:
        """Фильтры применяет сервер. Неизвестное значение даёт 422, а не пустой
        список: пустой ответ читается как «ничего нет», и опечатка выглядела бы
        достоверным фактом."""
        хвост = "&".join(f"{k}={v}" for k, v in фильтры.items() if v is not None)
        тело, _ = self._зов("GET", БАЗА + ("?" + хвост if хвост else ""))
        return тело

    def получить(self, cid: str) -> tuple[dict[str, Any], int]:
        """Набор и его версия. Версию возвращают обратно в `версия=`."""
        тело, заг = self._зов("GET", f"{БАЗА}/{cid}")
        метка = (заг.get("ETag") or "").strip('"')
        return тело, int(метка) if метка.isdigit() else int(тело.get("version", 0))

    def история(self, cid: str) -> dict[str, Any]:
        тело, _ = self._зов("GET", f"{БАЗА}/{cid}/transitions")
        return тело

    # --- действия ---------------------------------------------------------

    def предложить(self, заявка: dict[str, Any], *,
                   request_id: str = "") -> dict[str, Any]:
        тело, _ = self._зов("POST", БАЗА, тело=заявка, request_id=request_id)
        return тело

    def _действие(self, cid: str, действие: str, тело: dict | None = None, *,
                  версия: int | None = None,
                  request_id: str = "") -> dict[str, Any]:
        if действие not in ДЕЙСТВИЯ:
            raise ValueError(f"действие {действие!r} контуром не предусмотрено")
        ответ, _ = self._зов("POST", f"{БАЗА}/{cid}/{действие}",
                             тело=тело or {}, версия=версия,
                             request_id=request_id)
        return ответ

    def валидировать(self, cid: str, **kw) -> dict[str, Any]:
        return self._действие(cid, "validate", **kw)

    def одобрить(self, cid: str, *, expires_at: str, reason: str = "",
                 **kw) -> dict[str, Any]:
        """`expires_at` обязателен: бессрочное одобрение не отличается от его
        отсутствия, и служба подписи его не выдаёт."""
        return self._действие(cid, "approve",
                              {"expires_at": expires_at, "reason": reason}, **kw)

    def отклонить(self, cid: str, *, reason: str = "", **kw) -> dict[str, Any]:
        return self._действие(cid, "reject", {"reason": reason}, **kw)

    def отозвать_одобрение(self, cid: str, **kw) -> dict[str, Any]:
        return self._действие(cid, "revoke-approval", {}, **kw)

    def применить(self, cid: str, *, worker_id: str = "", **kw) -> dict[str, Any]:
        return self._действие(cid, "apply",
                              {"worker_id": worker_id} if worker_id else {}, **kw)

    def откатить(self, cid: str, **kw) -> dict[str, Any]:
        return self._действие(cid, "rollback", {}, **kw)

    def отменить(self, cid: str, *, reason: str = "", **kw) -> dict[str, Any]:
        return self._действие(cid, "cancel", {"reason": reason}, **kw)
