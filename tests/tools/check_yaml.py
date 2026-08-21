"""Статическая проверка YAML репозитория (исключая var/ и node_modules)."""
import pathlib
import sys

import yaml

SKIP = ("node_modules", "var/", ".git/")
bad = []
for path in sorted(list(pathlib.Path(".").rglob("*.yaml")) + list(pathlib.Path(".").rglob("*.yml"))):
    if any(part in str(path) for part in SKIP):
        continue
    try:
        yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        bad.append(f"{path}: {exc}")
for problem in bad:
    print(problem, file=sys.stderr)
sys.exit(1 if bad else 0)
