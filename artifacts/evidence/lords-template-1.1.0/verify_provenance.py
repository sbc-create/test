#!/usr/bin/env python3
"""Происхождение: исходный коммит → собранный артефакт → исполняемый код.

Три звена, и каждое проверяется отдельно. Обрыв любого означает, что по цифрам
витрины нельзя сказать, какой код работает, — а решают именно по ним.
"""
import hashlib, json, subprocess, sys, tarfile, tempfile, urllib.request
from pathlib import Path

N = Path("/tmp/claude-1001/-home-claude/9e5d5d7c-1b72-454b-9239-dbb120e73b48/scratchpad/new-lords-90")
БАЗА = "http://127.0.0.1:9190"
итог, провалы = [], []

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
    проверка("исполняемый код — тот же файл",
             здоровье["runtime_sha256"] == hashlib.sha256(рантайм).hexdigest(),
             f"{здоровье['runtime_sha256'][:12]} vs {hashlib.sha256(рантайм).hexdigest()[:12]}")

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
