#!/usr/bin/env python3
"""Репетиция поправок года на УСТАНОВЛЕННОМ издателе и РЕАЛЬНЫХ данных.

Зачем отдельная репетиция, когда есть разборные проверки. Разборные проверки
собирают запись сами, и ошибка «поправка написана на другой id» им невидима:
они сверяют механизм, а не данные. Здесь берутся настоящие записи ответа
поставщика и настоящий кэш подробностей, а издатель — установленный, с
приложенным точечным патчем.

Проход ничего не выкладывает и не пишет в данные витрин. Он собирает каталог в
временном каталоге и печатает год ДО и ПОСЛЕ по каждой записи поправки.

Отрицательный контроль входит в проход: вместе с исправляемыми берутся записи
`--control`, год которых сверка подтвердила верным. Если у них год изменился —
патч тронул не то, и это отказ.

    python3 automation/local/year-corrections-rehearsal.py
    python3 automation/local/year-corrections-rehearsal.py --json
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

КОРЕНЬ = Path(__file__).resolve().parents[2]
ИЗДАТЕЛЬ = Path("/srv/site-factory/repo")
СНИМОК_ПОСТАВЩИКА = ИЗДАТЕЛЬ / "var/lords/lords/catalog-cache/lords-01.json"
КЭШ_ПОДРОБНОСТЕЙ = ИЗДАТЕЛЬ / "var/lords/detail-cache"
ПОПРАВКИ = КОРЕНЬ / "config/anime-year-corrections.json"
ПАТЧ = КОРЕНЬ / "docs/handoff/year-corrections-nova-publish.patch"
МОДУЛЬ_ПОПРАВОК = КОРЕНЬ / "factory/lords/year_corrections.py"

#: Записи, год которых сверка 20.10 подтвердила ВЕРНЫМ. Они обязаны остаться
#: без изменений: иначе патч правит не то, что сверено.
КОНТРОЛЬ = ("povelitel-demonov-2099", "shaman-king-2021",
            "poschadi-menya-velikiy-gospodin-2", "iz-odnoy-komnaty-2",
            "gintama-9", "dostuchatsya-do-tebya-4")

СЦЕНАРИЙ = r'''
import importlib.util, json, sys
корень, модуль, вход = sys.argv[1], sys.argv[2], sys.argv[3]
sys.path.insert(0, корень)
спец = importlib.util.spec_from_file_location("nova_publish_патч", модуль)
м = importlib.util.module_from_spec(спец)
sys.modules["nova_publish_патч"] = м
спец.loader.exec_module(м)

дано = json.loads(open(вход, encoding="utf-8").read())
снимок = м.Снимок(записи=дано["записи"], получен=дано["получен"],
                  отпечаток=дано["отпечаток"])
реестр = м.РеестрСлагов(по_ид=дано["по_ид"], по_слагу=дано["по_слагу"])
каталог, подробности, ст = м.собрать_сайт(
    снимок=снимок, реестр=реестр, детали_кэш=дано["кэш"],
    site_id="animedia-01", только_аниме=False, аниме_видом=True)
итог = {}
for слаг, з in подробности["details"].items():
    итог[слаг] = {"year": з.get("year"), "type": з.get("type"),
                  "year_source": з.get("year_source")}
по_слагу = {з["slug"]: з for з in каталог["items"]}
for слаг in итог:
    итог[слаг]["catalog_year"] = (по_слагу.get(слаг) or {}).get("year")
    итог[слаг]["catalog_kind"] = (по_слагу.get(слаг) or {}).get("kind")
print(json.dumps({"записи": итог,
                  "ст": {к: з for к, з in ст.items()
                         if к.startswith(("year_", "type_"))}},
                 ensure_ascii=False))
'''


def _модуль(путь: Path, имя: str):
    спец = importlib.util.spec_from_file_location(имя, путь)
    м = importlib.util.module_from_spec(спец)
    sys.modules[имя] = м
    спец.loader.exec_module(м)
    return м


def подготовить(врем: Path, слаги_поправок: dict[str, str]) -> tuple[Path, Path]:
    """(корень с патчем, файл входных данных)."""
    корень = врем / "издатель"
    (корень / "factory" / "lords").mkdir(parents=True)
    # Копируется ТОЛЬКО то, что нужно для сборки: сам издатель и его сосед.
    for имя in sorted(p.name for p in (ИЗДАТЕЛЬ / "factory/lords").glob("*.py")):
        shutil.copy(ИЗДАТЕЛЬ / "factory/lords" / имя,
                    корень / "factory/lords" / имя)
    shutil.copy(ИЗДАТЕЛЬ / "factory/__init__.py", корень / "factory/__init__.py")
    г = subprocess.run(["patch", "-p1", "-i", str(ПАТЧ)], cwd=корень,
                       capture_output=True, text=True)
    if г.returncode != 0:
        raise SystemExit(f"патч не приложился: {г.stdout}{г.stderr}")
    shutil.copy(МОДУЛЬ_ПОПРАВОК, корень / "factory/lords/year_corrections.py")
    # Файл поправок издатель ищет от корня своего дерева.
    (корень / "config").mkdir()
    shutil.copy(ПОПРАВКИ, корень / "config/anime-year-corrections.json")
    return корень, врем / "вход.json"


def собрать_вход(ид_поправок: set[str], подробности: dict[str, dict]) -> dict:
    """Мини-снимок поставщика: только нужные записи, остальное не читается."""
    снимок = json.loads(СНИМОК_ПОСТАВЩИКА.read_text(encoding="utf-8"))
    записи = снимок.get("items") or []
    нужные = ид_поправок | {
        str((подробности.get(с) or {}).get("id") or "") for с in КОНТРОЛЬ}
    нужные.discard("")
    отобрано = {}
    for з in записи:
        ид = str(з.get("id") or з.get("external_id") or "")
        if ид in нужные:
            отобрано[ид] = з
    по_ид = {}
    по_слагу = {}
    for слаг, з in подробности.items():
        ид = str(з.get("id") or "")
        if ид in отобрано:
            по_ид[ид] = слаг
            по_слагу[слаг] = ид
    return {
        "записи": отобрано,
        "получен": снимок.get("fetched_at") or "2026-10-20T03:16:43Z",
        "отпечаток": "репетиция" * 4,
        "по_ид": по_ид,
        "по_слагу": по_слагу,
        "кэш": str(КЭШ_ПОДРОБНОСТЕЙ),
        "ненайденные": sorted(нужные - set(отобрано)),
    }


def главное(аргв: list[str] | None = None) -> int:
    р = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    р.add_argument("--snapshot",
                   default="/srv/animedia-icu/data/animedia-01-details.json")
    р.add_argument("--json", action="store_true")
    а = р.parse_args(аргв)

    for путь in (ИЗДАТЕЛЬ / "factory/lords/nova_publish.py", СНИМОК_ПОСТАВЩИКА,
                 ПОПРАВКИ, ПАТЧ, МОДУЛЬ_ПОПРАВОК):
        if not Path(путь).exists():
            print(f"НЕ ИЗМЕРЕНО: нет {путь}")
            return 2

    подробности = json.loads(
        Path(а.snapshot).read_text(encoding="utf-8"))["details"]
    поправки = _модуль(МОДУЛЬ_ПОПРАВОК, "year_corrections").загрузить(ПОПРАВКИ)
    слаги = {п.ид: п.слаг_при_замере for п in поправки.values()}

    with tempfile.TemporaryDirectory() as врем:
        врем = Path(врем)
        корень, вход_путь = подготовить(врем, слаги)
        вход = собрать_вход(set(поправки), подробности)
        вход_путь.write_text(json.dumps(вход, ensure_ascii=False),
                             encoding="utf-8")
        г = subprocess.run(
            [sys.executable, "-c", СЦЕНАРИЙ, str(корень),
             str(корень / "factory/lords/nova_publish.py"), str(вход_путь)],
            capture_output=True, text=True, timeout=600)
        if г.returncode != 0:
            print("РЕПЕТИЦИЯ НЕ ПРОШЛА:")
            print(г.stdout[-4000:])
            print(г.stderr[-4000:])
            return 1
        итог = json.loads(г.stdout.strip().splitlines()[-1])

    строки = []
    провалов = 0
    for ид, п in sorted(poправки_по_слагу(поправки).items()):
        слаг = п.слаг_при_замере
        было = (подробности.get(слаг) or {})
        стало = итог["записи"].get(слаг) or {}
        ожидался_год = п.год_источника if п.год_источника is not None \
            else было.get("year")
        ожидался_вид = п.вид_источника if п.вид_источника is not None \
            else было.get("type")
        ок = (стало.get("year") == ожидался_год
              and стало.get("type") == ожидался_вид
              and стало.get("catalog_year") == ожидался_год)
        провалов += 0 if ок else 1
        строки.append({
            "слаг": слаг, "ид": ид,
            "год_было": было.get("year"), "год_стало": стало.get("year"),
            "год_ожидался": ожидался_год,
            "вид_было": было.get("type"), "вид_стало": стало.get("type"),
            "год_в_каталоге": стало.get("catalog_year"),
            "источник_года": стало.get("year_source"),
            "итог": "ок" if ок else "ПРОВАЛ",
        })

    контроль = []
    for слаг in КОНТРОЛЬ:
        было = (подробности.get(слаг) or {})
        стало = итог["записи"].get(слаг) or {}
        if not стало:
            контроль.append({"слаг": слаг, "итог": "не собрана"})
            continue
        ок = (стало.get("year") == было.get("year")
              and стало.get("type") == было.get("type"))
        провалов += 0 if ок else 1
        контроль.append({"слаг": слаг, "год": стало.get("year"),
                         "год_в_снимке": было.get("year"),
                         "источник_года": стало.get("year_source"),
                         "итог": "не тронута" if ок else "ПРОВАЛ: тронута"})

    отчёт = {"поправки": строки, "отрицательный_контроль": контроль,
             "статистика_издателя": итог["ст"],
             "ненайдено_в_ответе_поставщика": вход["ненайденные"],
             "провалов": провалов}
    if а.json:
        print(json.dumps(отчёт, ensure_ascii=False, indent=1))
    else:
        печать(отчёт)
    return 1 if провалов else 0


def poправки_по_слагу(поправки):
    return поправки


def печать(отчёт: dict) -> None:
    print("ПОПРАВКИ (установленный издатель + точечный патч, реальные данные):")
    for с in отчёт["поправки"]:
        print(f"  {с['итог']:7} {с['слаг']:48} год {с['год_было']} →"
              f" {с['год_стало']} (ожидался {с['год_ожидался']}),"
              f" в каталоге {с['год_в_каталоге']}, вид {с['вид_было']} →"
              f" {с['вид_стало']}")
        print(f"          источник года: {с['источник_года']}")
    print("\nОТРИЦАТЕЛЬНЫЙ КОНТРОЛЬ — записи, год которых сверка подтвердила:")
    for с in отчёт["отрицательный_контроль"]:
        print(f"  {с['итог']:20} {с['слаг']:48} год {с.get('год')}"
              f" (в снимке {с.get('год_в_снимке')})")
    print(f"\nстатистика издателя: {отчёт['статистика_издателя']}")
    if отчёт["ненайдено_в_ответе_поставщика"]:
        print("НЕ НАЙДЕНО в ответе поставщика (поправка не проверена):"
              f" {отчёт['ненайдено_в_ответе_поставщика']}")
    print(f"провалов: {отчёт['провалов']}")


if __name__ == "__main__":
    sys.exit(главное())
