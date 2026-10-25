#!/usr/bin/env python3
"""Причина отсутствующего постера ПО КАЖДОЙ карточке: четыре версии по порядку.

Владелец назвал четыре возможные причины, и этот проход отвечает по каждой
карточке отдельно, а не по совокупности:

1. **ДАННЫЕ** — у поставщика нет `poster_url`, и в доставленном каталоге витрины
   его тоже нет. Тогда восстанавливать нечего до появления источника;
2. **СОПОСТАВЛЕНИЕ** — запись в ответе поставщика по её `id` не находится, или
   название у поставщика и на витрине расходится. Тогда дело не в картинке:
   карточка показывает чужое или потерянное произведение;
3. **АДРЕС ИЗОБРАЖЕНИЯ** — `poster_url` есть, но он негоден: без схемы, не на
   разрешённом хосте постеров, без расширения изображения;
4. **ЗАГРУЗКА** — адрес годен, но изображение не отдаётся: код не 200, тип не
   `image/*`, нулевая длина.

Порядок важен: причина называется ПЕРВАЯ сработавшая, а не все сразу. У записи
без `poster_url` версии 3 и 4 не «пройдены», а НЕ ПРИМЕНИМЫ, и проход говорит
это прямо — иначе «загрузка в порядке» читалось бы как исправность.

Отрицательный контроль входит в проход: вместе с заглушками берётся столько же
соседних карточек ТОЙ ЖЕ полки с постером (`--controls`). Если у контрольных
причина тоже находится, признак ничего не различает, и его выводам верить нельзя.

    python3 automation/local/poster-cause-per-card.py --domain lordserial33.biz
    python3 automation/local/poster-cause-per-card.py --domain zonafilm.space --json
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import re
import subprocess
import sys
from pathlib import Path

АГЕНТ = "factory-poster-cause-per-card"

КОРЕНЬ = Path(__file__).resolve().parents[2]

#: Домен → (site_id, каталог данных витрины). Берётся из отчёта публикации
#: (`cell_delivery`), а не угадывается по имени.
ВИТРИНЫ = {
    "lordserial33.biz": ("lords-02", "/srv/lordserial33-biz/data"),
    "zonafilm.space": ("zona-01", "/srv/zonafilm-space/data"),
    "zonafilm12.site": ("zona-03", "/srv/zonafilm12-site/data"),
    "zonafilm.cc": ("zona-02", "/srv/zonafilm-cc/data"),
    "lordfilm47.space": ("lords-01", "/srv/lordfilm47-space/data"),
    "lordserials22.info": ("lords-05", "/srv/lordserials22-info/data"),
    "1lordserials1.online": ("lords-03", "/srv/site-1lordserials1-online/data"),
}

#: Ответ поставщика, из которого собран каталог витрины. Один на семейство.
ПОСТАВЩИК = {
    "lords-01": "/srv/site-factory/repo/var/lords/lords/catalog-cache/lords-01.json",
    "lords-02": "/srv/site-factory/repo/var/lords/lords/catalog-cache/lords-02.json",
    "lords-03": "/srv/site-factory/repo/var/lords/lords/catalog-cache/lords-03.json",
    "lords-05": "/srv/site-factory/repo/var/lords/lords/catalog-cache/lords-01.json",
    "zona-01": "/srv/site-factory/repo/var/lords/lords/catalog-cache/lords-01.json",
    "zona-02": "/srv/site-factory/repo/var/lords/lords/catalog-cache/lords-01.json",
    "zona-03": "/srv/site-factory/repo/var/lords/lords/catalog-cache/lords-01.json",
}

#: Хосты, с которых витрины берут постеры, плюс собственный путь `/poster/...`.
ХОСТЫ_ПОСТЕРОВ = ("poster.cdnvideohub.com",)
РАСШИРЕНИЯ = (".webp", ".jpg", ".jpeg", ".png", ".avif")


def _модуль(путь: Path, имя: str):
    спец = importlib.util.spec_from_file_location(имя, путь)
    м = importlib.util.module_from_spec(спец)
    sys.modules[имя] = м
    спец.loader.exec_module(м)
    return м


def карточки_главной(домен: str) -> list[dict]:
    """Все карточки главной: слаг, полка, есть ли своё изображение.

    Берётся тем же проходом, которым измеряются заглушки
    (`automation/local/poster-coverage.py`), чтобы признак «заглушка» был ОДИН
    на оба прохода. Предел выборки намеренно не ставится: 24 карточки молча
    занижали, и на zonafilm.space это скрыло пять заглушек из шести.
    """
    м = _модуль(КОРЕНЬ / "automation/local/poster-coverage.py", "poster_coverage")
    А = м._ревизия()
    тело = А.добыть(f"https://{домен}/")
    if not тело:
        return []
    итог = []
    for к in А.карточки_по_порядку(тело, 10_000):
        итог.append({"слаг": к.get("слаг") or к.get("путь"),
                     "полка": к.get("блок"),
                     "есть_изображение": bool(к.get("постер"))})
    return итог


def каталог_витрины(site_id: str, каталог: str) -> dict[str, dict]:
    ф = Path(каталог) / f"{site_id}-catalog.json"
    if not ф.exists():
        return {}
    д = json.loads(ф.read_text(encoding="utf-8"))
    return {str(з.get("slug")): з for з in (д.get("items") or [])}


def подробности_витрины(site_id: str, каталог: str) -> dict[str, dict]:
    ф = Path(каталог) / f"{site_id}-details.json"
    if not ф.exists():
        return {}
    д = json.loads(ф.read_text(encoding="utf-8"))
    return д.get("details") or {}


def ответ_поставщика(site_id: str) -> dict[str, dict]:
    путь = ПОСТАВЩИК.get(site_id)
    if not путь or not Path(путь).exists():
        return {}
    д = json.loads(Path(путь).read_text(encoding="utf-8"))
    итог = {}
    for з in (д.get("items") or []):
        ид = str(з.get("id") or з.get("external_id") or "")
        if ид:
            итог[ид] = з
    return итог


def адрес_годен(адрес: str) -> tuple[bool, str]:
    if not адрес:
        return False, "адреса нет"
    if адрес.startswith("/"):
        return True, "локальный путь витрины"
    м = re.match(r"^https?://([^/]+)(/.*)?$", адрес)
    if not м:
        return False, "не абсолютный адрес и не локальный путь"
    хост, путь = м.group(1), (м.group(2) or "")
    if хост not in ХОСТЫ_ПОСТЕРОВ:
        return False, f"хост {хост} не входит в разрешённые {ХОСТЫ_ПОСТЕРОВ}"
    if not путь.lower().endswith(РАСШИРЕНИЯ):
        return False, f"путь не похож на изображение: {путь}"
    return True, f"хост {хост}"


def загрузка(адрес: str, домен: str, *, загрузчик=None) -> dict:
    """Код ответа, тип и длина. Проверяется ЗАГРУЗКОЙ, а не видом адреса."""
    полный = адрес if адрес.startswith("http") else f"https://{домен}{адрес}"
    if загрузчик is not None:
        return загрузчик(полный)
    г = subprocess.run(
        ["curl", "-A", АГЕНТ, "-sS", "-o", "/dev/null", "-L", "--max-time", "20",
         "-w", "%{http_code} %{content_type} %{size_download}", полный],
        capture_output=True, text=True, timeout=40)
    куски = (г.stdout or "").split()
    if len(куски) < 3:
        return {"url": полный, "код": None, "тип": "", "байт": 0,
                "ошибка": (г.stderr or г.stdout).strip()[:200]}
    return {"url": полный, "код": int(куски[0]) if куски[0].isdigit() else None,
            "тип": куски[1], "байт": int(куски[2]) if куски[2].isdigit() else 0}


def разобрать_карточку(слаг: str, *, запись_каталога: dict, деталь: dict,
                       поставщик: dict[str, dict], домен: str,
                       загрузчик=None) -> dict:
    ид = str((запись_каталога or {}).get("entity_id")
             or (деталь or {}).get("id") or "")
    постер_витрины = str((запись_каталога or {}).get("poster") or "").strip()
    постер_подробности = str((деталь or {}).get("poster_url") or "").strip()
    запись_поставщика = поставщик.get(ид) if ид else None
    постер_поставщика = str((запись_поставщика or {}).get("poster_url")
                            or "").strip()

    итог = {
        "slug": слаг, "id": ид,
        "постер_в_каталоге_витрины": постер_витрины or None,
        "постер_в_подробностях": постер_подробности or None,
        "постер_у_поставщика": постер_поставщика or None,
        "название_витрины": (запись_каталога or {}).get("title")
        or (деталь or {}).get("name"),
        "название_поставщика": (запись_поставщика or {}).get("name"),
    }

    # 2. СОПОСТАВЛЕНИЕ проверяется раньше данных: если записи нет или это
    #    другое произведение, разговор о картинке преждевременен.
    if not ид:
        итог.update(причина="СОПОСТАВЛЕНИЕ",
                    пояснение="у карточки витрины нет id записи — связать её с"
                              " ответом поставщика нечем")
        return итог
    if запись_поставщика is None:
        итог.update(причина="СОПОСТАВЛЕНИЕ",
                    пояснение=f"записи {ид} нет в ответе поставщика: каталог"
                              " витрины ссылается на то, чего источник не даёт")
        return итог
    наше = (итог["название_витрины"] or "").strip().lower()
    их = (итог["название_поставщика"] or "").strip().lower()
    if наше and их and наше != их and наше not in их and их not in наше:
        итог.update(причина="СОПОСТАВЛЕНИЕ",
                    пояснение=f"название расходится: {наше!r} против {их!r}")
        return итог

    # 1. ДАННЫЕ.
    адрес = постер_витрины or постер_подробности or постер_поставщика
    if not адрес:
        итог.update(
            причина="ДАННЫЕ",
            пояснение="`poster_url` пуст и у поставщика, и в доставленном"
                      " каталоге, и в подробностях — восстанавливать нечего"
                      " до появления источника изображений",
            версии_не_применимы=["АДРЕС ИЗОБРАЖЕНИЯ", "ЗАГРУЗКА"])
        return итог

    # 3. АДРЕС.
    годен, почему = адрес_годен(адрес)
    if not годен:
        итог.update(причина="АДРЕС ИЗОБРАЖЕНИЯ",
                    пояснение=f"{адрес}: {почему}",
                    версии_не_применимы=["ЗАГРУЗКА"])
        return итог

    # 4. ЗАГРУЗКА.
    о = загрузка(адрес, домен, загрузчик=загрузчик)
    итог["загрузка"] = о
    if о.get("код") != 200:
        итог.update(причина="ЗАГРУЗКА",
                    пояснение=f"{о['url']} отвечает {о.get('код')!r}"
                              f" {о.get('ошибка', '')}".strip())
        return итог
    if not str(о.get("тип") or "").startswith("image/"):
        итог.update(причина="ЗАГРУЗКА",
                    пояснение=f"{о['url']} отдаёт тип {о.get('тип')!r},"
                              " а не изображение")
        return итог
    if not о.get("байт"):
        итог.update(причина="ЗАГРУЗКА",
                    пояснение=f"{о['url']} отдаёт нулевую длину")
        return итог

    итог.update(причина="НЕ НАЙДЕНА",
                пояснение=f"данные, сопоставление, адрес и загрузка в порядке"
                          f" ({о['байт']} Б, {о['тип']}): заглушка на витрине"
                          " объясняется не этими четырьмя причинами")
    return итог


def главное(аргв: list[str] | None = None) -> int:
    р = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    р.add_argument("--domain", required=True)
    р.add_argument("--slugs", default="",
                   help="через запятую; по умолчанию берутся заглушки"
                        " проходом poster-coverage")
    р.add_argument("--controls", type=int, default=3,
                   help="сколько карточек С постером взять отрицательным"
                        " контролем")
    р.add_argument("--json", action="store_true")
    а = р.parse_args(аргв)

    if а.domain not in ВИТРИНЫ:
        print(f"НЕ ИЗМЕРЕНО: домена {а.domain} нет в перечне витрин —"
              " расширять его по своей инициативе нельзя")
        return 2
    site_id, каталог_данных = ВИТРИНЫ[а.domain]
    каталог = каталог_витрины(site_id, каталог_данных)
    подробности = подробности_витрины(site_id, каталог_данных)
    поставщик = ответ_поставщика(site_id)
    if not каталог or not поставщик:
        print(f"НЕ ИЗМЕРЕНО: нет каталога витрины ({len(каталог)} записей) или"
              f" ответа поставщика ({len(поставщик)} записей)")
        return 2

    карточки = [] if а.slugs else карточки_главной(а.domain)
    if а.slugs:
        слаги = [с for с in а.slugs.split(",") if с]
    else:
        if not карточки:
            print(f"НЕ ИЗМЕРЕНО: карточек на главной {а.domain} не найдено")
            return 2
        слаги = [к["слаг"] for к in карточки if not к["есть_изображение"]]
    if not слаги:
        print(f"{а.domain}: карточек-заглушек нет — разбирать нечего")
        return 0

    # Отрицательный контроль — карточки ТЕХ ЖЕ полок, у которых постер есть.
    полки_заглушек = {к["полка"] for к in карточки
                      if not к["есть_изображение"]}
    контроль = [к["слаг"] for к in карточки
                if к["есть_изображение"] and к["полка"] in полки_заглушек
                and к["слаг"] in каталог][:а.controls]

    строки = [разобрать_карточку(с, запись_каталога=каталог.get(с) or {},
                                 деталь=подробности.get(с) or {},
                                 поставщик=поставщик, домен=а.domain)
              for с in слаги]
    строки_контроля = [
        разобрать_карточку(с, запись_каталога=каталог.get(с) or {},
                           деталь=подробности.get(с) or {},
                           поставщик=поставщик, домен=а.domain)
        for с in контроль]

    сводка: dict[str, int] = {}
    for с in строки:
        сводка[с["причина"]] = сводка.get(с["причина"], 0) + 1

    отчёт = {"домен": а.domain, "site_id": site_id,
             "заглушек": len(строки), "по_причинам": сводка,
             "карточки": строки, "отрицательный_контроль": строки_контроля}
    if а.json:
        print(json.dumps(отчёт, ensure_ascii=False, indent=1))
    else:
        печать(отчёт)
    испорчен_контроль = any(с["причина"] != "НЕ НАЙДЕНА"
                            for с in строки_контроля)
    if испорчен_контроль:
        return 2
    return 1 if строки else 0


def печать(отчёт: dict) -> None:
    print(f"{отчёт['домен']} ({отчёт['site_id']}):"
          f" заглушек {отчёт['заглушек']}")
    for причина, сколько in sorted(отчёт["по_причинам"].items()):
        print(f"   {причина}: {сколько}")
    print()
    for с in отчёт["карточки"]:
        print(f"{с['slug']:40} {с['причина']}")
        print(f"   {с['пояснение']}")
        if с.get("версии_не_применимы"):
            print(f"   НЕ ПРИМЕНИМЫ (а не «в порядке»):"
                  f" {', '.join(с['версии_не_применимы'])}")
    print("\nОТРИЦАТЕЛЬНЫЙ КОНТРОЛЬ — карточки ТОЙ ЖЕ полки с постером:")
    if not отчёт["отрицательный_контроль"]:
        print("   не взят: состав полок не измерен")
    for с in отчёт["отрицательный_контроль"]:
        метка = "ок" if с["причина"] == "НЕ НАЙДЕНА" else "ПРОВАЛ ПРИЗНАКА"
        print(f"   {метка:16} {с['slug']:40} {с['причина']}")
        if с["причина"] != "НЕ НАЙДЕНА":
            print(f"      {с['пояснение']}")


if __name__ == "__main__":
    sys.exit(главное())
