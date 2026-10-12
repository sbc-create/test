#!/usr/bin/env python3
"""zonafilm.cc: у главной нет H1 — ставится видимый H1 из уже утверждённого титула. Перенос по якорям.

Замер 12.10 (automation/local/meta-audit.py): https://zonafilm.cc/ — `<h1>` 0 шт,
build 855f4259fb31-zona-02; у остальных 10 проверенных витрин H1 на главной есть
(zonafilm.space: «Сейчас на Zona»). Норма — SEO_KNOWLEDGE_PACK §4 п.1: один
понятный H1 на indexable-страницу из переданных полей и утверждённых шаблонов.

Текст H1 не придумывается: это тот же титул, что уже стоит в <title> главной
(`f"{self.имя} — фильмы и сериалы онлайн"`, src/serve.py). H1 ВИДИМ посетителю
(§4 п.5 — скрытый текст запрещён): обычный заголовок над первым блоком.

Нет якоря или он не единственный — отказ ДО записи. Повтор ничего не меняет.

    python3 automation/host/apply-home-h1.py [--check] <src/serve.py>
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

МЕТКА = "# H1 главной — из титула (apply-home-h1)."
ЯКОРЬ = '''        тело = home.построить(self, рантайм)
        return self.оболочка(
            тело, f"{self.имя} — фильмы и сериалы онлайн", "/", актив="/",
'''
ЗАМЕНА = '''        тело = home.построить(self, рантайм)
        ''' + МЕТКА + '''
        # У главной не было ни одного <h1> (замер 12.10). Текст — тот же
        # утверждённый титул, что в <title>; заголовок видим посетителю.
        титул_главной = f"{self.имя} — фильмы и сериалы онлайн"
        тело = ('<h1 class="zxh1" style="font-size:1.375rem;line-height:1.3;'
                'margin:.75rem 0 1rem">' + _html.escape(титул_главной) + "</h1>" + тело)
        return self.оболочка(
            тело, титул_главной, "/", актив="/",
'''
ИМПОРТ = "import importlib.util\n"
ИМПОРТ_НОВЫЙ = "import html as _html\nimport importlib.util\n"


def привести(текст: str) -> tuple[str, int]:
    if МЕТКА in текст:
        return текст, 0
    if текст.count(ЯКОРЬ) != 1:
        raise ValueError("якорь главной найден не ровно один раз")
    if текст.count(ИМПОРТ) != 1:
        raise ValueError("якорь импорта найден не ровно один раз")
    новый = текст.replace(ЯКОРЬ, ЗАМЕНА)
    if "import html as _html\n" not in новый:
        новый = новый.replace(ИМПОРТ, ИМПОРТ_НОВЫЙ)
    return новый, 1


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--check", action="store_true")
    ap.add_argument("file")
    a = ap.parse_args(argv)
    путь = Path(a.file)
    текст = путь.read_text(encoding="utf-8")
    try:
        новый, _ = привести(текст)
    except ValueError as exc:
        print(f"{путь}: ОТКАЗ — {exc}")
        return 2
    if a.check:
        print(f"{путь}: {'приведён' if новый == текст else 'не приведён'}")
        return 0 if новый == текст else 1
    if новый != текст:
        путь.write_text(новый, encoding="utf-8")
    print(f"{путь}: приведён")
    return 0


if __name__ == "__main__":
    sys.exit(main())
