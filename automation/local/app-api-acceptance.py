#!/usr/bin/env python3
"""Приёмка читающего API приложения. Один и тот же прогон до и после установки.

Зачем отдельный инструмент. До установки служба доступна только на петле, после
— по публичному адресу, и проверять надо ТО ЖЕ САМОЕ: иначе «проверено на
127.0.0.1» незаметно подменяет «работает у клиента». Поэтому база задаётся
аргументом, а список проверок один.

    # до установки, служба поднята на петле:
    python3 automation/local/app-api-acceptance.py --base http://127.0.0.1:9180 \\
        --key-file <файл ключа>

    # после установки, снаружи (root не нужен: файл ключа доступен учётной
    # записи службы):
    python3 automation/local/app-api-acceptance.py \\
        --base https://animedia.icu --key-file /etc/app-read-api/client-key

Ключ читается из ФАЙЛА и ни в вывод, ни в код возврата не попадает. Инструмент
только читает: ни одного запроса, меняющего состояние, здесь нет (служба и не
умеет — маршрут отвергает всё, кроме GET и HEAD).

Что проверяется и почему именно так:

* состояние по пути ВНУТРИ префикса `/api/app/v1/healthz` — корневой `/healthz`
  принадлежит витрине и наружу не отдан;
* отказ без ключа и с неверным ключом — 401, а не пустой список: «нет доступа»
  и «нет данных» должны различаться;
* поиск, карточка, сезоны, серии, обложка — путь клиента целиком;
* источники видео — ОЖИДАЕТСЯ пустой список с причиной
  `NO_SOURCE_CONTRACT_RELEASED`. Это не сбой, а постоянное ограничение
  контракта, и проверка падает, если список внезапно непустой: прямых ссылок у
  фабрики нет, и появиться они могут только с разрешением провайдера.

Код возврата: 0 — всё сошлось; 1 — есть расхождения; 2 — проверять нечем.
"""
from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

ТАЙМАУТ = 30
ПРИЧИНА_БЕЗ_ИСТОЧНИКА = "NO_SOURCE_CONTRACT_RELEASED"


