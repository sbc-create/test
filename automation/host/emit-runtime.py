#!/usr/bin/env python3
"""Записывает рантайм стенда Lords в указанный файл.

Отдельный файл, а не heredoc внутри сценария: рантайм понадобился в двух
местах — при создании нового релиза и при обновлении рантайма на тихом цикле, —
и вложенные кавычки в shell дважды оказались источником ошибок.
"""

import sys
from pathlib import Path

# Сценарий запускается из каталога хоста, а не из корня репозитория, поэтому
# корень добавляется явно: иначе `factory` не находится.
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from factory.lords.bundle import RUNTIME  # noqa: E402

if len(sys.argv) != 2:
    raise SystemExit("использование: emit-runtime.py <путь>")
Path(sys.argv[1]).write_text(RUNTIME, encoding="utf-8")
