"""Выгрузка пишет байты, а не текст — все страницы одинаково.

Каждая страница уходила на диск как `write_bytes(page.payload)`, и только
`404.html` — как `write_text(site.not_found.body)`. Одна строка из
восемнадцати, и в ней два отличия, оба тихие.

Первое: текстовый режим переводит переносы строк по правилам платформы. На
Linux `\n` остаётся собой, и разницы не видно; на платформе с другим
`os.linesep` артефакт вышел бы другим при тех же входах. Воспроизводимость,
которая держится на том, что все собирают на одной системе, — не
воспроизводимость.

Второе: `Page` умеет нести двоичное тело (`raw`), и тогда `body` — всего лишь
человекочитаемое описание для отчётов. Для страницы «не найдено» двоичного
тела сегодня нет; появится — на диск уйдёт описание вместо файла, и это будет
выглядеть как повреждение вывода, а не как забытая ветка.

Проверки требуют одинакового обращения со всеми страницами: то, что сайт
отдаёт в ответе, и то, что ложится на диск, — одни и те же байты.
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from factory.lords import render as render_mod  # noqa: E402
from factory.lords import serve as serve_mod  # noqa: E402


def _сайт(tmp_path: Path):
    site = render_mod.RenderedSite(site_id="проверка", profile="проверка", brand="Проверка")
    site.pages["/"] = render_mod.Page(path="/", body="<!doctype html><p>главная")
    site.not_found = render_mod.Page(path="/404", body="<!doctype html><p>не найдено")
    return site


class TestВсеСтраницыПишутсяОдинаково:
    def test_страница_не_найдено_пишется_байтами(self, tmp_path):
        site = _сайт(tmp_path)
        serve_mod.export(site, tmp_path)
        на_диске = (tmp_path / "404.html").read_bytes()
        assert на_диске == site.not_found.payload, (
            "на диск ушло не то, что сайт отдаёт в ответе")

    def test_двоичное_тело_не_подменяется_описанием(self, tmp_path):
        """`body` при заданном `raw` — описание для отчёта, а не содержимое."""
        site = _сайт(tmp_path)
        site.not_found = render_mod.Page(
            path="/404", body="описание для отчёта, не содержимое",
            raw=b"\x00\x01" + "двоичное тело".encode("utf-8"))
        serve_mod.export(site, tmp_path)
        assert ((tmp_path / "404.html").read_bytes()
                == b"\x00\x01" + "двоичное тело".encode("utf-8"))

    def test_переносы_строк_не_переводятся(self, tmp_path):
        """Текстовый режим переводит их по правилам платформы, двоичный — нет."""
        site = _сайт(tmp_path)
        site.not_found = render_mod.Page(path="/404", body="первая\nвторая\n")
        serve_mod.export(site, tmp_path)
        assert (tmp_path / "404.html").read_bytes() == "первая\nвторая\n".encode("utf-8")

    def test_обычные_страницы_тоже_байты(self, tmp_path):
        site = _сайт(tmp_path)
        serve_mod.export(site, tmp_path)
        assert (tmp_path / "index.html").read_bytes() == site.pages["/"].payload


class TestВыгрузкаВоспроизводима:
    def test_две_выгрузки_дают_те_же_байты(self, tmp_path):
        site = _сайт(tmp_path)
        первая, вторая = tmp_path / "one", tmp_path / "two"
        serve_mod.export(site, первая)
        serve_mod.export(site, вторая)
        файлы = sorted(p.relative_to(первая) for p in первая.rglob("*") if p.is_file())
        assert файлы == sorted(p.relative_to(вторая) for p in вторая.rglob("*") if p.is_file())
        for имя in файлы:
            assert (первая / имя).read_bytes() == (вторая / имя).read_bytes(), имя

    def test_перечень_файлов_отсортирован(self, tmp_path):
        """Порядок в отчёте не должен зависеть от обхода файловой системы."""
        site = _сайт(tmp_path)
        site.pages["/b/"] = render_mod.Page(path="/b/", body="б")
        site.pages["/a/"] = render_mod.Page(path="/a/", body="а")
        result = serve_mod.export(site, tmp_path)
        assert result["files"] == sorted(result["files"])
