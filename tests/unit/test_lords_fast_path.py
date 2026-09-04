"""Быстрый путь: переписывается только изменившееся.

Проверки не ходят ни к провайдеру, ни в живой каталог: они собирают маленький
сайт из выдуманных записей и сличают его сам с собой.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from factory.lords import fast_path


class ФиктивнаяСтраница:
    def __init__(self, payload: bytes) -> None:
        self.payload = payload


class ФиктивныйСайт:
    def __init__(self, pages: dict[str, bytes]) -> None:
        self.pages = {p: ФиктивнаяСтраница(b) for p, b in pages.items()}


def записать(base: Path, files: dict[str, bytes]) -> None:
    for relative, payload in files.items():
        target = base / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(payload)


def test_адрес_страницы_превращается_в_путь_файла():
    assert fast_path._relative_for("/") == "index.html"
    assert fast_path._relative_for("/catalog/") == "catalog/index.html"
    assert fast_path._relative_for("/robots.txt") == "robots.txt"
    assert fast_path._relative_for("/title/x/") == "title/x/index.html"


def test_совпадающий_сайт_не_даёт_ни_одной_записи(tmp_path):
    base = tmp_path / "base"
    записать(base, {"index.html": b"<html>a</html>", "catalog/index.html": b"<html>b</html>"})
    сайт = ФиктивныйСайт({"/": b"<html>a</html>", "/catalog/": b"<html>b</html>"})

    к_записи, добавлено, удалено = fast_path.diff_against(сайт, base)

    assert к_записи == {}
    assert добавлено == []
    assert удалено == []


def test_изменившаяся_страница_попадает_в_запись_одна(tmp_path):
    base = tmp_path / "base"
    записать(base, {"index.html": b"<html>a</html>", "catalog/index.html": b"<html>b</html>"})
    сайт = ФиктивныйСайт({"/": b"<html>a</html>", "/catalog/": "<html>ИЗМЕНИЛОСЬ</html>".encode()})

    к_записи, добавлено, удалено = fast_path.diff_against(сайт, base)

    assert list(к_записи) == ["catalog/index.html"]
    assert добавлено == []


def test_новая_страница_отмечается_добавленной(tmp_path):
    base = tmp_path / "base"
    записать(base, {"index.html": b"<html>a</html>"})
    сайт = ФиктивныйСайт({"/": b"<html>a</html>", "/new/": b"<html>n</html>"})

    к_записи, добавлено, _ = fast_path.diff_against(сайт, base)

    assert добавлено == ["new/index.html"]
    assert "new/index.html" in к_записи


def test_в_частичном_режиме_удалённые_не_вычисляются(tmp_path):
    """Отсутствие страницы среди отрисованных ничего не значит: её не просили.

    Без этого правила частичный рендер удалил бы из релиза всё, что не входило
    в план, — то есть почти весь сайт.
    """
    base = tmp_path / "base"
    записать(base, {"index.html": b"a", "title/x/index.html": b"x", "title/y/index.html": b"y"})
    сайт = ФиктивныйСайт({"/title/x/": b"x"})

    _, _, удалено_частично = fast_path.diff_against(сайт, base, partial=True)
    _, _, удалено_полностью = fast_path.diff_against(сайт, base, partial=False)

    assert удалено_частично == []
    assert sorted(удалено_полностью) == ["index.html", "title/y/index.html"]


def test_загрузчик_быстрого_пути_не_ходит_в_сеть():
    """Молчаливый выход в сеть выглядел бы как «просто медленно»."""
    загрузчик = fast_path._NoNetwork()
    with pytest.raises(RuntimeError, match="не ходит к провайдеру"):
        загрузчик.fetch("что угодно")
    with pytest.raises(RuntimeError, match="не ходит к провайдеру"):
        # Обращение к атрибуту и есть проверяемое действие: заглушка обязана
        # отказать на любом обращении, а не только на fetch.
        загрузчик.какой_то_метод  # noqa: B018


def test_результат_считает_время_по_частям():
    итог = fast_path.FastPathResult(
        site_id="lords-01", pages_total=10, pages_changed=1, pages_added=0,
        pages_removed=0, release=None, base=Path("/tmp/base"),
        seconds_catalog=1.0, seconds_render=2.0, seconds_diff=0.5, seconds_write=0.25,
    )
    assert итог.seconds_total == pytest.approx(3.75)
    assert json.loads(json.dumps(итог.as_dict()))["seconds"]["total"] == 3.75
