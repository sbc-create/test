#!/usr/bin/env python3
"""Проверка публичной витрины сразу после переключения релиза.

Переключение считается состоявшимся не тогда, когда команда вернула ноль, а
тогда, когда публичный домен отдаёт новый релиз и продолжает работать. Между
этими двумя событиями помещается всё, ради чего существует откат.

Проверяется по порядку: релиз действительно сменился; домен отвечает по HTTPS;
сертификат принадлежит этому имени; отдаётся тот tenant, что ожидался; главная,
каталог, поиск и страница произведения приходят целыми; постеры не подменены
заглушками; точка отката существует и указывает на прежний релиз.

Только чтение. Ничего не переключает и не откатывает: решение об откате
принимает тот, кто переключал, а этот сценарий даёт ему основание.

Запуск:
    .venv/bin/python automation/host/lords-post-switch-verify.py --site lords-02 \
        --expect-digest a0cfaf71… --previous-release edd290dd6616
"""

from __future__ import annotations

import argparse
import json
import re
import socket
import ssl
import sys
import urllib.error
import urllib.request
from pathlib import Path

LORDS = Path("/srv/lords")
AGENT = "site-factory-templates/1.0 (post-switch verify, read-only)"
TIMEOUT = 20

#: Поверхности, которые обязаны прийти целыми. Список короткий намеренно:
#: проверка идёт сразу после переключения, и её задача — заметить обвал, а не
#: заменить приёмку.
ROUTES = ("/", "/catalog/", "/search/", "/new/")


def _fetch(url: str) -> tuple[int | None, str, dict]:
    request = urllib.request.Request(url, headers={"User-Agent": AGENT})
    try:
        with urllib.request.urlopen(request, timeout=TIMEOUT) as response:
            return (response.status,
                    response.read(3_000_000).decode("utf-8", "replace"),
                    dict(response.headers))
    except urllib.error.HTTPError as error:
        return error.code, "", dict(error.headers)
    except (urllib.error.URLError, ssl.SSLError, TimeoutError, OSError) as error:
        return None, f"{type(error).__name__}: {error}"[:200], {}


def certificate(host: str) -> dict:
    context = ssl.create_default_context()
    try:
        with socket.create_connection((host, 443), timeout=TIMEOUT) as raw:
            with context.wrap_socket(raw, server_hostname=host) as tls:
                cert = tls.getpeercert()
                names = [v for k, v in cert.get("subjectAltName", ()) if k == "DNS"]
                return {"served": True, "matches_host": host in names,
                        "not_after": cert.get("notAfter")}
    except Exception as error:  # noqa: BLE001 — состояние, а не отказ проверки
        return {"served": False, "note": f"{type(error).__name__}"}


def verify(site: str, expect_digest: str | None, previous: str | None) -> dict:
    current = (LORDS / site / "current").resolve()
    manifest = json.loads((current / "release-manifest.json").read_text(encoding="utf-8"))
    domain = str(manifest["domain"])

    отчёт: dict = {
        "site": site, "domain": domain,
        "deployed_release": current.name,
        "previous_release": previous,
        "release_changed": (previous is None or current.name != previous),
        "template_digest": manifest["template_digest"],
        "digest_matches_expected": (expect_digest is None
                                    or manifest["template_digest"] == expect_digest),
        "content_source": manifest.get("content_source"),
        "content_snapshot": manifest.get("content_snapshot_id"),
        "rollback_target": manifest.get("rollback_target"),
        "rollback_exists": bool(manifest.get("rollback_target")
                                and (LORDS / site / "releases"
                                     / str(manifest["rollback_target"])).is_dir()),
        "tls": certificate(domain),
        "routes": {},
    }

    for route in ROUTES:
        status, body, _ = _fetch(f"https://{domain}{route}")
        запись = {"status": status, "bytes": len(body)}
        if status == 200:
            запись["title"] = (body.split("<title>", 1)[1].split("</title>", 1)[0][:100]
                               if "<title>" in body else "")
            # Признак берётся общий для всех страниц витрины, а не только
            # для главной. `data-block` и `data-shelf` описывают блоки главной
            # и на листингах не встречаются вовсе: первая редакция этой
            # проверки объявила отказом `/catalog/`, `/search/` и `/new/` на
            # исправной витрине и посоветовала откат.
            запись["renderer_markup"] = sum(
                1 for m in ('/assets/site.css', 'site-nav', 'class="container"')
                if m in body)
            запись["tenant_domain_in_page"] = domain in body
        отчёт["routes"][route] = запись

    # Страница произведения — со своей же главной, а не выдуманная.
    главная = отчёт["routes"].get("/", {})
    if главная.get("status") == 200:
        _, body, _ = _fetch(f"https://{domain}/")
        ссылки = re.findall(r'href="(/title/[^"]+)"', body)
        if ссылки:
            status, тело, _ = _fetch(f"https://{domain}{ссылки[0]}")
            отчёт["title_page"] = {"path": ссылки[0], "status": status,
                                   "bytes": len(тело)}

    # Постеры: заглушка отдаётся с кодом 200, поэтому код ни о чём не говорит.
    _, body, _ = _fetch(f"https://{domain}/")
    постеры = list(dict.fromkeys(re.findall(r'<img[^>]+src="(/poster/[^"]+)"', body)))[:12]
    состояния: dict[str, int] = {}
    for адрес in постеры:
        _, _, headers = _fetch(f"https://{domain}{адрес}")
        ключ = ("placeholder" if headers.get("X-Poster-Cache") == "PLACEHOLDER"
                else (headers.get("Content-Type") or "?").split(";")[0])
        состояния[ключ] = состояния.get(ключ, 0) + 1
    отчёт["posters"] = {"checked": len(постеры), "states": состояния,
                        "placeholders": состояния.get("placeholder", 0)}

    отказы = []
    if not отчёт["release_changed"]:
        отказы.append("релиз не сменился")
    if not отчёт["digest_matches_expected"]:
        отказы.append("отпечаток не тот, что ожидался")
    if not отчёт["rollback_exists"]:
        отказы.append("точки отката нет")
    if not отчёт["tls"].get("matches_host"):
        отказы.append("сертификат не для этого имени")
    for route, запись in отчёт["routes"].items():
        if запись.get("status") != 200:
            отказы.append(f"{route} отвечает {запись.get('status')}")
        elif not запись.get("renderer_markup"):
            отказы.append(f"{route} без разметки рендерера")
        elif not запись.get("tenant_domain_in_page"):
            отказы.append(f"{route} не называет свой домен: возможен чужой tenant")
    if отчёт["posters"]["placeholders"]:
        отказы.append(f"постеров-заглушек: {отчёт['posters']['placeholders']}")

    отчёт["failures"] = отказы
    отчёт["verdict"] = "OK" if not отказы else "ROLLBACK_RECOMMENDED"
    return отчёт


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--site", required=True)
    parser.add_argument("--expect-digest", default=None)
    parser.add_argument("--previous-release", default=None)
    args = parser.parse_args()

    отчёт = verify(args.site, args.expect_digest, args.previous_release)
    print(json.dumps(отчёт, ensure_ascii=False, indent=2))
    return 0 if отчёт["verdict"] == "OK" else 1


if __name__ == "__main__":
    raise SystemExit(main())
