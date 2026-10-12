#!/usr/bin/env python3
"""BreadcrumbList только из видимых крошек страницы (SEO_KNOWLEDGE_PACK §4 п.4). Перенос по якорям.

Замер 12.10 (страница тайтла, 11 витрин): у Lords ×4, AnimeGo ×3, Animedia ×2 общий
слой строил BreadcrumbList из сегментов адреса — «Главная › title › jamai-2-0»:
раздел /title/ отвечает 404, последнее звено — slug. Видимые крошки при этом
«Lordserial » Сериалы » Jamai 2.0». У Zona страница отдаёт свою разметку — верную.
Правка: цепочка строится из <nav aria-label="Хлебные крошки"> страницы; нет
видимых крошек — нет разметки. Источник — общий automation/host/seo_layer.py;
копии витрин расходятся с ним (D204), поэтому перенос по якорям, а не копией.

Нет якоря или он не единственный — отказ ДО записи (всех файлов). Повтор ничего
не меняет.

    python3 automation/host/apply-visible-breadcrumbs.py [--check] <seo_layer.py> […]
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

МЕТКА = "def крошки_со_страницы("
ИСТОЧНИК = Path(__file__).resolve().with_name("seo_layer.py")


def _функция() -> str:
    """Текст функции и её шаблона — из общего источника, чтобы не было двух копий правила."""
    т = ИСТОЧНИК.read_text(encoding="utf-8")
    начало = т.index("_НАВ_КРОШЕК = re.compile(")
    конец = т.index("def уже_есть_типы(")
    return т[начало:конец]


ЗАМЕНЫ = (
    ("def уже_есть_типы(тело: bytes) -> set[str]:",
     None),  # перед ней вставляется функция
    ('''          поиск: str = "", крошки: dict[str, str] | None = None,
          кроме: set[str] | None = None) -> str:''',
     '''          поиск: str = "", крошки: dict[str, str] | None = None,
          кроме: set[str] | None = None, видимые: list[dict] | None = None) -> str:'''),
    ('''    цепь = _цепочка(хост, путь, крошки or {})
    if len(цепь) > 1 and "BreadcrumbList" not in занято:''',
     '''    # Только видимые крошки страницы; цепочка из сегментов адреса больше не
    # строится (она расходилась с видимыми крошками — §4 п.4). `крошки`
    # оставлен для совместимости вызовов и на разметку не влияет.
    цепь = видимые or []
    if len(цепь) > 1 and "BreadcrumbList" not in занято:'''),
    ('''                         поиск=поиск, крошки=крошки, кроме=есть)''',
     '''                         поиск=поиск, крошки=крошки, кроме=есть,
                         видимые=крошки_со_страницы(тело, хост))'''),
)


def привести(текст: str) -> tuple[str, int]:
    if МЕТКА in текст:
        return текст, 0
    for якорь, _ in ЗАМЕНЫ:
        if текст.count(якорь) != 1:
            raise ValueError(f"якорь найден не ровно один раз: {якорь.strip()[:60]!r}")
    новый = текст
    for якорь, замена in ЗАМЕНЫ:
        новый = новый.replace(якорь, (_функция() + якорь) if замена is None else замена)
    return новый, 1


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--check", action="store_true")
    ap.add_argument("files", nargs="+")
    a = ap.parse_args(argv)
    планы = []
    for имя in a.files:
        путь = Path(имя)
        текст = путь.read_text(encoding="utf-8")
        try:
            новый, _ = привести(текст)
        except ValueError as exc:
            print(f"{имя}: ОТКАЗ — {exc}; ничего не записано")
            return 2
        планы.append((путь, текст, новый))
    if a.check:
        код = 0
        for путь, текст, новый in планы:
            print(f"{путь}: {'приведён' if новый == текст else 'не приведён'}")
            код = код or (0 if новый == текст else 1)
        return код
    # Записываемость всех целей — до первой записи (0444 у копий — D204: снять
    # осознанно, вернуть после).
    for путь, текст, новый in планы:
        if новый != текст and not os.access(путь, os.W_OK):
            print(f"{путь}: ОТКАЗ — файл не записываемый; ничего не записано")
            return 2
    for путь, текст, новый in планы:
        if новый != текст:
            путь.write_text(новый, encoding="utf-8")
        print(f"{путь}: приведён")
    return 0


if __name__ == "__main__":
    sys.exit(main())
