"""Оснастка испытаний канонического предложения SEO-контента.

Лежит в пакете, а не в каталоге тестов: репозиторий собирает тесты в режиме
importlib, и модуль оттуда не импортируется. При импорте ничего не делает.

Детерминированная модель — здесь. Живой Qwen не вызывается ни разу: его
ответ — чистая функция от замысла, и именно поэтому черновик воспроизводим,
а отпечатки стабильны от прогона к прогону.
"""
from __future__ import annotations

import hashlib
import json
import uuid
from typing import Any

from factory.site_engine.changeset.registry_client import RegistryUnavailable

from . import schema as SCH
from .service import ArtifactStore, FactPackStore

#: Витрины испытаний. Идентификаторы заведомо не совпадают ни с одной живой.
САЙТЫ: dict[str, dict[str, Any]] = {
    "arc-seo-test-0001": {"site_id": "arc-seo-test-0001", "environment": "test",
                          "lifecycle_state": "ACTIVE", "family": "anime"},
    "arc-seo-test-0002": {"site_id": "arc-seo-test-0002", "environment": "test",
                          "lifecycle_state": "ACTIVE", "family": "anime"},
    "arc-seo-np-0003": {"site_id": "arc-seo-np-0003",
                        "environment": "non-production",
                        "lifecycle_state": "ACTIVE", "family": "anime"},
    "arc-seo-prod-0004": {"site_id": "arc-seo-prod-0004",
                          "environment": "production",
                          "lifecycle_state": "ACTIVE", "family": "anime"},
    "arc-seo-retired-0005": {"site_id": "arc-seo-retired-0005",
                             "environment": "test",
                             "lifecycle_state": "RETIRED", "family": "anime"},
}

МОДЕЛЬ = "qwen2.5-14b-instruct"
ПРОМПТ = "seo.title.v3"
ПОЛИТИКА = "policy/1.0.0"


class FakeRegistry:
    """Реестр испытаний: отвечает как versioned API, ничего не читая извне."""

    def __init__(self, версия: int = 500, сайты: dict | None = None):
        self._версия = версия
        self._сайты = dict(сайты or САЙТЫ)
        self.недоступен = False

    def версия(self) -> int:
        if self.недоступен:
            raise RegistryUnavailable("реестр недоступен (испытание)")
        return self._версия

    def сдвинуть_версию(self, на: int = 1) -> int:
        self._версия += на
        return self._версия

    def сайт(self, site_id: str):
        if self.недоступен:
            raise RegistryUnavailable("реестр недоступен (испытание)")
        return self._сайты.get(site_id)

    def сайты(self) -> list[dict]:
        if self.недоступен:
            raise RegistryUnavailable("реестр недоступен (испытание)")
        return list(self._сайты.values())


class DeterministicQwen:
    """Детерминированная модель-автор.

    Живой Qwen не вызывается: счётчик обращений открыт, и проверки на нём
    настаивают. Ответ — чистая функция от замысла, поэтому один и тот же
    замысел даёт один и тот же черновик и один и тот же отпечаток.
    """

    def __init__(self) -> None:
        self.вызовов = 0
        self.live_calls = 0        # живых обращений не бывает по устройству
        self.model_downloads = 0

    def черновик(self, замысел: dict[str, Any]) -> dict[str, Any]:
        self.вызовов += 1
        основа = SCH.канон({
            "site_id": замысел["site_id"],
            "entity_id": замысел["entity_id"],
            "surface": замысел["surface"],
            "locale": замысел["locale"],
            "model_version": МОДЕЛЬ, "prompt_version": ПРОМПТ,
        })
        текст = "Аниме " + hashlib.sha256(основа.encode()).hexdigest()[:16]
        содержимое = {"surface": замысел["surface"], "locale": замысел["locale"],
                      "text": текст}
        return {"content": содержимое, "model_version": МОДЕЛЬ,
                "prompt_version": ПРОМПТ,
                "revision_id": "rev-" + hashlib.sha256(
                    основа.encode()).hexdigest()[:16]}


def замысел(site_id: str = "arc-seo-test-0001", *,
            entity_id: str = "anime-0001", surface: str = "title",
            locale: str = "ru") -> dict[str, Any]:
    return {"site_id": site_id, "entity_id": entity_id,
            "entity_kind": "anime.title", "surface": surface, "locale": locale}


def собрать_заявку(*, реестр, артефакты: ArtifactStore, модель: DeterministicQwen,
                   зам: dict[str, Any] | None = None,
                   idempotency_key: str | None = None,
                   **переопределения) -> dict[str, Any]:
    """Полный путь до канонической заявки: факты → черновик → предложение."""
    з = зам or замысел()
    снимок = FactPackStore(реестр).снимок(з["site_id"])
    черновик = модель.черновик(з)
    байты = SCH.канон(черновик["content"]).encode("utf-8")
    цифра = артефакты.положить(байты)
    заявка = {
        "schema_version": SCH.SCHEMA_VERSION,
        "resource_kind": SCH.RESOURCE_KIND,
        "site_id": з["site_id"],
        "entity_id": з["entity_id"],
        "entity_kind": з["entity_kind"],
        "surface": з["surface"],
        "locale": з["locale"],
        "fact_pack_ref": f"factpack:{з['site_id']}:{снимок['sha256'][:12]}",
        "source_snapshot_sha256": снимок["sha256"],
        "artifact_ref": f"sha256:{цифра}",
        "artifact_digest": цифра,
        "draft_revision_id": черновик["revision_id"],
        "draft_revision_digest": hashlib.sha256(байты).hexdigest(),
        "intent_id": "intent-" + hashlib.sha256(
            SCH.канон(з).encode()).hexdigest()[:12],
        "model_version": черновик["model_version"],
        "prompt_version": черновик["prompt_version"],
        "policy_version": ПОЛИТИКА,
        "requested_by": "service:seo",
        "correlation_id": "corr-" + hashlib.sha256(
            SCH.канон(з).encode()).hexdigest()[:12],
        "causation_id": "cause-" + hashlib.sha256(
            SCH.канон(з).encode()).hexdigest()[:12],
        "idempotency_key": idempotency_key or ("idem-" + uuid.uuid4().hex[:16]),
        "operations": [{"op": "set", "path": f"/{з['surface']}",
                        "value_digest": hashlib.sha256(
                            черновик["content"]["text"].encode()).hexdigest()}],
    }
    заявка.update(переопределения)
    return заявка
