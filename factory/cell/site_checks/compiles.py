"""Весь перенесённый рантайм компилируется.

Артефакт снят с работающего сайта, но это не освобождает от проверки: файл мог
не доехать целиком.
"""
import py_compile
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
bad = []
# cfile во временный файл: py_compile отказывается писать в /dev/null, а без
# cfile он засорил бы проект каталогами __pycache__.
with tempfile.TemporaryDirectory() as tmp:
    for i, p in enumerate(sorted((ROOT / "src").glob("*.py"))):
        try:
            py_compile.compile(str(p), doraise=True, cfile=f"{tmp}/{i}.pyc")
        except py_compile.PyCompileError as exc:
            bad.append(f"{p.name}: {exc}")
if bad:
    print("не компилируется:", *bad, sep="\n  ", file=sys.stderr)
    sys.exit(1)
