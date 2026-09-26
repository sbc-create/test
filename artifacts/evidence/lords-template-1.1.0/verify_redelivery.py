#!/usr/bin/env python3
"""Повторная доставка каталога: сохранность записей и честность «новинок»."""
import json
import os
import re
import signal
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

S = "/tmp/claude-1001/-home-claude/9e5d5d7c-1b72-454b-9239-dbb120e73b48/scratchpad"
БАЗА = "http://127.0.0.1:9190"
ДАННЫЕ = f"{S}/lords-90-data"
ПРОЕКТ = f"{S}/new-lords-90"
итог, провалы = [], []

def проверка(имя, условие, подр=""):
    итог.append((имя, "PASS" if условие else "FAIL", подр))
    if not условие: провалы.append(имя)

class НеСледовать(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *a, **k): return None

def get(путь, куки=""):
    зпр = urllib.request.Request(БАЗА + urllib.parse.quote(путь, safe="/?=&#"),
                                 headers={"Cookie": куки} if куки else {})
    with urllib.request.urlopen(зпр, timeout=30) as r:
        return r.read().decode("utf-8", "replace")

ПОЛКА = re.compile(r'<section class="sec-rail"(?![^>]*data-collections)(.*?)</section>', re.S)
def слаги(h): return re.findall(r'href="/title/([a-z0-9-]+)/"', h)
def на_полках(h): return {s for п in ПОЛКА.findall(h) for s in слаги(п)}

# --- 0. состояние сообщества ДО доставки ------------------------------------
хранилище = f"{ДАННЫЕ}/lords-90-community.json"
было = json.loads(open(хранилище, encoding="utf-8").read())
проверка("в хранилище есть записи до доставки", bool(было.get("subjects") or было),
         str(list(было)[:3]))
слепок_до = json.dumps(было, ensure_ascii=False, sort_keys=True)

# --- 1. доставка нового поколения -------------------------------------------
НОВЫЕ = [
  # Подходящий: фильм, свежая дата — обязан дойти до полки главной.
  {"slug": "kino-novyj-900", "title": "Совсем новый фильм", "kind": "Фильм",
   "type": "movie", "genres": ["боевик"], "published_at": "2026-09-26T09:00:00Z",
   "rating": 8.9},
  # Неподходящий: аниме — на полки главной попасть не должен, но раздел свой
  # обязан его показать.
  {"slug": "anime-novyj-901", "title": "Совсем новое аниме", "kind": "Сериал",
   "type": "tv", "genres": ["аниме", "сенен"], "published_at": "2026-09-26T09:30:00Z",
   "rating": 9.1, "seasons": [{"n": 1, "eps": 12, "avail": 12}]},
]
subprocess.run([sys.executable, f"{S}/seed.py", ДАННЫЕ, "rev-2",
                json.dumps(НОВЫЕ, ensure_ascii=False)], check=True,
               capture_output=True)

# Перезапуск: у этой ячейки в реестре объявлен режим `restart` — витрина
# перечитывает снимок при старте, а не по mtime. Это заявленное поведение, а
# не обход проверки.
подпроцесс = subprocess.run(["pgrep", "-f", "lords-frontend.py --port 9190"],
                            capture_output=True, text=True)
for pid in подпроцесс.stdout.split():
    os.kill(int(pid), signal.SIGTERM)
