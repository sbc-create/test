"""Отпечаток артефакта покрывает всё, из чего собираются страницы.

Найдено на живом примере. Правка `Catalog.years()` убрала со всех витрин
раздел `/years/0/` — заметное изменение вывода. Отпечаток артефакта при этом не
сдвинулся ни на бит, версия осталась восемнадцатой. Предполётная проверка
canary сверяет именно отпечаток, то есть пропустила бы другую сборку под
прежним номером и сочла бы её той же самой.

Это не понижение версии, а изменение без версии — и молчит оно точно так же.

Причина: список источников набран руками. В нём `render`, `theme`, `player` и
`pagination`, а `fixtures` — с разбиением по годам, странам и жанрам, то есть с
решением о том, какие разделы у витрины вообще есть, — в нём нет. Как нет и
`live_catalog`, переводящего поля источника в каталог.

Поэтому список здесь не сверяется с другим списком: проверка собирает страницы
в чистом интерпретаторе и смотрит, какие модули для этого понадобились. Всё,
что участвовало, обязано входить в отпечаток. Появится новый модуль — проверка
узнает о нём сама.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from factory.templates import digest as digest_mod  # noqa: E402

SNAPSHOT = Path("/srv/site-factory/repo/var/lords/lords/catalog-cache/lords-02.json")

# Сборка идёт отдельным процессом намеренно: `sys.modules` — состояние всего
# интерпретатора, и в общем прогоне туда попадают модули, затянутые соседними
# тестами. Такой замер показал бы участие того, что в сборке не участвует.
PROBE = r"""
import json, pathlib, sys
sys.path.insert(0, %r)
import yaml
from factory.lords import render as render_mod, live_catalog
snapshot = pathlib.Path(%r)
entries = json.loads(snapshot.read_text(encoding="utf-8"))
entries = (entries["items"] if isinstance(entries, dict) else entries)[:60]
package = yaml.safe_load(
    (pathlib.Path(%r) / "sites/zona-cinema-preview/package.yaml").read_text(encoding="utf-8"))
render_mod.render_site(package, catalog=live_catalog.catalog_from_live(entries),
                       environ={}, publisher_id="1")
print(json.dumps(sorted(m for m in sys.modules if m.startswith("factory.lords."))))
"""


def _modules_used_by_a_render() -> list[str]:
    probe = PROBE % (str(ROOT), str(SNAPSHOT), str(ROOT))
    result = subprocess.run([sys.executable, "-c", probe],
                            capture_output=True, text=True, cwd=str(ROOT), timeout=600)
    if result.returncode != 0:
        pytest.fail(f"сборка в чистом интерпретаторе не прошла:\n{result.stderr[-2000:]}")
    return json.loads(result.stdout.strip().splitlines()[-1])


@pytest.fixture(scope="module")
def покрытие() -> set[str]:
    return {m["path"] for m in digest_mod.compute()["members"]}


@pytest.mark.skipif(not SNAPSHOT.is_file(),
                    reason="снимка боевого каталога нет: состав сборки не измерить")
def test_каждый_модуль_сборки_входит_в_отпечаток(покрытие):
    участники = _modules_used_by_a_render()
    вне = sorted(m.replace(".", "/") + ".py" for m in участники
                 if m.replace(".", "/") + ".py" not in покрытие)
    assert вне == [], (
        "модули участвуют в сборке страниц, но в отпечаток артефакта не входят: "
        + ", ".join(вне)
        + " — правка любого из них меняет вывод, не двигая версию артефакта")


def test_выгрузка_входит_в_отпечаток(покрытие):
    """`serve` пишет дерево выкладки, и его поведение — часть артефакта.

    В сборке страниц он не участвует и замером не ловится, поэтому назван
    отдельно. Именно в нём жила невычищаемая выгрузка, оставлявшая снятые
    страницы доступными по их адресам.
    """
    assert "factory/lords/serve.py" in покрытие


def test_отпечаток_меняется_от_правки_разбиения(tmp_path, покрытие):
    """Смысл проверки — в этом: правка разбиения обязана двигать отпечаток."""
    assert "factory/lords/fixtures.py" in покрытие, (
        "разбиение по годам, странам и жанрам решает, какие разделы есть у "
        "витрины; вне отпечатка эта правка проходит немой")
