#!/usr/bin/env python3
"""Страница выдачи N>1 — номер в canonical и заголовке (оформление Zona). Перенос по якорям.

REQ-SEO-PAGINATION п.3 (knowledge/SEO_KNOWLEDGE_PACK.md §2; D202): полезная
страница пагинации имеет self-canonical. В репозиториях с исходником ядра
правка внесена коммитами (zonafilm.space 6491b65, zonafilm12.site 688983f); этот
инструмент — для витрин, где ядро закреплено артефактом шаблона (zona-02), как
`apply-meta-description.py`.

Якорь — возврат оболочки раздела каталога оформления Zona:
`return self.оболочка(тело, f"{титул} — {self.имя}", канон or (разд + "/"), …,
описание=f"{титул} на …{self.имя}.", …)`. Нет якоря и нет правки — отказ ДО
записи. Повторный запуск ничего не меняет. `--check` — «приведён ли файл».

    python3 automation/host/apply-pagination-canonical.py [--check] <файл> [<файл>…]
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

МЕТКА = "# Страница выдачи N>1 — номер в canonical и заголовке (apply-pagination-canonical)"
ЯКОРЬ = re.compile(
    r'^(?P<о>[ \t]+)актив = разд \+ "/"\n'
    r'(?P=о)return self\.оболочка\(тело, f"\{титул\} — \{self\.имя\}", канон or \(разд \+ "/"\),\n'
    r'(?P<п>[ \t]+)актив=актив,\n'
    r'(?P=п)описание=f"\{титул\} на (?P<mid>[^"{]*)\{self\.имя\}\.",\n',
    re.M)


def привести(текст: str) -> tuple[str, int]:
    if МЕТКА in текст:
        return текст, 0

    def замена(m: re.Match) -> str:
        о, п = m["о"], m["п"]
        return (f'{о}актив = разд + "/"\n'
                f"{о}{МЕТКА}\n"
                f"{о}# (REQ-SEO-PAGINATION п.3; D202): прежде все страницы объявляли\n"
                f"{о}# канонической первую и носили её заголовок.\n"
                f'{о}адрес = канон or (разд + "/")\n'
                f'{о}хвост = ""\n'
                f"{о}if стр > 1:\n"
                f'{о}    адрес += ("&" if "?" in адрес else "?") + f"page={{стр}}"\n'
                f'{о}    хвост = f" — страница {{стр}}"\n'
                f'{о}return self.оболочка(тело, f"{{титул}}{{хвост}} — {{self.имя}}", адрес,\n'
                f"{п}актив=актив,\n"
                f'{п}описание=f"{{титул}} на {m["mid"]}{{self.имя}}{{хвост}}.",\n')

    новый, n = ЯКОРЬ.subn(замена, текст)
    if not n:
        raise ValueError("якорь возврата оболочки раздела не найден — файл не того вида")
    return новый, n


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--check", action="store_true")
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
            print(f"{имя}: {'приведён' if новый == текст else 'не приведён'}")
            код = код or (0 if новый == текст else 1)
            continue
        if новый != текст:
            путь.write_text(новый, encoding="utf-8")
        print(f"{имя}: мест заменено {n}")
    return код


if __name__ == "__main__":
    sys.exit(main())
