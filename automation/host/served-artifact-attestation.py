#!/usr/bin/env python3
"""Что витрина обслуживает на самом деле: аттестация загруженного.

Вопрос, на который отвечает этот файл, один: совпадает ли то, что получает
браузер зрителя, с тем, что мы собрали. Ответ строится не из отчётов сборки, а
из ответа сервера: заголовки, отпечатки фактически загруженных HTML, CSS и JS,
объявленная версия шаблона, идентификатор сборки.

Отпечаток артефакта в манифесте релиза и отпечаток того, что реально пришло по
сети, — разные величины, и путать их нельзя. Первый говорит, что мы собрали;
второй — что видит человек.

    python3 automation/host/served-artifact-attestation.py \
        --out artifacts/served-attestation/live.json
"""
from __future__ import annotations

import argparse
import hashlib
import json
import pathlib
import re
import sys
import time
import urllib.error
import urllib.request

КОРЕНЬ = pathlib.Path(__file__).resolve().parents[2]
РЕЕСТР = "http://127.0.0.1:8790/api/v1/registry/snapshot"
АГЕНТ = "site-factory-templates-readonly/1.0 (+served-attestation)"

ВЕРСИЯ_ШАБЛОНА = re.compile(
    r'data-template-version="([^"]*)"[^>]*data-template-family="([^"]*)"'
    r'[^>]*data-build-id="([^"]*)"')
ОТПЕЧАТОК = re.compile(r'artifact-sha256="([^"]*)"')
ПОДВАЛ_ВЕРСИЯ = re.compile(r"Template:\s*([a-z0-9]+)\s*([0-9.]+)[^0-9a-f]*([0-9a-f]{6,})")
РЕСУРС = re.compile(r'(?:href|src)="(/[^"]+\.(?:css|js))"')


def получить(адрес: str) -> dict:
    зпр = urllib.request.Request(адрес, headers={"User-Agent": АГЕНТ})
    начало = time.monotonic()
    try:
        with urllib.request.urlopen(зпр, timeout=25) as о:
            тело = о.read()
            заг = {k.lower(): v for k, v in о.getheaders()}
            return {"status": о.status, "final_url": о.geturl(), "bytes": len(тело),
                    "sha256": hashlib.sha256(тело).hexdigest(),
                    "headers": заг, "body": тело.decode("utf-8", "replace"),
                    "seconds": round(time.monotonic() - начало, 3)}
    except urllib.error.HTTPError as ош:
        тело = ош.read()
        return {"status": ош.code, "final_url": адрес, "bytes": len(тело),
                "sha256": hashlib.sha256(тело).hexdigest(),
                "headers": {k.lower(): v for k, v in ош.getheaders()},
                "body": тело.decode("utf-8", "replace")}
    except Exception as ош:
        return {"status": None, "final_url": адрес, "error": f"{type(ош).__name__}: {ош}"[:160]}


def аттестовать(база: str, путь: str = "/") -> dict:
    страница = получить(база + путь)
    если_ошибка = страница.get("error")
    итог = {"url": база + путь, "checked_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "status": страница.get("status"), "error": если_ошибка,
            "html_sha256": страница.get("sha256"), "html_bytes": страница.get("bytes")}
    if если_ошибка:
        return итог
    тело = страница["body"]
    заг = страница["headers"]
    итог["headers"] = {k: заг.get(k) for k in
                       ("server", "cache-control", "etag", "last-modified",
                        "content-type", "age", "x-cache", "cf-cache-status")}
    в = ВЕРСИЯ_ШАБЛОНА.search(тело)
    о = ОТПЕЧАТОК.search(тело)
    п = ПОДВАЛ_ВЕРСИЯ.search(re.sub(r"<[^>]+>", " ", тело))
    итог["template_version"] = в.group(1) if в else None
    итог["template_family"] = в.group(2) if в else None
    итог["build_id"] = в.group(3) if в else None
    итог["artifact_sha256_declared"] = о.group(1) if о else None
    итог["footer_template"] = (f"{п.group(1)} {п.group(2)} · {п.group(3)}") if п else None
    # Отпечатки фактически подключённых ресурсов: не то, что лежит в артефакте,
    # а то, что браузер действительно загрузит по этим адресам.
    ресурсы = []
    for отн in dict.fromkeys(РЕСУРС.findall(тело)):
        r = получить(база + отн)
        ресурсы.append({"path": отн, "status": r.get("status"),
                        "bytes": r.get("bytes"), "sha256": r.get("sha256"),
                        "cache_control": (r.get("headers") or {}).get("cache-control")})
    итог["assets"] = ресурсы
    итог["service_worker_referenced"] = bool(
        re.search(r"serviceWorker\s*\.\s*register", тело))
    return итог


def главное(аргв=None) -> int:
    р = argparse.ArgumentParser(description=__doc__)
    р.add_argument("--out", default="artifacts/served-attestation/live.json")
    р.add_argument("--base", action="append", default=None,
                   help="дополнительный базовый адрес (например, стенд кандидата)")
    р.add_argument("--path", default="/")
    а = р.parse_args(аргв)

    цели: list[tuple[str, str]] = []
    if а.base:
        цели += [(f"ручной:{б}", б) for б in а.base]
    else:
        зпр = urllib.request.Request(РЕЕСТР, headers={"User-Agent": АГЕНТ})
        with urllib.request.urlopen(зпр, timeout=20) as о:
            снимок = json.loads(о.read())
        цели += [(с["site_id"], f"https://{с['canonical_domain']}")
                 for с in снимок["sites"] if с.get("family") in ("lords", "zona")]

    итог = {}
    for имя, база in цели:
        итог[имя] = аттестовать(база, а.path)
        з = итог[имя]
        print(f"{имя:12s} {з.get('status')} версия={з.get('template_version')} "
              f"build={з.get('build_id')} подвал={з.get('footer_template')} "
              f"html={str(з.get('html_sha256'))[:12]}", flush=True)
    путь = КОРЕНЬ / а.out
    путь.parent.mkdir(parents=True, exist_ok=True)
    путь.write_text(json.dumps(итог, ensure_ascii=False, indent=1), encoding="utf-8")
    print("записано:", а.out)
    return 0


if __name__ == "__main__":
    raise SystemExit(главное())
