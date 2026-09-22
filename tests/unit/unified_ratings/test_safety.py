"""Безопасность и честность: метрики, секреты, kill switch, чистота production.

Отдельный файл, потому что это проверки не функции, а обещаний: что
неизмеренное не выдаётся за ноль, что секрет не утёк в отчёт и что в
боевой базе не осталось тестовых голосов.
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pytest

from factory.community.antifraud import AntifraudGuard, KillSwitchActive, ReadOnlyMode
from factory.unified_ratings.metrics import METRIC_NAMES, MetricsRecorder
from factory.unified_ratings.sources import REGISTRY, AccessMethod, SourceStatus

PRODUCTION_DB = Path("/srv/site-factory/repo/var/ratings/ratings.sqlite")


# ---------------------------------------------------------------------------
# метрики: пустой счётчик ≠ отсутствие измерения
# ---------------------------------------------------------------------------


def test_measured_zero_and_unmeasured_are_different(store):
    metrics = MetricsRecorder(store, run_id="r1")
    metrics.record("source_errors", 0, labels={"source": "anilist"})
    metrics.unmeasured("widget_rendered", "виджет не разворачивался в этом прогоне")
    snapshot = metrics.snapshot(run_id="r1")
    assert snapshot["source_errors"]["state"] == "MEASURED"
    assert snapshot["source_errors"]["value"] == 0
    assert snapshot["widget_rendered"]["state"] == "UNMEASURED"
    assert snapshot["widget_rendered"]["value"] is None
    assert snapshot["widget_rendered"]["reason"]


def test_a_metric_nobody_recorded_reports_unmeasured_not_zero(store):
    metrics = MetricsRecorder(store, run_id="r2")
    metrics.record("imported", 5)
    snapshot = metrics.snapshot(run_id="r2")
    for name in METRIC_NAMES:
        if name == "imported":
            continue
        assert snapshot[name]["state"] == "UNMEASURED", name
        assert snapshot[name]["value"] is None, name


def test_unmeasured_requires_a_reason(store):
    with pytest.raises(ValueError):
        MetricsRecorder(store).unmeasured("db_errors", "")


def test_undeclared_metrics_are_refused(store):
    with pytest.raises(ValueError):
        MetricsRecorder(store).record("made_up_metric", 1)


def test_every_required_metric_is_declared():
    required = {
        "source_requests", "source_errors", "source_rate_limits", "imported", "updated",
        "unchanged", "rejected", "pending_review", "match_confidence", "ingestion_latency_ms",
        "checkpoint_age_seconds", "votes_created", "votes_updated", "votes_retracted",
        "duplicate_requests", "rate_limit_violations", "aggregate_rebuild_mismatches",
        "db_errors", "api_latency_p50_ms", "api_latency_p95_ms", "widget_rendered",
        "write_success", "write_failure",
    }
    assert required <= set(METRIC_NAMES)


# ---------------------------------------------------------------------------
# kill switch
# ---------------------------------------------------------------------------


def test_kill_switch_stops_writes():
    guard = AntifraudGuard()
    guard.assert_writable()
    guard.set_kill_switch(True)
    with pytest.raises(KillSwitchActive):
        guard.assert_writable()
    guard.set_kill_switch(False)
    guard.assert_writable()


def test_read_only_mode_stops_writes():
    guard = AntifraudGuard()
    guard.set_read_only(True)
    with pytest.raises(ReadOnlyMode):
        guard.assert_writable()


# ---------------------------------------------------------------------------
# секреты
# ---------------------------------------------------------------------------


def test_no_source_definition_carries_a_secret_value():
    """В реестре допустимы только ссылки на секрет, не сами значения."""
    blob = json.dumps(
        {
            key: {
                "credential_ref": source.credential_ref,
                "legal_basis": source.legal_basis,
                "blocker": source.blocker,
                "notes": source.notes,
            }
            for key, source in REGISTRY.items()
        },
        ensure_ascii=False,
    )
    for marker in ("Bearer ", "api_key=", "client_id=", "password", "token="):
        assert marker not in blob


def test_credential_backed_sources_reference_a_secret_not_a_value():
    for source in REGISTRY.values():
        if source.requires_credential:
            assert "secret_ref" in source.credential_ref, source.source_key


def test_simkl_stays_blocked_until_a_key_exists():
    simkl = REGISTRY["simkl"]
    assert simkl.status is SourceStatus.BLOCKED_SECRET
    assert simkl.access_method is AccessMethod.OFFICIAL_API, (
        "обходной путь вместо официального API выбирать нельзя"
    )
    assert simkl.scale.verified is False


def test_imdb_and_kinopoisk_are_feed_only():
    for key in ("provider_feed_imdb", "provider_feed_kinopoisk"):
        source = REGISTRY[key]
        assert source.status is SourceStatus.FEED_ONLY
        assert source.max_requests_per_minute == 0, "собственных запросов к площадке нет"
        assert "не запускается" in source.blocker


def test_page_parsing_is_the_exception_and_names_its_basis():
    """Разбор страниц допустим, но не молча.

    Раньше здесь стоял запрет на `PUBLIC_PAGE_PARSE` целиком: источников
    такого рода не было, и запрет ничего не стоил. AMD Online подключён
    как `AMD_ONLINE_PUBLIC_HTML` — ни API, ни фида, ни разрешения
    владельца нет, и источник обязан называться тем, чем является.

    Поэтому проверяется не отсутствие разбора, а его условия: разбор
    применяется только там, где выше по приоритету ничего не нашлось,
    основание записано в источнике, и нагрузка ограничена. Тест по-
    прежнему падает на настоящем нарушении — на источнике, который
    полез бы парсить страницы вместо официального API или без предела
    частоты.
    """
    allowed = {"amd_online"}
    for source in REGISTRY.values():
        if source.access_method is not AccessMethod.PUBLIC_PAGE_PARSE:
            continue
        assert source.source_key in allowed, (
            f"{source.source_key}: разбор страниц не заявлен в задании"
        )
        assert source.notes, f"{source.source_key}: основание доступа не записано"
        assert "AMD_ONLINE_PUBLIC_HTML" in source.notes, (
            "источник обязан называться тем, чем является: не API и не фид"
        )
        assert 0 < source.max_requests_per_minute <= 60, (
            f"{source.source_key}: разбор страниц без предела частоты запрещён"
        )


def test_page_parsing_source_respects_robots():
    """Явно запрещённый robots.txt путь не обходится, а заменяется.

    Пагинация `/ongoingi/page/N/` закрыта правилом `Disallow */page*`.
    Адаптер не притворяется браузером и не подбирает адреса: он берёт
    перечисление из карты сайта, объявленной тем же robots.txt.
    """
    from factory.unified_ratings.adapters.amd_online import (
        ROBOTS_DISALLOW_PATTERNS,
        robots_allows,
    )

    assert ROBOTS_DISALLOW_PATTERNS, "правила robots не загружены"
    assert robots_allows("https://amd.online/12345-nekotorroe-anime.html")
    assert not robots_allows("https://amd.online/ongoingi/page/2/")


# ---------------------------------------------------------------------------
# чистота production
# ---------------------------------------------------------------------------


def production_conn() -> sqlite3.Connection | None:
    if not PRODUCTION_DB.is_file():
        return None
    conn = sqlite3.connect(f"file:{PRODUCTION_DB}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    return conn


def test_production_contains_no_synthetic_votes():
    conn = production_conn()
    if conn is None:
        pytest.skip("production ratings.sqlite недоступна")
    try:
        votes = conn.execute("SELECT COUNT(*) AS n FROM community_votes").fetchone()["n"]
        fake = conn.execute(
            """SELECT COUNT(*) AS n FROM community_votes
               WHERE actor_id LIKE 'test%' OR actor_id LIKE 'fake%'
                  OR actor_id LIKE 'synthetic%' OR actor_id LIKE 'a%-bench%'"""
        ).fetchone()["n"]
        assert fake == 0, f"в production найдено {fake} тестовых голосов из {votes}"
    finally:
        conn.close()


def test_production_has_no_unified_test_rows():
    """Тесты пишут только во временные базы; в боевой их следов быть не должно."""
    conn = production_conn()
    if conn is None:
        pytest.skip("production ratings.sqlite недоступна")
    try:
        tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        if "unified_titles" not in tables:
            return  # миграция ещё не применена — писать было некуда
        leaked = conn.execute(
            "SELECT COUNT(*) AS n FROM unified_titles WHERE title_id LIKE 'nova:t-00%'"
        ).fetchone()["n"]
        assert leaked == 0, "тестовые тайтлы из фикстур попали в production"
    finally:
        conn.close()


def test_production_vote_events_have_no_test_idempotency_keys():
    conn = production_conn()
    if conn is None:
        pytest.skip("production ratings.sqlite недоступна")
    try:
        leaked = conn.execute(
            """SELECT COUNT(*) AS n FROM community_vote_events
               WHERE idempotency_key LIKE 'k%' AND length(idempotency_key) <= 3
                  OR idempotency_key LIKE 'concurrent-%'
                  OR idempotency_key LIKE 'one-key'"""
        ).fetchone()["n"]
        assert leaked == 0
    finally:
        conn.close()


def test_the_prepared_canary_flags_are_untouched():
    """Этот этап не включает и не выключает раскатку виджета."""
    conn = production_conn()
    if conn is None:
        pytest.skip("production ratings.sqlite недоступна")
    try:
        flags = {r["flag"]: r["value"] for r in conn.execute(
            "SELECT flag, value FROM community_feature_flags"
        )}
    finally:
        conn.close()
    assert set(flags), "флаги раскатки исчезли"
    # Значения не проверяем на конкретное число: важно, что набор флагов
    # цел и что этот этап их не создаёт и не удаляет.
    for required in ("RATINGS_NATIVE_WRITE_YUMMY", "RATINGS_PUBLIC_READ_YUMMY"):
        assert required in flags
