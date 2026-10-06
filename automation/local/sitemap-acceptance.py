#!/usr/bin/env python3
"""Приёмка карты сайта на ПУБЛИЧНОМ домене. Только чтение.

То же, что проверяет `checks/sitemap_wired.py` на стенде, но на живом домене и
по HTTPS: карта отдаётся, XML разбирается, части существуют, адреса ведут на
свой домен, дублей нет, выбранные адреса отвечают 200 и их `canonical`
совпадает с `loc` в карте, `robots.txt` называет карту и названный адрес
доступен, а публичный build-id совпадает с установленным выпуском.

    python3 automation/local/sitemap-acceptance.py <домен> [<домен> …]
"""
from __future__ import annotations

import json
import pathlib
import random
import re
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ET

SM = "{http://www.sitemaps.org/schemas/sitemap/0.9}"
УЧЁТКИ = pathlib.Path("/srv")


def достать(url: str, таймаут: int = 60) -> tuple[str, str, dict[str, str]]:
    """Код последнего ответа, тело и его заголовки.

    Заголовки пишутся в ОТДЕЛЬНЫЙ файл, а не в поток вывода вместе с телом.
    Разбор смешанного потока по пустой строке неверен: `\\r\\n\\r\\n`
    встречается и внутри HTML, и тогда за блок заголовков принимается кусок
    тела — кода ответа в нём нет, и исправная страница читается как «код
    пустой». Измерено на 1lordserials1.online: семь адресов из семи
    отвечали 200, а приёмка называла их провалом.
    """
    with tempfile.NamedTemporaryFile(prefix="curl-head-", suffix=".txt") as голова_ф:
        г = subprocess.run(
            ["curl", "-sS", "-L", "--max-time", str(таймаут), "-D", голова_ф.name, url],
            capture_output=True, text=True)
        голова = pathlib.Path(голова_ф.name).read_text(encoding="utf-8", errors="replace")
    тело = г.stdout or ""
    код, заг = "", {}
    # С переходами блоков заголовков несколько: берётся ПОСЛЕДНИЙ — он описывает
    # тот ответ, тело которого пришло.
    блоки = re.split(r"(?m)^(?=HTTP/)", голова)
    for с in (блоки[-1] if блоки else голова).splitlines():
        if с.lower().startswith("http/"):
            ч = с.split()
            код = ч[1] if len(ч) > 1 else ""
        elif ":" in с:
            к, _, з = с.partition(":")
            заг.setdefault(к.strip().lower(), з.strip())
    return код, тело, заг


