"""Инкрементальный релиз на жёстких ссылках.

Главная опасность выбранного механизма: запись в файл, на который ссылаются два
релиза, меняет оба. Прежний релиз перестаёт быть точкой отката ровно тогда,
когда он нужен, и обнаруживается это в худший момент. Большая часть проверок
ниже — об этом.
"""
import os
from pathlib import Path

import pytest

from factory.site_engine.incremental import (
    IncrementalError,
    build_incremental,
    checksums_of,
    clone,
    discard,
    remove_page,
    verify_base_untouched,
    write_page,
)


def релиз(корень: Path, имя: str, страниц: int = 5) -> Path:
    d = корень / имя
    (d / "site" / "title").mkdir(parents=True)
    for i in range(страниц):
        (d / "site" / "title" / f"t{i}.html").write_text(f"<html>{имя} t{i}</html>",
                                                         encoding="utf-8")
    (d / "site" / "index.html").write_text(f"<html>главная {имя}</html>", encoding="utf-8")
    return d


class TestСвязаннаяКопия:
    def test_копия_разделяет_данные(self, tmp_path: Path):
        база = релиз(tmp_path, "база")
        связано = clone(база, tmp_path / "новый")
        assert связано == 6
        исходный = (база / "site" / "index.html").stat()
        копия = (tmp_path / "новый" / "site" / "index.html").stat()
        assert исходный.st_ino == копия.st_ino, "файлы обязаны разделять данные"

    def test_копия_не_занимает_места(self, tmp_path: Path):
        база = релиз(tmp_path, "база", страниц=50)
        clone(база, tmp_path / "новый")
        # Число ссылок на индексный узел выросло — значит, данные общие.
        assert (база / "site" / "index.html").stat().st_nlink == 2

    def test_существующая_цель_отклоняется(self, tmp_path: Path):
        база = релиз(tmp_path, "база")
        (tmp_path / "занято").mkdir()
        with pytest.raises(IncrementalError, match="уже существует"):
            clone(база, tmp_path / "занято")

    def test_отсутствующая_база_отклоняется(self, tmp_path: Path):
        with pytest.raises(IncrementalError, match="базового релиза нет"):
            clone(tmp_path / "нет", tmp_path / "новый")


class TestБазовыйРелизНеПортится:
    def test_запись_страницы_не_трогает_базу(self, tmp_path: Path):
        """Самая опасная ошибка этого механизма — и главная проверка."""
        база = релиз(tmp_path, "база")
        было = (база / "site" / "index.html").read_text(encoding="utf-8")
        новый = tmp_path / "новый"
        clone(база, новый)

        write_page(новый, "site/index.html", "<html>переписано</html>")

        assert (база / "site" / "index.html").read_text(encoding="utf-8") == было
        assert (новый / "site" / "index.html").read_text(encoding="utf-8") == "<html>переписано</html>"

    def test_запись_разрывает_общую_связь(self, tmp_path: Path):
        база = релиз(tmp_path, "база")
        новый = tmp_path / "новый"
        clone(база, новый)
        write_page(новый, "site/index.html", "<html>иное</html>")
        assert (база / "site" / "index.html").stat().st_ino != \
               (новый / "site" / "index.html").stat().st_ino

    def test_удаление_страницы_не_трогает_базу(self, tmp_path: Path):
        база = релиз(tmp_path, "база")
        новый = tmp_path / "новый"
        clone(база, новый)
        assert remove_page(новый, "site/title/t0.html") is True
        assert (база / "site" / "title" / "t0.html").exists()
        assert not (новый / "site" / "title" / "t0.html").exists()

    def test_проверка_ловит_порчу_базы(self, tmp_path: Path):
        """Испорченная база выглядит целой, пока не понадобится откат."""
        база = релиз(tmp_path, "база")
        суммы = checksums_of(база, ("site/index.html",))
        assert verify_base_untouched(база, суммы) == []
        # Портим так, как это сделала бы запись на месте.
        with (база / "site" / "index.html").open("w", encoding="utf-8") as handle:
            handle.write("испорчено")
        расхождения = verify_base_untouched(база, суммы)
        assert расхождения and "изменилось" in расхождения[0]

    def test_проверка_ловит_исчезновение_файла(self, tmp_path: Path):
        база = релиз(tmp_path, "база")
        суммы = checksums_of(база, ("site/index.html",))
        (база / "site" / "index.html").unlink()
        assert "исчез" in verify_base_untouched(база, суммы)[0]


