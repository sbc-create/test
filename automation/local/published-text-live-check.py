#!/usr/bin/env python3
"""Видит ли читатель то, что редактор объявил опубликованным. Только чтение.

Зачем отдельная проверка. Прогон редактора ставит себе отметку
`public_page_verified`, и этой отметке верить нельзя по той же причине, по
которой нельзя верить отчёту без запуска: проверяющий и проверяемый — одно лицо.

Редактор выпускает ДВА разных вида материала, и путать их нельзя (первая
редакция этого инструмента путала и выдала 24 ложных «не измерено»):

* **описание произведения** — запись в накладке витрины (`title-overlays.json`
  у приложения, наш учёт `published.json` у adapter lords);
* **редакционный комментарий** — запись в `comment-drafts.json`, на странице
  появляется отдельным блоком, который витрина рисует НА СТОРОНЕ КЛИЕНТА.
  Поэтому по HTML комментарий проверить нельзя (измерено 09.10: текст был в базе
  и отдавался API, а в HTML его не было вовсе). Без браузера такой адрес
  печатается как «не измерено» с причиной; с `--comments-browser` проверка
  передаётся `automation/local/comment-visible-check.py`, который смотрит
  глазами посетителя.

Вид определяется по журналу витрины `history.jsonl` (`op`: `publish` или
`publish-comment`), а не по догадке об адресе.

Что считается подтверждением: первые `ОТРЕЗОК` знаков тела найдены в HTML
страницы после разворачивания мнемоник. Переадресация прослеживается (`-L`), и
в отчёт идёт конечный код.

Третий исход обязателен: нет прогонов за период, нет журнала витрины, в журнале
нет записи про этот slug — «не измерено» с причиной, а не тихое «всё хорошо».

    python3 automation/local/published-text-live-check.py --hours 12
    python3 automation/local/published-text-live-check.py --hours 24 --json

Коды: 0 — всё проверенное видно; 1 — есть невидимое; 2 — не измерено ничего.
"""
from __future__ import annotations

import argparse
import datetime as dt
import html as _html
import json
import pathlib
import re
import subprocess
import sys

КОРЕНЬ = pathlib.Path(__file__).resolve().parents[2]
if str(КОРЕНЬ) not in sys.path:
    sys.path.insert(0, str(КОРЕНЬ))

from factory.qwen import registry  # noqa: E402

ПРОГОНЫ = pathlib.Path("/home/claude/wt-portable-site-cell-01/var/editor-runs")
ОТРЕЗОК = 60


