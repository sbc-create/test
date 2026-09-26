#!/usr/bin/env python3
"""Совпадает ли установленное с источником. Без root, одной командой.

    python3 automation/host/check-installed.py

Зачем. Установка 26.09 в 13:30 «выполнилась», но ни один из ожидаемых
результатов не появился, и выяснение заняло полчаса сравнений дат и
содержимого. Причина оказалась простой и не в установщике: он копировал
источник, в котором нужных правок ЕЩЁ НЕ БЫЛО — я дописывал их в 13:33, 13:35,
13:47 и 13:54, то есть после запуска. `cell-install.json` этого не показывал:
там только корень источника и время.

Проверка отвечает на вопрос «что из установленного отстало от источника»
перечислением файлов, а не общим «расходится». Тогда просьба повторить
установку либо имеет конкретное основание, либо отпадает.
"""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

# Три уровня, а не два: файл лежит в automation/host/. Повтор №2 за сессию
# для этой же ошибки — первый раз в unblock-transfer.sh, там тоже вышел
# путь automation/automation/host. Проверка: корень обязан содержать
# factory/cell/executor.py, иначе скрипт молча сверяет ноль файлов.
КОРЕНЬ = Path(__file__).resolve().parent.parent.parent
if not (КОРЕНЬ / "factory" / "cell" / "executor.py").is_file():
    raise SystemExit(f"не похоже на репозиторий фабрики: {КОРЕНЬ}")
УСТАНОВЛЕНО = Path("/usr/local/lib/site-factory-cell")
ЧАСТИ = ("factory", "schemas", "config")


def цифра(п: Path) -> str:
    return hashlib.sha256(п.read_bytes()).hexdigest()


def main() -> int:
    if not УСТАНОВЛЕНО.is_dir():
        print(f"установленной копии нет: {УСТАНОВЛЕНО}")
        return 2
    маркер = УСТАНОВЛЕНО / "cell-install.json"
    if маркер.is_file():
        try:
            св = json.loads(маркер.read_text(encoding="utf-8"))
            print(f"установлено {св.get('installed_at')} из {св.get('site_repos_root')}")
        except (OSError, ValueError):
            print("cell-install.json не читается")

    отстали: list[str] = []
    нет_в_установленной: list[str] = []
    сверено = 0
    for часть in ЧАСТИ:
        источник = КОРЕНЬ / часть
        if not источник.is_dir():
            continue
        for п in sorted(источник.rglob("*.py")) + sorted(источник.rglob("*.json")):
            if "__pycache__" in п.parts:
                continue
            отн = п.relative_to(КОРЕНЬ)
            там = УСТАНОВЛЕНО / отн
            if not там.is_file():
                нет_в_установленной.append(str(отн))
                continue
            сверено += 1
            try:
                if цифра(там) != цифра(п):
                    отстали.append(str(отн))
            except OSError as ош:
                отстали.append(f"{отн} (не читается: {ош.strerror})")

    print(f"сверено файлов: {сверено}")
    if нет_в_установленной:
        print(f"нет в установленной копии ({len(нет_в_установленной)}):")
        for и in нет_в_установленной[:12]:
            print("   ", и)
    if отстали:
        print(f"РАСХОДЯТСЯ с источником ({len(отстали)}):")
        for и in отстали[:20]:
            print("   ", и)
        print("\nЭто и есть основание повторить установку: перечислены файлы, "
              "которые в установленной копии старее источника.")
        return 1
    if нет_в_установленной:
        return 1
    print("установленное совпадает с источником по всем сверенным файлам")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
