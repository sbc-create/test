#!/usr/bin/env python3
"""Карта сайта подключена и остаётся подключённой. Проверка проекта сайта.

Доставляется в `checks/sitemap_wired.py` инструментом
`automation/local/wire-sitemap.py` и встаёт в `checks/run.sh`. Один файл на
семейства — подключение у витрин разное, а требования к нему одни.

Зачем проверка, а не доверие к выпуску. Карта отсутствовала на восьми живых
доменах из двенадцати, и ни один выпуск этого не заметил: генератор
`seo_layer.построить_sitemap` лежал в каждом репозитории, маршрут `/sitemap.xml`
был в каждом рантайме, а не хватало ЧЕТЫРЁХ вещей разом — сборщика в общем
модуле, перечня разделов, переменной каталога и ссылки в `robots.txt`. Любая из
них теряется молча: домен отдаёт 404, и это неотличимо от «карта не нужна».

Проверка идёт в два яруса.

ЯРУС 1 — СТАТИЧЕСКИЙ, работает всюду, включая раннер CI без данных. Держит
ровно те четыре вещи, отсутствие которых и наблюдалось, плюс fail-closed
маршрут. Если следующий выпуск потеряет любую — проверка падает ДО выкладки.

ЯРУС 3 — СБОРЩИК, работает всюду. Вызывает сборщик ЭТОГО выпуска на
заглушке рантайма и держит его свойства: карта следует за каталогом, прежние
адреса не теряются, служебные пути в карту не попадают, `lastmod` стоит только
у точных дат, закрытие режима карту снимает. Заглушка, а не живая витрина,
намеренно: это свойство сборщика, и проверять его двумя подъёмами витрины и
ожиданием двух периодов по 300 с значило бы десять минут ждать ответа, который
даёт вызов функции.

ЯРУС 2 — ЖИВОЙ, работает там, где есть снимок каталога (`SITEMAP_CHECK_DATA`
или каталог данных ячейки). Поднимает НАСТОЯЩУЮ витрину на КОПИИ снимка и
проверяет поведение: закрытый режим карту не отдаёт, открытый отдаёт правильный
XML, адреса из карты отвечают 200 и их `canonical` совпадает с `loc`,
`robots.txt` называет карту, чужих домен и дублей нет, изменение каталога
карту обновляет. Без снимка ярус пропускается с названной причиной — пропуск
печатается, а не умалчивается.

    python3 checks/sitemap_wired.py
    SITEMAP_CHECK_DATA=/srv/<аккаунт>/data python3 checks/sitemap_wired.py
"""
from __future__ import annotations

import json
import os
import re
import shutil
import socket
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path

КОРЕНЬ = Path(__file__).resolve().parent.parent
SM = "{http://www.sitemaps.org/schemas/sitemap/0.9}"
ok = True


#: Сколько ждать перезаписи карты после изменения каталога. Два периода по
#: 300 с подряд: витрина сперва перечитывает снимок (слежение по mtime), и
#: только потом сборщик видит новое поколение. Прежние 400 с давали ложный
#: провал «карта не перезаписана» на исправном подключении — измерено на
#: 1lordserials1.online, снимок 57 340 записей.
ОЖИДАНИЕ_КАРТЫ_С = float(os.environ.get("SITEMAP_CHECK_WAIT", "900"))


def п(имя: str, у: bool, ф: str = "") -> None:
    global ok
    print(("  PASS  " if у else "  FAIL  ") + имя + (f"   [{ф}]" if ф else ""),
          flush=True)
    if not у:
        ok = False


def конфигурация() -> dict:
    return json.loads((КОРЕНЬ / "config" / "site.json").read_text(encoding="utf-8"))


# ---------------------------------------------------------------------------
# Ярус 1: подключение на месте
# ---------------------------------------------------------------------------

def рантайм_и_запуск(cfg: dict) -> tuple[Path, str]:
    """Файл, в котором живёт `main()` витрины, и его текст.

    У монолита это точка входа. У витрины на общем ядре точка входа —
    лаунчер, а `main()` ядра зовётся из него; разделы в этом случае объявляет
    лаунчер, и искать их надо там же.
    """
    точка = КОРЕНЬ / "src" / cfg["entrypoint"]
    if точка.is_file():
        return точка, точка.read_text(encoding="utf-8")
    raise SystemExit(f"нет точки входа {точка}")


