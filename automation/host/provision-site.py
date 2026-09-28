#!/usr/bin/env python3
"""Разворачивает витрину из готового среза: релиз, юнит, vhost, канонический адрес.

Зачем
-----

Zona и Animedia существовали как локальные срезы: пакет есть, содержимое
отрисовано, а домена, цели выката, рантайма и записи в nginx нет. Владелец
передал домены заданием от 2026-09-10 и распорядился создать инфраструктуру,
а не считать её отсутствие блокером.

Раскладка повторяет действующую у Lords, а не изобретает новую: неизменяемый
каталог `releases/<id>`, ссылка `current`, юнит с портом на петле, nginx
впереди. Ровно та схема, что уже держит три боевые витрины.

Что делает (идемпотентно)
-------------------------

1. считает идентификатор релиза от содержимого — одинаковый вход даёт
   одинаковый релиз, и повторный запуск не плодит каталоги;
2. раскладывает срез в `releases/<id>/site`, кладёт рядом `serve.py`;
3. вписывает canonical в каждую страницу — свой для каждого домена;
4. пишет release-manifest.json и ссылку `current`;
5. ставит systemd-юнит на свободном порту петли;
6. пишет vhost nginx и проверяет конфигурацию ДО перезагрузки.

Чего не делает: не трогает DNS и не выпускает сертификаты. Без записи DNS
ACME невозможен, и притворяться, что это не так, здесь нечем.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path

БАЗА = Path("/srv/lords")
ЮНИТЫ = Path("/etc/systemd/system")
NGINX = Path("/etc/nginx/lords")
ОБРАЗЕЦ_SERVE = Path("/srv/lords/lords-03/current/serve.py")

ЮНИТ = """[Unit]
Description=Витрина {сайт} ({домен})
After=network-online.target

[Service]
Type=simple
User=lords
WorkingDirectory={корень}/current
Environment=LORDS_HOST=127.0.0.1
Environment=LORDS_PORT={порт}
Environment=LORDS_SITE_ROOT={корень}/current
Environment=PYTHONDONTWRITEBYTECODE=1
ExecStart=/usr/bin/python3 {корень}/current/serve.py
Restart=on-failure
RestartSec=2

[Install]
WantedBy=multi-user.target
"""

VHOST = """# {домен} — витрина {сайт}.
#
# Выложена {когда} инструментом automation/host/provision-site.py.
# TLS появится вместе с записью DNS: ACME без неё невозможен, а притворяться
# нечем. До этого домен проверяется по Host/SNI на самом хосте.

