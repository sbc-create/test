#!/usr/bin/env python3
"""Публикация закреплённого релиза оснастки и переключение службы на него.

Зачем
-----

Обновление каталога исполняется не из рабочего checkout, а из неизменяемого
релиза `/srv/site-factory/lords-tooling/releases/<полный SHA>/`: закрепление
появилось после инцидента 6 сентября, когда таймер пересобирал витрину тем, что
лежало в репозитории, и выложенный канареечный шаблон исчезал.

Обратная сторона закрепления — исправление, которое есть в git и которого нет в
production. За одну ночь это случилось дважды: помощник `lords-deployctl`
остался на ревизии `31014bb4` и полтора часа падал на исправленном тремя
коммитами выше `TypeError`, а исправление хранения (`previous` больше не
удаляется) не действовало, потому что служба исполняла файл из релиза
`41031da0`. Ручное копирование эту дыру и создаёт, поэтому публикация
оформлена инструментом.

Что делает
----------

1. проверяет, что ревизия — полный SHA и существует в дереве;
2. раскладывает дерево ревизии в `releases/<SHA>` через `git archive`,
   владелец root, каталог только на чтение для службы;
3. сверяет ключевые файлы релиза с их видом в этой ревизии;
4. переписывает drop-in `pinned-tooling.conf` целиком — и `FACTORY_REPO`, и
   `ExecStart`, потому что закреплённая половина пути хуже, чем ничего:
   выглядит закреплённой, не будучи ею;
5. `daemon-reload` и доказательство, что служба читает новый путь.

Чего не делает: не запускает обновление, не трогает витрины, не переключает
релизы сайтов. Публикация оснастки и выкладка витрины — разные операции.

Отказывается работать, если обновление или канареечный прогон сейчас идут:
подменять исполняемый файл под работающим прогоном значит получить прогон,
собранный наполовину одной версией и наполовину другой.
"""

from __future__ import annotations

import argparse
import hashlib
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

ДЕРЕВО = Path("/home/claude/wt-integration-28")
БАЗА = Path("/srv/site-factory/lords-tooling")
РЕЛИЗЫ = БАЗА / "releases"
ДРОПИН = Path("/etc/systemd/system/lords-content-refresh.service.d/pinned-tooling.conf")
СЛУЖБА = "lords-content-refresh.service"
ХЕКС40 = re.compile(r"^[0-9a-f]{40}$")

#: Файлы, ради которых закрепление вообще существует. Сверяются пофайлово
#: после раскладки: «релиз опубликован» обязано означать «в нём именно этот код».
КЛЮЧЕВЫЕ = (
    "automation/host/lords-content-refresh.sh",
    "automation/host/lords-refresh-guard.py",
    "automation/host/lords-fast-render.py",
    "factory/lords/refresh_release.py",
)

ШАБЛОН_ДРОПИНА = """[Service]
# Оснастка обновления берётся из закреплённого неизменяемого релиза, а не из
# рабочего checkout. Причина — инцидент 6 сентября: обновление каталога
# пересобирало витрину тем, что лежало в /srv/site-factory/repo, и выложенный
# канареечный шаблон исчезал при первом же запуске таймера.
#
# WorkingDirectory намеренно НЕ меняется: относительно него живут кэш каталога
# и var/ — перенос корня состояния означал бы запись в каталог, доступный
# только на чтение, то есть отказ обновления вместо его исправления.
#
# Опубликовано automation/host/lords-tooling-release.py {когда}.
Environment=FACTORY_REPO={корень}
Environment=FACTORY_PYTHON=/srv/site-factory/repo/.venv/bin/python
Environment=LORDS_ARTIFACT_ROOT=/srv/lords/.artifacts
Environment=LORDS_PINNED_TEMPLATE=1
ReadOnlyPaths=/srv/site-factory/lords-tooling

# Сам сценарий тоже берётся из закреплённого релиза. Без этой строки drop-in
# менял только переменные, а исполнялся по-прежнему файл из рабочего checkout:
# закреплённой оказалась бы половина пути, а это хуже, чем ничего — выглядит
# закреплённым, не будучи им.
ExecStart=
ExecStart={корень}/automation/host/lords-content-refresh.sh
"""


def сказать(текст: str) -> None:
    print(f"[оснастка] {текст}", flush=True)


def выполнить(*аргументы: str, таймаут: float = 300.0) -> subprocess.CompletedProcess:
    return subprocess.run(аргументы, capture_output=True, text=True, timeout=таймаут)


def отпечаток(путь: Path) -> str:
    h = hashlib.sha256()
    with путь.open("rb") as ф:
        for кусок in iter(lambda: ф.read(1 << 20), b""):
            h.update(кусок)
    return h.hexdigest()


def занято() -> str | None:
    """Идёт ли сейчас обновление или канареечный прогон."""
    for юнит in (СЛУЖБА,):
        состояние = выполнить("systemctl", "is-active", юнит, таймаут=30).stdout.strip()
        if состояние in ("active", "activating", "reloading", "deactivating"):
            return f"{юнит}={состояние}"
    прогоны = выполнить("systemctl", "list-units", "lords-site-render@*", "--all",
                        "--no-pager", "--plain", "--no-legend", таймаут=60).stdout
    for строка in прогоны.splitlines():
        if "activating" in строка or "running" in строка:
            return строка.split()[0]
    return None


