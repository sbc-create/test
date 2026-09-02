"""Каталог сборки лежит там, где жёсткие ссылки возможны.

Регрессия к отказу третьего настоящего timer-цикла 2026-09-02 12:56:

    cp: cannot create hard link '/tmp/tmp.spjlRwy6IQ/index.html'
        to '/srv/lords/lords-01/releases/…/site/index.html': Invalid cross-device link

У службы `PrivateTmp=yes`, поэтому её `/tmp` — отдельная точка монтирования.
Ядро запрещает жёсткую ссылку через границу монтирования даже тогда, когда по
обе стороны одна и та же файловая система: `/srv/lords` и приватный `/tmp`
службы оба лежат на `/dev/vda1`, и связывание всё равно отказывало.

Снаружи службы это не воспроизводится — там `/tmp` и `/srv` в одном
монтировании. Поэтому проверка статическая: она смотрит, ГДЕ конвейер создаёт
каталог сборки, а не пытается повторить чужое пространство имён.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

КОНВЕЙЕР = Path(__file__).resolve().parents[2] / "automation" / "host" / "lords-content-refresh.sh"


@pytest.fixture(scope="module")
def текст() -> str:
    return КОНВЕЙЕР.read_text(encoding="utf-8")


class TestКаталогСборкиРядомСРелизами:
    def test_staging_создаётся_внутри_runtime(self, текст):
        строки = [s.strip() for s in текст.splitlines()
                  if re.match(r"^\s*staging=", s)]
        assert строки, "присваивание staging не найдено"
        for строка in строки:
            assert "${runtime}" in строка, (
                "каталог сборки обязан создаваться внутри ${runtime}: жёсткие ссылки "
                f"не пересекают границу монтирования. Найдено: {строка}")

    def test_нет_голого_mktemp_для_staging(self, текст):
        плохие = [s.strip() for s in текст.splitlines()
                  if re.match(r"^\s*staging=\"?\$\(mktemp -d\)", s)]
        assert not плохие, (
            "`mktemp -d` без пути кладёт каталог в /tmp, а у службы PrivateTmp=yes — "
            f"это отдельное монтирование: {плохие}")

    def test_остатки_прежних_сборок_убираются(self, текст):
        assert re.search(r'rm -rf "\$\{runtime\}"/\.staging\.\*', текст), (
            "каталоги сборки теперь лежат рядом с релизами, и брошенные после сбоя "
            "обязаны убираться: иначе они копятся на том же разделе, что и витрина")
