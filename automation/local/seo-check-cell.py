#!/usr/bin/env python3
"""SEO и выдача каталога на стенде — с настоящим заголовком Host.

Почему Host обязателен. Рантайм строит canonical из заголовка Host: обращение к
стенду по адресу `127.0.0.1` даёт `https://127.0.0.1/...`, и это НЕ дефект
витрины, а условие измерения. Первая версия осмотра записала такой canonical
витрине в ошибки — здесь это исправлено: страницы запрашиваются с доменом
витрины в Host, как их увидит посетитель.

Что проверяется:
  * title, description, canonical, h1 на главной, в каталоге, на карточке;
  * сортировка каталога МЕНЯЕТ порядок (сравниваются первые слуги);
  * у сериального профиля на карточке сериала есть сезоны и серии;
  * режим индексации: X-Robots-Tag на каждой странице.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import signal
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
from pathlib import Path

КОРЕНЬ = Path(__file__).resolve().parents[2]


def окружение(конфиг: dict, проект: Path, данные: Path) -> dict:
    env = dict(os.environ)
    for имя, шаблон in (конфиг.get("environment") or {}).items():
        env[имя] = (str(шаблон).replace("<data>", str(данные))
                    .replace("<app>", str(проект)))
    env["SITE_CONTACT_EMAIL"] = str(конфиг.get("contact_email") or "")
    env["LORDS_INDEXING_SITE"] = str(конфиг.get("domain") or "")
    env["LORDS_INDEXING_RELEASE_PERMITS_OPEN"] = "false"
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    return env


def запрос(база: str, путь: str, домен: str, таймаут: float = 30.0):
    req = urllib.request.Request(база + путь, headers={"Host": домен})
    try:
        с = urllib.request.urlopen(req, timeout=таймаут)
        return с.status, с.read().decode("utf-8", "replace"), dict(с.headers)
    except urllib.error.HTTPError as ош:
        return ош.code, ош.read().decode("utf-8", "replace"), dict(ош.headers)


def мета(html_: str) -> dict:
    def найти(образец: str) -> str:
        м = re.search(образец, html_, re.S | re.I)
        return (м.group(1).strip() if м else "")[:200]

    return {
        "title": найти(r"<title[^>]*>(.*?)</title>"),
        "description": найти(r'<meta[^>]+name="description"[^>]+content="([^"]*)"'),
        "canonical": найти(r'<link[^>]+rel="canonical"[^>]+href="([^"]*)"'),
        "h1": re.sub(r"<[^>]+>", "", найти(r"<h1[^>]*>(.*?)</h1>")),
        "ссылок внутренних": len(re.findall(r'href="/', html_)),
    }


def main() -> int:
    р = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    р.add_argument("--site", required=True)
    р.add_argument("--data", required=True)
    р.add_argument("--port", type=int, default=19500)
    а = р.parse_args()

    проект = КОРЕНЬ / "var" / "new-sites" / а.site
    конфиг = json.loads((проект / "config" / "site.json").read_text(encoding="utf-8"))
    домен = str(конфиг.get("domain"))
    врем = Path(tempfile.mkdtemp(prefix=f"seo-{а.site}-"))
    данные = врем / "data"
    данные.mkdir()
    for ф in Path(а.data).glob(f"{а.site}-*.json"):
        shutil.copy(ф, данные / ф.name)

    # Ручка живёт дольше любого блока намеренно: её получает Popen и
    # пишет в неё всё время работы витрины. Контекстный менеджер
    # закрыл бы журнал сразу после запуска, и в нём не осталось бы
    # ничего, кроме первых строк.
    журнал = open(врем / "runtime.log", "w", encoding="utf-8")  # noqa: SIM115
    проц = subprocess.Popen(
        [sys.executable, str(проект / "src" / конфиг["entrypoint"]),
         "--port", str(а.port)],
        cwd=проект, env=окружение(конфиг, проект, данные),
        stdout=журнал, stderr=журнал)
    база = f"http://127.0.0.1:{а.port}"
    готово = False
    for _ in range(60):
        try:
            urllib.request.urlopen(f"{база}/healthz", timeout=12)
            готово = True
            break
        except Exception:  # noqa: BLE001
            if проц.poll() is not None:
                break
            time.sleep(2)
    if not готово:
        журнал.flush()
        print("ОТКАЗ: стенд не поднялся")
        print((врем / "runtime.log").read_text(encoding="utf-8")[-1500:])
        проц.kill()
        return 1

    каталог = json.loads((данные / f"{а.site}-catalog.json").read_text(encoding="utf-8"))
    элементы = каталог.get("items") or []
    первый = элементы[0] if элементы else {}
    сериал = next((э for э in элементы
                   if str(э.get("kind", "")).lower() in ("сериал", "series", "tv")), None)

    итог: dict = {"site": а.site, "domain": домен, "страницы": {}}
    страницы = [("/", "главная"), ("/catalog/", "каталог"),
                (f"/title/{первый.get('slug', '')}/", "карточка")]
    if сериал:
        страницы.append((f"/title/{сериал.get('slug')}/", "карточка сериала"))
    for путь, имя in страницы:
        код, html_, заголовки = запрос(база, путь, домен)
        сведения = мета(html_)
        сведения["код"] = код
        сведения["x_robots"] = заголовки.get("X-Robots-Tag", "")
        if имя.startswith("карточка"):
            сведения["сезонов в разметке"] = len(re.findall(r"season", html_, re.I))
            сведения["серий в разметке"] = len(re.findall(r"episode", html_, re.I))
            сведения["состояние плеера"] = (
                "noaccess" if "Просмотр на сайте не подключён" in html_ else
                "nosource" if "Просмотр пока недоступен" in html_ else "playable")
        итог["страницы"][имя] = сведения

    # Сортировка: берём ссылки сортировки со страницы каталога и сравниваем
    # порядок слугов.
    _, html_каталога, _ = запрос(база, "/catalog/", домен)
    # Сортировка — это ФОРМА, а не ссылки. Прежний поиск `href="…sort=…"`
    # давал ноль и выглядел как провал витрины, хотя в разметке таких ссылок
    # нет вовсе: вариант выбирается в `<select name="sort">`, и форма GET
    # отправляет его в адрес. Поэтому варианты берутся из самого select, а
    # запрашивается тот адрес, который отправит форма.
    блок_sort = re.search(r'<select[^>]*name="sort"[^>]*>(.*?)</select>',
                          html_каталога, re.S)
    варианты = (re.findall(r'value="([^"]+)"', блок_sort.group(1))
                if блок_sort else [])
    базовый = re.findall(r'href="/title/([^/"]+)/', html_каталога)[:10]
    сортировки = [f"/catalog/?sort={в}" for в in варианты[:3]]
    итог["сортировка"] = {"ссылок": len(сортировки), "вариантов в форме": len(варианты),
                          "варианты": варианты, "проверено": []}
    for адрес in сортировки:
        _, html_с, _ = запрос(база, адрес.replace("&amp;", "&"), домен)
        порядок = re.findall(r'href="/title/([^/"]+)/', html_с)[:10]
        итог["сортировка"]["проверено"].append(
            {"адрес": адрес, "порядок отличается": порядок != базовый,
             "карточек": len(порядок)})

    проц.send_signal(signal.SIGTERM)
    try:
        проц.wait(timeout=15)
    except subprocess.TimeoutExpired:
        проц.kill()
    shutil.rmtree(врем, ignore_errors=True)

    выход = КОРЕНЬ / "var" / "k2-data" / "audit" / а.site
    выход.mkdir(parents=True, exist_ok=True)
    (выход / "seo.json").write_text(
        json.dumps(итог, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8")
    print(json.dumps(итог, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
