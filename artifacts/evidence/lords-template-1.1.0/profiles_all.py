#!/usr/bin/env python3
"""Все профили семейства на свежих экземплярах: свой вид у каждого.

Заменяет прежний profiles4.py. Профилей стало семь, и перечислять их в коде
проверки значит держать четвёртый список рядом с тремя существующими. Здесь
список берётся из journal версий и таблицы оформлений рантайма — тех самых
двух мест, расхождение которых эта проверка и должна ловить.

Проверяется не только «каждый поднялся», но и «никакие два не совпали»: пул
объявлен исключительным, и два домена на неразличимых витринах отменяют смысл
исключительности.
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

ЖУРНАЛ = json.loads((W / "status" / "lords-template-version.json")
                    .read_text(encoding="utf-8"))
_рантайм = (W / "automation" / "host" / "lords-frontend.py").read_text(encoding="utf-8")
_таблица = _рантайм.split("ДИЗАЙН_ПО_ПРОФИЛЮ = {", 1)[1].split("}", 1)[0]
ОФОРМЛЕНИЕ = dict(re.findall(r'"([^"]+)":\s*"([^"]+)"', _таблица))

#: Профиль → ожидаемое оформление. None означает «ожидается общий лист»:
#: профиль объявлен неподдержанным, и проверка обязана поймать, если он вдруг
#: начнёт выглядеть своим — это значило бы, что запрет разошёлся с кодом.
ОЖИДАНИЕ = {п: ОФОРМЛЕНИЕ.get(п) for п in ЖУРНАЛ["profiles"]}
ОЖИДАНИЕ.update({п: None for п in (ЖУРНАЛ.get("profiles_unsupported") or {})})

#: Раздел, которым профиль владеет, — из его же файла. Витрина обязана его
#: отдавать: домен заводят ради этого раздела.
СВОЙ_РАЗДЕЛ = {}
for _ф in sorted((W / "blueprints" / "lords" / "profiles").glob("*.yaml")):
    _т = _ф.read_text(encoding="utf-8")
    _в = re.search(r"^owns:\n((?:  - \w+\n)+)", _т, re.M)
    СВОЙ_РАЗДЕЛ[_ф.stem] = re.findall(r"  - (\w+)", _в.group(1)) if _в else []

РАЗДЕЛ_АДРЕС = {
    "catalog_index": "/catalog/", "movies_index": "/movies/",
    "series_index": "/series/", "animation_index": "/animation/",
    "anime_index": "/anime/", "dorama_index": "/dorama/",
    "collections_index": "/collections/", "new_index": "/new/",
    "schedule": "/schedule/", "genres_index": "/genres/",
    "years_index": "/years/", "countries_index": "/countries/",
}

итог: list[tuple[str, str, str, str]] = []
облик: dict[str, dict[str, str]] = {}


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
                        "--destination", str(проект), "--registry", str(РЕЕСТР)],
                       cwd=str(W), capture_output=True, text=True)
    if r.returncode:
        итог.append((профиль, "генерация", "FAIL", r.stderr.strip()[-120:]))
        continue
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
    лид = ""
    м = re.search(r'class="hd__lead"[^>]*>([^<]+)<', главная)
    if м:
        лид = м.group(1).strip()
    подвал = ""
    м = re.search(r'class="ft__about"[^>]*>(.*?)</', главная, re.S)
    if м:
        подвал = re.sub(r"\s+", " ", м.group(1)).strip()[:90]

    итог.append((профиль, "главная 200", "PASS" if код == 200 else "FAIL", ""))
    if ожидаемый is None:
        итог.append((профиль, "оформление",
                     "PASS" if дизайн == "lords-sheet" else "FAIL",
                     f"{дизайн}  (объявлен неподдержанным: общий лист — ожидаемо)"))
    else:
        итог.append((профиль, "оформление",
                     "PASS" if дизайн == ожидаемый else "FAIL", дизайн))
        облик[профиль] = {"дизайн": дизайн, "меню": " · ".join(пункты),
                          "лид": лид, "подвал": подвал}
    итог.append((профиль, "меню", "PASS" if пункты else "FAIL", " · ".join(пункты)))
    итог.append((профиль, "лид первого экрана", "PASS" if лид else "FAIL", лид))

    for раздел in СВОЙ_РАЗДЕЛ.get(профиль, []):
        адрес = РАЗДЕЛ_АДРЕС.get(раздел)
        if not адрес:
            continue
        к, _ = get(адрес)
        # Владеет — значит обязан отдавать. Для lords-genre это и есть причина,
        # по которой профиль объявлен неподдержанным: свои фасеты он не отдаёт.
        ждём_200 = ожидаемый is not None
        статус = "PASS" if (к == 200) == ждём_200 else "FAIL"
        если = "" if ждём_200 else "  (неподдержан: раздела нет — ожидаемо)"
        итог.append((профиль, f"свой раздел {адрес}", статус, f"{к}{если}"))

    прогон = subprocess.run([sys.executable, str(S / "verify.py")],
                            capture_output=True, text=True)
    строка = прогон.stdout.strip().splitlines()[-1] if прогон.stdout else "нет вывода"
    итог.append((профиль, "приёмка поверхностей",
                 "PASS" if прогон.returncode == 0 else "FAIL", строка))

# --- никакие два поддержанных профиля не совпали ----------------------------
for поле in ("дизайн", "меню", "лид", "подвал"):
    видели: dict[str, str] = {}
    повтор = []
    for профиль, о in sorted(облик.items()):
        зн = о[поле]
        if зн and зн in видели:
            повтор.append(f"{видели[зн]} = {профиль}")
        видели[зн] = профиль
    итог.append(("— все —", f"{поле}: попарно различны",
                 "FAIL" if повтор else "PASS",
                 "; ".join(повтор) if повтор else f"{len(облик)} профилей, совпадений нет"))

print(f"{'профиль':<17}{'проверка':<30}{'итог':<10}подробность")
print("-" * 110)
плохо = 0
for профиль, что, статус, подр in итог:
    if статус == "FAIL":
        плохо += 1
    print(f"{профиль:<17}{что:<30}{статус:<10}{подр}")
print("-" * 110)
print(f"строк {len(итог)}, провалов {плохо}")
sys.exit(1 if плохо else 0)
