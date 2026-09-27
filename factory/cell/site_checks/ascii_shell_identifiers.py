"""Имена переменных и функций в shell — только ASCII.

Bash считает именем лишь [A-Za-z_][A-Za-z0-9_]*. `СУХОЙ=0` для него не
присваивание, а вызов команды; падает только при запуске. `bash -n` пропускает.
"""
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ASSIGN = re.compile(r"^\s*(?:export\s+|local\s+)?([^\s=]*[^\x00-\x7F][^\s=]*)=")
REF = re.compile(r"\$\{?([A-Za-z_]*[^\x00-\x7F][^\s}/:\-]*)")
FUNC = re.compile(r"^\s*(?:function\s+)?([^\s()]*[^\x00-\x7F][^\s()]*)\s*\(\s*\)")

bad = []
for path in sorted(ROOT.rglob("*.sh")):
    if ".git" in path.parts:
        continue
    for n, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        code = line.split("#", 1)[0]
        for rule, what in ((ASSIGN, "присваивание"), (REF, "обращение"), (FUNC, "функция")):
            for name in rule.findall(code):
                bad.append(f"{path.relative_to(ROOT)}:{n}: {what} к не-ASCII имени {name!r}")
if bad:
    print("не-ASCII имена в shell:", *bad, sep="\n  ", file=sys.stderr)
    sys.exit(1)
