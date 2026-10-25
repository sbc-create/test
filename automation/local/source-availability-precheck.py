#!/usr/bin/env python3
"""Есть ли у работы завязка В ИСТОЧНИКЕ — проверка обычным кодом до модели.

ПОВОД ИЗМЕРЕН. За 7 суток (18–25.10) фоновый редактор закрыл 1 783 задания, из
них **1 193 (67 %)** исходом `SOURCES_MISSING`: модель читала записанный
источник и не находила, из чего писать. Один такой проход стоит около $0,15
(собственный учёт модели: $224,74 на 1 463 попытки). Проверка того же факта
обычным кодом — один запрос к источнику штатным путём, нулевой расход токенов.

Что именно проверяется. Берётся список кандидатов (тот, что цикл пишет в
`var/seo-regular/editor-candidates.json`) или слаги из командной строки. Для
каждой работы читается ЗАПИСАННЫЙ источник штатным путём (`source_fetch.py
shikimori <id>`, он же соблюдает robots и своё имя) и смотрится длина
`description`.

Три исхода, и третий обязателен:

* ``ЗАВЯЗКА ЕСТЬ``   — в источнике описание не короче порога: модели есть из
  чего писать, кандидат остаётся;
* ``ЗАВЯЗКИ НЕТ``    — источник отвечает, описание пустое или короче порога:
  проход кончился бы `SOURCES_MISSING`, и вызывать модель незачем;
* ``НЕ ИЗМЕРЕНО``    — источник не ответил, идентификатора нет, разбор не удался.
  Это НЕ «завязки нет»: кандидат остаётся, иначе сбой сети молча остановил бы
  работу. Правило fail-open названо здесь прямо.

    python3 automation/local/source-availability-precheck.py [--candidates <файл>] [--json out.json]
"""
from __future__ import annotations

import argparse
import collections
import json
import pathlib
import re
import subprocess
import sys

ИНСТРУМЕНТ = pathlib.Path(__file__).resolve().parent / "source_fetch.py"
КАНДИДАТЫ = pathlib.Path(
    "/home/claude/wt-portable-site-cell-01/var/seo-regular/editor-candidates.json")
#: Ниже этого числа знаков описание источника пересказывать нечем: измерено на
#: отказах редактора — у 97 % работ с исходом SOURCES_MISSING описания не было
#: вовсе, а у принятых материалов исходное описание было от двух сотен знаков.
ПОРОГ_ЗНАКОВ = 120


def ид_источника(запись: dict) -> str:
    """Идентификатор Shikimori из записи кандидата или из её примечания."""
    for ключ in ("source_id", "shikimori_id", "mal_id"):
        знач = запись.get(ключ)
        if знач:
            return str(знач)
    текст = json.dumps(запись, ensure_ascii=False)
    м = re.search(r"shikimori\.(?:io|one)/animes/(\d+)", текст)
    if м:
        return м.group(1)
    return ""


def завязка(ид: str, *, таймаут: int = 120, читатель=None) -> tuple[str, int, str]:
    """(исход, знаков, причина) по одному идентификатору источника.

    `читатель` подменяется в проверках, чтобы не ходить в сеть.
    """
    if not ид:
        return "НЕ ИЗМЕРЕНО", 0, "идентификатора Shikimori в записи нет"
    текст, причина = (читатель or _прочитать)(ид, таймаут)
    if текст is None:
        # 404 — источник ответил и записанного идентификатора не знает: это
        # подтверждённое отсутствие завязки, а не сбой измерения.
        исход = "ЗАВЯЗКИ НЕТ" if "404" in причина else "НЕ ИЗМЕРЕНО"
        return исход, 0, причина
    знаков = len(текст.strip())
    if знаков >= ПОРОГ_ЗНАКОВ:
        return "ЗАВЯЗКА ЕСТЬ", знаков, ""
    return "ЗАВЯЗКИ НЕТ", знаков, f"описание источника {знаков} знаков"


def _прочитать(ид: str, таймаут: int) -> tuple[str | None, str]:
    """Штатный путь к источнику: одна карточка, один запрос (`card`)."""
    try:
        г = subprocess.run([sys.executable, str(ИНСТРУМЕНТ), "card", ид],
                           capture_output=True, text=True, timeout=таймаут)
    except subprocess.TimeoutExpired:
        return None, f"источник не ответил за {таймаут} с"
    try:
        д = json.loads(г.stdout)
    except ValueError:
        return None, f"ответ источника не JSON (код {г.returncode})"
    if not д.get("ok"):
        return None, f"источник отказал: status {д.get('status')}"
    return str(д.get("description") or ""), ""


def главное(аргв=None) -> int:
    р = argparse.ArgumentParser(description=__doc__)
    р.add_argument("--candidates", type=pathlib.Path, default=КАНДИДАТЫ)
    р.add_argument("--json", type=pathlib.Path)
    р.add_argument("--limit", type=int, default=0)
    а = р.parse_args(аргв)
    try:
        д = json.loads(а.candidates.read_text(encoding="utf-8"))
    except (OSError, ValueError) as ош:
        print(f"НЕ ИЗМЕРЕНО: список кандидатов не прочитан: {ош}")
        return 2
    список = д.get("candidates") if isinstance(д, dict) else д
    if а.limit:
        список = список[:а.limit]
    счёт = collections.Counter()
    строки = []
    for з in список:
        ид = ид_источника(з)
        исход, знаков, причина = завязка(ид)
        счёт[исход] += 1
        строки.append({"site": з.get("site"), "slug": з.get("slug"),
                       "reason": з.get("reason"), "weight": з.get("weight"),
                       "source_id": ид, "исход": исход, "знаков": знаков,
                       "почему": причина})
        print(f"{исход:14} знаков {знаков:>5}  {str(з.get('reason')):13}"
              f" вес {str(з.get('weight')):>5}  {з.get('site')}/{str(з.get('slug'))[:40]}"
              + (f"  — {причина}" if причина else ""))
    всего = sum(счёт.values()) or 1
    print(f"\nкандидатов проверено {всего}: завязка есть {счёт['ЗАВЯЗКА ЕСТЬ']},"
          f" завязки нет {счёт['ЗАВЯЗКИ НЕТ']}, не измерено {счёт['НЕ ИЗМЕРЕНО']}")
    нет = счёт["ЗАВЯЗКИ НЕТ"]
    print(f"проходов модели, которых можно не делать: {нет}"
          f" ({нет/всего*100:.0f}% списка); при $0,15 за попытку это ${нет*0.15:.2f}")
    print("«НЕ ИЗМЕРЕНО» кандидата НЕ снимает: сбой сети не повод остановить работу")
    if а.json:
        а.json.parent.mkdir(parents=True, exist_ok=True)
        а.json.write_text(json.dumps({"порог_знаков": ПОРОГ_ЗНАКОВ,
                                      "итог": dict(счёт), "строки": строки},
                                     ensure_ascii=False, indent=1), encoding="utf-8")
        print(f"свод записан: {а.json}")
    return 0


if __name__ == "__main__":
    sys.exit(главное())
