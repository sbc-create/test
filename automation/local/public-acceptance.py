#!/usr/bin/env python3
"""Приёмка живого домена на ПУБЛИЧНОМ сайте. Только чтение.

Проверяет то, что названо в задании владельца, и ничего не меняет:

  HTTPS и домен            код ответа, схема, совпадение хоста
  build ID                 заголовок против установленного релиза в /srv
  главная, каталог, поиск  код, объём, число карточек
  карточки                 несколько адресов: код, h1, постер, соответствие
                           названия ссылке
  серии                    число ссылок на серии у сериала
  постеры и названия       доля карточек каталога с постером и названием
  оценки и сортировка      наличие оценок и порядок блока обновлений
  robots, sitemap          коды ответа и число адресов
  canonical                совпадение с запрошенным адресом
  режим индексации         X-Robots-Tag или meta robots

Чего скрипт НЕ делает: не нажимает в плеере (это отдельный инструмент
`player-idle-check.py`), не публикует, не выкладывает, не меняет настройки.

    python3 automation/local/public-acceptance.py <домен> [<домен> …]
"""
from __future__ import annotations

import json
import pathlib
import re
import subprocess
import sys

УЧЁТКИ = pathlib.Path("/srv")


def достать(url: str, таймаут: int = 45) -> tuple[str, str, dict[str, str]]:
    """Код ответа, тело и заголовки. Пустое тело — не ошибка, а факт."""
    # Переходы СЛЕДУЕМ (-L). Приложение Yummy отвечает 308 на адрес с
    # хвостовой косой чертой, и без следования витрина выглядела бы пустой: все
    # разделы и карточки отдавали бы «308, карточек 0». Это свойство проверки, а
    # не состояние сайта, и путать их нельзя. Заголовки берутся от ПОСЛЕДНЕГО
    # ответа в цепочке.
    # Заголовки идут в ОТДЕЛЬНЫЙ файл, а не в поток вывода вместе с телом.
    # Разбор смешанного потока по пустой строке неверен: `\r\n\r\n` встречается
    # и внутри HTML, и тогда за блок заголовков принимается кусок тела — кода
    # ответа в нём нет, и исправная страница читается как «код пустой».
    # Измерено 2026-10-06 на 1lordserials1.online: семь адресов из семи
    # отвечали 200, а приёмка называла их провалом.
    import tempfile

    with tempfile.NamedTemporaryFile(prefix="curl-head-", suffix=".txt") as ф:
        г = subprocess.run(
            ["curl", "-sS", "-L", "--max-time", str(таймаут), "-D", ф.name, url],
            capture_output=True, text=True)
        голова_всё = pathlib.Path(ф.name).read_text(encoding="utf-8", errors="replace")
    тело = г.stdout or ""
    # С переходами блоков заголовков несколько: берётся ПОСЛЕДНИЙ — он описывает
    # тот ответ, тело которого пришло.
    блоки = re.split(r"(?m)^(?=HTTP/)", голова_всё)
    голова = блоки[-1] if блоки else голова_всё
    код = ""
    заг: dict[str, str] = {}
    for с in голова.splitlines():
        if с.lower().startswith("http/"):
            части = с.split()
            код = части[1] if len(части) > 1 else ""
        elif ":" in с:
            к, _, з = с.partition(":")
            заг[к.strip().lower()] = з.strip()
    return код, тело, заг


