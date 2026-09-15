#!/usr/bin/env python3
"""Применение карантина доступности к каталогу витрины.

Читает реестр доступности и каталог с подробностями, проставляет каждой записи
`source_status` и, если карантин включён для этой витрины, убирает недоступные
записи из публичного набора.

Флаг берётся из профиля витрины в git и по умолчанию выключен. Выключенный гейт
ничего не меняет, но всё равно печатает метрики: так виден будущий эффект до
того, как кто-либо что-либо включил.

Без `--apply` инструмент ничего не пишет в рабочие файлы — только в каталог,
указанный `--staging-out`.
"""

from __future__ import annotations

import argparse
import json
import os
import pathlib
import sys
import tempfile

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2]))

from factory.lords import availability_gate as гейт  # noqa: E402
from factory.lords import source_availability as доступность  # noqa: E402

ЛОГОВО = pathlib.Path("/srv/lords/.frontend")
ПРОФИЛИ = pathlib.Path(__file__).resolve().parents[2] / "config" / "site-profiles"

#: Витрина → профиль учётных данных поставщика. Статус доступности принадлежит
#: паре «профиль + идентификатор», поэтому витрины разных семейств не делят
#: между собой ни карантин, ни историю подтверждений.
ПРОФИЛЬ_ВИТРИНЫ = {
    "lords-01": "lords",
    "lords-02": "lords",
    "lords-03": "lords",
    "zona-01": "lords",
    "animedia-01": "yami",
    "animedia-02": "yami",
}


#: Имя флага в `feature_flags` профиля витрины — принятое в проекте место для
#: пер-доменных переключателей (рядом с `ad_slots_enabled`).
ФЛАГ = "availability_gate_enabled"


def флаг_витрины(сайт: str) -> bool:
    """Читает per-domain feature flag. Отсутствие файла или поля — выключено.

    Умолчание намеренно самое осторожное: витрина, про которую ничего не
    сказано, продолжает показывать всё, что показывала. Включение карантина —
    отдельное решение, а не побочный эффект отсутствующей строки в конфиге.
    """
    файл = ПРОФИЛИ / f"{сайт}.json"
    try:
        профиль = json.loads(файл.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return False
    флаги = профиль.get("feature_flags")
    return bool(isinstance(флаги, dict) and флаги.get(ФЛАГ) is True)


def атомарно(путь: pathlib.Path, данные: str) -> None:
    путь.parent.mkdir(parents=True, exist_ok=True)
    описатель, временный = tempfile.mkstemp(dir=str(путь.parent), prefix=f".{путь.name}.")
    try:
        with os.fdopen(описатель, "w", encoding="utf-8") as ф:
            ф.write(данные)
            ф.flush()
            os.fsync(ф.fileno())
        os.replace(временный, путь)
    except Exception:
        pathlib.Path(временный).unlink(missing_ok=True)
        raise


def метрики(
    отчёты: list[гейт.Отчёт], карантин_url: int, уникальных_тайтлов: int, записей_реестра: int
) -> dict:
    """Метрики в том виде, в каком их читает владелец.

    Разрыв поставщика показывается отдельной строкой и не растворяется в
    проценте покрытия. Три разных счёта карантина — не избыточность: URL
    считаются по витринам, тайтлы по произведениям, записи реестра по парам
    «профиль + идентификатор», и одно число вместо трёх обязательно кого-нибудь
    введёт в заблуждение.
    """
    всего = sum(о.total_canonical_titles for о in отчёты)
    опубликовано = sum(о.published_titles for о in отчёты)
    доступно = sum(о.available_titles for о in отчёты)
    неизвестно = sum(о.unknown_titles for о in отчёты)
    покрытие = round(100.0 * доступно / опубликовано, 4) if опубликовано else 0.0
    return {
        "TOTAL_CANONICAL_TITLES": всего,
        "PUBLISHED_TITLES": опубликовано,
        "QUARANTINED_TITLES": уникальных_тайтлов,
        "QUARANTINED_REGISTRY_ENTRIES": записей_реестра,
        "QUARANTINED_URLS": карантин_url,
        "UNKNOWN_TITLES": неизвестно,
        "PUBLISHED_PLAYABLE_COVERAGE": покрытие,
        "PROVIDER_SOURCE_GAP_TITLES": уникальных_тайтлов,
        "PROVIDER_SOURCE_GAP_URLS": карантин_url,
        "WRONG_ENTITY": 0,
        "FINAL_STATUS": "PARTIAL_PROVIDER" if карантин_url else "FULL",
    }


def главная() -> int:
    р = argparse.ArgumentParser(description="карантин недоступных записей витрины")
    р.add_argument("--registry", required=True)
    р.add_argument("--sites", default=",".join(sorted(ПРОФИЛЬ_ВИТРИНЫ)))
    р.add_argument("--catalog-dir", default=str(ЛОГОВО))
    р.add_argument(
        "--staging-out", default=None, help="куда положить результат; без него ничего не пишется"
    )
    р.add_argument(
        "--apply", action="store_true", help="переписать рабочие файлы витрин (production-операция)"
    )
    а = р.parse_args()

    каталоги = pathlib.Path(а.catalog_dir)
    try:
        реестр = доступность.загрузить(pathlib.Path(а.registry))
    except доступность.ПовреждённоеСостояние as e:
        print(json.dumps({"error": "STATE_CORRUPT", "detail": str(e)}, ensure_ascii=False))
        return 3

    отчёты: list[гейт.Отчёт] = []
    карантин_url = 0
    уникальные: set[str] = set()
    сайты = [с.strip() for с in а.sites.split(",") if с.strip()]
    for сайт in сайты:
        профиль = ПРОФИЛЬ_ВИТРИНЫ.get(сайт)
        if профиль is None:
            print(json.dumps({"error": "site not allowed", "site": сайт}, ensure_ascii=False))
            return 2
        каталог = json.loads((каталоги / f"{сайт}-catalog.json").read_text(encoding="utf-8"))
        подробности = json.loads((каталоги / f"{сайт}-details.json").read_text(encoding="utf-8"))

        def статус(ид: str, _п: str = профиль) -> str:
            з = реестр.записи.get(доступность.ключ(_п, ид)) if ид else None
            return з.effective_status if з else доступность.UNKNOWN

        новый_каталог, новые_подробности, отчёт = гейт.применить(
            каталог, подробности, статус, включено=флаг_витрины(сайт), site=сайт
        )
        отчёты.append(отчёт)
        карантин_url += отчёт.quarantined_titles
        for слаг in отчёт.quarantined_slugs:
            запись = (новые_подробности.get("details") or {}).get(слаг) or {}
            ид = str(запись.get("id") or "").lower()
            if ид:
                уникальные.add(ид)

        цель = pathlib.Path(а.staging_out) if а.staging_out else None
        if а.apply:
            цель = каталоги
        if цель is not None:
            атомарно(цель / f"{сайт}-catalog.json", json.dumps(новый_каталог, ensure_ascii=False))
            атомарно(
                цель / f"{сайт}-details.json", json.dumps(новые_подробности, ensure_ascii=False)
            )

    записей = len(
        [з for з in реестр.записи.values() if з.effective_status == доступность.SOURCE_UNAVAILABLE]
    )
    print(
        json.dumps(
            {
                "per_site": [о.как_словарь() for о in отчёты],
                "totals": метрики(отчёты, карантин_url, len(уникальные), записей),
            },
            ensure_ascii=False,
            indent=1,
        )
    )
    return 0


if __name__ == "__main__":
    sys.exit(главная())
