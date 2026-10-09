#!/usr/bin/env python3
"""Внеочередная проверка доступности сети: содержимое страниц, а не код 200.

Для каждого домена реестра, который разрешается в наш адрес, проверяются
четыре вещи и каждая — ПО СОДЕРЖИМОМУ:

* главная — отвечает, несёт ссылки на карточки и объявляет сборку;
* карточка произведения — `h1`, постер, `canonical` равен запрошенному;
* страница серии — отвечает и несёт оболочку плеера;
* плеер — в разметке есть скрипт провайдера и непустой `publisher-id`.

Код 200 сам по себе ничего не доказывает: главная отвечает 200 и на пустом
каталоге, а страница серии — и без плеера. Поэтому каждая проверка называет
измеренное значение, а не «ок».

Слаги берутся ИЗ КАТАЛОГА САМОГО САЙТА (sitemap), а не задаются списком:
список разошёлся бы с каталогом и проверял бы несуществующие страницы.

Запуск: python3 automation/local/availability-sweep.py [домен …] [--json]
"""
from __future__ import annotations

import json
import pathlib
import re
import socket
import sys
import urllib.error
import urllib.request

КОРЕНЬ = pathlib.Path(__file__).resolve().parents[2]
ЗАГОЛОВКИ = {"User-Agent": "site-factory-availability/1.0"}
#: Карты витрин Yummy отдают по 8 000 адресов одной частью, и на 30 секундах
#: чтение обрывалось: проход сообщал «карта не дала адресов карточек» там, где
#: карта исправна (измерено 2026-10-09 на yummyani.org, .site и yummyani7.*).
#: Ложная находка инструмента хуже отсутствия находки: по ней ищут поломку,
#: которой нет.
ТАЙМАУТ = 90
НАШ_АДРЕС = "45.131.182.225"


def адреса(домен: str) -> list[str]:
    try:
        return sorted({с[4][0] for с in socket.getaddrinfo(домен, None)})
    except OSError as ош:
        return [f"DNS: {ош.strerror or ош}"]


def забрать(адрес: str) -> tuple[object, str]:
    try:
        with urllib.request.urlopen(
                urllib.request.Request(адрес, headers=ЗАГОЛОВКИ),
                timeout=ТАЙМАУТ) as о:
            return о.status, о.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as ош:
        return ош.code, ""
    except Exception as ош:  # noqa: BLE001
        return type(ош).__name__, ""


def домены_реестра() -> dict[str, str]:
    д = json.loads((КОРЕНЬ / "config" / "site-cells.json").read_text(encoding="utf-8"))
    итог = {}
    for c in д.get("cells") or []:
        домен = c.get("domain")
        if домен:
            итог[домен] = c.get("site_id") or ""
    return итог


def слаги_из_карты(домен: str, сколько: int = 2) -> list[str]:
    """Адреса карточек из карты сайта. Пусто — карта не отдалась."""
    код, т = забрать(f"https://{домен}/sitemap.xml")
    if not т:
        return []
    части = re.findall(r"<loc>([^<]+)</loc>", т)
    адреса_карточек: list[str] = []
    for ч in части[:6]:
        к, т2 = забрать(ч)
        if not т2:
            continue
        for а in re.findall(r"<loc>([^<]+)</loc>", т2):
            if re.search(r"/(title|anime)/[^/]+/?$", а):
                адреса_карточек.append(а)
            if len(адреса_карточек) >= сколько:
                return адреса_карточек
    return адреса_карточек


