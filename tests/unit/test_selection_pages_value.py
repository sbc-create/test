"""REQ-SEO-SELECTION-VALUE: страницы отбора меряются, а не оцениваются на глаз.

Официальное основание — `knowledge/FACTS.md` F7.6 и F7.7 (источник
SRC-YANDEX-WEBMASTER, обращение 2026-10-18): малоинформативные страницы
результатов отбора названы примером, по которому алгоритмы могут применить
ограничения, и про них сказано отдельно — их часто много, они увеличивают
нагрузку и снижают скорость обхода полезных страниц.

Измерено 2026-10-18 на zonafilm12.site: витрина предлагает 165 стран, все 165
отвечают 200, все индексируемы и с self-canonical; ровно одну запись показывают
32 страницы (19 %), одну-две — 43 (26 %), меньше одной страницы листалки — 97
(59 %). Пустых в индексе нет.

Здесь закреплены два свойства инструмента, без которых вывод был бы неверным:

* **находка только одна** — индексируемая страница отбора с НУЛЁМ записей: это
  прямой запрет пакета (§3 п.4). Числа «одна-две записи» печатаются, но
  находкой не называются: порога малоинформативности официальная документация
  не даёт, и подставлять свой — значит выдавать свою мерку за рекомендацию;
* **список значений берётся у самой витрины**, а не придумывается: что витрина
  предлагает в фильтре, то и проверяется.
"""
from __future__ import annotations

import importlib.util
import io
import sys
from contextlib import redirect_stdout
from pathlib import Path

ПУТЬ = (Path(__file__).resolve().parents[2] / "automation" / "local"
        / "selection-pages-value.py")


def _модуль():
    имя = "selection_pages_value"
    спец = importlib.util.spec_from_file_location(имя, ПУТЬ)
    м = importlib.util.module_from_spec(спец)
    sys.modules[имя] = м
    спец.loader.exec_module(м)
    return м


МОД = _модуль()


def _страница(записей: int | None, *, robots: str = "index, follow",
              canonical: str = "", карточек: int = 3) -> str:
    части = ["<html><head>"]
    if robots:
        части.append(f'<meta name="robots" content="{robots}">')
    if canonical:
        части.append(f'<link rel="canonical" href="{canonical}">')
    части.append("</head><body>")
    if записей is not None:
        части.append(f"<p>{записей} записей в выборке</p>")
    for н in range(карточек):
        части.append(f'<a href="/title/t{н}/">т{н}</a>')
    части.append("</body></html>")
    return "".join(части)


def _прогон(monkeypatch, страницы: dict, аргв: list[str]) -> tuple[int, str]:
    """страницы: адрес → (html, код). Неописанный адрес — отказ теста."""
    def взять(url, таймаут):
        assert url in страницы, f"тест не описал запрос {url}"
        return страницы[url]
    monkeypatch.setattr(МОД, "взять", взять)
    буфер = io.StringIO()
    with redirect_stdout(буфер):
        код = МОД.главная(аргв)
    return код, буфер.getvalue()


КАТАЛОГ = ('<a href="/catalog/?country=turciya">Турция</a>'
           '<a href="/catalog/?country=andorra">Андорра</a>'
           '<a href="/catalog/?country=chad">Чад</a>')


def test_пустая_страница_отбора_в_индексе_это_находка(monkeypatch):
    """Единственная безоговорочная находка: запрет пакета §3 п.4."""
    код, вывод = _прогон(monkeypatch, {
        "https://x.test/catalog/": (КАТАЛОГ, "200"),
        "https://x.test/catalog/?country=turciya": (_страница(869), "200"),
        "https://x.test/catalog/?country=andorra": (_страница(0, карточек=0), "200"),
        "https://x.test/catalog/?country=chad": (_страница(1, карточек=1), "200"),
    }, ["x.test", "country"])
    assert код == 1
    assert "с нулём записей: 1" in вывод
    assert "andorra" in вывод


def test_одна_запись_печатается_но_находкой_не_считается(monkeypatch):
    """Порога малоинформативности в документации нет — своей мерки не ставим."""
    код, вывод = _прогон(monkeypatch, {
        "https://x.test/catalog/": (КАТАЛОГ, "200"),
        "https://x.test/catalog/?country=turciya": (_страница(869), "200"),
        "https://x.test/catalog/?country=andorra": (_страница(1, карточек=1), "200"),
        "https://x.test/catalog/?country=chad": (_страница(2, карточек=2), "200"),
    }, ["x.test", "country"])
    assert код == 0, "это не находка"
    assert "без вердикта (порога у документации нет)" in вывод
    assert "одной или двумя записями: 2" in вывод


def test_пустая_но_закрытая_от_индексации_не_находка(monkeypatch):
    """Отрицательный контроль: запрет про ИНДЕКСИРУЕМЫЕ пустые страницы."""
    код, вывод = _прогон(monkeypatch, {
        "https://x.test/catalog/": (КАТАЛОГ, "200"),
        "https://x.test/catalog/?country=turciya": (_страница(869), "200"),
        "https://x.test/catalog/?country=andorra": (
            _страница(0, robots="noindex, follow", карточек=0), "200"),
        "https://x.test/catalog/?country=chad": (_страница(5), "200"),
    }, ["x.test", "country"])
    assert код == 0
    assert "с нулём записей: 0" in вывод


def test_не_200_это_не_пусто(monkeypatch):
    код, вывод = _прогон(monkeypatch, {
        "https://x.test/catalog/": (КАТАЛОГ, "200"),
        "https://x.test/catalog/?country=turciya": (_страница(869), "200"),
        "https://x.test/catalog/?country=andorra": ("", "404"),
        "https://x.test/catalog/?country=chad": (_страница(5), "200"),
    }, ["x.test", "country"])
    assert "НЕ ИЗМЕРЕНО, это не «пусто»" in вывод
    assert "andorra=404" in вывод
    assert код == 0


def test_значения_берутся_у_витрины_а_не_придумываются(monkeypatch):
    код, вывод = _прогон(monkeypatch, {
        "https://x.test/catalog/": ("<p>фильтра нет</p>", "200"),
    }, ["x.test", "country"])
    assert код == 2, "нечего проверять — это отказ, а не «находок нет»"


def test_наполнение_печатается_корзинами(monkeypatch):
    код, вывод = _прогон(monkeypatch, {
        "https://x.test/catalog/": (КАТАЛОГ, "200"),
        "https://x.test/catalog/?country=turciya": (_страница(869), "200"),
        "https://x.test/catalog/?country=andorra": (_страница(4), "200"),
        "https://x.test/catalog/?country=chad": (_страница(None), "200"),
    }, ["x.test", "country"])
    assert "наполнение (по объявленному числу записей)" in вывод
    assert "3–9: 1" in вывод and "50+: 1" in вывод
    assert "не объявлено: 1" in вывод, (
        "страница без объявленного числа — отдельная графа, а не ноль")


def test_основание_названо_в_инструменте():
    тело = ПУТЬ.read_text(encoding="utf-8")
    assert "F7.6" in тело and "F7.7" in тело
    assert "SRC-YANDEX-WEBMASTER" in тело
    assert "выдумывать его здесь значило бы" in тело
