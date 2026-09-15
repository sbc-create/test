"""Согласованность слоёв запрета индексации."""

from __future__ import annotations

from seo_operator.indexing_lock import CLOSED, MIXED, OPEN, findings, read_state, summarize

CLOSED_HEADERS = "HTTP/2 200\r\nx-robots-tag: noindex, nofollow\r\n"
OPEN_HEADERS = "HTTP/2 200\r\ncontent-type: text/html\r\n"
CLOSED_ROBOTS = "User-agent: *\nDisallow: /\n"
OPEN_ROBOTS = "User-agent: *\nAllow: /\n"
CLOSED_HTML = '<meta name="robots" content="noindex, nofollow">'
OPEN_HTML = '<meta name="robots" content="index, follow">'


def state(**kw):
    defaults = {
        "site_id": "yummyani-site",
        "response_headers": CLOSED_HEADERS,
        "robots_txt": CLOSED_ROBOTS,
        "html": CLOSED_HTML,
        "profile_indexing_enabled": False,
    }
    defaults.update(kw)
    return read_state(defaults.pop("site_id"), **defaults)


def test_all_four_layers_closed_is_clean() -> None:
    s = state()
    assert s.verdict == CLOSED
    assert s.open_layers == ()
    assert findings(s) == []


def test_all_four_layers_open_is_not_a_finding() -> None:
    """Открытый сайт — решение владельца, а не дефект. Проверка о согласованности."""
    s = state(
        response_headers=OPEN_HEADERS,
        robots_txt=OPEN_ROBOTS,
        html=OPEN_HTML,
        profile_indexing_enabled=True,
    )
    assert s.verdict == OPEN
    assert findings(s) == []


def test_the_real_2026_09_15_drift_is_critical() -> None:
    """Ровно то, что произошло на yummyani.site и чего цикл не заметил.

    Мета-тег выкатили открытым, заголовок и robots.txt остались запрещающими.
    Снаружи сайт по-прежнему не индексировался, и отчёт, считающий только
    «индексируется или нет», показал бы прежнее благополучие.
    """
    s = state(html=OPEN_HTML)
    assert s.verdict == MIXED
    assert "meta_robots" in s.open_layers
    assert "x_robots_tag" in s.closed_layers
    found = findings(s)
    assert [f["id"] for f in found] == ["LCK-001"]
    assert found[0]["severity"] == "критично"
    assert "meta_robots" in found[0]["summary"]


def test_unreadable_profile_counts_as_not_closed() -> None:
    """Закрытость надо подтвердить, а не предположить.

    Предположение здесь ошибается ровно в ту сторону, в которую нельзя.
    """
    s = state(profile_indexing_enabled=None)
    assert "profile_flag" in s.open_layers
    assert s.verdict == MIXED


def test_profile_flag_true_means_that_layer_is_open() -> None:
    s = state(profile_indexing_enabled=True)
    assert "profile_flag" in s.open_layers


def test_partial_robots_txt_does_not_count_as_closed() -> None:
    """`Disallow: /catalog` закрывает раздел, а не сайт."""
    s = state(robots_txt="User-agent: *\nDisallow: /catalog\n")
    assert "robots_txt" in s.open_layers


def test_missing_meta_tag_counts_as_open() -> None:
    s = state(html="<html><head></head></html>")
    assert "meta_robots" in s.open_layers


def test_header_case_does_not_matter() -> None:
    s = state(response_headers="HTTP/2 200\r\nX-Robots-Tag: NOINDEX, NOFOLLOW\r\n")
    assert "x_robots_tag" in s.closed_layers


def test_summary_counts_partial_separately_from_open() -> None:
    """Частично снятый замок нельзя складывать ни с закрытыми, ни с открытыми."""
    states = [
        state(),
        state(site_id="yummyani-org"),
        state(site_id="yummyani-biz", html=OPEN_HTML),
        state(
            site_id="demo",
            response_headers=OPEN_HEADERS,
            robots_txt=OPEN_ROBOTS,
            html=OPEN_HTML,
            profile_indexing_enabled=True,
        ),
    ]
    summary = summarize(states)
    assert summary == {
        "total": 4,
        "closed": 2,
        "mixed": 1,
        "open": 1,
        "mixed_sites": ["yummyani-biz"],
    }


def test_unavailable_profile_source_is_silence_not_alarm() -> None:
    """Источника профиля нет в этой раскладке — слой не измерялся.

    Считать неизмеренный слой открытым значило бы объявить расхождение сразу на
    всех витринах: ложная тревога вместо настоящей, после которой настоящую
    перестают читать.
    """
    s = read_state(
        "yummyani-site",
        response_headers=CLOSED_HEADERS,
        robots_txt=CLOSED_ROBOTS,
        html=CLOSED_HTML,
        profile_indexing_enabled=None,
        profile_measured=False,
    )
    assert s.verdict == CLOSED
    assert s.unmeasured_layers == ("profile_flag",)
    assert findings(s) == []


def test_drift_is_still_caught_without_the_profile_layer() -> None:
    s = read_state(
        "yummyani-site",
        response_headers=CLOSED_HEADERS,
        robots_txt=CLOSED_ROBOTS,
        html=OPEN_HTML,
        profile_indexing_enabled=None,
        profile_measured=False,
    )
    assert s.verdict == MIXED
    assert [f["id"] for f in findings(s)] == ["LCK-001"]


def test_layer_order_puts_the_header_last() -> None:
    """Порядок слоёв — он же порядок снятия: заголовок перекрывает остальные."""
    from seo_operator.indexing_lock import LAYERS

    assert LAYERS[-1] == "x_robots_tag"