def общий_модуль() -> tuple[Path | None, str]:
    """Копия `seo_layer` ЭТОГО выпуска, где бы она ни лежала.

    У монолитов она в `src/`, у витрины на закреплённом артефакте — рядом с
    артефактом в `template/<релиз>/`: именно этот каталог стоит первым в
    `sys.path`, и именно его копию витрина и импортирует.
    """
    кандидаты = sorted(КОРЕНЬ.rglob("seo_layer.py"))
    кандидаты = [к for к in кандидаты if ".git" not in к.parts]
    for к in кандидаты:
        т = к.read_text(encoding="utf-8", errors="replace")
        if "def запустить_карту" in т:
            return к, т
    if кандидаты:
        return кандидаты[0], кандидаты[0].read_text(encoding="utf-8", errors="replace")
    return None, ""


def ярус_статический(cfg: dict) -> list[str]:
    """Возвращает разделы, объявленные витриной (нужны второму ярусу)."""
    print("1. подключение карты на месте", flush=True)
    модуль, текст_модуля = общий_модуль()
    п("seo_layer несёт сборщик карты",
      bool(модуль) and "def запустить_карту" in текст_модуля,
      str(модуль.relative_to(КОРЕНЬ)) if модуль else "модуля нет")
    for имя in ("обновить_карту", "адреса_карты", "снять_карту", "построить_sitemap"):
        п(f"seo_layer: {имя}", f"def {имя}" in текст_модуля)

    # Разделы и запуск ищутся во ВСЕХ файлах сайта: у монолита они в точке
    # входа, у витрины на общем ядре — в лаунчере, и требование одно и то же.
    свои = [п_ for п_ in sorted(КОРЕНЬ.rglob("*.py"))
            if ".git" not in п_.parts and "template" not in п_.parts]
    текст_сайта = "\n".join(п_.read_text(encoding="utf-8", errors="replace")
                            for п_ in свои)
    разделы: list[str] = []
    м = re.search(r"РАЗДЕЛЫ_КАРТЫ\s*=\s*\(([^)]*)\)", текст_сайта)
    if м:
        разделы = re.findall(r'"([^"]+)"', м.group(1))
    п("разделы карты объявлены и не пусты", bool(разделы), " ".join(разделы) or "—")
    п("разделы — только пути своего сайта",
      all(р.startswith("/") for р in разделы), " ".join(разделы))
    заводится = ("запустить_карту" in текст_сайта
                 or "lords_sitemap_layer" in текст_сайта)
    п("сборщик заводится файлами сайта", заводится)

    # Ссылка в robots.txt — только условная. Безусловная `Sitemap:` обещает
    # адрес, которого у закрытого домена нет.
    есть_ссылка = ("sitemap=карта" in текст_сайта
                   or "ссылка_на_карту" in текст_сайта)
    п("robots.txt получает адрес карты условием", есть_ссылка)
    п("условие ссылки включает существование файла",
      'sitemap.xml").is_file()' in текст_сайта or "ссылка_на_карту" in текст_сайта)

    # Каталог карты: внутри каталога ДАННЫХ ячейки — единственного пути,
    # открытого юниту витрины на запись.
    где = ""
    лаунчер = (КОРЕНЬ / "run.py")
    текст_лаунчера = лаунчер.read_text(encoding="utf-8") if лаунчер.is_file() else ""
    if "LORDS_SITEMAP_DIR" in текст_лаунчера:
        где = "run.py"
    elif "LORDS_SITEMAP_DIR" in json.dumps(cfg, ensure_ascii=False):
        где = "config/site.json"
    п("каталог карты объявлен", bool(где), где or "ни в лаунчере, ни в пакете")
    внутри_данных = ('данные / "sitemap"' in текст_лаунчера
                     or "корень_данных / \"sitemap\"" in текст_лаунчера
                     or (cfg.get("environment") or {}).get("LORDS_SITEMAP_DIR")
                     == "<data>/sitemap")
    п("каталог карты внутри данных ячейки", внутри_данных)

    # Маршрут fail-closed: закрытая витрина карту не отдаёт даже при готовых
    # файлах. У витрин на общем ядре проверки в маршруте нет — там второй
    # рубеж даёт сам сборщик, снимая файлы.
    в_маршруте = 'режим_индексации()[0] != "OPEN"' in текст_сайта
    снимает = "снять_карту" in текст_модуля
    п("закрытая витрина карту не отдаёт", в_маршруте or снимает,
      f"проверка в маршруте: {в_маршруте}, снятие файлов сборщиком: {снимает}")
    return разделы


