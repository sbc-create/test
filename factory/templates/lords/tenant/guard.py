#!/usr/bin/env python3
"""Guard арендатора Lords: отказ по умолчанию.

## Принцип

Guard не ищет запрещённое — он пропускает только разрешённое. Неизвестная
ветка, неизвестный путь, неизвестный идентификатор шаблона или неизвестный
каталог вывода означают отказ, а не «вероятно, можно». Список запрещённого в
контракте существует не для решения, а для внятного объяснения отказа: сказать
«путь не разрешён» хуже, чем сказать «это путь чужого контура».

## Что проверяется

repository, ветка, HEAD, worktree, маркер арендатора, владелец блокировки,
изменяемые пути, staged-файлы, идентификаторы шаблонов, импорты и каталоги
вывода, а также отсутствие production-команд в изменяемых файлах.

## Когда запускается

Перед первым изменением, перед каждой сборкой, перед каждым commit, перед
созданием материалов приёмки, после проверки каждой семьи и перед итоговым
отчётом. Guard дешёвый и читающий: запускать его часто ничего не стоит.

Коды возврата: 0 — разрешено, 2 — отказ, 3 — контракт или маркер недоступны.
"""

from __future__ import annotations

import argparse
import json
import pathlib
import re
import subprocess
import sys

РАЗРЕШЕНО, ОТКАЗ, НЕИЗМЕРИМО = 0, 2, 3


class Отказ(Exception):
    """Guard закрылся. Причина всегда названа конкретно."""


def _git(*args: str, cwd: pathlib.Path, сырой: bool = False) -> str:
    """Вывод git. `сырой` сохраняет ведущие пробелы.

    В `status --porcelain` первые два символа — код состояния, и у изменённого
    незастейдженного файла первый из них пробел. Обрезка пробелов всей выдачи
    съедала его у ПЕРВОЙ строки, и путь сдвигался на символ: «factory/…»
    превращалось в «actory/…», а guard объявлял собственный путь чужим.
    """
    р = subprocess.run(["git", *args], cwd=str(cwd), capture_output=True, text=True)
    if р.returncode != 0:
        raise Отказ(f"git {' '.join(args)}: {р.stderr.strip()}")
    return р.stdout if сырой else р.stdout.strip()


def загрузить_контракт(путь: pathlib.Path) -> dict:
    if not путь.is_file():
        raise Отказ(f"контракта арендатора нет: {путь}")
    return json.loads(путь.read_text(encoding="utf-8"))


