"""Проверка разрешения на исполнение на границе адаптера Templates.

Зачем проверять на стороне адаптера
-----------------------------------

Разрешение выдаёт служба подписи, но исполняет адаптер. Если адаптер верит
факту вызова, то любой, кто добрался до него, исполняет что угодно: подпись
осталась у того, кто её не проверяет. Поэтому граница проходит здесь —
каждое притязание сверяется с тем, что адаптер собирается сделать, ДО того
как случится эффект.

Почему проверок много и они раздельные
--------------------------------------

Совпадение `plan_hash` ничего не говорит о том, тому ли сайту предназначено
разрешение; совпадение сайта — о том, не устарела ли версия реестра; а
действующий срок — о том, тот ли артефакт выкладывается. Объединять их в
одну проверку значит потерять способность сказать, что именно не сошлось.

Каждое несоответствие получает собственный код: по нему видно, это попытка
подмены цели, подмены плана, подмены артефакта или просто просроченное
разрешение.
"""
from __future__ import annotations

import datetime as _d
import hashlib
import json
from dataclasses import dataclass
from typing import Any

from factory.site_engine.approval import keyring as K

#: Кому адресуется разрешение на исполнение шаблонного релиза.
АУДИТОРИЯ = "templates-executor"
#: Притязания, без которых разрешение не является разрешением.
ОБЯЗАТЕЛЬНЫЕ = ("typ", "changeset_id", "audience", "expires_at", "jti",
                "fencing_token", "plan_hash", "resource_kind",
                "artifact_digest", "site_id", "registry_fingerprint")
ТИП = "execution-grant"


class GrantError(RuntimeError):
    def __init__(self, код: str, детали: str):
        super().__init__(детали)
        self.error_code, self.detail = код, детали


def _сейчас() -> _d.datetime:
    return _d.datetime.now(_d.timezone.utc)


def хэш(значение: str) -> str:
    """Безопасная ссылка на значение для evidence."""
    return hashlib.sha256(str(значение).encode("utf-8")).hexdigest()[:16]


@dataclass(frozen=True)
class Ожидания:
    """Что адаптер СОБИРАЕТСЯ сделать. Сверяется с притязаниями разрешения."""
    changeset_id: str
    site_id: str
    resource_kind: str
    plan_hash: str
    artifact_digest: str
    registry_fingerprint: str
    fencing_token: int
    audience: str = АУДИТОРИЯ


def проверить(подпись: str, полезное: dict[str, Any], ожидания: Ожидания,
              набор: K.НаборКлючей) -> dict[str, Any]:
    """Вернуть проверенные притязания или отказать с точным кодом."""
    if not подпись:
        raise GrantError("GRANT_MISSING",
                         "разрешение не предъявлено: исполнение без него "
                         "не выполняется")
    отсутствуют = [п for п in ОБЯЗАТЕЛЬНЫЕ if not полезное.get(п)]
    if отсутствуют:
        raise GrantError("GRANT_CLAIMS_INCOMPLETE",
                         f"в разрешении нет притязаний: {отсутствуют}")
    if полезное.get("typ") != ТИП:
        raise GrantError("GRANT_TYPE_INVALID",
                         f"тип {полезное.get('typ')!r} не является разрешением "
                         f"на исполнение")

    # Подпись проверяется ПЕРВОЙ среди содержательных проверок: сверять
    # притязания неподписанного разрешения бессмысленно.
    тело = json.dumps(полезное, ensure_ascii=False, sort_keys=True,
                      separators=(",", ":"))
    try:
        сведения = набор.проверить(подпись, тело)
    except K.KeyringError as ош:
        raise GrantError(ош.error_code, ош.detail) from ош

    if полезное["audience"] != ожидания.audience:
        raise GrantError(
            "GRANT_AUDIENCE_MISMATCH",
            f"разрешение адресовано {полезное['audience']!r}, а исполняет "
            f"{ожидания.audience!r}")
    if полезное["changeset_id"] != ожидания.changeset_id:
        raise GrantError("GRANT_CHANGESET_MISMATCH",
                         "разрешение выдано другому набору изменений")
    if полезное["site_id"] != ожидания.site_id:
        raise GrantError("GRANT_SITE_MISMATCH",
                         "разрешение выдано другому сайту")
    if полезное["resource_kind"] != ожидания.resource_kind:
        raise GrantError("GRANT_RESOURCE_KIND_MISMATCH",
                         "разрешение выдано ресурсу другого рода")
    if полезное["plan_hash"] != ожидания.plan_hash:
        raise GrantError("GRANT_PLAN_MISMATCH",
                         "план изменился после выдачи разрешения")
    if полезное["artifact_digest"] != ожидания.artifact_digest:
        raise GrantError("GRANT_ARTIFACT_MISMATCH",
                         "разрешение выдано на другой артефакт")
    if полезное["registry_fingerprint"] != ожидания.registry_fingerprint:
        raise GrantError("GRANT_REGISTRY_STALE",
                         "состав реестра изменился после выдачи разрешения")
    if int(полезное["fencing_token"]) != int(ожидания.fencing_token):
        raise GrantError("GRANT_FENCING_STALE",
                         "маркер ограждения не совпадает с действующей арендой")
    срок = _d.datetime.fromisoformat(
        str(полезное["expires_at"]).replace("Z", "+00:00"))
    if срок <= _сейчас():
        raise GrantError("GRANT_EXPIRED", "срок разрешения истёк")

    return {"kid": сведения["kid"], "jti_hash": хэш(полезное["jti"]),
            "audience": полезное["audience"],
            "expires_at": полезное["expires_at"]}
