#!/usr/bin/env python3
"""Опись редакционных материалов: что есть, где лежит, что использовано.

Повод. Инструмент `editorial_queue_status` отвечает числами (`works_total`,
`texts_present`, `texts_verified`), по которым нельзя ни открыть текст, ни
понять, лежит ли он на сайте. Вопрос «где уже написанные описания» числами не
закрывается: нужен путь к записи и публичный адрес страницы.

Источник один и тот же, что у очереди: реестр оператора. Опись считается ИЗ
НЕГО, а не из отчётов о нём.

Три вещи, которые инструмент обязан различать:

1. «нет текста» и «нет доступа к хранилищу» — это разные ответы. Недоступное
   хранилище печатается отдельной строкой с причиной, а не нулём.
2. накопленное и сделанное за сутки — по датам `draft_created_at`,
   `text_recorded_at` и `published_at`, а не по дате файла реестра.
3. уникальные тексты и их размещения. Поле `content_hash` в записи для этого
   НЕ годится: измерено 24.10 — у 148 записей animedia.space с разными телами
   он одинаков (на весь реестр 28 значений при 833 телах). Уникальность
   считается по самому тексту.

Запуск:
  editorial-inventory.py --summary            свод по доменам
  editorial-inventory.py --export <файл.tsv>  опись для открытия
  editorial-inventory.py --examples 10        примеры с фрагментами
  editorial-inventory.py --obstacles          препятствия готовым текстам
  editorial-inventory.py --window-hours 24    что создано и выверено за сутки
  editorial-inventory.py --control            положительный контроль
"""
from __future__ import annotations

import argparse
import datetime
import glob
import hashlib
import json
import pathlib
import sys

РЕЕСТР = pathlib.Path("/var/lib/seo-content-operator/registry.json")
ХРАНИЛИЩА = {
    "реестр оператора": РЕЕСТР,
    "черновики": pathlib.Path("/var/lib/seo-content-operator/drafts"),
    "пакеты источников": pathlib.Path("/var/lib/seo-content-operator/source_packets"),
    "суточные отчёты": pathlib.Path("/var/lib/seo-content-operator/outbox"),
    "аренды очереди": pathlib.Path("/var/lib/seo-content-operator/editorial_leases.json"),
}
K2 = ("lordfilm.group", "lordfilm.spb.ru", "lordfilm.msk.ru", "lordserial.su",
      "lordserial.group", "lordserial.spb.ru", "lordserial.msk.ru",
      "lordserial.net.ru")


def отпечаток(текст: str) -> str:
    """Хеш самого текста: пробелы не считаются различием."""
    return hashlib.sha256(" ".join(текст.split()).encode("utf-8")).hexdigest()


def доступность() -> list[tuple[str, str, str]]:
    """Состояние каждого хранилища: доступно / нет доступа / отсутствует.

    Отдельный ответ на каждое — чтобы «нет текста» не склеивалось с «не
    посмотрела».
    """
    из = []
    for имя, путь in ХРАНИЛИЩА.items():
        try:
            if not путь.exists():
                из.append((имя, str(путь), "ОТСУТСТВУЕТ"))
                continue
            if путь.is_dir():
                n = len(list(путь.iterdir()))
                из.append((имя, str(путь), f"доступно, элементов {n}"))
            else:
                из.append((имя, str(путь), f"доступно, {путь.stat().st_size} Б"))
        except PermissionError as о:
            из.append((имя, str(путь), f"НЕТ ДОСТУПА: {о.strerror}"))
        except OSError as о:
            из.append((имя, str(путь), f"НЕ ПРОЧИТАНО: {о}"))
    return из


def записи(путь: pathlib.Path = РЕЕСТР) -> list[dict]:
    return json.loads(путь.read_text(encoding="utf-8"))["items"]


def с_текстом(зп: list[dict]) -> list[dict]:
    return [з for з in зп if (з.get("body") or "").strip()]


