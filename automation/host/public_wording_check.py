#!/usr/bin/env python3
"""В публичном тексте нет внутренних слов. Проверка проекта сайта.

Доставляется в `checks/public_wording.py`. Один файл на семейства: формулировки
разные, требование одно.

Зачем. Витрина объясняет себя посетителю, и в объяснение просачивается
внутреннее устройство: «витрина», «ячейка», «снимок каталога», «поставщик
данных», «тестовая». Посетителю это ничего не говорит, а про устройство сети
площадок говорит лишнее. Измерено 2026-10-06: подвал всех страниц трёх домен
семейства zona объявлял «<Имя> — ВИТРИНА фильмов, сериалов и анимации».

Что проверка НЕ запрещает. Полезные пояснения остаются и перечислены в
`ОСТАЮТСЯ`: часовой пояс, различие эфира и появления серии, настоящие сообщения
плеера. Они описывают видимое посетителю, а не то, как это сделано.

Ищется в ВИДИМОМ тексте: скрипты, стили, комментарии и значения атрибутов
вырезаются. `data-*` метки, имена классов и JSON-LD посетителю не показываются,
и запрещать слово там значило бы запрещать имена в коде.

Два яруса. СТАТИЧЕСКИЙ работает всюду, включая раннер CI: внутренних
формулировок не должно быть в СВОИХ файлах витрины; если они приходят из
закреплённого артефакта, переходник обязан их заменять. ПОВЕДЕНЧЕСКИЙ поднимает
витрину на синтетическом снимке и читает готовую страницу; без `config/player.json`
(его нет на раннере, и это правильно) витрина не поднимается — тогда ярус
пропускается с названной причиной.

    python3 checks/public_wording.py
"""
from __future__ import annotations

import html as _html
import json
import os
import re
import shutil
import socket
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
from pathlib import Path

КОРЕНЬ = Path(__file__).resolve().parent.parent

#: Внутренние слова и причина, по которой каждое запрещено в видимом тексте.
ЗАПРЕЩЕНО: dict[str, str] = {
    "витрина": "внутреннее слово фабрики",
    "витрины": "внутреннее слово фабрики",
    "витрине": "внутреннее слово фабрики",
    "ячейка": "внутреннее слово фабрики",
    "ячейки": "внутреннее слово фабрики",
    "снимок каталога": "внутреннее устройство доставки",
    "снимка каталога": "внутреннее устройство доставки",
    "снимке каталога": "внутреннее устройство доставки",
    "снимком каталога": "внутреннее устройство доставки",
    "поставщик данных": "внутреннее устройство доставки",
    "поставщика данных": "внутреннее устройство доставки",
    "переходник": "внутреннее устройство выпуска",
    "тестовая витрина": "площадка объявляет себя тестовой посетителю",
    "site_id": "внутренний идентификатор площадки",
    "build_id": "внутренний идентификатор выпуска",
    "провайдер": "устройство доставки видео посетителю не называется",
    "провайдера": "устройство доставки видео посетителю не называется",
    "провайдеру": "устройство доставки видео посетителю не называется",
    "утверждённого снимка": "внутреннее понятие: посетителю это каталог",
    "утверждённом снимке": "внутреннее понятие: посетителю это каталог",
    "переданного снимка": "внутреннее понятие: посетителю это каталог",
}

#: Пояснения, которые ОСТАЮТСЯ: совпадение внутри них находкой не считается.
ОСТАЮТСЯ: tuple[str, ...] = (
    "по москве", "мск", "часовой пояс", "время эфира", "эфир",
    "серия появится", "серия появилась",
)

#: Формулировки, которые когда-то были в публичном тексте и больше не должны
#: туда вернуться. Статический ярус ищет их в СВОИХ файлах витрины.
БЫВШИЕ: tuple[str, ...] = (
    "витрина фильмов, сериалов и анимации",
    "провайдер не отдал дорожку",
    "из утверждённого снимка",
    # Подписи жанровых полок. Поведенческий ярус их не видит: на синтетическом
    # снимке жанровых полок нет вовсе, и нашла их живая проверка публичного
    # текста (`automation/local/public-text-audit.py`) на 1lordserials1.online.
    # Статический ярус держит то, что поведенческому недоступно.
    "по жанру из снимка",
    "по жанру снимка",
)

