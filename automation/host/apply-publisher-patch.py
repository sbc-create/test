#!/usr/bin/env python3
"""Зарегистрировать ячейку у производителя каталога. Идемпотентно и с проверкой.

    python3 automation/host/apply-publisher-patch.py --site zona-03 [--apply]

Почему отдельный сценарий, а не «откройте редактор». Файл производителя —
работающий код, у которого НЕТ исходной ветки: обход 155 ветвей origin показал,
что самая полная закоммиченная версия на 2.7 КБ меньше работающей. Значит в нём
есть незакоммиченная чужая работа, и любая правка обязана быть точечной,
проверяемой и повторно безопасной.

Что делает: проверяет, что запись ещё не добавлена; сверяет контекст с
фактическим файлом; применяет ровно вставку; убеждается, что результат
разбирается как Python и содержит запись РОВНО ОДИН раз. Повторный запуск
ничего не меняет и выходит с нулём.

Без `--apply` только показывает, что будет сделано.
"""
from __future__ import annotations

import argparse
import ast
import hashlib
import json
import os
import shutil
from pathlib import Path

КОРЕНЬ = Path(__file__).resolve().parent.parent.parent
ПРОИЗВОДИТЕЛЬ = Path(os.environ.get(
    "NOVA_CATALOG_PUBLISHER",
    "/srv/site-factory/repo/automation/host/nova-catalog-publish.py"))


def ключи_витрин(текст: str) -> list[str]:
    for узел in ast.walk(ast.parse(текст)):
        if (isinstance(узел, ast.Assign)
                and any(getattr(ц, "id", "") == "ВИТРИНЫ" for ц in узел.targets)
                and isinstance(узел.value, ast.Dict)):
            return [к.value for к in узел.value.keys if isinstance(к, ast.Constant)]
    raise SystemExit("в файле производителя не найден словарь ВИТРИНЫ")


def запись(site_id: str, домен: str, юнит: str, порт: int) -> list[str]:
    return [
        f"    # {домен} — ячейка с первого дня. Каталог тот же снимок поставщика,\n",
        "    # что у остальных витрин семейства: производитель пишет им\n",
        "    # байт-идентичные файлы. Без этой записи `опубликовать` отвечает\n",
        f"    # «витрина {site_id} не входит в профиль публикации», снимка не\n",
        "    # возникает, и первый выпуск домена падает на stage_snapshot.\n",
        "    #\n",
        "    # Доставку добавлять не нужно: `доставить_ячейкам` берёт адреса из\n",
        "    # реестра ячеек фабрики.\n",
        f'    "{site_id}": {{"unit": "{юнит}", "host": "{домен}",\n',
        f'                "port": {порт}}},\n',
    ]


def main() -> int:
    р = argparse.ArgumentParser()
    р.add_argument("--site", required=True)
    р.add_argument("--apply", action="store_true")
    а = р.parse_args()

    ячейки = {c["site_id"]: c for c in json.loads(
        (КОРЕНЬ / "config" / "site-cells.json").read_text(encoding="utf-8"))["cells"]}
    if а.site not in ячейки:
        print(f"{а.site} нет в реестре ячеек — регистрировать нечего")
        return 2
    c = ячейки[а.site]
    рв = c.get("runtime") or {}
    домен, юнит, порт = c.get("domain"), рв.get("unit"), рв.get("port")
    if not (домен and юнит and порт):
        print(f"{а.site}: в реестре нет домена, юнита или порта — вход неполон")
        return 2

    if not ПРОИЗВОДИТЕЛЬ.is_file():
        print(f"производителя нет по пути {ПРОИЗВОДИТЕЛЬ}")
        return 2
    исходный = ПРОИЗВОДИТЕЛЬ.read_text(encoding="utf-8")
    до = hashlib.sha256(исходный.encode("utf-8")).hexdigest()
    ключи = ключи_витрин(исходный)
    print(f"производитель: {ПРОИЗВОДИТЕЛЬ}")
    print(f"  sha256 {до[:16]}, витрин {len(ключи)}: {', '.join(ключи)}")

    if а.site in ключи:
        print(f"  {а.site} уже зарегистрирован — менять нечего")
        return 0

    строки = исходный.splitlines(keepends=True)
    # Вставляем после ПОСЛЕДНЕЙ записи словаря, перед его закрывающей скобкой:
    # так порядок объявлений не зависит от того, какие витрины уже есть.
    начало = next(i for i, с in enumerate(строки) if с.startswith("ВИТРИНЫ"))
    закрытие = next(i for i in range(начало, len(строки)) if строки[i].rstrip() == "}")
    новый = "".join(строки[:закрытие] + запись(а.site, домен, юнит, int(порт))
                    + строки[закрытие:])

    ast.parse(новый)
    после_ключи = ключи_витрин(новый)
    if после_ключи.count(а.site) != 1:
        print(f"  ОТКАЗ: после вставки {а.site} встречается "
              f"{после_ключи.count(а.site)} раз")
        return 1
    добавлено = len(новый.splitlines()) - len(строки)
    print(f"  будет добавлено строк: {добавлено}, удалено: 0")
    print(f"  витрины после: {', '.join(после_ключи)}")

    if not а.apply:
        print("\nсухой прогон: файл не менялся. Для записи добавь --apply")
        return 0

    # Копия рядом: работающий код с незакоммиченными правками нельзя менять без
    # возможности вернуть байт в байт.
    запас = ПРОИЗВОДИТЕЛЬ.with_suffix(f".py.before-{а.site}-{до[:12]}")
    if not запас.exists():
        shutil.copy2(ПРОИЗВОДИТЕЛЬ, запас)
    ПРОИЗВОДИТЕЛЬ.write_text(новый, encoding="utf-8")
    проверка = ПРОИЗВОДИТЕЛЬ.read_text(encoding="utf-8")
    ast.parse(проверка)
    assert ключи_витрин(проверка).count(а.site) == 1
    print(f"\nприменено. копия прежнего файла: {запас.name}")
    print(f"  sha256 после {hashlib.sha256(проверка.encode('utf-8')).hexdigest()[:16]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
