#!/usr/bin/env python3
"""Подключить механизм режима индексации витрине AnimeGo прямой установки.

    python3 automation/local/wire-animego-indexing.py --repo var/site-repos/<проект> [--dry-run]

Что измерено и почему нужен инструмент
--------------------------------------

`an1mego.site` и `animeg0.site` установлены ПРЯМО: рабочая копия лежит в
`/srv/<учётная запись>/app`, доставка идёт их собственным `deploy/install.sh`
(rsync + юниты + restart), очереди выпусков у них нет. Это не делает их
тестовыми: домены разрешаются в адрес площадки, отдают 200 и живут под своими
юнитами.

Режим индексации в их рантайме ЗАШИТ: `noindex, nofollow` стоит тремя
мета-тегами в шаблонах страниц и двумя заголовками; поле
`config/site.json: indexing_enabled` читают только `tools/stamp_manifest.py`
и `tools/new_site.py`, то есть сам рантайм его не спрашивает. Переключить
такой домен нельзя ничем.

У ОТКРЫТОГО соседа того же семейства и той же точки входа (`an1meg0.site`,
`src/animego-frontend.py`) механизм есть, и он общий для Animedia, Lords и
Zona: модуль `indexing_mode.py` + две переменные окружения от `run.py`.
Инструмент переносит именно его — байт в байт тот же модуль из шаблона
семейства, те же имена переменных, те же функции.

Что делается

1. `src/indexing_mode.py` — копия шаблона `automation/host/indexing_mode.py`;
2. блок чтения режима в рантайм: `режим_индексации()`, `мета_роботов()`,
   `_тело_robots()` — дословно как у соседа;
3. три мета-тега и ОДИН заголовок обычных страниц переводятся на
   `мета_роботов()`;
4. `/robots.txt` отдаётся из `_тело_robots()`;
5. `run.py` передаёт рантайму домен и разрешение выпуска;
6. `config/site.json` получает раздел `indexing` с разрешением выпуска.

Чего инструмент НЕ делает

* не снимает запрет со СЛУЖЕБНОГО пути `/poster/`: там заголовок остаётся
  зашитым, и это верно — служебные адреса закрыты независимо от режима сайта;
* не открывает домен. Открытие — отдельная штатная операция со своими
  предпроверками: разрешение владельца, разрешение выпуска, слой nginx;
* не правит ничего вслепую: без любой точки вставки отказывает с названной
  причиной и не меняет ни одного файла.
"""
from __future__ import annotations

import argparse
import json
import pathlib
import sys

КОРЕНЬ = pathlib.Path(__file__).resolve().parents[2]
ШАБЛОН_МОДУЛЯ = КОРЕНЬ / "automation" / "host" / "indexing_mode.py"

ЯКОРЬ_БЛОКА = 'СЕМЕЙСТВО = МАНИФЕСТ["template_family"]\nСБОРКА = МАНИФЕСТ["build_id"]'

БЛОК = '''СЕМЕЙСТВО = МАНИФЕСТ["template_family"]

# Читатель режима индексации. Общий файл семейств: тот же, что у Animedia и
# Lords, байт в байт (`automation/host/indexing_mode.py`). Отсутствие модуля
# витрину не роняет, но и не открывает: решение тогда ЗАКРЫТО с названной
# причиной — витрина, которая не умеет спросить про режим, не вправе считать
# себя открытой.
try:
    import indexing_mode as ИНДЕКС
except ImportError:
    ИНДЕКС = None

#: Домен витрины и РАЗРЕШЕНИЕ ВЫПУСКА приходят окружением из `run.py`.
#: Имена переменных — те же, что читает сам модуль (`LORDS_INDEXING_ROOT`):
#: третий префикс для одного и того же понятия означал бы третье имя и
#: расхождение при первой же правке.
ИНДЕКС_ДОМЕН = os.environ.get("LORDS_INDEXING_SITE", "").strip()
ИНДЕКС_РАЗРЕШЕНО_ВЫПУСКОМ = (
    os.environ.get("LORDS_INDEXING_RELEASE_PERMITS_OPEN", "").strip().lower()
    == "true")


def режим_индексации() -> tuple:
    """(состояние, причина). Любая беда — ЗАКРЫТО с названной причиной."""
    if ИНДЕКС is None:
        return ("CLOSED", "модуль indexing_mode не найден: режим не вычисляется")
    try:
        return ИНДЕКС.режим(ИНДЕКС_ДОМЕН,
                            разрешено_выпуском=ИНДЕКС_РАЗРЕШЕНО_ВЫПУСКОМ)
    except Exception:  # noqa: BLE001 — беда режима не открывает сайт
        return ("CLOSED", "ошибка вычисления режима")


def мета_роботов() -> str:
    """Значение `<meta name="robots">` и `X-Robots-Tag` обычных страниц."""
    состояние, _ = режим_индексации()
    if ИНДЕКС is None:
        return "noindex, nofollow"
    return ИНДЕКС.МЕТА.get(состояние, "noindex, nofollow")


def _тело_robots() -> str:
    """Содержимое `/robots.txt` по текущему режиму."""
    состояние, _ = режим_индексации()
    if ИНДЕКС is None:
        return "User-agent: *\\nDisallow: /\\n"
    return ИНДЕКС.robots_txt(состояние)


СБОРКА = МАНИФЕСТ["build_id"]'''

