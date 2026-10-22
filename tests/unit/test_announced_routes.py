"""Перечень поверхностей берётся из КАРТЫ витрины, а не из головы.

Повод: за одну смену 22.10 вывод «поверхности нет» был записан ПЯТЬ раз, и все
пять раз он был о моём незнании адреса, а не о витрине. Разделы стран у Zona и
Lords, анонсы и расписание у Yummy, расписание и жанры у Animedia — всё это
существовало и индексировалось, пока я проверяла придуманные адреса.

Проверки здесь — на чистых функциях разбора: сеть не трогается.
"""
from __future__ import annotations

import importlib.util
import pathlib

КОРЕНЬ = pathlib.Path(__file__).resolve().parents[2]
_сп = importlib.util.spec_from_file_location(
    "announced_routes", КОРЕНЬ / "automation" / "local" / "announced-routes.py")
мера = importlib.util.module_from_spec(_сп)
_сп.loader.exec_module(мера)

КАРТА = """<?xml version="1.0"?><urlset>
<url><loc>https://x.test/</loc></url>
<url><loc>https://x.test/catalog/ongoing</loc></url>
<url><loc>https://x.test/anime/nekiy-tayl</loc></url>
<url><loc>https://x.test/title/drugoy-tayl/</loc></url>
<url><loc>https://x.test/catalog/top</loc></url>
<url><loc>https://x.test/catalog/ongoing</loc></url>
</urlset>"""


def test_адреса_произведений_в_перечень_не_попадают():
    """Их десятки тысяч, и вопрос не про них."""
    п = мера.поверхности(КАРТА, "x.test")
    assert "/anime/nekiy-tayl" not in п
    assert "/title/drugoy-tayl/" not in п


def test_поверхности_собираются_и_повторы_убираются():
    п = мера.поверхности(КАРТА, "x.test")
    assert п == ["/", "/catalog/ongoing", "/catalog/top"]


def test_пустой_путь_становится_корнем():
    """`<loc>https://x.test</loc>` без слеша — это главная, а не пустота."""
    п = мера.поверхности("<loc>https://x.test</loc>", "x.test")
    assert п == ["/"]


def test_части_карты_узнаются_в_индексе():
    индекс = ("<sitemapindex><sitemap><loc>https://x.test/sitemap-1.xml</loc>"
              "</sitemap><sitemap><loc>https://x.test/sitemap/static.xml</loc>"
              "</sitemap></sitemapindex>")
    assert мера.части_карты(индекс) == ["https://x.test/sitemap-1.xml",
                                        "https://x.test/sitemap/static.xml"]


def test_сами_части_карты_поверхностями_не_считаются():
    индекс = "<loc>https://x.test/sitemap-1.xml</loc>"
    assert мера.поверхности(индекс, "x.test") == []


def test_разбор_страницы_читает_robots_canonical_и_карточки():
    тело = ('<title> Топ аниме </title>'
            '<meta name="robots" content="index, follow"/>'
            '<link rel="canonical" href="https://x.test/catalog/top"/>'
            '<a href="/anime/a"></a><a href="/anime/b"></a>'
            '<a href="/anime/a"></a>')
    р = мера.разобрать(тело)
    assert р["robots"] == "index, follow"
    assert р["canonical"] == "https://x.test/catalog/top"
    assert р["title"] == "Топ аниме"
    assert р["карточек"] == 2


def test_отсутствие_robots_названо_а_не_подставлено():
    р = мера.разобрать("<html></html>")
    assert р["robots"] == "—"
    assert р["canonical"] == "—"
    assert р["карточек"] == 0


def test_предел_перечня_назван_величиной():
    """Обрезка обязана быть видимой, иначе перечень выглядит полным."""
    assert мера.СКОЛЬКО >= 10


def test_непрочитанная_карта_это_не_отсутствие_поверхностей(monkeypatch):
    """Главное требование: «не измерено» и «нет» — разные исходы."""
    monkeypatch.setattr(мера, "достать", lambda url, таймаут=60: ("503", ""))
    и = мера.проверить("x.test")
    assert и["исход"] == "НЕ ИЗМЕРЕНО"
    assert и["поверхности"] == []
    assert мера.main(["x.test"]) == 2


def test_мёртвая_объявленная_поверхность_даёт_код_1(monkeypatch):
    def достать(url, таймаут=60):
        if url.endswith("/sitemap.xml"):
            return "200", "<url><loc>https://x.test/catalog/top</loc></url>"
        return "404", ""
    monkeypatch.setattr(мера, "достать", достать)
    assert мера.main(["x.test"]) == 1


def test_живые_поверхности_дают_код_0(monkeypatch):
    def достать(url, таймаут=60):
        if url.endswith("/sitemap.xml"):
            return "200", "<url><loc>https://x.test/catalog/top</loc></url>"
        return "200", '<meta name="robots" content="index, follow"/>'
    monkeypatch.setattr(мера, "достать", достать)
    assert мера.main(["x.test"]) == 0
