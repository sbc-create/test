#!/usr/bin/env python3
"""Объявленные возможности адаптера против ФАКТИЧЕСКИХ читателей витрин.

ПОВОД ИЗМЕРЕННЫЙ, 24.10 (MOD-172). `registry.ВОЗМОЖНОСТИ_АДАПТЕРА` объявляет
`display` только у семейства `animedia`, а у `lords`, `animego` и
`zona-serve` нет даже `deliver`. Поскольку
`ТРЕБУЕТ_ВОЗМОЖНОСТИ['publish'] = ('deliver','display')`, очередь отказывает в
заданиях на описание всем, кроме animedia, словами «задание невыполнимо, пока
у площадки не появится читатель накладки в выпущенном рантайме». А читатели
есть, и это проверяется здесь.

ЗАЧЕМ ПО ВИТРИНАМ, А НЕ ПО СЕМЕЙСТВАМ. Объявление живёт на уровне адаптера, а
читатель — в выпущенном рантайме КОНКРЕТНОЙ витрины: `current` у неё своя, и
две витрины одного семейства могут быть выложены из разных выпусков. Сверка по
семейству скрыла бы именно тот случай, из-за которого запись и появилась.

ТРИ МАРШРУТА ПОКАЗА, и путать их нельзя:
  наложение в дереве  — `<current>/src/seo_overlay.py` читает title-overlays;
  накладка витрины    — `<current>/src/*editorial*.py` читает
                        editorial-overrides.json (так показывают Lords и Zona);
  наложение в контейнере — путь задан переменной `TITLE_OVERLAYS_PATH`, а не
                        кодом в дереве (так показывают витрины Yummy: процессы
                        next-server в контейнерах, и поиск по дереву витрины
                        даёт ноль — измерено, я на этом ошиблась).

Инструмент только ЧИТАЕТ: рантаймы витрин, реестр ячеек и метки контейнеров.
Из `docker inspect` берутся ровно две вещи — монтирования и переменные с
именем TITLE_OVERLAYS*; окружение целиком не выгружается, там бывают секреты.
"""
from __future__ import annotations

import argparse
import json
import pathlib
import subprocess
import sys

КОРЕНЬ = pathlib.Path(__file__).resolve().parents[2]
ЯЧЕЙКИ = КОРЕНЬ / "config" / "site-cells.json"
SRV = pathlib.Path("/srv")


def _реестр():
    sys.path.insert(0, str(КОРЕНЬ))
    from factory.qwen import registry
    return registry


def витрины() -> list[dict]:
    д = json.loads(ЯЧЕЙКИ.read_text(encoding="utf-8"))
    яч = д.get("cells") or д
    яч = list(яч.values()) if isinstance(яч, dict) else яч
    return [з for з in яч if isinstance(з, dict) and з.get("domain")]


def дерево(домен: str) -> pathlib.Path | None:
    """Каталог витрины в /srv. Имя строится из домена, как у накладок."""
    основа = домен.replace(".", "-")
    for имя in (основа, f"site-{основа}"):
        п = SRV / имя
        if п.is_dir():
            return п
    return None


def читатель_в_дереве(корень: pathlib.Path) -> tuple[str, str]:
    """(маршрут, доказательство) по выпущенному рантайму витрины."""
    текущий = корень / "current"
    if not текущий.exists():
        return "", f"нет {текущий}"
    наложение = текущий / "src" / "seo_overlay.py"
    if наложение.is_file():
        return "наложение в дереве", str(наложение)
    исходники = текущий / "src"
    накладка = исходники / "editorial_overlay.py"
    if накладка.is_file():
        # Путь к накладке читатель берёт из `config/site.json`, поэтому
        # ЛИТЕРАЛА `editorial-overrides` в самом модуле нет. Первая редакция
        # требовала литерал и потому не видела читателя у lordserial33.biz и
        # zonafilm.space — недосмотр, а он здесь опаснее ложной тревоги: по
        # нему решают, что витрина показывать не умеет.
        подтверждение = []
        for место in (текущий / "config" / "site.json",
                      текущий / "checks" / "editorial_overlay.py"):
            try:
                if место.is_file() and "editorial-overrides" in место.read_text(
                        encoding="utf-8", errors="replace"):
                    подтверждение.append(место.name)
            except OSError:
                pass
        довод = str(накладка)
        if подтверждение:
            довод += " (подтверждено: " + ", ".join(подтверждение) + ")"
        return "накладка витрины", довод
    return "", f"читателя в {исходники} нет"


