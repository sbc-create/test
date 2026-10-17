#!/usr/bin/env python3
"""Приёмка дат в карте сайта по требованиям владельца от 17.10. Только чтение.

Почему недостаточно проверки диапазона годов — слова владельца, и здесь они
переведены в измерения: неизменённая страница обязана сохранять дату при
повторном запросе И при перезапуске службы, а существенное изменение — дату
обновлять. Поэтому инструмент умеет снимать снимок и сравнивать два снимка,
а не только смотреть на числа одного ответа.

Проверки одного прохода:

1. границы с ДВУХ сторон: ни одной даты позже текущего времени и ни одной
   раньше нижней границы. Проверять только одну сторону — ровно та ошибка, на
   которой я сама пропустила даты 1973 года.

   Нижняя граница по умолчанию — **2024-01-01**, и это не произвольное число:
   даты обновления записей у поставщика начинаются с 2025 года (самая ранняя
   измеренная — 2025-07-17), а всё, что старше 2010, — расписание эфира
   (1973–2009, недельный шаг). Между ними нет ни одного значения, поэтому
   граница 2024 отделяет «дату обновления записи» от «даты эфира», не объявляя
   дефектом законные даты поставщика за 2025 год. Границу можно сдвинуть
   ключом `--floor`, но подменять ею смысл проверки нельзя: дата эфира
   недопустима не потому, что старая, а потому что это не дата обновления;
2. массовая подстановка: доля самой частой даты в части и число различных дат;
3. индекс против содержимого: дата части в индексе не раньше свежайшей даты
   внутри неё и не позже текущего времени;
4. опущенные даты: сколько адресов идут без `lastmod` — это разрешённое
   состояние, и его надо видеть, а не считать ошибкой.

Сравнение двух снимков (`--compare`):

5. устойчивость: сколько адресов сохранили дату дословно, сколько изменили,
   сколько появилось и исчезло. Для неизменённых страниц ожидается полное
   совпадение — и при повторном запросе, и после перезапуска службы.

    python3 automation/local/sitemap-lastmod-check.py --domain yummyani7.info
    python3 automation/local/sitemap-lastmod-check.py --domain yummyani7.info \\
        --snapshot var/sitemap-dates/info-before.json
    python3 automation/local/sitemap-lastmod-check.py --domain yummyani7.info \\
        --snapshot var/sitemap-dates/info-after.json \\
        --compare var/sitemap-dates/info-before.json
"""
from __future__ import annotations

import argparse
import collections
import datetime as dt
import json
import re
import subprocess
from pathlib import Path

ЮТС = dt.timezone.utc


def взять(url: str, таймаут: int = 180) -> str:
    г = subprocess.run(["curl", "-sS", "--max-time", str(таймаут), url],
                       capture_output=True, text=True)
    return г.stdout or ""


def разобрать_индекс(xml: str) -> list[tuple[str, str | None]]:
    """[(адрес части, объявленная дата или None)] — в порядке индекса."""
    итог = []
    for блок in re.findall(r"<sitemap>(.*?)</sitemap>", xml, re.S):
        м = re.search(r"<loc>(.*?)</loc>", блок)
        д = re.search(r"<lastmod>(.*?)</lastmod>", блок)
        if м:
            итог.append((м.group(1).strip(),
                         д.group(1).strip() if д else None))
    return итог


def разобрать_часть(xml: str) -> list[tuple[str, str | None]]:
    итог = []
    for блок in re.findall(r"<url>(.*?)</url>", xml, re.S):
        м = re.search(r"<loc>(.*?)</loc>", блок)
        д = re.search(r"<lastmod>(.*?)</lastmod>", блок)
        if м:
            итог.append((м.group(1).strip(),
                         д.group(1).strip() if д else None))
    return итог


def снять(домен: str) -> dict:
    индекс = взять(f"https://{домен}/sitemap.xml")
    части = разобрать_индекс(индекс)
    данные = {"domain": домен,
              "measured_at": dt.datetime.now(ЮТС).strftime("%Y-%m-%dT%H:%M:%SZ"),
              "index": {адрес.rsplit("/", 1)[-1]: дата for адрес, дата in части},
              "parts": {}}
    for адрес, _ in части:
        имя = адрес.rsplit("/", 1)[-1]
        данные["parts"][имя] = {а: д for а, д in разобрать_часть(взять(адрес))}
    return данные


def _дата(значение: str | None) -> dt.datetime | None:
    if not значение:
        return None
    т = значение.replace("Z", "+00:00")
    try:
        д = dt.datetime.fromisoformat(т)
    except ValueError:
        return None
    return д if д.tzinfo else д.replace(tzinfo=ЮТС)


