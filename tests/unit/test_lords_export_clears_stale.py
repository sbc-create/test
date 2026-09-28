"""Выгрузка не оставляет страниц, которых сайт больше не отдаёт.

Найдено так: раздел `/years/0/` перестал строиться, указатель на него больше не
ссылался, а страница осталась и отвечала 200 — со старым заголовком «Год
выпуска: 0». Сборка была новая, файл — трёхчасовой давности.

Причина не в годах. Идиома очистки каталога скопирована дословно в `live_site`
и `preview` и забыта в двух сборщиках стендов. Снятый раздел жил по своему
адресу неограниченно: ни с одной страницы на него не сослаться, а по прямой
ссылке, из поиска или из чужого закладочного списка он открывался.

Поэтому идиома здесь одна, названная, и проверяется отдельно от того, кто её
зовёт.
"""

from __future__ import annotations

from factory.lords import serve as serve_mod


class TestОчисткаКаталогаВыгрузки:
    def test_прежние_страницы_удаляются(self, tmp_path):
        (tmp_path / "years" / "0").mkdir(parents=True)
        (tmp_path / "years" / "0" / "index.html").write_text("Год выпуска: 0")
        serve_mod.clear_directory(tmp_path)
        assert not (tmp_path / "years" / "0").exists()

    def test_каталог_остаётся_и_пригоден_для_записи(self, tmp_path):
        (tmp_path / "a.html").write_text("x")
        serve_mod.clear_directory(tmp_path)
        assert tmp_path.is_dir()
        assert list(tmp_path.iterdir()) == []

    def test_отсутствующий_каталог_создаётся(self, tmp_path):
        target = tmp_path / "нет-такого" / "вложенный"
        serve_mod.clear_directory(target)
        assert target.is_dir()

    def test_вложенность_любой_глубины(self, tmp_path):
        deep = tmp_path / "a" / "b" / "c" / "d"
        deep.mkdir(parents=True)
        (deep / "index.html").write_text("x")
        serve_mod.clear_directory(tmp_path)
        assert list(tmp_path.iterdir()) == []

    def test_за_пределы_каталога_не_выходит(self, tmp_path):
        """Очистка — операция разрушительная, и радиус у неё обязан быть точным."""
        сосед = tmp_path / "сосед"
        сосед.mkdir()
        (сосед / "важное").write_text("не трогать")
        цель = tmp_path / "цель"
        цель.mkdir()
        (цель / "старое.html").write_text("x")
        serve_mod.clear_directory(цель)
        assert (сосед / "важное").read_text() == "не трогать"

    def test_символическая_ссылка_не_разыменовывается(self, tmp_path):
        """Ссылка удаляется как запись; то, на что она указывает, — нет."""
        внешнее = tmp_path / "внешнее"
        внешнее.mkdir()
        (внешнее / "файл").write_text("цел")
        цель = tmp_path / "цель"
        цель.mkdir()
        (цель / "ссылка").symlink_to(внешнее, target_is_directory=True)
        serve_mod.clear_directory(цель)
        assert list(цель.iterdir()) == []
        assert (внешнее / "файл").read_text() == "цел"
