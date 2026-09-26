"""Издатель каталога: отказ одной ячейки не отменяет доставку остальным.

Живой отказ, ради которого проверка написана. Суточный прогон 25 сентября упал
целиком:

    OSError: [Errno 30] Read-only file system:
      '/srv/lordfilm47-space/data/lords-01-catalog.json.<pid>.tmp'

Файловая система была rw — «read-only» оказалось свойством песочницы юнита:
`ProtectSystem=strict` и `ReadWritePaths`, в котором каталогов данных ячеек не
было. Важно не это, а то, что исключение уходило из `доставить_ячейкам`
наверх. Порядок доставки — `sorted(ВИТРИНЫ)`, первым идёт `lords-01`, и до
остальных витрин очередь не доходила ни разу: пять готовых снимков не уехали
из-за одной недоступной папки, и прогон не оставил даже отчёта.

Расширение `ReadWritePaths` лечило случай, а не род ошибки: список путей
строится по реестру, и любая ячейка, появившаяся в реестре позже установки
drop-in, возвращала бы ту же остановку целого прогона. Ровно это и произошло
бы с `zona-02`, добавленной в реестр 25 сентября.

Проверяется поведение, а не текст: одна ячейка недоступна на запись — она
названа в отчёте с ошибкой, вторая получает и каталог, и подробности. И
отдельно — что расхождение sha256 остановкой БЫТЬ не перестало: среда и
содержимое не равны, и продолжать прогон, записавший в ячейку не то, нельзя.

Издатель живёт вне этого репозитория (`/srv/site-factory/repo`, ветка витрин) и
тянет свой пакет `factory` оттуда же. Поэтому сценарий выполняется отдельным
процессом с его корнем на `sys.path`: импортировать его в наш процесс значит
подсунуть ему наш `factory` и проверить не то, что работает на хосте. Нет файла
или не поднимается окружение — пропуск с названной причиной.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import textwrap
from pathlib import Path

import pytest

КОРЕНЬ_ИЗДАТЕЛЯ = Path("/srv/site-factory/repo")
ИЗДАТЕЛЬ = КОРЕНЬ_ИЗДАТЕЛЯ / "automation" / "host" / "nova-catalog-publish.py"

СЦЕНАРИЙ = textwrap.dedent('''
    import hashlib, importlib.util, json, stat, sys
    from pathlib import Path

    корень, рабочий = Path(sys.argv[1]), Path(sys.argv[2])
    sys.path.insert(0, str(корень))
    sys.path.insert(0, str(корень / "automation" / "host"))
    спец = importlib.util.spec_from_file_location(
        "nova_catalog_publish", корень / "automation" / "host" / "nova-catalog-publish.py")
    м = importlib.util.module_from_spec(спец)
    sys.modules["nova_catalog_publish"] = м
    спец.loader.exec_module(м)

    доступная, закрытая = рабочий / "ok", рабочий / "closed"
    доступная.mkdir(parents=True); закрытая.mkdir(parents=True)
    закрытая.chmod(stat.S_IRUSR | stat.S_IXUSR)

    карта = {
        "site-ok": {"managed_by": "cell", "data_owner": "pipeline",
                    "data_dir": str(доступная), "reload": "mtime"},
        "site-closed": {"managed_by": "cell", "data_owner": "pipeline",
                        "data_dir": str(закрытая), "reload": "mtime"},
    }
    м.размещения = lambda *a, **k: карта

    тексты, отчёт = {}, {"sites": {}}
    for s in карта:
        кат = json.dumps({"items": [], "revision": "r1"}, ensure_ascii=False)
        под = json.dumps({"записи": {}}, ensure_ascii=False)
        тексты[s] = {"catalog": кат, "details": под}
        отчёт["sites"][s] = {"expected_sha256": {
            "catalog": hashlib.sha256(кат.encode()).hexdigest(),
            "details": hashlib.sha256(под.encode()).hexdigest()}}

    свод = {}
    try:
        итог = м.доставить_ячейкам(sorted(карта), тексты, отчёт)
        свод["delivery"] = итог
    except Exception as ош:
        свод["raised"] = f"{type(ош).__name__}: {ош}"
    finally:
        закрытая.chmod(stat.S_IRWXU)
    свод["files_ok"] = sorted(p.name for p in доступная.iterdir())

    # Расхождение содержимого обязано остаться остановкой.
    цель = рабочий / "mismatch"; цель.mkdir(parents=True)
    м.размещения = lambda *a, **k: {"site-ok": {
        "managed_by": "cell", "data_owner": "pipeline",
        "data_dir": str(цель), "reload": "mtime"}}
    try:
        м.доставить_ячейкам(["site-ok"], {"site-ok": {"catalog": "{}", "details": "{}"}},
                            {"sites": {"site-ok": {"expected_sha256": {
                                "catalog": "0" * 64, "details": "0" * 64}}}})
        свод["mismatch"] = "не остановился"
    except м.PublishError:
        свод["mismatch"] = "PublishError"
    except Exception as ош:
        свод["mismatch"] = f"другое: {type(ош).__name__}"
    print(json.dumps(свод, ensure_ascii=False))
''')


def выполнить(tmp_path) -> dict:
    if not ИЗДАТЕЛЬ.is_file():
        pytest.skip(f"издателя нет по пути {ИЗДАТЕЛЬ}: проверять нечего")
    if os.geteuid() == 0:
        pytest.skip("от root снятие права записи ничего не запрещает")
    сценарий = tmp_path / "сценарий.py"
    сценарий.write_text(СЦЕНАРИЙ, encoding="utf-8")
    прогон = subprocess.run(
        [sys.executable, str(сценарий), str(КОРЕНЬ_ИЗДАТЕЛЯ), str(tmp_path / "стенд")],
        capture_output=True, text=True, timeout=300)
    if прогон.returncode != 0:
        pytest.skip("издатель не поднимается в этом окружении: "
                    + (прогон.stderr.strip().splitlines() or ["без вывода"])[-1])
    return json.loads(прогон.stdout.strip().splitlines()[-1])


def test_недоступная_ячейка_не_отменяет_доставку_остальным(tmp_path):
    свод = выполнить(tmp_path)
    assert "raised" not in свод, (
        f"отказ одной ячейки уронил весь прогон: {свод['raised']}")
    плохая = свод["delivery"]["site-closed"]
    assert плохая.get("error"), f"отказ записи не назван: {плохая}"
    хорошая = свод["delivery"]["site-ok"]
    assert not хорошая.get("error"), хорошая
    assert свод["files_ok"] == ["site-ok-catalog.json", "site-ok-details.json"], (
        f"доступной ячейке доставлено не всё: {свод['files_ok']}")


def test_несоответствие_содержимого_остаётся_остановкой(tmp_path):
    свод = выполнить(tmp_path)
    assert свод["mismatch"] == "PublishError", (
        "в ячейку легло не то, что проверено, а прогон продолжился: "
        + свод["mismatch"])
