#!/usr/bin/env python3
"""Фактическое состояние всех доменов задачи. Одна таблица, обновляемая прогоном.

    python3 automation/host/domain-state.py [--json] [--domain <домен>]

Четыре исхода различаются везде, где это возможно, и не сливаются в «нет»:

    ок / значение      проверено и работает
    НЕ РАБОТАЕТ        объект существует, но результата не даёт
    НЕТ ОБЪЕКТА        объекта не существует
    нет доступа        проверить нельзя: прав не хватает
    не проверено       проверка не выполнялась

Отдельно проверяется то, что чаще всего врёт: совпадение публичного build-id с
манифестом установленного выпуска. Переключённый `current` при процессе со
старым кодом активацией не считается, и по одному `current` этого не видно.
"""
from __future__ import annotations

import argparse
import json
import os
import socket
import ssl
import subprocess
import sys
import urllib.error
import urllib.request
from pathlib import Path

КОРЕНЬ = Path(__file__).resolve().parent.parent.parent
if not (КОРЕНЬ / "factory" / "cell" / "executor.py").is_file():
    raise SystemExit(f"не похоже на репозиторий фабрики: {КОРЕНЬ}")

#: Домены задачи в заданном порядке. Список закрыт: найденные сверх него
#: показываются отдельно и молча в объём работы не входят.
ДОМЕНЫ = (
    "zonafilm.space", "zonafilm.cc", "lordfilm47.space", "lordserial33.biz",
    "1lordserials1.online", "animedia.space", "animedia.icu", "yummyani.site",
    "yummyani.org", "yummyani.biz", "zonafilm12.site", "lordserials22.site",
    "lordserials22.space", "lordserials22.info", "yummyani7.site", "yummyani7.info",
)

НЕТ = "НЕТ ОБЪЕКТА"
НЕДОСТУП = "нет доступа"
НЕ_ПРОВЕРЕНО = "не проверено"
АГЕНТ = {"User-Agent": "site-factory-domain-state"}


def _ctx() -> ssl.SSLContext:
    c = ssl.create_default_context()
    c.check_hostname = False
    c.verify_mode = ssl.CERT_NONE
    return c


def публичный(домен: str) -> dict:
    итог: dict = {"dns": НЕ_ПРОВЕРЕНО, "https": НЕ_ПРОВЕРЕНО, "build_id": None}
    try:
        итог["dns"] = socket.gethostbyname(домен)
    except OSError as ош:
        итог["dns"] = f"{НЕТ}: {ош.strerror or ош}"
        # Без DNS проверять HTTPS нечего, но «не проверено» здесь читалось бы
        # как «не дошли руки». Причина называется явно.
        итог["https"] = "не проверялось: нет записи DNS"
        return итог
    try:
        r = urllib.request.urlopen(urllib.request.Request(f"https://{домен}/", headers=АГЕНТ),
                                   timeout=20, context=_ctx())
        тело = r.read()
        итог["https"] = f"{r.status}"
        итог["build_id"] = r.headers.get("X-Site-Factory-Build-Id")
        итог["bytes"] = len(тело)
    except urllib.error.HTTPError as ош:
        итог["https"] = f"НЕ РАБОТАЕТ: HTTP {ош.code}"
    except (urllib.error.URLError, OSError) as ош:
        итог["https"] = f"НЕ РАБОТАЕТ: {type(ош).__name__}"
    return итог


def репозиторий(ячейка: dict) -> dict:
    """Рабочая копия и её ветки. Существование на GitHub — отдельным полем."""
    r = ячейка.get("repo") or {}
    remote = r.get("remote")
    путь = КОРЕНЬ / (r.get("path") or "")
    итог = {"remote": remote or НЕТ, "worktree": str(путь) if r.get("path") else НЕТ}
    if not (путь / ".git").exists():
        итог["branch"] = НЕТ
        return итог

    def г(*а: str) -> str:
        return subprocess.run(("git", *а), cwd=путь, capture_output=True,
                              text=True).stdout.strip()

    итог["branch"] = г("rev-parse", "--abbrev-ref", "HEAD") or НЕ_ПРОВЕРЕНО
    итог["head"] = г("rev-parse", "HEAD")[:12]
    итог["dirty"] = bool(г("status", "--short"))
    ветки = г("branch", "-a", "--format=%(refname:short)").split()
    итог["release_branches"] = sorted(b for b in ветки if "release/" in b)
    return итог


def на_github(remote: str) -> str:
    """Существует ли репозиторий. Отвечает УЧЁТНОЙ ЗАПИСЬЮ СЕССИИ, не исполнителя."""
    if not remote or remote == НЕТ:
        return НЕТ
    проект = "/".join(remote.rstrip("/").removesuffix(".git").split("/")[-2:])
    гот = subprocess.run(["gh", "api", f"repos/{проект}", "--jq", ".private"],
                         capture_output=True, text=True)
    if гот.returncode == 0:
        return "есть (приватный)" if гот.stdout.strip() == "true" else "есть (публичный)"
    if "404" in (гот.stderr or ""):
        return НЕТ
    return f"{НЕДОСТУП}: {(гот.stderr or '').strip()[:60]}"


