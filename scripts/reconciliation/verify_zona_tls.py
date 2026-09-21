#!/usr/bin/env python3
"""Проверяет публичный край витрины: TLS, заголовки версии и индексацию.

Проверка на origin доказывает, что выложенный артефакт отдаёт правильно, но
про публичный край не говорит ничего: сертификат, протокол и заголовки от
nginx туда не входят. Предмет здесь другой, а не тот же самый с другого
адреса.

Запуск: python3 scripts/reconciliation/verify_zona_tls.py <метка>
"""

from __future__ import annotations

import json
import socket
import ssl
import sys
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

ДОМЕН = "zonafilm.space"
ВЫХОД = Path("artifacts/evidence/zona-slider-date-deploy-01")

ОЖИДАЕМЫЙ_АРТЕФАКТ = "19c3e70cf7a1286b5e1dc5a316aceab778dbf804216558f16e69413dfe7b88b7"
ОЖИДАЕМАЯ_СБОРКА = "20260921T161251Z-c3c9c37f-nova"
ОЖИДАЕМЫЙ_ИСХОДНИК = "c3c9c37f8033907b2297f84faf829f89047d3438"


def tls() -> dict[str, object]:
    ctx = ssl.create_default_context()
    with socket.create_connection((ДОМЕН, 443), timeout=30) as сырой:
        with ctx.wrap_socket(сырой, server_hostname=ДОМЕН) as s:
            серт = s.getpeercert()
            шифр = s.cipher()
            до = серт.get("notAfter")
            осталось = None
            if до:
                конец = datetime.strptime(до, "%b %d %H:%M:%S %Y %Z").replace(
                    tzinfo=timezone.utc)
                осталось = (конец - datetime.now(timezone.utc)).days
            субъект = {k: v for часть in серт.get("subject", ()) for k, v in часть}
            издатель = {k: v for часть in серт.get("issuer", ()) for k, v in часть}
            имена = [v for k, v in серт.get("subjectAltName", ()) if k == "DNS"]
            return {
                "protocol": s.version(),
                "cipher": шифр[0] if шифр else None,
                "cert_subject_cn": субъект.get("commonName"),
                "cert_issuer": издатель.get("organizationName") or издатель.get("commonName"),
                "cert_not_after": до,
                "cert_days_left": осталось,
                "cert_covers_domain": ДОМЕН in имена or f"*.{ДОМЕН.split('.', 1)[1]}" in имена,
                "san": имена[:8],
                "hostname_verified": True,
            }


def страница(путь: str = "/") -> dict[str, object]:
    запрос = urllib.request.Request(
        f"https://{ДОМЕН}{путь}",
        headers={"User-Agent": "zona-public-acceptance", "Cache-Control": "no-cache"})
    with urllib.request.urlopen(запрос, timeout=60) as r:
        тело = r.read().decode("utf-8", "replace")
        h = {k.lower(): v for k, v in r.headers.items()}
        return {
            "path": путь,
            "status": r.status,
            "bytes": len(тело),
            "build": h.get("x-site-factory-build-id"),
            "artifact": h.get("x-site-factory-artifact-sha256"),
            "revision": h.get("x-site-factory-template-revision"),
            "robots_header": h.get("x-robots-tag"),
            "server": h.get("server"),
            "cache": h.get("cache-control"),
            "robots_meta_noindex": 'name="robots" content="noindex' in тело,
        }


def main() -> int:
    метка = sys.argv[1] if len(sys.argv) > 1 else "public"
    ВЫХОД.mkdir(parents=True, exist_ok=True)

    сертификат = tls()
    страницы = [страница(p) for p in ("/", "/catalog/", "/new/", "/search/?q=matrix")]
    ok = [p for p in страницы if p["status"] == 200]

    ворота = {
        "TLS_PROTOCOL_MODERN": сертификат["protocol"] in ("TLSv1.2", "TLSv1.3"),
        "TLS_CERT_COVERS_DOMAIN": bool(сертификат["cert_covers_domain"]),
        "TLS_CERT_NOT_EXPIRING_SOON": (сертификат["cert_days_left"] or 0) > 14,
        "ALL_200": len(ok) == len(страницы),
        "ARTIFACT_MATCH": all(p["artifact"] == ОЖИДАЕМЫЙ_АРТЕФАКТ for p in ok),
        "BUILD_MATCH": all(p["build"] == ОЖИДАЕМАЯ_СБОРКА for p in ok),
        "REVISION_MATCH": all(p["revision"] == ОЖИДАЕМЫЙ_ИСХОДНИК for p in ok),
        "NOINDEX_HEADER": all(
            "noindex" in (p["robots_header"] or "").lower() for p in ok),
        "NOINDEX_META": all(p["robots_meta_noindex"] for p in ok),
    }
    отчёт = {
        "domain": ДОМЕН,
        "метка": метка,
        "at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "tls": сертификат,
        "pages": страницы,
        "ворота": ворота,
        "VERDICT": "PASS" if all(ворота.values()) else "FAIL",
    }
    (ВЫХОД / f"PUBLIC_TLS_{метка}.json").write_text(
        json.dumps(отчёт, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"tls": сертификат, "ворота": ворота,
                      "VERDICT": отчёт["VERDICT"]}, ensure_ascii=False, indent=2))
    return 0 if all(ворота.values()) else 2


if __name__ == "__main__":
    raise SystemExit(main())
