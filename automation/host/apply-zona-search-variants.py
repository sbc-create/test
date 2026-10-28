#!/usr/bin/env python3
"""T347: варианты названия переносятся на витрину с рантаймом в `src/`.

    python3 automation/host/apply-zona-search-variants.py \
        --repo var/site-repos/zonafilm-space [--check] [--dry-run]

Чем эта витрина отличается от zonafilm.cc
-----------------------------------------

У zonafilm.cc рантайм лежит в `template/<выпуск>/lords-frontend.py`, а правки
ставятся наложениями из `src/serve.py` (`установить(рантайм)`). У zonafilm.space
и zonafilm12.site рантайм — САМ `src/lords-frontend.py`, и слоя наложений нет
вовсе: расширения подключаются обычным импортом внутри рантайма
(`import seo_layer as SEO`). Поэтому перенос — не копия проводки, а одна точка
вставки в рантайм.

Внутренности у трёх витрин одной породы совпадают, и это ПРОВЕРЯЕТСЯ, а не
предполагается: инструмент требует, чтобы каждое имя, на которое опираются
модули, встречалось в рантайме РОВНО ОДИН раз — `нормализовать`,
`нормализовать_фразу`, `токены`, `СЛУЖЕБНЫЕ`, `Данные`, `Обработчик`,
`построить_индекс`, `_дополнить_формы_поиска`, `сбросить_указатель`, `main`.
Нет имени или их два — отказ, без правки.

Куда ставится
-------------

Перед `def main() -> int:`: к этому месту модуль определён целиком, а `main()`
зовёт `построить_индекс` и `Данные.искать` уже обёрнутыми. Импорт жёсткий, как
у `seo_layer`: витрина без обещанного механизма подниматься не должна —
молчаливая потеря механизма хуже отказа на старте.

Ворота
------

Правка накладывается на ВРЕМЕННУЮ копию витрины и там ПРОВЕРЯЕТСЯ прогоном.
Рубежей два, и оба обязательны для доставки:

1. **19 случаев** — семь запросов, которые на живой витрине не находят нужное
   или ставят его не первым, и двенадцать групп одноимённых. Каждый обязан
   дать нужную работу ПЕРВОЙ.
2. **Сплошной обход** по списку приёмки (`--sweep`): у каждой карточки берётся
   её собственный H1 и по нему идёт поиск; карточка обязана быть первой. Это
   рубеж ОТ РЕГРЕССИЙ: 19 случаев говорят, что исправленное исправилось, и
   ничего не говорят о том, что остальное не сломалось. На живых витринах
   первыми 97 из 109; норма после правки — 109 из 109, и ни одной потери.

Сухой прогон «будет сделано» воротами не считается: три изъяна точки вставки в
соседнем инструменте видел только запуск. Без `--sweep` доставка НЕ идёт:
отказ с названной причиной, а не тихая доставка по слабым воротам.
"""
from __future__ import annotations

import argparse
import ast
import http.client
import json
import os
import pathlib
import shutil
import socket
import subprocess
import sys
import tempfile
import time
import urllib.parse

ИСТОЧНИК = pathlib.Path("/home/claude/wt-nova-publish-memory-02/var/site-repos/"
                        "zonafilm-cc")
МОДУЛИ = ("search_aliases.py", "search_short_words.py", "search_same_name.py",
          "search_exact_form.py")
СЛОВАРЬ = "search-aliases.json"

ИМЕНА = ("def нормализовать(", "def нормализовать_фразу(", "def токены(",
         "СЛУЖЕБНЫЕ = ", "class Данные", "class Обработчик",
         "def построить_индекс(", "def _дополнить_формы_поиска(",
         "def сбросить_указатель(", "def main() -> int:")

ЯКОРЬ = "def main() -> int:"

