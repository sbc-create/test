#!/usr/bin/env python3
"""Порядок запуска проверок: соблюдает ли рабочий процесс правила расхода.

Зачем инструмент, а не документ. Правила расхода Actions нарушаются молча: ни
один прогон не падает из-за того, что он лишний. Поэтому они проверяются
машиной — на файлах рабочих процессов, до того как прогон состоится.

Правила выведены из замера 13.10 (минуты реконструированы по заданиям; поле
`billable` этому токену отдаёт 0 даже у прогона, шедшего 4,5 минуты):

    закрытые репозитории        4 143 мин за 48 ч = 2 072 мин/сутки
      ott-app-sandbox:CI        2 982 (72 %), из них эмуляторы 2 116
      21 ячейка site-*:release  1 161 (28 %)
    открытый sbc-create/test      276 мин — квоту НЕ тратят
    вытеснено (новый коммит пришёл раньше конца прежнего прогона): 64,2 %

Проверяемые правила и то, чем каждое оплачено:

  ОТМЕНА      у процесса есть `concurrency`, группа включает ветвь, и отмена
              включена вне `main`. 64,2 % минут ушли в прогоны, чей результат
              к голове ветви уже не относился.
  ДОКУМЕНТЫ   у `push` и `pull_request` есть `paths-ignore` с документацией:
              правка отчёта не должна стоить прогона.
  ПРЕДЕЛ      у каждого задания есть `timeout-minutes`: иначе зависшее задание
              списывает минуты до шести часов по умолчанию.
  ДУБЛЬ       `pull_request` без `types` повторяет то, что уже проверил
              `push` по той же ветви.
  ТЯЖЁЛОЕ     задание, которое ЗАПУСКАЕТ эмулятор (`uses` с
              `emulator-runner`) или включено входом ручного запуска
              (`inputs.e2e`, `inputs.tv4k`, `inputs.soak`), не идёт по
              коммиту и по расписанию чаще раза в сутки. Признак по `uses`, а
              не по словам в именах шагов: иначе шестиминутная сборка APK
              попадает в тяжёлые из-за шага «e2e helper unit tests».

Исходы различимы и ни один не выводится из другого:
  СОБЛЮДЕНО   правило выполнено
  НАРУШЕНО    правило не выполнено, и это видно в файле
  НЕ ИЗМЕРЕНО файл не разобран (нет pyyaml, битый YAML) — это не «соблюдено»

Только чтение файлов. Сети не касается, прогонов не запускает.

    python3 automation/local/workflow-policy-check.py
    python3 automation/local/workflow-policy-check.py --file путь/к/ci.yml
    python3 automation/local/workflow-policy-check.py --template
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

КОРЕНЬ = Path(__file__).resolve().parents[2]

СОБЛЮДЕНО = "СОБЛЮДЕНО"
НАРУШЕНО = "НАРУШЕНО"
НЕ_ИЗМЕРЕНО = "НЕ ИЗМЕРЕНО"

#: Что считается документацией: изменение таких путей сборку не затрагивает.
ДОКУМЕНТЫ = ("docs/**", "**/*.md")
#: Действия, запуск которых и делает задание тяжёлым. Признак взят из того,
#: что задание ОБЪЯВЛЯЕТ в `uses`, а не из слов в именах шагов: 13.10 правило
#: по словам объявило тяжёлым шестиминутную сборку APK, потому что в ней есть
#: шаг «e2e helper unit tests (anr attribution)» — юнит-тест про e2e.
ТЯЖЁЛЫЕ_ДЕЙСТВИЯ = ("emulator-runner", "android-emulator", "macos-emulator")
#: Входы ручного запуска, которыми включаются тяжёлые сценарии.
ТЯЖЁЛЫЕ_ВХОДЫ = ("inputs.e2e", "inputs.tv4k", "inputs.soak")


def триггеры(разобран: dict) -> dict:
    """Блок `on`. В YAML 1.1 ключ `on` разбирается как булево True."""
    for ключ in (True, "on", "On", "ON"):
        if ключ in разобран:
            значение = разобран[ключ]
            return значение if isinstance(значение, dict) else {}
    return {}


def _перечень(значение) -> list[str]:
    if значение is None:
        return []
    if isinstance(значение, str):
        return [значение]
    if isinstance(значение, list):
        return [str(x) for x in значение]
    return []


def покрывает_рабочие_ветви(разобран: dict) -> bool:
    """Запускается ли процесс на чём-то кроме `main`.

    Нужно, чтобы правило отмены не осуждало верное поведение: процесс,
    который идёт только на `main` и публикует набор, обязан НЕ отменяться.
    Первый прогон проверки записал `deploy.yml` в нарушители именно поэтому.
    """
    т = триггеры(разобран)
    if "pull_request" in т or "pull_request_target" in т:
        return True
    пуш = т.get("push")
    if пуш is None:
        return False
    ветви = _перечень(пуш.get("branches") if isinstance(пуш, dict) else None)
    if not ветви:
        # `push` без фильтра ветвей — это все ветви.
        return True
    return any(в not in ("main", "master") for в in ветви)


def правило_отмены(разобран: dict) -> tuple[str, str]:
    рабочие = покрывает_рабочие_ветви(разобран)
    c = разобран.get("concurrency")
    if not c:
        if not рабочие:
            return СОБЛЮДЕНО, ("процесс идёт только на main: вытеснять там "
                               "нечего, группа не обязательна")
        return НАРУШЕНО, "блока concurrency нет: вытесненные прогоны доходят до конца"
    if isinstance(c, str):
        return НАРУШЕНО, (f"concurrency задан строкой {c!r}: отмена не настроена, "
                          "и группа не зависит от ветви")
    группа = str(c.get("group") or "")
    отмена = str(c.get("cancel-in-progress"))
    беды = []
    if "github.ref" not in группа and "github.head_ref" not in группа:
        беды.append("группа не включает ветвь — прогоны разных ветвей встанут "
                    "в очередь друг за другом")
    if отмена in ("None", "", "false", "False"):
        if рабочие:
            беды.append("cancel-in-progress выключен на всех ветвях, а процесс "
                        "идёт и на рабочих")
    elif отмена in ("true", "True"):
        беды.append("cancel-in-progress включён и на main: приёмку выпуска "
                    "обрывать нельзя")
    elif "github.ref" not in отмена:
        беды.append(f"cancel-in-progress={отмена!r} не различает ветви")
    if беды:
        return НАРУШЕНО, "; ".join(беды)
    пояснение = f"группа {группа!r}, отмена {отмена!r}"
    if not рабочие:
        пояснение += " (процесс только на main — выключенная отмена верна)"
    return СОБЛЮДЕНО, пояснение


def правило_документов(разобран: dict) -> tuple[str, str]:
    т = триггеры(разобран)
    беды = []
    нашлось = False
    for событие in ("push", "pull_request"):
        тело = т.get(событие)
        if тело is None:
            continue
        нашлось = True
        if not isinstance(тело, dict):
            беды.append(f"{событие}: фильтров нет вовсе")
            continue
        игнор = set(_перечень(тело.get("paths-ignore")))
        пути = set(_перечень(тело.get("paths")))
        if пути:
            # Белый список путей сам по себе исключает документацию.
            continue
        не_хватает = [ш for ш in ДОКУМЕНТЫ if ш not in игнор]
        if не_хватает:
            беды.append(f"{событие}: в paths-ignore нет {', '.join(не_хватает)}")
    if not нашлось:
        return СОБЛЮДЕНО, "процесс не запускается по push и pull_request"
    return (НАРУШЕНО, "; ".join(беды)) if беды else (
        СОБЛЮДЕНО, "правка документации проверок не запускает")


def правило_предела(разобран: dict) -> tuple[str, str]:
    задания = разобран.get("jobs") or {}
    без = [имя for имя, тело in задания.items()
           if isinstance(тело, dict) and not тело.get("timeout-minutes")]
    if без:
        return НАРУШЕНО, (f"без timeout-minutes: {', '.join(без)} — зависшее "
                          "задание списывает минуты до шести часов")
    return СОБЛЮДЕНО, f"предел есть у всех заданий ({len(задания)})"


def правило_дубля(разобран: dict) -> tuple[str, str]:
    т = триггеры(разобран)
    пр = т.get("pull_request")
    пуш = т.get("push")
    if пр is None or пуш is None:
        return СОБЛЮДЕНО, "push и pull_request вместе не заданы — дубля нет"
    типы = _перечень((пр or {}).get("types") if isinstance(пр, dict) else None)
    ветви = _перечень((пуш or {}).get("branches") if isinstance(пуш, dict) else None)
    # Дубль возникает, когда push покрывает рабочие ветви: тогда каждый push в
    # ветвь PR проверяется дважды.
    покрывает = any(в not in ("main", "master") for в in ветви)
    if покрывает and not типы:
        return НАРУШЕНО, (f"push покрывает {ветви}, а у pull_request нет types: "
                          "каждый коммит в ветвь PR проверяется дважды")
    if "synchronize" in типы:
        return НАРУШЕНО, ("pull_request types содержит synchronize — это и есть "
                          "повтор того, что проверил push")
    return СОБЛЮДЕНО, (f"pull_request types={типы or 'по умолчанию'}, "
                       f"push branches={ветви or 'все'}")


def тяжёлые_задания(разобран: dict) -> list[str]:
    """Задания, которые дорого стоят, по их собственному объявлению."""
    итог = []
    for имя, тело in (разобран.get("jobs") or {}).items():
        if not isinstance(тело, dict):
            continue
        тяжёлое = False
        for шаг in тело.get("steps") or []:
            if not isinstance(шаг, dict):
                continue
            использует = str(шаг.get("uses") or "").lower()
            if any(д in использует for д in ТЯЖЁЛЫЕ_ДЕЙСТВИЯ):
                тяжёлое = True
                break
        условие = str(тело.get("if") or "")
        if any(в in условие for в in ТЯЖЁЛЫЕ_ВХОДЫ):
            тяжёлое = True
        if тяжёлое:
            итог.append(str(имя))
    return итог


def правило_тяжёлого(разобран: dict) -> tuple[str, str]:
    тяжёлые = тяжёлые_задания(разобран)
    if not тяжёлые:
        return СОБЛЮДЕНО, "тяжёлых заданий в процессе нет"
    т = триггеры(разобран)
    беды = []
    for имя in тяжёлые:
        тело = (разобран.get("jobs") or {}).get(имя) or {}
        условие = str(тело.get("if") or "")
        по_коду = any(с in т for с in ("push", "pull_request"))
        if по_коду and "workflow_dispatch" not in условие and "inputs." not in условие:
            беды.append(f"{имя}: запускается по коммиту без условия на ручной "
                        "запуск")
    расписание = т.get("schedule")
    if расписание:
        for запись in _перечень_расписаний(расписание):
            if not _не_чаще_суток(запись):
                беды.append(f"расписание {запись!r} чаще раза в сутки")
    return (НАРУШЕНО, "; ".join(беды)) if беды else (
        СОБЛЮДЕНО, f"тяжёлые задания ({', '.join(тяжёлые)}) идут по условию")


def _перечень_расписаний(значение) -> list[str]:
    if isinstance(значение, list):
        return [str((з or {}).get("cron") if isinstance(з, dict) else з)
                for з in значение]
    return []


def _не_чаще_суток(cron: str) -> bool:
    """Запись cron запускает не чаще раза в сутки.

    Разбираются только минута и час: если в них есть `*`, `/` или список, то
    запусков больше одного в сутки. Непонятная запись считается НАРУШЕНИЕМ, а
    не «наверное, редко»: ошибиться в сторону лишнего прогона дороже.
    """
    части = cron.split()
    if len(части) < 5:
        return False
    минута, час = части[0], части[1]
    for поле in (минута, час):
        if "*" in поле or "/" in поле or "," in поле or "-" in поле:
            return False
    return True


ПРАВИЛА = (
    ("ОТМЕНА", правило_отмены),
    ("ДОКУМЕНТЫ", правило_документов),
    ("ПРЕДЕЛ", правило_предела),
    ("ДУБЛЬ", правило_дубля),
    ("ТЯЖЁЛОЕ", правило_тяжёлого),
)


def проверить(текст: str) -> list[tuple[str, str, str]]:
    """[(правило, исход, пояснение)] для одного файла рабочего процесса."""
    try:
        import yaml
    except ImportError:
        return [(имя, НЕ_ИЗМЕРЕНО, "pyyaml не установлен — файл не разобран")
                for имя, _ in ПРАВИЛА]
    try:
        разобран = yaml.safe_load(текст)
    except Exception as ош:  # noqa: BLE001 — поломка называется
        return [(имя, НЕ_ИЗМЕРЕНО, f"YAML не разобран: {type(ош).__name__}")
                for имя, _ in ПРАВИЛА]
    if not isinstance(разобран, dict):
        return [(имя, НЕ_ИЗМЕРЕНО, "файл не похож на рабочий процесс")
                for имя, _ in ПРАВИЛА]
    return [(имя, *функция(разобран)) for имя, функция in ПРАВИЛА]


def шаблон_ячейки() -> str:
    import importlib.util

    путь = КОРЕНЬ / "factory" / "cell" / "extract.py"
    спец = importlib.util.spec_from_file_location("cell_extract_check", путь)
    м = importlib.util.module_from_spec(спец)
    sys.modules.setdefault("cell_extract_check", м)
    спец.loader.exec_module(м)
    return м.CI_WORKFLOW.format(domain="пример.site", site_id="пример-01")


def главная(аргв: list[str] | None = None) -> int:
    р = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    р.add_argument("--file", action="append", default=[], type=Path)
    р.add_argument("--template", action="store_true",
                   help="проверить шаблон CI ячейки из factory/cell/extract.py")
    р.add_argument("--json", action="store_true")
    а = р.parse_args(аргв)

    цели: list[tuple[str, str]] = []
    if а.file:
        for ф in а.file:
            if not ф.is_file():
                print(f"ОТКАЗ: {ф} не найден", file=sys.stderr)
                return 2
            цели.append((str(ф), ф.read_text(encoding="utf-8")))
    else:
        для_проверки = sorted((КОРЕНЬ / ".github" / "workflows").glob("*.yml"))
        цели += [(str(ф.relative_to(КОРЕНЬ)), ф.read_text(encoding="utf-8"))
                 for ф in для_проверки]
        а.template = True
    if а.template:
        цели.append(("factory/cell/extract.py::CI_WORKFLOW", шаблон_ячейки()))

    итог = {}
    нарушений = 0
    неизмеренных = 0
    for имя, текст in цели:
        строки = проверить(текст)
        итог[имя] = [{"правило": п, "исход": и, "пояснение": пз}
                     for п, и, пз in строки]
        нарушений += sum(1 for _, и, _ in строки if и == НАРУШЕНО)
        неизмеренных += sum(1 for _, и, _ in строки if и == НЕ_ИЗМЕРЕНО)

    if а.json:
        print(json.dumps({"файлы": итог, "нарушений": нарушений,
                          "не_измерено": неизмеренных},
                         ensure_ascii=False, indent=1))
    else:
        print("ПОРЯДОК ЗАПУСКА ПРОВЕРОК: СОБЛЮДЕНИЕ ПРАВИЛ РАСХОДА\n")
        for имя, строки in итог.items():
            print(f"{имя}")
            for с in строки:
                метка = {СОБЛЮДЕНО: "[+]", НАРУШЕНО: "[x]",
                         НЕ_ИЗМЕРЕНО: "[?]"}[с["исход"]]
                print(f"   {метка} {с['правило']:11} {с['исход']:12} "
                      f"{с['пояснение']}")
            print()
        print(f"нарушений: {нарушений}; не измерено: {неизмеренных}")
        if неизмеренных:
            print("«не измерено» — это не «соблюдено»: файл не разобран")

    if неизмеренных:
        return 2
    return 1 if нарушений else 0


if __name__ == "__main__":
    sys.exit(главная())
