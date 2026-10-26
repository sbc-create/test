#!/usr/bin/env python3
"""Что ФАКТИЧЕСКИ нужно службе, запущенной из рабочей копии сессии.

Повод — MOD-198: 18 действующих служб запускаются из пяти рабочих копий, и все
пять грязные. Владелец поручил устранить это поэтапно, а перед переносом
установить по каждой службе её зависимости, незакоммиченные изменения,
конфигурацию и расположение данных. Угадывать здесь нельзя: перенос по
неполному набору даёт службу, которая запускается и молча делает не то.

Что измеряется по каждой службе (и ничего не домысливается):

* **юнит** — `ExecStart`, `WorkingDirectory`, `User`, `Environment`,
  `EnvironmentFile`, и какой таймер её запускает;
* **точка входа** — файл или модуль из `ExecStart`, разрешённый в дереве;
* **код** — транзитивные импорты точки входа, разрешённые В ЭТОМ ЖЕ дереве
  (стандартная библиотека и сторонние пакеты не переносятся: они в системе);
* **конфигурация** — пути вида `config/…`, `inventory/…`, `schemas/…`,
  встреченные в найденных файлах;
* **данные** — пути записи: `var/…`, `/srv/…`, `/var/lib/…`;
* **незакоммиченное** — какие из нужных файлов отличаются от HEAD дерева.
  Это главный ответ: перенести службу, не взяв её незакоммиченные файлы,
  значит откатить её поведение на неизвестную величину.

Чего инструмент НЕ делает: не копирует, не правит юниты, не останавливает
службы. Только измерение и опись.

    python3 automation/local/service-dependency-map.py
    python3 automation/local/service-dependency-map.py --service analytics-cabinet.service
    python3 automation/local/service-dependency-map.py --json
"""
from __future__ import annotations

import argparse
import ast
import json
import pathlib
import re
import subprocess
import sys

ЮНИТЫ = pathlib.Path("/etc/systemd/system")
ПОЛЬЗ = pathlib.Path("/home/claude/.config/systemd/user")
КОРНИ_КОПИЙ = pathlib.Path("/home/claude")
ПУТИ_КОНФИГА = ("config/", "inventory/", "schemas/", "knowledge/", "blueprints/")
ПУТИ_ДАННЫХ = ("var/", "/srv/", "/var/lib/", "/home/k2deploy/")


def _включённые(корень: pathlib.Path) -> set[str]:
    итог: set[str] = set()
    for цель in ("multi-user.target.wants", "timers.target.wants", "default.target.wants"):
        д = корень / цель
        if д.is_dir():
            итог |= {п.name for п in д.iterdir()}
    return итог


def службы_из_копий() -> list[dict]:
    """Службы, чей юнит ссылается на рабочую копию сессии."""
    найдено = []
    for корень in (ЮНИТЫ, ПОЛЬЗ):
        if not корень.is_dir():
            continue
        включены = _включённые(корень)
        for файл in sorted(корень.glob("*.service")):
            try:
                текст = файл.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue
            копии = sorted(set(re.findall(r"/home/claude/(wt-[A-Za-z0-9._-]+)", текст)))
            if not копии:
                continue
            таймеры = []
            for т in sorted(корень.glob("*.timer")):
                тт = т.read_text(encoding="utf-8", errors="replace")
                цель = (re.search(r"^Unit=(\S+)", тт, re.M) or [None])
                имя = цель.group(1) if hasattr(цель, "group") else т.name.replace(".timer", ".service")
                if имя == файл.name and т.name in включены:
                    таймеры.append(т.name)
            найдено.append({
                "служба": файл.name,
                "уровень": "система" if корень == ЮНИТЫ else "пользователь",
                "копии": копии,
                "включена_сама": файл.name in включены,
                "таймеры": таймеры,
                "юнит": {к: v for к, v in (
                    ("ExecStart", _поле(текст, "ExecStart")),
                    ("WorkingDirectory", _поле(текст, "WorkingDirectory")),
                    ("User", _поле(текст, "User")),
                    ("EnvironmentFile", _поле(текст, "EnvironmentFile")),
                    ("Environment", "; ".join(re.findall(r"^Environment=(.*)$", текст, re.M))),
                ) if v},
            })
    return найдено


