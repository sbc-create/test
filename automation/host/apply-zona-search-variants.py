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

ОБЁРТКА = """#!/usr/bin/env python3
\"\"\"Запуск витрины: закреплённый артефакт плюс правки сайта (T347).

Почему обёртка, а не правка артефакта
-------------------------------------

`src/lords-frontend.py` — ЗАКРЕПЛЁННЫЙ артефакт шаблона: `pins.lock.json`
сверяет его байты с исходным коммитом, и проверка выпускного набора
`verify_pins` отказывает при любом расхождении. Измерено 28.10: правка
наложений прямо в артефакте дала `pins-match-sources FAIL`
(«sha256 d0583aa04af2 вместо dd111ee18f2d»), и выпуск с таким состоянием не
прошёл бы. Путь «поправить шаблон и продвинуть» для этой витрины закрыт:
`promote-cell-pins.py` отказывает, когда у витрины есть свои имена вне канона,
а их тут 105 (у zona-03 — 100), и продвижение их стёрло бы.

Поэтому артефакт остаётся байт-в-байт своим пином, а правки ставятся ПОВЕРХ —
ровно так, как это сделано у `zonafilm.cc`. Точка входа объявлена в
`config/site.json: entrypoint`, откуда её и берёт `run.py` (строка 180), и
оттуда же её читает `entrypoint_present.py` — зеркало сходится по построению,
`pins.lock.json` не трогается.

`--check` сюда не доходит: его обрабатывает сам `run.py` ранним возвратом.
\"\"\"
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

КОРЕНЬ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(КОРЕНЬ))

#: Имя артефакта берётся из замка, а не из кода: так обёртка не станет вторым
#: местом, где это имя записано.
_ПИНЫ = json.loads((КОРЕНЬ / "pins.lock.json").read_text(encoding="utf-8"))
АРТЕФАКТ = КОРЕНЬ / "src" / str(_ПИНЫ["pins"]["entrypoint"])


def загрузить_рантайм():
    \"\"\"Импорт закреплённого артефакта как модуля, с регистрацией в sys.modules.

    Регистрация обязательна: артефакт и его соседи импортируют друг друга по
    имени, а наложения ставятся на этот же объект модуля.
    \"\"\"
    if not АРТЕФАКТ.is_file():
        raise SystemExit(f"нет артефакта {АРТЕФАКТ}")
    sys.path.insert(0, str(АРТЕФАКТ.parent))
    спец = importlib.util.spec_from_file_location("nova_runtime", АРТЕФАКТ)
    модуль = importlib.util.module_from_spec(спец)
    sys.modules["nova_runtime"] = модуль
    спец.loader.exec_module(модуль)
    return модуль


def применить(рантайм) -> list:
    \"\"\"Поставить правки сайта поверх рантайма. Возвращает их перечень.

    Порядок обязателен: одноимённые, затем дословное имя (имя работы сильнее
    числа голосов), затем короткие слова — их повтор должен пройти через оба
    упорядочивания.
    \"\"\"
    from src import search_aliases, search_exact_form
    from src import search_same_name, search_short_words

    словарь = json.loads((КОРЕНЬ / "config" / "search-aliases.json")
                         .read_text(encoding="utf-8"))
    внесено = [
        search_aliases.установить(рантайм, словарь),
        search_same_name.установить(рантайм),
        search_exact_form.установить(рантайм),
        search_short_words.установить(рантайм),
    ]
    return внесено


def main() -> int:
    рантайм = загрузить_рантайм()
    внесено = применить(рантайм)
    домен = json.loads((КОРЕНЬ / "config" / "site.json")
                       .read_text(encoding="utf-8")).get("domain", "витрина")
    print(f"[{домен}] правки сайта: {', '.join(внесено)}", flush=True)
    return рантайм.main()


if __name__ == "__main__":
    raise SystemExit(main())
"""

ЯКОРЬ_УСТАРЕЛ = "def main() -> int:"

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

