"""Живая read-only проверка credentials CDNVideoHub.

Задание требует: «перед сохранением проверить credentials живым read-only
запросом к CDNVideoHub; неверные значения не записывать». Модуль делает ровно
это и ничего сверх: один ``GET``, три исхода, никакого тела ответа наружу.

Свойства, которые модуль обязан удержать:

* значение токена подставляется в заголовок в момент отправки и нигде не
  сохраняется — ни в объекте запроса, ни в журнале, ни в тексте исключения;
* тело ответа не разбирается, не печатается и не сохраняется: проверке нужен
  HTTP-статус, а прочитанный каталог провайдера — уже не проверка токена;
* «сеть недоступна» и «токен отвергнут» — разные исходы. Смешать их значило бы
  либо записать неверный токен при сетевом сбое, либо объявить рабочий токен
  негодным из-за таймаута;
* сам факт «direction verified» не выводится из отсутствия ошибки: он ставится
  только по явному ``2xx``.

Publisher ID отдельным запросом не проверяется: в переданном контракте
(`knowledge/cdnvideohub/PLAYER_CONTRACT.yaml`) он — `configured_public_value`,
передаваемый web component'у, а не credential Content API. Проверять его
выдуманным endpoint'ом запрещено; проверяется его форма, и это честно
называется `format_checked`, а не `verified`.
"""
from __future__ import annotations

import contextlib
import re
import urllib.error
import urllib.request
from dataclasses import dataclass
from enum import Enum

from factory import audit
from factory.errors import BlockedAccess
from factory.secret_hub.crypto import Secret
from factory.secret_hub.registry import VerifyContract

#: Ответы, означающие «провайдер понял запрос и отверг credentials».
REJECTED_STATUSES = frozenset({400, 401, 403})

#: Ответы, означающие «провайдер принял credentials».
ACCEPTED_MIN, ACCEPTED_MAX = 200, 299

#: Форма Publisher ID: непустая строка без пробелов и управляющих символов.
#: Более строгую маску контракт провайдера не задаёт, а придумывать её нельзя.
PUBLISHER_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{1,127}$")


class Outcome(str, Enum):
    ACCEPTED = "accepted"
    REJECTED = "rejected"
    UNMEASURED = "unmeasured"


@dataclass(frozen=True)
class VerifyResult:
    """Исход проверки. Значений и тела ответа здесь нет по построению."""

    outcome: Outcome
    http_status: int | None
    reason: str
    publisher_id_format_ok: bool
    url: str

    @property
    def ok(self) -> bool:
        return self.outcome is Outcome.ACCEPTED and self.publisher_id_format_ok

    @property
    def may_store(self) -> bool:
        """Можно ли записывать значения в хранилище.

        Записывается только явно принятое. «Не проверено» записью не считается:
        требование «неверные значения не записывать» иначе выполнялось бы лишь
        тогда, когда сеть работает.
        """
        return self.ok

    def as_dict(self) -> dict:
        return {
            "outcome": self.outcome.value,
            "http_status": self.http_status,
            "reason": self.reason,
            "publisher_id_format_ok": self.publisher_id_format_ok,
            "url": self.url,
        }


def check_publisher_id(publisher_id: Secret) -> bool:
    return bool(PUBLISHER_ID_RE.match(publisher_id.reveal().strip()))


def verify(contract: VerifyContract, api_token: Secret, publisher_id: Secret, *,
           opener=None, portfolio: str = "-") -> VerifyResult:
    """Один read-only запрос. Возвращает исход, а не выбрасывает при отказе.

    Отказ провайдера — это результат проверки, а не авария процесса: вызывающий
    код обязан отличить «токен неверен» от «проверка не выполнена», и исключение
    сделало бы оба случая одинаковыми на вид.
    """
    format_ok = check_publisher_id(publisher_id)
    url = contract.url
    request = urllib.request.Request(url, method=contract.method)
    request.add_header(contract.auth_header, f"{contract.auth_scheme} {api_token.reveal()}")
    request.add_header("Accept", "application/json")

    open_url = opener or urllib.request.urlopen
    timeout = contract.timeout_ms / 1000.0
    status: int | None = None
    try:
        response = open_url(request, timeout=timeout)
    except urllib.error.HTTPError as exc:
        status = exc.code
        # Тело ответа не читается вообще: содержимое ошибки провайдера ничего не
        # добавляет к статусу, а прочитанное имеет свойство попадать в логи.
        with contextlib.suppress(Exception):
            exc.close()
        if status in REJECTED_STATUSES:
            result = VerifyResult(Outcome.REJECTED, status,
                                  f"провайдер отверг credentials (HTTP {status})",
                                  format_ok, url)
        else:
            result = VerifyResult(Outcome.UNMEASURED, status,
                                  f"провайдер ответил HTTP {status}: проверка не выполнена",
                                  format_ok, url)
    except urllib.error.URLError as exc:
        # В причину попадает только класс ошибки и, для сетевых ошибок, её текст
        # без URL с параметрами: токен передаётся заголовком, но осторожность
        # здесь дешевле разбирательства потом.
        result = VerifyResult(Outcome.UNMEASURED, None,
                              f"сеть до провайдера недоступна ({exc.__class__.__name__})",
                              format_ok, url)
    except TimeoutError:
        result = VerifyResult(Outcome.UNMEASURED, None,
                              f"провайдер не ответил за {contract.timeout_ms} мс",
                              format_ok, url)
    else:
        with response:
            status = getattr(response, "status", None) or response.getcode()
        if ACCEPTED_MIN <= status <= ACCEPTED_MAX:
            reason = "провайдер принял credentials"
            if not format_ok:
                reason = ("провайдер принял токен, но publisher_id не соответствует форме "
                          "контракта")
            result = VerifyResult(Outcome.ACCEPTED, status, reason, format_ok, url)
        else:
            result = VerifyResult(Outcome.UNMEASURED, status,
                                  f"неожиданный ответ HTTP {status}: проверка не выполнена",
                                  format_ok, url)

    audit.record(
        job_id=f"secret-hub/{portfolio}",
        site_id=portfolio,
        environment="secret-hub",
        action="secret_hub.verify",
        target=url,
        exit_code=result.http_status,
        mutation=False,
        extra={
            "outcome": result.outcome.value,
            "method": contract.method,
            "publisher_id_format_ok": result.publisher_id_format_ok,
        },
    )
    return result


def require_verified(result: VerifyResult, portfolio: str) -> None:
    """Превращает неуспешный исход в типизированный отказ.

    Нужна там, где вызывающий уже решил, что без проверки продолжать нельзя, —
    например, при применении к боевой инфраструктуре.
    """
    if result.ok:
        return
    if result.outcome is Outcome.REJECTED:
        raise BlockedAccess(
            f"Направление «{portfolio}»: {result.reason}. Значения не сохранены.",
            field=portfolio,
            required_input="Действующий API Token CDNVideoHub",
            blocks_stage="VALIDATING",
        )
    if not result.publisher_id_format_ok:
        raise BlockedAccess(
            f"Направление «{portfolio}»: publisher_id не соответствует форме контракта.",
            field="publisher_id",
            required_input="Publisher ID из контракта CDNVideoHub",
            blocks_stage="VALIDATING",
        )
    raise BlockedAccess(
        f"Направление «{portfolio}»: {result.reason}. Непроверенные значения не сохраняются.",
        field=portfolio,
        required_input="Доступность public-api.cdnvideohub.com с этого хоста",
        blocks_stage="VALIDATING",
    )
