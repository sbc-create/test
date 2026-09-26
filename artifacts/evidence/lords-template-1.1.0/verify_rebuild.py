#!/usr/bin/env python3
"""Пользовательские записи переживают ПЕРЕСБОРКУ проекта, а не только доставку.

Пересборка — это `newsite --force`: каталог проекта удаляется и собирается
заново из шаблона. Голоса и комментарии лежат ВНЕ каталога проекта, в каталоге
данных, и пережить это обязаны. Проверяется тем же способом, что и всё
остальное: состоянием, которое отдаёт живая витрина, а не наличием файла.
"""
from __future__ import annotations

import http.cookiejar
import os
import re
import signal
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

S = Path("/tmp/claude-1001/-home-claude/9e5d5d7c-1b72-454b-9239-dbb120e73b48/scratchpad")
W = Path("/home/claude/wt-lords-template-consolidation-01")
N, D = S / "prof-lords-general", S / "lords-90-data"
МОДУЛЬ = Path("/srv/lords/.frontend/releases/20260923T190000Z-community-2-2-12/community.py")
РЕЕСТР = S / "registry-test.json"
БАЗА = "http://127.0.0.1:9190"
КЛЮЧ = "test-moderator-key-9190"

итог, провалы = [], []


def проверка(имя, ок, подр=""):
    итог.append((имя, "PASS" if ок else "FAIL", подр))
    if not ок:
        провалы.append(имя)


class НеСледовать(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *a, **k):
        return None


def стоп():
    for pid in subprocess.run(["pgrep", "-f", "lords-frontend.py --port 9190"],
                              capture_output=True, text=True).stdout.split():
        try:
            os.kill(int(pid), signal.SIGTERM)
        except ProcessLookupError:
            pass
    time.sleep(2)


def старт():
    subprocess.Popen([sys.executable, str(N / "run.py"), "--port", "9190",
                      "--data-dir", str(D)], cwd=str(N),
                     env=dict(os.environ, LORDS_90_COMMUNITY_MODERATOR_KEY=КЛЮЧ),
                     stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    for _ in range(60):
        try:
            urllib.request.urlopen(БАЗА + "/healthz", timeout=5)
            return True
        except Exception:
            time.sleep(0.5)
    return False


jar = http.cookiejar.CookieJar()
клиент = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar), НеСледовать())


def страница(путь="/title/kino-000/"):
    return клиент.open(БАЗА + путь, timeout=30).read().decode("utf-8", "replace")


def отправить(путь, поля):
    данные = urllib.parse.urlencode(поля).encode()
    try:
        клиент.open(urllib.request.Request(
            БАЗА + путь, data=данные,
            headers={"Content-Type": "application/x-www-form-urlencoded"}), timeout=30)
    except urllib.error.HTTPError:
        pass


# --- запись до пересборки ----------------------------------------------------
стоп()
for f in D.glob("*community*"):
    f.unlink()
assert старт(), "витрина не поднялась"

тело = страница()
поля = dict(re.findall(r'name="(subject|slug|back|csrf)" value="([^"]*)"',
                       тело.split('data-community-form="vote"', 1)[1]))
отправить("/community/vote", dict(поля, value="6"))
отправить("/community/comment", dict(поля, name="Пересборка", text="Запись до пересборки"))
до = страница()
проверка("голос поставлен", 'data-my-vote="6"' in до)
проверка("комментарий оставлен", "Запись до пересборки" in до)
хранилище = D / "lords-90-community.json"
проверка("хранилище лежит вне каталога проекта",
         хранилище.is_file() and str(N) not in str(хранилище), str(хранилище))
слепок = хранилище.read_bytes()

# --- пересборка проекта из шаблона -------------------------------------------
стоп()
r = subprocess.run([sys.executable, "-m", "factory", "cell", "newsite",
                    "--site", "lords-90", "--domain", "lords90.example",
                    "--template", "lords-general", "--port", "9190",
                    "--site-name", "Проверочная витрина",
                    "--remote", "https://github.com/sbc-create/site-lords90-example",
                    "--destination", str(N), "--registry", str(РЕЕСТР), "--force"],
                   cwd=str(W), capture_output=True, text=True)
проверка("проект пересобран из шаблона", r.returncode == 0, r.stderr.strip()[-140:])
subprocess.run(["install", "-m", "0600", "/srv/lords/.frontend/player-lords-01.json",
                str(N / "config" / "player.json")], check=True)
subprocess.run(["cp", str(МОДУЛЬ), str(N / "src" / "community.py")], check=True)
assert старт(), "витрина не поднялась после пересборки"

проверка("хранилище пересборкой не тронуто", хранилище.read_bytes() == слепок)
после = страница()
проверка("голос пережил пересборку", 'data-my-vote="6"' in после)
проверка("комментарий пережил пересборку", "Запись до пересборки" in после)
проверка("среднее и число голосов на месте",
         'data-community-votes="1"' in после,
         (re.search(r'data-community-votes="\d+"', после) or ["нет"])[0])

print(f"{'проверка':<44} итог")
print("-" * 62)
for имя, статус, подр in итог:
    print(f"{имя:<44} {статус}" + (f"  {подр}" if статус == "FAIL" and подр else ""))
print("-" * 62)
print(f"всего {len(итог)}, провалов {len(провалы)}")
sys.exit(1 if провалы else 0)