МЕТА_СТАРАЯ = '<meta name="robots" content="noindex, nofollow">'
МЕТА_НОВАЯ = '<meta name="robots" content="{мета_роботов()}">'

#: Заголовок ОБЫЧНЫХ страниц. Отличается от служебного ОТСТУПОМ и соседями:
#: общий метод отдачи стоит на 8 пробелах и не ставит `Cache-Control`, а ветка
#: постера — на 12 и кэширует на сутки. Измерено 2026-10-05: якорь по 12
#: пробелам совпал бы именно со служебной ветвью, и правка сняла бы запрет
#: там, где он обязателен всегда.
ЗАГОЛОВОК_СТАРЫЙ = ('        self.send_header("Content-Length", str(len(тело)))\n'
                    '        self.send_header("X-Robots-Tag", "noindex, nofollow")')
ЗАГОЛОВОК_НОВЫЙ = ('        self.send_header("Content-Length", str(len(тело)))\n'
                   '        self.send_header("X-Robots-Tag", мета_роботов())')

ROBOTS_СТАРЫЙ = ('        if путь == "/robots.txt":\n'
                 '            return self._отдать(b"User-agent: *\\nDisallow: /\\n", '
                 '"text/plain; charset=utf-8")')
ROBOTS_НОВЫЙ = ('        if путь == "/robots.txt":\n'
                '            return self._отдать(_тело_robots().encode("utf-8"), '
                '"text/plain; charset=utf-8")')

ЯКОРЬ_СРЕДЫ = '''    контакт = str(конфиг.get("contact_email") or "").strip()
    if контакт:
        среда["SITE_CONTACT_EMAIL"] = контакт'''

СРЕДА = '''    контакт = str(конфиг.get("contact_email") or "").strip()
    if контакт:
        среда["SITE_CONTACT_EMAIL"] = контакт

    # РЕЖИМ ИНДЕКСАЦИИ. Домен нужен рантайму, чтобы спросить про СВОЙ режим:
    # файл состояния лежит по имени домена, и без него витрина спросила бы про
    # чужой. Разрешение ВЫПУСКА приезжает отдельной переменной: это
    # способность кода поддержать открытие, а не разрешение владельца —
    # последнее живёт в каталоге root и этой переменной не выдаётся.
    #
    # Стоит ДО раннего возврата `--check`: иначе проверка конфигурации не
    # касалась бы этих строк вовсе.
    домен_для_режима = str(конфиг.get("domain") or "").strip()
    if домен_для_режима:
        среда["LORDS_INDEXING_SITE"] = домен_для_режима
    среда["LORDS_INDEXING_RELEASE_PERMITS_OPEN"] = (
        "true" if (конфиг.get("indexing") or {}).get("release_permits_open") is True
        else "false")'''


class ОтказИнструмента(RuntimeError):
    """Инструмент остановился с названной причиной. Вслепую он не правит."""


def патч_рантайма(текст: str) -> str:
    if "мета_роботов" in текст:
        return ""
    if текст.count(ЯКОРЬ_БЛОКА) != 1:
        raise ОтказИнструмента(
            "нет точки вставки блока режима (СЕМЕЙСТВО/СБОРКА из манифеста)")
    if текст.count(МЕТА_СТАРАЯ) != 3:
        raise ОтказИнструмента(
            f"мета-тегов запрета {текст.count(МЕТА_СТАРАЯ)}, а ожидалось 3: "
            "состав шаблонов изменился, вслепую не правлю")
    if текст.count(ЗАГОЛОВОК_СТАРЫЙ) != 1:
        raise ОтказИнструмента(
            "заголовок обычных страниц не найден однозначно: его сосед "
            "`Content-Length` обязателен, иначе правка задела бы служебный путь")
    if текст.count(ROBOTS_СТАРЫЙ) != 1:
        raise ОтказИнструмента("ветка /robots.txt не найдена")
    if "import os" not in текст:
        raise ОтказИнструмента("в рантайме нет `import os`: переменные не прочитать")
    текст = текст.replace(ЯКОРЬ_БЛОКА, БЛОК, 1)
    текст = текст.replace(МЕТА_СТАРАЯ, МЕТА_НОВАЯ)
    текст = текст.replace(ЗАГОЛОВОК_СТАРЫЙ, ЗАГОЛОВОК_НОВЫЙ, 1)
    текст = текст.replace(ROBOTS_СТАРЫЙ, ROBOTS_НОВЫЙ, 1)
    return текст


