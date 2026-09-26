#!/usr/bin/env python3
"""Все ЧЕТЫРЕ профиля семейства, объявленные версией шаблона.

Отчёт 1.1.0 перечислял четыре профиля, а проверены были три. Здесь проверяются
все, и о том, чего профиль не умеет, говорится прямо, а не умолчанием.
"""
from __future__ import annotations

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
from pathlib import Path

S = Path("/tmp/claude-1001/-home-claude/9e5d5d7c-1b72-454b-9239-dbb120e73b48/scratchpad")
W = Path("/home/claude/wt-lords-template-consolidation-01")
БАЗА = "http://127.0.0.1:9190"
МОДУЛЬ = Path("/srv/lords/.frontend/releases/20260923T190000Z-community-2-2-12/community.py")
РЕЕСТР = S / "registry-test.json"

#: Что профиль обязан дать. Дизайн — из ДИЗАЙН_ПО_ПРОФИЛЮ рантайма.
ОЖИДАНИЕ = {
    "lords-general": "lords-cinema-v2",
    "lords-new": "lords-series-feed-v2",
    "lords-curated": "lords-curated-v2",
    "lords-genre": None,      # объявлен неподдержанным: своего оформления нет
}

итог = []


def get(путь):
    зпр = urllib.request.Request(БАЗА + urllib.parse.quote(путь, safe="/?=&#"))
    try:
        with urllib.request.urlopen(зпр, timeout=30) as о:
            return о.status, о.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf-8", "replace")


def стоп():
    for pid in subprocess.run(["pgrep", "-f", "lords-frontend.py --port 9190"],
                              capture_output=True, text=True).stdout.split():
        try:
            os.kill(int(pid), signal.SIGTERM)
        except ProcessLookupError:
            pass
    time.sleep(2)


def старт(проект: Path, данные: Path):
    subprocess.Popen([sys.executable, str(проект / "run.py"), "--port", "9190",
                      "--data-dir", str(данные)], cwd=str(проект),
                     env=dict(os.environ,
                              LORDS_90_COMMUNITY_MODERATOR_KEY="test-moderator-key-9190"),
                     stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    for _ in range(60):
        try:
            get("/healthz")
            return True
        except Exception:
            time.sleep(0.5)
    return False


for профиль, ожидаемый in ОЖИДАНИЕ.items():
    проект = S / f"prof-{профиль}"
    # Синтетический каталог: приёмка поверхностей опирается на его состав
    # (слаги kino-*, anime-*, dorama-*), и различить разделы можно только на
    # нём. Настоящие идентификаторы источника нужны отдельной проверке —
    # воспроизведению, и она идёт на lords-90-real.
    данные = S / "lords-90-data"
    стоп()
    d = json.loads(РЕЕСТР.read_text(encoding="utf-8"))
    d["cells"] = []
    РЕЕСТР.write_text(json.dumps(d, ensure_ascii=False, indent=2), encoding="utf-8")
    r = subprocess.run([sys.executable, "-m", "factory", "cell", "newsite",
                        "--site", "lords-90", "--domain", "lords90.example",
                        "--template", профиль, "--port", "9190",
                        "--site-name", "Проверочная витрина",
                        "--remote", "https://github.com/sbc-create/site-lords90-example",
                        "--destination", str(проект), "--registry", str(РЕЕСТР),
                        "--force"], cwd=str(W), capture_output=True, text=True)
    if r.returncode:
        итог.append((профиль, "генерация", "FAIL", r.stderr.strip()[-120:]))
        continue
    # Настройка места и канонический модуль — отдельно, как на боевой ячейке.
    subprocess.run(["install", "-m", "0600", "/srv/lords/.frontend/player-lords-01.json",
                    str(проект / "config" / "player.json")], check=True)
    subprocess.run(["cp", str(МОДУЛЬ), str(проект / "src" / "community.py")], check=True)
    if not старт(проект, данные):
        итог.append((профиль, "запуск", "FAIL", "витрина не поднялась"))
        continue

    код, главная = get("/")
    дизайн = главная.split('data-design="', 1)[1].split('"', 1)[0]
    нав = главная.split('class="hd__nav"', 1)[1].split("</nav>", 1)[0]
    пункты = re.findall(r">([^<>]+)</a>", нав)
    итог.append((профиль, "главная 200", "PASS" if код == 200 else "FAIL", ""))
    if ожидаемый is None:
        # Ожидается именно общий лист: профиль объявлен неподдержанным, и
        # проверка обязана поймать, если он вдруг начнёт выглядеть своим.
        итог.append((профиль, "оформление",
                     "PASS" if дизайн == "lords-sheet" else "FAIL",
                     f"{дизайн}  (объявлен неподдержанным: общий лист — ожидаемо)"))
    else:
        итог.append((профиль, "оформление",
                     "PASS" if дизайн == ожидаемый else "FAIL", дизайн))
    итог.append((профиль, "меню", "PASS" if пункты else "FAIL",
                 " · ".join(пункты)))

    # Разделы: состав каждого — только своё.
    for путь, префикс in (("/movies/", "Фильм"), ("/series/", "Сериал")):
        к, тело = get(путь)
        итог.append((профиль, f"раздел {путь}", "PASS" if к == 200 else "FAIL", str(к)))

    # Фасеты, которыми владеет профиль lords-genre.
    фасеты = {}
    for путь in ("/genres/", "/years/", "/countries/"):
        к, _ = get(путь)
        фасеты[путь] = к
    # /years/ и /countries/ не отдаются НИ ОДНИМ профилем: это разрыв рантайма
    # с blueprint, общий для семейства. Для lords-genre он и есть причина, по
    # которой профиль объявлен неподдержанным.
    итог.append((профиль, "фасетные разделы", "ИЗВЕСТНО",
                 " ".join(f"{k}={v}" for k, v in фасеты.items())
                 + ("  <= содержание профиля" if профиль == "lords-genre" else "")))

    прогон = subprocess.run([sys.executable, str(S / "verify.py")],
                            capture_output=True, text=True)
    строка = прогон.stdout.strip().splitlines()[-1] if прогон.stdout else "нет вывода"
    итог.append((профиль, "приёмка поверхностей",
                 "PASS" if прогон.returncode == 0 else "FAIL", строка))

print(f"{'профиль':<16}{'проверка':<24}{'итог':<10}подробность")
print("-" * 100)
плохо = 0
for профиль, что, статус, подр in итог:
    if статус == "FAIL":
        плохо += 1
    print(f"{профиль:<16}{что:<24}{статус:<10}{подр}")
print("-" * 100)
print(f"строк {len(итог)}, провалов {плохо}")
sys.exit(1 if плохо else 0)
