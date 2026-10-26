#!/usr/bin/env python3
"""Зафиксированный выпуск службы вне рабочих ветвей — с описью и откатом.

Повод — MOD-198: 18 действующих служб запускаются из пяти рабочих копий, и все
пять грязные, то есть исполняют код, которого нет ни в одном коммите. Владелец
поручил устранять это поэтапно, существующим механизмом установки и проверки.

Образец взят у `k2-install-delivery.py` и обобщён: копия (не ссылка на дерево),
опись `INSTALL.json` с коммитом источника и суммой каждого файла, отдельная
команда сверки. Добавлено то, чего там не было и что требует задание:

* **выпуски рядом и ссылка `current`** — как у витрин: откат это переключение
  ссылки, а не повторная сборка;
* **незакоммиченные файлы названы в описи отдельно.** Перенести службу, не
  взяв их, значит откатить её поведение на неизвестную величину; взять их
  молча — значит зафиксировать в выпуске то, чего нет в истории. Поэтому они
  переносятся и ПЕРЕЧИСЛЯЮТСЯ как отклонение от коммита;
* **пакетные `__init__.py` добираются сами.** Разбор импортов их не называет
  (их никто не импортирует по имени), а без них установленная копия не
  импортируется вовсе — проверено на первой же службе;
* **состав берётся у измерителя зависимостей**, а не задаётся списком: список
  в коде разошёлся бы с действительностью, как это уже было с составом узла.

Данные служба продолжает читать и писать там, где они лежат (`/var/lib/…`,
`/srv/…`): выпуск — это код, а не данные. Пути данных печатаются, чтобы при
переносе их никто не искал заново.

    python3 automation/local/install-service-release.py --service seo-report-viewer.service
    python3 automation/local/install-service-release.py --service … --provision
    python3 automation/local/install-service-release.py --service … --verify
    python3 automation/local/install-service-release.py --service … --rollback
"""
from __future__ import annotations

import argparse
import datetime as _dt
import hashlib
import importlib.util
import json
import pathlib
import shutil
import subprocess
import sys

КОРЕНЬ = pathlib.Path(__file__).resolve().parents[2]
ВЫПУСКИ = pathlib.Path("/srv/site-factory/services")
ОПИСЬ = "INSTALL.json"


def _измеритель():
    путь = КОРЕНЬ / "automation" / "local" / "service-dependency-map.py"
    сп = importlib.util.spec_from_file_location("service_dependency_map", путь)
    м = importlib.util.module_from_spec(сп)
    сп.loader.exec_module(м)
    return м


def _сумма(путь: pathlib.Path) -> str:
    return hashlib.sha256(путь.read_bytes()).hexdigest()


def состав(служба: str) -> dict:
    """Что переносим: код, пакетные файлы, конфигурация; и что из этого грязное."""
    м = _измеритель()
    записи = [з for з in м.службы_из_копий() if з["служба"] == служба]
    if not записи:
        raise SystemExit(f"служба {служба} не найдена среди запускаемых из рабочих копий")
    разбор = м.разобрать(записи[0])
    дерево = pathlib.Path(разбор["дерево"])
    файлы = set(разбор["код"])
    # Пакетные `__init__.py` по пути каждого модуля: без них копия не
    # импортируется вовсе. И сами они тоже разбираются на импорты — иначе
    # состав остаётся неполным. Это не предположение: первый установленный
    # выпуск упал на `ModuleNotFoundError: seo_engine.content_operator.
    # methodology`, потому что `__init__.py` пакета импортирует модуль,
    # которого в составе не было. Замыкание повторяется до неизменности.
    while True:
        добавилось = False
        for отн in list(файлы):
            части = pathlib.PurePath(отн).parts[:-1]
            for глубина in range(1, len(части) + 1):
                кандидат = str(pathlib.PurePath(*части[:глубина]) / "__init__.py")
                if кандидат not in файлы and (дерево / кандидат).is_file():
                    файлы.add(кандидат)
                    добавилось = True
        for отн in list(файлы):
            if not отн.endswith(".py"):
                continue
            for п2 in м.импорты(дерево / отн, дерево):
                отн2 = str(п2.relative_to(дерево))
                if отн2 not in файлы:
                    файлы.add(отн2)
                    добавилось = True
        if not добавилось:
            break
    # Файлы, которые служба грузит ПО ПУТИ: импортом их не видно, а без них
    # перенос молча теряет часть работы (seo-daily-cycle и его
    # seo_qwen_review.py). Неразрешённые не угадываются — они остаются
    # причиной отказа в вердикте переноса.
    for з in разбор.get("догружаемые") or []:
        if з["разрешён"] and з["разрешён"] not in файлы:
            файлы.add(з["разрешён"])
            for п2 in м.импорты(дерево / з["разрешён"], дерево):
                файлы.add(str(п2.relative_to(дерево)))
    # Конфигурация переносится, если это файл в том же дереве.
    for путь in разбор["конфигурация"]:
        if (дерево / путь).is_file():
            файлы.add(путь)
    грязные = м.незакоммиченные(дерево)
    return {"служба": служба, "дерево": дерево, "разбор": разбор,
            "файлы": sorted(файлы), "грязные": sorted(set(файлы) & грязные)}


