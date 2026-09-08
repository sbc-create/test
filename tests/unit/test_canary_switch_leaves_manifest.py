"""Переключение оставляет манифест релиза, иначе витрина замирает.

Сценарий переключения создавал релиз, копировал в него `bundle-manifest.json`,
`rollback.json`, `README.md` и `Dockerfile` — и не оставлял
`release-manifest.json`.

Последствие тихое и полное. Ворота обновления содержимого читают манифест
действующего релиза, чтобы взять из него шаблон; без манифеста они отказывают,
а при отказе обновление **пропускает витрину целиком**:

    ${site}: ворота шаблона отказали — …
    ${site}: витрина остаётся на прежнем релизе, обновление пропущено

То есть переключение проходило успешно, витрина отвечала 200, приёмка была
зелёной — и каталог на ней замирал навсегда. Обнаружить это можно было только
по отсутствию новых релизов, то есть через часы.

Манифест пишет тот же сторож, что его потом читает. Одна реализация на запись и
на проверку: две разошлись бы, и разошлась бы именно та, что реже открывают.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
СЦЕНАРИЙ = ROOT / "automation" / "host" / "lords-canary-apply.sh"


@pytest.fixture(scope="module")
def текст() -> str:
    return СЦЕНАРИЙ.read_text(encoding="utf-8")


class TestМанифестПишется:
    def test_переключение_вызывает_сторожа(self, текст):
        assert "lords-refresh-guard.py" in текст, (
            "манифест релиза не пишется: обновление содержимого будет пропускать "
            "витрину на каждом цикле")

    def test_вызывается_именно_adopt(self, текст):
        assert re.search(r"adopt \"\$\{SITE\}\"", текст), (
            "нужна подкоманда adopt: pin собирает архив, но манифеста не пишет")

    def test_ревизия_и_репозиторий_переданы(self, текст):
        assert "--revision \"${HEAD_SHA}\"" in текст
        assert "--repo \"${REPO}\"" in текст

    def test_домен_и_тема_берутся_из_прежнего_манифеста(self, текст):
        """Выдумывать их нельзя: домен чужой витрины увёл бы поиск на неё."""
        assert "PREV_MANIFEST=" in текст
        assert '"domain"' in текст and '"theme"' in текст

    def test_счёт_записей_и_снимок_переданы(self, текст):
        assert "--content-count \"${SNAPSHOT_ITEMS}\"" in текст
        assert "--snapshot \"${SNAPSHOT_DIGEST}\"" in текст


class TestОтказМанифестаОткатывает:
    def test_неудача_записи_возвращает_прежний_релиз(self, текст):
        """Витрина без манифеста хуже невыложенной: она молча перестаёт обновляться."""
        кусок = текст[текст.index("adopt \"${SITE}\""):]
        конец = кусок.index("mkdir -p \"${AUDIT_DIR}\"")
        кусок = кусок[:конец]
        assert 'ln -sfn "${CURRENT}" "${RUNTIME}/current"' in кусок, (
            "при отказе манифеста ссылка не возвращается")
        assert "die " in кусок, "отказ манифеста не останавливает переключение"

    def test_манифест_пишется_после_проверки_отклика(self, текст):
        """Сторож смотрит на действующий релиз, поэтому только после подмены ссылки."""
        подмена = текст.index('ln -sfn "${TARGET}" "${RUNTIME}/current"')
        манифест = текст.index("adopt \"${SITE}\"")
        assert подмена < манифест


class TestСторожНаМесте:
    def test_сторож_существует(self):
        assert (ROOT / "automation" / "host" / "lords-refresh-guard.py").is_file(), (
            "сценарий вызывает сторожа, которого нет в дереве")

    def test_у_сторожа_есть_подкоманда_adopt(self):
        текст = (ROOT / "automation" / "host" / "lords-refresh-guard.py").read_text(
            encoding="utf-8")
        assert 'add_parser("adopt")' in текст
        assert "def команда_adopt" in текст
