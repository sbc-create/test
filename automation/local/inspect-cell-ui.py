#!/usr/bin/env python3
"""Осмотр интерфейса витрины на стенде — без запуска штатной службы.

Зачем отдельный инструмент. Штатный запуск (`run.py`) намеренно отказывается
стартовать без `config/player.json`: плеер без publisher_id не заработает, и
это правильная защита. Но осмотреть каталог, поиск, карточку, навигацию и
мобильную вёрстку можно и до появления номера — страницы к плееру отношения не
имеют.

Поэтому здесь поднимается САМ рантайм (`src/<entrypoint>`) с окружением,
собранным по `config/site.json` той же подстановкой `<data>`/`<app>`, что
делает `run.py`. Отличие ровно одно и названо в отчёте: `LORDS_PLAYER_CONFIG`
не указывает на существующий файл, поэтому поверхность плеера не проверяется.

ЭТО ОСМОТР, А НЕ ВЫПУСК. Инструмент не ставит релиз, не трогает `/srv`, не
включает службы и ничего не пишет в данные витрины: каталог данных копируется
во временный каталог и после осмотра удаляется.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import signal
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
from pathlib import Path

КОРЕНЬ = Path(__file__).resolve().parents[2]

#: Что осматриваем. Для каждой поверхности — что обязано быть в ответе.
ПОВЕРХНОСТИ = [
    ("/", "главная", ["<title", "href="]),
    ("/catalog/", "каталог", ["<title", "href="]),
    ("/search/?q=%D0%B2%D0%B5%D1%82%D0%B5%D1%80", "поиск", ["<title"]),
    ("/collections/", "подборки", ["<title"]),
    ("/robots.txt", "robots.txt", []),
    ("/sitemap.xml", "карта сайта", []),
    ("/healthz", "healthz", []),
]


def окружение(конфиг: dict, проект: Path, данные: Path) -> dict:
    env = dict(os.environ)
    for имя, шаблон in (конфиг.get("environment") or {}).items():
        env[имя] = (str(шаблон).replace("<data>", str(данные))
                    .replace("<app>", str(проект)))
    контакт = str(конфиг.get("contact_email") or "").strip()
    if контакт:
        env["SITE_CONTACT_EMAIL"] = контакт
    домен = str(конфиг.get("domain") or "").strip()
    if домен:
        env["LORDS_INDEXING_SITE"] = домен
    разрешение = (конфиг.get("indexing") or {}).get("release_permits_open")
    env["LORDS_INDEXING_RELEASE_PERMITS_OPEN"] = "true" if разрешение is True else "false"
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    return env


def ответ(адрес: str, таймаут: float = 30.0) -> tuple[int, bytes, dict]:
    try:
        с = urllib.request.urlopen(адрес, timeout=таймаут)
        return с.status, с.read(), dict(с.headers)
    except urllib.error.HTTPError as ош:
        return ош.code, ош.read(), dict(ош.headers)
    except Exception as ош:  # noqa: BLE001 — любая сетевая беда названа кодом 0
        return 0, str(ош).encode(), {}


def main() -> int:
    р = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    р.add_argument("--site", required=True)
    р.add_argument("--project", default=None, help="каталог проекта витрины")
    р.add_argument("--data", required=True, help="каталог с данными каталога")
    р.add_argument("--port", type=int, default=19200)
    р.add_argument("--keep", action="store_true", help="не удалять временные данные")
    а = р.parse_args()

    проект = Path(а.project or (КОРЕНЬ / "var" / "new-sites" / а.site))
    конфиг = json.loads((проект / "config" / "site.json").read_text(encoding="utf-8"))
    точка = проект / "src" / конфиг["entrypoint"]
    if not точка.is_file():
        print(f"ОТКАЗ: нет точки входа {точка}", file=sys.stderr)
        return 2

    врем = Path(tempfile.mkdtemp(prefix=f"inspect-{а.site}-"))
    данные = врем / "data"
    данные.mkdir()
    for ф in Path(а.data).glob(f"{а.site}-*.json"):
        shutil.copy(ф, данные / ф.name)
    скопировано = sorted(п.name for п in данные.iterdir())
    print(f"стенд: {врем}; данных файлов {len(скопировано)}: {', '.join(скопировано)}")

    env = окружение(конфиг, проект, данные)
    плеер = Path(env.get("LORDS_PLAYER_CONFIG", ""))
    print(f"плеер: {'есть' if плеер.is_file() else 'ОТСУТСТВУЕТ — поверхность плеера не проверяется'}")

    процесс = subprocess.Popen(
        [sys.executable, str(точка), "--port", str(а.port)],
        cwd=проект, env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    база = f"http://127.0.0.1:{а.port}"
    готово = False
    for _ in range(90):
        код, _, _ = ответ(f"{база}/healthz", таймаут=3)
        if код:
            готово = True
            break
        if процесс.poll() is not None:
            break
        time.sleep(1)

    итог: list[dict] = []
    if not готово:
        вывод = (процесс.stdout.read() if процесс.stdout else b"").decode("utf-8", "replace")
        print("ОТКАЗ: рантайм не поднялся")
        print("\n".join(вывод.splitlines()[-12:]))
        процесс.kill()
        if not а.keep:
            shutil.rmtree(врем, ignore_errors=True)
        return 1

    print(f"\n{'поверхность':16} {'код':>4} {'байт':>9}  заметки")
    for путь, имя, обязательно in ПОВЕРХНОСТИ:
        начало = time.time()
        код, тело, заголовки = ответ(база + путь)
        текст = тело.decode("utf-8", "replace")
        нет = [м for м in обязательно if м not in текст]
        робот = заголовки.get("X-Robots-Tag", "")
        заметки = []
        if нет:
            заметки.append(f"нет маркеров {нет}")
        if робот:
            заметки.append(f"X-Robots-Tag: {робот}")
        заметки.append(f"{time.time() - начало:.2f} с")
        print(f"{имя:16} {код:>4} {len(тело):>9}  {'; '.join(заметки)}")
        итог.append({"path": путь, "code": код, "bytes": len(тело),
                     "missing": нет, "x_robots": робот})

    # Карточка произведения: идентификатор берётся из каталога.
    каталог = json.loads((данные / f"{а.site}-catalog.json").read_text(encoding="utf-8"))
    первый = (каталог.get("items") or [{}])[0]
    слаг = первый.get("slug") or первый.get("id") or ""
    if слаг:
        код, тело, заголовки = ответ(f"{база}/title/{слаг}/")
        текст = тело.decode("utf-8", "replace")
        название = (первый.get("title") or первый.get("name") or "")
        есть_название = bool(название) and название in текст
        print(f"{'карточка':16} {код:>4} {len(тело):>9}  слаг {слаг}; "
              f"название в разметке: {'да' if есть_название else 'НЕТ'}")
        итог.append({"path": f"/title/{слаг}/", "code": код, "bytes": len(тело),
                     "title_in_markup": есть_название})

        # Мобильная вёрстка: viewport и отсутствие горизонтальной прокрутки
        # проверяются по разметке — без браузера это предел измерения.
        viewport = re.search(r'<meta[^>]+name="viewport"[^>]*>', текст)
        print(f"{'мобильная':16} {'—':>4} {'—':>9}  viewport: "
              f"{'есть' if viewport else 'НЕТ'}")
        итог.append({"viewport": bool(viewport)})

    процесс.send_signal(signal.SIGTERM)
    try:
        процесс.wait(timeout=15)
    except subprocess.TimeoutExpired:
        процесс.kill()
    if not а.keep:
        shutil.rmtree(врем, ignore_errors=True)
    беды = [з for з in итог if з.get("code") not in (None, 200)
            and з.get("path") not in ("/sitemap.xml",)]
    print(f"\nповерхностей с кодом не 200 (кроме карты сайта): {len(беды)}")
    for з in беды:
        print(f"   {з['path']}: код {з['code']}")
    return 1 if беды else 0


if __name__ == "__main__":
    raise SystemExit(main())
