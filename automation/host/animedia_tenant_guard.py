#!/usr/bin/env python3
"""Preflight guard контура ANIMEDIA: fail closed.

Читает `config/animedia/TENANT_SCOPE.yaml` и отвечает на один вопрос: можно ли
выполнить заявленное действие, не выйдя за границы контура. Неизвестное —
запрещено: неизвестная ветка, каталог, служба, домен, профиль или template ID
дают отказ, а не разрешение по умолчанию.

Зачем это нужно отдельной программой, а не внимательностью: шесть витрин трёх
контуров живут в одном репозитории и под одним корнем рантайма, чьё имя
принадлежит соседу. Ошибка на один символ в пути манифеста или в имени службы
меняет чужой проект, и заметно это становится только после перезапуска.

Запускать:

    python3 automation/host/animedia_tenant_guard.py --stage before-write \\
        --paths automation/host/animedia-frontend.py
    python3 automation/host/animedia_tenant_guard.py --stage before-assignment \\
        --domain animedia.icu --profile animedia-icu \\
        --service nova-animedia-01.service --template-id animedia-original-parity

Код возврата 0 — разрешено, 1 — отказ (причины печатаются и возвращаются в
JSON при `--json`).
"""
from __future__ import annotations

import argparse
import fnmatch
import json
import os
import re
import subprocess
import sys
from pathlib import Path

СТАДИИ = ("before-first-change", "before-write", "before-build", "before-commit",
          "before-artifact", "before-manifest", "before-assignment", "before-report")


class Отказ(Exception):
    """Guard отказал. Текст — причина, пригодная для отчёта."""


def _контракт(корень: Path) -> dict:
    путь = корень / "config" / "animedia" / "TENANT_SCOPE.yaml"
    if not путь.is_file():
        raise Отказ(f"контракт изоляции не найден: {путь}")
    текст = путь.read_text(encoding="utf-8")
    try:
        import yaml  # type: ignore
        данные = yaml.safe_load(текст)
    except ImportError:  # pragma: no cover — в окружении фабрики yaml есть
        данные = _разобрать_упрощённо(текст)
    if not isinstance(данные, dict) or данные.get("tenant") != "animedia":
        raise Отказ("контракт изоляции не объявляет tenant: animedia")
    if данные.get("mode") != "fail_closed":
        raise Отказ("контракт изоляции обязан работать в режиме fail_closed")
    return данные


def _разобрать_упрощённо(текст: str) -> dict:
    """Запасной разбор подмножества YAML — вложенные словари и списки строк.

    Нужен только чтобы guard не выключался из-за отсутствия библиотеки: guard,
    который молча пропускает всё, когда не смог прочитать контракт, хуже
    отсутствующего.
    """
    корень: dict = {}
    стек: list[tuple[int, object]] = [(-1, корень)]
    for строка in текст.splitlines():
        if not строка.strip() or строка.lstrip().startswith("#"):
            continue
        отступ = len(строка) - len(строка.lstrip())
        тело = строка.strip()
        while стек and стек[-1][0] >= отступ:
            стек.pop()
        родитель = стек[-1][1]
        if тело.startswith("- "):
            значение = тело[2:].strip().strip('"')
            if isinstance(родитель, list):
                родитель.append(значение)
            continue
        ключ, _, значение = тело.partition(":")
        ключ = ключ.strip()
        значение = значение.strip().strip('"')
        if значение == "":
            новый: object = {}
            # Определяем тип по следующей значимой строке.
            остаток = текст.split(строка, 1)[1].splitlines()
            for след in остаток:
                if not след.strip() or след.lstrip().startswith("#"):
                    continue
                новый = [] if след.lstrip().startswith("- ") else {}
                break
            if isinstance(родитель, dict):
                родитель[ключ] = новый
            стек.append((отступ, новый))
        elif isinstance(родитель, dict):
            if значение in ("true", "false"):
                родитель[ключ] = значение == "true"
            else:
                родитель[ключ] = значение
    return корень


def _г(*args: str, cwd: Path) -> str:
    return subprocess.run(list(args), cwd=str(cwd), capture_output=True,
                          text=True).stdout.strip()


def _совпадает(путь: str, шаблоны) -> bool:
    return any(fnmatch.fnmatch(путь, ш) or fnmatch.fnmatch(путь, ш.rstrip("*") + "*")
               for ш in (шаблоны or []))


