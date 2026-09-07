"""Ответ на HANDOFF-043 §6, вопрос второй: отдаёт ли поставщик число голосов.

Спрашивается сама спецификация поставщика, а не наши записи: отсутствие поля
во всех 53 257 записях доказывает, что его не присылают, но не то, что его
нельзя запросить. Спецификация отвечает на второе.
"""
from __future__ import annotations

import json
import re
import sys
import urllib.error
import urllib.request
from pathlib import Path

СПЕКА = "https://public-api.cdnvideohub.com/api/v1/docs/doc.json"
СЕКРЕТ = Path("/etc/site-factory/secrets/lords/lords-01/cdnvideohub-api-token")

req = urllib.request.Request(СПЕКА, method="GET")
req.add_header("Authorization", f"Bearer {СЕКРЕТ.read_text(encoding='utf-8').strip()}")
req.add_header("Accept", "application/json")
try:
    with urllib.request.urlopen(req, timeout=30) as ответ:
        спека = json.loads(ответ.read().decode("utf-8"))
except urllib.error.HTTPError as ошибка:
    print(f"источник ответил {ошибка.code}: спецификация не прочитана")
    sys.exit(1)
except (urllib.error.URLError, ValueError, OSError) as ошибка:
    print(f"спецификация не получена: {type(ошибка).__name__}")
    sys.exit(1)

текст = json.dumps(спека, ensure_ascii=False)
print("размер спецификации:", len(текст), "байт")

# Ищем любое упоминание счёта голосов под всеми правдоподобными именами.
имена = ("votes", "vote_count", "votes_count", "rating_count", "ratings_count",
         "num_votes", "voters", "reviews_count")
найдено = {и: len(re.findall(rf'"{и}"', текст)) for и in имена}
print("упоминания в спецификации:", {k: v for k, v in найдено.items() if v})

# Какие вообще поля со словом rating объявлены.
рейтинговые = sorted(set(re.findall(r'"([a-z_]*rating[a-z_]*)"', текст)))
print("поля со словом rating:", рейтинговые)