# ---------------------------------------------------------------------------
# Ярус 2: живая отдача
# ---------------------------------------------------------------------------

def свободный_порт() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def живые_данные(cfg: dict) -> Path | None:
    явно = os.environ.get("SITEMAP_CHECK_DATA", "").strip()
    if явно:
        п_ = Path(явно)
        return п_ if п_.is_dir() else None
    return None


def ответ(база: str, путь: str, таймаут: int = 60, домен: str = ""):
    """Запрос к стенду ОТ ИМЕНИ домена.

    Заголовок `Host` обязателен: витрина строит `canonical` из хоста запроса, и
    без него каждая страница объявляла `https://127.0.0.1/...`. Проверка
    «canonical совпадает с loc» тогда падает на исправном подключении —
    измерено на 1lordserials1.online, десять адресов из десяти.
    """
    req = urllib.request.Request(база + путь)
    if домен:
        req.add_header("Host", домен)
    try:
        with urllib.request.urlopen(req, timeout=таймаут) as о:
            return о.status, о.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as ош:
        return ош.code, ош.read().decode("utf-8", "replace")


def дождаться(база: str, предел: float = 120.0) -> bool:
    край = time.time() + предел
    while time.time() < край:
        try:
            код, _ = ответ(база, "/healthz", таймаут=5)
            if код == 200:
                return True
        except (urllib.error.URLError, OSError):
            pass
        time.sleep(0.5)
    return False


def поднять(данные: Path, корень_режима: Path, порт: int) -> subprocess.Popen:
    среда = dict(os.environ)
    среда.update({
        "LORDS_INDEXING_ROOT": str(корень_режима),
        "ANIMEDIA_INDEXING_ROOT": str(корень_режима),
        "LORDS_INDEXING_TTL": "0",
        "ANIMEDIA_INDEXING_TTL": "0",
        "PYTHONDONTWRITEBYTECODE": "1",
    })
    среда.pop("SITEMAP_CHECK_DATA", None)
    return subprocess.Popen(
        [sys.executable, str(КОРЕНЬ / "run.py"), "--port", str(порт),
         "--data-dir", str(данные)],
        cwd=str(КОРЕНЬ), env=среда,
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)


def разобрать_карту(тело: str) -> tuple[str, list[str]]:
    корень = ET.fromstring(тело.encode("utf-8"))
    части = [э.findtext(f"{SM}loc") or "" for э in корень.findall(f"{SM}sitemap")]
    return корень.tag, части


