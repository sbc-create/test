#!/usr/bin/env python3
"""Доказать, что дыра в проверке публичных текстов БЫЛА, а не только закрыта.

Проходящая проверка доказывает сегодняшнее состояние и ничего не говорит о
прошлом. Утверждение «проверка молчала» требует прогона ПРЕЖНЕЙ её версии на
тех же данных — она берётся из git, данные собираются здесь.

Две вёрстки одной и той же фразы проверяются отдельно: у витрины на профиле
`lords-curated` публичный текст печатает наложение (`overlay/`), и фраза в
исходнике бывает разбита переносом строковых литералов. Прежняя версия читала
только `src/` и сравнивала подстрокой по файлу — то есть не видела ни того, ни
другого.

Ничего не меняет: собирает временные ячейки и запускает в них проверку.

    python3 automation/local/prove-wording-check-hole.py
    python3 automation/local/prove-wording-check-hole.py --ref HEAD~1
"""
from __future__ import annotations

import argparse
import json
import pathlib
import shutil
import subprocess
import sys
import tempfile

КОРЕНЬ = pathlib.Path(__file__).resolve().parents[2]
ИСТОЧНИК = КОРЕНЬ / "automation" / "host" / "public_wording_check.py"
ОТНОСИТЕЛЬНО = "automation/host/public_wording_check.py"

#: Фраза из таблицы владельца, свёрстанная ПЕРЕНОСОМ литералов — ровно так, как
#: она лежала в наложении живой витрины.
ПЕРЕНОСОМ = '''
def _о_каталоге() -> str:
    return (
        "Каталог Lordserials опирается на переданные жанры, годы и оценки. "
        "Редакционные пометки — только при наличии подтверждённого "
        "источника."
    )
'''

#: Та же формулировка одной строкой: вторая вёрстка.
ОДНОЙ_СТРОКОЙ = '''
def _вступление() -> str:
    return "Алгоритмические списки не выдаются за редакционный выбор."
'''

ЧИСТО = '''
def _о_каталоге() -> str:
    return "В каталоге Lordserials фильм или сериал можно выбрать по жанру."
'''


def ячейка(куда: pathlib.Path, тело_проверки: str, наложение: str) -> pathlib.Path:
    (куда / "checks").mkdir(parents=True)
    (куда / "src").mkdir()
    (куда / "overlay").mkdir()
    (куда / "config").mkdir()
    (куда / "checks" / "public_wording.py").write_text(тело_проверки,
                                                       encoding="utf-8")
    (куда / "src" / "lords-frontend.py").write_text(ЧИСТО, encoding="utf-8")
    (куда / "overlay" / "view.py").write_text(наложение, encoding="utf-8")
    (куда / "config" / "site.json").write_text(
        json.dumps({"domain": "проба.test", "site_id": "проба"},
                   ensure_ascii=False), encoding="utf-8")
    return куда


def статический_ярус(вывод: str) -> list[str]:
    """Только строки первого яруса: второй без плеера пропускается."""
    строки: list[str] = []
    for с in вывод.splitlines():
        if с.startswith("2."):
            break
        строки.append(с)
    return строки


def поймала(тело: str, наложение: str) -> tuple[bool, str]:
    врем = pathlib.Path(tempfile.mkdtemp())
    try:
        проект = ячейка(врем, тело, наложение)
        г = subprocess.run([sys.executable, "checks/public_wording.py"],
                           cwd=проект, capture_output=True, text=True,
                           timeout=300)
        ярус = статический_ярус((г.stdout or "") + (г.stderr or ""))
        return any("FAIL" in с for с in ярус), "\n".join(ярус)
    finally:
        shutil.rmtree(врем, ignore_errors=True)


def главное(аргв=None) -> int:
    р = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    р.add_argument("--ref", default="HEAD~1",
                   help="коммит, из которого берётся ПРЕЖНЯЯ версия проверки")
    опции = р.parse_args(аргв)

    прежняя = subprocess.run(
        ["git", "show", f"{опции.ref}:{ОТНОСИТЕЛЬНО}"],
        cwd=КОРЕНЬ, capture_output=True, text=True)
    if прежняя.returncode != 0:
        print(f"прежняя версия не прочитана из {опции.ref}: "
              f"{прежняя.stderr.strip()[:160]}", file=sys.stderr)
        return 2
    if "overlay" in прежняя.stdout:
        print(f"в {опции.ref} правка уже есть — сравнивать нечего. "
              "Назовите коммит до правки через --ref.", file=sys.stderr)
        return 2

    новая = ИСТОЧНИК.read_text(encoding="utf-8")
    расхождений = 0
    for подпись, наложение in (("фраза одной строкой", ОДНОЙ_СТРОКОЙ),
                               ("фраза переносом литералов", ПЕРЕНОСОМ)):
        было, _ = поймала(прежняя.stdout, наложение)
        стало, ярус = поймала(новая, наложение)
        print(f"{подпись:28s} прежняя: {'ПОЙМАЛА' if было else 'молчит':8s} "
              f"новая: {'ПОЙМАЛА' if стало else 'молчит'}")
        if было or not стало:
            расхождений += 1
            print(ярус)
    if расхождений:
        print(f"\nожидание не подтвердилось у {расхождений} случаев: прежняя "
              "версия обязана молчать, новая — ловить", file=sys.stderr)
        return 1
    print("\nобе дыры подтверждены: прежняя версия молчала, новая ловит")
    return 0


if __name__ == "__main__":
    raise SystemExit(главное())