def интерпретатор(св: dict) -> dict:
    """Какой Python нужен службе — это ТОЖЕ зависимость, и не файловая.

    Измерено на первой же службе: системный python3 здесь 3.10.12, а служба
    использует `enum.StrEnum`, появившийся в 3.11. Её юнит зовёт python из
    `.venv` рабочей копии, а тот ведёт на интерпретатор uv в домашнем
    каталоге. Перенести только файлы и оставить `.venv` внутри удаляемой копии
    значило бы перенести службу наполовину.
    """
    import re
    команда = св["разбор"]["юнит"].get("ExecStart", "")
    первое = команда.split()[0] if команда.split() else ""
    итог = {"из_юнита": первое, "системный": sys.executable,
            "версия_системного": ".".join(map(str, sys.version_info[:3]))}
    путь = pathlib.Path(первое)
    if путь.name.startswith("python") and путь.is_file():
        цель = путь.resolve()
        итог["ведёт_на"] = str(цель)
        вер = subprocess.run([str(путь), "-V"], capture_output=True, text=True)
        итог["версия"] = (вер.stdout or вер.stderr).strip()
        cfg = путь.parent.parent / "pyvenv.cfg"
        if cfg.is_file():
            текст = cfg.read_text(encoding="utf-8")
            м = re.search(r"^executable = (.*)$", текст, re.M)
            итог["venv_в_копии"] = str(путь.parent.parent)
            итог["базовый_интерпретатор"] = м.group(1).strip() if м else ""
    return итог


