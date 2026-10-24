#!/usr/bin/env python3
"""Согласование реестра опытов между рабочими копиями: объединение, не замена.

ПОВОД ИЗМЕРЕННЫЙ, 24.10, и он стоил почти двух опытов. Реестр опытов
существует в нескольких рабочих копиях и разошёлся: в копии этой линии 2
записи, в копии объявленного владельца — 8. По своей копии я предложила
порядок снятия паузы на витринах Lords, не зная, что все четыре витрины
Lords — канарейка либо контроль двух действующих опытов с оценкой 28.10.
Поймала это соседняя линия. Вывод был сделан ПО РЕЕСТРУ, который молча
неполон, — это опаснее ошибки в рассуждении, потому что рассуждение было
верным.

СПОСОБ СОГЛАСОВАНИЯ ВЫБРАН ТАК, а не иначе:

1. Объединение по `experiment_id`, а не замена одной копии другой. Замена
   уничтожила бы `exp-poster-priority-first-screen`, который есть только в
   копии этой линии.
2. Направление задано ОБЪЯВЛЕНИЕМ, а не старшинством копии:
   `config/active-domains.json` → `shared_components.experiments.owner`
   называет владельца реестра. Авторитетна копия владельца; остальные
   приводятся к объединению.
3. Конфликт поля НЕ разрешается молча. Если одна копия говорит `phase:
   canary`, а другая `phase: kept` — это расхождение решений, и инструмент
   отказывает, называя поле и оба значения. Молчаливый выбор «посвежее»
   потерял бы вердикт, историю или контрольную группу.
4. Добавление — не конфликт: пустое/отсутствующее поле против заполненного
   даёт заполненное.
5. Своё поле для следов согласования не вводится: схема реестра объявляет
   `additionalProperties: false`, и ослаблять её ради удобства нельзя. След
   идёт в `evidence` — там и место происхождению записи.

Инструмент НЕ пишет в чужую рабочую копию: для неё готовится патч. Один
владелец общего кода — условие проекта, и согласование его не отменяет.

Запуск:
  experiments-merge.py --check                 расхождения, без записи
  experiments-merge.py --write-local           привести свою копию к объединению
  experiments-merge.py --patch <файл.json>     объединение для копии владельца
  experiments-merge.py --control               положительный контроль
"""
from __future__ import annotations

import argparse
import copy
import json
import pathlib
import sys

КОРЕНЬ = pathlib.Path(__file__).resolve().parents[2]
КОПИИ = pathlib.Path("/home/claude")
СПИСОК = КОРЕНЬ / "config" / "active-domains.json"
ПУСТО = (None, "", [], {})


def владелец() -> str:
    """Чья копия ведёт реестр. Берётся из объявления, не из догадки."""
    д = json.loads(СПИСОК.read_text(encoding="utf-8"))
    общие = д.get("shared_components") or {}
    запись = общие.get("experiments") or общие.get("regular_cycle") or {}
    return str(запись.get("owner") or "")


def копии() -> list[pathlib.Path]:
    """Копия владельца первой, своя второй. Только существующие файлы."""
    пути = []
    х = владелец()
    if х:
        пути.append(КОПИИ / х / "config" / "experiments.json")
    своя = КОРЕНЬ / "config" / "experiments.json"
    if своя not in пути:
        пути.append(своя)
    return [п for п in пути if п.is_file()]


def прочитать(путь: pathlib.Path) -> dict:
    return json.loads(путь.read_text(encoding="utf-8"))


def записи(д: dict) -> dict[str, dict]:
    сп = д.get("experiments") if isinstance(д, dict) else д
    return {з["experiment_id"]: з for з in (сп or [])}


def объединить(копии_данных: list[tuple[pathlib.Path, dict]]
               ) -> tuple[dict[str, dict], list[str]]:
    """Объединение по id. Возвращает (записи, конфликты).

    Конфликт — когда одно и то же поле заполнено в двух копиях по-разному.
    Такой случай не решается: он означает, что решения по опыту разошлись.
    """
    итог: dict[str, dict] = {}
    откуда: dict[str, pathlib.Path] = {}
    конфликты: list[str] = []
    for путь, д in копии_данных:
        for ид, з in записи(д).items():
            if ид not in итог:
                итог[ид] = copy.deepcopy(з)
                откуда[ид] = путь
                continue
            для = итог[ид]
            for поле in set(для) | set(з):
                а, б = для.get(поле), з.get(поле)
                if а == б:
                    continue
                if а in ПУСТО:
                    для[поле] = б
                elif б in ПУСТО:
                    pass
                else:
                    конфликты.append(
                        f"{ид}.{поле}: {откуда[ид].parent.parent.name}="
                        f"{str(а)[:60]!r} против {путь.parent.parent.name}="
                        f"{str(б)[:60]!r}")
    return итог, конфликты


def след(з: dict, источник: str) -> dict:
    """След согласования — в `evidence`, своего поля схема не разрешает."""
    з = copy.deepcopy(з)
    отметка = (f"согласовано 2026-10-24 объединением копий реестра"
               f" (добавлено из {источник}); способ —"
               f" automation/local/experiments-merge.py")
    было = (з.get("evidence") or "").strip()
    if "согласовано 2026-10-24" not in было:
        з["evidence"] = f"{было} | {отметка}" if было else отметка
    return з


