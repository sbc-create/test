#!/usr/bin/env python3
"""Приёмка витрины Zona сразу после перезапуска — одной командой.

Зачем отдельный инструмент. Выкладка заканчивается не установкой байтов, а
подтверждением, что домен отдаёт то, что от него ждут. Между этими двумя
событиями стоит перезапуск, который выполняет владелец, и проверять результат
надо в ту же минуту — иначе витрина остаётся непроверенной ровно там, где её
меняли.

Что проверяется на живом домене:

* главная отдаёт 200 и ровно один непустой H1;
* в героe настоящий слайдер: не меньше двух РАЗНЫХ слайдов с уникальными
  идентификаторами, названиями и картинками;
* страницы произведений, на которые ведёт главная, отвечают 200;
* заведомо несуществующий адрес отвечает честным 404;
* объявленная сборка совпадает с установленной;
* индексация не изменилась.

Ничего не меняет. При провале печатает точную команду отката.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

ФРОНТ = Path("/srv/lords/.frontend")


def взять(домен: str, порт: int, путь: str, таймаут: float = 45.0):
    req = urllib.request.Request(
        f"http://127.0.0.1:{порт}{urllib.parse.quote(путь, safe='/?&=%')}",
        headers={"Host": домен, "User-Agent": "zona-post-restart-verify"})
    try:
        with urllib.request.urlopen(req, timeout=таймаут) as r:
            return r.status, r.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        return e.code, (e.read() or b"").decode("utf-8", "replace")
    except Exception as e:
        return 0, f"{e!r}"


def main() -> int:
    р = argparse.ArgumentParser(description=__doc__)
    р.add_argument("--domain", default="zonafilm.space")
    р.add_argument("--port", type=int, default=9120)
    р.add_argument("--site", default="zona-01")
    р.add_argument("--titles", type=int, default=12,
                   help="сколько страниц произведений проверить с главной")
    р.add_argument("--out", default="")
    а = р.parse_args()

    манифест_путь = ФРОНТ / f"template-manifest-{а.site}.json"
    манифест = json.loads(манифест_путь.read_text(encoding="utf-8"))
    артефакт = Path(манифест["artifact_path"])
    на_диске = hashlib.sha256(артефакт.read_bytes()).hexdigest()

    беды: list[str] = []
    итог: dict = {"domain": а.domain, "site": а.site,
                  "manifest_build": манифест.get("build_id"),
                  "manifest_code_sha256": манифест.get("code_file_sha256"),
                  "artifact_sha256_on_disk": на_диске}

    if манифест.get("code_file_sha256") != на_диске:
        беды.append("манифест объявляет не те байты, что лежат на диске")

    код, дом = взять(а.domain, а.port, "/")
    итог["home_status"] = код
    if код != 200:
        беды.append(f"главная отдала {код}")
        дом = ""

    h1 = [re.sub(r"<[^>]+>", "", т).strip()
          for т in re.findall(r"<h1\b[^>]*>(.*?)</h1>", дом, re.S)]
    итог["h1_count"] = len(h1)
    if len(h1) != 1 or not h1[0]:
        беды.append(f"H1 на главной: {len(h1)}")

    разметка = re.sub(r"<script\b.*?</script>|<style\b.*?</style>", "", дом, flags=re.S)
    ид = re.findall(r'data-slide-id="([^"]*)"', разметка)
    названия = re.findall(r'data-slide-title="([^"]*)"', разметка)
    картинки = re.findall(r'<img src="([^"]+)"[^>]*data-zhero-img>', разметка)
    итог["slides"] = len(ид)
    итог["unique_ids"] = len(set(ид))
    итог["unique_titles"] = len(set(названия))
    итог["unique_images"] = len(set(картинки))
    if len(ид) < 2:
        беды.append(f"в героe {len(ид)} слайд(ов) — это картинка, а не слайдер")
    else:
        if len(set(ид)) != len(ид):
            беды.append("повторяющиеся идентификаторы слайдов")
        if len(set(картинки)) != len(картинки):
            беды.append("одна картинка размножена по слайдам")
        if any(not т for т in названия):
            беды.append("слайд без названия")

    m = re.search(r'data-build-id="([^"]*)"', дом)
    итог["served_build"] = m.group(1) if m else None
    if итог["served_build"] != манифест.get("build_id"):
        беды.append(f"витрина объявляет сборку {итог['served_build']!r}, "
                    f"манифест — {манифест.get('build_id')!r}")

    m = re.search(r'<meta name="robots" content="([^"]*)"', дом)
    итог["robots"] = m.group(1) if m else None
    ожидание = манифест.get("expected_indexability", "noindex,nofollow").replace(" ", "")
    if (итог["robots"] or "").replace(" ", "") != ожидание:
        беды.append(f"индексация изменилась: {итог['robots']!r}")

    адреса = []
    for href in re.findall(r'<a\b[^>]*href="(/title/[^"#?]+)"', разметка):
        if href not in адреса:
            адреса.append(href)
    проверено, плохие = 0, []
    for путь in адреса[:а.titles]:
        с, _ = взять(а.domain, а.port, путь)
        проверено += 1
        if с != 200:
            плохие.append({"url": путь, "status": с})
    итог["title_pages_checked"] = проверено
    итог["title_pages_bad"] = плохие
    if плохие:
        беды.append(f"страниц произведений с ошибкой: {len(плохие)} из {проверено}")
    if проверено == 0:
        беды.append("на главной нет ни одной ссылки на произведение")

    с404, _ = взять(а.domain, а.port, "/takogo-adresa-tochno-net-9f3a/")
    итог["missing_status"] = с404
    if с404 != 404:
        беды.append(f"несуществующий адрес отдал {с404}, а не 404")

    итог["verdict"] = "PASS" if not беды else "FAIL"
    итог["issues"] = беды
    if беды:
        итог["rollback"] = (
            f"cp {манифест.get('rollback_target_file')} {артефакт} && "
            f"sudo systemctl restart nova-{а.site}.service")
    if а.out:
        Path(а.out).write_text(json.dumps(итог, ensure_ascii=False, indent=1),
                               encoding="utf-8")
    print(json.dumps(итог, ensure_ascii=False, indent=1))
    return 0 if итог["verdict"] == "PASS" else 2


if __name__ == "__main__":
    sys.exit(main())
