"""Снимок каталога переживает render и находится switch'ем — по расписке.

Что произошло. Фаза `render` запускалась с `LORDS_SNAPSHOT_DIR`, указывающим на
снимок в основном чекауте. Фаза `switch` эту переменную не получала и считала
путь заново, по умолчанию — `${REPO}/var/lords/lords/catalog-cache/lords-02.json`
внутри рабочего дерева, где снимка нет никогда. Переключение падало с
`FileNotFoundError`, ссылка не менялась.

Расписка о сборке при этом называла только **отпечаток** снимка, но не путь к
нему. То есть две фазы договаривались о том, что построено, и не договаривались
о том, из чего.

Хуже: пока шёл рендер, обновление содержимого переписало сам файл. Снимок с
отпечатком, записанным в расписке, перестал существовать физически — а значит
предпереключательные ворота нечем было бы выполнить даже при верном пути.

Отсюда три требования, и все три проверяются здесь.

Render обязан заморозить снимок: скопировать его в неизменяемое хранилище
сборки и строить из копии. Расписка обязана назвать абсолютный путь копии и её
отпечаток. Switch обязан взять путь из расписки и не вычислять свой.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]

#: Разделитель фаз в сценарии. Берётся точно, а не пересчитывается: длина
#: черты значения не имеет, но промах по ней делит файл не там и превращает
#: проверку в бессмыслицу — что и случилось с первой редакцией.
МАРКЕР_SWITCH = "# " + "-" * 69 + " switch"
СЦЕНАРИЙ = ROOT / "automation" / "host" / "lords-canary-apply.sh"
СНИМОК_СЦЕНАРИЙ = ROOT / "automation" / "host" / "lords-canary-snapshot.py"


@pytest.fixture(scope="module")
def текст() -> str:
    return СЦЕНАРИЙ.read_text(encoding="utf-8")


class TestРаспискаНазываетПуть:
    def test_расписка_содержит_абсолютный_путь_снимка(self, текст):
        assert '"content_snapshot_path"' in текст, (
            "расписка называет только отпечаток снимка: switch не знает, где его "
            "искать, и вычисляет свой путь")

    def test_switch_берёт_путь_из_расписки(self, текст):
        хвост = текст[текст.index(МАРКЕР_SWITCH):]
        assert "content_snapshot_path" in хвост, (
            "фаза переключения не читает путь снимка из расписки")

    def test_switch_не_вычисляет_свой_путь_снимка(self, текст):
        """Вычисленный по умолчанию путь и есть исходный дефект."""
        хвост = текст[текст.index(МАРКЕР_SWITCH):]
        assert "catalog-cache" not in хвост, (
            "фаза переключения снова вычисляет путь снимка сама")


class TestRenderЗамораживаетСнимок:
    def test_render_копирует_снимок_в_сборку(self, текст):
        голова = текст[:текст.index(МАРКЕР_SWITCH)]
        assert "FROZEN_SNAPSHOT" in голова, (
            "render не замораживает снимок: обновление содержимого перепишет его "
            "во время сборки, и построенное окажется не из чего проверять")

    def test_сборка_идёт_из_замороженной_копии(self, текст):
        голова = текст[:текст.index(МАРКЕР_SWITCH)]
        m = re.search(r"lords-canary-build\.py[^\n]*", голова)
        assert m, "вызов сборки не найден"
        assert "FROZEN" in m.group(0) or "LORDS_SNAPSHOT_DIR=\"${FROZEN_DIR}\"" in голова, (
            "сборка идёт из изменяемого снимка, а не из замороженной копии")


class TestЧистоеОкружениеИзКорня:
    """Воспроизведение отказа: root запускает сценарий из `/root` без переменных."""

    def _пути(self) -> dict:
        проба = (
            'SCRIPT_DIR="$(cd -- "$(dirname -- "%s")" && pwd)"; '
            'REPO="$(cd -- "${SCRIPT_DIR}/../.." && pwd)"; '
            'echo "${LORDS_SNAPSHOT_DIR:-${REPO}/var/lords/lords/catalog-cache}"'
        ) % СЦЕНАРИЙ
        готово = subprocess.run(["/bin/bash", "-c", проба], capture_output=True,
                                text=True, cwd="/", env={"PATH": "/usr/bin:/bin"})
        return {"snapshot_dir": готово.stdout.strip()}

    def test_умолчание_вне_рабочего_дерева_не_существует(self):
        """Это и есть отказ: путь по умолчанию ведёт в каталог, которого нет."""
        путь = Path(self._пути()["snapshot_dir"]) / "lords-02.json"
        assert not путь.is_file(), (
            f"неожиданно: {путь} существует — тогда отказ был вызван чем-то иным")

    def test_расписка_даёт_путь_которого_умолчание_не_даёт(self):
        расписка = ROOT / "var" / "canary-staging" / "lords-02.render.json"
        if not расписка.is_file():
            pytest.skip("расписки о сборке нет: нечего проверять")
        данные = json.loads(расписка.read_text(encoding="utf-8"))
        путь = данные.get("content_snapshot_path")
        assert путь, "расписка не называет путь снимка"
        assert Path(путь).is_absolute(), f"путь не абсолютный: {путь}"
        assert Path(путь).is_file(), f"снимок из расписки не существует: {путь}"


class TestОтпечатокСнимкаСходится:
    def test_отпечаток_замороженного_совпадает_с_распиской(self):
        расписка = ROOT / "var" / "canary-staging" / "lords-02.render.json"
        if not расписка.is_file():
            pytest.skip("расписки о сборке нет")
        данные = json.loads(расписка.read_text(encoding="utf-8"))
        путь = данные.get("content_snapshot_path")
        if not путь or not Path(путь).is_file():
            pytest.fail(f"снимок из расписки недоступен: {путь}")
        готово = subprocess.run([sys.executable, str(СНИМОК_СЦЕНАРИЙ), путь],
                                capture_output=True, text=True, timeout=900)
        assert готово.returncode == 0, готово.stderr[-500:]
        записей, отпечаток = готово.stdout.split()
        assert отпечаток == данные["content_snapshot_digest"], (
            f"отпечаток снимка разошёлся: на диске {отпечаток}, "
            f"в расписке {данные['content_snapshot_digest']}")
        assert int(записей) == данные["content_snapshot_items"]
