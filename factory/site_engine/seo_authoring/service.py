"""Канонический путь предложения SEO-контента.

Единственное место, где предложение становится устойчивой записью. Ни один
другой участник — ни SEO, ни тем более модель — не пишет каноническую строку
сам: он подаёт заявку, а запись делает эта служба, и только после того, как
проверены схема, права, реестр и отпечатки.

Запись предложения и создание набора изменений выполняются ОДНОЙ транзакцией
в одном хранилище. Разнести их значило бы допустить предложение без набора
или набор без предложения — и оба состояния выглядели бы как исправные.
"""
from __future__ import annotations

import hashlib
import json
import sqlite3
import uuid
from typing import Any

from factory.site_engine.changeset import model as M
from factory.site_engine.changeset import store as CS
from factory.site_engine.changeset.registry_client import (
    RegistryClient, RegistryUnavailable)

from . import schema as SCH
from .schema import ProposalRejected

#: Кто вправе подавать предложение. Модель сюда не входит: она автор
#: содержимого, а не заказчик канонической записи.
ЗАКАЗЧИКИ = frozenset({"seo", "architect"})

#: Кто делает устойчивую запись. Ровно один.
DURABLE_WRITER = "control-plane"

СХЕМА_ТАБЛИЦ = """
CREATE TABLE IF NOT EXISTS seo_content_proposal (
  proposal_id            TEXT PRIMARY KEY,
  schema_version         TEXT NOT NULL,
  resource_kind          TEXT NOT NULL,
  resource_version       TEXT NOT NULL,
  changeset_id           TEXT NOT NULL REFERENCES changeset(changeset_id),
  site_id                TEXT NOT NULL,
  entity_id              TEXT NOT NULL,
  entity_kind            TEXT NOT NULL,
  surface                TEXT NOT NULL,
  locale                 TEXT NOT NULL,
  fact_pack_ref          TEXT NOT NULL,
  source_snapshot_sha256 TEXT NOT NULL,
  artifact_ref           TEXT NOT NULL,
  artifact_digest        TEXT NOT NULL,
  draft_revision_id      TEXT,
  draft_revision_digest  TEXT,
  intent_id              TEXT,
  model_version          TEXT NOT NULL,
  prompt_version         TEXT NOT NULL,
  policy_version         TEXT NOT NULL,
  content_author         TEXT NOT NULL,
  requested_by           TEXT NOT NULL,
  requester_service      TEXT NOT NULL,
  durable_writer         TEXT NOT NULL,
  owner_service          TEXT NOT NULL,
  audience               TEXT NOT NULL,
  target_environment     TEXT NOT NULL,
  correlation_id         TEXT NOT NULL,
  causation_id           TEXT NOT NULL,
  idempotency_key        TEXT NOT NULL,
  payload_digest         TEXT NOT NULL,
  operations             TEXT NOT NULL,
  accepted_at            TEXT NOT NULL,
  UNIQUE (requester_service, idempotency_key)
);
CREATE INDEX IF NOT EXISTS scp_site ON seo_content_proposal(site_id);
CREATE INDEX IF NOT EXISTS scp_changeset ON seo_content_proposal(changeset_id);
"""


def подготовить(соед: sqlite3.Connection) -> None:
    соед.executescript(СХЕМА_ТАБЛИЦ)


class FactPackStore:
    """Снимок фактов реестра, по которым составлен текст.

    Отдельного хранилища не заводит: это тонкая обёртка над тем, что уже
    отдаёт реестр. Нужна ради одного — посчитать отпечаток одинаково у
    заказчика и у нас.
    """

    def __init__(self, реестр: RegistryClient):
        self.реестр = реестр

    def снимок(self, site_id: str) -> dict[str, Any]:
        сайт = self.реестр.сайт(site_id)
        if сайт is None:
            raise ProposalRejected("SITE_ID_UNKNOWN",
                                   f"site_id {site_id!r} реестру неизвестен; "
                                   f"домен идентификатором не является")
        # В отпечаток входит только то, от чего зависит текст. Включить сюда
        # всё подряд значило бы объявлять предложение устаревшим от любой
        # посторонней правки реестра.
        факты = {
            "site_id": сайт["site_id"],
            "environment": сайт.get("environment"),
            "lifecycle_state": сайт.get("lifecycle_state"),
            "registry_version": self.реестр.версия(),
        }
        return {"facts": факты, "sha256": SCH.отпечаток(факты)}