class TestИнкрементальнаяСборка:
    def test_переписывается_только_названное(self, tmp_path: Path):
        база = релиз(tmp_path, "база", страниц=100)
        суммы = checksums_of(база, tuple(f"site/title/t{i}.html" for i in range(100)))
        итог = build_incremental(
            база, tmp_path / "новый",
            pages={"site/title/t7.html": "<html>новая серия</html>"},
        )
        assert итог.rewritten == ("site/title/t7.html",)
        assert итог.touched == 1
        assert итог.linked_files == 101
        assert verify_base_untouched(база, суммы) == []

    def test_страница_действительно_обновилась(self, tmp_path: Path):
        база = релиз(tmp_path, "база")
        итог = build_incremental(база, tmp_path / "новый",
                                 pages={"site/index.html": "<html>свежее</html>"})
        assert (итог.release / "site" / "index.html").read_text(encoding="utf-8") \
            == "<html>свежее</html>"

    def test_удаление_учитывается(self, tmp_path: Path):
        база = релиз(tmp_path, "база")
        итог = build_incremental(база, tmp_path / "новый",
                                 remove=("site/title/t1.html",))
        assert итог.removed == ("site/title/t1.html",)
        assert not (итог.release / "site" / "title" / "t1.html").exists()

    def test_несуществующее_удаление_не_считается(self, tmp_path: Path):
        база = релиз(tmp_path, "база")
        итог = build_incremental(база, tmp_path / "новый", remove=("site/нет.html",))
        assert итог.removed == ()

    def test_пустые_каталоги_не_остаются(self, tmp_path: Path):
        """Пустой раздел читается как «есть, но пуст» — это хуже отсутствия."""
        база = релиз(tmp_path, "база", страниц=1)
        итог = build_incremental(база, tmp_path / "новый",
                                 remove=("site/title/t0.html",))
        assert not (итог.release / "site" / "title").exists()

    def test_сборка_быстрее_полного_копирования(self, tmp_path: Path):
        база = релиз(tmp_path, "база", страниц=300)
        итог = build_incremental(база, tmp_path / "новый",
                                 pages={"site/index.html": "<html>x</html>"})
        assert итог.seconds < 5, f"связывание заняло {итог.seconds:.1f} с"

    def test_отчёт_называет_сделанное(self, tmp_path: Path):
        база = релиз(tmp_path, "база")
        итог = build_incremental(база, tmp_path / "новый",
                                 pages={"site/index.html": "x"})
        отчёт = итог.as_dict()
        assert отчёт["touched"] == 1
        assert отчёт["base"] == "база"


class TestНедостроенное:
    def test_недостроенный_релиз_убирается_дёшево(self, tmp_path: Path):
        база = релиз(tmp_path, "база")
        новый = tmp_path / "новый"
        clone(база, новый)
        discard(новый)
        assert not новый.exists()
        assert (база / "site" / "index.html").exists(), "база обязана уцелеть"

    def test_прерванная_запись_не_оставляет_обрывков(self, tmp_path: Path):
        база = релиз(tmp_path, "база")
        новый = tmp_path / "новый"
        clone(база, новый)
        with pytest.raises(TypeError):
            write_page(новый, "site/index.html", None)  # type: ignore[arg-type]
        обрывки = list((новый / "site").glob("*.part"))
        assert обрывки == [], f"остались обрывки: {обрывки}"
        assert (новый / "site" / "index.html").read_text(encoding="utf-8").startswith("<html>")
