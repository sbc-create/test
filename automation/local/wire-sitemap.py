#!/usr/bin/env python3
"""Подключить карту сайта к витрине семейства lords/zona.

    python3 automation/local/wire-sitemap.py --repo var/site-repos/<проект> \\
        --sections /movies/ /series/ /animation/ [--dry-run]

Зачем инструмент, а не правка руками в каждом репозитории
---------------------------------------------------------
Подключение состоит из пяти однотипных правок, и все пять уже сделаны для
lordserials22.info. Повторять их руками в четырёх оставшихся репозиториях
значит четыре раза ошибиться по-разному: `lords-frontend.py` у каждого сайта
свой, а правки — одни и те же.

Что делает:

1. копирует ОБЩИЙ `seo_layer.py` из шаблона семейства (в нём живёт сборщик
   карты; файл у семейства один и совпадает с шаблоном побайтово);
2. объявляет `РАЗДЕЛЫ_КАРТЫ` — перечень разделов ЭТОГО сайта;
3. ставит ссылку на карту в `robots.txt` только при существующей карте;
4. делает маршрут `/sitemap.xml` fail-closed: закрытая витрина карту не
   отдаёт даже при готовых файлах;
5. заводит фоновое обновление карты в `main()`;
6. добавляет в лаунчер правило `LORDS_SITEMAP_DIR = <data>/sitemap`.

Чего инструмент НЕ делает: не выдумывает разделы. Их перечень передаётся
явно, потому что он у сайтов РАЗНЫЙ — измерено 2026-10-04: у
lordserials22.info есть `/anime/` и `/dorama/`, а у lordfilm47.space те же
адреса отвечают 404. Раздел, попавший в карту по аналогии, дал бы поисковику
ошибочный адрес.

Проверять ответы разделов — обязанность вызывающего: инструмент принимает то,
что ему назвали, и печатает это в отчёте.
"""
from __future__ import annotations

import argparse
import pathlib
import re
import sys

КОРЕНЬ = pathlib.Path(__file__).resolve().parents[2]
ШАБЛОН = КОРЕНЬ / "automation" / "host"

ОБЪЯВЛЕНИЕ = ('SITEMAP_DIR = os.environ.get("LORDS_SITEMAP_DIR", "").strip()')

ДОМЕН_КАРТЫ = '''
#: Домен, которым подписываются адреса карты. Та же цепочка переменных, что у
#: сборщика (`seo_layer.запустить_карту`): расхождение имён дало бы карту с
#: адресами одного домена, объявленную на другом.
ДОМЕН_КАРТЫ = (os.environ.get("LORDS_SITE_HOST")
               or os.environ.get("LORDS_INDEXING_SITE")
               or os.environ.get("LORDS_SITE_DOMAIN") or "").strip()'''

МАРШРУТ_СТАРЫЙ = '''        if путь == "/sitemap.xml" or re.fullmatch(r"/sitemap-\\d+\\.xml", путь):
            if not SITEMAP_DIR:'''
МАРШРУТ_НОВЫЙ = '''        if путь == "/sitemap.xml" or re.fullmatch(r"/sitemap-\\d+\\.xml", путь):
            # Закрытая витрина карту не отдаёт даже при готовых файлах: карта —
            # приглашение к обходу, и на закрытом домене она противоречила бы
            # и заголовку, и robots.txt. Файлы при этом не удаляются: закрытие
            # обратимо, а удаление — нет.
            if режим_индексации()[0] != "OPEN":
                return self._отдать(b"", "text/plain; charset=utf-8", код=404)
            if not SITEMAP_DIR:'''

ROBOTS_СТАРЫЙ = '''def _тело_robots() -> str:
    """Содержимое `/robots.txt` по текущему режиму."""
    состояние, _ = режим_индексации()
    try:
        import indexing_mode
        return indexing_mode.robots_txt(состояние)
    except Exception:  # noqa: BLE001 — без модуля остаёмся закрытыми
        return "User-agent: *\\nDisallow: /\\n"'''
