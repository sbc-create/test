#!/usr/bin/env python3
"""Прогрев карт сайта: один обход индекса и всех вложенных карт.

Повод (B016, измерено SEO-сессией 12–13 октября). У витрин Yummy индекс карт
отвечает 200 за 0,1 с, а вложенная `/sitemap/titles.xml` ПЕРВЫМ обращением
отдаёт 504 ровно через 30 с либо молчит дольше 40 с; повторное обращение — 200
за 0,2–0,9 с. Для робота это значит, что все тайтлы недоступны, причём проверка
«карта отдаёт 200» в это время зелёная: она смотрит на индекс.

Поднятие таймаута шлюза отвергнуто сознательно: оно прячет медленную
генерацию. Прогрев её устраняет — первое обращение делает не робот, а мы,
сразу после сборки, и платит за генерацию наш запрос.

Состояние на 2026-10-15: у `yummyani7.site` и `yummyani7.info` обе карты
отвечают 200, медленнейшая вложенная — 1 с, замечаний нет. То есть дефект
сейчас НЕ воспроизводится: кэш тёплый. Остаётся окно сразу после сборки, когда
кэш пуст, — ради него этот сценарий и существует.

Куда его ставить. В конец выкладки витрины: у Yummy это собственный сценарий
площадки (`deploy/staging/deploy.sh` владельца), у ячеек — шаг после установки
выпуска. Сценарий ничего не меняет на сайте: только читает.

    python3 automation/local/warm-sitemaps.py --domain yummyani7.site
    python3 automation/local/warm-sitemaps.py --all-live --timeout 90

Код возврата: 0 — все карты прогреты; 1 — хотя бы одна не ответила 200;
2 — не удалось даже прочитать индекс (тогда прогревать нечего).
"""
from __future__ import annotations

import argparse
import json
import pathlib
import re
import sys
import time
import urllib.error
import urllib.request

КОРЕНЬ = pathlib.Path(__file__).resolve().parents[2]
РЕЕСТР = КОРЕНЬ / "config" / "site-cells.json"

#: Имена из RFC 6761 публично не разрешаются: их молчание — свойство имени, а
#: не состояние витрины. В прогрев они не попадают.
СЛУЖЕБНЫЕ = (".localhost", ".test", ".invalid", ".example")


def живые_домены() -> list[str]:
    """Домены действующих витрин из реестра ячеек."""
    try:
        данные = json.loads(РЕЕСТР.read_text(encoding="utf-8"))
    except (OSError, ValueError) as ош:
        raise SystemExit(f"реестр ячеек не прочитан: {ош}") from ош
    ячейки = данные.get("cells") if isinstance(данные, dict) else данные
    ячейки = ячейки if isinstance(ячейки, list) else list(ячейки.values())
    return [я["domain"] for я in ячейки
            if я.get("status") == "live" and я.get("domain")
            and not any(я["domain"].endswith(с) for с in СЛУЖЕБНЫЕ)]


def достать(адрес: str, таймаут: float) -> tuple[int | str, str, float]:
    """Код, тело и время ответа. Исключение кодом ответа не подменяется."""
    начало = time.monotonic()
    # Значение заголовка — только ASCII: заголовки кодируются latin-1, и
    # кириллица в User-Agent валит запрос UnicodeEncodeError ещё до сети.
    # Поймано своим же первым прогоном: инструмент печатал «индекс карт
    # ответил UnicodeEncodeError» про домены, которые отвечают 200.
    запрос = urllib.request.Request(адрес, headers={
        "User-Agent": "site-factory-warmup/1.0 (sitemap warmup)"})
    try:
        with urllib.request.urlopen(запрос, timeout=таймаут) as о:
            тело = о.read().decode("utf-8", "replace")
            return о.status, тело, time.monotonic() - начало
    except urllib.error.HTTPError as ош:
        return ош.code, "", time.monotonic() - начало
    except (urllib.error.URLError, OSError, ValueError) as ош:
        return f"{type(ош).__name__}: {ош}", "", time.monotonic() - начало