def служба(ячейка: dict) -> dict:
    рв = ячейка.get("runtime") or {}
    имя = рв.get("unit")
    итог = {"unit": имя or НЕТ, "port": рв.get("port"), "account": рв.get("account"),
            "data_dir": рв.get("data_dir")}
    if not имя:
        return итог
    файл = Path("/etc/systemd/system") / имя
    итог["unit_file"] = "есть" if файл.is_file() else НЕТ
    хочет = Path("/etc/systemd/system/multi-user.target.wants") / имя
    итог["enabled"] = "да" if хочет.exists() else "нет"
    корень = Path("/srv") / (рв.get("account") or "нет")
    итог["cell_dir"] = "есть" if корень.is_dir() else НЕТ
    ссылка = корень / "current"
    if ссылка.is_symlink() or ссылка.exists():
        итог["current"] = os.path.basename(os.path.realpath(ссылка))
        манифест = ссылка / "release-manifest.json"
        try:
            м = json.loads(манифест.read_text(encoding="utf-8"))
            итог["installed_commit"] = (м.get("commit") or "")[:12]
            итог["installed_build_id"] = м.get("live_build_id")
        except OSError as ош:
            итог["installed_commit"] = (НЕДОСТУП if isinstance(ош, PermissionError) else НЕТ)
        except ValueError:
            итог["installed_commit"] = "НЕ РАБОТАЕТ: манифест нечитаем"
    else:
        итог["current"] = НЕТ
    return итог


def nginx(site_id: str, домен: str) -> dict:
    conf = Path("/etc/nginx/lords") / f"{site_id}.conf"
    tls = Path("/etc/nginx/lords") / f"{site_id}-tls.conf"
    upstream = Path("/etc/nginx/cells") / f"{site_id}.upstream"
    итог = {"http_conf": "есть" if conf.is_file() else НЕТ,
            "tls_conf": "есть" if tls.is_file() else НЕТ,
            "upstream": НЕТ}
    try:
        итог["upstream"] = (upstream.read_text(encoding="utf-8").strip()
                            if upstream.is_file() else НЕТ)
    except PermissionError:
        итог["upstream"] = НЕДОСТУП
    return итог


def краткий(вердикт: str) -> str:
    """Вердикт в узкую колонку: «да» либо начало причины."""
    return "да" if вердикт == "да" else вердикт[:10]


def main() -> int:
    р = argparse.ArgumentParser()
    р.add_argument("--json", action="store_true")
    р.add_argument("--domain")
    а = р.parse_args()

    ячейки = {c.get("domain"): c for c in json.loads(
        (КОРЕНЬ / "config" / "site-cells.json").read_text(encoding="utf-8"))["cells"]}
    аналитика = {z["domain"]: z for z in json.loads(
        (КОРЕНЬ / "config" / "analytics.json").read_text(encoding="utf-8"))["properties"]}
    sys.path.insert(0, str(КОРЕНЬ))
    from factory.topvisor.manifest import MANIFEST as TV
    топвизор = {s.domain: s for s in TV}

    отчёты = []
    for домен in ДОМЕНЫ:
        if а.domain and домен != а.domain:
            continue
        ячейка = ячейки.get(домен) or {}
        з = аналитика.get(домен) or {}
        сеть = публичный(домен)
        рп = репозиторий(ячейка) if ячейка else {"remote": НЕТ, "branch": НЕТ}
        сл = служба(ячейка) if ячейка else {"unit": НЕТ}
        нг = nginx(ячейка.get("site_id") or "нет", домен) if ячейка else {"http_conf": НЕТ}
        # Главная проверка соответствия: публичный build-id обязан совпасть с
        # манифестом установленного выпуска. Иначе процесс отдаёт не тот код,
        # что установлен, и `current` об этом молчит.
        живой = сеть.get("build_id")
        установленный = сл.get("installed_build_id")
        if живой and установленный:
            совпадение = ("да" if живой == установленный else
                          f"НЕ РАБОТАЕТ: живой {живой}, "
                          f"установлен {установленный}")
        elif живой and not установленный:
            совпадение = "нет манифеста выпуска (монолит или доступ)"
        else:
            совпадение = НЕ_ПРОВЕРЕНО
        отчёты.append({
            "domain": домен,
            "site_id": ячейка.get("site_id") or НЕТ,
            "registry_status": ячейка.get("status") or НЕТ,
            "network": сеть,
            "repo": рп,
            "github": на_github(рп.get("remote", НЕТ)),
            "service": сл,
            "nginx": нг,
            "build_matches_release": совпадение,
            "metrika": з.get("counter_id") or НЕТ,
            "metrika_state": з.get("counter_state") or НЕ_ПРОВЕРЕНО,
            "topvisor_manifest": "да" if домен in топвизор else НЕТ,
            "indexing": (ячейка.get("indexing") or {}).get("desired_state") or НЕ_ПРОВЕРЕНО,
        })

    if а.json:
        print(json.dumps({"domains": отчёты}, ensure_ascii=False, indent=2))
        return 0

    print(f"{'домен':22} {'site_id':12} {'HTTPS':16} {'build-id живой':28} {'совпадает':10} "
          f"{'GitHub':18} {'Метрика':11} TV")
    for о in отчёты:
        print(f"{о['domain']:22} {о['site_id']:12} {str(о['network']['https']):16} "
              f"{str(о['network']['build_id'] or '—'):28} "
              f"{краткий(о['build_matches_release']):10} "
              f"{о['github']:18} {str(о['metrika']):11} {о['topvisor_manifest']}")
    лишние = [d for d in ячейки if d and d not in ДОМЕНЫ]
    if лишние:
        print(f"\nдомены реестра вне списка задачи ({len(лишние)}): {', '.join(sorted(лишние))}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
