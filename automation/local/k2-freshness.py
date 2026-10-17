#!/usr/bin/env python3
"""Свежесть каталога восьми витрин K2: четыре различимых состояния.

Успешный ответ сайта ничего не говорит о свежести данных: витрина с каталогом
двухдневной давности отвечает 200 так же бодро, как со вчерашним. Поэтому
сравниваются три факта, а не доступность:

  снимок поставщика   время файла и число записей на управляющем узле;
  последний комплект  отчёт издателя: когда собран и из какого снимка;
  установленный       ревизия и время установки НА ВИТРИНАХ (через опись узла).

Состояния различаются явно, потому что действия у них разные:

  СВЕЖО            установленная ревизия совпадает с последним собранным
                   комплектом, и комплект не отстал от снимка поставщика;
  УСТАРЕЛО         снимок поставщика ушёл вперёд, а доставки не было;
  ОШИБКА ДОСТАВКИ  комплект собран и/или доставлен, но на витрине не стоит:
                   остался рабочий каталог доставки либо на узле висит
                   непринятый входящий комплект;
  НЕТ ДАННЫХ       чего-то из трёх фактов нет — снимка, отчётов или связи с
                   узлом. Это НЕ «свежо» и не «устарело».

    python3 automation/local/k2-freshness.py
    python3 automation/local/k2-freshness.py --root /srv/site-factory/k2-delivery
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import re
import subprocess
import sys
from pathlib import Path

ЗДЕСЬ = Path(__file__).resolve().parents[2]
СНИМОК = Path("/srv/site-factory/repo/var/lords/lords/catalog-cache/"
              "lords-01.json")
ХОСТ = "k2-zomro-01"
ПРЕДЕЛ_ОТСТАВАНИЯ_Ч = 30


def теперь() -> dt.datetime:
    return dt.datetime.now(dt.timezone.utc)


def разобрать_время(текст: str | None) -> dt.datetime | None:
    if not текст:
        return None
    try:
        return dt.datetime.strptime(текст, "%Y-%m-%dT%H:%M:%SZ").replace(
            tzinfo=dt.timezone.utc)
    except ValueError:
        try:
            return dt.datetime.strptime(текст, "%Y-%m-%dT%H:%MZ").replace(
                tzinfo=dt.timezone.utc)
        except ValueError:
            return None


def последний_отчёт(каталог: Path) -> dict:
    лучший: dict = {}
    когда_лучший = None
    for файл in sorted(каталог.glob("pub-*.json")) if каталог.is_dir() else []:
        try:
            данные = json.loads(файл.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        когда = разобрать_время(данные.get("started_at"))
        if когда and (когда_лучший is None or когда > когда_лучший):
            когда_лучший, лучший = когда, данные
    return лучший


def состояние_узла(инвентарь: Path, корень: Path) -> dict:
    """site_id → {revision, items, installed_at, incoming_pending}."""
    if not инвентарь.is_file():
        return {}
    п = subprocess.run(
        ["ansible", "-i", str(инвентарь), ХОСТ, "-m", "shell",
         "-a", "python3 /home/k2deploy/stage/k2-catalog-state.py"],
        capture_output=True, text=True, cwd=str(корень))
    итог = {}
    for строка in (п.stdout or "").splitlines():
        м = re.match(r"(lords-\d+) revision=(\S+) items=(\d+) "
                     r"installed_at=(\S+) details_mib=(\d+) "
                     r"incoming_pending=(\S+)", строка.strip())
        if м:
            итог[м.group(1)] = {
                "revision": м.group(2), "items": int(м.group(3)),
                "installed_at": м.group(4),
                "incoming": м.group(6) == "да",
            }
    return итог


def главная(аргв: list[str] | None = None) -> int:
    р = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    р.add_argument("--root", default=str(ЗДЕСЬ),
                   help="рабочий каталог доставки (отчёты и инвентарь)")
    а = р.parse_args(аргв)
    корень = Path(а.root)
    отчёты = корень / "var" / "k2-data" / "publish-reports"
    рабочий = корень / "var" / "k2-data" / "deliver"
    инвентарь = корень / "var" / "ansible" / "hosts.yml"

    неизвестно: list[str] = []
    снят = None
    if СНИМОК.is_file():
        снят = dt.datetime.fromtimestamp(СНИМОК.stat().st_mtime,
                                         dt.timezone.utc)
        print(f"снимок поставщика: {снят:%Y-%m-%d %H:%M}Z "
              f"({(теперь() - снят).total_seconds() / 3600:.1f} ч назад)")
    else:
        неизвестно.append(f"снимка поставщика нет ({СНИМОК})")

    отчёт = последний_отчёт(отчёты)
    собран = разобрать_время(отчёт.get("started_at"))
    ожидаемая = ((отчёт.get("snapshot") or {}).get("id_set_checksum") or "")[:32]
    if отчёт:
        print(f"последний комплект: {отчёт.get('run_id')} от "
              f"{отчёт.get('started_at')}, ожидаемая ревизия "
              f"{ожидаемая or '—'}")
    else:
        неизвестно.append(f"отчётов издателя нет ({отчёты})")

    узел = состояние_узла(инвентарь, корень)
    if not узел:
        неизвестно.append("состояние витрин не получено (инвентарь или связь)")

    оборвана = рабочий.is_dir()
    if оборвана:
        когда = dt.datetime.fromtimestamp(рабочий.stat().st_mtime,
                                          dt.timezone.utc)
        print(f"рабочий каталог доставки остался с {когда:%Y-%m-%d %H:%M}Z — "
              f"прогон не завершился")

    if неизвестно:
        print("\nНЕТ ДАННЫХ для вывода о свежести:")
        for п in неизвестно:
            print(f"  • {п}")
        return 2

    отстал = (снят - собран).total_seconds() / 3600.0 if собран else 0.0
    # «Только что доставлено» считается от последнего прогона издателя:
    # доставка идёт сразу за ним и длится минуты.
    свежая_доставка = bool(собран) and \
        (теперь() - собран).total_seconds() < 40 * 60
    print(f"\n{'витрина':10} {'ревизия':34} {'установлено':18} состояние")
    плохо = 0
    for site_id in sorted(узел):
        з = узел[site_id]
        совпала = ожидаемая and з["revision"].startswith(ожидаемая[:32])
        if з["incoming"] and свежая_доставка:
            # Приёмщик узла срабатывает каждые 15 минут: сразу после доставки
            # непринятый комплект — это норма, а не отказ. Ошибкой он
            # становится, когда переживает два цикла приёмщика.
            состояние = "ДОСТАВЛЕНО, ЖДЁТ УСТАНОВКИ (приёмщик каждые 15 мин)"
        elif з["incoming"]:
            состояние = ("ОШИБКА ДОСТАВКИ: комплект лежит непринятым дольше "
                         "двух циклов приёмщика")
        elif оборвана:
            состояние = "ОШИБКА ДОСТАВКИ: прогон оборвался"
        elif not совпала:
            состояние = "УСТАРЕЛО: стоит не последний собранный комплект"
        elif отстал > ПРЕДЕЛ_ОТСТАВАНИЯ_Ч:
            состояние = (f"УСТАРЕЛО: комплект отстал от поставщика на "
                         f"{отстал:.0f} ч")
        else:
            состояние = "СВЕЖО"
        плохо += not (состояние.startswith("СВЕЖО")
                      or состояние.startswith("ДОСТАВЛЕНО"))
        print(f"{site_id:10} {з['revision'][:32]:34} {з['installed_at']:18} "
              f"{состояние}")
    print(f"\nвитрин не в порядке: {плохо} из {len(узел)} "
          f"(«свежо» и «ждёт установки» считаются порядком)")
    return 1 if плохо else 0


if __name__ == "__main__":
    sys.exit(главная())
