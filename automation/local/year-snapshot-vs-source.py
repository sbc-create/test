#!/usr/bin/env python3
"""Расхождение года снимка и года источника: сиквелы против прочих работ."""
import glob, json, pathlib, random, re, subprocess, sys
sys.path.insert(0, "/home/claude/wt-nova-publish-memory-02")
from factory.qwen import editorial

ИНСТР = "/home/claude/wt-nova-publish-memory-02/automation/local/source_fetch.py"

черновики = []
for путь in sorted(glob.glob("/srv/sites/*/runtime/overlays/*/drafts.json")):
    дом = pathlib.Path(путь).parent.name
    try:
        д = json.loads(pathlib.Path(путь).read_text(encoding="utf-8"))
    except Exception:
        continue
    записи = д.get("items") if isinstance(д, dict) else д
    пары = записи.items() if isinstance(записи, dict) else [((x or {}).get("slug"), x) for x in (записи or [])]
    for слаг, зап in пары:
        ид = [s for s in (зап.get("sources") or []) if "shikimori.io/animes/" in str(s)]
        if слаг and ид:
            черновики.append((дом, слаг, ид[0].rsplit("/", 1)[-1]))

сиквел = lambda с: bool(re.search(r"-\d$", с))
сиквелы = [т for т in черновики if сиквел(т[1])]
прочие = [т for т in черновики if not сиквел(т[1])]
случ = random.Random(20261025)
выборка = (случ.sample(сиквелы, min(12, len(сиквелы)))
           + случ.sample(прочие, min(12, len(прочие))))
print(f"черновиков с карточкой Shikimori: {len(черновики)}"
      f" (сиквелов {len(сиквелы)}, прочих {len(прочие)})")
print(f"{'вид':8} {'домен':16} {'слаг':34} {'снимок':7} {'источник':9} исход")
итог = {"сиквел": [0, 0], "прочее": [0, 0]}
for дом, слаг, ид in выборка:
    вид = "сиквел" if сиквел(слаг) else "прочее"
    try:
        ф = (editorial.факты(дом, слаг).get("facts") or {})
    except Exception as ош:
        print(f"{вид:8} {дом:16} {слаг[:34]:34} отказ фактов: {type(ош).__name__}")
        continue
    снимок = str(ф.get("year") or "")
    г = subprocess.run([sys.executable, ИНСТР, "shikimori", ид],
                       capture_output=True, text=True, timeout=180)
    ист = ""
    if г.returncode == 0:
        try:
            д = json.loads(г.stdout)
            дата = str(д.get("aired_on") or д.get("released_on") or "")
            ист = дата[:4] if дата[:4].isdigit() else ""
        except ValueError:
            pass
    если = ("НЕ ИЗМЕРЕНО" if not ист or not снимок
            else "расходятся" if снимок != ист else "совпадают")
    if если != "НЕ ИЗМЕРЕНО":
        итог[вид][0] += 1
        итог[вид][1] += 1 if если == "расходятся" else 0
    print(f"{вид:8} {дом:16} {слаг[:34]:34} {снимок:7} {ист:9} {если}")
print()
for вид, (всего, расх) in итог.items():
    доля = f"{расх/всего*100:.0f} %" if всего else "—"
    print(f"{вид}: измерено {всего}, расходятся {расх} ({доля})")