def патч_лаунчера(текст: str) -> str:
    if "LORDS_INDEXING_SITE" in текст:
        return ""
    if текст.count(ЯКОРЬ_СРЕДЫ) != 1:
        raise ОтказИнструмента(
            "в run.py нет точки вставки переменных (блок SITE_CONTACT_EMAIL)")
    return текст.replace(ЯКОРЬ_СРЕДЫ, СРЕДА, 1)


def главная(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--repo", required=True)
    p.add_argument("--dry-run", action="store_true")
    args = p.parse_args(argv)

    репо = pathlib.Path(args.repo)
    пакет_путь = репо / "config" / "site.json"
    if not пакет_путь.is_file():
        print(f"{репо}: не похоже на репозиторий сайта", file=sys.stderr)
        return 2
    пакет = json.loads(пакет_путь.read_text(encoding="utf-8"))
    точка = репо / "src" / str(пакет.get("entrypoint") or "animego-frontend.py")
    лаунчер = репо / "run.py"
    if not точка.is_file() or not лаунчер.is_file():
        print(f"{репо}: нет {точка.name} или run.py", file=sys.stderr)
        return 2
    if not ШАБЛОН_МОДУЛЯ.is_file():
        print(f"нет шаблона {ШАБЛОН_МОДУЛЯ}", file=sys.stderr)
        return 2

    сделано: list[str] = []
    записать: dict[pathlib.Path, bytes] = {}
    try:
        новый_рантайм = патч_рантайма(точка.read_text(encoding="utf-8"))
        новый_лаунчер = патч_лаунчера(лаунчер.read_text(encoding="utf-8"))
    except ОтказИнструмента as отказ:
        print(f"{репо.name}: {отказ}", file=sys.stderr)
        return 3
    if новый_рантайм:
        записать[точка] = новый_рантайм.encode("utf-8")
        сделано.append(f"{точка.name}: блок режима, 3 мета-тега, заголовок, robots.txt")
    if новый_лаунчер:
        записать[лаунчер] = новый_лаунчер.encode("utf-8")
        сделано.append("run.py: LORDS_INDEXING_SITE и разрешение выпуска")

    модуль = ШАБЛОН_МОДУЛЯ.read_bytes()
    цель_модуля = репо / "src" / "indexing_mode.py"
    if (цель_модуля.read_bytes() if цель_модуля.is_file() else b"") != модуль:
        записать[цель_модуля] = модуль
        сделано.append("indexing_mode.py: общий модуль семейств из шаблона")

    # Разрешение ВЫПУСКА объявляется пакетом. Значение false: открытие — это
    # отдельное решение владельца и отдельная операция.
    раздел = пакет.get("indexing")
    if not isinstance(раздел, dict) or "release_permits_open" not in раздел:
        пакет["indexing"] = {
            "release_permits_open": False,
            "note": ("Техническая способность выпуска поддержать открытие. "
                     "Рантайм читает режим через src/indexing_mode.py, домен и "
                     "это разрешение приходят окружением из run.py. Разрешение "
                     "ВЛАДЕЛЬЦА живёт отдельно, в каталоге root, и этим полем "
                     "не выдаётся."),
        }
        записать[пакет_путь] = (json.dumps(пакет, ensure_ascii=False, indent=2)
                                + "\n").encode("utf-8")
        сделано.append("config/site.json: indexing.release_permits_open = false")

    if not сделано:
        print(f"{репо.name}: механизм уже подключён — ничего не меняю")
        return 0
    print(f"{репо.name}:")
    for строка in сделано:
        print("   ", строка)
    if args.dry_run:
        print("сухой прогон: файлы не менялись")
        return 0
    непишущиеся = [str(п) for п in записать
                   if п.exists() and not p_доступен(п)]
    if непишущиеся:
        print(f"{репо.name}: файлы только для чтения: {', '.join(непишущиеся)}",
              file=sys.stderr)
        return 5
    for путь, байты in записать.items():
        путь.write_bytes(байты)
    print("дальше обязательны: update_pins и checks/run.sh в этом репозитории")
    return 0


def p_доступен(путь: pathlib.Path) -> bool:
    import os as _os
    return _os.access(путь, _os.W_OK)


if __name__ == "__main__":
    raise SystemExit(главная())