def наблюдать(корень: Path) -> dict:
    """Факты окружения, которые guard проверяет: где мы и на какой ветке.

    Выделено отдельно, чтобы отрицательные пробы могли подать заведомо чужое
    окружение, не создавая ради этого репозиторий другого контура. Боевой путь
    всегда читает git.
    """
    гд = Path(_г("git", "rev-parse", "--git-dir", cwd=корень) or ".")
    if not гд.is_absolute():
        гд = (корень / гд).resolve()
    return {"toplevel": _г("git", "rev-parse", "--show-toplevel", cwd=корень),
            "branch": _г("git", "rev-parse", "--abbrev-ref", "HEAD", cwd=корень),
            "head": _г("git", "rev-parse", "HEAD", cwd=корень),
            "git_dir": str(гд),
            "status_porcelain": _г("git", "status", "--porcelain",
                                   cwd=корень).splitlines()}


def проверить(корень: Path, стадия: str, пути=(), домен=None, профиль=None,
              служба=None, template_id=None, импорты=(), команда=None,
              вывод=None, цели_выката=(), наблюдения=None) -> dict:
    """Единая проверка. Возвращает отчёт; при отказе поднимает `Отказ`."""
    к = _контракт(корень)
    причины: list[str] = []
    факты: dict = {"stage": стадия, "tenant": "animedia"}

    if стадия not in СТАДИИ:
        raise Отказ(f"неизвестная стадия guard: {стадия}")

    н = наблюдения if наблюдения is not None else наблюдать(корень)

    # --- репозиторий и worktree ---
    верх = н["toplevel"]
    факты["toplevel"] = верх
    разрешённые = [str(Path(p)) for p in (к["worktrees"]["allowed"] or [])]
    if верх not in разрешённые:
        причины.append(f"worktree вне контура: {верх}")

    # --- ветка ---
    ветка = н["branch"]
    факты["branch"] = ветка
    префикс = к["branch"]["allowed_prefix"]
    if not ветка.startswith(префикс):
        причины.append(f"ветка вне контура: {ветка} (нужен префикс {префикс})")
    известные = к["branch"].get("known") or []
    if известные and ветка not in известные:
        причины.append(f"ветка не объявлена в контракте: {ветка}")

    # --- HEAD ---
    head = н["head"]
    факты["head"] = head
    if not re.fullmatch(r"[0-9a-f]{40}", head or ""):
        причины.append("HEAD не определён")

    # --- владелец блокировки worktree ---
    блок = Path(н["git_dir"]) / "locked"
    факты["worktree_locked"] = блок.is_file()
    if блок.is_file():
        владелец = блок.read_text(encoding="utf-8", errors="replace").strip()
        факты["lock_owner"] = владелец
        причины.append(f"worktree заблокирован другим владельцем: {владелец}")

    # --- изменяемые пути ---
    запрещённые_префиксы = к["denylist"]["foreign_tenant_prefixes"] or []
    исключения = к["denylist"].get("exceptions_read_only") or []
    разрешено_писать = к["source_paths"]["allowed_write"] or []
    только_чтение = к["source_paths"].get("allowed_read_only") or []
    проверяемые = list(пути)
    if стадия in ("before-commit", "before-artifact", "before-report"):
        проверяемые += [s.split(None, 1)[-1] for s in н["status_porcelain"]]
    факты["paths_checked"] = sorted(set(проверяемые))
    for сырой in факты["paths_checked"]:
        путь = сырой.strip().replace("\\", "/")
        if путь.startswith("/"):
            # абсолютный путь — правила рантайма
            рп = к["runtime_paths"]
            ок = (путь in (рп["allowed_write"] or [])
                  or _совпадает(путь, рп.get("allowed_write_globs")))
            если_чтение = путь in (рп.get("allowed_read_only") or [])
            if not ок and not если_чтение:
                причины.append(f"путь рантайма вне контура: {путь}")
            continue
        if путь in только_чтение or путь in исключения:
            # Общее ядро можно читать при аудите — но не подавать guard'у как
            # цель действия. Правка, коммит, сборка и артефакт из него равно
            # запрещены: артефакт Animedia, собранный из чужого entrypoint,
            # именно так и появился бы.
            причины.append(
                f"общее ядро доступно только для чтения и не может быть целью "
                f"действия «{стадия}»: {путь}")
            continue
        if not _совпадает(путь, разрешено_писать):
            причины.append(f"путь вне разрешённых контуру: {путь}")
        имя = Path(путь).name.lower()
        for пр in запрещённые_префиксы:
            if имя.startswith(пр) and путь not in исключения:
                причины.append(f"файл чужого контура в наборе изменений: {путь}")

    # --- импорты ---
    факты["imports_checked"] = list(импорты)
    for модуль in импорты:
        низ = модуль.lower()
        for пр in запрещённые_префиксы:
            if низ.startswith(пр) or f".{пр}" in низ:
                причины.append(f"cross-tenant import запрещён: {модуль}")

    # --- адресаты ---
    if домен is not None:
        факты["domain"] = домен
        if домен not in (к["domains"]["allowed"] or []):
            причины.append(f"домен вне контура: {домен}")
    if профиль is not None:
        факты["profile"] = профиль
        if профиль not in (к["profiles"]["allowed"] or []):
            причины.append(f"профиль вне контура: {профиль}")
    if служба is not None:
        факты["service"] = служба
        if служба not in (к["services"]["allowed"] or []):
            причины.append(f"служба вне контура: {служба}")
    if template_id is not None:
        факты["template_id"] = template_id
        if template_id not in (к["template_ids"]["allowed"] or []):
            причины.append(f"template ID вне контура: {template_id}")
    if вывод is not None:
        факты["output_dir"] = вывод
        разр = (к["output_paths"]["allowed"] or []) + [к["output_paths"]["scratch_root"]]
        if not _совпадает(вывод, разр):
            причины.append(f"каталог вывода вне контура: {вывод}")

    # --- запрещённые команды ---
    if команда is not None:
        факты["command"] = команда
        низ = команда.lower()
        if "systemctl" in низ and not к["services"].get("session_may_run_systemctl"):
            причины.append("systemctl из сессии запрещён контрактом")
        for опасное, поле in (("git reset --hard", "reset_hard"),
                              ("git branch -f", "force_branch_move"),
                              ("push --force", "force_push"),
                              ("git clean", "history_rewrite")):
            if опасное in низ and к["denylist"]["forbidden"].get(поле, True):
                причины.append(f"запрещённая операция: {опасное}")
        for сеть in ("dig +update", "certbot", "nsupdate", "robots.txt",
                     "x-robots-tag", "noindex"):
            if сеть in низ:
                причины.append(f"операция DNS/TLS/индексации запрещена: {сеть}")
        # Массовый выкат: одна команда, задевающая больше одной витрины.
        упомянуто = [с for с in (к["services"]["allowed"] or []) if с in команда]
        if len(упомянуто) > 1:
            причины.append(f"массовый выкат запрещён: в одной команде {len(упомянуто)} служб")

    # --- поэтапность выката ---
    факты["deploy_targets"] = list(цели_выката)
    if len(set(цели_выката)) > 1:
        причины.append(
            "массовый выкат запрещён: витрины переключаются по одной, "
            f"заявлено сразу {len(set(цели_выката))}")

    # --- производственные ворота ---
    if стадия == "before-assignment":
        ворота = к["gates"]["owner_visual_acceptance"]
        if ворота.get("previous") == "REJECTED":
            факты["owner_visual_acceptance_previous"] = "REJECTED"
    факты["reasons"] = причины
    факты["allowed"] = not причины
    if причины:
        raise Отказ("; ".join(причины))
    return факты


