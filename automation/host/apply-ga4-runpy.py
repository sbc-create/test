#!/usr/bin/env python3
"""AnimeGo/Animedia: run.py экспортирует GA4 из `analytics` site.json под общим именем. Перенос по якорям.

Зачем. У этих витрин run.py собирает окружение в коде и блок `environment` из
site.json не читает (у AnimeGo ×3 и animedia.space его нет вовсе). Метрика
приходит так: `analytics.counter_id` → `LORDS_METRIKA_COUNTER`. GA4 ложится в тот
же образец, не в новый механизм (согласовано с Архитектором 12.10):

    analytics.ga4_measurement_id  → LORDS_GA4_MEASUREMENT_ID
    analytics.ga4_allowed_hosts   → LORDS_GA4_ALLOWED_HOSTS (через запятую)

GA4 — независимый счётчик (решение владельца 12.10): ни `counter_id`, ни
`analytics.enabled` Метрики условием не являются. Свои условия, каждое — отказ:
ID задан; список хостов задан; домен витрины (`domain` site.json) в списке —
ID, по ошибке скопированный из соседнего репозитория, не включится. Форму ID
проверяет слой (`seo_layer.тег_ga4`), хост запроса — тоже слой.

Нет якоря или он не единственный — отказ ДО записи. Повтор ничего не меняет.

    python3 automation/host/apply-ga4-runpy.py [--check] <run.py> […]
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

МЕТКА = "# GA4 — независимый счётчик (apply-ga4-runpy)."
ЯКОРЬ = re.compile(
    r'(?P<отступ>        )(?P<среда>\w+)\["LORDS_METRIKA_COUNTER"\] = счётчик\n    return (?P=среда)\n')
ФУНКЦИЯ = re.compile(r"^def (?:окружение|environment)\((?P<конфиг>\w+): dict", re.M)


def блок(среда: str, конфиг: str) -> str:
    return f'''        {среда}["LORDS_METRIKA_COUNTER"] = счётчик
    {МЕТКА}
    # Не зависит от Метрики: ни counter_id, ни analytics.enabled не условие.
    # ID и хосты — только из site.json ЭТОГО сайта, и домен сайта обязан быть
    # в списке хостов; иначе переменные не выставляются и тега нет.
    _а = {конфиг}.get("analytics") or {{}}
    _ga4 = str(_а.get("ga4_measurement_id") or "").strip()
    _ga4_хосты = [str(х).strip().lower() for х in (_а.get("ga4_allowed_hosts") or []) if str(х).strip()]
    if _ga4 and _ga4_хосты and str({конфиг}.get("domain") or "").strip().lower() in _ga4_хосты:
        {среда}["LORDS_GA4_MEASUREMENT_ID"] = _ga4
        {среда}["LORDS_GA4_ALLOWED_HOSTS"] = ",".join(_ga4_хосты)
    return {среда}
'''


def привести(текст: str) -> tuple[str, int]:
    if МЕТКА in текст:
        return текст, 0
    найдено = list(ЯКОРЬ.finditer(текст))
    if len(найдено) != 1:
        raise ValueError("якорь экспорта Метрики найден не ровно один раз")
    функции = ФУНКЦИЯ.findall(текст)
    if len(функции) != 1:
        raise ValueError("функция сборки окружения найдена не ровно один раз")
    м = найдено[0]
    return текст[:м.start()] + блок(м["среда"], функции[0]) + текст[м.end():], 1


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--check", action="store_true")
    ap.add_argument("files", nargs="+")
    a = ap.parse_args(argv)
    планы = []
    for имя in a.files:
        путь = Path(имя)
        try:
            новый, _ = привести(путь.read_text(encoding="utf-8"))
        except ValueError as exc:
            print(f"{имя}: ОТКАЗ — {exc}")
            return 2
        планы.append((путь, новый))
    if a.check:
        код = 0
        for путь, новый in планы:
            приведён = новый == путь.read_text(encoding="utf-8")
            print(f"{путь}: {'приведён' if приведён else 'не приведён'}")
            код = код or (0 if приведён else 1)
        return код
    # Записываемость всех целей — до первой записи (отказ на последнем файле
    # однажды оставил репозиторий в половине правок).
    for путь, новый in планы:
        if новый != путь.read_text(encoding="utf-8") and not os_access_w(путь):
            print(f"{путь}: ОТКАЗ — файл не записываемый; ничего не записано")
            return 2
    for путь, новый in планы:
        if новый != путь.read_text(encoding="utf-8"):
            путь.write_text(новый, encoding="utf-8")
        print(f"{путь}: приведён")
    return 0


def os_access_w(путь: Path) -> bool:
    import os  # noqa: PLC0415
    return os.access(путь, os.W_OK)


if __name__ == "__main__":
    sys.exit(main())
