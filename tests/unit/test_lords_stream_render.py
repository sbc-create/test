"""REQ-LORDS-STREAM: потоковое сличение даёт то же, что и обычное.

Рендер складывал тела всех 9721 страницы в словарь: замер 3 сентября — 1791 МБ
на витрину при 3671 МБ доступных на хосте, из которых почти три гигабайта уже
в swap. Поэтому три витрины нельзя было собирать одновременно, и третья выходила
за пятнадцатиминутный срок.

Потоковый путь сличает страницу сразу и тут же её забывает. Он имеет право
существовать, только если отвечает ровно то же, что и прежний, — это здесь и
проверяется.
"""

from __future__ import annotations

from pathlib import Path

import yaml

from factory.lords import fast_path
from factory.lords import fixtures as fx
from factory.lords import render as render_mod
from factory.paths import PATHS


def пакет(site_id: str = "lords-01") -> dict:
    return yaml.safe_load(PATHS.site_package(site_id).read_text(encoding="utf-8"))


class TestПотоковаяОтдачаСтраниц:
    def test_отдаёт_те_же_страницы_что_и_обычная_сборка(self):
        каталог = fx.build_catalog()
        обычный = render_mod.render_site(пакет(), catalog=каталог)

        отданные: dict[str, bytes] = {}
        поток = render_mod.render_site(
            пакет(), catalog=каталог, sink=lambda page: отданные.__setitem__(page.path, page.payload)
        )

        assert sorted(отданные) == sorted(обычный.pages)
        for путь, страница in обычный.pages.items():
            assert отданные[путь] == страница.payload, путь
        assert sorted(поток.pages) == sorted(обычный.pages)

    def test_тела_в_словаре_не_остаются(self):
        каталог = fx.build_catalog()
        поток = render_mod.render_site(пакет(), catalog=каталог, sink=lambda page: None)
        assert all(страница.body == "" for страница in поток.pages.values())
        # Состав сайта при этом виден по-прежнему: пути, признак индексируемости.
        assert any(страница.indexable for страница in поток.pages.values())

    def test_без_sink_поведение_прежнее(self):
        каталог = fx.build_catalog()
        сайт = render_mod.render_site(пакет(), catalog=каталог)
        assert any(страница.body for страница in сайт.pages.values())


class TestПотоковоеСличениеРавносильно:
    """Оба пути сличения обязаны отвечать одинаково."""

    СТРАНИЦЫ = {
        "/": b"<html>home v2</html>",
        "/movies/": b"<html>movies</html>",
        "/movies/page/2/": b"<html>page two</html>",
        "/new/": b"<html>new page</html>",
    }

    def _база(self, tmp_path: Path) -> Path:
        base = tmp_path / "base"
        for relative, payload in {
            "index.html": b"<html>home v1</html>",
            "movies/index.html": b"<html>movies</html>",
            "movies/page/2/index.html": b"<html>page two</html>",
            "ushedshaya/index.html": b"<html>gone</html>",
        }.items():
            цель = base / relative
            цель.parent.mkdir(parents=True, exist_ok=True)
            цель.write_bytes(payload)
        return base

    def _подделать_рендер(self, monkeypatch):
        class Страница:
            def __init__(self, path: str, payload: bytes) -> None:
                self.path, self.payload, self.body = path, payload, payload.decode()
                self.indexable = True

        class Сайт:
            def __init__(self, pages) -> None:
                self.pages = pages

        def подделка(site_id, *, cache_root=None, var_root=None,
                     only_title_slugs=None, sink=None):
            страницы = {p: Страница(p, b) for p, b in self.СТРАНИЦЫ.items()}
            if sink is not None:
                for страница in страницы.values():
                    sink(страница)
            return Сайт(страницы), 0.1, 0.2

        monkeypatch.setattr(fast_path, "render_from_cache", подделка)

    def test_оба_пути_называют_одни_и_те_же_страницы(self, tmp_path, monkeypatch):
        self._подделать_рендер(monkeypatch)
        base = self._база(tmp_path)

        обычный = fast_path.apply("lords-01", base=base, write=False)
        потоковый = fast_path.apply("lords-01", base=base, write=False, stream=True)

        assert потоковый.changed_paths == обычный.changed_paths
        assert потоковый.pages_changed == обычный.pages_changed == 2  # главная и новая
        assert потоковый.pages_added == обычный.pages_added == 1
        assert потоковый.pages_removed == обычный.pages_removed == 1
        assert потоковый.pages_total == обычный.pages_total

    def test_оба_пути_молчат_когда_ничего_не_изменилось(self, tmp_path, monkeypatch):
        self._подделать_рендер(monkeypatch)
        base = tmp_path / "base"
        for путь, payload in self.СТРАНИЦЫ.items():
            relative = fast_path._relative_for(путь)
            цель = base / relative
            цель.parent.mkdir(parents=True, exist_ok=True)
            цель.write_bytes(payload)

        обычный = fast_path.apply("lords-01", base=base, write=False)
        потоковый = fast_path.apply("lords-01", base=base, write=False, stream=True)
        assert потоковый.pages_changed == обычный.pages_changed == 0
        assert потоковый.pages_removed == обычный.pages_removed == 0