def собрать() -> tuple[dict, list[str], list[pathlib.Path]]:
    пути = копии()
    данные = [(п, прочитать(п)) for п in пути]
    слитые, конфликты = объединить(данные)
    # Верхний уровень берётся у владельца, но заметка приводится к правде:
    # прежняя говорила «на реальных данных экспериментов не проводилось», а в
    # реестре их восемь. Отчёт, противоречащий своему же содержимому, — ошибка.
    основа = copy.deepcopy(данные[0][1]) if данные else {"version": 1,
                                                         "experiments": []}
    основа["note"] = (
        "Реестр экспериментов. Ведётся оператором; завершённые эксперименты"
        " питают learning playbook. Копий реестра несколько, владелец объявлен"
        " в config/active-domains.json (shared_components.experiments.owner);"
        " копии согласуются объединением по experiment_id через"
        " automation/local/experiments-merge.py, замена одной копии другой"
        " запрещена. Неполный реестр не разрешает менять экспериментальную"
        " группу и снимать паузу публикации —"
        " automation/local/experiments-consistency-gate.py.")
    # След согласования ставится ТОЛЬКО записи, которой у владельца не было:
    # переписывать `evidence` остальным — значит менять историю, которую просили
    # сохранить. Способ согласования для всех описан в `note` выше.
    у_владельца = set(записи(данные[0][1])) if данные else set()
    основа["experiments"] = [
        (слитые[k] if k in у_владельца
         else след(слитые[k], f"копии {КОРЕНЬ.name}"))
        for k in sorted(слитые)]
    return основа, конфликты, пути


def главное(argv: list[str] | None = None) -> int:
    р = argparse.ArgumentParser(description=__doc__)
    р.add_argument("--check", action="store_true")
    р.add_argument("--write-local", action="store_true")
    р.add_argument("--patch", type=pathlib.Path)
    р.add_argument("--control", action="store_true")
    а = р.parse_args(argv)
    if not any((а.check, а.write_local, а.patch, а.control)):
        р.print_help()
        return 2

    пути = копии()
    if len(пути) < 2:
        print(f"НЕ ИЗМЕРЕНО: найдена одна копия реестра из двух — {пути}")
        return 2
    print(f"владелец реестра по объявлению: {владелец() or '(не объявлен)'}")
    for п in пути:
        print(f"  копия {п} — записей {len(записи(прочитать(п)))}")

    слитые, конфликты, _ = собрать()
    всего = len(слитые["experiments"])
    print(f"объединение: {всего} записей")
    if конфликты:
        print("СОГЛАСОВАНИЕ НЕ ВЫПОЛНЕНО — поля расходятся решениями:")
        for к in конфликты:
            print(f"   {к}")
        print("   такой случай решает не инструмент: разошлись РЕШЕНИЯ по опыту")
        return 1

    for п in пути:
        свои = set(записи(прочитать(п)))
        нет = sorted({з["experiment_id"] for з in слитые["experiments"]} - свои)
        print(f"  копии {п.parent.parent.name} не хватает: {нет or 'ничего'}")

    if а.control:
        код = контроль(слитые)
        if код:
            return код

    if а.write_local:
        своя = КОРЕНЬ / "config" / "experiments.json"
        было = len(записи(прочитать(своя)))
        своя.write_text(json.dumps(слитые, ensure_ascii=False, indent=1) + "\n",
                        encoding="utf-8")
        print(f"своя копия приведена к объединению: было {было}, стало {всего}")
    if а.patch:
        а.patch.parent.mkdir(parents=True, exist_ok=True)
        а.patch.write_text(json.dumps(слитые, ensure_ascii=False, indent=1) + "\n",
                           encoding="utf-8")
        print(f"патч для копии владельца: {а.patch}")
    return 0


def контроль(слитые: dict) -> int:
    """Инструмент обязан уметь и объединить, и отказать."""
    ошибки = []
    а = {"experiments": [{"experiment_id": "x", "phase": "canary"}]}
    б = {"experiments": [{"experiment_id": "x", "phase": "kept"}]}
    _, к = объединить([(pathlib.Path("/a/b/c"), а), (pathlib.Path("/d/e/f"), б)])
    if not к:
        ошибки.append("расхождение phase не названо конфликтом")
    в = {"experiments": [{"experiment_id": "x", "phase": "canary",
                          "verdict": "keep"}]}
    слито, к2 = объединить([(pathlib.Path("/a/b/c"), а), (pathlib.Path("/d/e/f"), в)])
    if к2 or слито["x"].get("verdict") != "keep":
        ошибки.append("дополнение пустого поля принято за конфликт")
    if len(слитые["experiments"]) < 2:
        ошибки.append("объединение дало меньше двух записей — источники не те")
    for о in ошибки:
        print(f"КОНТРОЛЬ НЕ ПРОЙДЕН: {о}")
    if ошибки:
        return 1
    print("контроль пройден: конфликт полей называется, дополнение — нет")
    return 0


if __name__ == "__main__":
    sys.exit(главное())
