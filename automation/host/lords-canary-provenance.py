#!/usr/bin/env python3
"""Происхождение и целостность оснастки canary — без git в привилегированном пути.

## Зачем файл существует

Привилегированная операция шла от root, а рабочее дерево принадлежит `claude`.
Git на это отвечает `detected dubious ownership` и отказывается работать —
запуск падал до единой проверки. Объявить каталог доверенным можно, но это
лечит симптом: git в той операции нужен был только ради двух вещей —
идентификатора коммита для журнала и признака «дерево не правили после
коммита».

Обе достижимы без git и без доверия к чужому каталогу:

* **целостность артефакта** уже обеспечена отпечатком девятнадцати файлов,
  который считает `factory.templates.digest` по содержимому и который зашит в
  сам сценарий;
* **целостность оснастки** — тем же способом: отпечаток файлов, которые root
  собирается исполнить.

## Два режима

    --write   собрать манифест (запускается под учётной записью разработчика,
              где git доступен; коммит записывается для журнала)
    --verify  сверить манифест с содержимым файлов (запускается привилегированно,
              git не нужен)

Расхождение в режиме `--verify` — отказ. Файл, который root исполняет, обязан
совпадать с тем, что было проверено и зафиксировано.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MANIFEST = ROOT / "automation" / "host" / "lords-canary-provenance.json"

#: Файлы, которые исполняет привилегированная операция. Изменение любого из них
#: меняет то, что делает root, и потому обязано ломать сверку.
TOOLING = (
    "automation/host/lords-canary-apply.sh",
    "automation/host/lords-canary-install-and-run.sh",
    "automation/host/systemd/lords-canary-render@.service",
    "automation/host/systemd/lords-canary-switch@.service",
    "automation/host/lords-canary-build.py",
    "automation/host/lords-canary-gates.py",
    "automation/host/lords-canary-snapshot.py",
    "automation/host/emit-runtime.py",
    "factory/lords/canary.py",
    "factory/lords/live_site.py",
)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def collect() -> dict:
    tooling = {}
    for name in TOOLING:
        path = ROOT / name
        if not path.is_file():
            raise SystemExit(f"нет файла оснастки: {name}")
        tooling[name] = sha256(path)
    sys.path.insert(0, str(ROOT))
    from factory.templates import digest as digest_mod

    fingerprint = digest_mod.compute()
    head = subprocess.run(["git", "-C", str(ROOT), "rev-parse", "HEAD"],
                          capture_output=True, text=True).stdout.strip()
    # Собственный файл из проверки исключается: манифест пишется до своего же
    # коммита и потому всегда выглядел бы грязью. Прежде это давало
    # `tree_clean_at_write: false` и отказ сверки на ровном месте — манифест
    # обвинял в недостоверности сам факт своей записи.
    changed = subprocess.run(["git", "-C", str(ROOT), "status", "--porcelain",
                              "--untracked-files=no"], capture_output=True, text=True).stdout
    own = MANIFEST.relative_to(ROOT).as_posix()
    dirty = "\n".join(
        line for line in changed.splitlines()
        if line.strip() and not line.split(maxsplit=1)[-1].strip() == own
    ).strip()
    return {
        "head_sha": head or None,
        "tree_clean_at_write": dirty == "",
        "template_digest": fingerprint["template_digest"],
        "template_digest_files": fingerprint["files"],
        "tooling": tooling,
        "note": (
            "манифест собран под учётной записью разработчика; привилегированная "
            "операция сверяет его без git"
        ),
    }


def verify() -> int:
    if not MANIFEST.is_file():
        print(f"нет манифеста происхождения {MANIFEST}", file=sys.stderr)
        return 2
    saved = json.loads(MANIFEST.read_text(encoding="utf-8"))

    sys.path.insert(0, str(ROOT))
    from factory.templates import digest as digest_mod

    fingerprint = digest_mod.compute()
    problems: list[str] = []
    if fingerprint["template_digest"] != saved.get("template_digest"):
        problems.append(
            f"отпечаток шаблона {fingerprint['template_digest'][:16]} не совпал с "
            f"записанным {str(saved.get('template_digest'))[:16]}")
    for name, expected in (saved.get("tooling") or {}).items():
        path = ROOT / name
        if not path.is_file():
            problems.append(f"пропал файл оснастки {name}")
        elif sha256(path) != expected:
            problems.append(f"изменён файл оснастки {name}")
    if not saved.get("tree_clean_at_write", False):
        problems.append("манифест собран на грязном дереве: происхождение недостоверно")

    for problem in problems:
        print(f"ОТКАЗ: {problem}", file=sys.stderr)
    if problems:
        return 1
    print(saved.get("head_sha") or "")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--write", action="store_true", help="собрать манифест")
    group.add_argument("--verify", action="store_true",
                       help="сверить манифест с содержимым; печатает commit при совпадении")
    args = parser.parse_args()
    if args.write:
        data = collect()
        MANIFEST.write_text(json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
                            encoding="utf-8")
        print(f"манифест записан: {MANIFEST}")
        print(f"  commit {data['head_sha']}, дерево чисто: {data['tree_clean_at_write']}")
        print(f"  отпечаток шаблона {data['template_digest'][:16]}, файлов оснастки {len(data['tooling'])}")
        return 0
    return verify()


if __name__ == "__main__":
    raise SystemExit(main())
