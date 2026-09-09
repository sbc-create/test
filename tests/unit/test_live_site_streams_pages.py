"""Страницы боевой сборки уходят на диск, а не копятся в памяти.

Замер 9 сентября на lords-03: cgroup юнита обновления упёрся в предел 2 ГиБ,
`memory.max` сработал 97 530 раз, `pgsteal` дошёл до 4 099 604, процесс сжёг
2 ч 52 мин процессорного времени и не записал ни одного файла — вытеснение по
кругу вместо работы. Юнит при этом занят до десяти часов, и всё это время
выкладка невозможна ни для одной витрины.

Причина измерена, а не предположена: фактическая сборка витрины — 62 157
файлов, 819 МБ, из них 61 734 страницы разметки на 814 МБ. Все эти тела
удерживались в `site.pages` до конца отрисовки, а строки Python весят больше
своих байт.

Механизм потоковой отдачи в рендерере уже был и ровно для этого — он просто не
использовался боевой сборкой. Здесь закреплено, что используется.
"""

from __future__ import annotations

import ast
import inspect
from pathlib import Path

from factory.lords import live_site, serve


class TestБоеваяСборкаПотоковая:
    def test_render_site_вызывается_с_sink(self):
        дерево = ast.parse(Path(inspect.getfile(live_site)).read_text(encoding="utf-8"))
        вызовы = [у for у in ast.walk(дерево)
                  if isinstance(у, ast.Call)
                  and getattr(у.func, "attr", "") == "render_site"]
        assert вызовы, "render_site в боевой сборке не вызывается"
        for вызов in вызовы:
            имена = {к.arg for к in вызов.keywords}
            assert "sink" in имена, (
                "боевая сборка копит тела страниц в памяти: "
                "61 734 страницы, 814 МБ разметки")

    def test_страница_404_записывается_отдельно(self):
        """`not_found` присваивается напрямую и через `sink` не проходит."""
        текст = Path(inspect.getfile(live_site)).read_text(encoding="utf-8")
        assert "site.not_found" in текст and "404.html" in текст


class TestПравилоПутиОдноНаДвоих:
    def test_поток_и_выгрузка_кладут_страницу_в_одно_место(self, tmp_path):
        """Две копии правила разошлись бы молча, и каталоги отличались бы."""
        assert serve.page_target(tmp_path, "/catalog/") == tmp_path / "catalog" / "index.html"
        assert serve.page_target(tmp_path, "/robots.txt") == tmp_path / "robots.txt"
        assert serve.page_target(tmp_path, "/") == tmp_path / "index.html"

    def test_выгрузка_пользуется_тем_же_правилом(self):
        текст = Path(inspect.getfile(serve)).read_text(encoding="utf-8")
        дерево = ast.parse(текст)
        экспорт = next(у for у in ast.walk(дерево)
                       if isinstance(у, ast.FunctionDef) and у.name == "export")
        внутри = ast.unparse(экспорт)
        assert "write_page(" in внутри, "выгрузка завела собственное правило пути"

    def test_запись_возвращает_относительный_путь(self, tmp_path):
        class Страница:
            path = "/genres/drama/"
            payload = b"<html></html>"
        относительный = serve.write_page(tmp_path, Страница())
        assert относительный == "genres/drama/index.html"
        assert (tmp_path / относительный).read_bytes() == b"<html></html>"
