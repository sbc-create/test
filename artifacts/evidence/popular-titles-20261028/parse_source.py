"""Разбор и контроль полноты списка владельца (28.10): номера 1–392, суммы по категориям.

python3 parse_source.py  → source-owner-20261028.json рядом; код 1 при расхождении с контролем.
"""
import json
import pathlib
import re
import sys

HERE = pathlib.Path(__file__).resolve().parent
SRC = HERE / "source-owner-20261028.txt"
OUT = HERE / "source-owner-20261028.json"
# Контроль полноты из сообщения владельца.
EXPECTED = {"Лорд": (100, 59290771), "Дорама": (99, 50141123),
            "Аниме": (95, 234206414), "Другое": (98, 199321856)}
EXPECTED_TOTAL = 542960164

rows, cat = [], None
for line in SRC.read_text(encoding="utf-8").splitlines():
    m = re.match(r"КАТЕГОРИЯ ИСХОДНИКА «(.+?)»: (\d+) ПОЗИЦИЙ", line)
    if m:
        cat = m.group(1).capitalize()  # в заголовке прописными: «ЛОРД» → «Лорд»
        continue
    m = re.match(r"^(\d+)\. (.+?) \| (\d+) \| (\d+)$", line)
    if m:
        rows.append({"n": int(m.group(1)), "title": m.group(2), "pageviews": int(m.group(3)),
                     "sites": int(m.group(4)), "source_category": cat})

problems = []
nums = [r["n"] for r in rows]
if nums != list(range(1, 393)):
    problems.append(f"номера не 1–392 подряд: {len(nums)} строк")
for c, (cnt, total) in EXPECTED.items():
    got = [r for r in rows if r["source_category"] == c]
    s = sum(r["pageviews"] for r in got)
    if (len(got), s) != (cnt, total):
        problems.append(f"{c}: {len(got)} строк, сумма {s}; ожидалось {cnt}, {total}")
grand = sum(r["pageviews"] for r in rows)
if grand != EXPECTED_TOTAL:
    problems.append(f"общая сумма {grand}, ожидалась {EXPECTED_TOTAL}")
dup = sorted({r["title"] for r in rows if [x["title"] for x in rows].count(r["title"]) > 1})

OUT.write_text(json.dumps({
    "source": "Яндекс Метрика, отчёт «Заголовки страниц», 28.04–28.10.2026; 1000 сайтов × 100 заголовков; сообщение владельца 28.10.2026",
    "caveat": "просмотры страниц (карточки, сезоны, серии) — не зрители, не просмотры видео, не частотность запроса; число сайтов не доказывает низкую конкуренцию",
    "rows": rows, "control": {"problems": problems, "total": grand, "duplicate_titles": dup},
}, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
print(f"строк {len(rows)}, сумма {grand}, повторов названий {len(dup)}")
for p in problems:
    print("РАСХОЖДЕНИЕ:", p)
sys.exit(1 if problems else 0)