ВСТАВКА = '''# T347: варианты названия — синоним по словарю, короткое служебное слово,
# порядок одноимённых, дословное имя первым. Разбор — src/search_aliases.py,
# src/search_short_words.py, src/search_same_name.py, src/search_exact_form.py.
#
# Ставится ПЕРЕД main(): модуль к этому месту определён целиком, а main() зовёт
# построить_индекс и Данные.искать уже обёрнутыми. Порядок обязателен:
# одноимённые, затем дословное имя (имя работы сильнее числа голосов), затем
# короткие слова (их повтор должен пройти через оба упорядочивания).
#
# Импорт жёсткий, как у seo_layer: витрина без обещанного механизма подниматься
# не должна — молчаливая потеря механизма хуже отказа на старте.
import search_aliases as _СИНОНИМЫ  # noqa: E402
import search_exact_form as _ДОСЛОВНО  # noqa: E402
import search_same_name as _ОДНОИМЁННЫЕ  # noqa: E402
import search_short_words as _КОРОТКИЕ  # noqa: E402

_ВАРИАНТЫ_НАЗВАНИЯ = [
    _СИНОНИМЫ.установить(sys.modules[__name__], json.loads(
        (Path(__file__).resolve().parent.parent / "config"
         / "search-aliases.json").read_text(encoding="utf-8"))),
    _ОДНОИМЁННЫЕ.установить(sys.modules[__name__]),
    _ДОСЛОВНО.установить(sys.modules[__name__]),
    _КОРОТКИЕ.установить(sys.modules[__name__]),
]


'''

#: Запросы, у которых нужная работа обязана быть ПЕРВОЙ, и её слаг.
ЗАПРОСЫ = (
    ("Легенда Вокс Машины", "legenda-o-vox-machina"),
    ("Улыбающиеся друзья", "zadornye-druzya"),
    ("Этим летом я стала красивой", "to-leto-kogda-ya-pohoroshela"),
    ("Любовь, смерть и роботы", "lyubov-smert-roboty"),
    ("C.S.I. Место преступления", "csi-mesto-prestupleniya"),
    ("Очень страшное кино 6", "ochen-strashnoe-kino"),
    ("Сумерки 2", "sumerki-saga-novolunie"),
    ("Гримм", "grimm"),
    ("Касл", "kasl"),
    ("Мыслить как преступник", "myslit-kak-prestupnik"),
    ("Шерлок", "sherlok"),
    ("Сверхъестественное", "sverhestestvennoe-3"),
    ("Сотня", "sotnya-2"),
    ("Флэш", "flesh-3"),
    ("Офис", "ofis-2"),
    ("Каратель", "karatel-6"),
    ("Кости", "kosti-3"),
    ("Клиника", "klinika-3"),
    ("Друзья", "druzya-3"),
)

import re  # noqa: E402

_КАРТОЧКА = re.compile(r'data-testid="title-card" href="/title/([^/"]+)/?"')


def _правка(репо: pathlib.Path) -> tuple[bool, str]:
    рантайм = репо / "src" / "lords-frontend.py"
    if not рантайм.is_file():
        return False, f"нет рантайма {рантайм}"
    текст = рантайм.read_text(encoding="utf-8")
    if "_ВАРИАНТЫ_НАЗВАНИЯ" in текст:
        return False, "уже"
    плохие = [и for и in ИМЕНА if текст.count(и) != 1]
    if плохие:
        return False, ("в рантайме нет или неоднозначны имена: "
                       + ", ".join(и.strip() for и in плохие))
    for имя in МОДУЛИ:
        источник = ИСТОЧНИК / "src" / имя
        if not источник.is_file():
            return False, f"нет источника модуля {источник}"
        (репо / "src" / имя).write_bytes(источник.read_bytes())
    словарь = ИСТОЧНИК / "config" / СЛОВАРЬ
    if not словарь.is_file():
        return False, f"нет словаря {словарь}"
    (репо / "config" / СЛОВАРЬ).write_bytes(словарь.read_bytes())
    новый = текст.replace(ЯКОРЬ, ВСТАВКА + ЯКОРЬ, 1)
    try:
        ast.parse(новый)
    except SyntaxError as сбой:
        return False, f"правка дала бы SyntaxError: {сбой.msg} (строка {сбой.lineno})"
    рантайм.write_text(новый, encoding="utf-8")
    return True, "правлено"