ROBOTS_НОВЫЙ = '''def _тело_robots() -> str:
    """Содержимое `/robots.txt` по текущему режиму.

    Ссылка на карту ставится ТОЛЬКО если карта действительно отдаётся:
    `Sitemap:` на адрес, отвечающий 404, — обещание, которого витрина не
    выполняет, и обходчик запоминает именно его. Условий три, и все
    обязательны: открытый режим, заданный каталог карты и существующий в нём
    `sitemap.xml`.
    """
    состояние, _ = режим_индексации()
    карта = ""
    if состояние == "OPEN" and SITEMAP_DIR and ДОМЕН_КАРТЫ:
        try:
            if (Path(SITEMAP_DIR) / "sitemap.xml").is_file():
                карта = f"https://{ДОМЕН_КАРТЫ}/sitemap.xml"
        except OSError:
            карта = ""
    try:
        import indexing_mode
        return indexing_mode.robots_txt(состояние, sitemap=карта)
    except Exception:  # noqa: BLE001 — без модуля остаёмся закрытыми
        return "User-agent: *\\nDisallow: /\\n"'''

ЗАГОЛОВОК_СТАРЫЙ = '        self.send_header("X-Robots-Tag", мета_роботов())'
ЗАГОЛОВОК_НОВЫЙ = ('        self.send_header("X-Robots-Tag",\n'
                   '                         мета_роботов_пути(self.path or "/"))')

ПО_ПУТИ = '''

def мета_роботов_пути(путь: str) -> str:
    """Значение `X-Robots-Tag` для КОНКРЕТНОГО пути: служебные закрыты всегда.

    Измерено 2026-10-04 на открытом домене: `/healthz` отдавал ДВА заголовка —
    `index, follow` от приложения и `noindex, nofollow` от nginx. Запрет
    держался только на слое nginx, а ответ противоречил сам себе. Полагаться на
    разрешение конфликта нельзя: запрет служебного пути обязан стоять там, где
    этот путь и отдаётся.

    Перечень берётся из `indexing_mode.СЛУЖЕБНЫЕ_ЗАПРЕТЫ` — того же, из
    которого собираются `robots.txt` и карта запретов nginx.
    """
    try:
        import indexing_mode
        служебные = tuple(indexing_mode.СЛУЖЕБНЫЕ_ЗАПРЕТЫ)
    except Exception:  # noqa: BLE001 — без модуля служебные всё равно закрыты
        служебные = ("/poster/", "/api/", "/healthz", "/__")
    п = (путь or "/").split("?", 1)[0]
    if any(п.startswith(с) for с in служебные):
        return "noindex, nofollow"
    return мета_роботов()

'''

ЗАПУСК = '''    # Карта сайта собирается ФОНОМ и никогда в пути запроса: сборка идёт по
    # всему снимку каталога, и делать её при отдаче страницы значило бы
    # заставить посетителя ждать.
    #
    # Сборщик живёт в общем `seo_layer`: файл у семейства один, и выпуск
    # доставляет его всем сайтам сразу. Молчаливый пропуск запрещён — причина
    # называется в журнале.
    try:
        import seo_layer as _карта
    except ImportError:
        _карта = None
    if _карта is None:
        print("[nova] карта сайта не заводится: модуля seo_layer нет", flush=True)
    elif not hasattr(_карта, "запустить_карту"):
        print("[nova] карта сайта не заводится: в seo_layer нет запустить_карту "
              "(выпуск несёт прежнюю версию модуля)", flush=True)
    else:
        _карта.запустить_карту(sys.modules[__name__])

'''


def разделы_блок(разделы: list[str]) -> str:
    строки = ", ".join(f'"{р}"' for р in разделы)
    return f'''
#: Разделы, попадающие в карту сайта. Перечень ЯВНЫЙ и ИЗМЕРЕННЫЙ: в карту
#: идёт только то, что витрина действительно отдаёт кодом 200. У сайтов
#: семейства наборы РАЗНЫЕ — у одного есть `/anime/` и `/dorama/`, у другого
#: те же адреса отвечают 404, — поэтому раздел по аналогии не добавляется.
РАЗДЕЛЫ_КАРТЫ = ({строки},)
'''


