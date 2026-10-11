#!/usr/bin/env python3
"""Описание страницы произведения из фактов каталога. Перенос по якорям.

SEO-аудит 2026-10-11: у карточки без текста описания `<meta name="description">`
было «Имя: Фильм 2025» — одна и та же заглушка у тысяч страниц Lords/Zona, а
текст описания резался на 180-м знаке посреди слова. В репозиториях с
исходником ядра правка внесена коммитами (site-lordserial33-biz 90a413d и
перенос); этот инструмент — для витрин, где ядро закреплено артефактом шаблона
байт в байт (zona-02: template/<релиз>/lords-frontend.py), как
`apply-contact-footer.py`.

Что делается:
  * функция `краткое_описание()` — одна на файл, перед `def факты(`;
  * каждая сборка описания по образцу «описание[:180] или «Имя: вид год»»
    (обе формы: `описание` и `meta_desc`) заменяется её вызовом.

Якоря обязательны: если ни одной заглушки нет и функции нет — отказ ДО
записи. Повторный запуск ничего не меняет. `--check` — «приведён ли файл».

    python3 automation/host/apply-meta-description.py [--check] <файл> [<файл>…]
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

ПОМОЩНИК = '''#: Метки поставщика, которые не жанр для посетителя (раздел витрины, а не тема).
_ТЕХНИЧЕСКИЕ_ЖАНРЫ = {"западный контент"}


def краткое_описание(имя: str, запись: dict, деталь: dict, описание: str, сайт: str) -> str:
    """<meta name="description"> страницы произведения.

    Текст описания обрезается по границе слова. Без описания — фраза из фактов
    каталога: оригинальное название, вид, год, страна, жанры. Ничего сверх
    данных каталога не добавляется (apply-meta-description.py, 2026-10-11).
    """
    описание = " ".join(str(описание or "").split())
    if описание:
        if len(описание) <= 180:
            return описание
        срез = описание[:178].rsplit(" ", 1)[0].rstrip(",;:—- ")
        return срез + "…"
    деталь = деталь or {}
    ориг = str(деталь.get("original_name") or "").strip()
    голова = f"«{имя}»" + (f" ({ориг})" if ориг and ориг.casefold() != str(имя).casefold() else "")
    вид = str(запись.get("kind") or "").strip().lower()
    год = str(запись.get("year") or "").strip()
    что = " ".join(x for x in (вид, f"{год} года" if год else "") if x)
    страны = ", ".join(str(с) for с in (деталь.get("countries") or [])[:2])
    жанры = [str(ж) for ж in (деталь.get("genres") or [])
             if str(ж).strip().casefold() not in _ТЕХНИЧЕСКИЕ_ЖАНРЫ][:3]
    части = [голова + (f" — {что}" if что else "") + (f", {страны}" if страны else "") + "."]
    if жанры:
        части.append(("Жанры: " if len(жанры) > 1 else "Жанр: ") + ", ".join(жанры) + ".")
    части.append(f"Смотреть онлайн на {сайт}.")
    return " ".join(части)


'''
ЯКОРЬ_ПОМОЩНИКА = "def факты(вид: Вид, запись: dict, деталь: dict) -> list:"
ЗАГЛУШКА = re.compile(
    r"^(?P<отступ>[ \t]+)краткое = \((?P<поле>описание|meta_desc)\[:180\] if (?P=поле) else\n"
    r"[ \t]+f\"\{имя\}: \{запись\.get\('kind'\) or ''\} \{запись\.get\('year'\) or ''\}\"\.strip\(\)\)\n",
    re.M)


def привести(текст: str) -> tuple[str, int]:
    """(новый текст, число заменённых заглушек). ValueError — якоря не сошлись."""
    есть_помощник = "def краткое_описание(" in текст
    новый, n = ЗАГЛУШКА.subn(
        lambda m: f"{m['отступ']}краткое = краткое_описание(имя, запись, деталь, {m['поле']}, self.имя)\n",
        текст)
    if not n and not есть_помощник:
        raise ValueError("ни заглушки описания, ни функции краткое_описание — файл не того вида")
    if n and not есть_помощник:
        if новый.count(ЯКОРЬ_ПОМОЩНИКА) != 1:
            raise ValueError(f"якорь «{ЯКОРЬ_ПОМОЩНИКА}» найден не ровно один раз")
        новый = новый.replace(ЯКОРЬ_ПОМОЩНИКА, ПОМОЩНИК + ЯКОРЬ_ПОМОЩНИКА)
    return новый, n


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--check", action="store_true", help="только ответить, приведён ли файл")
    ap.add_argument("files", nargs="+")
    a = ap.parse_args(argv)
    код = 0
    for имя in a.files:
        путь = Path(имя)
        текст = путь.read_text(encoding="utf-8")
        try:
            новый, n = привести(текст)
        except ValueError as exc:
            print(f"{имя}: ОТКАЗ — {exc}")
            код = 2
            continue
        if a.check:
            print(f"{имя}: {'приведён' if новый == текст else f'не приведён (заглушек {n})'}")
            код = код or (0 if новый == текст else 1)
            continue
        if новый != текст:
            путь.write_text(новый, encoding="utf-8")
        print(f"{имя}: заглушек заменено {n}")
    return код


if __name__ == "__main__":
    sys.exit(main())