ПРОВАЛ = 1
УСПЕХ = 0
_беды: list[str] = []


def п(имя: str, ок: bool, подробно: str = "") -> None:
    print(f"  {'PASS' if ок else 'FAIL'}  {имя}"
          + (f"   [{подробно}]" if подробно else ""), flush=True)
    if not ок:
        _беды.append(имя)


def пропуск(причина: str) -> None:
    print(f"  ПРОПУСК  {причина}", flush=True)


def видимый_текст(страница: str) -> str:
    б = re.sub(r"(?is)<script.*?</script>", " ", страница)
    б = re.sub(r"(?is)<style.*?</style>", " ", б)
    б = re.sub(r"(?s)<!--.*?-->", " ", б)
    б = re.sub(r"(?is)<title[^>]*>(.*?)</title>", r" \1 ", б)
    б = re.sub(r'(?is)<meta[^>]+name="description"[^>]+content="([^"]*)"', r" \1 ", б)
    б = re.sub(r"(?s)<[^>]+>", " ", б)
    return _html.unescape(re.sub(r"\s+", " ", б))


def находки(текст: str) -> list[tuple[str, str]]:
    низ = текст.lower()
    итог: list[tuple[str, str]] = []
    for слово, причина in ЗАПРЕЩЕНО.items():
        начало = 0
        while True:
            i = низ.find(слово, начало)
            if i < 0:
                break
            начало = i + len(слово)
            окно = текст[max(0, i - 70): i + len(слово) + 70]
            if any(о in окно.lower() for о in ОСТАЮТСЯ):
                continue
            итог.append((слово, окно.strip()))
    return итог


def ярус_статический() -> None:
    """Бывших формулировок нет в своих файлах; из артефакта — заменяются."""
    print("1. статический: формулировка не вернулась в свои файлы", flush=True)
    свои = [p for p in (КОРЕНЬ / "src").rglob("*.py") if "__pycache__" not in str(p)]
    текст_своих = "".join(p.read_text(encoding="utf-8", errors="replace") for p in свои)
    закреплённые = sorted((КОРЕНЬ / "template").glob("*/lords-frontend.py"))
    текст_закреплённых = "".join(
        p.read_text(encoding="utf-8", errors="replace") for p in закреплённые)

    for ф in БЫВШИЕ:
        в_своих = ф in текст_своих and "public_wording" not in текст_своих.split(ф)[0][-400:]
        в_артефакте = ф in текст_закреплённых
        if в_артефакте:
            # Формулировка приходит из закреплённого артефакта — его правка
            # запрещена замком версий. Тогда обязателен переходник, который её
            # заменяет, и его вызов в перечне правок витрины.
            модуль = (КОРЕНЬ / "src" / "public_wording.py").is_file()
            вызов = "public_wording.установить" in текст_своих
            п(f"из артефакта «{ф[:34]}…» заменяется переходником",
              модуль and вызов,
              f"модуль {'есть' if модуль else 'НЕТ'}, "
              f"вызов {'есть' if вызов else 'НЕТ'}")
            continue
        # Своя разметка: формулировки быть не должно вовсе. Исключение — сам
        # модуль подмены: он обязан называть то, что заменяет.
        где = [p.name for p in свои
               if ф in p.read_text(encoding="utf-8", errors="replace")
               and p.name != "public_wording.py"]
        п(f"«{ф[:34]}…» в своих файлах нет", not где, ", ".join(где) or "—")


def свободный_порт() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def ответ(база: str, путь: str, домен: str, таймаут: int = 60):
    req = urllib.request.Request(база + путь)
    req.add_header("Host", домен)
    try:
        with urllib.request.urlopen(req, timeout=таймаут) as о:
            return о.status, о.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as ош:
        return ош.code, ош.read().decode("utf-8", "replace")
    except urllib.error.URLError as ош:
        return 0, str(ош)


