#!/usr/bin/env python3
"""Прокси Yummy не отменяет кеш и сжатие приложения и объявляет SDK плеера.

Замер 2026-10-05 (docs/PERF_NETWORK_AUDIT_20261005.md): на всех пяти витринах
Yummy прокси `src/yummy-frontend.py` перед Next.js дописывал к
`cache-control: immutable` чанков `Cache-Control: no-store`, просил у
приложения `Accept-Encoding: identity` и не объявлял SDK плеера, который
приложение вставляет только после гидратации.

Правка проверена на yummyani.site (ветка claude/extract-yummyani-site-perf-01):
A/B копий — LCP главной 1820 → 536 мс, повторный визит JS 517 → 0 КБ,
SDK плеера загружен 1261 → 588 мс. Здесь те же замены по якорям — для
переноса на остальные витрины по одной (AGENTS.md п. 2: массовая замена
запрещена — инструмент берёт один файл за раз). Нет якоря — отказ.
Идемпотентен (`СТАТИКА_ПРИЛОЖЕНИЯ` в файле — уже применено). `--check`
ничего не пишет.
"""
from __future__ import annotations

import argparse
from pathlib import Path

БЛОК_КОНСТАНТ = '#: Скорость (замер 2026-10-05, СКОРОСТЬ — СЕТЬ САЙТОВ). Неизменяемые чанки\n#: приложения: только для них сжатие приложения доходит до браузера. Страницы\n#: прокси читает сам (признак своей страницы в первых килобайтах), поэтому им\n#: по-прежнему идёт `identity`. Next.js сжимает чанк 37 КБ → 11 КБ; пока прокси\n#: просил `identity`, каждый визит тянул ~1 МБ несжатого JS.\nСТАТИКА_ПРИЛОЖЕНИЯ = "/_next/static/"\n#: Страницы с плеером: тайтл и серия. Им заголовком `Link` объявляется SDK\n#: плеера: приложение вставляет его скрипт только после гидратации, и на\n#: замере запрос SDK уходил через 2,0 с после начала навигации против 0,04 с\n#: на витринах, где тег стоит в HTML. Разметка не меняется — это заголовок.\nСТРАНИЦА_ПЛЕЕРА = re.compile(r"^/anime/[^/]+(?:/season/\\d+/episode/\\d+)?/?$")\nПРЕДЗАГРУЗКА_ПЛЕЕРА = ("<https://player.cdnvideohub.com/s2/stable/video-player.umd.js>; rel=preload; as=script, "\n                       "<https://player.cdnvideohub.com>; rel=preconnect, "\n                       "<https://plapi.cdnvideohub.com>; rel=preconnect; crossorigin")\n'
ЯКОРЬ_КОНСТАНТ = 'ПЕРЕНОСИМЫЕ = ("location", "cache-control", "content-language", "vary",'
БЛОК_КЕША = '# Политику кеша называет приложение, если назвало: чанки Next.js\n        # неизменяемы (`immutable`), а второй заголовок `no-store` рядом с ним\n        # отменял кеш браузера — повторный визит тянул те же ~1 МБ заново.\n        # Без политики приложения остаётся прежнее `no-store`.\n        if not any(str(и).lower() == "cache-control" for и, _ in (перенос or [])):\n            self.send_header("Cache-Control", "no-store")'
ЯКОРЬ_КЕША = 'self.send_header("Cache-Control", "no-store")'
ЯКОРЬ_СЖАТИЯ = ('            заг["Accept-Encoding"] = "identity"\n'
                '            соед.request("GET", адрес, headers=заг)\n'
                '            ответ = соед.getresponse()')
ЗАМЕНА_СЖАТИЯ = ('            статика = разбор.path.startswith(СТАТИКА_ПРИЛОЖЕНИЯ)\n'
                 '            заг["Accept-Encoding"] = ((self.headers.get("Accept-Encoding") or "identity")\n'
                 '                                      if статика else "identity")\n'
                 '            соед.request("GET", адрес, headers=заг)\n'
                 '            ответ = соед.getresponse()')
ЯКОРЬ_ПЕРЕНОСА = ('            перенос = [(и, ответ.getheader(и)) for и in ПЕРЕНОСИМЫЕ\n'
                  '                       if ответ.getheader(и)]')
ЗАМЕНА_ПЕРЕНОСА = ЯКОРЬ_ПЕРЕНОСА + (
    '\n            if статика and ответ.getheader("Content-Encoding"):\n'
    '                перенос.append(("Content-Encoding", ответ.getheader("Content-Encoding")))\n'
    '            if "text/html" in тип and ответ.status == 200 and СТРАНИЦА_ПЛЕЕРА.match(разбор.path):\n'
    '                перенос.append(("Link", ПРЕДЗАГРУЗКА_ПЛЕЕРА))')


def один(текст: str, якорь: str, где: str) -> None:
    if текст.count(якорь) != 1:
        raise SystemExit(f"якорь «{где}» найден {текст.count(якорь)} раз(а), ожидался 1")


def применить(текст: str) -> tuple[str, str]:
    if "СТАТИКА_ПРИЛОЖЕНИЯ" in текст:
        return текст, "already"
    один(текст, ЯКОРЬ_КОНСТАНТ, "константы")
    текст = текст.replace(ЯКОРЬ_КОНСТАНТ, БЛОК_КОНСТАНТ + ЯКОРЬ_КОНСТАНТ, 1)
    i = текст.index("    def _потоком(")
    j = текст.index(ЯКОРЬ_КЕША, i)
    текст = текст[:j] + БЛОК_КЕША + текст[j + len(ЯКОРЬ_КЕША):]
    i = текст.index("    def наверх(self, разбор):")
    голова, хвост = текст[:i], текст[i:]
    один(хвост, ЯКОРЬ_СЖАТИЯ, "сжатие")
    один(хвост, ЯКОРЬ_ПЕРЕНОСА, "перенос")
    хвост = хвост.replace(ЯКОРЬ_СЖАТИЯ, ЗАМЕНА_СЖАТИЯ, 1).replace(ЯКОРЬ_ПЕРЕНОСА, ЗАМЕНА_ПЕРЕНОСА, 1)
    return голова + хвост, "applied"


def main(argv=None) -> int:
    р = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    р.add_argument("файл")
    р.add_argument("--check", action="store_true")
    а = р.parse_args(argv)
    путь = Path(а.файл)
    новый, исход = применить(путь.read_text(encoding="utf-8"))
    if а.check:
        print(f"{путь}: {'приведён' if исход == 'already' else 'НЕ приведён'}")
        return 0 if исход == "already" else 1
    if исход == "applied":
        compile(новый, str(путь), "exec")
        путь.write_text(новый, encoding="utf-8")
    print(f"{путь}: {исход}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