def _поле(текст: str, имя: str) -> str:
    """Значение поля юнита, склеенное по переносам.

    systemd разрешает продолжение строки обратным слешем, и `ExecStart`
    реальных юнитов им пользуется. Первая редакция читала только первую
    строку и теряла `-m пакет.модуль` — то есть саму точку входа.
    """
    склеенный = re.sub(r"\\\s*\n\s*", " ", текст)
    м = re.search(rf"^{имя}=(.*)$", склеенный, re.M)
    return м.group(1).strip() if м else ""


def точка_входа(юнит: dict, дерево: pathlib.Path) -> tuple[pathlib.Path | None, str]:
    """Файл, который служба фактически исполняет."""
    команда = юнит.get("ExecStart", "")
    # `python -c '…'`: точка входа названа импортом внутри строки. Встречается
    # у community-ratings-monitor, и без разбора служба выглядела бы «без
    # зависимостей», что неправда.
    вставка = re.search(r"-c\s+'([^']+)'", команда) or re.search(r'-c\s+"([^"]+)"', команда)
    if вставка:
        код = вставка.group(1)
        имена = re.findall(r"from\s+([A-Za-z_][\w.]*)\s+import", код)
        имена += re.findall(r"(?<!from )\bimport\s+([A-Za-z_][\w.]*)", код)
        for имя in имена:
            путь = дерево / (имя.replace(".", "/") + ".py")
            пакет = дерево / имя.replace(".", "/") / "__init__.py"
            for кандидат in (путь, пакет):
                if кандидат.is_file():
                    return кандидат, f"импорт из -c: {имя}"
        return None, f"-c разобран, но модули {имена} в дереве не найдены"

    # `-m пакет.модуль`
    м = re.search(r"-m\s+([A-Za-z_][\w.]*)", команда)
    if м:
        путь = дерево / (м.group(1).replace(".", "/") + ".py")
        if путь.is_file():
            return путь, f"модуль {м.group(1)}"
        пакет = дерево / м.group(1).replace(".", "/") / "__main__.py"
        if пакет.is_file():
            return пакет, f"пакет {м.group(1)}"
        return None, f"модуль {м.group(1)} в дереве не найден"
    # Интерпретатор — не точка входа. Первая редакция возвращала
    # `.venv/bin/python` из ExecStart и честно сообщала «файлов кода: 1»:
    # формально верно, по сути бесполезно.
    ИНТЕРПРЕТАТОРЫ = ("python", "python3", "bash", "sh", "node", "env")
    for слово in команда.split():
        имя = слово.rsplit("/", 1)[-1]
        if имя in ИНТЕРПРЕТАТОРЫ or имя.startswith("python"):
            continue
        # Принадлежность дереву проверяется ПУТЁМ, а не префиксом имени:
        # привязка к `/home/claude/wt-` делала инструмент непроверяемым и
        # сломалась бы на дереве, лежащем в другом месте.
        кандидат = pathlib.Path(слово)
        if кандидат.is_file() and кандидат.is_relative_to(дерево):
            return кандидат, "файл из ExecStart"
        if слово.startswith(("automation/", "seo_operator/", "factory/", "scripts/", "bin/")):
            путь = дерево / слово
            if путь.is_file():
                return путь, "относительный путь из ExecStart"
    # Обёртка ВНЕ дерева: сама команда дерева не называет, а зависимость от
    # него прячет в PYTHONPATH. Так устроен community-ratings-gateway —
    # /usr/local/bin/… с `export PYTHONPATH=<рабочая копия>` и `python -c`.
    # Это худший вид привязки: в юните видно только WorkingDirectory.
    for слово in команда.split():
        п_ = pathlib.Path(слово)
        if not слово.startswith("/") or not п_.is_file() or п_.is_relative_to(дерево):
            continue
        try:
            тело = п_.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        if str(дерево) not in тело:
            continue
        вложенный = re.search(r"-c\s+'([^']+)'", тело) or re.search(r"-m\s+([A-Za-z_][\w.]*)", тело)
        if not вложенный:
            continue
        код = вложенный.group(1)
        имена = re.findall(r"from\s+([A-Za-z_][\w.]*)\s+import", код) or [код]
        for имя in имена:
            путь = дерево / (имя.replace(".", "/") + ".py")
            if путь.is_file():
                return путь, f"через обёртку {слово} (PYTHONPATH на рабочую копию)"
    return None, "точка входа из ExecStart не разрешена"


