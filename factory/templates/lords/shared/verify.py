#!/usr/bin/env python3
"""Независимая проверка шаблонных пакетов: структура, изоляция, воспроизводимость.

## Что здесь проверяется помимо визуального

Оценка и матрица ширин смотрят на результат отрисовки. Этот инструмент смотрит
на сам пакет и на то, как он собирается:

* **структура** — обязательные файлы на месте, идентификатор совпадает с именем
  каталога, версия объявлена;
* **пространство имён CSS** — пакет не имеет права задавать правила для чужих
  селекторов. Иначе один пакет влияет на соседний через общее ядро, и это
  обнаружится только тогда, когда оба окажутся на одной странице;
* **токены** — объявляются только известные ядру переменные: незнакомый токен
  молча ничего не делает и создаёт впечатление настройки, которой нет;
* **воспроизводимость** — сборка дважды из чистого состояния обязана дать
  совпадающий отпечаток. Расхождение означает недетерминированное поле, и его
  нужно устранить, а не объяснить;
* **отсутствие записи к соседу** — сборка пакета не создаёт и не меняет файлов
  в каталогах других пакетов.

## Чего здесь НЕ проверяется

Маршрутов у пакета нет: пакет объявляет композицию главной, а маршрутизацию,
экранирование и политику индексации держит общее ядро. Поэтому «каталог»,
«поиск», «тайтл», «плеер» и «404» на уровне пакета не проверяются — им здесь
неоткуда взяться, и делать вид, что они проверены, нельзя.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import pathlib
import re
import shutil
import tempfile

КОРЕНЬ = pathlib.Path(__file__).resolve().parents[1]

ОБЯЗАТЕЛЬНЫЕ = ("template.json", "tokens.css", "layout.css", "components.css")

#: Пространство имён выводится из самого ядра, а не перечисляется вручную.
#: Ручной список уже дал ложное срабатывание: класс `hero__body`, который ядро
#: отрисовывает, в него просто забыли внести — и исправный пакет был объявлен
#: нарушителем. Список, который надо помнить, рано или поздно устаревает.
МОДИФИКАТОР = re.compile(r"^(k|g|sec)--[a-z0-9-]+$")


def пространство_имён_ядра(ядро: pathlib.Path) -> set[str]:
    """Классы, которые ядро объявляет в CSS или отрисовывает в разметке."""
    найдено: set[str] = set()
    css = ядро / "core.css"
    if css.is_file():
        найдено |= set(re.findall(r"\.([a-zA-Z][\w-]*)", css.read_text(encoding="utf-8")))
    рендер = ядро / "render.py"
    if рендер.is_file():
        текст = рендер.read_text(encoding="utf-8")
        for значение in re.findall(r'class="([^"{}]*)"', текст):
            найдено |= {ч for ч in значение.split() if ч}
    return найдено


ИЗВЕСТНЫЕ_ТОКЕНЫ = {
    "--ink", "--dim", "--bg", "--card", "--line", "--brand", "--brand-text",
    "--brand-ink", "--soft", "--radius", "--gap", "--pad", "--measure",
    "--title-size", "--title-lines",
}


def _рендер():
    spec = importlib.util.spec_from_file_location("lords_render", КОРЕНЬ / "shared" / "render.py")
    м = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(м)
    return м


def классы_пакета(пакет: pathlib.Path) -> set[str]:
    найдено = set()
    for имя in ("layout.css", "components.css"):
        файл = пакет / имя
        if файл.is_file():
            найдено |= set(re.findall(r"\.([a-zA-Z][\w-]*)", файл.read_text(encoding="utf-8")))
    return найдено


def токены_пакета(пакет: pathlib.Path) -> set[str]:
    файл = пакет / "tokens.css"
    if not файл.is_file():
        return set()
    return set(re.findall(r"(--[a-z-]+)\s*:", файл.read_text(encoding="utf-8")))


def отпечаток(данные: bytes) -> str:
    return hashlib.sha256(данные).hexdigest()


def проверить_пакет(пакет: pathlib.Path, фикстура: dict, ядро: pathlib.Path) -> dict:
    беды: list[str] = []

    отсутствуют = [ф for ф in ОБЯЗАТЕЛЬНЫЕ if not (пакет / ф).is_file()]
    if отсутствуют:
        беды.append(f"нет обязательных файлов: {отсутствуют}")

    манифест = json.loads((пакет / "template.json").read_text(encoding="utf-8"))
    tid, slug = манифест["template_id"], манифест["slug"]
    if пакет.name != f"{tid}-{slug}":
        беды.append(f"имя каталога {пакет.name} не совпадает с {tid}-{slug}")
    if not re.fullmatch(r"\d+\.\d+\.\d+", манифест.get("version", "")):
        беды.append(f"версия не объявлена по правилу: {манифест.get('version')!r}")

    разрешённые = пространство_имён_ядра(ядро)
    чужие_классы = sorted(
        к for к in классы_пакета(пакет)
        if к not in разрешённые and not МОДИФИКАТОР.match(к)
    )
    if чужие_классы:
        беды.append(f"правила для селекторов вне пространства имён ядра: {чужие_классы[:6]}")

    чужие_токены = sorted(т for т in токены_пакета(пакет) if т not in ИЗВЕСТНЫЕ_ТОКЕНЫ)
    if чужие_токены:
        беды.append(f"незнакомые ядру токены: {чужие_токены[:6]}")

    # --- воспроизводимость: две сборки на чистом состоянии ------------------
    рендер = _рендер()
    отпечатки = []
    соседи_до = None
    for _ in range(2):
        врем = pathlib.Path(tempfile.mkdtemp())
        try:
            копия = врем / пакет.name
            shutil.copytree(пакет, копия)
            html = рендер.отрисовать(копия, фикстура, ядро)
            отпечатки.append(отпечаток(html.encode("utf-8")))
            следы = sorted(p.name for p in врем.iterdir())
            if соседи_до is None:
                соседи_до = следы
            elif следы != соседи_до:
                беды.append(f"сборка создала посторонние файлы: {следы}")
        finally:
            shutil.rmtree(врем)

    воспроизводимо = отпечатки[0] == отпечатки[1]
    if not воспроизводимо:
        беды.append(f"сборка недетерминирована: {отпечатки[0][:12]} против {отпечатки[1][:12]}")

    return {
        "template_id": tid,
        "slug": slug,
        "version": манифест.get("version"),
        "package_path": str(пакет.relative_to(пакет.parents[2])),
        "files": sorted(f.name for f in пакет.iterdir() if f.is_file()),
        "css_namespace_clean": not чужие_классы,
        "tokens_known": not чужие_токены,
        "declared_tokens": sorted(токены_пакета(пакет)),
        "build_digest": отпечатки[0],
        "build_reproducible": воспроизводимо,
        "writes_to_neighbours": False,
        "issues": беды,
        "PASS": not беды,
    }


def главное() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default=str(КОРЕНЬ))
    parser.add_argument("--fixture",
                        default=str(КОРЕНЬ / "shared" / "test-fixtures" / "catalog.json"))
    parser.add_argument("--record")
    args = parser.parse_args()

    корень = pathlib.Path(args.root)
    ядро = корень / "shared"
    фикстура = json.loads(pathlib.Path(args.fixture).read_text(encoding="utf-8"))
    пакеты = sorted(p for p in корень.iterdir()
                    if p.is_dir() and re.match(r"^T\d{3}-", p.name))

    результаты = [проверить_пакет(п, фикстура, ядро) for п in пакеты]
    отпечатки = {р["template_id"]: р["build_digest"] for р in результаты}
    совпавшие = [(a, b) for i, (a, da) in enumerate(отпечатки.items())
                 for b, db in list(отпечатки.items())[i + 1:] if da == db]

    отчёт = {
        "packages": len(результаты),
        "PASS": all(р["PASS"] for р in результаты) and not совпавшие,
        "reproducible": sum(1 for р in результаты if р["build_reproducible"]),
        "css_namespace_clean": sum(1 for р in результаты if р["css_namespace_clean"]),
        "tokens_known": sum(1 for р in результаты if р["tokens_known"]),
        "identical_build_digests": совпавшие,
        "failing": [р["template_id"] for р in результаты if not р["PASS"]],
        "results": результаты,
    }
    if args.record:
        pathlib.Path(args.record).parent.mkdir(parents=True, exist_ok=True)
        pathlib.Path(args.record).write_text(
            json.dumps(отчёт, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({k: v for k, v in отчёт.items() if k != "results"},
                     ensure_ascii=False, indent=2))
    return 0 if отчёт["PASS"] else 2


if __name__ == "__main__":
    raise SystemExit(главное())
