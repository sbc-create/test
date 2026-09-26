#!/usr/bin/env python3
"""Приёмка всех профилей Lords на новом экземпляре: по одному, до конца."""
import json
import os
import signal
import subprocess
import sys
import time
import urllib.request

S = "/tmp/claude-1001/-home-claude/9e5d5d7c-1b72-454b-9239-dbb120e73b48/scratchpad"
W = "/home/claude/wt-lords-template-consolidation-01"
N, D = f"{S}/new-lords-90", f"{S}/lords-90-data"
MOD = "/srv/lords/.frontend/releases/20260923T190000Z-community-2-2-12/community.py"
ОЖИДАЕМЫЙ_ДИЗАЙН = {"lords-general": "lords-cinema-v2",
                    "lords-new": "lords-series-feed-v2",
                    "lords-curated": "lords-curated-v2"}

def стоп():
    for pid in subprocess.run(["pgrep", "-f", "lords-frontend.py --port 9190"],
                              capture_output=True, text=True).stdout.split():
        try: os.kill(int(pid), signal.SIGTERM)
        except ProcessLookupError: pass
    time.sleep(2)

def старт():
    subprocess.Popen([sys.executable, f"{N}/run.py", "--port", "9190", "--data-dir", D],
                     cwd=N, env=dict(os.environ,
                         LORDS_90_COMMUNITY_MODERATOR_KEY="test-moderator-key-9190"),
                     stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    for _ in range(60):
        try:
            urllib.request.urlopen("http://127.0.0.1:9190/healthz", timeout=5); return True
        except Exception: time.sleep(0.5)
    return False

плохо = []
for профиль, дизайн in ОЖИДАЕМЫЙ_ДИЗАЙН.items():
    print(f"\n##### профиль {профиль} #####", flush=True)
    стоп()
    r = subprocess.run([sys.executable, "-m", "factory", "cell", "newsite",
                        "--site", "lords-90", "--domain", "lords90.example",
                        "--template", профиль, "--port", "9190",
                        "--site-name", "Проверочная витрина",
                        "--destination", N, "--force"],
                       cwd=W, capture_output=True, text=True)
    if r.returncode:
        плохо.append(f"{профиль}: генерация не прошла — {r.stderr.strip()[-200:]}")
        continue
    open(f"{N}/config/player.json", "w").write(
        '{"publisher_id":"10555","source_mode":"provider-id"}\n')
    subprocess.run(["cp", MOD, f"{N}/src/community.py"], check=True)
    if not старт():
        плохо.append(f"{профиль}: экземпляр не поднялся")
        continue
    страница = urllib.request.urlopen("http://127.0.0.1:9190/", timeout=30).read().decode()
    манифест = json.load(open(f"{N}/config/template-manifest.json"))
    факт = страница.split('data-design="', 1)[1].split('"', 1)[0]
    print(f"  профиль в манифесте: {манифест['profile']}")
    print(f"  data-design:         {факт} (ожидался {дизайн})")
    if манифест["profile"] != профиль:
        плохо.append(f"{профиль}: в манифесте {манифест['profile']}")
    if факт != дизайн:
        плохо.append(f"{профиль}: дизайн {факт}, ожидался {дизайн}")
    нав = страница.split('class="hd__nav"', 1)[1].split("</nav>", 1)[0]
    пункты = [т for т in __import__("re").findall(r'>([^<>]+)</a>', нав)]
    print(f"  меню: {' · '.join(пункты)}")
    r = subprocess.run([sys.executable, f"{S}/verify.py"], capture_output=True, text=True)
    print("  " + r.stdout.strip().splitlines()[-1])
    if r.returncode:
        плохо.append(f"{профиль}: приёмка поверхностей провалена")

print("\n" + "=" * 60)
print("ПРОВАЛЫ:" if плохо else "все профили прошли")
for п in плохо: print("  " + п)
sys.exit(1 if плохо else 0)
