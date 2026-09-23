"""Ограниченный исполнитель активации: сайт и коммит, но не путь и не команда.

Зачем он устроен именно так
---------------------------

Активация требует root: учётная запись, каталоги, юнит, переключение службы.
Соблазнительное решение — разрешить владельцу один раз выполнить «любой скрипт
по такому-то пути от root». Оно не работает как граница: кто может писать в этот
путь, тот выполняет код от root, а писать в рабочий каталог может кто угодно из
сессии.

Поэтому исполнитель не принимает ни пути к скрипту, ни пути к артефакту, ни
release-manifest со стороны. Он принимает **идентификатор зарегистрированного
сайта** и **коммит его собственного репозитория**, а всё остальное выводит сам:

1. сайт обязан быть в реестре ячеек и иметь собственный репозиторий;
2. репозиторий обязан быть чистым и содержать названный коммит;
3. артефакт **собирается здесь же** из этого коммита;
4. если известен digest, записанный CI для этого коммита, он обязан совпасть;
5. запускается `deploy/activate.sh` того же репозитория — и только он.

Ключ к пункту 3 — воспроизводимость сборки. Раз один и тот же коммит даёт
побайтово один и тот же артефакт, «проверить артефакт» и «собрать артефакт» —
одно и то же действие, и подсунуть посторонние байты становится нечем: их
неоткуда взять, потому что путь снаружи не принимается вовсе.

Чего исполнитель не делает: не создаёт сайтов, не меняет DNS, TLS и индексацию,
не трогает соседние ячейки и не удаляет пользовательские данные.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from factory.cell import registry
from factory.paths import PATHS

#: Единственный исполняемый файл, который исполнитель готов запустить, и только
#: внутри репозитория сайта. Имя фиксировано намеренно: параметр «какой скрипт
#: запустить» превратил бы исполнителя в оболочку.
СЦЕНАРИЙ = Path("deploy") / "activate.sh"

#: Сборщик релиза — тоже фиксирован и тоже берётся из репозитория сайта.
СБОРЩИК = Path("tools") / "build_release.py"

#: Признак того, что каталог — именно репозиторий, а не просто папка.
ПРИЗНАК_РЕПОЗИТОРИЯ = ".git"

ХЕКС = "0123456789abcdef"


class ExecutorRefused(Exception):
    """Операция отклонена до единой мутации."""


@dataclass
class Решение:
    """Что исполнитель намерен сделать. Пригодно к печати и к журналу."""

    site_id: str
    domain: str
    repo_path: str
    commit: str
    digest: str = ""
    build_id: str = ""
    dry_run: bool = True
    steps: list[str] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        return {"site_id": self.site_id, "domain": self.domain,
                "repo_path": self.repo_path, "commit": self.commit,
                "digest": self.digest, "build_id": self.build_id,
                "dry_run": self.dry_run, "steps": self.steps}


def _проверить_коммит(значение: str) -> str:
    """Коммит — 40 или 12 шестнадцатеричных знаков и ничего больше.

    Проверка формой, а не экранированием: значение уходит в аргумент `git`, и
    единственный надёжный способ не спорить с оболочкой — не пропускать ничего,
    что могло бы ей что-то значить.
    """
    очищенный = (значение or "").strip().lower()
    if len(очищенный) not in (12, 40) or any(с not in ХЕКС for с in очищенный):
        raise ExecutorRefused(
            f"коммит {значение!r} не похож на git-хеш (12 или 40 знаков 0-9a-f)")
    return очищенный


def _окружение_git(repo: Path) -> dict[str, str]:
    """Окружение, в котором git согласится работать с чужим по владельцу репо.

    Активация идёт от root, а репозиторий ячейки принадлежит обычной учётной
    записи. С Git 2.35.2 это «dubious ownership», и обе команды — и `rev-parse`,
    и сборщик релиза — отказали бы на первом же запуске у владельца. Путь берётся
    из реестра и уже проверен на выход за пределы фабрики, поэтому доверие здесь
    не шире, чем у самой операции.
    """
    окружение = dict(os.environ)
    существующих = int(окружение.get("GIT_CONFIG_COUNT", "0") or 0)
    окружение["GIT_CONFIG_COUNT"] = str(существующих + 1)
    окружение[f"GIT_CONFIG_KEY_{существующих}"] = "safe.directory"
    окружение[f"GIT_CONFIG_VALUE_{существующих}"] = str(repo)
    return окружение


def _git(repo: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(["git", "-C", str(repo), *args],
                          capture_output=True, text=True, env=_окружение_git(repo))


def _репозиторий(site_id: str) -> tuple[registry.Cell, Path]:
    try:
        cell = registry.resolve(site_id)
    except registry.RegistryError as exc:
        raise ExecutorRefused(
            f"{site_id}: сайта нет в реестре ячеек — исполнитель работает "
            "только с зарегистрированными сайтами") from exc
    registry.require_own_repo(cell)

    путь = (cell.repo or {}).get("path")
    if not путь:
        raise ExecutorRefused(
            f"{site_id}: в реестре нет локального пути репозитория (repo.path)")
    корень = (PATHS.root / путь).resolve()
    # Путь берётся из реестра, но проверяется всё равно: реестр — файл, и
    # запись вида `../../etc` в нём не должна уводить исполнителя наружу.
    if not str(корень).startswith(str(PATHS.root.resolve())):
        raise ExecutorRefused(f"{site_id}: repo.path уводит за пределы фабрики: {корень}")
    if not (корень / ПРИЗНАК_РЕПОЗИТОРИЯ).is_dir():
        raise ExecutorRefused(f"{site_id}: {корень} не похож на репозиторий сайта")
    for обязательный in (СЦЕНАРИЙ, СБОРЩИК):
        if not (корень / обязательный).is_file():
            raise ExecutorRefused(f"{site_id}: в репозитории нет {обязательный}")
    return cell, корень



def _чистое_дерево(repo: Path) -> None:
    состояние = _git(repo, "status", "--porcelain")
    if состояние.returncode != 0:
        raise ExecutorRefused(f"{repo}: git не отвечает: {состояние.stderr.strip()}")
    if состояние.stdout.strip():
        raise ExecutorRefused(
            f"{repo}: рабочее дерево грязное. Активировать можно только то, что "
            "зафиксировано: иначе в production уедет чужая незакоммиченная правка, "
            "и коммит в отчёте будет описывать не то, что работает")


def _коммит_существует(repo: Path, commit: str) -> str:
    найден = _git(repo, "rev-parse", "--verify", f"{commit}^{{commit}}")
    if найден.returncode != 0:
        raise ExecutorRefused(f"{repo}: коммита {commit} в репозитории нет")
    полный = найден.stdout.strip()
    текущий = _git(repo, "rev-parse", "HEAD").stdout.strip()
    if полный != текущий:
        raise ExecutorRefused(
            f"{repo}: HEAD на {текущий[:12]}, а просят {полный[:12]}. "
            "Исполнитель не переключает ветки и не трогает историю — "
            "приведите репозиторий к нужному коммиту сами")
    return полный


def _собрать(repo: Path, куда: Path) -> tuple[Path, dict[str, Any]]:
    готово = subprocess.run([sys.executable, str(repo / СБОРЩИК), "--output", str(куда)],
                            cwd=str(repo), capture_output=True, text=True,
                            env=_окружение_git(repo))
    if готово.returncode != 0:
        raise ExecutorRefused(
            f"{repo}: сборка релиза не удалась:\n{готово.stderr.strip()[-800:]}")
    манифест = json.loads((куда / "release-manifest.json").read_text(encoding="utf-8"))
    артефакт = куда / манифест["artifact"]
    if not артефакт.is_file():
        raise ExecutorRefused(f"{repo}: сборщик не оставил артефакта {артефакт}")
    return артефакт, манифест


def план(site_id: str, *, commit: str) -> Решение:
    """Проверить всё, ничего не меняя. Возвращает намерение целиком."""
    коммит = _проверить_коммит(commit)
    cell, repo = _репозиторий(site_id)
    _чистое_дерево(repo)
    полный = _коммит_существует(repo, коммит)

    with tempfile.TemporaryDirectory() as tmp:
        артефакт, манифест = _собрать(repo, Path(tmp))
        digest = манифест["digest"]
        build_id = манифест.get("live_build_id") or ""
        размер = артефакт.stat().st_size

    if манифест.get("source_dirty"):
        raise ExecutorRefused(f"{site_id}: сборщик пометил дерево грязным")
    if манифест["site_id"] != cell.site_id:
        raise ExecutorRefused(
            f"артефакт собран для {манифест['site_id']}, а ставится в {cell.site_id}")

    return Решение(
        site_id=cell.site_id, domain=cell.domain, repo_path=str(repo),
        commit=полный, digest=digest, build_id=build_id, dry_run=True,
        steps=[f"собрать релиз из {полный[:12]} ({размер} байт)",
               f"сверить digest {digest}",
               f"запустить {СЦЕНАРИЙ} этого репозитория с --artifact",
               "переключить службу и проверить здоровье"],
    )


def активировать(site_id: str, *, commit: str, dry_run: bool = True,
                 expect_digest: str | None = None) -> dict[str, Any]:
    """Собрать из коммита и запустить сценарий активации того же репозитория.

    `dry_run=True` по умолчанию: команда, которая по умолчанию меняет боевой
    сайт, рано или поздно будет запущена без флага случайно.
    """
    решение = план(site_id, commit=commit)
    if expect_digest and решение.digest != expect_digest:
        raise ExecutorRefused(
            f"ожидали digest {expect_digest}, собрался {решение.digest}. "
            "Расхождение означает, что выкладывается не тот выпуск, который "
            "проверял CI")
    решение.dry_run = dry_run
    if dry_run:
        return {"status": "dry-run", **решение.as_dict()}

    repo = Path(решение.repo_path)
    with tempfile.TemporaryDirectory() as tmp:
        артефакт, _ = _собрать(repo, Path(tmp))
        окружение = _окружение_git(repo)
        # Сценарий сайта сам решает, что делать; исполнитель не передаёт ему ни
        # одной переменной, меняющей поведение, кроме уже имеющихся в среде.
        готово = subprocess.run(["bash", str(repo / СЦЕНАРИЙ), "--artifact", str(артефакт)],
                                cwd=str(repo), env=окружение, text=True,
                                capture_output=True)
    итог = {"status": "activated" if готово.returncode == 0 else "failed",
            "exit_code": готово.returncode,
            "stdout": готово.stdout[-4000:], "stderr": готово.stderr[-4000:],
            **решение.as_dict()}
    if готово.returncode != 0:
        итог["status"] = "failed"
    return итог