def проверить(домен: str) -> dict:
    итог: dict[str, object] = {"домен": домен, "адреса": адреса(домен)}
    итог["наш_адрес"] = НАШ_АДРЕС in итог["адреса"]
    if not итог["наш_адрес"]:
        итог["вывод"] = "не наш адрес или нет DNS: со стороны фабрики не обслуживается"
        return итог

    код, главная = забрать(f"https://{домен}/")
    итог["главная_код"] = код
    итог["главная_карточек"] = len(set(re.findall(r'href="(/(?:title|anime)/[^"]+)"', главная)))
    сборка = re.search(r'data-build-id="([^"]+)"', главная)
    итог["главная_сборка"] = сборка.group(1) if сборка else ""
    мета = re.search(
        r'<meta[^>]+name=["\']robots["\'][^>]+content=["\']([^"\']*)["\']', главная, re.I)
    итог["индексация"] = мета.group(1) if мета else ""

    карточки = слаги_из_карты(домен)
    итог["карточка_адрес"] = карточки[0] if карточки else ""
    if карточки:
        код2, стр = забрать(карточки[0])
        итог["карточка_код"] = код2
        h1 = re.search(r"<h1[^>]*>(.*?)</h1>", стр, re.S)
        итог["карточка_h1"] = (re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "", h1.group(1))).strip()[:48]
                               if h1 else "")
        канон = re.search(r'<link[^>]+rel="canonical"[^>]+href="([^"]+)"', стр)
        итог["карточка_canonical_свой"] = bool(
            канон and канон.group(1).rstrip("/") == карточки[0].rstrip("/"))
        итог["карточка_постер"] = bool(re.search(r'<img[^>]+(data-poster|class="[^"]*__img)', стр))
        серии = re.findall(r'href="([^"]*/(?:season|episode)[^"]*)"', стр)
        итог["серий_в_разметке"] = len(set(серии))
        итог["плеер_скрипт"] = "player.cdnvideohub.com" in стр
        изд = re.search(r'data-publisher-id="([^"]*)"', стр)
        итог["publisher_id"] = изд.group(1) if изд else ""
        if серии:
            адрес_серии = серии[0]
            if адрес_серии.startswith("/"):
                адрес_серии = f"https://{домен}{адрес_серии}"
            код3, стр3 = забрать(адрес_серии)
            итог["серия_адрес"] = адрес_серии
            итог["серия_код"] = код3
            итог["серия_плеер"] = "player.cdnvideohub.com" in стр3
            изд3 = re.search(r'data-publisher-id="([^"]*)"', стр3)
            итог["серия_publisher_id"] = изд3.group(1) if изд3 else ""
    беды = []
    if итог.get("главная_код") != 200:
        беды.append(f"главная {итог.get('главная_код')}")
    elif not итог.get("главная_карточек"):
        беды.append("главная без карточек")
    if not карточки:
        беды.append("карта не дала адресов карточек")
    else:
        if итог.get("карточка_код") != 200:
            беды.append(f"карточка {итог.get('карточка_код')}")
        if not итог.get("карточка_h1"):
            беды.append("карточка без h1")
        if not итог.get("карточка_canonical_свой"):
            беды.append("canonical карточки не свой")
        if not итог.get("плеер_скрипт"):
            беды.append("нет скрипта плеера")
        if not итог.get("publisher_id"):
            беды.append("пустой publisher-id")
        if "серия_код" in итог and итог["серия_код"] != 200:
            беды.append(f"серия {итог['серия_код']}")
        if итог.get("серия_код") == 200 and not итог.get("серия_плеер"):
            беды.append("серия без плеера")
    итог["беды"] = беды
    итог["вывод"] = "исправно" if not беды else "; ".join(беды)
    return итог


def main() -> int:
    арг = [а for а in sys.argv[1:] if not а.startswith("--")]
    домены = арг or list(домены_реестра())
    строки = [проверить(д) for д in домены]
    if "--json" in sys.argv:
        print(json.dumps(строки, ensure_ascii=False, indent=1))
        return 0
    for с in строки:
        print(f"=== {с['домен']} ({', '.join(str(а) for а in с['адреса'])})")
        if not с.get("наш_адрес"):
            print(f"    {с['вывод']}")
            continue
        print(f"    главная  HTTP {с.get('главная_код')} | карточек "
              f"{с.get('главная_карточек')} | сборка {с.get('главная_сборка') or '—'} "
              f"| robots {с.get('индексация') or '—'}")
        print(f"    карточка HTTP {с.get('карточка_код', '—')} | h1 "
              f"{с.get('карточка_h1') or '—'!r} | canonical свой "
              f"{с.get('карточка_canonical_свой')} | постер {с.get('карточка_постер')}")
        print(f"    плеер    скрипт {с.get('плеер_скрипт')} | publisher-id "
              f"{с.get('publisher_id') or '—'!r}")
        print(f"    серия    {с.get('серия_адрес', '—')} HTTP "
              f"{с.get('серия_код', '—')} | плеер {с.get('серия_плеер', '—')}")
        print(f"    ВЫВОД: {с['вывод']}")
    плохих = [с for с in строки if с.get("наш_адрес") and с.get("беды")]
    чужих = [с for с in строки if not с.get("наш_адрес")]
    print(f"\nдомен проверено {len(строки)}; с замечаниями {len(плохих)}; "
          f"не наших или без DNS {len(чужих)}")
    return 1 if плохих else 0


if __name__ == "__main__":
    raise SystemExit(main())
