"""Адрес страницы из названия: чистое преобразование текста.

Жила эта функция в `factory/lords/live_catalog.py`, то есть внутри семейства
витрин, а нужна была и управляющему контуру: `adapters/lords_seo_binding` брал
её оттуда. Этот единственный импорт держал цикл `site_engine ↔ lords`, а цикл
означает, что ни одну из подсистем нельзя вынести, не вынеся вторую.

Никакого знания о витринах в функции нет: она превращает строку в строку.
Место ей в общей опоре, которую знают все и которая не знает никого.

Цена ошибки здесь выше обычной: вывод — адреса страниц на боевых доменах.
Перенос сделан дословно и закреплён `tests/unit/test_slug_characterization.py`,
включая три реальных боевых адреса.
"""
from __future__ import annotations

import re
import unicodedata

_TRANSLIT = {
    "а": "a", "б": "b", "в": "v", "г": "g", "д": "d", "е": "e", "ё": "e", "ж": "zh",
    "з": "z", "и": "i", "й": "y", "к": "k", "л": "l", "м": "m", "н": "n", "о": "o",
    "п": "p", "р": "r", "с": "s", "т": "t", "у": "u", "ф": "f", "х": "h", "ц": "c",
    "ч": "ch", "ш": "sh", "щ": "sch", "ъ": "", "ы": "y", "ь": "", "э": "e",
    "ю": "yu", "я": "ya",
}


def slugify(value: str) -> str:
    """Адрес из названия. Пусто на входе — пусто на выходе, без выдумки."""
    lowered = (value or "").strip().lower()
    out: list[str] = []
    for char in lowered:
        if char in _TRANSLIT:
            out.append(_TRANSLIT[char])
        elif char.isalnum() and char.isascii():
            out.append(char)
        elif unicodedata.category(char).startswith("L") or unicodedata.category(char) == "Nd":
            # Незнакомая письменность: пропускаем символ, а не весь тайтл.
            continue
        else:
            out.append("-")
    slug = re.sub(r"-{2,}", "-", "".join(out)).strip("-")
    return slug[:80]
