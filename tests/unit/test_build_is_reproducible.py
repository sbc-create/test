"""Одинаковые входы дают одинаковый вывод — доказано двумя сборками.

Проверяется не «должно быть детерминированно», а фактическое совпадение байтов
двух независимых сборок одной витрины. Утверждение о воспроизводимости, не
подкреплённое двумя прогонами, — обещание, а не свойство.

Отдельно проверяется устойчивость к тому, что обычно её и ломает: рабочему
каталогу, часовому поясу и языку среды. Сборка, зависящая от них, воспроизводима
ровно до первой чужой машины.
"""

from __future__ import annotations

import hashlib
import os
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from factory.lords import fixtures as fx  # noqa: E402
from factory.lords import render as render_mod  # noqa: E402
from factory.lords import serve as serve_mod  # noqa: E402
from factory.paths import PATHS  # noqa: E402

САЙТ = "lords-02"


def _собрать(tmp: Path) -> dict[str, str]:
    package = yaml.safe_load(PATHS.site_package(САЙТ).read_text(encoding="utf-8"))
    site = render_mod.render_site(package, catalog=fx.build_catalog(),
                                  environ={}, publisher_id="1")
    serve_mod.export(site, tmp)
    return {p.relative_to(tmp).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted(tmp.rglob("*")) if p.is_file()}


class TestДвеСборкиСовпадают:
    def test_состав_и_содержимое_одинаковы(self, tmp_path):
        первая = _собрать(tmp_path / "one")
        вторая = _собрать(tmp_path / "two")
        assert sorted(первая) == sorted(вторая), "состав файлов разошёлся"
        различия = [имя for имя in первая if первая[имя] != вторая[имя]]
        assert различия == [], f"содержимое разошлось: {различия[:10]}"

    def test_собрано_не_пусто(self, tmp_path):
        """Совпадение двух пустых сборок доказывало бы только пустоту."""
        assert len(_собрать(tmp_path / "one")) > 20


class TestСредаНеВлияет:
    def test_часовой_пояс_не_меняет_вывод(self, tmp_path, monkeypatch):
        первая = _собрать(tmp_path / "one")
        monkeypatch.setenv("TZ", "Pacific/Kiritimati")
        import time
        if hasattr(time, "tzset"):
            time.tzset()
        try:
            вторая = _собрать(tmp_path / "two")
        finally:
            monkeypatch.undo()
            if hasattr(time, "tzset"):
                time.tzset()
        assert первая == вторая, "вывод зависит от часового пояса среды"

    def test_язык_среды_не_меняет_вывод(self, tmp_path, monkeypatch):
        первая = _собрать(tmp_path / "one")
        monkeypatch.setenv("LC_ALL", "C")
        monkeypatch.setenv("LANG", "C")
        вторая = _собрать(tmp_path / "two")
        assert первая == вторая, "вывод зависит от языка среды"

    def test_рабочий_каталог_не_меняет_вывод(self, tmp_path):
        """Сборка из другого каталога — обычное дело в CI."""
        первая = _собрать(tmp_path / "one")
        прежний = os.getcwd()
        os.chdir(tmp_path)
        try:
            вторая = _собрать(tmp_path / "two")
        finally:
            os.chdir(прежний)
        assert первая == вторая, "вывод зависит от рабочего каталога"


class TestОтпечатокАртефактаУстойчив:
    def test_два_вычисления_дают_одно_значение(self):
        from factory.templates import digest as digest_mod
        assert digest_mod.compute()["template_digest"] == \
               digest_mod.compute()["template_digest"]

    def test_отпечаток_не_зависит_от_рабочего_каталога(self, tmp_path):
        проба = (
            "import json, sys; sys.path.insert(0, %r);"
            "from factory.templates import digest;"
            "print(digest.compute()['template_digest'])" % str(ROOT)
        )
        свой = subprocess.run([sys.executable, "-c", проба], capture_output=True,
                              text=True, cwd=str(ROOT), timeout=600)
        чужой = subprocess.run([sys.executable, "-c", проба], capture_output=True,
                               text=True, cwd=str(tmp_path), timeout=600)
        assert свой.returncode == 0 and чужой.returncode == 0, чужой.stderr[-500:]
        assert свой.stdout.strip() == чужой.stdout.strip(), (
            "отпечаток артефакта зависит от того, откуда его считают")


class TestВерсияНеПереиспользуется:
    def test_номер_версии_принадлежит_одному_отпечатку(self):
        sys.path.insert(0, str(ROOT / "scripts"))
        from release_input_audit import ARTIFACT_VERSIONS

        по_номерам: dict[int, list[str]] = {}
        for отпечаток, версия in ARTIFACT_VERSIONS.items():
            по_номерам.setdefault(версия, []).append(отпечаток)
        двойные = {в: о for в, о in по_номерам.items() if len(о) > 1}
        assert двойные == {}, (
            f"номер версии выдан нескольким отпечаткам: {list(двойные)}. "
            "При откате такая ссылка неразрешима")
