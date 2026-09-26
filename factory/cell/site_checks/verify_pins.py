"""Файлы совпадают с тем, что закреплено в pins.lock.json.

Без этого закрепление — запись о намерении, а не о факте.
"""
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
pins = json.loads((ROOT / "pins.lock.json").read_text(encoding="utf-8"))
bad = []
pending = []
for name, meta in pins["files"].items():
    p = ROOT / "src" / name
    # Файл без объявленной суммы поставляется ОТДЕЛЬНЫМ выпуском (у него свой
    # владелец), и его отсутствие в проекте — законное состояние, а не
    # расхождение с замком. Но и молчать о нём нельзя: пока он не приехал,
    # соответствующий раздел витрины выключен, и это должно быть видно.
    if not meta.get("sha256"):
        if not p.is_file():
            pending.append(f"{name}: поставляется отдельным выпуском, ещё не доставлен")
        continue
    if not p.is_file():
        bad.append(f"{name}: файла нет")
        continue
    actual = hashlib.sha256(p.read_bytes()).hexdigest()
    if actual != meta["sha256"]:
        bad.append(f"{name}: sha256 {actual[:12]} вместо {meta['sha256'][:12]}")
if pending:
    print("ожидают доставки:", *pending, sep="\n  ")
if bad:
    print("исходники разошлись с замком:", *bad, sep="\n  ", file=sys.stderr)
    sys.exit(1)