class _СамРантайм:
    """Доступ к глобальным именам этого модуля как к атрибутам.

    Нельзя брать `sys.modules[__name__]`: проверка, которая загружает рантайм
    модулем (`spec_from_file_location("ядро", …)` + `exec_module`), в
    `sys.modules` его НЕ регистрирует, и обращение падало с `KeyError: 'ядро'`
    — измерено полным набором zonafilm.space 28.10 на checks/similar_fast.py.
    На живом сайте `run.py` исполняет файл как `__main__`, поэтому там дефект
    не проявлялся: прогон двух выбранных проверок его и не увидел.

    Посредник читает и ПИШЕТ настоящие глобальные имена, поэтому обёртки
    (`построить_индекс`, `Данные.искать`) попадают туда же, откуда их берёт
    `main()`.
    """

    def __getattr__(self, имя):
        try:
            return globals()[имя]
        except KeyError as сбой:
            raise AttributeError(имя) from сбой

    def __setattr__(self, имя, значение):
        globals()[имя] = значение


_ЭТОТ_РАНТАЙМ = _СамРантайм()

_ВАРИАНТЫ_НАЗВАНИЯ = [
    _СИНОНИМЫ.установить(_ЭТОТ_РАНТАЙМ, json.loads(
        (Path(__file__).resolve().parent.parent / "config"
         / "search-aliases.json").read_text(encoding="utf-8"))),
    _ОДНОИМЁННЫЕ.установить(_ЭТОТ_РАНТАЙМ),
    _ДОСЛОВНО.установить(_ЭТОТ_РАНТАЙМ),
    _КОРОТКИЕ.установить(_ЭТОТ_РАНТАЙМ),
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
    """Обёртка и объявление точки входа. Закреплённый артефакт НЕ трогается.

    Измерено 28.10: правка наложений прямо в `src/lords-frontend.py` дала
    `pins-match-sources FAIL` — артефакт закреплён в `pins.lock.json`, и
    выпускная проверка сверяет его байты. Поэтому ставится обёртка:
    `run.py` берёт путь из `config["entrypoint"]` (строка 180), а
    `entrypoint_present.py` читает то же поле первым, так что зеркало сходится,
    а замок остаётся нетронутым.
    """
    артефакт = репо / "src" / "lords-frontend.py"
    if not артефакт.is_file():
        return False, f"нет артефакта {артефакт}"
    текст = артефакт.read_text(encoding="utf-8")
    if "_ВАРИАНТЫ_НАЗВАНИЯ" in текст:
        return False, ("артефакт несёт прежнюю вставку — сперва верните его к "
                       "закреплённым байтам")
    плохие = [и for и in ИМЕНА if текст.count(и) != 1]
    if плохие:
        return False, ("в рантайме нет или неоднозначны имена: "
                       + ", ".join(и.strip() for и in плохие))
    настройка = репо / "config" / "site.json"
    if not настройка.is_file():
        return False, f"нет {настройка}"
    cfg = json.loads(настройка.read_text(encoding="utf-8"))
    if str(cfg.get("entrypoint") or "") == "serve.py" and (репо / "src" / "serve.py").is_file():
        return False, "уже"
    for имя in МОДУЛИ:
        источник = ИСТОЧНИК / "src" / имя
        if not источник.is_file():
            return False, f"нет источника модуля {источник}"
        (репо / "src" / имя).write_bytes(источник.read_bytes())
    словарь = ИСТОЧНИК / "config" / СЛОВАРЬ
    if not словарь.is_file():
        return False, f"нет словаря {словарь}"
    (репо / "config" / СЛОВАРЬ).write_bytes(словарь.read_bytes())
    try:
        ast.parse(ОБЁРТКА)
    except SyntaxError as сбой:
        return False, f"обёртка не разбирается: {сбой.msg}"
    (репо / "src" / "serve.py").write_text(ОБЁРТКА, encoding="utf-8")
    cfg["entrypoint"] = "serve.py"
    настройка.write_text(json.dumps(cfg, ensure_ascii=False, indent=1) + "\n",
                         encoding="utf-8")
    return True, "обёртка поставлена, точка входа объявлена в config/site.json"


def _замок_и_зеркало(репо: pathlib.Path) -> list[str]:
    """Две выпускные проверки, ради которых прежний слой и отменён."""
    беды = []
    for имя in ("verify_pins", "entrypoint_present"):
        файл = репо / "checks" / f"{имя}.py"
        if not файл.is_file():
            continue
        готово = subprocess.run(  # noqa: S603
            [sys.executable, f"checks/{имя}.py"], cwd=репо,
            capture_output=True, text=True, timeout=600)
        if готово.returncode != 0:
            хвост = ((готово.stdout or "") + (готово.stderr or "")).strip()
            беды.append(f"{имя}: код {готово.returncode} — "
                        + (хвост.splitlines()[-1][:120] if хвост else "без вывода"))
    return беды


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


def _обход(дай, слаги: list) -> tuple[int, int, list, dict]:
    """Сплошной обход: по своему H1 карточка обязана быть первой.

    Повторяет приёмку линии SEO (`probe_cards.py`): запрос — это H1 САМОЙ
    карточки, а место считается только среди совпадений, до блока «Возможно,
    вы искали». Иначе подсказка засчиталась бы за находку.
    """
    первыми, проверено, беды = 0, 0, []
    # Распределение мест целиком: «первыми 109 из 109» не отличает «остальные
    # вторыми» от «остальных нет в совпадениях вовсе», а это разные беды.
    распределение: dict = {}
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
        место = (порядок.index(слаг) + 1) if слаг in порядок else None
        ключ = str(место) if место else "нет в совпадениях"
        распределение[ключ] = распределение.get(ключ, 0) + 1
        if место == 1:
            первыми += 1
        else:
            беды.append(f"«{имя}» ({слаг}): место {место or 'нет в совпадениях'}")
    return первыми, проверено, беды, распределение


def _погасить_сирот() -> None:
    """Снять свои осиротевшие стенды ПЕРЕД подъёмом нового.

    Сирота переживает `finally` по определению: когда родитель умирает раньше
    (timeout, kill, конец хода), `finally` не исполняется вообще. Измерено
    28.10: стенд прожил 409 минут с ppid 1 и держал 598 МиБ, из-за чего шлюз
    фонового редактора трижды не запустился. Поэтому уборка — перед подъёмом.
    """
    import importlib.util as _иу
    путь = pathlib.Path(__file__).resolve().parent / "_orphan_stands.py"
    if not путь.is_file():
        return
    спец = _иу.spec_from_file_location("_orphan_stands", путь)
    if спец is None or спец.loader is None:
        return
    модуль = _иу.module_from_spec(спец)
    try:
        спец.loader.exec_module(модуль)
        модуль.погасить(pathlib.Path("/home/claude/wt-nova-publish-memory-02"))
    except Exception:  # noqa: BLE001 — уборка не обязана мешать прогону
        return


def _прогнать(репо: pathlib.Path, слаги: list | None = None) -> tuple[int, str]:
    _погасить_сирот()
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
            первыми, всего, беды_о, распределение = _обход(дай, слаги)
            места = ", ".join(f"{к}: {распределение[к]}"
                              for к in sorted(распределение,
                                              key=lambda з: (not з.isdigit(),
                                                             int(з) if з.isdigit() else 0)))
            если_обход = (f"; сплошной обход: первыми {первыми} из {всего}"
                          f"; распределение мест — {места}"
                          + (f"; расхождения: {'; '.join(беды_о[:5])}"
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
        беды_выпуска = _замок_и_зеркало(копия)
        if беды_выпуска:
            return "refuse", ("выпускные проверки не зелёные: "
                              + "; ".join(беды_выпуска))
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
