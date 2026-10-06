#!/usr/bin/env python3
"""Публичные новости Yummy: список /posts и ответ каждой записи.

yummy_posts.py <домен> <out.json> [обязательный слаг ...]
Читает https://<домен>/posts, собирает ссылки /posts/<слаг>, открывает каждую
и пишет код ответа и длину текста. Обязательные слаги должны быть и в списке,
и отвечать 200. Ничего не пишет на сайт.
"""
import json
import re
import sys
import urllib.error
import urllib.request

домен, out = sys.argv[1], sys.argv[2]
обязательные = sys.argv[3:]


def взять(путь):
    з = urllib.request.Request(f"https://{домен}{путь}", headers={"User-Agent": "site-factory-perf-audit"})
    try:
        with urllib.request.urlopen(з, timeout=60) as о:
            return о.status, о.read().decode("utf-8", "ignore")
    except urllib.error.HTTPError as о:
        return о.code, ""


код, лента = взять("/posts")
слаги = sorted(set(re.findall(r'href="/posts/([a-z0-9\-]+)"', лента)))
записи = {}
for с in слаги:
    к, т = взять(f"/posts/{с}")
    текст = re.sub(r"<[^>]+>", " ", re.sub(r"<script.*?</script>", " ", т, flags=re.S))
    записи[с] = {"код": к, "символов": len(" ".join(текст.split()))}
недостаёт = [с for с in обязательные if с not in записи or записи[с]["код"] != 200]
итог = {"домен": домен, "posts_код": код, "записей": len(слаги), "записи": записи,
        "обязательные": обязательные, "недостаёт": недостаёт}
json.dump(итог, open(out, "w"), ensure_ascii=False, indent=1)
print(f"{домен}: /posts {код}, записей {len(слаги)}, не 200: "
      f"{[с for с, з in записи.items() if з['код'] != 200]}, обязательных нет/не 200: {недостаёт}")