def адреса_прогонов(часов: int, сейчас: dt.datetime | None = None,
                    каталог: pathlib.Path = ПРОГОНЫ) -> list[str]:
    сейчас = сейчас or dt.datetime.now(dt.timezone.utc)
    порог = сейчас - dt.timedelta(hours=часов)
    итог: list[str] = []
    for п in sorted(каталог.glob("*.run.json")):
        try:
            когда = dt.datetime.strptime(п.name.split(".")[0], "%Y%m%dT%H%M%SZ")
        except ValueError:
            continue
        if когда.replace(tzinfo=dt.timezone.utc) < порог:
            continue
        try:
            д = json.loads(п.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        for а in (д.get("self_report") or {}).get("urls") or []:
            if а not in итог:
                итог.append(str(а))
    return итог


def slug_из_адреса(адрес: str) -> str:
    м = re.search(r"/(?:anime|title)/([^/?#]+)", адрес)
    return м.group(1) if м else ""


def _читать(п: pathlib.Path):
    try:
        return json.loads(п.read_text(encoding="utf-8")), ""
    except (OSError, ValueError) as сбой:
        return None, f"{п.name}: {сбой}"


def склад_витрины(домен: str) -> dict:
    """Что витрина знает о наших публикациях: журнал, описания, комментарии."""
    сайты = {s.domain: s for s in registry.собрать(опрашивать_сеть=False)}
    s = сайты.get(домен)
    if s is None:
        return {"почему": "домена нет в реестре ячеек"}
    каталог = pathlib.Path(registry.корень_хранилища(s.adapter)) / домен
    живой = pathlib.Path(registry.путь_доставки(s))
    описания: dict[str, str] = {}
    источник = живой if живой.name == "title-overlays.json" else каталог / "published.json"
    д, беда_о = _читать(источник)
    if д and isinstance(д.get("items"), list):
        описания = {str(и.get("slug")): str(и.get("body") or "")
                    for и in д["items"] if isinstance(и, dict) and и.get("slug")}
    комментарии: dict[str, list[str]] = {}
    д2, беда_к = _читать(каталог / "comment-drafts.json")
    # `items` у черновиков комментариев — СЛОВАРЬ по slug, а у накладки описаний
    # список. Первая редакция инструмента ждала список и получила 24 ложных «не
    # измерено»: пустой разбор выглядел как отсутствие материала.
    записи_к = (д2 or {}).get("items")
    if isinstance(записи_к, dict):
        записи_к = list(записи_к.values())
    if isinstance(записи_к, list):
        for и in записи_к:
            if isinstance(и, dict) and и.get("slug"):
                комментарии.setdefault(str(и["slug"]), []).append(str(и.get("body") or ""))
    журнал: dict[str, str] = {}
    п = каталог / "history.jsonl"
    try:
        for строка in п.read_text(encoding="utf-8").splitlines():
            try:
                з = json.loads(строка)
            except ValueError:
                continue
            if з.get("slug") and з.get("op") in ("publish", "publish-comment"):
                журнал[str(з["slug"])] = str(з["op"])
    except OSError as сбой:
        return {"почему": f"журнал витрины не прочитан: {сбой}"}
    return {"журнал": журнал, "описания": описания, "комментарии": комментарии,
            "беды": [б for б in (беда_о, беда_к) if б]}


def страница(адрес: str) -> tuple[str, str]:
    г = subprocess.run(
        ["curl", "-sSL", "-w", "\n%{http_code}", "--max-time", "40", адрес],
        capture_output=True, text=True)
    if г.returncode != 0:
        return "", f"curl код {г.returncode}"
    т = г.stdout
    тело, код = т.rsplit("\n", 1)[0], т.rsplit("\n", 1)[-1].strip()
    if код != "200":
        return "", f"конечный код ответа {код}"
    return тело, ""


def _браузером(домен: str, slug: str, тела: list[str]) -> dict:
    """Видимость комментария глазами посетителя — через уже готовый инструмент."""
    фрагмент = re.sub(r"<[^>]+>", "", тела[0]).strip()[:ОТРЕЗОК]
    г = subprocess.run(
        [sys.executable, str(КОРЕНЬ / "automation/local/comment-visible-check.py"),
         домен, slug, фрагмент],
        capture_output=True, text=True, timeout=180)
    if г.returncode == 0:
        return {"итог": "видно", "почему": ""}
    if г.returncode == 1:
        return {"итог": "отказ", "почему": "блок есть, фрагмента в нём нет"}
    вывод = (г.stderr or г.stdout or "").strip().splitlines()
    return {"итог": "не измерено",
            "почему": вывод[-1][:120] if вывод else "браузерная проверка не удалась"}


def проверить(адреса: list[str], *, браузер: bool = False) -> list[dict]:
    склады: dict[str, dict] = {}
    итоги = []
    for адрес in адреса:
        домен = адрес.split("/")[2] if "//" in адрес else ""
        slug = slug_из_адреса(адрес)
        запись = {"url": адрес, "домен": домен, "slug": slug, "вид": ""}
        if домен not in склады:
            склады[домен] = склад_витрины(домен)
        склад = склады[домен]
        if склад.get("почему"):
            итоги.append({**запись, "итог": "не измерено", "почему": склад["почему"]})
            continue
        оп = склад["журнал"].get(slug, "")
        if not оп:
            итоги.append({**запись, "итог": "не измерено",
                          "почему": "в журнале витрины нет записи об этом slug"})
            continue
        вид = "описание" if оп == "publish" else "комментарий"
        запись["вид"] = вид
        тела = ([склад["описания"].get(slug, "")] if вид == "описание"
                else склад["комментарии"].get(slug, []))
        тела = [т for т in тела if т.strip()]
        if not тела:
            итоги.append({**запись, "итог": "не измерено",
                          "почему": f"тела ({вид}) нет в хранилище витрины"})
            continue
        if вид == "комментарий":
            if not браузер:
                итоги.append({**запись, "итог": "не измерено",
                              "почему": "блок комментариев рисуется на стороне "
                                        "клиента: по HTML не проверяется, нужен "
                                        "--comments-browser"})
                continue
            итоги.append({**запись, **_браузером(домен, slug, тела)})
            continue
        html_, беда = страница(адрес)
        if беда:
            итоги.append({**запись, "итог": "отказ", "почему": беда})
            continue
        развёрнутый = _html.unescape(html_)
        видно = False
        for тело in тела:
            отрезок = re.sub(r"<[^>]+>", "", тело).strip()[:ОТРЕЗОК]
            if отрезок and отрезок in развёрнутый:
                видно = True
                break
        итоги.append({**запись, "итог": "видно" if видно else "отказ",
                      "почему": "" if видно else f"текста ({вид}) на странице нет"})
    return итоги


def main(аргв: list[str] | None = None) -> int:
    р = argparse.ArgumentParser(description="материалы редактора на живых страницах")
    р.add_argument("--hours", type=int, default=12)
    р.add_argument("--json", action="store_true")
    р.add_argument("--limit", type=int, default=0)
    р.add_argument("--comments-browser", action="store_true",
                   help="проверять комментарии браузером (медленно, но это "
                        "единственный способ: блок рисует клиент)")
    дов = р.parse_args(аргв)

    адреса = адреса_прогонов(дов.hours)
    if дов.limit:
        адреса = адреса[-дов.limit:]
    if not адреса:
        print(f"НЕ ИЗМЕРЕНО: за последние {дов.hours} ч опубликованных адресов "
              "в прогонах нет")
        return 2
    итоги = проверить(адреса, браузер=дов.comments_browser)
    видно = [и for и in итоги if и["итог"] == "видно"]
    отказы = [и for и in итоги if и["итог"] == "отказ"]
    не_изм = [и for и in итоги if и["итог"] == "не измерено"]

    if дов.json:
        print(json.dumps({"часов": дов.hours, "адресов": len(итоги),
                          "видно": len(видно), "отказов": len(отказы),
                          "не_измерено": len(не_изм), "записи": итоги},
                         ensure_ascii=False, indent=2))
    else:
        for и in итоги:
            метка = {"видно": "видно      ", "отказ": "ОТКАЗ      ",
                     "не измерено": "не измерено"}[и["итог"]]
            вид = f"[{и['вид']}] " if и["вид"] else ""
            хвост = f" — {и['почему']}" if и["почему"] else ""
            print(f"{метка} {вид}{и['url']}{хвост}")
        по_виду = {}
        for и in видно:
            по_виду[и["вид"]] = по_виду.get(и["вид"], 0) + 1
        print()
        print(f"адресов {len(итоги)}: видно {len(видно)} ({по_виду}),"
              f" отказов {len(отказы)}, не измерено {len(не_изм)}")
    if not видно and not отказы:
        return 2
    return 1 if отказы else 0


if __name__ == "__main__":
    sys.exit(main())
