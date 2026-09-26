#!/usr/bin/env python3
"""Обновление каталога и обновление кода на проверочном экземпляре.

Доставляет новый снимок (витрина перечитывает его сама), пересобирает релиз из
дерева ветки и перезапускает витрину на новом каталоге релиза. Данные
сообщества лежат вне каталога релиза и здесь не трогаются — что и проверяется
следующим шагом.

Перезапуск идёт по ПИДУ из файла, а не по `pkill -f`: шаблон командной строки
совпадал с командной строкой самой проверки, и она убивала себя.
"""
import copy, hashlib, json, os, signal, subprocess, sys, time
import urllib.request
from pathlib import Path

V = Path(sys.argv[1]); ДАННЫЕ = V / "data"; САЙТ = os.environ.get("ANIMEDIA_PROBE_SITE", "animedia-verify")
ШАБЛОН = Path("/home/claude/wt-animedia-template-port-02")
БАЗА = os.environ.get("ANIMEDIA_PROBE_BASE", "http://127.0.0.1:9310")
пид_файл = V / "server.pid"

def жив():
    try:
        with urllib.request.urlopen(БАЗА + "/healthz", timeout=10) as о:
            return о.status == 200
    except Exception:
        return False

# --- 1. доставка нового снимка каталога --------------------------------------
подр = json.loads((ДАННЫЕ / f"{САЙТ}-details.json").read_text(encoding="utf-8"))
новый = copy.deepcopy(подр)
поднято = 0
for slug, д in новый.get("details", {}).items():
    сез = [с for с in (д.get("seasons") or []) if isinstance(с, dict)]
    if сез and int(сез[0].get("avail") or 0) > 0 and поднято < 25:
        сез[0]["avail"] = int(сез[0]["avail"]) + 1
        сез[0]["eps"] = max(int(сез[0].get("eps") or 0), int(сез[0]["avail"]))
        поднято += 1
новый["catalog_built_at"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
(ДАННЫЕ / f"{САЙТ}-details.json").write_text(json.dumps(новый), encoding="utf-8")
кат = json.loads((ДАННЫЕ / f"{САЙТ}-catalog.json").read_text(encoding="utf-8"))
прежняя = str(кат.get("revision") or "")
кат["revision"] = hashlib.sha256((прежняя + "+1").encode()).hexdigest()
(ДАННЫЕ / f"{САЙТ}-catalog.json").write_text(json.dumps(кат), encoding="utf-8")
print(f"доставка: поднято {поднято} тайтлов, ревизия {прежняя[:12]} → {кат['revision'][:12]}")
# Ждём по `catalog_revision`: только оно берётся из ЗАГРУЖЕННОГО каталога.
# `details_digest` в `/healthz` считается по файлу на диске в момент запроса и
# совпадает сразу после записи — как признак перечитывания он бесполезен.
перечитала = False
край = time.time() + 90
while time.time() < край:
    time.sleep(2)
    try:
        with urllib.request.urlopen(БАЗА + "/healthz", timeout=10) as о:
            if json.loads(о.read()).get("catalog_revision") == кат["revision"]:
                перечитала = True
                break
    except Exception:
        pass
print("витрина перечитала доставленный снимок:", перечитала)
if not перечитала:
    sys.exit("витрина не перечитала снимок — обновление каталога не состоялось")

# --- 2. пересборка релиза ----------------------------------------------------
# Манифест витрины пересоздаётся ТОЙ ЖЕ сборкой. Пересобрать артефакт и
# оставить прежний манифест — это и есть расхождение, которое ловит
# `identity_match`: витрина исполняет новый выпуск и называет старый.
манифест = os.environ.get("ANIMEDIA_PROBE_MANIFEST") or str(
    ДАННЫЕ / f"template-manifest-{САЙТ}.json")
профиль = os.environ.get("ANIMEDIA_PROBE_PROFILE", "animedia-space")
сб = subprocess.run([sys.executable, str(ШАБЛОН / "automation/host/animedia_release_build.py"),
                     "--out-dir", str(V / "releases"),
                     "--stage", "ANIMEDIA-TEMPLATE-PORT-SPACE-02-VERIFY",
                     "--profile", профиль, "--emit-manifest", манифест],
                    capture_output=True, text=True, cwd=str(ШАБЛОН))
print(сб.stdout.strip() or сб.stderr.strip()[-400:])
if сб.returncode != 0:
    sys.exit(f"сборка релиза не удалась: {сб.returncode}")
релизы = sorted(p for p in (V / "releases").iterdir() if p.is_dir())
новейший = релизы[-1]

# --- 3. перезапуск на новом релизе ------------------------------------------
if пид_файл.is_file():
    try:
        os.kill(int(пид_файл.read_text().strip()), signal.SIGTERM)
    except (OSError, ValueError):
        pass
else:
    # первый перезапуск: ищем по порту, а не по шаблону командной строки
    вывод = subprocess.run(["bash", "-lc",
                            "ss -lptn 'sport = :9310' 2>/dev/null | grep -oE 'pid=[0-9]+'"],
                           capture_output=True, text=True).stdout
    for кусок in set(вывод.split()):
        try:
            os.kill(int(кусок.split("=")[1]), signal.SIGTERM)
        except (OSError, ValueError, IndexError):
            pass
time.sleep(3)
запуск = V / "run.sh"
текст = запуск.read_text(encoding="utf-8")
import re as _re
текст = _re.sub(r'exec python3 "[^"]*/animedia-frontend\.py"',
                f'exec python3 "{новейший}/animedia-frontend.py"', текст)
запуск.write_text(текст, encoding="utf-8")
проц = subprocess.Popen(["bash", str(запуск)],
                        stdout=open(V / "server.log", "ab"),
                        stderr=subprocess.STDOUT, start_new_session=True)
пид_файл.write_text(str(проц.pid), encoding="utf-8")
время = time.time()
while time.time() - время < 60:
    time.sleep(1)
    if жив():
        break
свод = {}
if жив():
    with urllib.request.urlopen(БАЗА + "/healthz", timeout=10) as о:
        свод = json.loads(о.read())
print(f"код обновлён: релиз {новейший.name}, витрина отвечает: {жив()}")
print(f"  release_id={свод.get('release_id')}")
print(f"  identity_match={свод.get('identity_match')} "
      f"runtime_digest_match={свод.get('runtime_digest_match')}")
if not свод.get("identity_match"):
    sys.exit("после пересборки витрина называет не тот выпуск, который исполняет: "
             f"манифест {свод.get('manifest_build_id')}, релиз {свод.get('release_id')}")
sys.exit(0 if жив() else 1)
