#!/usr/bin/env python3
"""Происхождение: исходный коммит → собранный артефакт → исполняемый код.

Три звена, и каждое проверяется отдельно. Обрыв любого означает, что по цифрам
витрины нельзя сказать, какой код работает, — а решают именно по ним.
"""
import hashlib
import json
import subprocess
import sys
import tarfile
import tempfile
import urllib.request
from pathlib import Path

#: СВОЙ каталог проекта и СВОЙ запущенный экземпляр. Прежде проверка
#: осматривала общий `new-lords-90`, а поля `/healthz` читала с того, кто
#: оказался на порту. Пока все сценарии поднимали один и тот же проект, это
#: сходилось; как только соседний сценарий стал поднимать свой
#: (`refresh-lords-90`), проверка начала сравнивать сумму ОДНОГО рантайма с
#: отпечатком ДРУГОГО и отказывала «исполняемый код — тот же файл» при
#: исправном происхождении. Проверка происхождения обязана мерить то, что сама
#: собрала и запустила.
S = Path("/tmp/claude-1001/-home-claude/9e5d5d7c-1b72-454b-9239-dbb120e73b48/scratchpad")
W = Path("/home/claude/wt-lords-template-consolidation-01")
N = S / "prov-lords-90"
D = S / "lords-90-data"
МОДУЛЬ = Path("/srv/lords/.frontend/releases/20260923T190000Z-community-2-2-12/community.py")
РЕЕСТР = S / "registry-prov.json"
БАЗА = "http://127.0.0.1:9190"
итог, провалы = [], []

#: Поля устройства машины `/healthz` отдаёт только ВНУТРЕННЕМУ вызову:
#: обработчик опознаёт его по заголовку Host, а он опознаётся только на
#: `127.0.0.1:<порт>` — через nginx приходит имя домена или upstream. Публично
#: ответ короткий: {ok, service, revision}.
#:
#: Поэтому адрес здесь — петля, и так и должно остаться. Если поле пропало,
#: проверка обязана сказать ПОЧЕМУ, а не упасть по KeyError: ошибка «нет
#: ключа runtime_sha256» заставляет искать дефект в рантайме, которого нет.
ПОДРОБНОСТЬ_ТОЛЬКО_ИЗНУТРИ = (
    "{поле} в ответе /healthz отсутствует. Подробность отдаётся только "
    "внутреннему вызову — по адресу http://127.0.0.1:<порт>/healthz. "
    "Публичный ответ короткий по построению, и читать поля по домену нельзя: "
    "обработчик опознаёт внутренний вызов по заголовку Host, а через nginx "
    "приходит имя домена. Адрес проверки: {база}")


def подробность(ответ: dict, поле: str, база: str):
    """Поле устройства из /healthz или отказ с названной причиной."""
    if поле not in ответ:
        raise SystemExit(ПОДРОБНОСТЬ_ТОЛЬКО_ИЗНУТРИ.format(поле=поле, база=база))
    return ответ[поле]