server {{
    listen 80;
    listen [::]:80;
    server_name {домен} www.{домен};

    server_tokens off;

    location ^~ /.well-known/acme-challenge/ {{
        root /var/www/certbot;
        default_type "text/plain";
    }}

    location / {{
        proxy_pass http://127.0.0.1:{порт};
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_read_timeout 30s;
    }}

    location = /healthz {{
        proxy_pass http://127.0.0.1:{порт}/healthz;
        access_log off;
    }}
}}
"""


def сказать(т: str) -> None:
    print(f"[витрина] {т}", flush=True)


def выполнить(*а: str, таймаут: float = 300.0):
    return subprocess.run(а, capture_output=True, text=True, timeout=таймаут)


def идентификатор(срез: Path, домен: str) -> str:
    """От содержимого И домена: одинаковый вход — одинаковый релиз.

    Домен входит в отпечаток не для красоты. Canonical вписывается в каждую
    страницу свой, поэтому два релиза из одного среза для разных доменов —
    это разное содержимое. Считать им один идентификатор значит объявить
    одинаковым то, что различается; при первой раскладке animedia.icu и
    animedia.space так и получили один номер 852aae298457 на две разные
    выкладки.
    """
    h = hashlib.sha256()
    h.update(домен.encode("utf-8") + b"\0")
    for путь in sorted(срез.rglob("*")):
        if путь.is_file():
            h.update(str(путь.relative_to(срез)).encode("utf-8"))
            h.update(путь.read_bytes()[:65536])
    return h.hexdigest()[:12]


КАНОНИКАЛ = re.compile(rb'<link[^>]+rel="canonical"[^>]*>', re.I)


def вписать_canonical(корень_сайта: Path, домен: str) -> int:
    """Свой canonical на каждой странице. Чужой — хуже отсутствующего."""
    изменено = 0
    for стр in корень_сайта.rglob("*.html"):
        данные = стр.read_bytes()
        относительный = str(стр.relative_to(корень_сайта)) if False else str(
            стр.relative_to(корень_сайта))
        путь = "/" if относительный == "index.html" else (
            "/" + относительный[: -len("index.html")] if относительный.endswith("/index.html")
            else "/" + относительный)
        адрес = f"https://{домен}{путь}".encode("utf-8")
        ссылка = b'<link rel="canonical" href="' + адрес + b'">'
        if КАНОНИКАЛ.search(данные):
            новые = КАНОНИКАЛ.sub(ссылка, данные, count=1)
        elif b"</head>" in данные:
            новые = данные.replace(b"</head>", ссылка + b"</head>", 1)
        else:
            continue
        if новые != данные:
            стр.write_bytes(новые)
            изменено += 1
    return изменено


def развернуть(сайт: str, домен: str, порт: int, срез: Path, применить: bool) -> dict:
    корень = БАЗА / сайт
    релиз_ид = идентификатор(срез, домен)
    релиз = корень / "releases" / релиз_ид
    итог = {"site": сайт, "domain": домен, "port": порт, "release": релиз_ид}

    if not применить:
        итог["verdict"] = "ПЛАН"
        return итог

    if not релиз.is_dir():
        (корень / "releases").mkdir(parents=True, exist_ok=True)
        временный = релиз.with_name(f".{релиз_ид}.new")
        if временный.exists():
            shutil.rmtree(временный)
        (временный / "site").mkdir(parents=True)
        # copytree с dirs_exist_ok: срез переносится как есть.
        shutil.copytree(срез, временный / "site", dirs_exist_ok=True)
        shutil.copy2(ОБРАЗЕЦ_SERVE, временный / "serve.py")
        итог["canonical_страниц"] = вписать_canonical(временный / "site", домен)
        (временный / "release-manifest.json").write_text(json.dumps({
            "tenant_id": сайт, "domain": домен, "release": релиз_ид,
            "source_slice": str(срез), "created_at": time.strftime(
                "%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "created_by": "automation/host/provision-site.py",
            "production_authorized": True,
            "release_reason": "provision-from-slice",
            "previous_release": None,
            "rollback_target": None,
            "note": ("Первая раскладка витрины: откатываться некуда, и ссылка "
                     "previous намеренно не создаётся — обещание отката, "
                     "которого нет, хуже его отсутствия."),
        }, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        os.replace(временный, релиз)
        выполнить("chown", "-R", "lords:lords", str(корень))
        сказать(f"{сайт}: релиз {релиз_ид} разложен")
    else:
        сказать(f"{сайт}: релиз {релиз_ид} уже есть")

    ссылка = корень / "current"
    # Прежний релиз становится точкой отката — но только если он существует и
    # это не он же. Первая раскладка ссылку не создаёт: обещание отката,
    # которого нет, хуже его отсутствия.
    прежний = None
    if ссылка.is_symlink():
        цель = ссылка.resolve()
        if цель.is_dir() and цель != релиз:
            прежний = цель
    временная = корень / ".current.new"
    if временная.exists() or временная.is_symlink():
        временная.unlink()
    временная.symlink_to(релиз)
    os.replace(временная, ссылка)
    выполнить("chown", "-h", "lords:lords", str(ссылка))
    if прежний is not None:
        врем_пред = корень / ".previous.new"
        if врем_пред.exists() or врем_пред.is_symlink():
            врем_пред.unlink()
        врем_пред.symlink_to(прежний)
        os.replace(врем_пред, корень / "previous")
        выполнить("chown", "-h", "lords:lords", str(корень / "previous"))
        итог["previous"] = прежний.name
        сказать(f"{сайт}: точка отката {прежний.name}")

    (ЮНИТЫ / f"{сайт}.service").write_text(
        ЮНИТ.format(сайт=сайт, домен=домен, корень=корень, порт=порт), encoding="utf-8")
    выполнить("systemctl", "daemon-reload", таймаут=180)
    выполнить("systemctl", "enable", "--now", f"{сайт}.service", таймаут=180)
    состояние = выполнить("systemctl", "is-active", f"{сайт}.service").stdout.strip()
    итог["unit"] = состояние
    сказать(f"{сайт}: юнит {состояние} на 127.0.0.1:{порт}")

    NGINX.mkdir(parents=True, exist_ok=True)
    (NGINX / f"{сайт}.conf").write_text(
        VHOST.format(сайт=сайт, домен=домен, порт=порт,
                     когда=time.strftime("%Y-%m-%d", time.gmtime())), encoding="utf-8")
    проверка = выполнить("nginx", "-t", таймаут=120)
    итог["nginx_test"] = "ok" if проверка.returncode == 0 else проверка.stderr[-200:]
    if проверка.returncode != 0:
        (NGINX / f"{сайт}.conf").unlink(missing_ok=True)
        итог["verdict"] = "ОТКАЗ: конфигурация nginx не прошла проверку"
        return итог
    выполнить("systemctl", "reload", "nginx", таймаут=120)
    сказать(f"{сайт}: vhost {домен} принят, nginx перезагружен")
    итог["verdict"] = "ГОТОВО"
    return итог


ВИТРИНЫ = [
    ("zona-01", "zonafilm.space", 9104, Path("/home/claude/wt-integration-28/var/product-preview/zona-cinema")),
    ("animedia-01", "animedia.icu", 9105, Path("/home/claude/wt-integration-28/var/product-preview/animedia-portal")),
    ("animedia-02", "animedia.space", 9106, Path("/home/claude/wt-integration-28/var/product-preview/animedia-portal")),
]


def main() -> int:
    р = argparse.ArgumentParser(description=__doc__)
    р.add_argument("--apply", action="store_true")
    р.add_argument("--only", default=None, help="развернуть одну витрину по имени")
    args = р.parse_args()
    код = 0
    for сайт, домен, порт, срез in ВИТРИНЫ:
        if args.only and сайт != args.only:
            continue
        if not срез.is_dir():
            print(json.dumps({"site": сайт, "verdict": f"ОТКАЗ: нет среза {срез}"},
                             ensure_ascii=False))
            код = 1
            continue
        итог = развернуть(сайт, домен, порт, срез, args.apply)
        print(json.dumps(итог, ensure_ascii=False))
        if str(итог.get("verdict", "")).startswith("ОТКАЗ"):
            код = 1
    return код


if __name__ == "__main__":
    sys.exit(main())