def вложенные(тело: str) -> list[str]:
    """Адреса вложенных карт из `sitemapindex`.

    Разбор регулярным выражением, а не XML-парсером, намеренно: карта может
    прийти с лишним байтом или обрезанной, и падение разбора превратило бы
    «карта битая» в «прогрев не состоялся по неизвестной причине». Нужны
    адреса, а не валидация схемы.
    """
    if "<sitemapindex" not in тело:
        return []
    return re.findall(r"<loc>\s*([^<\s]+)\s*</loc>", тело)


def прогреть(домен: str, таймаут: float, повтор: bool = True) -> dict:
    """Один обход индекса и всех вложенных карт одного домена."""
    итог: dict = {"domain": домен, "maps": [], "ok": False}
    код, тело, сек = достать(f"https://{домен}/sitemap.xml", таймаут)
    итог["index"] = {"status": код, "seconds": round(сек, 2)}
    if код != 200:
        итог["reason"] = (f"индекс карт ответил {код}: прогревать нечего, "
                          "вложенные адреса взять негде")
        return итог
    адреса = вложенные(тело)
    итог["nested_declared"] = len(адреса)
    if not адреса:
        # Одиночная карта — не ошибка: прогрет сам индекс, он же и карта.
        итог["ok"] = True
        итог["reason"] = "индекс вложенных карт не объявляет: прогрет сам он"
        return итог
    беды = []
    for адрес in адреса:
        код, _, сек = достать(адрес, таймаут)
        запись = {"url": адрес, "status": код, "seconds": round(сек, 2)}
        # Повторное обращение — не для красоты: прогрев считается состоявшимся,
        # когда ВТОРОЙ запрос быстр. Первый мог заплатить за генерацию, и
        # печатать только его значило бы отчитываться временем робота.
        if повтор and код == 200:
            _, _, сек2 = достать(адрес, таймаут)
            запись["seconds_warm"] = round(сек2, 2)
        if код != 200:
            беды.append(f"{адрес}: {код}")
        итог["maps"].append(запись)
    итог["ok"] = not беды
    if беды:
        итог["reason"] = "вложенные карты не прогреты: " + "; ".join(беды)
    return итог


def main() -> int:
    р = argparse.ArgumentParser(description=__doc__)
    р.add_argument("--domain", action="append", default=[])
    р.add_argument("--all-live", action="store_true",
                   help="все витрины со статусом live из реестра ячеек")
    р.add_argument("--timeout", type=float, default=60.0,
                   help="предел ожидания одной карты, с (по умолчанию 60)")
    р.add_argument("--json", action="store_true")
    а = р.parse_args()
    домены = list(dict.fromkeys(а.domain + (живые_домены() if а.all_live else [])))
    if not домены:
        print("нужен --domain или --all-live", file=sys.stderr)
        return 2
    итоги = [прогреть(д, а.timeout) for д in домены]
    if а.json:
        print(json.dumps(итоги, ensure_ascii=False, indent=2))
    else:
        print(f"{'домен':26} {'индекс':>7} {'карт':>5} {'холодн.':>8} "
              f"{'тёплая':>7}  замечания")
        for и in итоги:
            холодные = [м.get("seconds", 0) for м in и["maps"]]
            тёплые = [м["seconds_warm"] for м in и["maps"]
                      if "seconds_warm" in м]
            print(f"{и['domain']:26} {str(и['index']['status']):>7} "
                  f"{len(и['maps']):>5} "
                  f"{max(холодные, default=0):>7.1f}с "
                  f"{max(тёплые, default=0):>6.1f}с  "
                  f"{и.get('reason', '—')}")
    плохих = [и for и in итоги if not и["ok"]]
    if any(и["index"]["status"] != 200 for и in итоги):
        return 2
    return 1 if плохих else 0


if __name__ == "__main__":
    sys.exit(main())