def происхождение(з: dict) -> str:
    """Откуда факты. Не выдумывает автора, которого в записи нет."""
    p = з.get("provenance") or {}
    ид = p.get("source_id") or p.get("source") or ""
    if not ид:
        ряд = p.get("inventory_row") or {}
        ид = ряд.get("задание") or ""
    return ид or "не записано"


def авторство(з: dict) -> str:
    """Кто написал. Пустое поле — пробел в данных, а не «Qwen»."""
    а = (з.get("author") or "").strip()
    if а:
        return а
    ряд = (з.get("provenance") or {}).get("inventory_row") or {}
    if ряд.get("автор текста"):
        return f"{ряд['автор текста']} (из описи задания)"
    if з.get("authorship_data_gap"):
        return "не записано (отмечен пробел авторства)"
    return "не записано"


def изменено(з: dict) -> str:
    """Самая поздняя из дат записи — она и есть дата изменения."""
    даты = [(з.get(п) or "").strip() for п in
            ("published_at", "updated_at", "draft_created_at")]
    даты.append(((з.get("provenance") or {}).get("text_recorded_at") or "").strip())
    даты = [д for д in даты if д]
    return max(даты) if даты else "не записано"


def ключ(з: dict) -> str:
    return f"{РЕЕСТР}#items[content_id={з['content_id']}]"


# --- своды -----------------------------------------------------------------

def свод(зп: list[dict]) -> int:
    дом: dict[str, list[dict]] = {}
    for з in зп:
        дом.setdefault(з.get("target_site") or "(домен не указан)", []).append(з)

    print(f"{'домен':24} {'записей':>8} {'с текстом':>10} {'уник.текстов':>13}"
          f" {'выверено':>9} {'на сайте':>9}")
    всего_т = всего_у = 0
    тела_всех: set[str] = set()
    for д in sorted(дом, key=lambda x: -len(дом[x])):
        v = дом[д]
        ст = с_текстом(v)
        отп = {отпечаток(з["body"]) for з in ст}
        тела_всех |= отп
        выв = sum(1 for з in v if з["status"] == "READY_VERIFIED")
        живо = sum(1 for з in v if з["status"] in ("PUBLISHED", "ALREADY_LIVE"))
        всего_т += len(ст)
        всего_у += len(отп)
        print(f"{д:24} {len(v):8} {len(ст):10} {len(отп):13} {выв:9} {живо:9}")
    print()
    print(f"итого записей {len(зп)}, с текстом {всего_т},"
          f" уникальных текстов {len(тела_всех)}")
    if всего_т != len(тела_всех):
        print(f"  повторов текста: {всего_т - len(тела_всех)}"
              f" (один текст размещён более одного раза)")
    else:
        print("  повторов текста нет: каждое тело встречается один раз")
    k2_зап = [з for з in зп if з.get("target_site") in K2]
    print(f"витрины K2 ({len(K2)} доменов): записей {len(k2_зап)},"
          f" с текстом {len(с_текстом(k2_зап))}")
    return 0


def опись(зп: list[dict], файл: pathlib.Path) -> int:
    строки = ["\t".join((
        "домен", "ID произведения", "заголовок", "происхождение фактов",
        "авторство", "статус", "хранилище и ключ записи", "изменено",
        "публичный URL", "знаков"))]
    for з in sorted(зп, key=lambda x: (x.get("target_site") or "", x["content_id"])):
        тело = (з.get("body") or "").strip()
        строки.append("\t".join((
            з.get("target_site") or "",
            з.get("title_id") or "",
            (з.get("headline") or "").replace("\t", " "),
            происхождение(з).replace("\t", " "),
            авторство(з),
            з["status"],
            ключ(з),
            изменено(з),
            з.get("canonical_url") or "",
            str(len(тело)) if тело else "0 (текста нет)")))
    файл.parent.mkdir(parents=True, exist_ok=True)
    файл.write_text("\n".join(строки) + "\n", encoding="utf-8")
    print(f"опись: {файл} — строк {len(строки) - 1} + заголовок")
    return 0