def контейнеры() -> dict[str, dict]:
    """Монтирования и переменные TITLE_OVERLAYS* по работающим контейнерам."""
    из: dict[str, dict] = {}
    try:
        имена = subprocess.run(["docker", "ps", "--format", "{{.Names}}"],
                               capture_output=True, text=True, timeout=60)
    except (OSError, subprocess.SubprocessError):
        return из
    if имена.returncode != 0:
        return из
    for имя in имена.stdout.split():
        try:
            м = subprocess.run(
                ["docker", "inspect", "--format",
                 '{{range .Mounts}}{{.Source}}->{{.Destination}}\n{{end}}', имя],
                capture_output=True, text=True, timeout=60)
            с = subprocess.run(
                ["docker", "inspect", "--format",
                 "{{range .Config.Env}}{{println .}}{{end}}", имя],
                capture_output=True, text=True, timeout=60)
        except (OSError, subprocess.SubprocessError):
            continue
        пути = [с2 for с2 in (с.stdout or "").splitlines()
                if с2.startswith("TITLE_OVERLAYS")]
        if пути:
            из[имя] = {"переменные": пути,
                       "монтирования": [x for x in (м.stdout or "").splitlines()
                                        if "overlay" in x.lower()]}
    return из


def маршрут_контейнера(домен: str, кон: dict[str, dict]) -> tuple[str, str]:
    for имя, д in кон.items():
        for м in д["монтирования"]:
            if f"/{домен}" in м:
                return ("наложение в контейнере",
                        f"{имя}: {м.strip()} + {д['переменные'][0].split('=')[0]}")
    return "", ""


def главное(argv: list[str] | None = None) -> int:
    р = argparse.ArgumentParser(description=__doc__)
    р.add_argument("--json", type=pathlib.Path)
    а = р.parse_args(argv)

    registry = _реестр()
    возм = registry.ВОЗМОЖНОСТИ_АДАПТЕРА
    по_рантайму = registry.АДАПТЕРЫ_ПО_РАНТАЙМУ
    кон = контейнеры()
    if not кон:
        print("ПРИМЕЧАНИЕ: контейнеры не опрошены (docker недоступен) —"
              " маршрут «наложение в контейнере» по этому прогону не виден")

    строки = []
    print(f"{'витрина':24} {'ячейка':12} {'маршрут показа':24}"
          f" {'объявлено':18} расхождение")
    расхождений = 0
    for з in sorted(витрины(), key=lambda x: x["domain"]):
        домен = з["domain"]
        корень = дерево(домен)
        маршрут, довод = ("", "витрины нет в /srv")
        if корень:
            маршрут, довод = читатель_в_дереве(корень)
        if not маршрут:
            маршрут, д2 = маршрут_контейнера(домен, кон)
            if маршрут:
                довод = д2
        адаптер = ""
        if корень:
            for точка, имя in по_рантайму.items():
                if (корень / "current" / точка).exists() or (
                        корень / "current" / "src" / точка).exists():
                    адаптер = имя
                    break
        объявлено = sorted(возм.get(адаптер, {})) if адаптер else []
        показывает = bool(маршрут)
        объявлен_показ = "display" in объявлено
        расх = ""
        if показывает and not объявлен_показ:
            расх = "ПОКАЗЫВАЕТ, но display не объявлен"
            расхождений += 1
        elif объявлен_показ and not показывает:
            расх = "display объявлен, читателя не нашла"
            расхождений += 1
        print(f"{домен:24} {str(з.get('site_id')):12} {(маршрут or '—'):24}"
              f" {(','.join(объявлено) or '—'):18} {расх}")
        строки.append({"домен": домен, "ячейка": з.get("site_id"),
                       "адаптер": адаптер, "маршрут": маршрут,
                       "доказательство": довод, "объявлено": объявлено,
                       "расхождение": расх})
    print()
    print(f"витрин {len(строки)}; расхождений объявления и факта: {расхождений}")
    if а.json:
        а.json.parent.mkdir(parents=True, exist_ok=True)
        а.json.write_text(json.dumps(строки, ensure_ascii=False, indent=1),
                          encoding="utf-8")
        print(f"подробности: {а.json}")
    if расхождений:
        print("ВЫВОД: очередь судит о возможности публикации по объявлению,"
              " а не по рантайму — поэтому отказывает витринам, которые текст"
              " показывают (MOD-172). Правка объявления требует решения"
              " владельца: она снимает действующий запрет.")
        return 1
    print("ВЫВОД: объявление совпадает с фактом по каждой витрине")
    return 0


if __name__ == "__main__":
    sys.exit(главное())
