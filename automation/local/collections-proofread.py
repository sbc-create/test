#!/usr/bin/env python3
"""Независимая вычитка подборки против описаний каталога витрины.

    python3 automation/local/collections-proofread.py \
        --collections docs/seo-operator/ZONAFILM_SPACE_COLLECTIONS_20261028.json \
        --details /srv/zonafilm-space/data/zona-01-details.json

Зачем
-----

Тексты подборок утверждают факты о произведениях: имена героев, места,
годы, предметы. Правило фабрики — ни одного придуманного факта: дата, состав,
оценка, доступность и популярность берутся из одобренного источника либо не
появляются. Автор текста проверить себя не может, поэтому вычитка идёт ОТДЕЛЬНО
и НЕ АВТОРОМ, механически.

Что инструмент делает
---------------------

1. Сверяет строй записи: произведение есть в каталоге по `id` (иначе по
   `slug`), совпадают `slug`, `name`, `year`, `type`, адрес собран из слага.
2. Разбирает текст `reason` и `intro` на ПРОВЕРЯЕМЫЕ АТОМЫ — имена собственные
   (слова с большой буквы не в начале предложения), числа и латиницу — и ищет
   каждый в описании произведения из каталога.
3. Печатает атомы, которых в каталоге НЕТ: это утверждения без источника,
   каждое — замечание автору, а не повод правки по месту.

Чего инструмент НЕ делает: не правит тексты, не ходит в сеть, не придумывает
замену, не судит о стиле. Он отвечает на один вопрос — есть ли у утверждения
источник в каталоге витрины.

Сверка слова ведётся по основе (первые пять знаков в нижнем регистре), чтобы
склонение и число не давали ложных замечаний: «Винчестеры» находит
«Винчестер», «Малдера» — «Малдер».
"""
from __future__ import annotations

import argparse
import difflib
import json
import pathlib
import re
import sys
import unicodedata

ОСНОВА = 5

#: Слова с большой буквы, которые именами собственными не являются.
НЕ_ИМЕНА = {
    "Сначала", "Затем", "Потом", "Хочу", "Сериал", "Сериалы", "Фильм",
    "Фильмы", "Аниме", "Мультфильм", "Если", "Когда", "После", "Это", "Эта",
    "Эти", "Тот", "Там", "Для", "Как", "Что", "Кто", "Где", "Все", "Всё",
    "Она", "Они", "Его", "Её", "Их", "Но", "Не", "Ни", "При", "Под", "Над",
    "Без", "Про", "Два", "Три", "Одна", "Один", "Герои", "Героиня",
    "Девушка", "Девочка", "Мальчик", "Мужчина", "Женщина", "Агенты", "Братья",
}

_СЛОВО = re.compile(r"[А-ЯЁ][а-яё\-]{2,}|[A-Z][A-Za-z\-]{2,}|\d{2,4}")
_КОНЕЦ = re.compile(r"[.!?…]\s+|^")


def основа(слово: str) -> str:
    """Основа для сверки: пять знаков, но у коротких слов четыре.

    Измерено 28.10: «Древа» (5 знаков) против «Древо Жизни» в описании
    расходится ровно на пятом знаке, и пять знаков дали бы ложное замечание на
    обычном склонении. Четыре знака у слов не длиннее пяти такие пары сводят,
    а имена вроде «Фаня» (его в описании нет вовсе) по-прежнему не находят.
    """
    ч = unicodedata.normalize("NFC", слово).strip("«»\"'-").lower()
    предел = ОСНОВА if len(ч) > ОСНОВА else max(4, len(ч) - 1)
    return ч[:предел]


def атомы(текст: str) -> list[str]:
    """Проверяемые атомы: имена собственные не в начале предложения, числа."""
    если_начало = set()
    поз = 0
    for кусок in re.split(r"(?<=[.!?…])\s+", текст or ""):
        м = re.match(r"\s*([А-ЯЁA-Z][\w\-]*)", кусок)
        if м:
            если_начало.add(поз + м.start(1))
        поз += len(кусок) + 1
    вышло = []
    for м in _СЛОВО.finditer(текст or ""):
        слово = м.group(0)
        if м.start() in если_начало and not слово.isdigit():
            continue
        if слово in НЕ_ИМЕНА:
            continue
        вышло.append(слово)
    return вышло