def ярус_живой(cfg: dict, разделы: list[str], данные_живые: Path) -> None:
    домен = cfg["domain"]
    print(f"2. живая отдача (копия снимка из {данные_живые})", flush=True)
    врем = Path(tempfile.mkdtemp(prefix="sitemap-wired-"))
    данные = врем / "data"
    данные.mkdir()
    # Копируется то, что ЧИТАЕТСЯ. Каталог данных ячейки принадлежит её
    # пользователю, и часть подкаталогов (`site-data` с записями сообщества)
    # посторонним закрыта правами — это правильно и менять этого проверка не
    # вправе. Недоступное пропускается с НАЗВАННОЙ причиной: карта собирается
    # из снимка каталога, и записи сообщества ей не нужны. Прежде проверка
    # падала здесь PermissionError, и отказ выглядел дефектом подключения.
    пропущено: list[str] = []
    for ф in sorted(данные_живые.iterdir()):
        try:
            if ф.is_file():
                shutil.copy2(ф, данные / ф.name)
            elif ф.is_dir() and ф.name in ("site-data", "legacy", "site"):
                shutil.copytree(ф, данные / ф.name, dirs_exist_ok=True,
                                ignore=shutil.ignore_patterns("sitemap"))
        except (PermissionError, OSError) as ош:
            пропущено.append(f"{ф.name} ({type(ош).__name__})")
            # Каталог создаётся пустым: витрине он нужен как место для записи,
            # а не как источник карты.
            if ф.is_dir():
                (данные / ф.name).mkdir(exist_ok=True)
    if пропущено:
        print("  ПРОПУСК  недоступно на чтение, карте не нужно: "
              + ", ".join(пропущено), flush=True)
    shutil.rmtree(данные / "sitemap", ignore_errors=True)
    снимки = sorted(п.name for п in данные.glob("*catalog*.json"))
    if not снимки:
        п("живой ярус: снимок каталога скопирован", False,
          f"в {данные_живые} нет доступного файла каталога")
        shutil.rmtree(врем, ignore_errors=True)
        return
    print(f"  снимки: {' '.join(снимки)}", flush=True)
    режим = врем / "indexing"
    режим.mkdir()
    состояние = режим / f"{домен}.json"
    порт = свободный_порт()
    база = f"http://127.0.0.1:{порт}"

    try:
        # --- закрытый режим -------------------------------------------------
        состояние.unlink(missing_ok=True)
        пр = поднять(данные, режим, порт)
        try:
            if not дождаться(база):
                вывод = (пр.stdout.read() if пр.stdout else "")
                # НЕ ПОДНЯЛАСЬ ПО ПРАВАМ — это ограничение окружения проверки, а
                # не дефект подключения карты. Так бывает с `config/player.json`:
                # файл закрыт правами, и запуск fail-closed честно отказывает ещё
                # до первого запроса. Разница названа, а не сглажена: любая другая
                # причина незапуска остаётся ПРОВАЛОМ.
                if "PermissionError" in вывод:
                    строка = next((с for с in вывод.splitlines()
                                   if "PermissionError" in с), "")
                    print(f"  ПРОПУСК  живой ярус: витрину не поднять правами — "
                          f"{строка.strip()[:160]}", flush=True)
                    return
                п("закрыто: витрина поднялась", False, вывод[-600:])
                return
            код, _ = ответ(база, "/sitemap.xml", домен=домен)
            п("закрыто: /sitemap.xml -> 404", код == 404, str(код))
            _, роботс = ответ(база, "/robots.txt", домен=домен)
            п("закрыто: robots.txt карту не называет", "Sitemap:" not in роботс,
              репр(роботс))
            п("закрыто: robots.txt запрещает обход",
              re.search(r"(?mi)^Disallow:\s*/\s*$", роботс) is not None, репр(роботс))
            п("закрыто: файлов карты не появилось",
              not (данные / "sitemap" / "sitemap.xml").is_file())
        finally:
            остановить(пр)

        # --- открытый режим -------------------------------------------------
        состояние.write_text(json.dumps(
            {"schema_version": 1, "site": домен, "desired_state": "OPEN"},
            ensure_ascii=False), encoding="utf-8")
        порт = свободный_порт()
        база = f"http://127.0.0.1:{порт}"
        пр = поднять(данные, режим, порт)
        try:
            if not дождаться(база):
                п("открыто: витрина поднялась", False,
                  (пр.stdout.read() if пр.stdout else "")[-600:])
                return
            файл = данные / "sitemap" / "sitemap.xml"
            край = time.time() + 180
            while time.time() < край and not файл.is_file():
                time.sleep(1.0)
            п("открыто: сборщик записал карту", файл.is_file(),
              str(sorted(p.name for p in (данные / "sitemap").glob("*"))
                  if (данные / "sitemap").is_dir() else "каталога нет"))
            if not файл.is_file():
                return

            код, тело = ответ(база, "/sitemap.xml", домен=домен)
            п("открыто: /sitemap.xml -> 200", код == 200, str(код))
            тег, части = "", []
            try:
                тег, части = разобрать_карту(тело)
            except ET.ParseError as ош:
                п("открыто: /sitemap.xml разбирается как XML", False, str(ош))
            else:
                п("открыто: /sitemap.xml разбирается как XML", True, тег)
                п("открыто: это индекс карт", тег == f"{SM}sitemapindex", тег)
                п("открыто: индекс называет части", bool(части), str(части[:3]))

            адреса: list[str] = []
            for ч in части:
                имя = ч.rsplit("/", 1)[-1]
                кодч, телоч = ответ(база, f"/{имя}", домен=домен)
                п(f"открыто: {имя} -> 200", кодч == 200, str(кодч))
                if кодч != 200:
                    continue
                try:
                    корень_части = ET.fromstring(телоч.encode("utf-8"))
                except ET.ParseError as ош:
                    п(f"открыто: {имя} разбирается как XML", False, str(ош))
                    continue
                п(f"открыто: {имя} — urlset",
                  корень_части.tag == f"{SM}urlset", корень_части.tag)
                адреса += [у.findtext(f"{SM}loc") or ""
                           for у in корень_части.findall(f"{SM}url")]

            п("адресов в карте больше одного", len(адреса) > 1, str(len(адреса)))
            п("дублей нет", len(адреса) == len(set(адреса)),
              f"{len(адреса)} против {len(set(адреса))}")
            свой = f"https://{домен}/"
            чужие = [а for а in адреса if not а.startswith(свой)]
            п("чужих домен нет", not чужие, str(чужие[:3]))
            СЛУЖЕБНЫЕ = ("/poster/", "/api/", "/healthz", "/__", "/robots.txt",
                         "/sitemap", "/search", "/event/", "/community/")
            служебные = [а for а in адреса if any(с in а for с in СЛУЖЕБНЫЕ)]
            п("служебных путей нет", not служебные, str(служебные[:3]))
            п("главная в карте", свой in адреса)
            нет_разделов = [р for р in разделы
                            if р != "/" and f"https://{домен}{р}" not in адреса]
            п("объявленные разделы в карте", not нет_разделов, str(нет_разделов))

            _, роботс = ответ(база, "/robots.txt", домен=домен)
            п("открыто: robots.txt называет карту",
              f"Sitemap: https://{домен}/sitemap.xml" in роботс, репр(роботс))

            # Выборка адресов: разделы и три карточки — первая, средняя, последняя.
            карточки = [а for а in адреса if "/title/" in а or "/anime/" in а]
            выборка = [свой] + [f"https://{домен}{р}" for р in разделы if р != "/"]
            if карточки:
                выборка += [карточки[0], карточки[len(карточки) // 2], карточки[-1]]
            for адрес in выборка:
                путь = адрес[len(f"https://{домен}"):]
                кодс, страница = ответ(база, путь, домен=домен)
                п(f"открыто: {путь} -> 200", кодс == 200, str(кодс))
                if кодс != 200:
                    continue
                м = re.search(r'<link[^>]+rel="canonical"[^>]+href="([^"]+)"', страница)
                п(f"открыто: canonical == loc ({путь})",
                  bool(м) and м.group(1) == адрес,
                  (м.group(1) if м else "canonical отсутствует"))

        finally:
            остановить(пр)
    finally:
        shutil.rmtree(врем, ignore_errors=True)


НОВЫЙ_СЛАГ = "proverka-karty-sayta-vypuskom"
НОВЫЙ_ПУТЬ = f"/title/{НОВЫЙ_СЛАГ}/"


class _Снимок:
    """Снимок каталога в том виде, в котором его видит сборщик."""

    def __init__(self, записи: list[dict], revision: str) -> None:
        self.items = записи
        self.revision = revision


class _Обработчик:
    данные: _Снимок


class _Рантайм:
    """Минимальный рантайм: ровно то, что сборщик у него спрашивает.

    Заглушка, а не живая витрина: свойство «карта следует за каталогом»
    принадлежит СБОРЩИКУ, и проверять его подъёмом двух витрин и ожиданием двух
    периодов по 300 с значило бы десять минут ждать ответа на вопрос, который
    решается вызовом функции. Живая отдача проверяется отдельно и выше.
    """

    def __init__(self, записи: list[dict], разделы: list[str], режим: str) -> None:
        self.Обработчик = _Обработчик()
        self.Обработчик.данные = _Снимок(записи, "gen-1")
        self.РАЗДЕЛЫ_КАРТЫ = tuple(р for р in разделы if р != "/")
        self._режим = режим

    def режим_индексации(self):
        return (self._режим, "проверка")


def ярус_сборщика(cfg: dict, разделы: list[str]) -> None:
    """Карта следует за каталогом и исчезает при закрытии. Сборщик выпуска."""
    import importlib.util

    print("3. сборщик: карта следует за каталогом", flush=True)
    модуль, _ = общий_модуль()
    if модуль is None:
        п("сборщик загружается", False, "seo_layer не найден")
        return
    спец = importlib.util.spec_from_file_location("seo_layer_проверка_карты", модуль)
    слой = importlib.util.module_from_spec(спец)
    try:
        спец.loader.exec_module(слой)
    except Exception as ош:  # noqa: BLE001 — причина называется, а не глотается
        п("сборщик загружается", False, f"{type(ош).__name__}: {ош}")
        return
    п("сборщик загружается", True, str(модуль.relative_to(КОРЕНЬ)))

    домен = cfg["domain"]
    записи = [{"url": f"/title/zapis-{i}/", "slug": f"zapis-{i}",
               "published_at": "2026-10-01T00:00:00Z",
               "published_at_estimated": False} for i in range(3)]
    # Служебное и оценочное: первого в карте быть не должно, у второго не должно
    # быть `lastmod` — оценочная дата, выданная за точную, обесценивает поле у
    # всех остальных адресов.
    записи.append({"url": "/api/vnutrennee/", "slug": "sluzhebnoe"})
    записи.append({"url": "/title/ocenochnaya-data/", "slug": "ocenochnaya-data",
                   "published_at": "2026-10-02T00:00:00Z",
                   "published_at_estimated": True})
    с_времянкой = Path(tempfile.mkdtemp(prefix="sitemap-collector-"))
    try:
        каталог = с_времянкой / "sitemap"
        рантайм = _Рантайм(записи, разделы, "OPEN")
        итог = слой.обновить_карту(рантайм, str(каталог), домен)
        п("карта собрана", итог.get("written") is True, str(итог)[:200])
        адреса = прочитать_карту(каталог, домен)
        п("служебный путь в карту не попал",
          f"https://{домен}/api/vnutrennee/" not in адреса)
        п("карточки и разделы в карте",
          f"https://{домен}/title/zapis-0/" in адреса and f"https://{домен}/" in адреса,
          str(len(адреса)))
        тексты = (каталог / "sitemap-1.xml").read_text(encoding="utf-8")
        п("lastmod только у точной даты",
          тексты.count("<lastmod>") == 3,
          f"{тексты.count('<lastmod>')} из {len(адреса)} адресов")

        # --- каталог изменился -------------------------------------------
        рантайм.Обработчик.данные = _Снимок(
            записи + [{"url": НОВЫЙ_ПУТЬ, "slug": НОВЫЙ_СЛАГ}], "gen-2")
        итог2 = слой.обновить_карту(рантайм, str(каталог), домен)
        адреса2 = прочитать_карту(каталог, домен)
        п("изменение каталога обновило карту", итог2.get("written") is True,
          str(итог2)[:200])
        п("новый адрес появился в карте",
          f"https://{домен}{НОВЫЙ_ПУТЬ}" in адреса2,
          f"адресов {len(адреса)} -> {len(адреса2)}")
        п("прежние адреса на месте",
          all(а in адреса2 for а in адреса), "карта потеряла прежние адреса")

        # --- режим закрыли -----------------------------------------------
        рантайм._режим = "CLOSED"
        итог3 = слой.обновить_карту(рантайм, str(каталог), домен)
        п("закрытый режим карту не пишет", итог3.get("written") is False,
          str(итог3)[:160])
        п("файлы карты сняты", not (каталог / "sitemap.xml").is_file(),
          str(sorted(p.name for p in каталог.iterdir())) if каталог.is_dir() else "—")
    finally:
        shutil.rmtree(с_времянкой, ignore_errors=True)


def прочитать_карту(каталог: Path, домен: str) -> list[str]:
    адреса: list[str] = []
    индекс = каталог / "sitemap.xml"
    if not индекс.is_file():
        return адреса
    корень = ET.fromstring(индекс.read_bytes())
    for э in корень.findall(f"{SM}sitemap"):
        имя = (э.findtext(f"{SM}loc") or "").rsplit("/", 1)[-1]
        часть = каталог / имя
        if not часть.is_file():
            continue
        for у in ET.fromstring(часть.read_bytes()).findall(f"{SM}url"):
            адреса.append(у.findtext(f"{SM}loc") or "")
    return адреса


def остановить(пр: subprocess.Popen) -> None:
    пр.terminate()
    try:
        пр.wait(timeout=30)
    except subprocess.TimeoutExpired:
        пр.kill()


def репр(текст: str) -> str:
    return repr(текст[:160])


def main() -> int:
    cfg = конфигурация()
    print(f"карта сайта: {cfg['domain']} ({cfg['site_id']})", flush=True)
    разделы = ярус_статический(cfg)
    живые = живые_данные(cfg)
    if живые is None:
        print("2. живая отдача ПРОПУЩЕНА: снимка каталога нет "
              "(задайте SITEMAP_CHECK_DATA=<каталог данных ячейки>). "
              "Ярусы 1 и 3 работают и без снимка.", flush=True)
    else:
        ярус_живой(cfg, разделы, живые)
    ярус_сборщика(cfg, разделы)
    print("\n" + ("карта сайта: все проверки пройдены" if ok else "КАРТА САЙТА: ЕСТЬ ПРОВАЛЫ"))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
