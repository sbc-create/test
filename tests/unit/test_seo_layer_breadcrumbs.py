"""seo_layer: BreadcrumbList только из видимых крошек (SEO_KNOWLEDGE_PACK §4 п.4).

Замер 12.10: на 9 витринах разметка строилась из адреса — «Главная › title ›
jamai-2-0» (раздел /title/ отвечает 404, последнее звено — slug), а видимые
крошки — «Lordserial » Сериалы » Jamai 2.0».
"""

from __future__ import annotations

import importlib.util
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
спец = importlib.util.spec_from_file_location("seo_layer_crumbs", ROOT / "automation" / "host" / "seo_layer.py")
слой = importlib.util.module_from_spec(спец)
спец.loader.exec_module(слой)

LORDS = ('<nav class="crumbs" aria-label="Хлебные крошки"><a href="/">Lordserial</a> » '
         '<a href="/series/">Сериалы</a> » <b>Jamai 2.0</b></nav>')
ANIMEDIA = ('<nav class="zcr" aria-label="Хлебные крошки"><a href="/">Animedia</a> / '
            '<a href="/catalog/">Каталог</a> / <span aria-current="page">Эй, у тебя ушки торчат!</span></nav>')
ZONA_PLAIN = ('<nav class="zcr" aria-label="Хлебные крошки"><a href="/">Zona</a> / '
              '<a href="/series/">Сериалы</a> / Я &amp; ты</nav>')


def _страница(тело_body: str, голова: str = "") -> bytes:
    return f"<html><head><title>t</title>{голова}</head><body>{тело_body}<h1>x</h1></body></html>".encode()


def _крошки(html_bytes: bytes) -> list:
    out = слой.обогатить(html_bytes, "text/html", хост="a.test", путь="/title/jamai-2-0/", имя_сайта="S")
    блоки = [json.loads(b) for b in re.findall(rb'<script type="application/ld\+json">(.*?)</script>', out, re.S)]
    return [б for б in блоки if б.get("@type") == "BreadcrumbList"]


def test_lords_visible_crumbs_become_markup():
    [бл] = _крошки(_страница(LORDS))
    assert [(i["name"], i.get("item")) for i in бл["itemListElement"]] == [
        ("Lordserial", "https://a.test/"), ("Сериалы", "https://a.test/series/"), ("Jamai 2.0", None)]
    assert [i["position"] for i in бл["itemListElement"]] == [1, 2, 3]


def test_animedia_and_plain_tail():
    assert [i["name"] for i in _крошки(_страница(ANIMEDIA))[0]["itemListElement"]] == [
        "Animedia", "Каталог", "Эй, у тебя ушки торчат!"]
    assert [i["name"] for i in _крошки(_страница(ZONA_PLAIN))[0]["itemListElement"]] == ["Zona", "Сериалы", "Я & ты"]


def test_no_visible_crumbs_no_markup_and_no_path_segments():
    out = слой.обогатить(_страница("<main>без крошек</main>"), "text/html", хост="a.test",
                         путь="/title/jamai-2-0/", имя_сайта="S")
    assert b"BreadcrumbList" not in out
    assert b'"name":"title"' not in out and b"jamai-2-0\"" not in out


def test_foreign_host_in_crumbs_refused():
    чужие = LORDS.replace('href="/series/"', 'href="https://evil.test/series/"')
    assert _крошки(_страница(чужие)) == []


def test_page_with_own_breadcrumblist_untouched():
    своя = '<script type="application/ld+json">{"@type":"BreadcrumbList","itemListElement":[]}</script>'
    out = слой.обогатить(_страница(LORDS, своя), "text/html", хост="a.test", путь="/catalog/", имя_сайта="S")
    assert out.count(b"BreadcrumbList") == 1


def test_apply_tool_brings_old_layer_to_same_behaviour():
    import subprocess  # noqa: PLC0415
    спец_и = importlib.util.spec_from_file_location(
        "apply_visible_breadcrumbs", ROOT / "automation" / "host" / "apply-visible-breadcrumbs.py")
    инструмент = importlib.util.module_from_spec(спец_и)
    спец_и.loader.exec_module(инструмент)
    старый = subprocess.run(["git", "-C", str(ROOT), "show", "1f89008:automation/host/seo_layer.py"],
                            capture_output=True, text=True)
    if старый.returncode:
        import pytest  # noqa: PLC0415
        pytest.skip("нет коммита 1f89008 в этой копии")
    новый, n = инструмент.привести(старый.stdout)
    assert n == 1 and инструмент.привести(новый) == (новый, 0)
    п: dict = {"__name__": "приведённый"}
    exec(compile(новый, "приведённый_слой", "exec"), п)  # noqa: S102
    out = п["обогатить"](_страница(LORDS), "text/html", хост="a.test", путь="/title/jamai-2-0/", имя_сайта="S")
    assert b'"name":"Jamai 2.0"' in out and b'"name":"title"' not in out