class Приёмка:
    def __init__(self, база: str, ключ: str) -> None:
        self.база = база.rstrip("/")
        self.ключ = ключ
        self.расхождений = 0

    # --- запрос ---------------------------------------------------------
    def запрос(self, путь: str, *, ключ: str | None = "свой"):
        заголовки = {"User-Agent": "app-api-acceptance"}
        значение = self.ключ if ключ == "свой" else ключ
        if значение:
            заголовки["X-App-Key"] = значение
        зап = urllib.request.Request(self.база + путь, headers=заголовки)
        try:
            with urllib.request.urlopen(зап, timeout=ТАЙМАУТ) as о:
                сырое = о.read()
                тело = json.loads(сырое) if сырое[:1] in (b"{", b"[") else сырое[:200]
                return о.status, тело, dict(о.headers)
        except urllib.error.HTTPError as сбой:
            сырое = сбой.read()
            try:
                тело = json.loads(сырое)
            except ValueError:
                тело = сырое[:200].decode("utf-8", "replace")
            return сбой.code, тело, dict(сбой.headers)
        except urllib.error.URLError as сбой:
            return 0, f"соединение не состоялось: {сбой.reason}", {}

    def шаг(self, имя: str, сошлось: bool, подробно: str) -> bool:
        метка = "ок " if сошлось else "НЕТ"
        print(f"   [{метка}] {имя:34} {подробно}")
        if not сошлось:
            self.расхождений += 1
        return сошлось

    # --- проверки -------------------------------------------------------
    def состояние(self) -> dict:
        код, тело, _ = self.запрос("/api/app/v1/healthz", ключ=None)
        if код == 308:
            self.шаг("состояние", False,
                     "308 — перенаправление витрины: маршрута API нет, "
                     "служба не установлена")
            return {}
        if код == 404:
            self.шаг("состояние", False,
                     "404 — маршрута нет: включите location /api/app/v1/")
            return {}
        if код in (502, 504):
            self.шаг("состояние", False,
                     f"{код} — маршрут есть, служба не отвечает")
            return {}
        if код == 503 and isinstance(тело, dict):
            self.шаг("состояние", False,
                     f"503 — ключ клиента на сервере не настроен: "
                     f"{тело.get('reason')}")
            return {}
        сошлось = код == 200 and isinstance(тело, dict) and тело.get("ready") is True
        self.шаг("состояние", сошлось,
                 f"код {код}, ready={тело.get('ready') if isinstance(тело, dict) else '—'}, "
                 f"тайтлов {тело.get('titles') if isinstance(тело, dict) else '—'}, "
                 f"поколение {тело.get('catalogRevision') if isinstance(тело, dict) else '—'}")
        return тело if isinstance(тело, dict) else {}

    def отказы(self) -> None:
        код, _тело, _ = self.запрос("/api/app/v1/titles?sort=added&limit=1", ключ=None)
        self.шаг("без ключа — отказ", код == 401, f"код {код}, ожидается 401")
        код, _тело, _ = self.запрос("/api/app/v1/titles?sort=added&limit=1",
                                    ключ="x" * 32)
        self.шаг("с неверным ключом — отказ", код == 401, f"код {код}, ожидается 401")

    def каталог(self) -> str:
        код, тело, заг = self.запрос("/api/app/v1/titles?sort=added&limit=10")
        пункты = тело.get("items") if isinstance(тело, dict) else None
        self.шаг("список главной", код == 200 and bool(пункты),
                 f"код {код}, карточек {len(пункты or [])}, "
                 f"поколение в заголовке {заг.get('X-Catalog-Revision', '—')}")
        if not пункты:
            return ""
        self.обложки(пункты)
        первый = пункты[0].get("contentId", "")
        слово = (пункты[0].get("title") or пункты[0].get("originalTitle") or "")[:12]
        if слово:
            код, тело, _ = self.запрос(
                "/api/app/v1/search?" + urllib.parse.urlencode({"q": слово}))
            найдено = тело.get("items") if isinstance(тело, dict) else None
            self.шаг("поиск", код == 200 and bool(найдено),
                     f"код {код}, по {слово!r} найдено {len(найдено or [])}")
        return первый

    def карточка(self, ид: str) -> None:
        код, тело, _ = self.запрос(f"/api/app/v1/titles/{ид}")
        если_словарь = тело if isinstance(тело, dict) else {}
        self.шаг("карточка", код == 200 and bool(если_словарь.get("contentId")),
                 f"код {код}, название "
                 f"{(если_словарь.get('title') or если_словарь.get('originalTitle') or '—')[:28]!r}")

    def обложки(self, пункты: list[dict]) -> None:
        """Обложка проверяется по ВЫБОРКЕ, а не по одной карточке.

        В снимке есть записи без обложки (6 из 8547 на 2026-10-10) — это факт
        данных, а не поломка службы. Проверка на одной карточке поэтому
        случайна: ей может попасться как раз такая запись, и исправная служба
        будет объявлена расхождением. Порог 80% ловит настоящую поломку —
        исчезновение адресов обложек целиком.
        """
        с_обложкой = 0
        пример = ""
        for пункт in пункты:
            код, тело, _ = self.запрос(f"/api/app/v1/titles/{пункт.get('contentId')}")
            если_словарь = тело if isinstance(тело, dict) else {}
            худ = если_словарь.get("artwork") or {}
            адрес = худ.get("posterUrl") if isinstance(худ, dict) else None
            if адрес:
                с_обложкой += 1
                пример = пример or адрес
        доля = с_обложкой / len(пункты) if пункты else 0
        self.шаг("обложки в выборке", доля >= 0.8,
                 f"{с_обложкой} из {len(пункты)}"
                 + (f", например {пример[:52]}" if пример else ""))

    def серии(self, ид: str) -> None:
        код, тело, _ = self.запрос(f"/api/app/v1/titles/{ид}/seasons")
        сезоны = тело if isinstance(тело, list) else (
            тело.get("seasons") if isinstance(тело, dict) else None)
        self.шаг("сезоны", код == 200 and isinstance(сезоны, list),
                 f"код {код}, сезонов {len(сезоны or [])}")
        if not сезоны:
            return
        ид_сезона = сезоны[0].get("seasonId")
        код, тело, _ = self.запрос(f"/api/app/v1/seasons/{ид_сезона}/episodes")
        серии = тело if isinstance(тело, list) else (
            тело.get("episodes") if isinstance(тело, dict) else None)
        self.шаг("серии", код == 200 and isinstance(серии, list),
                 f"код {код}, серий {len(серии or [])} — ЧИСЛО ИЗ СНИМКА, "
                 "доказательством воспроизведения не является")
        if серии:
            self.источники(f"/api/app/v1/episodes/{серии[0].get('episodeId')}/sources",
                           "источники серии")

    def источники(self, путь: str, имя: str) -> None:
        код, тело, _ = self.запрос(путь)
        д = тело if isinstance(тело, dict) else {}
        пусто = д.get("sources") == []
        причина = д.get("reason")
        self.шаг(имя, код == 200 and пусто and причина == ПРИЧИНА_БЕЗ_ИСТОЧНИКА,
                 f"код {код}, sources={д.get('sources')}, reason={причина} — "
                 "честное отсутствие прямого потока")

    def фильм(self, ид: str) -> None:
        self.источники(f"/api/app/v1/episodes/movie/sources?contentId={ид}",
                       "источники фильма")


def главное(аргв: list[str] | None = None) -> int:
    р = argparse.ArgumentParser(description="приёмка читающего API приложения")
    р.add_argument("--base", required=True,
                   help="например http://127.0.0.1:9180 или https://animedia.icu")
    р.add_argument("--key-file", required=True, help="файл с ключом клиента")
    а = р.parse_args(аргв)

    файл = Path(а.key_file)
    try:
        ключ = файл.read_text(encoding="utf-8").strip()
    except OSError as сбой:
        print(f"ключ не прочитан: {сбой}", file=sys.stderr)
        return 2
    if not ключ:
        print(f"файл ключа пуст: {файл}", file=sys.stderr)
        return 2

    print(f"=== приёмка {а.base}")
    п = Приёмка(а.base, ключ)
    состояние = п.состояние()
    if состояние:
        п.отказы()
        ид = п.каталог()
        if ид:
            п.карточка(ид)
            п.серии(ид)
            п.фильм(ид)
    print(f"\nрасхождений: {п.расхождений}")
    if not состояние:
        print("дальше не проверялось: служба не ответила состоянием")
    return 0 if п.расхождений == 0 and состояние else 1


if __name__ == "__main__":
    sys.exit(главное())
