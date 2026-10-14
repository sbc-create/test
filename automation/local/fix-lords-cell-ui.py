#!/usr/bin/env python3
"""Правки интерфейса витрин партии K2 — по осмотру в браузере, не по вкусу.

Каждая правка названа дефектом, который её вызвал, и проверяется отдельно:
инструмент отказывает, если место правки не найдено (значит рантайм изменился и
править вслепую нельзя) или если правка уже стоит (тогда просто сообщает).

Дефекты, найденные осмотром 2026-10-14 на стенде lordfilm.group:

1. **Имя сайта в шапке обрезано**: «LORDFILM.GROU». Причина измерена в CSS:
   `.hd__logo{max-width:min(42vw,220px)}` и 240px на компьютере при имени из
   14–17 знаков прописными с межбуквенным интервалом. Обрезка молчаливая —
   `overflow:hidden`, и многоточие во флексе не видно.

2. **В подвале нет адреса обратной связи.** Контракт сети прямо требует:
   `config/site.json` несёт `contact_email`, `run.py` кладёт его в
   `SITE_CONTACT_EMAIL`, рантайм выводит строку подвала со ссылкой `mailto:`.
   В рантайме этой партии переменная не встречается ВООБЩЕ — проверено
   поиском: ни `SITE_CONTACT_EMAIL`, ни `mailto`. Проверка проекта
   `contact_email.py` этого не ловит: она сверяет цепочку до переменной, а не
   разметку страницы.

3. **Техническая подпись в подвале**: «жанры появятся из sidecar» —
   внутреннее слово в тексте для посетителя.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

КОРЕНЬ = Path(__file__).resolve().parents[2]

ЛОГО_БЫЛО = """.hd__logo{display:flex;align-items:center;gap:9px;font-weight:800;font-size:17px;
letter-spacing:.5px;text-transform:uppercase;color:@INK@;flex:0 1 auto;
max-width:min(42vw,220px);overflow:hidden;white-space:nowrap;text-overflow:ellipsis}
@media(min-width:1024px){.hd__logo{font-size:19px;max-width:240px}}"""

ЛОГО_СТАЛО = """.hd__logo{display:flex;align-items:center;gap:9px;font-weight:800;font-size:16px;
letter-spacing:.3px;text-transform:uppercase;color:@INK@;flex:0 1 auto;
max-width:min(62vw,300px);overflow:hidden;white-space:nowrap;text-overflow:ellipsis}
/* Ширина подобрана по САМОМУ ДЛИННОМУ имени партии: lordserial.spb.ru — 17
   знаков прописными. При прежних 220/240px оно обрезалось молча, и в шапке
   стояло «LORDFILM.GROU». Межбуквенный интервал уменьшен с .5 до .3px по той
   же причине: он добавлял имени почти десять пикселей ни за чем. */
@media(min-width:1024px){.hd__logo{font-size:19px;max-width:360px}}"""

КОНТАКТ_ФУНКЦИЯ = '''

def _контакт_подвала() -> str:
    """Строка обратной связи для подвала.

    Адрес берётся из окружения, куда его кладёт `run.py` из `config/site.json`
    (ключ `contact_email`). Пустое значение — не повод подставить умолчание:
    выдуманный адрес хуже отсутствующего, потому что письма по нему уходят в
    никуда и никто об этом не узнаёт. Поэтому при пустом или негодном значении
    строка не выводится вовсе.

    Ссылка настоящая `mailto:`, и сам адрес остаётся текстом: его копируют
    выделением чаще, чем нажимают.
    """
    import os as _os

    адрес = str(_os.environ.get("SITE_CONTACT_EMAIL") or "").strip()
    if not адрес or "@" not in адрес or " " in адрес:
        return ""
    видимый = html.escape(адрес)
    return (f'<span class="ft__contact">Обратная связь: '
            f'<a href="mailto:{видимый}">{видимый}</a></span>')
'''

ПОДВАЛ_БЫЛО = """            f'<div class="ft__bar"><span>© {html.escape(self.имя)}</span>'
            '<span>Каталог фильмов и сериалов</span></div>'"""
ПОДВАЛ_СТАЛО = """            f'<div class="ft__bar"><span>© {html.escape(self.имя)}</span>'
            '<span>Каталог фильмов и сериалов</span>'
            f'{_контакт_подвала()}</div>'"""

ЗАГЛУШКА_БЫЛО = '{жанры or "<span>жанры появятся из sidecar</span>"}'
ЗАГЛУШКА_СТАЛО = '{жанры or ""}'

СТИЛЬ_КОНТАКТА = """.ft__contact{overflow-wrap:anywhere}
.ft__contact a{color:inherit;text-decoration:underline}
"""
СТИЛЬ_ЯКОРЬ = ".hd__mark{width:30px;height:30px;"


def правка(текст: str, было: str, стало: str, имя: str) -> tuple[str, str]:
    if стало in текст and было not in текст:
        return текст, f"{имя}: уже стоит"
    if было not in текст:
        return текст, f"{имя}: МЕСТО НЕ НАЙДЕНО"
    return текст.replace(было, стало, 1), f"{имя}: внесена"


def main() -> int:
    р = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    р.add_argument("--site", required=True)
    р.add_argument("--check", action="store_true", help="только показать, не писать")
    а = р.parse_args()

    путь = КОРЕНЬ / "var" / "new-sites" / а.site / "src" / "lords-frontend.py"
    if not путь.is_file():
        print(f"ОТКАЗ: нет {путь}", file=sys.stderr)
        return 2
    текст = исходный = путь.read_text(encoding="utf-8")
    отчёт: list[str] = []

    текст, с = правка(текст, ЛОГО_БЫЛО, ЛОГО_СТАЛО, "имя сайта в шапке")
    отчёт.append(с)

    # Функция контакта ставится рядом с другими помощниками разметки — перед
    # первым классом, который ей пользуется.
    if "_контакт_подвала" not in текст:
        якорь = "\nclass Вид:"
        if якорь in текст:
            текст = текст.replace(якорь, КОНТАКТ_ФУНКЦИЯ + якорь, 1)
            отчёт.append("функция контакта: внесена")
        else:
            отчёт.append("функция контакта: МЕСТО НЕ НАЙДЕНО")
    else:
        отчёт.append("функция контакта: уже стоит")

    текст, с = правка(текст, ПОДВАЛ_БЫЛО, ПОДВАЛ_СТАЛО, "строка подвала")
    отчёт.append(с)
    текст, с = правка(текст, ЗАГЛУШКА_БЫЛО, ЗАГЛУШКА_СТАЛО, "техподпись про sidecar")
    отчёт.append(с)
    текст, с = правка(текст, СТИЛЬ_ЯКОРЬ, СТИЛЬ_КОНТАКТА + СТИЛЬ_ЯКОРЬ,
                      "стиль строки контакта")
    отчёт.append(с)

    беда = [с for с in отчёт if "НЕ НАЙДЕНО" in с]
    for с in отчёт:
        print(f"   {с}")
    if беда:
        print("ОТКАЗ: часть мест не найдена — рантайм изменился, вслепую не правлю",
              file=sys.stderr)
        return 1
    if а.check:
        print("проверка: файл не изменён")
        return 0
    if текст != исходный:
        путь.write_text(текст, encoding="utf-8")
        print(f"записано: {путь}")
    else:
        print("изменений не потребовалось")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