def main() -> int:
    р = argparse.ArgumentParser(description=__doc__)
    р.add_argument("--stage", required=True, choices=СТАДИИ)
    р.add_argument("--root", default=None)
    р.add_argument("--paths", nargs="*", default=())
    р.add_argument("--imports", nargs="*", default=())
    р.add_argument("--domain"); р.add_argument("--profile")
    р.add_argument("--service"); р.add_argument("--template-id")
    р.add_argument("--command"); р.add_argument("--output-dir")
    р.add_argument("--deploy-targets", nargs="*", default=())
    р.add_argument("--json", action="store_true")
    a = р.parse_args()
    корень = Path(a.root or _г("git", "rev-parse", "--show-toplevel", cwd=Path.cwd()))
    try:
        факты = проверить(корень, a.stage, a.paths, a.domain, a.profile, a.service,
                          a.template_id, a.imports, a.command, a.output_dir,
                          a.deploy_targets)
    except Отказ as e:
        отчёт = {"allowed": False, "stage": a.stage, "tenant": "animedia",
                 "reason": str(e)}
        print(json.dumps(отчёт, ensure_ascii=False, indent=1) if a.json
              else f"GUARD=DENY\n  причина: {e}")
        return 1
    print(json.dumps(факты, ensure_ascii=False, indent=1) if a.json
          else f"GUARD=ALLOW стадия {a.stage} ветка {факты['branch']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