class ArtifactStore:
    """Содержимое черновика, адресуемое отпечатком.

    Хранит байты по их же хэшу. Подменить содержимое, не изменив ссылку,
    поэтому нельзя: ссылка и есть хэш.
    """

    def __init__(self) -> None:
        self._данные: dict[str, bytes] = {}

    def положить(self, содержимое: bytes) -> str:
        х = hashlib.sha256(содержимое).hexdigest()
        self._данные[х] = содержимое
        return х

    def отпечаток(self, ref: str) -> str | None:
        # Ссылка вида "sha256:<hex>" либо сам hex.
        х = ref.split(":", 1)[1] if ref.startswith("sha256:") else ref
        return х if х in self._данные else None


class SeoProposalService:
    """Приём канонического предложения SEO-контента."""

    def __init__(self, соед: sqlite3.Connection, *,
                 реестр: RegistryClient, артефакты: ArtifactStore,
                 факты: FactPackStore | None = None):
        self.соед = соед
        self.реестр = реестр
        self.артефакты = артефакты
        self.факты = факты or FactPackStore(реестр)
        подготовить(соед)

    # --- вспомогательное --------------------------------------------------

    @staticmethod
    def _отпечаток_заявки(заявка: dict[str, Any]) -> str:
        # В отпечаток не входят поля, выводимые сервером: иначе повтор с
        # другим присланным окружением считался бы другим содержимым, хотя
        # сервер всё равно выведет своё.
        тело = {k: v for k, v in заявка.items() if k not in SCH.ВЫВОДИМЫЕ}
        return SCH.отпечаток(тело)

    def _разрешить_сайт(self, site_id: str) -> dict[str, Any]:
        try:
            сайт = self.реестр.сайт(site_id)
        except RegistryUnavailable as e:
            raise ProposalRejected("REGISTRY_UNAVAILABLE", str(e), 503) from e
        if сайт is None:
            raise ProposalRejected(
                "SITE_ID_UNKNOWN",
                f"site_id {site_id!r} реестру неизвестен; домен "
                f"идентификатором не является")
        if сайт.get("lifecycle_state") not in ("ACTIVE", "DRAFT"):
            raise ProposalRejected(
                "LIFECYCLE_FORBIDDEN",
                f"{site_id}: состояние {сайт.get('lifecycle_state')} "
                f"не допускает изменений", 409)
        return сайт

    # --- приём ------------------------------------------------------------

    def принять(self, заявка: dict[str, Any], *, requester_service: str,
                actor_id: str, actor_type: str,
                content_author: str = "qwen") -> dict[str, Any]:
        """Проверить и, если всё сошлось, устойчиво записать предложение."""
        # 1. Кто просит. Опознание — снаружи, здесь только права.
        if actor_type == "MODEL":
            raise ProposalRejected(
                "MODEL_DURABLE_WRITE_DENIED",
                "актор-модель не подаёт каноническую запись: он автор "
                "содержимого, а заказчиком выступает служба", 403)
        if requester_service not in ЗАКАЗЧИКИ:
            raise ProposalRejected(
                "REQUESTER_NOT_ALLOWED",
                f"служба {requester_service} не вправе подавать предложения "
                f"SEO-контента", 403)
        if M.PROPOSER not in M.роли_службы(requester_service):
            raise ProposalRejected(
                "ROLE_NOT_GRANTED",
                f"у службы {requester_service} нет роли {M.PROPOSER}", 403)

        # 2. Схема. До обращения к реестру и хранилищу.
        проверенная = SCH.проверить(заявка)

        # 3. Заявленный заказчик обязан совпасть с опознанным.
        заявлен = проверенная["requested_by"].removeprefix("service:")
        if заявлен != requester_service:
            raise ProposalRejected(
                "ACTOR_SPOOFED",
                f"запрос объявляет заказчиком {заявлен!r}, а предъявленный "
                f"токен принадлежит {requester_service!r}", 403)

        # 4. Сайт, окружение и аудитория выводятся сервером.
        сайт = self._разрешить_сайт(проверенная["site_id"])
        выведено = {
            "target_environment": сайт.get("environment") or "UNKNOWN",
            "owner_service": "seo",
            "audience": "internal",
            "site_kind": сайт.get("family") or "generic",
        }
        for поле, значение in выведено.items():
            присланное = проверенная.get(поле)
            if присланное is not None and str(присланное) != str(значение):
                raise ProposalRejected(
                    "DERIVED_FIELD_MISMATCH",
                    f"{поле}: прислано {присланное!r}, сервер вывёл "
                    f"{значение!r}; это поле назначает не отправитель", 403)
        проверенная.update(выведено)

        # 5. Production в этой версии недостижим по устройству.
        if выведено["target_environment"] not in ("test", "non-production"):
            raise ProposalRejected(
                "PRODUCTION_TARGET_DENIED",
                f"цель в окружении {выведено['target_environment']!r}: "
                f"применение вне test и non-production выключено", 403)

        # 6. Отпечатки: факты не устарели, содержимое то самое.
        снимок = self.факты.снимок(проверенная["site_id"])
        if снимок["sha256"] != проверенная["source_snapshot_sha256"]:
            raise ProposalRejected(
                "SOURCE_SNAPSHOT_STALE",
                f"снимок фактов разошёлся: предложение составлено по "
                f"{проверенная['source_snapshot_sha256'][:12]}, реестр даёт "
                f"{снимок['sha256'][:12]}", 409)
        факт_артефакта = self.артефакты.отпечаток(проверенная["artifact_ref"])
        if факт_артефакта is None:
            raise ProposalRejected("ARTIFACT_NOT_FOUND",
                                   "содержимое черновика не найдено по ссылке")
        if факт_артефакта != проверенная["artifact_digest"]:
            raise ProposalRejected(
                "ARTIFACT_DIGEST_MISMATCH",
                f"отпечаток содержимого не совпал: заявлен "
                f"{проверенная['artifact_digest'][:12]}, фактический "
                f"{факт_артефакта[:12]}", 409)

        отпечаток_заявки = self._отпечаток_заявки(проверенная)

        # 7. Повтор. Тот же ключ с тем же содержимым — тот же результат.
        есть = self.соед.execute(
            "SELECT * FROM seo_content_proposal WHERE requester_service=? AND "
            "idempotency_key=?",
            (requester_service, проверенная["idempotency_key"])).fetchone()
        if есть is not None:
            if есть["payload_digest"] != отпечаток_заявки:
                raise ProposalRejected(
                    "IDEMPOTENCY_CONFLICT",
                    "ключ идемпотентности уже использован с другим "
                    "содержимым", 409)
            return {"proposal_id": есть["proposal_id"],
                    "changeset_id": есть["changeset_id"],
                    "idempotent_replay": True,
                    "resource_kind": SCH.RESOURCE_KIND,
                    "target_environment": есть["target_environment"]}

        # 8. Устойчивая запись. Предложение и набор — одной транзакцией.
        return self._записать(проверенная, requester_service=requester_service,
                              actor_id=actor_id, actor_type=actor_type,
                              content_author=content_author,
                              отпечаток_заявки=отпечаток_заявки,
                              снимок=снимок)

    def _записать(self, п: dict[str, Any], *, requester_service: str,
                  actor_id: str, actor_type: str, content_author: str,
                  отпечаток_заявки: str, снимок: dict) -> dict[str, Any]:
        proposal_id = "scp-" + uuid.uuid4().hex[:20]
        т = CS.сейчас()
        заявка_набора = {
            "resource_type": SCH.RESOURCE_KIND,
            "resource_id": f"{п['entity_id']}:{п['surface']}:{п['locale']}",
            "operation_type": "update",
            "target_site_ids": [п["site_id"]],
            "requested_change": {
                "proposal_id": proposal_id,
                "entity_id": п["entity_id"],
                "entity_kind": п["entity_kind"],
                "surface": п["surface"],
                "locale": п["locale"],
                "artifact_digest": п["artifact_digest"],
                "operations": п["operations"],
            },
            "idempotency_key": f"seo-proposal:{п['idempotency_key']}",
            "correlation_id": п["correlation_id"],
            "causation_id": п["causation_id"],
            "policy_version": п["policy_version"],
        }
        try:
            with self.соед:
                # Набор изменений создаёт control-plane — единственный
                # устойчивый писатель. Служба-заказчик здесь только названа.
                итог = CS.создать(self.соед, заявка_набора,
                                  producer_service=DURABLE_WRITER,
                                  actor_id=f"service:{DURABLE_WRITER}",
                                  actor_type="SERVICE")
                self.соед.execute(
                    "INSERT INTO seo_content_proposal("
                    "proposal_id, schema_version, resource_kind, "
                    "resource_version, changeset_id, site_id, entity_id, "
                    "entity_kind, surface, locale, fact_pack_ref, "
                    "source_snapshot_sha256, artifact_ref, artifact_digest, "
                    "draft_revision_id, draft_revision_digest, intent_id, "
                    "model_version, prompt_version, policy_version, "
                    "content_author, requested_by, requester_service, "
                    "durable_writer, owner_service, audience, "
                    "target_environment, correlation_id, causation_id, "
                    "idempotency_key, payload_digest, operations, accepted_at"
                    ") VALUES(" + ",".join("?" * 33) + ")",
                    (proposal_id, п["schema_version"], SCH.RESOURCE_KIND,
                     SCH.RESOURCE_VERSION, итог["changeset_id"], п["site_id"],
                     п["entity_id"], п["entity_kind"], п["surface"],
                     п["locale"], п["fact_pack_ref"],
                     п["source_snapshot_sha256"], п["artifact_ref"],
                     п["artifact_digest"], п.get("draft_revision_id"),
                     п.get("draft_revision_digest"), п.get("intent_id"),
                     п["model_version"], п["prompt_version"],
                     п["policy_version"], content_author, п["requested_by"],
                     requester_service, DURABLE_WRITER, п["owner_service"],
                     п["audience"], п["target_environment"],
                     п["correlation_id"], п["causation_id"],
                     п["idempotency_key"], отпечаток_заявки,
                     CS.канон(п["operations"]), т))
                # Событие предложения — тем же ящиком, что и всё остальное.
                CS._в_ящик(self.соед, итог["changeset_id"],
                           "seo.changeset.proposed.v1", {
                               "changeset_id": итог["changeset_id"],
                               "proposal_id": proposal_id,
                               "status": итог["status"],
                               "resource_type": SCH.RESOURCE_KIND,
                               "resource_id": заявка_набора["resource_id"],
                               "target_site_ids": [п["site_id"]],
                               "producer_service": DURABLE_WRITER,
                               "actor_id": f"service:{requester_service}",
                               "content_author": content_author,
                               "owner_service": п["owner_service"],
                               "correlation_id": п["correlation_id"],
                               "causation_id": п["causation_id"],
                               "occurred_at": т,
                           },
                           ключ=f"{итог['changeset_id']}:seo.changeset.proposed.v1")
        except sqlite3.IntegrityError:
            # Кто-то успел первым между проверкой и вставкой. Побеждает
            # первый, остальные получают его результат — это и есть
            # идемпотентность, а не совпадение.
            есть = self.соед.execute(
                "SELECT * FROM seo_content_proposal WHERE requester_service=? "
                "AND idempotency_key=?",
                (requester_service, п["idempotency_key"])).fetchone()
            if есть is None:
                raise
            if есть["payload_digest"] != отпечаток_заявки:
                raise ProposalRejected("IDEMPOTENCY_CONFLICT",
                                       "ключ уже использован с другим "
                                       "содержимым", 409) from None
            return {"proposal_id": есть["proposal_id"],
                    "changeset_id": есть["changeset_id"],
                    "idempotent_replay": True,
                    "resource_kind": SCH.RESOURCE_KIND,
                    "target_environment": есть["target_environment"]}
        return {"proposal_id": proposal_id,
                "changeset_id": итог["changeset_id"],
                "idempotent_replay": False,
                "resource_kind": SCH.RESOURCE_KIND,
                "target_environment": п["target_environment"],
                "accepted_at": т}

    # --- чтение -----------------------------------------------------------

    def получить(self, proposal_id: str) -> dict[str, Any] | None:
        р = self.соед.execute(
            "SELECT * FROM seo_content_proposal WHERE proposal_id=?",
            (proposal_id,)).fetchone()
        if р is None:
            return None
        d = dict(р)
        d["operations"] = json.loads(d["operations"])
        return d