def разложить(ревизия: str) -> Path:
    корень = РЕЛИЗЫ / ревизия
    if корень.is_dir() and (корень / "automation").is_dir():
        сказать(f"релиз {ревизия[:12]} уже разложен — переиспользую")
        return корень
    РЕЛИЗЫ.mkdir(parents=True, exist_ok=True)
    временный = Path(tempfile.mkdtemp(prefix=f".{ревизия[:12]}.", dir=str(РЕЛИЗЫ)))
    # Двоичный поток: text=True здесь испортил бы tar на первом же байте,
    # который не разбирается как UTF-8. Поэтому git пишет прямо в tar, а не
    # через общий помощник `выполнить`.
    архив = subprocess.Popen(
        ["git", "-C", str(ДЕРЕВО), "archive", "--format=tar", ревизия],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    распаковка = subprocess.run(["tar", "-x", "-C", str(временный)],
                                stdin=архив.stdout, capture_output=True, timeout=1800)
    архив.stdout.close()
    ошибка_архива = архив.stderr.read().decode("utf-8", "replace")
    архив.wait(timeout=60)
    if архив.returncode != 0:
        shutil.rmtree(временный, ignore_errors=True)
        raise SystemExit(f"git archive отказал: {ошибка_архива[:300]}")
    if распаковка.returncode != 0:
        shutil.rmtree(временный, ignore_errors=True)
        raise SystemExit(f"распаковка отказала: {распаковка.stderr[:300]!r}")
    os.replace(временный, корень)
    выполнить("chown", "-R", "root:root", str(корень), таймаут=300)
    выполнить("chmod", "-R", "a-w", str(корень), таймаут=300)
    сказать(f"разложен {корень}")
    return корень


def сверить(ревизия: str, корень: Path) -> None:
    for имя in КЛЮЧЕВЫЕ:
        цель = корень / имя
        if not цель.is_file():
            raise SystemExit(f"в релизе нет ключевого файла: {имя}")
        из_git = выполнить("git", "-C", str(ДЕРЕВО), "show", f"{ревизия}:{имя}",
                           таймаут=120)
        if из_git.returncode != 0:
            raise SystemExit(f"не читается {имя} из ревизии {ревизия[:12]}")
        ожидаемый = hashlib.sha256(
            из_git.stdout.encode("utf-8", "surrogateescape")).hexdigest()
        фактический = отпечаток(цель)
        if ожидаемый != фактический:
            raise SystemExit(f"{имя}: отпечаток релиза не совпал с ревизией")
        сказать(f"сверен {имя} ({фактический[:12]}…)")


def переключить(корень: Path) -> None:
    ДРОПИН.parent.mkdir(parents=True, exist_ok=True)
    if ДРОПИН.is_file():
        копия = ДРОПИН.with_suffix(
            f".conf.bak.{time.strftime('%Y%m%dT%H%M%SZ', time.gmtime())}")
        shutil.copy2(ДРОПИН, копия)
        сказать(f"копия прежнего drop-in: {копия}")
    текст = ШАБЛОН_ДРОПИНА.format(
        корень=корень, когда=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()))
    временный = ДРОПИН.with_suffix(".conf.new")
    временный.write_text(текст, encoding="utf-8")
    os.chmod(временный, 0o644)
    os.replace(временный, ДРОПИН)
    выполнить("systemctl", "daemon-reload", таймаут=180)
    сказать("drop-in переписан, конфигурация перечитана")


def доказать(корень: Path) -> int:
    """Доказательство берётся у systemd, а не из файла, который мы записали."""
    ошибки = 0
    исполняемое = выполнить("systemctl", "show", СЛУЖБА, "-p", "ExecStart",
                            таймаут=60).stdout
    if str(корень) not in исполняемое:
        сказать(f"ОТКАЗ: ExecStart службы не указывает на {корень}")
        ошибки += 1
    else:
        сказать(f"ExecStart службы: {корень}/automation/host/lords-content-refresh.sh")
    окружение = выполнить("systemctl", "show", СЛУЖБА, "-p", "Environment",
                          таймаут=60).stdout
    if f"FACTORY_REPO={корень}" not in окружение:
        сказать("ОТКАЗ: FACTORY_REPO службы указывает на другой корень")
        ошибки += 1
    else:
        сказать(f"FACTORY_REPO службы: {корень}")
    return ошибки


def main() -> int:
    р = argparse.ArgumentParser(description=__doc__)
    р.add_argument("--revision", required=True, help="полный сороказначный SHA")
    р.add_argument("--force-busy", action="store_true",
                   help="публиковать даже при работающем обновлении (не надо)")
    args = р.parse_args()

    if not ХЕКС40.match(args.revision):
        raise SystemExit(f"ревизия должна быть полным SHA: {args.revision!r}")
    есть = выполнить("git", "-C", str(ДЕРЕВО), "cat-file", "-e",
                     f"{args.revision}^{{commit}}", таймаут=60)
    if есть.returncode != 0:
        raise SystemExit(f"ревизии {args.revision} нет в дереве")

    кто = занято()
    if кто and not args.force_busy:
        raise SystemExit(
            f"сейчас идёт {кто}: подмена исполняемого файла под работающим "
            "прогоном дала бы прогон из двух версий сразу. Публикация отменена.")

    корень = разложить(args.revision)
    сверить(args.revision, корень)
    переключить(корень)
    ошибки = доказать(корень)
    if ошибки:
        return 1
    сказать(f"TOOLING_RELEASE_ACTIVE={args.revision}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
