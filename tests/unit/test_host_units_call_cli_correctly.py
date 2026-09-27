"""Юнит обязан вызывать CLI фабрики так, как CLI его разбирает.

Почему это тест, а не комментарий. Ошибка «глобальный флаг после имени
подкоманды» уже была допущена, описана предупреждением в
`site-factory-analytics-apply.service` — и повторена в
`analytics-connect@.service`. argparse отвечает на неё
«unrecognized arguments: --json» и выходит с кодом 2, то есть служба
запускается, завершается ошибкой и НЕ создаёт ни одного счётчика. Снаружи это
выглядит как выполненная команда владельца.

Проверка идёт от самого парсера: список глобальных флагов берётся у корневого
парсера фабрики, а не переписывается сюда руками, иначе новый глобальный флаг
остался бы непокрытым.
"""
from __future__ import annotations

import functools
import re
import subprocess
import sys
from pathlib import Path

import pytest

КОРЕНЬ = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(КОРЕНЬ))

ЮНИТЫ = sorted((КОРЕНЬ / "automation" / "host").glob("*.service"))

#: Подкоманды верхнего уровня фабрики и её глобальные флаги берутся из самого
#: CLI — его выводом `--help`, а не списком, переписанным в тест. Парсер фабрики
#: собирается внутри `main()`, и импортировать его отдельно нельзя: импорт
#: `factory.__main__` сразу запускает разбор argv. Поэтому спрашиваем процесс.
@functools.lru_cache(maxsize=1)
def _usage() -> str:
    r = subprocess.run([sys.executable, "-m", "factory", "--help"],
                       cwd=str(КОРЕНЬ), capture_output=True, text=True, timeout=120)
    assert r.returncode == 0, f"factory --help вышел с {r.returncode}: {r.stderr[-300:]}"
    return r.stdout


def _глобальные_флаги() -> set[str]:
    флаги = set(re.findall(r"\[(--[a-z0-9-]+)", _usage().split("{", 1)[0]))
    флаги.discard("--help")
    return флаги


def _подкоманды() -> set[str]:
    тело = _usage().split("{", 1)[1].split("}", 1)[0]
    return {с.strip() for с in тело.split(",") if с.strip()}


def _строки_exec(текст: str) -> list[str]:
    """ExecStart с продолжениями строк, склеенные в одну команду."""
    склеено = re.sub(r"\\\s*\n\s*", " ", текст)
    return [s for s in склеено.splitlines() if s.startswith(("ExecStart=", "ExecStartPost="))]


@pytest.mark.parametrize("юнит", ЮНИТЫ, ids=lambda p: p.name)
def test_глобальный_флаг_стоит_до_подкоманды(юнит: Path) -> None:
    флаги, подкоманды = _глобальные_флаги(), _подкоманды()
    assert флаги and подкоманды, "парсер фабрики не дал ни флагов, ни подкоманд"
    for строка in _строки_exec(юнит.read_text(encoding="utf-8")):
        if "-m factory " not in строка:
            continue
        слова = строка.split()
        try:
            хвост = слова[слова.index("factory") + 1:]
        except ValueError:  # pragma: no cover - выше уже проверено вхождение
            continue
        имя = next((с for с in хвост if с in подкоманды), None)
        if имя is None:
            continue
        после = хвост[хвост.index(имя) + 1:]
        поздние = sorted(set(после) & флаги)
        assert not поздние, (
            f"{юнит.name}: глобальный флаг {', '.join(поздние)} стоит после подкоманды "
            f"«{имя}» — argparse ответит «unrecognized arguments» и служба выйдет с кодом 2"
        )


@pytest.mark.parametrize("юнит", ЮНИТЫ, ids=lambda p: p.name)
def test_специфер_каталога_credentials_не_используется(юнит: Path) -> None:
    """`%d` появился в systemd 250, на хосте 249: строка остаётся literal-ом.

    Путь вычисляет код по `$CREDENTIALS_DIRECTORY`, и модули учётных данных
    отдельно отбрасывают значение с неразвёрнутым специфером.
    """
    for строка in юнит.read_text(encoding="utf-8").splitlines():
        if строка.startswith(("Environment=", "ExecStart=", "ExecStartPre=")):
            assert "%d" not in строка, f"{юнит.name}: специфер %d — {строка}"


#: Куда юнит обязан положить причину отказа, читаемую без root.
#:
#: Повод. Прогон `analytics-cabinet.service` в 18:42 не оставил ни отчёта, ни
#: объяснения: вывод уходил только в журнал, доступа к которому у сессии нет, а
#: каталог отчётов остался пустым. Пустой каталог неотличим от «служба не
#: запускалась», и час ушёл на выяснение того, что служба запускалась и падала.
#: Причина оказалась в ReadWritePaths — но узнать это можно было только измерив
#: команду отдельно.
СЛЕД_В_ФАЙЛЕ = ("StandardError=append:", "StandardError=file:", "> var/", ">var/")

#: Свой журнал состояния на диске — равноценный след, а не исключение «чтобы
#: прошло». Исполнитель заявок пишет переходы каждой заявки в каталог очереди и
#: восстанавливается по нему после гибели процесса; отказ виден в состоянии
#: заявки, а не в перехваченном stderr. Признак — объявление каталога очереди.
СВОЙ_ЖУРНАЛ = ("SITE_CELL_QUEUE=",)


@pytest.mark.parametrize("юнит", ЮНИТЫ, ids=lambda p: p.name)
def test_причина_отказа_читается_без_root(юнит: Path) -> None:
    текст = юнит.read_text(encoding="utf-8")
    if "-m factory" not in текст and "bin/seo-operator" not in текст:
        pytest.skip(f"{юнит.name}: не запускает команду репозитория")
    if any(признак in текст for признак in СВОЙ_ЖУРНАЛ):
        return
    assert any(признак in текст for признак in СЛЕД_В_ФАЙЛЕ), (
        f"{юнит.name}: вывод уходит только в журнал. Отказ будет виден как пустой "
        "каталог отчётов, неотличимый от «служба не запускалась»")


@pytest.mark.parametrize("юнит", ЮНИТЫ, ids=lambda p: p.name)
def test_каталог_артефактов_открыт_если_команда_в_него_пишет(юнит: Path) -> None:
    """`ProtectSystem=strict` отказывает в записи молча — для процесса это EACCES.

    `bin/seo-operator analytics-collect` пишет не только файл из `--out`, но и
    артефакт прогона в `artifacts/`. Измерено прямым запуском той же команды.
    """
    текст = юнит.read_text(encoding="utf-8")
    if "ProtectSystem=strict" not in текст or "bin/seo-operator" not in текст:
        pytest.skip(f"{юнит.name}: условие не про этот юнит")
    пути = " ".join(s for s in текст.splitlines() if s.startswith("ReadWritePaths="))
    assert "/artifacts" in пути, (
        f"{юнит.name}: команда пишет artifacts/, а путь не открыт на запись — "
        "прогон отказывает и не оставляет отчёта")
