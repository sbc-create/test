#!/usr/bin/env python3
"""Зафиксировать установочный пакет: коммит, состав, контрольные суммы.

    python3 automation/host/freeze-package.py                 # зафиксировать HEAD
    python3 automation/host/freeze-package.py --check <пакет>  # сверить пакет с описью
    python3 automation/host/freeze-package.py --latest         # путь последнего пакета

Зачем это появилось
-------------------

26.09 установка в 13:30 «выполнилась», но ни один ожидаемый результат не
появился. Причина не в установщике: он читал РАБОЧИЙ КАТАЛОГ, а я дописывал
обязательные части пакета в 13:33, 13:35, 13:47 и 13:54 — то есть после запуска.
Каждый шаг честно скопировал то, что видел; видел он недоделанное.

Вывод не «быть внимательнее», а «у установщика не должно быть доступа к
меняющемуся источнику». Поэтому:

  * пакет собирается из КОММИТА через `git archive`, а не из рабочего дерева;
  * фиксация ОТКАЗЫВАЕТ, если в путях пакета есть незакоммиченные изменения:
    дописать обязательную часть «на ходу» больше нельзя, её сначала придётся
    закоммитить и получить НОВЫЙ идентификатор пакета;
  * опись содержит sha256 каждого файла и общий digest; установщик сверяет
    digest до начала и после конца работы и падает, если состав менялся;
  * дерево пакета переводится в режим только для чтения.

Идентификатор пакета выводится из содержимого, поэтому одинаковый состав даёт
одинаковый идентификатор, а любое изменение — другой.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tarfile
from datetime import datetime, timezone
from pathlib import Path

# Файл лежит в automation/host/ — до корня три уровня. Повтор этой ошибки
# в сессии уже случался дважды, поэтому корень проверяется явно.
КОРЕНЬ = Path(__file__).resolve().parent.parent.parent
if not (КОРЕНЬ / "factory" / "cell" / "executor.py").is_file():
    raise SystemExit(f"не похоже на репозиторий фабрики: {КОРЕНЬ}")

# Состав пакета. Ровно то, что читают установщики хоста, и ничего больше:
# factory/schemas/config копируются в корневую копию, automation/host — сами
# сценарии установки.
ПУТИ = ("factory", "schemas", "config", "automation/host")
ХРАНИЛИЩЕ = КОРЕНЬ / "var" / "install-packages"


def git(*арг: str, cwd: Path | None = None) -> str:
    # core.quotePath=false обязателен: иначе git отдаёт пути с не-ASCII именами
    # в восьмеричных escape-последовательностях, и сверка состава молча ищет
    # файл, которого «нет». Нашлось тестом на файле с русским именем.
    гот = subprocess.run(("git", "-c", "core.quotePath=false") + арг,
                         cwd=str(cwd or КОРЕНЬ), capture_output=True, text=True)
    if гот.returncode != 0:
        raise SystemExit(f"git {' '.join(арг)}: {гот.stderr.strip()}")
    return гот.stdout


def имена(вывод: str) -> list[str]:
    """Разбор вывода с -z: пути могут содержать пробелы, split() их разорвёт."""
    return [и for и in вывод.split("\0") if и]


def цифра_файла(п: Path) -> str:
    х = hashlib.sha256()
    with п.open("rb") as ф:
        for кусок in iter(lambda: ф.read(1 << 20), b""):
            х.update(кусок)
    return х.hexdigest()


def опись_дерева(дерево: Path) -> dict[str, str]:
    итог: dict[str, str] = {}
    for п in sorted(дерево.rglob("*")):
        if п.is_dir() or п.is_symlink():
            continue
        if "__pycache__" in п.parts:
            continue
        итог[str(п.relative_to(дерево))] = цифра_файла(п)
    return итог


def общий_digest(коммит: str, файлы: dict[str, str]) -> str:
    канон = json.dumps({"commit": коммит, "files": файлы},
                       ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(канон.encode("utf-8")).hexdigest()


def незакоммиченное(коммит: str) -> list[str]:
    """Что в путях пакета расходится с коммитом. Пусто — можно фиксировать."""
    расхождения: list[str] = []
    изм = имена(git("diff", "--name-only", "-z", коммит, "--", *ПУТИ))
    расхождения += [f"изменён: {и}" for и in изм]
    новые = имена(git("ls-files", "--others", "--exclude-standard", "-z", "--", *ПУТИ))
    расхождения += [f"не в git: {и}" for и in новые
                    if "__pycache__" not in и]
    return расхождения


def снять_запись(корень: Path) -> None:
    for путь in [корень] + list(корень.rglob("*")):
        try:
            реж = путь.stat().st_mode & 0o7777
            os.chmod(путь, реж & ~0o222)
        except OSError:
            pass


def вернуть_запись(корень: Path) -> None:
    for путь in [корень] + list(корень.rglob("*")):
        try:
            реж = путь.stat().st_mode & 0o7777
            os.chmod(путь, реж | 0o200)
        except OSError:
            pass


def зафиксировать(ссылка: str, принудительно: bool) -> int:
    коммит = git("rev-parse", ссылка).strip()
    расх = незакоммиченное(коммит)
    if расх and not принудительно:
        print(f"ОТКАЗ: в путях пакета есть изменения вне коммита {коммит[:12]}:")
        for и in расх[:20]:
            print("   ", и)
        print("\nСначала закоммить их. Смысл отказа: пакет, часть которого"
              "\nдописана после фиксации, — это ровно та ошибка 26.09.")
        return 2

    файлы_git = имена(git("ls-tree", "-r", "--name-only", "-z", коммит, "--", *ПУТИ))
    файлы_git = [и for и in файлы_git if "__pycache__" not in и]
    if not файлы_git:
        raise SystemExit("в коммите нет ни одного файла пакета")

    ХРАНИЛИЩЕ.mkdir(parents=True, exist_ok=True)
    черновик = ХРАНИЛИЩЕ / ".черновик"
    if черновик.exists():
        вернуть_запись(черновик)
        shutil.rmtree(черновик)
    дерево = черновик / "tree"
    дерево.mkdir(parents=True)

    архив = черновик / "pkg.tar"
    with архив.open("wb") as ф:
        гот = subprocess.run(("git", "archive", "--format=tar", коммит, "--", *ПУТИ),
                             cwd=str(КОРЕНЬ), stdout=ф, stderr=subprocess.PIPE, text=False)
    if гот.returncode != 0:
        raise SystemExit(f"git archive: {гот.stderr.decode('utf-8', 'replace')}")
    with tarfile.open(архив, "r") as т:
        т.extractall(дерево)
    архив.unlink()

    файлы = опись_дерева(дерево)
    пропали = sorted(set(файлы_git) - set(файлы))
    if пропали:
        raise SystemExit("git archive не выдал файлы коммита: " + ", ".join(пропали[:5]))

    digest = общий_digest(коммит, файлы)
    иден = "pkg-" + digest[:12]
    готовый = ХРАНИЛИЩЕ / иден
    if готовый.exists():
        вернуть_запись(готовый)
        shutil.rmtree(готовый)

    опись = {
        "package_id": иден,
        "digest": digest,
        "commit": коммит,
        "commit_subject": git("log", "-1", "--format=%s", коммит).strip(),
        "branch": git("rev-parse", "--abbrev-ref", "HEAD").strip(),
        "frozen_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "paths": list(ПУТИ),
        # Куда исполнителю смотреть за рабочими копиями репозиториев сайтов.
        # Это НЕ источник кода: код берётся из дерева пакета. Значение
        # объявлено здесь, чтобы установщик не выводил его из своего места.
        "site_repos_root": str(КОРЕНЬ),
        "file_count": len(файлы),
        "files": файлы,
    }
    (черновик / "manifest.json").write_text(
        json.dumps(опись, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8")
    черновик.rename(готовый)
    снять_запись(готовый)

    print(f"пакет зафиксирован: {иден}")
    print(f"  коммит   {коммит[:12]}  {опись['commit_subject'][:60]}")
    print(f"  digest   {digest}")
    print(f"  файлов   {len(файлы)}")
    print(f"  дерево   {готовый / 'tree'}  (только чтение)")
    if расх:
        print("  ВНИМАНИЕ: зафиксировано принудительно при расхождениях")
    return 0


def сверить(пакет: Path) -> int:
    опись_п = пакет / "manifest.json"
    if not опись_п.is_file():
        print(f"это не пакет: нет {опись_п}")
        return 2
    опись = json.loads(опись_п.read_text(encoding="utf-8"))
    факт = опись_дерева(пакет / "tree")
    ожид = опись["files"]
    изменились = sorted(и for и in факт.keys() & ожид.keys() if факт[и] != ожид[и])
    лишние = sorted(факт.keys() - ожид.keys())
    пропали = sorted(ожид.keys() - факт.keys())
    digest = общий_digest(опись["commit"], факт)
    print(f"пакет {опись['package_id']}  коммит {опись['commit'][:12]}  файлов {len(факт)}")
    if digest == опись["digest"] and not (изменились or лишние or пропали):
        print("состав совпадает с описью, digest совпадает")
        return 0
    print(f"СОСТАВ ИЗМЕНИЛСЯ. digest описи {опись['digest'][:16]}, фактический {digest[:16]}")
    for имя, набор in (("изменены", изменились), ("лишние", лишние), ("пропали", пропали)):
        if набор:
            print(f"  {имя} ({len(набор)}):")
            for и in набор[:10]:
                print("     ", и)
    return 1


def последний() -> int:
    кандидаты = [п for п in ХРАНИЛИЩЕ.glob("pkg-*") if (п / "manifest.json").is_file()]
    if not кандидаты:
        print("зафиксированных пакетов нет", file=sys.stderr)
        return 2
    кандидаты.sort(key=lambda п: json.loads((п / "manifest.json").read_text(encoding="utf-8"))["frozen_at"])
    print(кандидаты[-1])
    return 0


def main() -> int:
    р = argparse.ArgumentParser(add_help=True)
    р.add_argument("--commit", default="HEAD")
    р.add_argument("--check", metavar="ПАКЕТ")
    р.add_argument("--latest", action="store_true")
    р.add_argument("--force", action="store_true",
                   help="зафиксировать несмотря на незакоммиченные изменения")
    а = р.parse_args()
    if а.latest:
        return последний()
    if а.check:
        return сверить(Path(а.check).resolve())
    return зафиксировать(а.commit, а.force)


if __name__ == "__main__":
    raise SystemExit(main())
