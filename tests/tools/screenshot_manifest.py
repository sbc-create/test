#!/usr/bin/env python3
"""Манифест скриншотов приёмки: имя, размер и SHA-256 каждого снимка.

Сами PNG в git не коммитятся — они раздули бы репозиторий. Без манифеста
утверждение «скриншоты сняты» проверить нечем, а файл `screenshots.md` в
artifacts/evidence не пересоздавался ничем и исчезал при каждой пересборке
доказательств.
"""
import hashlib
import json
import sys

sys.path.insert(0, ".")
from factory.paths import PATHS  # noqa: E402

SITE = sys.argv[1] if len(sys.argv) > 1 else "pilot-local"

jobs = list((PATHS.artifacts / "jobs" / SITE).glob("*.json"))
if not jobs:
    print(f"нет результатов заданий для {SITE}", file=sys.stderr)
    raise SystemExit(1)
latest = max(jobs, key=lambda p: json.loads(p.read_text(encoding="utf-8")).get("finished_at", ""))
job_id = json.loads(latest.read_text(encoding="utf-8"))["job_id"]

qa_dir = PATHS.artifacts / "qa" / SITE / job_id
shots = sorted(qa_dir.glob("screenshot-*.png"))
if not shots:
    print(f"скриншотов в {qa_dir} нет", file=sys.stderr)
    raise SystemExit(1)

# Брейкпоинты берутся из имён файлов, а не из константы: если браузерная
# проверка снимет другой набор, манифест это покажет, а не промолчит.
widths = sorted({name.split("-")[2] for name in (p.name for p in shots) if name.count("-") >= 2},
                key=lambda w: int(w) if w.isdigit() else 0)

lines = [
    "# Скриншоты приёмки пилота",
    "",
    "Файлы остаются локально в `artifacts/qa/pilot-local/` (в git не коммитятся, чтобы",
    "не раздувать репозиторий бинарями). Ниже — размер и SHA-256 каждого снимка, чтобы",
    "их можно было сверить с тем, что видел прогон.",
    "",
    f"Снято `tools/browser-audit.js` на брейкпоинтах {', '.join(widths)} px.",
    "",
    f"Задание: `{job_id}`",
    "",
    "| Файл | Байт | SHA-256 (первые 16) |",
    "|---|---:|---|",
]
for shot in shots:
    digest = hashlib.sha256(shot.read_bytes()).hexdigest()[:16]
    lines.append(f"| `{shot.name}` | {shot.stat().st_size} | `{digest}` |")
lines.append("")

out = qa_dir.parent / "screenshots.md"
out.write_text("\n".join(lines), encoding="utf-8")
print(f"манифест скриншотов: {out} ({len(shots)} снимков)")