def проверить(данные: dict, порог: dt.datetime, предел_доли: float) -> int:
    сейчас = dt.datetime.now(ЮТС)
    провалов = 0
    print(f"витрина {данные['domain']}, снято {данные['measured_at']}")
    print(f"частей в индексе: {len(данные['index'])}")
    for имя, адреса in данные["parts"].items():
        даты = [_дата(д) for д in адреса.values()]
        с_датой = [д for д in даты if д is not None]
        без_даты = len(даты) - len(с_датой)
        позже = [д for д in с_датой if д > сейчас]
        раньше = [д for д in с_датой if д < порог]
        сч = collections.Counter(д.date().isoformat() for д in с_датой)
        доля = (сч.most_common(1)[0][1] / len(с_датой)) if с_датой else 0.0
        частая = сч.most_common(1)[0][0] if сч else "—"
        объявлено = _дата(данные["index"].get(имя))
        свежайшая = max(с_датой) if с_датой else None

        print(f"\n{имя}: адресов {len(адреса)}, с датой {len(с_датой)}, "
              f"без даты {без_даты}")
        print(f"   дат позже текущего времени: {len(позже)}"
              + ("" if not позже else f"  ПРОВАЛ (пример {max(позже)})"))
        print(f"   дат раньше {порог.date()}: {len(раньше)}"
              + ("" if not раньше else f"  ПРОВАЛ (самая старая {min(раньше)})"))
        print(f"   самая частая дата {частая}: доля {100 * доля:.1f} %"
              + ("" if доля <= предел_доли else
                 f"  ПРОВАЛ (предел {100 * предел_доли:.0f} %)"))
        print(f"   различных дат: {len(сч)}")
        if объявлено is None:
            print("   индекс даты не объявляет — допустимо (необязательное поле)")
        else:
            поздно = объявлено > сейчас
            рано = bool(свежайшая and объявлено < свежайшая)
            print(f"   индекс объявляет {объявлено.isoformat()}"
                  + ("  ПРОВАЛ: позже текущего времени" if поздно else "")
                  + (f"  ПРОВАЛ: раньше свежайшей внутри ({свежайшая.isoformat()})"
                     if рано else ""))
            провалов += int(поздно) + int(рано)
        провалов += int(bool(позже)) + int(bool(раньше)) + int(доля > предел_доли)
    print(f"\nпровалов проверок: {провалов}")
    return провалов


def сравнить(новый: dict, старый: dict) -> int:
    print(f"\nсравнение снимков: {старый['measured_at']} → "
          f"{новый['measured_at']}")
    расхождений = 0
    for имя, адреса in новый["parts"].items():
        прежние = старый["parts"].get(имя, {})
        общие = set(адреса) & set(прежние)
        совпало = sum(1 for а in общие if адреса[а] == прежние[а])
        изменилось = [а for а in общие if адреса[а] != прежние[а]]
        print(f"{имя}: общих адресов {len(общие)}, дата совпала {совпало}, "
              f"изменилась {len(изменилось)}; новых "
              f"{len(set(адреса) - set(прежние))}, исчезло "
              f"{len(set(прежние) - set(адреса))}")
        for а in изменилось[:3]:
            print(f"   изменилась: {а.rsplit('/', 1)[-1][:40]} "
                  f"{прежние[а]} → {адреса[а]}")
        расхождений += len(изменилось)
    о_и, н_и = старый.get("index", {}), новый.get("index", {})
    for имя in sorted(set(о_и) | set(н_и)):
        if о_и.get(имя) != н_и.get(имя):
            print(f"индекс {имя}: {о_и.get(имя)} → {н_и.get(имя)}")
    print(f"\nизменившихся дат у общих адресов: {расхождений}")
    return расхождений


def главное(аргв=None) -> int:
    р = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    р.add_argument("--domain", required=True)
    р.add_argument("--floor", default="2024-01-01",
                   help="нижняя граница дат: отделяет дату обновления записи от даты эфира")
    р.add_argument("--max-share", type=float, default=0.20,
                   help="предел доли самой частой даты в части")
    р.add_argument("--snapshot", help="куда сохранить снимок")
    р.add_argument("--compare", help="снимок, с которым сравнить")
    опции = р.parse_args(аргв)

    порог = dt.datetime.fromisoformat(опции.floor).replace(tzinfo=ЮТС)
    данные = снять(опции.domain)
    провалов = проверить(данные, порог, опции.max_share)
    if опции.snapshot:
        п = Path(опции.snapshot)
        п.parent.mkdir(parents=True, exist_ok=True)
        п.write_text(json.dumps(данные, ensure_ascii=False) + "\n",
                     encoding="utf-8")
        print(f"снимок сохранён: {п}")
    if опции.compare:
        старый = json.loads(Path(опции.compare).read_text(encoding="utf-8"))
        сравнить(данные, старый)
    return 0 if провалов == 0 else 1


if __name__ == "__main__":
    raise SystemExit(главное())