def установить(св: dict, корень_выпусков: pathlib.Path) -> int:
    дерево, файлы = св["дерево"], св["файлы"]
    нет = [ф for ф in файлы if not (дерево / ф).is_file()]
    if нет:
        print(f"ОТКАЗ: в источнике нет файлов: {нет}", file=sys.stderr)
        return 1

    def git(*арг) -> str:
        return subprocess.run(["git", "-C", str(дерево), *арг],
                              capture_output=True, text=True).stdout.strip()

    коммит = git("rev-parse", "HEAD")
    метка = _dt.datetime.now(_dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    корень = корень_выпусков / св["служба"]
    выпуск = корень / "releases" / f"{метка}-{коммит[:12]}"
    выпуск.mkdir(parents=True, exist_ok=False)

    опись = {
        "служба": св["служба"],
        "источник": str(дерево),
        "ветка": git("rev-parse", "--abbrev-ref", "HEAD"),
        "коммит": коммит,
        "незакоммиченных_в_дереве": len(св["разбор"]["состояние_дерева"]
                                        and git("status", "--porcelain").splitlines()),
        "установлено": _dt.datetime.now(_dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "точка_входа": св["разбор"]["точка_входа"],
        "юнит_источника": св["разбор"]["юнит"],
        "пути_данных": св["разбор"]["данные"],
        "интерпретатор": интерпретатор(св),
        "файлы": {},
        "файлы_вне_коммита": св["грязные"],
    }
    for ф in файлы:
        цель = выпуск / ф
        цель.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(дерево / ф, цель)
        опись["файлы"][ф] = _сумма(цель)
    (выпуск / ОПИСЬ).write_text(json.dumps(опись, ensure_ascii=False, indent=1) + "\n",
                                encoding="utf-8")

    текущая = корень / "current"
    прежняя = корень / ".previous"
    if текущая.is_symlink():
        цель_прежней = текущая.resolve()
        if прежняя.is_symlink() or прежняя.exists():
            прежняя.unlink()
        прежняя.symlink_to(цель_прежней)
    времянка = корень / ".current.new"
    if времянка.is_symlink() or времянка.exists():
        времянка.unlink()
    времянка.symlink_to(выпуск)
    времянка.replace(текущая)

    print(f"выпуск: {выпуск}")
    print(f"   файлов {len(опись['файлы'])}, из них вне коммита "
          f"{len(опись['файлы_вне_коммита'])}: {опись['файлы_вне_коммита'] or 'ни одного'}")
    print(f"   коммит источника {коммит[:12]} ({опись['ветка']})")
    print(f"   current -> {текущая.resolve().name}"
          + (f", .previous -> {прежняя.resolve().name}" if прежняя.is_symlink() else
             ", прежнего выпуска нет"))
    print(f"   пути данных (НЕ копируются): {опись['пути_данных'] or 'нет'}")
    и = опись["интерпретатор"]
    print(f"   интерпретатор службы: {и.get('версия', '?')} из {и.get('из_юнита', '?')}")
    if и.get("venv_в_копии"):
        print(f"   ВНИМАНИЕ: venv лежит В РАБОЧЕЙ КОПИИ ({и['venv_в_копии']}) — "
              f"базовый интерпретатор {и.get('базовый_интерпретатор', '?')}; "
              "выпуску нужен свой venv, иначе перенос половинчатый")
    return 0


def самодостаточен(выпуск: pathlib.Path,
                   дерево: pathlib.Path | None = None) -> list[str]:
    """Импорты установленных файлов, которых в выпуске нет.

    Сверка сумм этого не видит: она сравнивает выпуск с ОПИСЬЮ, а не с тем,
    что коду нужно. Измерено 26.10 на двух службах из трёх: у
    community-ratings-monitor не хватало factory/community/metrics_store.py
    (`from factory.community import metrics_store` разбор счёл импортом
    ИМЕНИ), и служба не импортировалась вовсе, хотя сверка давала 0
    расхождений. У seo-engine-topvisor-inventory состав был 17 файлов из 149,
    и `--help` это скрывал: CLI импортирует подмодули при разборе команды.

    `from pkg import X` статически неразрешим: X бывает модулем и бывает
    классом. Оракул — ДЕРЕВО-ИСТОЧНИК: если там `pkg/X.py` существует, значит
    это модуль, и в выпуске он обязан быть. Без дерева проверяются только
    безусловно обязательные модули, и тогда ровно тот случай, ради которого
    проверка сделана, проходит незамеченным.
    """
    import ast as _ast
    нет = []
    файлы = sorted(выпуск.rglob("*.py"))
    for файл in файлы:
        try:
            текст = файл.read_text(encoding="utf-8", errors="replace").replace("\x00", "")
            разбор = _ast.parse(текст)
        except (OSError, SyntaxError, ValueError):
            continue
        изм = _измеритель()
        обязательные = изм._кандидаты_импорта(разбор, файл, выпуск,
                                              обязательные_только=True)
        если_модуль = []
        if дерево is not None:
            for имя in изм._кандидаты_импорта(разбор, файл, выпуск):
                if имя in обязательные:
                    continue
                if (дерево / (имя + ".py")).is_file() or \
                        (дерево / имя / "__init__.py").is_file():
                    если_модуль.append(имя)
        for имя in обязательные + если_модуль:
            верх = имя.split("/")[0]
            # Проверяется только то, что принадлежит самому выпуску: сторонние
            # пакеты берутся из venv, и их отсутствие — другой разговор.
            if not (выпуск / верх).exists():
                continue
            if (выпуск / (имя + ".py")).is_file() or (выпуск / имя / "__init__.py").is_file():
                continue
            нет.append(f"{файл.relative_to(выпуск)} → {имя.replace('/', '.')}")
    return sorted(set(нет))


def сверить(служба: str, корень_выпусков: pathlib.Path) -> int:
    текущая = корень_выпусков / служба / "current"
    if not текущая.is_symlink():
        print(f"ОТКАЗ: {текущая} не ссылка — выпуска нет", file=sys.stderr)
        return 1
    выпуск = текущая.resolve()
    оп = выпуск / ОПИСЬ
    if not оп.is_file():
        print(f"ОТКАЗ: в {выпуск} нет описи {ОПИСЬ}", file=sys.stderr)
        return 1
    опись = json.loads(оп.read_text(encoding="utf-8"))
    плохо = []
    for ф, сумма in опись["файлы"].items():
        п = выпуск / ф
        if not п.is_file() or _сумма(п) != сумма:
            плохо.append(ф)
    источник = опись.get("источник")
    дерево = pathlib.Path(источник) if источник and pathlib.Path(источник).is_dir() else None
    недостающие = самодостаточен(выпуск, дерево)
    print(f"выпуск {выпуск.name}: файлов {len(опись['файлы'])}, расхождений "
          f"{len(плохо)}, недостающих импортов {len(недостающие)}")
    for н in недостающие[:10]:
        print(f"   НЕ ХВАТАЕТ: {н}")
    for ф in плохо[:10]:
        print(f"   РАСХОЖДЕНИЕ: {ф}")
    print(f"   коммит источника {опись['коммит'][:12]} ({опись['ветка']}), "
          f"установлено {опись['установлено']}")
    if опись["файлы_вне_коммита"]:
        print(f"   ВНЕ КОММИТА на момент установки: {опись['файлы_вне_коммита']}")
    return 1 if (плохо or недостающие) else 0


def откатить(служба: str, корень_выпусков: pathlib.Path) -> int:
    корень = корень_выпусков / служба
    прежняя, текущая = корень / ".previous", корень / "current"
    if not прежняя.is_symlink():
        print("ОТКАЗ: прежнего выпуска нет — откатывать нечем", file=sys.stderr)
        return 1
    было, станет = текущая.resolve(), прежняя.resolve()
    времянка = корень / ".current.new"
    if времянка.is_symlink() or времянка.exists():
        времянка.unlink()
    времянка.symlink_to(станет)
    времянка.replace(текущая)
    прежняя.unlink()
    прежняя.symlink_to(было)
    print(f"current: {было.name} -> {станет.name} (прежним стал {было.name})")
    print("службу это НЕ перезапускает: перезапуск — отдельная привилегированная операция")
    return 0


def главная(аргв: list[str] | None = None) -> int:
    р = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    р.add_argument("--service", required=True)
    р.add_argument("--root", type=pathlib.Path, default=ВЫПУСКИ)
    р.add_argument("--provision", action="store_true", help="разложить новый выпуск")
    р.add_argument("--verify", action="store_true", help="сверить текущий выпуск с описью")
    р.add_argument("--rollback", action="store_true", help="переключить current на прежний")
    а = р.parse_args(аргв)

    if а.verify:
        return сверить(а.service, а.root)
    if а.rollback:
        return откатить(а.service, а.root)

    св = состав(а.service)
    print(f"служба {а.service}")
    print(f"   дерево: {св['дерево']} ({св['разбор']['состояние_дерева']['ветка']} "
          f"{св['разбор']['состояние_дерева']['голова']}, незакоммичено "
          f"{св['разбор']['состояние_дерева']['незакоммичено_всего']})")
    print(f"   точка входа: {св['разбор']['точка_входа']}")
    print(f"   к переносу файлов: {len(св['файлы'])}")
    for ф in св["файлы"]:
        метка = " (ВНЕ КОММИТА)" if ф in св["грязные"] else ""
        print(f"      {ф}{метка}")
    print(f"   пути данных (остаются на месте): {св['разбор']['данные'] or 'нет'}")
    if not а.provision:
        print("это перечень, а не установка: для установки нужен --provision")
        return 0
    return установить(св, а.root)


if __name__ == "__main__":
    raise SystemExit(главная())