def стог(запись: dict) -> str:
    части = []
    for ключ in ("name", "title", "original_name", "original_title",
                 "description", "overview", "year", "slug", "type", "kind",
                 "country", "countries", "genres", "genre",
                 "cast", "actors", "director", "studio", "tags"):
        зн = запись.get(ключ)
        if зн is None:
            continue
        if isinstance(зн, (list, tuple)):
            части.extend(str(э) for э in зн)
        elif isinstance(зн, dict):
            части.extend(f"{к} {v}" for к, v in зн.items())
        else:
            части.append(str(зн))
    return unicodedata.normalize("NFC", " ".join(части)).lower()


def есть(атом: str, где: str) -> bool:
    о = основа(атом)
    if о and о in где:
        return True
    # Год против десятилетия: описание часто пишет «20-х годов прошлого века»
    # там, где текст подборки пишет «1920-х». Это одна и та же дата в другой
    # форме, а не утверждение без источника. Измерено 28.10 на «Острых
    # козырьках».
    if атом.isdigit() and len(атом) == 4 and атом[:2] in ("19", "20"):
        десятилетие = f"{int(атом[2:]) // 10 * 10}-х"
        if десятилетие in где:
            return True
    return False


def ближайшее(атом: str, где: str) -> str:
    """Самое похожее слово описания — чтобы склонение не требовало разбора.

    Детектор НАМЕРЕННО остаётся строгим: пропустить придуманный факт опаснее,
    чем дать замечание на склонении. Поэтому вместо ослабления сверки
    замечание несёт доказательство: «Фаня» → «Фань» в описании видно сразу,
    и читающему не нужно открывать каталог.
    """
    слова = {с.strip(".,:;!?()«»\"'—–-") for с in (где or "").split()}
    слова = {с for с in слова if len(с) > 2}
    близкие = difflib.get_close_matches(атом.lower(), sorted(слова), n=1,
                                        cutoff=0.6)
    if not близкие:
        return ""
    доля = difflib.SequenceMatcher(None, атом.lower(), близкие[0]).ratio()
    return f"; ближайшее в описании: «{близкие[0]}» ({доля:.2f})"


def выдержка(где: str, длина: int = 150) -> str:
    ч = " ".join(где.split())
    return ч[:длина] + ("…" if len(ч) > длина else "")


def разобрать_каталог(путь: pathlib.Path) -> tuple[dict, dict]:
    """Снимок витрины: описания лежат в `details` по слагу, не в catalog.

    Измерено 28.10: `zona-01-catalog.json` держит только slug, title, poster,
    kind, year, url, published_at — ни описания, ни id. Вычитка, сверяющая
    утверждения по каталогу, не нашла бы НИ ОДНОГО источника и выдала бы
    замечание на каждое имя. Источник описаний — `*-details.json` той же
    сборки (`catalog_revision`), запись содержит description, id,
    external_ids, name, original_name, type, year, genres, playable.
    """
    д = json.loads(путь.read_text(encoding="utf-8"))
    по_id, по_слагу = {}, {}
    if isinstance(д, dict) and isinstance(д.get("details"), dict):
        пары = d_пары = list(д["details"].items())
        for слаг, з in пары:
            if not isinstance(з, dict):
                continue
            з = {**з, "slug": слаг}
            по_слагу[str(слаг)] = з
            if з.get("id"):
                по_id[str(з["id"])] = з
        return по_id, по_слагу
    записи = д.get("items") if isinstance(д, dict) else д
    for з in записи or []:
        if not isinstance(з, dict):
            continue
        if з.get("id"):
            по_id[str(з["id"])] = з
        if з.get("slug"):
            по_слагу[str(з["slug"])] = з
    return по_id, по_слагу


