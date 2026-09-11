"""Опознание производителя сервером. Клиенту на слово не верят.

Личность службы выводится ИЗ ПРЕДЪЯВЛЕННОГО СЕКРЕТА, а не из полей запроса.
Если бы `producer_service` брался из JSON, любая служба объявила бы себя
любой другой, и весь журнал превратился бы в набор утверждений о том, кем
отправитель захотел показаться.

Токены задаются переменными вида `AUDIT_TOKEN_<SERVICE>` и в журнал, логи и
отчёты не попадают: сравнивается только их хэш, а наружу уходит имя службы.
"""

from __future__ import annotations

import hashlib
import hmac
import os

ПРЕФИКС = "AUDIT_TOKEN_"

#: Отозванные токены — список отпечатков через запятую. Отзыв нужен отдельно
#: от замены значения: пока старый токен просто заменяют, он остаётся годным
#: везде, где переменную ещё не перечитали.
ОТОЗВАННЫЕ = "AUDIT_REVOKED_FINGERPRINTS"

#: Роли. Сырая лента показывает и собственные ошибки системы, поэтому её
#: читают только те, кому положено разбирать историю; рабочая проекция открыта
#: всем опознанным службам.
РОЛИ = {"architect": ("audit-admin", "producer"),
        "human_owner": ("audit-admin",)}
РОЛЬ_ПО_УМОЛЧАНИЮ = ("producer",)

#: Тип актора по умолчанию для каждой службы. Qwen — MODEL: это не деталь
#: оформления, а то, что запрещает ему исполняющие фазы.
ТИП_АКТОРА = {"architect": "SERVICE", "registry": "SERVICE",
              "templates": "SERVICE", "content": "SERVICE", "seo": "SERVICE",
              "monitoring": "SERVICE", "backup": "SERVICE",
              "integrations": "SERVICE", "qwen": "MODEL",
              "human_owner": "HUMAN"}


class IdentityError(RuntimeError):
    def __init__(self, code: str, detail: str, status: int = 401):
        super().__init__(detail)
        self.error_code, self.detail, self.status = code, detail, status


def _реестр_токенов() -> dict[str, str]:
    """Имя службы → токен. Пусто означает «запись выключена», а не «всем можно»."""
    итог = {}
    for k, v in os.environ.items():
        if k.startswith(ПРЕФИКС) and v.strip():
            итог[k[len(ПРЕФИКС):].lower()] = v.strip()
    return итог


def опознать(заголовки: dict[str, str]) -> dict[str, str]:
    """Вернуть опознанную службу. Заявленное клиентом имя только сверяется."""
    токены = _реестр_токенов()
    if not токены:
        raise IdentityError(
            "LEDGER_WRITE_DISABLED",
            "ни один служебный токен не настроен: запись в журнал выключена",
            503)
    предъявлен = (заголовки.get("authorization") or "").removeprefix(
        "Bearer ").strip()
    if not предъявлен:
        raise IdentityError("UNAUTHENTICATED", "служебный токен не предъявлен")

    опознана = None
    for служба, ожидаемый in токены.items():
        # Сравнение постоянного времени по БАЙТАМ. На строках
        # `compare_digest` выбрасывает TypeError, если во входе есть не-ASCII,
        # — и присланный кем-то не-ASCII токен ронял бы endpoint вместо
        # честного отказа. Кодирование убирает и эту зависимость от алфавита.
        if hmac.compare_digest(предъявлен.encode("utf-8", "surrogatepass"),
                               ожидаемый.encode("utf-8", "surrogatepass")):
            опознана = служба
            break
    if опознана is None:
        raise IdentityError("UNAUTHENTICATED", "служебный токен не распознан")

    отпечаток = hashlib.sha256(предъявлен.encode()).hexdigest()[:12]
    отозваны = {x.strip() for x in os.environ.get(ОТОЗВАННЫЕ, "").split(",")
                if x.strip()}
    if отпечаток in отозваны:
        # Отдельный код, а не «не распознан»: владельцу важно отличать чужой
        # токен от своего же, выведенного из обращения.
        raise IdentityError("TOKEN_REVOKED",
                            "предъявленный токен отозван", 403)

    # Если клиент ЗАЯВИЛ службу, она обязана совпасть с опознанной. Иначе это
    # попытка выдать себя за другого, и её нужно назвать именно так.
    заявлена = (заголовки.get("x-service-name") or "").strip().lower()
    заявлена = заявлена.removeprefix("service:")
    if заявлена and заявлена != опознана:
        raise IdentityError(
            "IDENTITY_SPOOF",
            f"предъявленный токен принадлежит службе {опознана}, а запрос "
            f"объявляет себя {заявлена}", 403)

    return {"producer_service": опознана,
            "actor_id": f"service:{опознана}",
            "actor_type": ТИП_АКТОРА.get(опознана, "SERVICE"),
            "roles": list(РОЛИ.get(опознана, РОЛЬ_ПО_УМОЛЧАНИЮ)),
            "token_fingerprint": отпечаток}


def требовать_роль(заголовки: dict[str, str], роль: str) -> dict[str, str]:
    """Опознать и убедиться, что у службы есть нужная роль."""
    кто = опознать(заголовки)
    if роль not in кто["roles"]:
        raise IdentityError(
            "ROLE_DENIED",
            f"служба {кто['producer_service']} не имеет роли {роль}", 403)
    return кто