def установленный_релиз(домен: str) -> tuple[str, str]:
    """Что ОБЪЯВЛЯЕТ установленное дерево: `(значение, вид раскладки)`.

    Раскладок у сети две, и обе действующие:

    * `releases/<build>` + симлинк `current` — тогда объявленное лежит в
      `current/release-manifest.json: release`, и публичный заголовок с него
      НАЧИНАЕТСЯ (к нему приписан site_id);
    * дерево `app/` без выпусков — так живут две ячейки AnimeGo. Объявленное
      лежит в `app/config/template-manifest.json: build_id`, и публичный
      заголовок равен ему ЦЕЛИКОМ.

    Прежде проверка знала только первую и на ячейках `app/` отвечала «при релизе
    —», то есть объявляла расхождением собственную неосведомлённость. Измерено
    2026-10-06 на an1mego.site и animeg0.site: заголовок совпадал с манифестом
    выложенного дерева, а приёмка называла это отклонением.
    """
    for к in sorted(УЧЁТКИ.glob("*/current")):
        конфиг = к / "config" / "site.json"
        try:
            если = json.loads(конфиг.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if если.get("domain") != домен:
            continue
        try:
            м = json.loads((к / "release-manifest.json").read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return "", "releases"
        return str(м.get("release") or ""), "releases"
    for к in sorted(УЧЁТКИ.glob("*/app")):
        конфиг = к / "config" / "site.json"
        try:
            если = json.loads(конфиг.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if если.get("domain") != домен:
            continue
        try:
            м = json.loads((к / "config" / "template-manifest.json").read_text(
                encoding="utf-8"))
        except (OSError, ValueError):
            return "", "app"
        return str(м.get("build_id") or ""), "app"
    return "", ""


def проверить(домен: str) -> list[str]:
    беды: list[str] = []

    def шаг(имя: str, ок: bool, подробно: str = "") -> None:
        print(("  PASS  " if ок else "  FAIL  ") + имя + (f"   [{подробно}]" if подробно else ""),
              flush=True)
        if not ок:
            беды.append(имя)

    код, тело, заг = достать(f"https://{домен}/sitemap.xml")
    шаг("/sitemap.xml -> 200", код == "200", f"код {код}")
    if код != "200":
        return беды
    билд = заг.get("x-site-factory-build-id", "")
    объявлено, вид = установленный_релиз(домен)
    совпало = bool(объявлено) and (билд == объявлено if вид == "app"
                                   else билд.startswith(объявлено))
    шаг("build-id совпадает с установленным",
        совпало,
        f"{билд or '—'} при объявленном {объявлено or '—'} "
        f"(раскладка {вид or 'не определена'})")
    try:
        корень = ET.fromstring(тело.encode("utf-8"))
    except ET.ParseError as ош:
        шаг("XML разбирается", False, str(ош))
        return беды
    шаг("XML разбирается", True, корень.tag.replace(SM, ""))
    шаг("это индекс карт", корень.tag == f"{SM}sitemapindex", корень.tag)
    части = [э.findtext(f"{SM}loc") or "" for э in корень.findall(f"{SM}sitemap")]
    шаг("индекс называет части", bool(части), f"{len(части)}")
    шаг("части на своём домене",
        all(ч.startswith(f"https://{домен}/") for ч in части), str(части[:2]))

    адреса: list[str] = []
    для_даты = 0
    for ч in части:
        к2, т2, _ = достать(ч)
        шаг(f"часть {ч.rsplit('/', 1)[-1]} -> 200", к2 == "200", f"код {к2}")
        if к2 != "200":
            continue
        try:
            к_часть = ET.fromstring(т2.encode("utf-8"))
        except ET.ParseError as ош:
            шаг(f"часть {ч.rsplit('/', 1)[-1]} разбирается", False, str(ош))
            continue
        шаг(f"часть {ч.rsplit('/', 1)[-1]} — urlset",
            к_часть.tag == f"{SM}urlset", к_часть.tag)
        for у in к_часть.findall(f"{SM}url"):
            адреса.append(у.findtext(f"{SM}loc") or "")
            если_дата = у.findtext(f"{SM}lastmod")
            для_даты += int(bool(если_дата))

    шаг("адресов больше одного", len(адреса) > 1, str(len(адреса)))
    шаг("дублей нет", len(адреса) == len(set(адреса)),
        f"{len(адреса)} против {len(set(адреса))}")
    чужие = [а for а in адреса if not а.startswith(f"https://{домен}/")]
    шаг("чужих домен нет", not чужие, str(чужие[:3]))
    СЛУЖЕБНЫЕ = ("/poster/", "/api/", "/healthz", "/__", "/robots.txt", "/sitemap",
                 "/search", "/event/", "/community/")
    служебные = [а for а in адреса if any(с in а for с in СЛУЖЕБНЫЕ)]
    шаг("служебных путей нет", not служебные, str(служебные[:3]))
    шаг("lastmod у части адресов", 0 < для_даты <= len(адреса),
        f"{для_даты} из {len(адреса)}")

    к3, т3, _ = достать(f"https://{домен}/robots.txt")
    строка = f"Sitemap: https://{домен}/sitemap.xml"
    шаг("robots.txt называет карту", строка in т3, repr(т3[:200]))

    # Выборка: главная, первый и последний адрес, плюс пять случайных.
    random.seed(len(адреса))
    выборка = [а for а in (адреса[0], адреса[-1]) if а]
    выборка += random.sample(адреса, min(5, len(адреса)))
    for адрес in dict.fromkeys(выборка):
        к4, т4, _ = достать(адрес)
        путь = адрес[len(f"https://{домен}"):] or "/"
        шаг(f"{путь[:44]} -> 200", к4 == "200", f"код {к4}")
        if к4 != "200":
            continue
        м = re.search(r'<link[^>]+rel="canonical"[^>]+href="([^"]+)"', т4)
        шаг(f"canonical == loc {путь[:36]}",
            bool(м) and м.group(1) == адрес,
            (м.group(1) if м else "canonical отсутствует"))
    return беды


def главная(argv: list[str]) -> int:
    домены = argv[1:]
    if not домены:
        print(__doc__)
        return 2
    плохих = 0
    for домен in домены:
        print(f"\n=== {домен}", flush=True)
        беды = проверить(домен)
        if беды:
            плохих += 1
            print(f"   ИТОГ: расхождений {len(беды)}: {', '.join(беды[:4])}")
        else:
            print("   ИТОГ: карта принята")
    print(f"\nдоменов {len(домены)}, с расхождениями {плохих}")
    return 1 if плохих else 0


if __name__ == "__main__":
    raise SystemExit(главная(sys.argv))