def примеры(зп: list[dict], сколько: int) -> int:
    """Примеры берутся из РАЗНЫХ доменов и разных статусов, а не первые с краю."""
    ст = с_текстом(зп)
    по_домену: dict[str, list[dict]] = {}
    for з in ст:
        по_домену.setdefault(з.get("target_site") or "", []).append(з)
    отобраны: list[dict] = []
    живые = [з for з in ст if з["status"] in ("PUBLISHED", "ALREADY_LIVE")]
    отобраны.extend(живые[:3])
    домены = sorted(по_домену, key=lambda x: -len(по_домену[x]))
    круг = 0
    while len(отобраны) < сколько and круг < 8:
        for д in домены:
            if len(отобраны) >= сколько:
                break
            сп = [з for з in по_домену[д] if з not in отобраны]
            if len(сп) > круг:
                отобраны.append(сп[круг])
        круг += 1
    for н, з in enumerate(отобраны[:сколько], 1):
        тело = " ".join((з.get("body") or "").split())
        print(f"--- {н}. {з.get('target_site')} | {з['status']} ---")
        print(f"  произведение : {з.get('title_id') or '(нет ID)'} — {з.get('headline')}")
        print(f"  открыть      : {ключ(з)}")
        print(f"  URL          : {з.get('canonical_url')}")
        print(f"  факты        : {происхождение(з)}")
        print(f"  авторство    : {авторство(з)}")
        print(f"  изменено     : {изменено(з)}   знаков: {len(тело)}")
        print(f"  фрагмент     : {тело[:220]}…")
        print()
    print(f"показано {min(сколько, len(отобраны))} из {len(ст)} записей с текстом")
    return 0


def препятствия(зп: list[dict]) -> int:
    """Почему готовый текст не на сайте. Причина берётся из данных.

    Для статусов реестра — сам статус и его `reject_reason`; для выверенных,
    которые не отвергнуты, препятствие названо суточными отчётами оператора.
    """
    from collections import Counter
    готовые = [з for з in зп if з["status"] == "READY_VERIFIED"]
    print(f"выверено и не на сайте: {len(готовые)}")
    прич = Counter(з.get("reject_reason") or "(причина в записи не указана)"
                   for з in готовые)
    for п, c in прич.most_common():
        print(f"  {c:5}  {п}")
    print()
    отчёты = sorted(glob.glob(
        "/var/lib/seo-content-operator/outbox/2026-*/DAILY_REPORT_*.json"))
    if not отчёты:
        print("суточные отчёты оператора: НЕ НАЙДЕНЫ — препятствие не названо")
        return 1
    print(f"суточные отчёты оператора: {len(отчёты)}; последние 5:")
    for ф in отчёты[-5:]:
        d = json.loads(pathlib.Path(ф).read_text(encoding="utf-8"))
        отк = Counter(о.get("reason") for о in d.get("rejected") or [])
        б = d.get("buffer_eta") or {}
        print(f"  {d['run_id']}: запуск {d.get('trigger_source')},"
              f" план {len(d.get('planned') or [])},"
              f" опубликовано {len(d.get('published') or [])},"
              f" отказов {dict(отк) or '—'}")
        print(f"     режим новостей {б.get('NEWS_PUBLICATION_MODE')},"
              f" анонсов {б.get('ANNOUNCEMENT_PUBLICATION_MODE')},"
              f" полная автономия {б.get('FULL_CONTENT_AUTONOMY_OK')},"
              f" titles-only {б.get('TITLES_ONLY_LIVE_OK')}")
    return 0


