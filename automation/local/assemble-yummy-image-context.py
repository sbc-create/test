#!/usr/bin/env python3
"""Сборка контекста образа Yummy из подготовленных правок. Один вход на все цели.

Зачем отдельный сборщик. Контекстов три (четыре витрины на исправленном образе,
`.site` на своём, и проверочный), а шаги в них одни и те же: положить правленые
файлы, положить тесты, собрать Dockerfile из общего тестового шага. Руками это
расходится на второй сборке — и расходилось: в одном контексте тестовый шаг
остался от опыта с конфигурацией, в другом был уже исправленный.

    python3 automation/local/assemble-yummy-image-context.py \\
        --out var/yummy-build/d3d4-fixed --base yummyani/web:rel-944c932e76ff \\
        --title "D3 + D4 для витрин на исправленном образе" \\
        --src var/yummy-build/d3-fixed/src --src var/yummy-build/d4-fixed/src \\
        --test var/yummy-build/shared/freshness.test.ts \\
        --test var/yummy-build/shared/walk-budget.test.ts
"""
from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path

КОРЕНЬ = Path(__file__).resolve().parents[2]
ШАГ_ТЕСТОВ = КОРЕНЬ / "var" / "yummy-build" / "shared" / "test-step.dockerfile"

ШАПКА = """# {title}
#
# Образ собирается ОТ работающего, а не из ветки: исходники ветки разошлись с
# установленными образами (ревизий 944c932e76ff и 9cbfac20fbe8 в локальных
# копиях нет вовсе), и сборка «из ветки» принесла бы на витрину две недели
# чужой работы вместе с правкой.
#
# B031 не затрагивается: `seo-core/truncate.ts` в сборку не входит, и образ
# наследует поведение заголовков того образа, от которого собран. Для `.site`
# это и есть условие эксперимента — обрезанный заголовок у контроля.
ARG BASE={base}
FROM ${{BASE}}

WORKDIR /app

COPY src /app/src

"""

СБОРКА = """
# Сборка приложения теми же значениями окружения, какими её делает штатный
# `Dockerfile` приложения (стадия builder): APP_ENV=development и заглушки,
# указывающие никуда. Поэтому сборка не требует ни базы, ни Redis, ни
# SITE_PROFILE, и поэтому в базовом образе в предсобранных страницах стоит
# `http://build.invalid`.
#
# `NEXT_PUBLIC_*` обязаны совпадать с рабочими: они инлайнятся в клиентский
# бандл и после сборки не меняются. Значения взяты из окружения работающего
# контейнера и совпадают со штатной сборкой.
#
# Ни одно значение в образ не запекается: они действуют только на время
# команды. Секретов среди них нет.
RUN NEXT_TELEMETRY_DISABLED=1 \\
    APP_ENV=development \\
    APP_URL=http://build.invalid \\
    DATABASE_URL=postgresql://build:build@build.invalid:5432/build?schema=public \\
    REDIS_URL=redis://build.invalid:6379 \\
    SMTP_HOST=build.invalid \\
    SMTP_PORT=1025 \\
    NEXT_PUBLIC_CDNVIDEOHUB_PLAYER_MODE=live \\
    NEXT_PUBLIC_CDNVIDEOHUB_SCRIPT_URL=https://player.cdnvideohub.com/s2/stable/video-player.umd.js \\
    node_modules/.bin/next build
"""

#: Файлы, попадание которых в контекст означает ошибку сборки контекста.
ЗАПРЕЩЕНО = {
    "seo-core/truncate.ts": "условие эксперимента B031 (обрезка заголовка)",
    "app/(portal)/page.tsx": "главная витрины — не предмет этих правок",
    "app/globals.css": "оформление — не предмет этих правок",
    "modules/catalog/home-shelves.ts": "полки главной — не предмет этих правок",
}


def главное(аргв: list[str] | None = None) -> int:
    р = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    р.add_argument("--out", required=True)
    р.add_argument("--base", required=True)
    р.add_argument("--title", required=True)
    р.add_argument("--src", action="append", default=[],
                   help="каталог `src` с правлеными файлами (можно несколько)")
    р.add_argument("--test", action="append", default=[],
                   help="файл теста (можно несколько)")
    а = р.parse_args(аргв)

    выход = Path(а.out)
    if выход.exists():
        shutil.rmtree(выход)
    (выход / "src").mkdir(parents=True)
    (выход / "tests-patch").mkdir()

    положено: list[str] = []
    for каталог in а.src:
        корень = Path(каталог)
        if not корень.is_dir():
            print(f"НЕ СОБРАНО: нет каталога {корень}")
            return 2
        for файл in sorted(корень.rglob("*")):
            if not файл.is_file():
                continue
            отн = файл.relative_to(корень)
            цель = выход / "src" / отн
            цель.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(файл, цель)
            положено.append(str(отн))

    for файл, причина in ЗАПРЕЩЕНО.items():
        if (выход / "src" / файл).exists():
            print(f"НЕ СОБРАНО: в контексте оказался {файл} — {причина}")
            return 2

    for тест in а.test:
        путь = Path(тест)
        if not путь.is_file():
            print(f"НЕ СОБРАНО: нет теста {путь}")
            return 2
        текст = путь.read_text(encoding="utf-8")
        # Тесты импортируют ПРОИЗВОДНУЮ копию дерева, которую собирает тестовый
        # шаг. Подстановка делается здесь, чтобы один и тот же файл теста
        # годился и для запуска вне образа.
        текст = текст.replace('from "../src/', 'from "./src/')
        (выход / "tests-patch" / путь.name).write_text(текст, encoding="utf-8")

    шаг = ШАГ_ТЕСТОВ.read_text(encoding="utf-8")
    (выход / "Dockerfile").write_text(
        ШАПКА.format(title=а.title, base=а.base) + шаг + СБОРКА,
        encoding="utf-8")

    print(f"контекст: {выход}")
    print(f"   файлов приложения: {len(положено)}")
    for имя in положено:
        print(f"      {имя}")
    print(f"   тестов: {len(а.test)}")
    print(f"   база: {а.base}")
    print(f"   запрещённых к переносу проверено: {len(ЗАПРЕЩЕНО)}")
    return 0


if __name__ == "__main__":
    sys.exit(главное())
