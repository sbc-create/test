#!/usr/bin/env python3
"""Какая подсистема какие области состояния трогает.

`factory.paths` — единственное место, где области названы, и потому
единственное место, по которому можно посчитать владение. Атрибут `PATHS.x`,
употреблённый двумя подсистемами, означает общую область: разделить их, не
назначив владельца этой области, нельзя.
"""
from __future__ import annotations

import ast
import collections
import pathlib
import re
import sys

КОРЕНЬ = pathlib.Path(sys.argv[1] if len(sys.argv) > 1 else "/home/claude/wt-prod-25")

области = sorted(set(re.findall(r"def ([a-z_]+)\(self\)", (КОРЕНЬ / "factory" / "paths.py")
                                .read_text(encoding="utf-8"))))
print(f"областей объявлено: {len(области)} — {', '.join(области)}\n")


def подсистема(путь: pathlib.Path) -> str:
    части = путь.relative_to(КОРЕНЬ).parts
    return ".".join(части[:2]) if len(части) > 2 else части[0]


кто_где: dict[str, set[str]] = collections.defaultdict(set)
for пакет in ("factory", "seo_engine"):
    корень = КОРЕНЬ / пакет
    if not корень.is_dir():
        continue
    for путь in корень.rglob("*.py"):
        if "__pycache__" in путь.parts or путь.name == "paths.py":
            continue
        try:
            дерево = ast.parse(путь.read_text(encoding="utf-8"))
        except (OSError, SyntaxError, UnicodeDecodeError):
            continue
        кто = подсистема(путь)
        for узел in ast.walk(дерево):
            if (isinstance(узел, ast.Attribute)
                    and isinstance(узел.value, ast.Name)
                    and узел.value.id in ("PATHS", "paths")
                    and узел.attr in области):
                кто_где[узел.attr].add(кто)

print(f"{'область':14} {'подсистем':>9}  кто")
одиночные, общие = 0, 0
for область in области:
    кто = sorted(кто_где.get(область, ()))
    if not кто:
        continue
    if len(кто) == 1:
        одиночные += 1
    else:
        общие += 1
    метка = "ОБЩАЯ" if len(кто) > 1 else "одна"
    print(f"{область:14} {len(кто):9}  {метка:6} {', '.join(кто)}")

print(f"\nобластей с одним потребителем: {одиночные}; общих: {общие}")