def проверить(worktree: pathlib.Path, контракт: dict, маркер_путь: pathlib.Path,
              изменения: list[str] | None = None) -> dict:
    разрешено = контракт["allowed"]
    запрещено = контракт["denied"]
    проверки: dict[str, str] = {}

    # --- repository и worktree ---------------------------------------------
    корень = pathlib.Path(_git("rev-parse", "--show-toplevel", cwd=worktree)).resolve()
    допустимые = {pathlib.Path(p).resolve() for p in разрешено["worktrees"]}
    if корень not in допустимые:
        raise Отказ(f"worktree {корень} не входит в разрешённые арендатору")
    проверки["worktree"] = str(корень)

    # --- ветка ---------------------------------------------------------------
    ветка = _git("rev-parse", "--abbrev-ref", "HEAD", cwd=worktree)
    if not ветка.startswith(разрешено["branch_prefix"]):
        чужой = next((p for p in запрещено["foreign_branch_prefixes"] if ветка.startswith(p)), "")
        raise Отказ(
            f"ветка {ветка} вне префикса {разрешено['branch_prefix']}"
            + (f": это ветка чужого контура ({чужой})" if чужой else "")
        )
    if ветка not in разрешено["branches"]:
        raise Отказ(f"ветка {ветка} не перечислена в контракте арендатора")
    проверки["branch"] = ветка

    # --- HEAD ----------------------------------------------------------------
    head = _git("rev-parse", "HEAD", cwd=worktree)
    if not re.fullmatch(r"[0-9a-f]{40}", head):
        raise Отказ(f"HEAD не похож на коммит: {head!r}")
    проверки["head"] = head

    # --- маркер арендатора ----------------------------------------------------
    if not маркер_путь.is_file():
        raise Отказ(f"маркера арендатора нет: {маркер_путь}")
    маркер = json.loads(маркер_путь.read_text(encoding="utf-8"))
    if маркер.get("tenant") != контракт["tenant"]:
        raise Отказ(f"маркер объявляет арендатора {маркер.get('tenant')!r}, контракт — {контракт['tenant']!r}")
    if маркер.get("branch") != ветка:
        raise Отказ(f"маркер объявляет ветку {маркер.get('branch')!r}, фактическая — {ветка!r}")
    if pathlib.Path(маркер.get("worktree", "")).resolve() != корень:
        raise Отказ(f"маркер объявляет worktree {маркер.get('worktree')!r}, фактический — {корень}")
    проверки["tenant_marker"] = "совпадает"

    # --- владелец блокировки --------------------------------------------------
    # В связанном worktree `.git` — файл со ссылкой, а не каталог, и индекс
    # лежит в собственном git-dir этого worktree. Проверка по `корень/.git`
    # не сработала бы никогда: файла index.lock там не может быть в принципе.
    git_dir = pathlib.Path(_git("rev-parse", "--absolute-git-dir", cwd=worktree))
    замок = git_dir / "index.lock"
    if замок.exists():
        raise Отказ(f"чужая блокировка индекса: {замок}")
    проверки["lock"] = f"свободно ({git_dir.name})"

    # --- изменяемые пути ------------------------------------------------------
    if изменения is None:
        сырое = _git("status", "--porcelain=v1", cwd=worktree, сырой=True)
        изменения = [строка[3:].strip() for строка in сырое.splitlines() if строка.strip()]
    допустимые_пути = tuple(разрешено["paths"])
    вне = [п for п in изменения if not п.startswith(допустимые_пути)]
    if вне:
        чужие = [п for п in вне if any(м in п for м in запрещено["foreign_path_markers"])]
        raise Отказ(
            f"изменяются пути вне контракта: {вне[:5]}"
            + (f"; из них пути чужого контура: {чужие[:3]}" if чужие else "")
        )
    проверки["changed_paths"] = f"{len(изменения)} путей, все внутри контракта"

    # --- идентификаторы шаблонов ----------------------------------------------
    образец = re.compile(разрешено["template_id_pattern"])
    найденные = set()
    for путь in изменения:
        м = re.search(r"/(T\d{3})[-/]", "/" + путь)
        if м:
            найденные.add(м.group(1))
    плохие = sorted(i for i in найденные if not образец.fullmatch(i))
    if плохие:
        raise Отказ(f"идентификаторы вне диапазона {разрешено['template_id_range']}: {плохие}")
    проверки["template_ids"] = f"{len(найденные)} в диапазоне" if найденные else "нет"

    # --- импорты и production-команды в изменяемых файлах ----------------------
    самоссылочные = set((разрешено.get("self_referential_files") or {}).get("files", []))
    чужие_импорты, команды = [], []
    for путь in изменения:
        if путь in самоссылочные:
            continue
        файл = корень / путь
        if not файл.is_file() or файл.suffix not in (".py", ".sh", ".json", ".css", ".md"):
            continue
        try:
            текст = файл.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        низ = текст.lower()
        for чужой in запрещено["foreign_tenants"]:
            if чужой in низ:
                чужие_импорты.append(f"{путь}: {чужой}")
        for прод in запрещено["production_paths"]:
            if прод in текст:
                команды.append(f"{путь}: путь production {прод}")
        for кмд in запрещено["production_commands"]:
            if re.search(rf"(?<![\w-]){re.escape(кмд)}(?![\w-])", текст):
                команды.append(f"{путь}: команда {кмд}")
    if чужие_импорты:
        raise Отказ(f"обращение к чужому контуру в изменяемых файлах: {чужие_импорты[:4]}")
    if команды:
        raise Отказ(f"production-команды или пути в изменяемых файлах: {команды[:4]}")
    проверки["imports"] = f"чужих нет (самоссылочных файлов пропущено: {len(самоссылочные)})"
    проверки["production_commands"] = "нет"

    # --- каталоги вывода -------------------------------------------------------
    выводы = tuple(разрешено["output_dirs"])
    подозрительные = [п for п in изменения
                      if п.startswith(("artifacts/", "var/")) and not п.startswith(выводы)]
    if подозрительные:
        raise Отказ(f"вывод вне разрешённых каталогов: {подозрительные[:5]}")
    проверки["output_dirs"] = "внутри контракта"

    return проверки


def главное() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--worktree", default=".")
    parser.add_argument("--contract",
                        default="factory/templates/lords/tenant/lords-tenant.json")
    parser.add_argument("--marker", default=".lords-tenant")
    parser.add_argument("--stage", default="ad-hoc", help="на каком шаге запущен")
    parser.add_argument("--record")
    args = parser.parse_args()

    worktree = pathlib.Path(args.worktree).resolve()
    try:
        контракт = загрузить_контракт(worktree / args.contract)
        проверки = проверить(worktree, контракт, worktree / args.marker)
    except Отказ as ошибка:
        print(json.dumps({"stage": args.stage, "GUARD": "DENY", "reason": str(ошибка)},
                         ensure_ascii=False, indent=2))
        print(f"GUARD DENY [{args.stage}]: {ошибка}", file=sys.stderr)
        return ОТКАЗ
    except (OSError, ValueError) as ошибка:
        print(json.dumps({"stage": args.stage, "GUARD": "UNMEASURABLE", "reason": str(ошибка)},
                         ensure_ascii=False, indent=2))
        return НЕИЗМЕРИМО

    отчёт = {"stage": args.stage, "GUARD": "ALLOW", "tenant": контракт["tenant"],
             "role": контракт["role"], "checks": проверки}
    if args.record:
        pathlib.Path(args.record).parent.mkdir(parents=True, exist_ok=True)
        pathlib.Path(args.record).write_text(
            json.dumps(отчёт, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(отчёт, ensure_ascii=False, indent=2))
    return РАЗРЕШЕНО


if __name__ == "__main__":
    raise SystemExit(главное())