#: Корни кода репозитория: то, что оттуда упомянуто в сценарии оболочки, —
#: его зависимость, даже если имя файла собрано из переменных.
КОРНИ_КОДА = ("automation/", "seo_operator/", "seo_engine/", "factory/",
              "scripts/", "bin/", "tests/tools/")


def зависимости_оболочки(файл: pathlib.Path, дерево: pathlib.Path,
                         собрано: set[pathlib.Path] | None = None) -> set[pathlib.Path]:
    """Что сценарий оболочки зовёт из этого же дерева.

    Нужна потому, что у шести служб точка входа — `.sh` или обёртка `bin/*`, и
    разбор только Python давал «файлов кода: 1». Формально верно, а по сути
    это означало бы перенести обёртку без того, что она зовёт.

    Берутся два вида упоминаний: относительные пути в корни кода и
    `python -m пакет.модуль`. Из найденного Python-файла дальше идёт обычный
    разбор импортов.
    """
    собрано = собрано if собрано is not None else set()
    if файл in собрано or not файл.is_file():
        return собрано
    собрано.add(файл)
    try:
        текст = файл.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return собрано
    for путь in re.findall(r"(?<![\w/])((?:%s)[\w./-]+)" % "|".join(
            re.escape(к) for к in КОРНИ_КОДА), текст):
        цель = дерево / путь
        if цель.is_file():
            if цель.suffix == ".py":
                импорты(цель, дерево, собрано)
            else:
                зависимости_оболочки(цель, дерево, собрано)
    for модуль in re.findall(r"-m\s+([A-Za-z_][\w.]*)", текст):
        путь = дерево / (модуль.replace(".", "/") + ".py")
        пакет = дерево / модуль.replace(".", "/") / "__main__.py"
        for кандидат in (путь, пакет):
            if кандидат.is_file():
                импорты(кандидат, дерево, собрано)
    return собрано


def импорты(файл: pathlib.Path, дерево: pathlib.Path, собрано: set[pathlib.Path] | None = None) -> set[pathlib.Path]:
    """Транзитивные импорты, разрешённые в этом же дереве."""
    собрано = собрано if собрано is not None else set()
    if файл in собрано or not файл.is_file():
        return собрано
    собрано.add(файл)
    try:
        # Нулевые байты в файле бывают (например, частично записанный файл в
        # грязном дереве), и для `ast.parse` это ValueError, а не SyntaxError.
        текст = файл.read_text(encoding="utf-8", errors="replace").replace("\x00", "")
        дерево_ast = ast.parse(текст)
    except (OSError, SyntaxError, ValueError):
        return собрано
    имена: list[str] = []
    for узел in ast.walk(дерево_ast):
        if isinstance(узел, ast.Import):
            имена += [а.name for а in узел.names]
        elif isinstance(узел, ast.ImportFrom) and узел.module and узел.level == 0:
            имена.append(узел.module)
    for имя in имена:
        путь = дерево / (имя.replace(".", "/") + ".py")
        пакет = дерево / имя.replace(".", "/") / "__init__.py"
        for кандидат in (путь, пакет):
            if кандидат.is_file():
                импорты(кандидат, дерево, собрано)
    return собрано


def пути_в_файлах(файлы: set[pathlib.Path], префиксы: tuple[str, ...]) -> list[str]:
    найдено: set[str] = set()
    образец = re.compile(
        r"""["']((?:%s)[\w./@{}-]*)["']""" % "|".join(re.escape(p) for p in префиксы))
    for ф in файлы:
        try:
            текст = ф.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        for м in образец.finditer(текст):
            найдено.add(м.group(1))
    return sorted(найдено)


