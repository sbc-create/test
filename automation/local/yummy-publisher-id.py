#!/usr/bin/env python3
"""Publisher ID витрины Yummy: закрепление за доменом и сверка с учётом.

Почему отдельный инструмент, а не `assign-publisher-id.py`
----------------------------------------------------------

D177 называет три места и годится для витрин, которые играют сами: значение у
производителя, объявление `publisher_id_expected` в пакете и учёт в реестре.
У семейства Yummy своего плеера нет. Страницу отдаёт верхний поток Next.js, а
ячейка только проксирует к нему (`LORDS_LEGACY_UPSTREAM`), поэтому
`LORDS_PLAYER_CONFIG` в её окружении отсутствует НАМЕРЕННО. Как только ячейка
объявляет `publisher_id_expected`, её собственная пусковая проверка отказывает
словами «LORDS_PLAYER_CONFIG не задан», и витрина не поднимается вовсе —
измерено 2026-10-14 на yummyani7.site, записано ещё 12.10 (пункт B010).

Где номер живёт на самом деле
-----------------------------

Приложение читает `CDNVIDEOHUB_PUBLISHER_ID`
(`src/modules/playback/cdn-video-hub/publisher-id.ts`), а кладёт его туда точка
входа образа — и предпочитает ЗАКРЕПЛЁННОЕ значение общему файлу направления:

    if [ -n "${CDNVIDEOHUB_PUBLISHER_ID_PINNED:-}" ]; then
      export CDNVIDEOHUB_PUBLISHER_ID="$CDNVIDEOHUB_PUBLISHER_ID_PINNED"
    else
      read_secret_file CDNVIDEOHUB_PUBLISHER_ID publisher-id
    fi

Общий файл `/run/cdnvideohub/publisher-id` один на все витрины семейства,
поэтому без закрепления разных номеров у доменов быть не может. Тем же
способом закреплены соседи: yummyani.org — 10377, yummyani.biz — 10375
(решение владельца 2026-10-01).

Что делает этот инструмент
--------------------------

Сверяет три вещи и приводит витрину к ним:

1. **учёт** — `config/site-cells.json: publisher.publisher_id` (источник);
2. **закрепление** — `deploy/compose.yaml: CDNVIDEOHUB_PUBLISHER_ID_PINNED`;
3. **живое** — что отдаёт работающий контейнер.

Номер инструмент НЕ принимает аргументом: его назначает владелец, а инструмент
следит, чтобы контур и витрина не разошлись с учётом. При расхождении учёта и
закрепления — отказ с названной разницей, а не тихая правка: какое из двух
значений верно, решает не инструмент.

    python3 automation/local/yummy-publisher-id.py --site yummy-07
    python3 automation/local/yummy-publisher-id.py --site yummy-07 --apply
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

КОРЕНЬ = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(КОРЕНЬ))

from factory.cell import registry  # noqa: E402

ПЕРЕМЕННАЯ = "CDNVIDEOHUB_PUBLISHER_ID_PINNED"
#: Общий файл направления. Инструмент его не читает и не меняет — ни разу.
ОБЩИЙ = Path("/srv/sites/yummyani-staging/runtime/cdnvideohub/publisher-id")


class Отказ(RuntimeError):
    """Операция не выполнена, и причина названа."""


def закрепление(compose: Path) -> str:
    """Что закреплено в контуре. Разбор построчный: файл читают и люди."""
    образец = re.compile(rf'^\s*{ПЕРЕМЕННАЯ}:\s*"?(\d+)"?\s*$')
    for строка in compose.read_text(encoding="utf-8").splitlines():
        м = образец.match(строка)
        if м:
            return м.group(1)
    return ""


def метки_контура(контейнер: str) -> dict[str, str]:
    """Имя проекта и файл переменных — у самого работающего контейнера.

    Ни то, ни другое не выводится из путей. Имя проекта, выведенное из имени
    каталога (`deploy`), однажды подняло ПАРАЛЛЕЛЬНЫЙ контур со своими базой и
    кешем, а веб упал на занятом порте: измерено 2026-10-14 на yummyani7.site,
    побочные контейнеры и тома пришлось убирать руками.
    """
    формат = ('{{index .Config.Labels "com.docker.compose.project"}}|'
              '{{index .Config.Labels "com.docker.compose.project.environment_file"}}')
    г = subprocess.run(["docker", "inspect", контейнер, "--format", формат],
                       capture_output=True, text=True, timeout=120)
    if г.returncode != 0:
        return {}
    части = (г.stdout or "").strip().split("|")
    if len(части) != 2 or not части[0]:
        return {}
    return {"проект": части[0],
            "переменные": "" if части[1] in ("", "<no value>") else части[1]}


def дождаться(порт: int, домен: str, предел: float = 120.0) -> bool:
    """Витрина отвечает? Без этого первый же запрос приходит в поднимающийся web."""
    конец = time.monotonic() + предел
    while time.monotonic() < конец:
        try:
            зпр = urllib.request.Request(f"http://127.0.0.1:{порт}/api/health",
                                         headers={"Host": домен})
            if urllib.request.urlopen(зпр, timeout=10).status == 200:
                return True
        except (urllib.error.URLError, OSError):
            pass
        time.sleep(3)
    return False


def живое_значение(порт: int, домен: str) -> dict:
    """Что отдаёт работающая витрина: атрибут `data-publisher-id` в разметке.

    Страница произведения берётся со своей же главной: жёстко вписанный слуг
    устарел бы вместе с каталогом и выглядел бы отказом витрины.
    """
    def достать(адрес: str) -> str:
        зпр = urllib.request.Request(адрес, headers={"Host": домен})
        return urllib.request.urlopen(зпр, timeout=40).read().decode("utf-8", "replace")

    основа = f"http://127.0.0.1:{порт}"
    try:
        главная = достать(основа + "/")
        ссылки = sorted(set(re.findall(r'href="(/anime/[^"]+)"', главная)))
        if not ссылки:
            return {"проверено": False,
                    "причина": "на главной нет ссылок на произведения"}
        путь = ссылки[0]
        html = достать(основа + путь)
    except (urllib.error.URLError, OSError) as ош:
        return {"проверено": False, "причина": f"{type(ош).__name__}: {ош}"}
    return {"проверено": True, "страница": путь,
            "в разметке": sorted(set(re.findall(r'data-publisher-id="([^"]*)"', html)))}


def поднять(compose: Path, *, apply: bool, контейнер: str) -> dict:
    """Пересоздать веб-контейнер витрины. Остальные службы не трогаются."""
    метки = метки_контура(контейнер)
    if not метки:
        return {"выполнено": False, "код": 70,
                "хвост": f"контейнер {контейнер} не найден: пересоздавать нечего, "
                         "а поднимать новый контур — не дело этого инструмента"}
    команда = ["docker", "compose", "-p", метки["проект"], "-f", str(compose)]
    if метки["переменные"] and Path(метки["переменные"]).is_file():
        команда += ["--env-file", метки["переменные"]]
    команда += ["up", "-d", "web"]
    отчёт = {"команда": " ".join(команда), "проект": метки["проект"],
             "файл переменных": метки["переменные"]}
    if not apply:
        отчёт["выполнено"] = False
        return отчёт
    г = subprocess.run(команда, capture_output=True, text=True, timeout=900,
                       cwd=str(compose.parent))
    отчёт.update({"выполнено": True, "код": г.returncode,
                  "хвост": (г.stderr or г.stdout or "").strip()[-300:]})
    return отчёт


def верхний_порт(репо: Path) -> int:
    """Порт верхнего потока берётся из пакета витрины, а не угадывается."""
    конфиг = репо / "config" / "site.json"
    if not конфиг.is_file():
        return 0
    окружение = json.loads(конфиг.read_text(encoding="utf-8")).get("environment") or {}
    верх = str(окружение.get("LORDS_LEGACY_UPSTREAM") or "")
    хвост = верх.rsplit(":", 1)[-1]
    return int(хвост) if хвост.isdigit() else 0


def главное(site_id: str, *, apply: bool) -> dict:
    try:
        ячейка = registry.resolve(site_id)
    except registry.RegistryError as ош:
        raise Отказ(str(ош)) from None
    учёт = str((ячейка.publisher or {}).get("publisher_id") or "").strip()
    if not учёт:
        raise Отказ(
            f"{site_id}: в учёте реестра нет publisher_id. Это BLOCKED_INPUT, а не "
            "повод подставить общее значение направления: номер назначает владелец")

    путь_репо = str((ячейка.repo or {}).get("path") or "").strip()
    if not путь_репо:
        raise Отказ(f"{site_id}: в реестре не записан путь репозитория")
    п = Path(путь_репо)
    репо = п if п.is_absolute() else КОРЕНЬ / п
    compose = репо / "deploy" / "compose.yaml"
    if not compose.is_file():
        raise Отказ(f"{site_id}: нет {compose}: контур витрины не описан")

    закреплено = закрепление(compose)
    отчёт = {
        "site_id": ячейка.site_id,
        "domain": ячейка.domain,
        "закрепление есть": bool(закреплено),
        "учёт и закрепление согласны": закреплено == учёт,
        "общий файл направления": str(ОБЩИЙ),
        "общий файл не читается и не меняется": True,
        "контур": str(compose),
    }
    if not закреплено:
        отчёт["итог"] = (
            f"ОТКАЗ: в {compose} нет {ПЕРЕМЕННАЯ}; без закрепления витрина возьмёт "
            "общее значение направления, одно на все домены семейства")
        return отчёт
    if закреплено != учёт:
        отчёт["итог"] = (
            "ОТКАЗ: учёт реестра и закрепление контура расходятся. Какое из двух "
            "верно — решает владелец, а не этот инструмент; значения не печатаются")
        return отчёт

    отчёт["перезапуск"] = поднять(compose, apply=apply, контейнер=f"{репо.name}-web-1")
    код = отчёт["перезапуск"].get("код")
    if apply and код not in (0, None):
        # Первая редакция писала «контур поднят» при ненулевом коде: отчёт
        # утверждал бы то, чего не было. Измерено на yummy-07.
        отчёт["итог"] = f"ОТКАЗ: пересоздание web вернуло код {код}"
        return отчёт

    порт = верхний_порт(репо)
    if apply and порт:
        отчёт["дождались готовности"] = дождаться(порт, ячейка.domain)
        if not отчёт["дождались готовности"]:
            отчёт["итог"] = ("ОТКАЗ: витрина не ответила на /api/health за 120 с — "
                             "проверять значение не на чем")
            return отчёт
        отчёт["живое"] = живое_значение(порт, ячейка.domain)
        отчёт["живое согласно с учётом"] = (
            (отчёт["живое"].get("в разметке") or []) == [учёт])
        if not отчёт["живое согласно с учётом"]:
            отчёт["итог"] = ("ОТКАЗ: витрина отдаёт не закреплённое значение "
                             "(значения не печатаются)")
            return отчёт
    отчёт["итог"] = ("закрепление применено и подтверждено живой страницей" if apply
                     else "сухой прогон: закрепление согласовано, web будет пересоздан")
    return отчёт


def main() -> int:
    р = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    р.add_argument("--site", required=True, help="site_id ячейки Yummy")
    р.add_argument("--apply", action="store_true",
                   help="пересоздать контур и проверить живьём")
    а = р.parse_args()
    try:
        отчёт = главное(а.site, apply=а.apply)
    except Отказ as ош:
        print(str(ош), file=sys.stderr)
        return 2
    print(json.dumps(отчёт, ensure_ascii=False, indent=2))
    return 0 if str(отчёт.get("итог", "")).startswith(("закрепление", "сухой")) else 3


if __name__ == "__main__":
    raise SystemExit(main())