def проверить(подборки: dict, по_id: dict, по_слагу: dict) -> list[str]:
    сайт = str(подборки.get("site") or "").strip()
    замечания: list[str] = []
    общий_стог = " ".join(стог(з) for з in по_id.values()) if по_id else ""
    for п in подборки.get("collections") or []:
        метка = f"{п.get('key')}"
        # Вступление подборки описывает тему, а не одну работу: его атомы
        # ищутся по описаниям ВСЕХ её работ.
        стог_подборки = " ".join(
            стог(по_id.get(str(э.get("id"))) or по_слагу.get(str(э.get("slug"))) or {})
            for э in п.get("items") or [])
        for атом in атомы(str(п.get("intro") or "")):
            if not есть(атом, стог_подборки):
                замечания.append(f"{метка} / intro: «{атом}» — в описаниях работ "
                                 "подборки не найдено")
        for э in п.get("items") or []:
            имя = э.get("name") or э.get("slug")
            з = по_id.get(str(э.get("id")))
            откуда = "id"
            if з is None:
                з = по_слагу.get(str(э.get("slug")))
                откуда = "slug"
            if з is None:
                замечания.append(f"{метка} / {имя}: в каталоге витрины нет ни по "
                                 f"id {э.get('id')}, ни по слагу {э.get('slug')}")
                continue
            if откуда == "slug":
                замечания.append(f"{метка} / {имя}: по id {э.get('id')} в каталоге "
                                 "нет, нашлось только по слагу — id под вопросом")
            if э.get("slug") and з.get("slug") and э["slug"] != з["slug"]:
                замечания.append(f"{метка} / {имя}: слаг {э['slug']} против "
                                 f"{з['slug']} в каталоге")
            if э.get("year") and з.get("year") and int(э["year"]) != int(з["year"]):
                замечания.append(f"{метка} / {имя}: год {э['year']} против "
                                 f"{з['year']} в каталоге")
            if э.get("type") and з.get("type") and э["type"] != з["type"]:
                замечания.append(f"{метка} / {имя}: вид {э['type']} против "
                                 f"{з['type']} в каталоге")
            if э.get("name") and з.get("name") and э["name"] != з["name"]:
                замечания.append(f"{метка} / {имя}: название «{э['name']}» против "
                                 f"«{з['name']}» в каталоге")
            for сист, зн in (э.get("external_ids") or {}).items():
                их = (з.get("external_ids") or {}).get(сист)
                if их and str(их) != str(зн):
                    замечания.append(f"{метка} / {имя}: {сист} {зн} против "
                                     f"{их} в каталоге")
            # Утверждение «воспроизведение есть (playable)» проверяемо.
            if "playable" in з and not з["playable"] and "playable" in str(э.get("basis") or ""):
                замечания.append(f"{метка} / {имя}: в основании сказано "
                                 "«воспроизведение есть (playable)», а в "
                                 "каталоге playable: false")
            ожидаемый = f"https://{сайт}/title/{з.get('slug')}/" if сайт else None
            if ожидаемый and э.get("url") and э["url"] != ожидаемый:
                замечания.append(f"{метка} / {имя}: адрес {э['url']} против "
                                 f"{ожидаемый}")
            где = стог(з)
            for атом in атомы(str(э.get("reason") or "")):
                if есть(атом, где):
                    continue
                # Собственное название работы и её оригинал — свой источник.
                свои = f"{э.get('name','')} {э.get('original_name','')} {э.get('year','')}"
                if есть(атом, свои.lower()):
                    continue
                есть_описание = bool(str(з.get("description") or "").strip())
                если = ("не найдено дословно — проверить форму записи"
                        if есть_описание else "утверждение без источника: "
                        "описания в каталоге нет вовсе")
                замечания.append(
                    f"{метка} / {имя}: «{атом}» — {если}"
                    + (ближайшее(атом, где) if есть_описание else "")
                    + (f"; источник: {выдержка(str(з.get('description') or ''))}"
                       if есть_описание else ""))
    if not по_id and not по_слагу:
        замечания.append("НЕ ИЗМЕРЕНО: каталог витрины пуст")
    return замечания


def main() -> int:
    р = argparse.ArgumentParser()
    р.add_argument("--collections", required=True)
    гр = р.add_mutually_exclusive_group(required=True)
    гр.add_argument("--details")
    гр.add_argument("--catalog")
    а = р.parse_args()
    пк = pathlib.Path(а.collections)
    пкат = pathlib.Path(а.details or а.catalog)
    if not пк.is_file():
        print(f"НЕ ИЗМЕРЕНО: нет {пк}")
        return 2
    if not пкат.is_file():
        print(f"НЕ ИЗМЕРЕНО: нет каталога {пкат} — вычитка идёт на хосте площадки")
        return 2
    подборки = json.loads(пк.read_text(encoding="utf-8"))
    по_id, по_слагу = разобрать_каталог(пкат)
    замечания = проверить(подборки, по_id, по_слагу)
    работ = sum(len(п.get("items") or []) for п in подборки.get("collections") or [])
    print(f"{пк.name}: подборок {len(подборки.get('collections') or [])}, "
          f"работ {работ}, каталог {len(по_id)} записей")
    if замечания and замечания[0].startswith("НЕ ИЗМЕРЕНО"):
        print(замечания[0])
        return 2
    for з in замечания:
        print("  замечание:", з)
    print(f"  всего замечаний: {len(замечания)}")
    return 1 if замечания else 0


if __name__ == "__main__":
    sys.exit(main())