def главная(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--repo", required=True)
    p.add_argument("--sections", nargs="+", required=True,
                   help="разделы ЭТОГО сайта, проверенные ответом 200")
    p.add_argument("--dry-run", action="store_true")
    args = p.parse_args(argv)

    репо = pathlib.Path(args.repo)
    if not (репо / "config" / "site.json").is_file():
        print(f"{репо}: не похоже на репозиторий сайта", file=sys.stderr)
        return 2
    cfg = (репо / "config" / "site.json").read_text(encoding="utf-8")
    точка = re.search(r'"entrypoint"\s*:\s*"([^"]+)"', cfg)
    if not точка:
        print("в config/site.json нет entrypoint", file=sys.stderr)
        return 2
    витрина = репо / "src" / точка.group(1)
    лаунчер = репо / "run.py"
    if not витрина.is_file():
        print(f"нет витрины {витрина}", file=sys.stderr)
        return 2

    сделано: list[str] = []
    т = витрина.read_text(encoding="utf-8")
    if "запустить_карту" in т:
        print(f"{репо.name}: карта уже подключена — ничего не меняю")
        return 0
    # АДАПТЕР НАД ОБЩИМ ЯДРОМ — отдельный случай, и правка ядра здесь
    # запрещена правилами самого репозитория: `src/lords-frontend.py` совпадает
    # с ядром соседа байт в байт и закреплён в `pins.lock.json` с
    # происхождением `verified_against: git`; его `AGENTS.md` требует менять
    # ядро отдельной задачей и отдельным коммитом производителя. Измерено
    # 2026-10-04: так устроены lordfilm47.space и lordserial33.biz, а
    # lordserials22.info, 1lordserials1.online, zonafilm.space и
    # zonafilm12.site — монолиты, где точка входа и есть рантайм.
    ядро = репо / "src" / "lords-frontend.py"
    if ОБЪЯВЛЕНИЕ not in т and ядро.is_file() and витрина != ядро:
        if ОБЪЯВЛЕНИЕ in ядро.read_text(encoding="utf-8"):
            print(f"{репо.name}: точка входа {витрина.name} — АДАПТЕР над общим "
                  f"ядром {ядро.name}. Подключение идёт в ядро семейства "
                  "отдельной задачей: правка ядра в этом репозитории запрещена "
                  "его собственными правилами (замок версий с происхождением "
                  "`verified_against: git`).", file=sys.stderr)
            return 4
    for якорь, что in ((ОБЪЯВЛЕНИЕ, "SITEMAP_DIR"), (МАРШРУТ_СТАРЫЙ, "маршрут карты"),
                       (ROBOTS_СТАРЫЙ, "_тело_robots"),
                       (ЗАГОЛОВОК_СТАРЫЙ, "отдача заголовка")):
        if якорь not in т:
            print(f"{репо.name}: нет точки вставки «{что}» — правка не "
                  "применяется вслепую", file=sys.stderr)
            return 3
    т = т.replace(ОБЪЯВЛЕНИЕ, ОБЪЯВЛЕНИЕ + ДОМЕН_КАРТЫ + разделы_блок(args.sections), 1)
    т = т.replace(МАРШРУТ_СТАРЫЙ, МАРШРУТ_НОВЫЙ, 1)
    т = т.replace(ROBOTS_СТАРЫЙ, ПО_ПУТИ.strip("\n") + "\n\n\n" + ROBOTS_НОВЫЙ, 1)
    т = т.replace(ЗАГОЛОВОК_СТАРЫЙ, ЗАГОЛОВОК_НОВЫЙ, 1)
    м = re.search(r"^(    import time as _time\n)", т, re.M)
    if not м:
        print(f"{репо.name}: нет точки запуска в main()", file=sys.stderr)
        return 3
    т = т[:м.start(1)] + ЗАПУСК + т[м.start(1):]
    сделано.append(f"{витрина.name}: разделы, robots, маршрут, заголовок по пути, запуск")

    # КАТАЛОГ КАРТЫ: два законных способа, и выбирается тот, который у сайта
    # есть. У части лаунчеров есть функция дополнений — там правило выводится
    # из `--data-dir`. У остальных (193 строки против 236) переменные
    # объявляет `config/site.json: environment`, а `<data>` подставляет
    # `environment()`. Результат один; подменять одну форму другой незачем.
    л = лаунчер.read_text(encoding="utf-8")
    правка_лаунчера = None
    правка_пакета = False
    уже_есть = "LORDS_SITEMAP_DIR" in л or "LORDS_SITEMAP_DIR" in cfg
    if not уже_есть:
        if "def дополнения(config: dict) -> dict:" in л:
            якорь = '    доп["LORDS_INDEXING_RELEASE_PERMITS_OPEN"] = ('
            if якорь not in л:
                print(f"{репо.name}: в лаунчере есть дополнения, но нет якоря "
                      "режима индексации — вслепую не правлю", file=sys.stderr)
                return 3
            правка_лаунчера = л.replace(
                "def дополнения(config: dict) -> dict:",
                "def дополнения(config: dict, данные: Path | None = None) -> dict:", 1)
            правка_лаунчера = правка_лаунчера.replace(якорь, '''    # Каталог карты сайта выводится из каталога ДАННЫХ, а не объявляется в
    # пакете: правило одно на все сайты семейства, и забыть его при заведении
    # следующего сайта нечем. Писать туда вправе только сама витрина — это
    # единственный путь, открытый её юнитом на запись.
    if данные is not None:
        доп["LORDS_SITEMAP_DIR"] = str(данные / "sitemap")

''' + якорь, 1)
            правка_лаунчера = правка_лаунчера.replace(
                "    env.update(дополнения(config))",
                "    env.update(дополнения(config, data))", 1)
            сделано.append("run.py: LORDS_SITEMAP_DIR из --data-dir")
        elif '"environment"' in cfg:
            правка_пакета = True
            сделано.append("config/site.json: LORDS_SITEMAP_DIR = <data>/sitemap")
        else:
            print(f"{репо.name}: ни функции дополнений в лаунчере, ни раздела "
                  "environment в пакете — подключать нечем", file=sys.stderr)
            return 3

    общий = (ШАБЛОН / "seo_layer.py").read_bytes()
    цель = репо / "src" / "seo_layer.py"
    # Модуля может не быть вовсе — тогда он доставляется, а не считается
    # препятствием: сборщик карты живёт именно в нём, и файл у семейства один.
    прежний = цель.read_bytes() if цель.is_file() else b""
    if прежний != общий:
        сделано.append("seo_layer.py: общий модуль семейства из шаблона"
                       + ("" if прежний else " (прежде отсутствовал)"))

    print(f"{репо.name}: разделы {' '.join(args.sections)}")
    for строка in сделано:
        print("   ", строка)
    if args.dry_run:
        print("сухой прогон: файлы не менялись")
        return 0
    витрина.write_text(т, encoding="utf-8")
    if правка_лаунчера is not None:
        лаунчер.write_text(правка_лаунчера, encoding="utf-8")
    if правка_пакета:
        import json as _json

        путь_пакета = репо / "config" / "site.json"
        данные = _json.loads(путь_пакета.read_text(encoding="utf-8"))
        данные.setdefault("environment", {})["LORDS_SITEMAP_DIR"] = "<data>/sitemap"
        путь_пакета.write_text(
            _json.dumps(данные, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8")
    цель.write_bytes(общий)
    print("дальше обязателен прогон checks/run.sh в этом репозитории")
    return 0


if __name__ == "__main__":
    raise SystemExit(главная())
