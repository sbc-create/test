#!/usr/bin/env python3
"""Сверяет, что выкладываемые файлы не изменились с момента сборки артефакта.

Поверх артефакта ложатся коммиты с оснасткой и evidence. Они не входят в
артефакт, но HEAD от его source_head расходится, и заявление «выложено то,
что в HEAD» перестаёт быть очевидным. Сверка по digest'у трёх файлов
превращает это из обещания в проверку.

Запуск: python3 scripts/reconciliation/check_code_tree.py <ожидаемый_digest>
"""

from __future__ import annotations

import hashlib
import subprocess
import sys

ФАЙЛЫ = (
    "automation/host/lords-frontend.py",
    "automation/host/genre_aliases.py",
    "automation/host/collection_contract.py",
)


def main() -> int:
    ожидаемый = sys.argv[1] if len(sys.argv) > 1 else None
    куски = []
    for путь in ФАЙЛЫ:
        данные = subprocess.check_output(["git", "show", f"HEAD:{путь}"])
        куски.append(hashlib.sha256(данные).hexdigest())
    текущий = hashlib.sha256("\n".join(куски).encode()).hexdigest()
    print("CODE_TREE_DIGEST_AT_HEAD =", текущий)
    if ожидаемый:
        print("CODE_TREE_DIGEST_IN_ARTIFACT =", ожидаемый)
        совпало = текущий == ожидаемый
        print("MATCH =", "YES" if совпало else "NO")
        return 0 if совпало else 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
