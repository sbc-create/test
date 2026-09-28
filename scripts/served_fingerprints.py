#!/usr/bin/env python3
"""Отпечатки того, что витрина РЕАЛЬНО отдала браузеру.

Зачем отдельный инструмент. Сборка знает, что она собрала; манифест знает, что
он объявляет. Ни то, ни другое не доказывает, что по публичному адресу лежит
именно этот артефакт: между ними стоят юнит, прокси и кэш. Здесь берётся
только ответ по HTTPS и считается его отпечаток — так, как его увидел бы
посетитель.

Считается по каждому адресу:

* код ответа и конечный адрес после переходов, плюс их число;
* SHA-256 тела;
* объявленные витриной семейство, версия оформления, build_id, artifact_sha256
  и коммит — из заголовков `X-Site-Factory-*`, а не из разметки;
* SHA-256 встроенного CSS и встроенного JS (рантайм отдаёт их внутри страницы,
  отдельными файлами их нет).

Отпечаток CSS и JS берётся из тела страницы намеренно: искать их отдельными
запросами значило бы измерять не то, что отдали, а то, что удалось найти.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import urllib.error
import urllib.request
from datetime import datetime, timezone

СТИЛЬ = re.compile(r"<style[^>]*>(.*?)</style>", re.S)
СКРИПТ = re.compile(r"<script(?![^>]*\bsrc=)[^>]*>(.*?)</script>", re.S)

ЗАГОЛОВКИ = {
    "family": "X-Site-Factory-Template-Family",
    "design_version": "X-Site-Factory-Template-Version",
    "build_id": "X-Site-Factory-Build-Id",
    "artifact_sha256": "X-Site-Factory-Artifact-Sha256",
    "source_commit": "X-Site-Factory-Template-Revision",
    "profile": "X-Site-Factory-Profile",
    "template": "X-Site-Factory-Template",
}


def _sha(данные: bytes) -> str:
    return hashlib.sha256(данные).hexdigest()


class Счётчик(urllib.request.HTTPRedirectHandler):
    """Переходы считаются, а не «обрабатываются прозрачно».

    Цепочка длиннее одного перехода — это дефект маршрутизации, и увидеть его
    можно только если переходы сосчитаны. Стандартный обработчик их прячет.
    """

    def __init__(self):
        self.цепочка = []

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        self.цепочка.append({"from": req.full_url, "code": code, "to": newurl})
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def отпечаток(адрес: str, таймаут: int = 30) -> dict:
    счётчик = Счётчик()
    открыватель = urllib.request.build_opener(счётчик)
    запрос = urllib.request.Request(адрес, headers={"User-Agent": "site-factory-fingerprint"})
    итог = {"url": адрес, "redirects": счётчик.цепочка}
    try:
        with открыватель.open(запрос, timeout=таймаут) as ответ:
            тело = ответ.read()
            итог["status"] = ответ.status
            итог["final_url"] = ответ.url
            заголовки = ответ.headers
    except urllib.error.HTTPError as ош:
        тело = ош.read()
        итог["status"] = ош.code
        итог["final_url"] = адрес
        заголовки = ош.headers
    except OSError as ош:
        итог["status"] = -1
        итог["error"] = str(ош)[:160]
        return итог

    итог["bytes"] = len(тело)
    итог["html_sha256"] = _sha(тело)
    текст = тело.decode("utf-8", "replace")
    стили = "".join(СТИЛЬ.findall(текст))
    скрипты = "".join(СКРИПТ.findall(текст))
    итог["css_sha256"] = _sha(стили.encode("utf-8")) if стили else ""
    итог["css_bytes"] = len(стили)
    итог["js_sha256"] = _sha(скрипты.encode("utf-8")) if скрипты else ""
    итог["js_bytes"] = len(скрипты)
    итог["declared"] = {имя: заголовки.get(з, "") for имя, з in ЗАГОЛОВКИ.items()}
    метка = re.search(r"Template:\s*([^<]+)", текст)
    итог["footer_marker"] = метка.group(1).strip() if метка else ""
    return итог


def main(argv=None) -> int:
    разбор = argparse.ArgumentParser(description=__doc__)
    разбор.add_argument("--url", action="append", required=True,
                        help="адрес; можно повторять")
    разбор.add_argument("--out", help="куда сложить JSON (по умолчанию — stdout)")
    разбор.add_argument("--label", default="", help="метка снимка (before/after/rollback)")
    арг = разбор.parse_args(argv)

    снимок = {
        "label": арг.label,
        "taken_at_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "pages": [отпечаток(u) for u in арг.url],
    }
    текст = json.dumps(снимок, ensure_ascii=False, indent=1)
    if арг.out:
        with open(арг.out, "w", encoding="utf-8") as ф:
            ф.write(текст + "\n")
        for с in снимок["pages"]:
            д = с.get("declared") or {}
            print(f"{с['status']:>4} {с['url']}\n"
                  f"     версия={д.get('design_version') or '—'} "
                  f"build={(д.get('build_id') or '—')} "
                  f"артефакт={(д.get('artifact_sha256') or '—')[:12]} "
                  f"html={(с.get('html_sha256') or '')[:12]} "
                  f"css={(с.get('css_sha256') or '')[:12]}")
        print(f"снимок: {арг.out}")
    else:
        print(текст)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
