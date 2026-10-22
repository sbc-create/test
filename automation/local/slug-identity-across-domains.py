#!/usr/bin/env python3
"""Один адрес — одно произведение? Сверка личности слага между витринами семейства.

Только чтение публичных страниц.

ЗАЧЕМ. MOD-49: у поставщика есть пары произведений с одинаковым НАЗВАНИЕМ, и
витрины раздают им слаги по-разному. Измерено 21.10 на «Стесняшке»:
`/anime/stesnyashka` ведёт на сезон 2 у `.site`, `.org` и `7.info` и на сезон
1 у `.biz` и `7.site`, а `/anime/stesnyashka-2023` — зеркально. То есть один
адрес на соседних домéнах сети означает РАЗНОЕ содержимое.

ЧЕМ РАЗЛИЧАТЬ, если названия совпадают. Заголовок `h1` здесь бесполезен: у
двух работ он один и тот же («Стесняшка»). Различает СОСТАВ: номера сезонов и
число серий, которые страница печатает своими ссылками. Это и взято признаком.

Исходы раздельные:

* ``ОДИН И ТОТ ЖЕ``   — состав совпал у всех витрин, где адрес отвечает 200;
* ``РАЗНЫЕ``          — состав различается: дефект, и печатается, у кого что;
* ``НЕ У ВСЕХ``       — где-то 200, где-то нет; это не дефект личности, а
  разный охват, и смешивать их нельзя;
* ``НЕ ИЗМЕРЕНО``     — адрес не ответил ни у одной витрины.

    python3 automation/local/slug-identity-across-domains.py \\
        --slug stesnyashka --slug stesnyashka-2023
    python3 automation/local/slug-identity-across-domains.py --from-journal 12

Коды: 0 — различий нет; 1 — есть; 2 — ничего не измерено.
"""
from __future__ import annotations

import argparse
import json
import pathlib
import re
import subprocess
import sys

СЕМЬЯ_YUMMY = ("yummyani.site", "yummyani.org", "yummyani.biz",
               "yummyani7.site", "yummyani7.info")
ЖУРНАЛ = pathlib.Path("/srv/sites/yummyani-staging/runtime/"
                      "episode-state/events.jsonl")

ОДИН = "ОДИН И ТОТ ЖЕ"
РАЗНЫЕ = "РАЗНЫЕ"
НЕ_У_ВСЕХ = "НЕ У ВСЕХ"
НЕ_ИЗМЕРЕНО = "НЕ ИЗМЕРЕНО"


def состав(тело: str, слаг: str) -> tuple[tuple[int, int], ...]:
    """Состав работы по её же странице: (сезон, число серий) по каждому сезону.

    Берутся ссылки вида `/anime/<слаг>/season/<N>/episode/<M>` — то, что
    витрина печатает сама. Названию не доверяем: у двойников оно совпадает.
    """
    пары = re.findall(rf"/anime/{re.escape(слаг)}/season/(\d+)/episode/(\d+)",
                      тело)
    по_сезонам: dict[int, set[int]] = {}
    for с, э in пары:
        по_сезонам.setdefault(int(с), set()).add(int(э))
    return tuple(sorted((с, len(э)) for с, э in по_сезонам.items()))


def сверить(составы: dict[str, tuple | None]) -> dict:
    """Исход по составам, собранным с витрин. Чистая функция."""
    отвечают = {д: с for д, с in составы.items() if с is not None}
    if not отвечают:
        return {"исход": НЕ_ИЗМЕРЕНО, "почему": "адрес не ответил нигде"}
    различные = {с for с in отвечают.values()}
    if len(различные) > 1:
        return {"исход": РАЗНЫЕ, "составы": отвечают,
                "почему": f"составов {len(различные)} на"
                          f" {len(отвечают)} витринах"}
    if len(отвечают) < len(составы):
        молчат = [д for д, с in составы.items() if с is None]
        return {"исход": НЕ_У_ВСЕХ, "составы": отвечают, "молчат": молчат,
                "почему": "состав один, но адрес есть не у всех"}
    return {"исход": ОДИН, "составы": отвечают,
            "почему": "состав совпал у всех витрин"}


def достать(url: str, таймаут: int = 35) -> tuple[int, str]:
    г = subprocess.run(["curl", "-sSL", "--max-time", str(таймаут),
                        "-w", "\n@@КОД@@%{http_code}", url],
                       capture_output=True, text=True)
    текст = г.stdout or ""
    тело, _, код = текст.rpartition("@@КОД@@")
    try:
        return int(код.strip()[:3]), тело
    except ValueError:
        return 0, тело


def проверить(слаг: str, домены: tuple[str, ...]) -> dict:
    составы: dict[str, tuple | None] = {}
    for д in домены:
        код, тело = достать(f"https://{д}/anime/{слаг}")
        составы[д] = состав(тело, слаг) if код == 200 else None
    итог = {"слаг": слаг}
    итог.update(сверить(составы))
    return итог


def слаги_из_журнала(сколько: int) -> list[str]:
    """Слаги последних наблюдений — те, где двойники опаснее всего."""
    if not ЖУРНАЛ.is_file():
        return []
    имена: list[str] = []
    for строка in reversed(ЖУРНАЛ.read_text(encoding="utf-8",
                                            errors="replace").splitlines()):
        try:
            з = json.loads(строка)
        except ValueError:
            continue
        имя = (з.get("name") or "").strip()
        if имя and имя not in имена:
            имена.append(имя)
        if len(имена) >= сколько:
            break
    # Из имени слаг не выводим: это и есть ошибка сопоставления. Берём слаги
    # поиском по витрине, как делает мера новой серии.
    слаги: list[str] = []
    for имя in имена:
        import urllib.parse
        код, тело = достать("https://yummyani.biz/search?q="
                            + urllib.parse.quote(имя[:26]), 40)
        if код != 200:
            continue
        найденные = list(dict.fromkeys(
            re.findall(r'href="/anime/([^"/#?]+)"', тело)))[:2]
        слаги.extend(с for с in найденные if с not in слаги)
    return слаги[:сколько]


def main(аргв: list[str] | None = None) -> int:
    р = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    р.add_argument("--slug", action="append", default=[])
    р.add_argument("--from-journal", type=int, default=0)
    р.add_argument("--json", action="store_true")
    а = р.parse_args(аргв)

    слаги = list(а.slug)
    if а.from_journal:
        слаги.extend(с for с in слаги_из_журнала(а.from_journal)
                     if с not in слаги)
    if not слаги:
        слаги = ["stesnyashka", "stesnyashka-2023"]

    итоги = [проверить(с, СЕМЬЯ_YUMMY) for с in слаги]
    if а.json:
        print(json.dumps({"слагов": len(итоги), "слаги": итоги},
                         ensure_ascii=False, indent=2, default=str))
    else:
        for и in итоги:
            print(f"{и['слаг'][:44]:46} {и['исход']}  — {и.get('почему','')}")
            if и["исход"] in (РАЗНЫЕ, НЕ_У_ВСЕХ):
                for д, с in (и.get("составы") or {}).items():
                    print(f"      {д:16} сезоны и число серий: {list(с)}")
                for д in и.get("молчат", []):
                    print(f"      {д:16} адрес не отвечает")

    if all(и["исход"] == НЕ_ИЗМЕРЕНО for и in итоги):
        return 2
    return 1 if any(и["исход"] == РАЗНЫЕ for и in итоги) else 0


if __name__ == "__main__":
    sys.exit(main())