def незакоммиченные(дерево: pathlib.Path) -> set[str]:
    г = subprocess.run(["git", "-C", str(дерево), "status", "--porcelain"],
                       capture_output=True, text=True)
    итог = set()
    for строка in (г.stdout or "").splitlines():
        if len(строка) > 3:
            итог.add(строка[3:].strip().strip('"'))
    return итог


def состояние_дерева(дерево: pathlib.Path) -> dict:
    def г(*арг):
        return subprocess.run(["git", "-C", str(дерево), *арг],
                              capture_output=True, text=True).stdout.strip()
    грязь = незакоммиченные(дерево)
    return {"ветка": г("rev-parse", "--abbrev-ref", "HEAD"),
            "голова": г("rev-parse", "--short", "HEAD"),
            "незакоммичено_всего": len(грязь)}


def разобрать(запись: dict) -> dict:
    дерево = КОРНИ_КОПИЙ / запись["копии"][0]
    вход, как = точка_входа(запись["юнит"], дерево)
    if вход is None:
        файлы = set()
    elif вход.suffix == ".py":
        файлы = импорты(вход, дерево)
    else:
        файлы = зависимости_оболочки(вход, дерево)
    грязь = незакоммиченные(дерево)
    относительные = sorted(str(ф.relative_to(дерево)) for ф in файлы)
    нужно_грязного = sorted(set(относительные) & грязь)
    запись = dict(запись)
    запись.update({
        "дерево": str(дерево),
        "состояние_дерева": состояние_дерева(дерево),
        "точка_входа": str(вход.relative_to(дерево)) if вход else None,
        "как_определена": как,
        "файлов_кода": len(относительные),
        "код": относительные,
        "конфигурация": пути_в_файлах(файлы, ПУТИ_КОНФИГА),
        "данные": пути_в_файлах(файлы, ПУТИ_ДАННЫХ),
        "нужны_незакоммиченные": нужно_грязного,
    })
    return запись


def главная(аргв: list[str] | None = None) -> int:
    р = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    р.add_argument("--service", action="append", default=[])
    р.add_argument("--json", action="store_true")
    а = р.parse_args(аргв)

    записи = службы_из_копий()
    работают = [з for з in записи if з["включена_сама"] or з["таймеры"]]
    if а.service:
        работают = [з for з in работают if з["служба"] in а.service]
    разобранные = [разобрать(з) for з in работают]

    if а.json:
        print(json.dumps({"служб": len(разобранные), "службы": разобранные},
                         ensure_ascii=False, indent=1))
        return 0

    print(f"юнитов со путём в рабочую копию: {len(записи)}; "
          f"фактически запускаются: {len(работают)}")
    for з in sorted(разобранные, key=lambda x: (x["дерево"], x["служба"])):
        с = з["состояние_дерева"]
        print(f"\n=== {з['служба']} ({з['уровень']})")
        print(f"    дерево: {з['дерево']} | ветка {с['ветка']} {с['голова']} | "
              f"незакоммичено в дереве {с['незакоммичено_всего']}")
        print(f"    запуск: {'сама' if з['включена_сама'] else ''}"
              f"{' + '.join(з['таймеры']) if з['таймеры'] else ''}")
        print(f"    точка входа: {з['точка_входа']} ({з['как_определена']})")
        print(f"    файлов кода в дереве: {з['файлов_кода']}")
        print(f"    конфигурация: {len(з['конфигурация'])} путей "
              f"{з['конфигурация'][:4]}")
        print(f"    данные: {len(з['данные'])} путей {з['данные'][:4]}")
        if з["нужны_незакоммиченные"]:
            print(f"    НУЖНЫ НЕЗАКОММИЧЕННЫЕ ({len(з['нужны_незакоммиченные'])}): "
                  f"{з['нужны_незакоммиченные'][:6]}")
        else:
            print("    незакоммиченных среди нужных файлов нет")
    return 0


if __name__ == "__main__":
    raise SystemExit(главная())