def окно(зп: list[dict], часов: int) -> int:
    сейчас = datetime.datetime.now(datetime.timezone.utc)
    порог = сейчас - datetime.timedelta(hours=часов)

    def в_окне(значение: str) -> bool:
        з = (значение or "").strip()
        if not з:
            return False
        try:
            d = datetime.datetime.fromisoformat(з.replace("Z", "+00:00"))
        except ValueError:
            return False
        if d.tzinfo is None:
            d = d.replace(tzinfo=datetime.timezone.utc)
        return d >= порог

    создано = [з for з in зп if в_окне(з.get("draft_created_at"))]
    записан = [з for з in зп if в_окне(
        (з.get("provenance") or {}).get("text_recorded_at"))]
    опубл = [з for з in зп if в_окне(з.get("published_at"))]
    print(f"окно: последние {часов} ч (с {порог:%Y-%m-%dT%H:%M}Z"
          f" по {сейчас:%Y-%m-%dT%H:%M}Z)")
    print(f"  черновик создан : {len(создано)}")
    print(f"  текст записан   : {len(записан)}")
    print(f"  опубликовано    : {len(опубл)}")
    print(f"накоплено всего   : записей {len(зп)}, с текстом {len(с_текстом(зп))}")
    for имя, сп in (("создано", создано), ("записан текст", записан)):
        if сп:
            дом = sorted({з.get("target_site") or "?" for з in сп})
            print(f"  {имя} — домены: {', '.join(дом)}")
    return 0


def контроль() -> int:
    """Положительный контроль: инструмент обязан уметь найти текст и не найти.

    Без него чистый ноль по K2 неотличим от инструмента, который ничего не
    смотрел.
    """
    зп = записи()
    ст = с_текстом(зп)
    ошибки = []
    if not ст:
        ошибки.append("в реестре не найдено НИ ОДНОГО текста — источник пуст или не тот")
    образец = {"body": "  ", "status": "X", "content_id": "c", "target_site": "d"}
    if с_текстом([образец]):
        ошибки.append("пустое тело принято за текст")
    if отпечаток("а  б") != отпечаток("а б"):
        ошибки.append("отпечаток считает пробелы различием")
    if отпечаток("а") == отпечаток("б"):
        ошибки.append("отпечаток не различает разные тексты")
    k2 = [з for з in зп if з.get("target_site") in K2]
    print(f"контроль: записей {len(зп)}, с текстом {len(ст)},"
          f" доменов {len({з.get('target_site') for з in зп})}")
    print(f"контроль: записей витрин K2 в реестре {len(k2)}")
    if ошибки:
        for о in ошибки:
            print(f"КОНТРОЛЬ НЕ ПРОЙДЕН: {о}")
        return 1
    print("контроль пройден: инструмент видит тексты и отличает пустое от текста")
    return 0


def главное(argv: list[str] | None = None) -> int:
    р = argparse.ArgumentParser(description=__doc__)
    р.add_argument("--summary", action="store_true")
    р.add_argument("--export", type=pathlib.Path)
    р.add_argument("--examples", type=int)
    р.add_argument("--obstacles", action="store_true")
    р.add_argument("--window-hours", type=int)
    р.add_argument("--control", action="store_true")
    р.add_argument("--registry", type=pathlib.Path, default=РЕЕСТР)
    а = р.parse_args(argv)

    print("== хранилища ==")
    нет_доступа = []
    for имя, путь, сост in доступность():
        print(f"  {имя:22} {сост:34} {путь}")
        if "НЕТ ДОСТУПА" in сост or "ОТСУТСТВУЕТ" in сост:
            нет_доступа.append(имя)
    if нет_доступа:
        print(f"  ВНИМАНИЕ: недоступны/отсутствуют: {', '.join(нет_доступа)}"
              " — по ним ответ «нет текста» НЕ даётся")
    print()

    if not а.registry.exists():
        print(f"НЕ ИЗМЕРЕНО: реестра нет по пути {а.registry}")
        return 2
    зп = записи(а.registry)
    код = 0
    if а.control:
        код |= контроль()
    if а.summary:
        print("\n== свод по доменам ==")
        код |= свод(зп)
    if а.export:
        print("\n== опись ==")
        код |= опись(зп, а.export)
    if а.examples:
        print("\n== примеры ==")
        код |= примеры(зп, а.examples)
    if а.obstacles:
        print("\n== препятствия ==")
        код |= препятствия(зп)
    if а.window_hours:
        print("\n== сутки против накопленного ==")
        код |= окно(зп, а.window_hours)
    if not any((а.summary, а.export, а.examples, а.obstacles,
                а.window_hours, а.control)):
        р.print_help()
        return 2
    return код


if __name__ == "__main__":
    sys.exit(главное())
