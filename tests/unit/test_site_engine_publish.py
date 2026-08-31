"""Атомарность публикации проверяется наблюдением, а не чтением кода.

`readlink` после переключения ничего не доказывает: он смотрит на результат,
а вопрос — существует ли момент, в котором ссылки нет. Поэтому здесь по ссылке
непрерывно ходят читатели, пока публикация переключает её сотни раз.
"""
import threading
import time
from pathlib import Path

import pytest

from factory.site_engine.publish import (
    PublishError,
    preflight,
    prune,
    publish,
    rollback,
    switch,
)


def релиз(корень: Path, имя: str, страниц: int = 3) -> Path:
    d = корень / "releases" / имя
    (d / "site").mkdir(parents=True)
    for i in range(страниц):
        (d / "site" / f"page{i}.html").write_text(f"<html>{имя} {i}</html>", encoding="utf-8")
    (d / "serve.py").write_text("# рантайм\n", encoding="utf-8")
    return d


class TestПредполётнаяПроверка:
    def test_пустой_релиз_не_публикуется(self, tmp_path: Path):
        d = tmp_path / "releases" / "пустой"
        (d / "site").mkdir(parents=True)
        (d / "serve.py").write_text("#", encoding="utf-8")
        with pytest.raises(PublishError, match="пустую витрину"):
            preflight(d)

    def test_релиз_без_рантайма_не_публикуется(self, tmp_path: Path):
        d = релиз(tmp_path, "без-рантайма")
        (d / "serve.py").unlink()
        with pytest.raises(PublishError, match="serve.py"):
            preflight(d)

    def test_несуществующий_релиз_не_публикуется(self, tmp_path: Path):
        with pytest.raises(PublishError, match="релиза нет"):
            preflight(tmp_path / "нет")

    def test_проверка_идёт_до_переключения(self, tmp_path: Path):
        """Переключиться и потом обнаружить пустоту — значит показать пустоту."""
        первый = релиз(tmp_path, "первый")
        current = tmp_path / "current"
        publish(current, первый)
        плохой = tmp_path / "releases" / "плохой"
        (плохой / "site").mkdir(parents=True)
        (плохой / "serve.py").write_text("#", encoding="utf-8")
        with pytest.raises(PublishError):
            publish(current, плохой)
        assert current.resolve() == первый.resolve(), "ссылка обязана остаться прежней"


class TestАтомарность:
    def test_ссылка_никогда_не_исчезает(self, tmp_path: Path):
        """Главная проверка: читатель не видит отсутствия ссылки.

        Прежний `ln -sfn` — это unlink плюс symlink, и между ними существует
        окно. Здесь замена делается через `os.replace`, то есть `rename(2)`.
        """
        первый = релиз(tmp_path, "первый")
        второй = релиз(tmp_path, "второй")
        current = tmp_path / "current"
        publish(current, первый)

        пропаж = []
        смешанных = []
        стоп = threading.Event()

        def читатель():
            while not стоп.is_set():
                try:
                    цель = current.resolve(strict=True)
                except (OSError, FileNotFoundError):
                    пропаж.append(time.monotonic())
                    continue
                # Релиз обязан быть целым: не бывает половины одного и
                # половины другого.
                страницы = sorted(p.name for p in (цель / "site").glob("*.html"))
                if страницы != ["page0.html", "page1.html", "page2.html"]:
                    смешанных.append(страницы)

        потоки = [threading.Thread(target=читатель) for _ in range(4)]
        for t in потоки:
            t.start()
        try:
            for i in range(200):
                switch(current, второй if i % 2 else первый)
        finally:
            стоп.set()
            for t in потоки:
                t.join(5)

        assert пропаж == [], f"ссылка отсутствовала {len(пропаж)} раз"
        assert смешанных == [], f"наблюдался смешанный релиз: {смешанных[:3]}"

    def test_активный_релиз_не_меняется_на_месте(self, tmp_path: Path):
        первый = релиз(tmp_path, "первый")
        второй = релиз(tmp_path, "второй")
        current = tmp_path / "current"
        publish(current, первый)
        до = (первый / "site" / "page0.html").read_text(encoding="utf-8")
        publish(current, второй)
        assert (первый / "site" / "page0.html").read_text(encoding="utf-8") == до

    def test_временный_файл_не_остаётся(self, tmp_path: Path):
        первый = релиз(tmp_path, "первый")
        current = tmp_path / "current"
        for _ in range(20):
            publish(current, первый)
        мусор = [p for p in tmp_path.iterdir() if p.name.startswith(".current.")]
        assert мусор == [], f"остались временные ссылки: {мусор}"

    def test_переключение_на_другую_файловую_систему_отклоняется(self, tmp_path: Path):
        """`rename(2)` между устройствами не работает; узнать это надо заранее."""
        from unittest.mock import patch

        первый = релиз(tmp_path, "первый")
        current = tmp_path / "current"
        with patch("factory.site_engine.publish._same_filesystem", return_value=False):
            with pytest.raises(PublishError, match="разных файловых системах"):
                switch(current, первый)


class TestОткат:
    def test_откат_возвращает_прежний_релиз(self, tmp_path: Path):
        первый = релиз(tmp_path, "первый")
        второй = релиз(tmp_path, "второй")
        current = tmp_path / "current"
        publish(current, первый)
        результат = publish(current, второй)
        assert результат.previous.resolve() == первый.resolve()
        rollback(current, результат.previous)
        assert current.resolve() == первый.resolve()

    def test_откат_тем_же_механизмом(self, tmp_path: Path):
        """Отдельный путь отката оказался бы непроверенным ровно тогда, когда нужен."""
        первый = релиз(tmp_path, "первый")
        второй = релиз(tmp_path, "второй")
        current = tmp_path / "current"
        publish(current, первый)
        publish(current, второй)
        пропаж = []
        стоп = threading.Event()

        def читатель():
            while not стоп.is_set():
                try:
                    current.resolve(strict=True)
                except OSError:
                    пропаж.append(1)

        t = threading.Thread(target=читатель)
        t.start()
        try:
            for i in range(100):
                rollback(current, первый if i % 2 else второй)
        finally:
            стоп.set()
            t.join(5)
        assert пропаж == []


class TestУборка:
    def test_активный_и_запасной_не_удаляются(self, tmp_path: Path):
        активный = релиз(tmp_path, "активный")
        запасной = релиз(tmp_path, "запасной")
        старый = релиз(tmp_path, "старый")
        удалить = prune(tmp_path / "releases", keep=(активный, запасной), limit=2)
        assert активный not in удалить
        assert запасной not in удалить
        assert старый in удалить

    def test_при_двух_релизах_удалять_нечего(self, tmp_path: Path):
        первый = релиз(tmp_path, "первый")
        второй = релиз(tmp_path, "второй")
        assert prune(tmp_path / "releases", keep=(первый, второй), limit=2) == []
