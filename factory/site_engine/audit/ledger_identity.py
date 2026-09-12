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
import json
import os

from factory.site_engine.credentials import store as C

ПРЕФИКС = "AUDIT_TOKEN_"

#: Credential с ОТПЕЧАТКАМИ служебных токенов. Верификатору сырые значения
#: не нужны: чтобы ответить «этот токен принадлежит службе X», достаточно
#: сравнить SHA-256. Хранение сырых токенов у проверяющего означало бы, что
#: компрометация Control API выдаёт личности всех девяти служб сразу.
ОТПЕЧАТКИ = "audit-token-fingerprints"

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
ТИП_АКТОРА = {"architect": "SERVICE", "audit-bridge": "SERVICE",
              "changeset-worker": "SERVICE", "registry": "SERVICE",
              "templates": "SERVICE", "content": "SERVICE", "seo": "SERVICE",
              "monitoring": "SERVICE", "backup": "SERVICE",
              "integrations": "SERVICE", "qwen": "MODEL",
              "human_owner": "HUMAN"}


class IdentityError(RuntimeError):
    def __init__(self, code: str, detail: str, status: int = 401):
        super().__init__(detail)
        self.error_code, self.detail, self.status = code, detail, status


def _реестр_отпечатков() -> tuple[dict[str, str], set[str]]:
    """Имя службы → SHA-256 её токена, плюс множество отозванных отпечатков.

    Пустой реестр означает «запись выключена», а не «всем можно».
    """
    сырое = C.получить_или_none(ОТПЕЧАТКИ)
    if сырое:
        данные = json.loads(сырое)
        службы = {k.lower(): v.lower()
                  for k, v in (данные.get("services") or {}).items() if v}
        отозваны = {x.lower() for x in (данные.get("revoked") or []) if x}
        return службы, отозваны

    if not C.послабление_включено():
        # Молча вернуть пустой реестр нельзя: это выглядело бы как «запись
        # выключена по решению», а на деле означает несконфигурированный юнит.
        raise IdentityError(
            "LEDGER_IDENTITY_NOT_PROVISIONED",
            f"credential {ОТПЕЧАТКИ} не передан: юнит обязан объявить "
            f"LoadCredential; передача служебных токенов окружением "
            f"запрещена", 503)

    # Переходный режим на время поэтапного перевода служб.
    службы = {}
    for k, v in os.environ.items():
        if k.startswith(ПРЕФИКС) and v.strip():
            службы[k[len(ПРЕФИКС):].lower()] = hashlib.sha256(
                v.strip().encode("utf-8")).hexdigest()
    отозваны = {x.strip().lower()
                for x in os.environ.get(ОТОЗВАННЫЕ, "").split(",") if x.strip()}
    return службы, отозваны


def опознать(заголовки: dict[str, str]) -> dict[str, str]:
    """Вернуть опознанную службу. Заявленное клиентом имя только сверяется."""
    отпечатки, отозваны = _реестр_отпечатков()
    if not отпечатки:
        raise IdentityError(
            "LEDGER_WRITE_DISABLED",
            "ни один служебный токен не настроен: запись в журнал выключена",
            503)
    предъявлен = (заголовки.get("authorization") or "").removeprefix(
        "Bearer ").strip()
    if not предъявлен:
        raise IdentityError("UNAUTHENTICATED", "служебный токен не предъявлен")

    полный = hashlib.sha256(
        предъявлен.encode("utf-8", "surrogatepass")).hexdigest()
    опознана = None
    for служба, ожидаемый in отпечатки.items():
        # Сравнение постоянного времени: вычисленный отпечаток против
        # записанного. Сырого токена у верификатора нет вовсе.
        if hmac.compare_digest(полный.encode("ascii"),
                               ожидаемый.encode("ascii")):
            опознана = служба
            break
    if опознана is None:
        raise IdentityError("UNAUTHENTICATED", "служебный токен не распознан")

    отпечаток = полный[:12]
    if полный in отозваны or отпечаток in отозваны:
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