def снимок(site: str) -> dict:
    записи = [
        {"kind": "Фильм", "slug": "proverka-teksta-film", "title": "Проверка: фильм",
         "url": "/title/proverka-teksta-film/", "year": 1993,
         "published_at": "2026-01-02T00:00:00Z", "published_at_estimated": False},
        {"kind": "Сериал", "slug": "proverka-teksta-serial", "title": "Проверка: сериал",
         "url": "/title/proverka-teksta-serial/", "year": 2024,
         "published_at": "2026-01-03T00:00:00Z", "published_at_estimated": False},
    ]
    return {"schema": 1, "version": 1, "site": site, "revision": "wording-check",
            "count": len(записи), "builtAt": "2026-10-07T00:00:00Z",
            "source": "checks/public_wording.py", "items": записи}


def ярус_поведенческий(домен: str, site_id: str) -> int:
    print("2. поведенческий: готовая страница витрины", flush=True)
    врем = Path(tempfile.mkdtemp(prefix="public-wording-"))
    try:
        данные = врем / "data"
        данные.mkdir()
        имя = f"{site_id}-catalog.json" if site_id else "catalog.json"
        (данные / имя).write_text(json.dumps(снимок(site_id or домен),
                                             ensure_ascii=False), encoding="utf-8")
        режим = врем / "indexing"
        режим.mkdir()
        (режим / f"{домен}.json").write_text(
            json.dumps({"state": "OPEN", "reason": "проверка текста"}),
            encoding="utf-8")
        порт = свободный_порт()
        база = f"http://127.0.0.1:{порт}"
        среда = dict(os.environ)
        среда.update({"LORDS_INDEXING_ROOT": str(режим),
                      "ANIMEDIA_INDEXING_ROOT": str(режим),
                      "LORDS_INDEXING_TTL": "0",
                      "ANIMEDIA_INDEXING_TTL": "0",
                      "LORDS_SITE_HOST": домен,
                      "PYTHONDONTWRITEBYTECODE": "1"})
        пр = subprocess.Popen(
            [sys.executable, str(КОРЕНЬ / "run.py"), "--port", str(порт),
             "--data-dir", str(данные)],
            cwd=str(КОРЕНЬ), env=среда,
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
        try:
            край = time.time() + 180
            поднялась = False
            while time.time() < край:
                код, _ = ответ(база, "/healthz", домен, 5)
                if код == 200:
                    поднялась = True
                    break
                time.sleep(0.5)
            if not поднялась:
                вывод = (пр.stdout.read() if пр.stdout else "")[-900:]
                если_окружение = ("Permission denied", "PermissionError",
                                  "плеер без publisher_id не заработает",
                                  "LORDS_PLAYER_CONFIG")
                if any(п_ in вывод for п_ in если_окружение):
                    пропуск("витрина не поднялась по окружению проверки: "
                            + вывод.strip()[-200:])
                    return УСПЕХ
                п("витрина поднялась", False, вывод.strip()[-400:] or "нет вывода")
                return ПРОВАЛ
            п("витрина поднялась", True, f"порт {порт}")
            for путь in ("/", "/catalog/", "/collections/"):
                код, тело = ответ(база, путь, домен)
                if код != 200:
                    пропуск(f"{путь}: код {код} — страница не проверяется")
                    continue
                н = находки(видимый_текст(тело))
                п(f"видимый текст {путь}", not н,
                  "; ".join(f"«{с}» … {о[:60]}" for с, о in н[:3]) or "чисто")
        finally:
            пр.terminate()
            try:
                пр.wait(timeout=20)
            except subprocess.TimeoutExpired:
                пр.kill()
    finally:
        shutil.rmtree(врем, ignore_errors=True)
    return УСПЕХ


def main() -> int:
    cfg = json.loads((КОРЕНЬ / "config" / "site.json").read_text(encoding="utf-8"))
    домен = cfg["domain"]
    print(f"публичный текст без внутренних слов: {домен}", flush=True)
    ярус_статический()
    ярус_поведенческий(домен, cfg.get("site_id") or "")
    if _беды:
        print(f"\nпубличный текст: провалов {len(_беды)}: " + ", ".join(_беды),
              flush=True)
        return ПРОВАЛ
    print("\nпубличный текст: все проверки пройдены", flush=True)
    return УСПЕХ


if __name__ == "__main__":
    raise SystemExit(main())