def собрать_и_поднять() -> None:
    """Свой проект из шаблона и свой процесс на порту."""
    import os
    import shutil
    import time

    for pid in subprocess.run(["pgrep", "-f", "lords-frontend.py --port 9190"],
                              capture_output=True, text=True).stdout.split():
        try:
            os.kill(int(pid), 15)
        except (ProcessLookupError, ValueError):
            pass
    time.sleep(2)
    shutil.rmtree(N, ignore_errors=True)
    if РЕЕСТР.is_file():
        РЕЕСТР.unlink()
    r = subprocess.run([sys.executable, "-m", "factory", "cell", "newsite",
                        "--site", "lords-90", "--domain", "lords90.example",
                        "--template", "lords-general", "--port", "9190",
                        "--site-name", "Проверка происхождения",
                        "--remote", "https://github.com/sbc-create/site-lords90-example",
                        "--destination", str(N), "--registry", str(РЕЕСТР)],
                       cwd=str(W), capture_output=True, text=True)
    if r.returncode:
        raise SystemExit("newsite не собрал проект: " + r.stderr.strip()[-300:])
    subprocess.run(["install", "-m", "0600",
                    "/srv/lords/.frontend/player-lords-01.json",
                    str(N / "config" / "player.json")], check=True)
    subprocess.run(["cp", str(МОДУЛЬ), str(N / "src" / "community.py")], check=True)
    # Сборщик выпуска берёт состав из ИНДЕКСА Git — без репозитория ему нечего
    # собирать, а происхождение проверяется именно собранным артефактом.
    for аргументы in (["git", "init", "-q"], ["git", "add", "-A"],
                      ["git", "-c", "user.email=t@t", "-c", "user.name=t",
                       "commit", "-q", "-m", "проект проверки происхождения"]):
        subprocess.run(аргументы, cwd=str(N), check=True,
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    subprocess.Popen([sys.executable, str(N / "run.py"), "--port", "9190",
                      "--data-dir", str(D)], cwd=str(N),
                     env=dict(os.environ, LORDS_90_COMMUNITY_MODERATOR_KEY="k"),
                     stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    for _ in range(60):
        try:
            urllib.request.urlopen(БАЗА + "/healthz", timeout=5).read()
            return
        except Exception:
            time.sleep(0.5)
    raise SystemExit("экземпляр проверки происхождения не поднялся")


собрать_и_поднять()


def проверка(имя, ок, подр=""):
    итог.append((имя, "PASS" if ок else "FAIL", подр))
    if not ок: провалы.append(имя)

коммит = subprocess.run(["git", "-C", str(N), "rev-parse", "HEAD"],
                        capture_output=True, text=True, check=True).stdout.strip()

with tempfile.TemporaryDirectory() as вых:
    r = subprocess.run([sys.executable, str(N / "tools" / "build_release.py"),
                        "--output", вых], cwd=str(N), capture_output=True, text=True)
    проверка("артефакт собрался", r.returncode == 0, r.stderr[-200:])
    архив = next(Path(вых).glob("*.tar.gz"))
    манифест_выпуска = json.loads(next(Path(вых).glob("*release-manifest.json")).read_text())

    # звено 1: артефакт назван коммитом и его digest записан
    проверка("манифест выпуска называет коммит",
             манифест_выпуска["source_commit"] == коммит,
             f"{манифест_выпуска['source_commit'][:12]} vs {коммит[:12]}")
    факт = "sha256:" + hashlib.sha256(архив.read_bytes()).hexdigest()
    проверка("digest артефакта совпал с манифестом",
             манифест_выпуска["digest"] == факт, f"{манифест_выпуска['digest'][:20]}…")
    проверка("сборка из чистого дерева", манифест_выпуска["source_dirty"] is False)

    # звено 2: манифест ВНУТРИ артефакта проштампован тем же коммитом
    with tarfile.open(архив, "r:gz") as t:
        внутри = json.loads(t.extractfile("config/template-manifest.json").read())
    проверка("манифест в артефакте: runtime_commit = коммит",
             внутри["runtime_commit"] == коммит, внутри["runtime_commit"][:12])
    проверка("манифест в артефакте: site_repo_commit = коммит",
             внутри["site_repo_commit"] == коммит)
    проверка("build_id выведен из коммита",
             внутри["build_id"].startswith(коммит[:12]), внутри["build_id"])
    проверка("происхождение шаблона отделено от версии сайта",
             внутри["template_origin"]["source_commit"] != коммит
             and внутри["source_commit"] != коммит,
             f"origin={внутри['template_origin']['source_commit'][:12]}")
    проверка("ни одно поле выпуска не смотрит в общую фабрику",
             not [к for к, v in внутри.items()
                  if к != "template_origin" and isinstance(v, str)
                  and v.startswith("/srv/lords/.frontend")])

    # звено 3: artifact_sha256 — сумма ФАЙЛА РАНТАЙМА, и он же исполняется
    рантайм = (N / "src" / "lords-frontend.py").read_bytes()
    проверка("artifact_sha256 — сумма файла рантайма",
             внутри["artifact_sha256"] == hashlib.sha256(рантайм).hexdigest())
    здоровье = json.loads(urllib.request.urlopen(БАЗА + "/healthz", timeout=30).read())
    факт = подробность(здоровье, "runtime_sha256", БАЗА)
    проверка("исполняемый код — тот же файл",
             факт == hashlib.sha256(рантайм).hexdigest(),
             f"{факт[:12]} vs {hashlib.sha256(рантайм).hexdigest()[:12]}")

    # закрепление: рантайм совпадает с тем, что записано в pins
    пины = json.loads((N / "pins.lock.json").read_text())
    for имя, мета in пины["files"].items():
        if not мета.get("sha256"):
            continue
        файл = N / "src" / имя
        проверка(f"пин {имя} сходится",
                 hashlib.sha256(файл.read_bytes()).hexdigest() == мета["sha256"])

    # секреты в диагностике
    сырое = json.dumps(здоровье, ensure_ascii=False)
    проверка("publisher_id не в /healthz", "10555" not in сырое)
    проверка("содержимого настройки плеера нет", "publisher_id" not in сырое)

print(f"{'проверка':<50} итог")
print("-" * 66)
for имя, статус, подр in итог:
    print(f"{имя:<50} {статус}" + (f"  {подр}" if статус == "FAIL" and подр else ""))
print("-" * 66)
print(f"всего {len(итог)}, провалов {len(провалы)}")
sys.exit(1 if провалы else 0)