def _данные(репо: pathlib.Path) -> pathlib.Path | None:
    настройка = репо / "config" / "site.json"
    try:
        cfg = json.loads(настройка.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    развёртка = cfg.get("deployment") or {}
    из_настройки = str(развёртка.get("data_dir") or "").replace(
        "<root>", str(развёртка.get("root") or ""))
    домен = str(cfg.get("domain") or "")
    для = pathlib.Path(из_настройки) if из_настройки.startswith("/") else None
    if для and для.is_dir():
        return для
    по_домену = pathlib.Path(f"/srv/{домен.replace('.', '-')}/data")
    return по_домену if по_домену.is_dir() else None


_H1 = re.compile(r"<h1[^>]*>(.*?)</h1>", re.S)
_МЕТКА = "Совпадений:"


def _обход(дай, слаги: list) -> tuple[int, int, list]:
    """Сплошной обход: по своему H1 карточка обязана быть первой.

    Повторяет приёмку линии SEO (`probe_cards.py`): запрос — это H1 САМОЙ
    карточки, а место считается только среди совпадений, до блока «Возможно,
    вы искали». Иначе подсказка засчиталась бы за находку.
    """
    первыми, проверено, беды = 0, 0, []
    for слаг in слаги:
        к, т = дай(f"/title/{слаг}/")
        if к != 200:
            беды.append(f"{слаг}: карточка ответила {к}")
            continue
        м = _H1.search(т)
        if not м:
            беды.append(f"{слаг}: у карточки нет H1 — искать нечем")
            continue
        имя = re.sub(r"<[^>]+>", "", м.group(1)).strip()
        кп, тп = дай("/search/?q=" + urllib.parse.quote(имя))
        if кп != 200:
            беды.append(f"{слаг}: поиск «{имя}» ответил {кп}")
            continue
        проверено += 1
        хвост = тп.split(_МЕТКА, 1)[1] if _МЕТКА in тп else ""
        порядок = list(dict.fromkeys(_КАРТОЧКА.findall(хвост)))
        if not порядок or порядок[0] != слаг:
            место = (порядок.index(слаг) + 1) if слаг in порядок else None
            беды.append(f"«{имя}» ({слаг}): место {место or 'нет в совпадениях'}")
        else:
            первыми += 1
    return первыми, проверено, беды


def _прогнать(репо: pathlib.Path, слаги: list | None = None) -> tuple[int, str]:
    данные_ист = _данные(репо)
    if данные_ист is None:
        return 2, "каталог данных не разрешился — проверка идёт на хосте площадки"
    домен = json.loads((репо / "config" / "site.json").read_text(
        encoding="utf-8")).get("domain") or ""
    врем = pathlib.Path(tempfile.mkdtemp(prefix="t347-port-"))
    данные = врем / "data"
    данные.mkdir()
    for ф in данные_ист.iterdir():
        цель = данные / ф.name
        try:
            if ф.is_dir() or ф.stat().st_size > (4 << 20):
                цель.symlink_to(ф)
            else:
                shutil.copyfile(ф, цель)
        except (PermissionError, OSError):
            pass
    с = socket.socket()
    с.bind(("127.0.0.1", 0))
    порт = с.getsockname()[1]
    с.close()
    процесс = subprocess.Popen(  # noqa: S603
        [sys.executable, "run.py", "--port", str(порт), "--data-dir", str(данные)],
        cwd=репо, env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"},
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)

    def дай(путь: str):
        к = http.client.HTTPConnection("127.0.0.1", порт, timeout=120)
        try:
            к.request("GET", путь, headers={"Host": домен})
            о = к.getresponse()
            return о.status, о.read().decode("utf-8", "replace")
        finally:
            к.close()

    try:
        поднялся = False
        for _ in range(300):
            if процесс.poll() is not None:
                хвост = (процесс.stdout.read() if процесс.stdout else "") or ""
                return 2, f"стенд не поднялся: {хвост.strip().splitlines()[-1][:200] if хвост.strip() else 'без вывода'}"
            try:
                if дай("/healthz")[0] == 200:
                    поднялся = True
                    break
            except OSError:
                pass
            time.sleep(1)
        if not поднялся:
            return 2, "стенд не поднялся за 300 с"
        беды = []
        проверено = 0
        for запрос, слаг in ЗАПРОСЫ:
            к, т = дай("/search/?q=" + urllib.parse.quote(запрос))
            if к != 200:
                беды.append(f"«{запрос}»: код {к}")
                continue
            карточки = _КАРТОЧКА.findall(т)
            проверено += 1
            if слаг not in карточки:
                беды.append(f"«{запрос}»: {слаг} не найден (первые {карточки[:2]})")
            elif карточки[0] != слаг:
                беды.append(f"«{запрос}»: {слаг} на {карточки.index(слаг)+1}-м месте")
        if беды:
            return 1, f"проверено {проверено} из {len(ЗАПРОСЫ)}; " + "; ".join(беды[:6])
        если_обход = ""
        if слаги:
            первыми, всего, беды_о = _обход(дай, слаги)
            если_обход = (f"; сплошной обход: первыми {первыми} из {всего}"
                          + (f", расхождения: {'; '.join(беды_о[:5])}"
                             if беды_о else ""))
            if беды_о:
                return 1, (f"все {проверено} запросов первыми, но обход не "
                           f"чистый{если_обход}")
        return 0, (f"все {проверено} запросов дают нужную работу первой"
                   + если_обход)
    finally:
        if процесс.poll() is None:
            процесс.terminate()
            try:
                процесс.wait(timeout=20)
            except subprocess.TimeoutExpired:
                процесс.kill()
        shutil.rmtree(врем, ignore_errors=True)


def _слаги_обхода(путь: pathlib.Path) -> tuple[list, str]:
    try:
        сырое = json.loads(путь.read_text(encoding="utf-8"))
    except (OSError, ValueError) as сбой:
        return [], f"список обхода не прочитан: {сбой!r}"
    записи = сырое if isinstance(сырое, list) else (сырое.get("cards") or [])
    слаги = []
    for з in записи:
        адрес = str((з or {}).get("url") or "")
        часть = адрес.rstrip("/").rsplit("/title/", 1)
        if len(часть) == 2 and часть[1]:
            слаги.append(часть[1])
    if not слаги:
        return [], "в списке обхода нет ни одного адреса карточки"
    return слаги, ""


def применить(репо: pathlib.Path, писать: bool,
             обход: pathlib.Path | None = None) -> tuple[str, str]:
    if not (репо / "src").is_dir():
        return "refuse", f"нет {репо / 'src'}"
    слаги: list = []
    if обход is not None:
        слаги, беда = _слаги_обхода(обход)
        if беда:
            return "refuse", беда
    elif писать:
        return "refuse", ("для доставки нужен --sweep: 19 случаев говорят, что "
                          "исправленное исправилось, и ничего не говорят о "
                          "регрессиях на остальных карточках")
    врем = pathlib.Path(tempfile.mkdtemp(prefix="t347-copy-"))
    try:
        копия = врем / "repo"
        shutil.copytree(репо, копия, symlinks=True,
                        ignore=shutil.ignore_patterns("__pycache__", ".git",
                                                      "var", "artifacts"))
        сделано, причина = _правка(копия)
        if not сделано:
            return ("skip", причина) if причина == "уже" else ("refuse", причина)
        код, пояснение = _прогнать(копия, слаги)
        if код == 2:
            return "refuse", f"НЕ ИЗМЕРЕНО: {пояснение}"
        if код != 0:
            return "refuse", f"прогон на копии не зелёный: {пояснение}"
    finally:
        shutil.rmtree(врем, ignore_errors=True)
    if not писать:
        return "ok", f"прогон на копии зелёный: {пояснение}; запись не велась"
    сделано, причина = _правка(репо)
    if not сделано:
        return "refuse", f"правка витрины не прошла: {причина}"
    код2, пояснение2 = _прогнать(репо, слаги)
    if код2 != 0:
        return "refuse", ("доставлено, но прогон в витрине не зелёный: "
                          f"{пояснение2} — откатите правку вручную")
    return "ok", f"доставлено и подтверждено прогоном: {пояснение2}"


def main() -> int:
    р = argparse.ArgumentParser()
    р.add_argument("--repo", required=True)
    р.add_argument("--check", action="store_true")
    р.add_argument("--dry-run", action="store_true")
    р.add_argument("--sweep", help="список приёмки со адресами карточек "
                                   "(sweep-<домен>.json); обязателен для доставки")
    а = р.parse_args()
    репо = pathlib.Path(а.repo).resolve()
    исход, пояснение = применить(
        репо, писать=not (а.check or а.dry_run),
        обход=pathlib.Path(а.sweep) if а.sweep else None)
    print(f"[{исход:6s}] {репо.name}: {пояснение}")
    if исход == "refuse":
        return 2
    if а.check:
        return 1 if исход == "ok" else 0
    return 0


if __name__ == "__main__":
    sys.exit(main())
