"""Ни данных, ни секретов среди файлов, которые Git действительно хранит.

Проверяется индекс, а не рабочий каталог: `config/player.json` обязан лежать
рядом с работающим сайтом и обязан отсутствовать в Git. Отдельно сверяется, что
git отвечает про ЭТОТ проект, иначе распакованное дерево опросило бы
объемлющий репозиторий и прошло проверку, ничего не проверив.
"""
import fnmatch
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
FORBIDDEN = ("*.sqlite3", "*.db", "*.dump", "*.sql", ".env", "*.pem", "*.key",
             "player.json", "*-catalog.json", "*-details.json", "*community*.json")

top = subprocess.run(["git", "rev-parse", "--show-toplevel"], capture_output=True,
                     text=True, check=False, cwd=ROOT)
if top.returncode != 0 or Path(top.stdout.strip()).resolve() != ROOT:
    print("git отвечает не про этот проект: проверка прошла бы впустую",
          file=sys.stderr)
    sys.exit(1)

tracked = subprocess.run(["git", "ls-files"], capture_output=True, text=True,
                         check=False, cwd=ROOT).stdout.split()
bad = [p for p in tracked
       if not p.endswith(".example")
       and any(fnmatch.fnmatch(p.rsplit("/", 1)[-1], pat) for pat in FORBIDDEN)]
if bad:
    print("эти файлы не должны быть в Git:", ", ".join(sorted(bad)), file=sys.stderr)
    sys.exit(1)
