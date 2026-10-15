"""То же измерение, но без ложных совпадений.

Первая редакция брала только левый столбец таблицы замен. У части строк замена
удаляет ХВОСТ, а начало остаётся дословно — и такое начало на странице
означает исправный текст, а не остаток. Поэтому куски, встречающиеся и справа,
из поиска убираются: иначе отчёт назвал бы дефектом исправное.
"""
import json
import pathlib
import re
import subprocess
from concurrent.futures import ThreadPoolExecutor

ОБЗОР = pathlib.Path("/home/claude/wt-portable-site-cell-01/docs/seo-operator/"
                     "EDITORIAL_REVIEW_20261015.md")
РЕЕСТР = pathlib.Path("/home/claude/wt-nova-publish-memory-02/config/site-cells.json")


def куски_из(текст: str) -> set:
    итог = set()
    for кусок in re.split(r"[.…]\s*", текст):
        кусок = кусок.strip()
        кусок = re.sub(r"^(about|description|title=\")", "", кусок).strip()
        if len(кусок) >= 30 and "…" not in кусок:
            итог.add(кусок)
    return итог


слева, справа = set(), set()
for с in ОБЗОР.read_text(encoding="utf-8").splitlines():
    if с.startswith("| ") and с.count("|") >= 3 and "Было" not in с:
        части = [ч.strip() for ч in с.strip("|").split("|")]
        if len(части) == 2 and части[0] and части[0] != "---":
            слева |= куски_из(части[0])
            справа |= куски_из(части[1])

# Кусок, который есть и в новом тексте, остатком не является.
искать = {к for к in слева if not any(к in п for п in справа)}
print(f"кусков слева {len(слева)}, из них настоящих остатков для поиска "
      f"{len(искать)} (отброшено {len(слева) - len(искать)} совпадающих с новым текстом)")

д = json.loads(РЕЕСТР.read_text(encoding="utf-8"))
ячейки = д.get("cells") or д
список = ячейки if isinstance(ячейки, list) else list(ячейки.values())
домены = sorted({я["domain"] for я in список if isinstance(я, dict)
                 and я.get("status") in ("live", "not_extracted") and я.get("domain") and "localhost" not in я.get("domain", "")})

СТРАНИЦЫ = ["/", "/catalog/"]


def проверить(домен: str) -> tuple:
    тело = ""
    for путь in СТРАНИЦЫ:
        г = subprocess.run(["curl", "-sSL", "--max-time", "45",
                            f"https://{домен}{путь}"],
                           capture_output=True, text=True, timeout=70)
        тело += г.stdout or ""
    if len(тело) < 500:
        return домен, None, len(тело)
    плоско = (тело.replace("&quot;", '"').replace("&#x27;", "'")
              .replace("&amp;", "&").replace("&nbsp;", " "))
    return домен, sorted(к for к in искать if к in плоско), len(тело)


with ThreadPoolExecutor(8) as ex:
    итоги = list(ex.map(проверить, домены))

чисто, грязно = [], []
for домен, остались, байт in sorted(итоги):
    (грязно if остались else чисто).append((домен, остались))

print(f"\nчисто ({len(чисто)}): {', '.join(д for д, _ in чисто)}")
print(f"\nс остатками ({len(грязно)}):")
for домен, остались in грязно:
    print(f"  {домен}: {len(остались)}")
    for к in остались:
        print(f"    ! {к[:110]}")

pathlib.Path("/tmp/claude-1001/-home-claude-wt-portable-site-cell-01/"
             "c1416a86-4527-43b4-94e6-35e0f08a27d0/scratchpad/"
             "кухня-публично.json").write_text(json.dumps(
                 {"чисто": [д for д, _ in чисто],
                  "с_остатками": {д: о for д, о in грязно}},
                 ensure_ascii=False, indent=1), encoding="utf-8")