time.sleep(2)
среда = dict(os.environ, LORDS_90_COMMUNITY_MODERATOR_KEY="test-moderator-key-9190")
сервер = subprocess.Popen([sys.executable, f"{ПРОЕКТ}/run.py", "--port", "9190",
                           "--data-dir", ДАННЫЕ], cwd=ПРОЕКТ, env=среда,
                          stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
for _ in range(40):
    try:
        get("/healthz"); break
    except Exception:
        time.sleep(0.5)

# --- 2. сохранность пользовательских записей --------------------------------
стало = json.loads(open(хранилище, encoding="utf-8").read())
проверка("хранилище сообщества не тронуто доставкой",
         json.dumps(стало, ensure_ascii=False, sort_keys=True) == слепок_до)
стр = get("/title/kino-000/")
проверка("средняя оценка пережила доставку", 'data-community-score="8,0"' in стр,
         re.search(r'data-community-score="[^"]*"', стр).group(0) if 'data-community-score' in стр else "нет")
проверка("комментарий пережил доставку", "Первое сообщение проверки" in стр)

# --- 3. новый подходящий тайтл доходит до нужного блока ---------------------
главная = get("/")
проверка("новый фильм на полке главной", "kino-novyj-900" in на_полках(главная))
фильмы = get("/movies/")
проверка("новый фильм в разделе фильмов", "kino-novyj-900" in слаги(фильмы))
новое = get("/new/")
проверка("новый фильм в «Новом»", "kino-novyj-900" in слаги(новое))
код = get("/collection/recently_added/")
проверка("новый фильм в подборке новизны", "kino-novyj-900" in слаги(код))

# --- 4. неподходящий не попадает --------------------------------------------
проверка("новое аниме НЕ на полках главной", "anime-novyj-901" not in на_полках(главная))
проверка("новое аниме НЕ в разделе фильмов", "anime-novyj-901" not in слаги(фильмы))
аниме = get("/anime/")
проверка("новое аниме в своём разделе", "anime-novyj-901" in слаги(аниме))
проверка("раздел аниме не содержит фильмов",
         not [s for s in слаги(аниме) if s.startswith("kino-")])

# --- 5. повторная доставка не создаёт ложного поступления -------------------
порядок_до = [s for s in слаги(get("/new/"))][:10]
subprocess.run([sys.executable, f"{S}/seed.py", ДАННЫЕ, "rev-3",
                json.dumps(НОВЫЕ, ensure_ascii=False)], check=True, capture_output=True)
for pid in subprocess.run(["pgrep", "-f", "lords-frontend.py --port 9190"],
                          capture_output=True, text=True).stdout.split():
    os.kill(int(pid), signal.SIGTERM)
time.sleep(2)
сервер = subprocess.Popen([sys.executable, f"{ПРОЕКТ}/run.py", "--port", "9190",
                           "--data-dir", ДАННЫЕ], cwd=ПРОЕКТ, env=среда,
                          stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
for _ in range(40):
    try:
        get("/healthz"); break
    except Exception:
        time.sleep(0.5)
порядок_после = [s for s in слаги(get("/new/"))][:10]
проверка("повторная доставка не переставила «Новое»", порядок_до == порядок_после,
         f"{порядок_до[:3]} → {порядок_после[:3]}")

# --- 6. новая озвучка не выдаётся за поступление -----------------------------
С_ОЗВУЧКОЙ = list(НОВЫЕ)
С_ОЗВУЧКОЙ[1] = dict(НОВЫЕ[1], seasons=[{"n": 1, "eps": 24, "avail": 24}])
subprocess.run([sys.executable, f"{S}/seed.py", ДАННЫЕ, "rev-4",
                json.dumps(С_ОЗВУЧКОЙ, ensure_ascii=False)], check=True, capture_output=True)
for pid in subprocess.run(["pgrep", "-f", "lords-frontend.py --port 9190"],
                          capture_output=True, text=True).stdout.split():
    os.kill(int(pid), signal.SIGTERM)
time.sleep(2)
сервер = subprocess.Popen([sys.executable, f"{ПРОЕКТ}/run.py", "--port", "9190",
                           "--data-dir", ДАННЫЕ], cwd=ПРОЕКТ, env=среда,
                          stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
for _ in range(40):
    try:
        get("/healthz"); break
    except Exception:
        time.sleep(0.5)
порядок_озвучка = [s for s in слаги(get("/new/"))][:10]
проверка("новая озвучка не создала поступления", порядок_до == порядок_озвучка,
         f"{порядок_до[:3]} → {порядок_озвучка[:3]}")
проверка("голоса целы после трёх доставок",
         'data-community-score="8,0"' in get("/title/kino-000/"))

print(f"{'проверка':<46} итог")
print("-" * 62)
for имя, статус, подр in итог:
    print(f"{имя:<46} {статус}" + (f"  {подр}" if статус == "FAIL" and подр else ""))
print("-" * 62)
print(f"всего {len(итог)}, провалов {len(провалы)}")
sys.exit(1 if провалы else 0)