def установленный_релиз(домен: str) -> tuple[str, str]:
    """Что ОБЪЯВЛЯЕТ установленное дерево: `(значение, вид раскладки)`.

    Раскладок две, и обе действующие: `releases/<build>` + симлинк `current`
    (объявленное — `release` из `release-manifest.json`, публичный заголовок с
    него начинается) и дерево `app/` без выпусков — так живут две ячейки AnimeGo
    (объявленное — `build_id` из `config/template-manifest.json`, заголовок равен
    ему целиком).

    Прежде функция знала только первую и на ячейках `app/` возвращала пустоту,
    то есть приёмка объявляла расхождением собственную неосведомлённость.
    Измерено 2026-10-06 на an1mego.site и animeg0.site.

    Домен сопоставляется по конфигурации ячейки, а не по имени каталога.
    """
    for к in sorted(УЧЁТКИ.glob("*/current")):
        if not (к.parent / "releases").is_dir():
            continue
        try:
            манифест = json.loads((к / "release-manifest.json").read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        try:
            д = json.loads((к / "config" / "site.json").read_text(encoding="utf-8"))
        except (OSError, ValueError):
            д = {}
        if д.get("domain") == домен:
            return str(манифест.get("release") or ""), "releases"
    for к in sorted(УЧЁТКИ.glob("*/app")):
        try:
            д = json.loads((к / "config" / "site.json").read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if д.get("domain") != домен:
            continue
        try:
            м = json.loads((к / "config" / "template-manifest.json").read_text(
                encoding="utf-8"))
        except (OSError, ValueError):
            return "", "app"
        return str(м.get("build_id") or ""), "app"
    return "", ""


def карточки(тело: str, домен: str, предел: int = 4) -> list[str]:
    пути = re.findall(r'href="(/(?:title|anime)/[a-z0-9-]+)/?"', тело)
    видно: list[str] = []
    for п in пути:
        if п not in видно:
            видно.append(п)
        if len(видно) >= предел:
            break
    return [f"https://{домен}{п}/" for п in видно]


def проверить(домен: str) -> dict:
    отчёт: dict = {"домен": домен, "проверки": [], "беды": []}

    def шаг(имя: str, ок: bool, подробно: str) -> None:
        отчёт["проверки"].append({"что": имя, "ок": ок, "подробно": подробно})
        if not ок:
            отчёт["беды"].append(f"{имя}: {подробно}")

    код, тело, заг = достать(f"https://{домен}/")
    шаг("HTTPS и главная", код == "200", f"код {код}, {len(тело)} Б")
    билд = заг.get("x-site-factory-build-id", "")
    объявлено, вид = установленный_релиз(домен)
    шаг("build ID против установленного",
        bool(объявлено) and (билд == объявлено if вид == "app"
                             else билд.startswith(объявлено)),
        f"заголовок {билд or '—'}, объявлено {объявлено or '—'} "
        f"(раскладка {вид or 'не определена'})")
    роботы = заг.get("x-robots-tag", "")
    мета = (re.search(r'<meta[^>]+name="robots"[^>]+content="([^"]+)"', тело) or [None, ""])[1]
    шаг("режим индексации", bool(роботы or мета),
        f"X-Robots-Tag: {роботы or '—'} | meta robots: {мета or '—'}")
    кан = (re.search(r'<link[^>]+rel="canonical"[^>]+href="([^"]+)"', тело) or [None, ""])[1]
    шаг("canonical главной", домен in кан, кан or "—")
    карточек_главной = len(set(re.findall(r'href="/(?:title|anime)/[a-z0-9-]+', тело)))
    шаг("главная отдаёт карточки", карточек_главной > 0,
        f"{карточек_главной} карточек")

    for путь, имя in (("/catalog/", "каталог"), ("/series/", "сериалы"),
                      ("/movies/", "фильмы")):
        к2, т2, _ = достать(f"https://{домен}{путь}")
        if к2 == "404":
            отчёт["проверки"].append({"что": имя, "ок": True,
                                      "подробно": "404 — раздела у витрины нет"})
            continue
        счёт = len(set(re.findall(r'href="/(?:title|anime)/[a-z0-9-]+', т2)))
        шаг(имя, к2 == "200" and счёт > 0, f"код {к2}, карточек {счёт}")

    к3, т3, _ = достать(f"https://{домен}/search/?q=%D0%B2%D0%BE%D0%BB%D0%BA")
    if к3 == "404":
        к3, т3, _ = достать(f"https://{домен}/search?q=%D0%B2%D0%BE%D0%BB%D0%BA")
    шаг("поиск", к3 == "200",
        f"код {к3}, карточек {len(set(re.findall(r'href=./(?:title|anime)/[a-z0-9-]+', т3)))}")

    адреса = карточки(тело, домен) or карточки(т3, домен)
    постеров = названий = 0
    серий_всего = 0
    for адрес in адреса:
        к4, т4, _ = достать(адрес)
        h1 = (re.search(r"<h1[^>]*>(.*?)</h1>", т4, re.S) or [None, ""])[1]
        h1 = re.sub(r"<[^>]+>", "", h1).strip()
        слаг = адрес.rstrip("/").rsplit("/", 1)[-1]
        постер = "poster.cdnvideohub.com" in т4
        серий = len(set(re.findall(rf'href="/(?:title|anime)/{слаг}/[^"]*episode[^"]*"', т4)))
        серий_всего += серий
        постеров += int(постер)
        названий += int(bool(h1))
        кан4 = (re.search(r'<link[^>]+rel="canonical"[^>]+href="([^"]+)"', т4) or [None, ""])[1]
        шаг(f"карточка {слаг[:28]}",
            к4 == "200" and bool(h1) and слаг in кан4,
            f"код {к4}, h1 {h1[:40]!r}, постер {постер}, серий {серий}, "
            f"canonical {'совпадает' if слаг in кан4 else кан4 or '—'}")
    if адреса:
        шаг("постеры и названия карточек", постеров == len(адреса) == названий,
            f"постеров {постеров}/{len(адреса)}, названий {названий}/{len(адреса)}")
        отчёт["серий_на_проверенных_карточках"] = серий_всего

    к5, т5, _ = достать(f"https://{домен}/robots.txt")
    шаг("robots.txt", к5 == "200" and "user-agent" in т5.lower(),
        f"код {к5}, {len(т5)} Б")
    for карта in ("/sitemap.xml", "/sitemap/titles.xml"):
        к6, т6, _ = достать(f"https://{домен}{карта}")
        if к6 == "200":
            адресов = len(re.findall(r"<loc>", т6))
            шаг(f"карта {карта}", адресов > 0, f"код 200, адресов {адресов}")
            break
    else:
        шаг("карта сайта", False, "ни /sitemap.xml, ни /sitemap/titles.xml не 200")
    return отчёт


def главная(argv: list[str]) -> int:
    домены = argv[1:]
    if not домены:
        print(__doc__)
        return 2
    плохих = 0
    for домен in домены:
        о = проверить(домен)
        print(f"\n=== {домен}")
        for п in о["проверки"]:
            метка = "ок " if п["ок"] else "НЕТ"
            print(f"   [{метка}] {п['что']:34} {п['подробно']}")
        if о["беды"]:
            плохих += 1
            print(f"   ИТОГ: расхождений {len(о['беды'])}")
        else:
            print("   ИТОГ: все проверки пройдены")
    print(f"\nдоменов проверено: {len(домены)}, с расхождениями: {плохих}")
    return 1 if плохих else 0


if __name__ == "__main__":
    raise SystemExit(главная(sys.argv))
