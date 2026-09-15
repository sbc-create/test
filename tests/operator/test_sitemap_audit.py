"""Сверка карты сайта с каталогом."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from seo_operator.sitemap_audit import FRESH_WINDOW, findings, reconcile

NOW = datetime(2026, 9, 15, 17, 0, tzinfo=timezone.utc)
HOST = "lordserial33.biz"


def url(slug: str, host: str = HOST) -> str:
    return f"https://{host}/title/{slug}/"


def catalog(**slugs: str | None) -> dict[str, str | None]:
    return dict(slugs)


def test_matching_sitemap_is_clean() -> None:
    result = reconcile(
        "lords-02",
        [url("a"), url("b")],
        catalog(a="2026-01-01T00:00:00Z", b="2026-01-01T00:00:00Z"),
        canonical_host=HOST,
        now=NOW,
    )
    assert result.clean
    assert findings(result) == []


def test_url_without_a_catalog_entry_is_a_finding() -> None:
    result = reconcile(
        "lords-02",
        [url("a"), url("ghost")],
        catalog(a="2026-01-01T00:00:00Z"),
        canonical_host=HOST,
        now=NOW,
    )
    assert result.stray == ["ghost"]
    assert [f["id"] for f in findings(result)] == ["SMP-002"]


def test_foreign_host_in_the_sitemap_is_critical() -> None:
    result = reconcile(
        "lords-02",
        [url("a"), url("a", host="lordfilm47.space")],
        catalog(a="2026-01-01T00:00:00Z"),
        canonical_host=HOST,
        now=NOW,
    )
    finding = findings(result)[0]
    assert finding["id"] == "SMP-001"
    assert finding["severity"] == "критично"


def test_duplicate_entries_are_reported() -> None:
    result = reconcile(
        "lords-02",
        [url("a"), url("a")],
        catalog(a="2026-01-01T00:00:00Z"),
        canonical_host=HOST,
        now=NOW,
    )
    assert result.duplicated == ["a"]
    assert "SMP-003" in [f["id"] for f in findings(result)]


def test_freshly_added_entry_missing_from_the_sitemap_is_not_a_finding() -> None:
    """Позиция моложе окна обновления карты — задержка рендера, а не потеря.

    Ровно это и наблюдалось на трёх витринах Lords: все отсутствующие позиции
    появились в каталоге в тот же день. Объявить это дефектом значит приучить
    читателя отчёта пропускать раздел.
    """
    fresh = (NOW - timedelta(hours=2)).isoformat().replace("+00:00", "Z")
    result = reconcile(
        "lords-02", [url("a")], catalog(a="2026-01-01T00:00:00Z", b=fresh),
        canonical_host=HOST, now=NOW,
    )
    assert result.missing_fresh == ["b"]
    assert result.missing_stale == []
    assert result.clean
    assert findings(result) == []


def test_long_missing_entry_is_a_finding() -> None:
    stale = (NOW - FRESH_WINDOW - timedelta(hours=1)).isoformat().replace("+00:00", "Z")
    result = reconcile(
        "lords-02", [url("a")], catalog(a="2026-01-01T00:00:00Z", b=stale),
        canonical_host=HOST, now=NOW,
    )
    assert result.missing_stale == ["b"]
    assert not result.clean
    assert "SMP-004" in [f["id"] for f in findings(result)]


def test_unknown_first_seen_counts_as_old() -> None:
    """Молодость позиции надо доказать, а не предположить.

    Иначе любая запись без отметки времени бесшумно выпадает из проверки.
    """
    result = reconcile(
        "lords-02", [url("a")], catalog(a="2026-01-01T00:00:00Z", b=None),
        canonical_host=HOST, now=NOW,
    )
    assert result.missing_stale == ["b"]


def test_unparseable_first_seen_also_counts_as_old() -> None:
    result = reconcile(
        "lords-02", [url("a")], catalog(a="2026-01-01T00:00:00Z", b="позавчера"),
        canonical_host=HOST, now=NOW,
    )
    assert result.missing_stale == ["b"]


def test_non_entity_urls_are_counted_but_not_matched() -> None:
    """Главная и разделы в карте есть, а позициями каталога не являются."""
    result = reconcile(
        "lords-02",
        [f"https://{HOST}/", f"https://{HOST}/catalog/", url("a")],
        catalog(a="2026-01-01T00:00:00Z"),
        canonical_host=HOST,
        now=NOW,
    )
    assert result.sitemap_total == 3
    assert result.stray == []
    assert result.clean


def test_measured_lords_shape_reconciles_clean() -> None:
    """Форма измерения 2026-09-15: мусора нет, отсутствуют только свежие."""
    fresh = (NOW - timedelta(hours=8)).isoformat().replace("+00:00", "Z")
    old = "2026-05-01T00:00:00Z"
    cat = {f"t{i}": old for i in range(100)}
    cat.update({f"new{i}": fresh for i in range(27)})
    result = reconcile(
        "lords-02", [url(f"t{i}") for i in range(100)], cat, canonical_host=HOST, now=NOW,
    )
    assert (result.stray, result.duplicated, result.foreign_host) == ([], [], [])
    assert len(result.missing_fresh) == 27
    assert result.missing_stale == []
    assert result.clean
