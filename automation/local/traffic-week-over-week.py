#!/usr/bin/env python3
"""Неделя к неделе по снимкам Метрики: визиты, люди, поиск, разрыв до цели.

Зачем по снимкам, а не по API. Токен Метрики читает служба, а не сессия
(`BLOCKED_SECRET`), зато сборщик кладёт суточные снимки в
`artifacts/analytics/analytics-YYYY-MM-DD.json`, и окно каждого снимка —
`7daysAgo…yesterday`. Значит два снимка с разницей в семь дней дают ровно то
сравнение, которое нужно: последние семь полных суток против предыдущих семи,
без доступа к API и без потока повторных запросов.

Что инструмент НЕ смешивает:

  посетители  `ym:s:users` за период — это НЕ сумма по дням и не визиты;
  визиты      `ym:s:visits`;
  поиск       визиты с источником «переход из поисковой системы», отдельно по
              системам; пустой список значит ноль ПОИСКОВЫХ визитов, а не
              отсутствие данных;
  роботы      разрез `ym:s:isRobot` по дням: «люди» и «роботы» считаются
              отдельно, потому что у этой сети роботов больше, чем людей.

Отсутствие счётчика и ошибка сбора печатаются как «не измерено» и в ноль не
превращаются.

    python3 automation/local/traffic-week-over-week.py
    python3 automation/local/traffic-week-over-week.py --now 2026-10-17 --prev 2026-10-10
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ЦЕЛЬ_В_СУТКИ = 5000
СНИМКИ = [
    Path("/home/claude/wt-portable-site-cell-01/artifacts/analytics"),
    Path(__file__).resolve().parents[2] / "artifacts" / "analytics",
]


def найти_снимок(дата: str) -> Path | None:
    for каталог in СНИМКИ:
        п = каталог / f"analytics-{дата}.json"
        if п.is_file():
            return п
    return None


def измерение(домен: dict, ключ: str):
    """Значение измерения или None, если оно не снято."""
    for м in домен.get("measurements") or []:
        if м.get("key") == ключ:
            return м.get("value") if м.get("measured") else None
    return None


def поисковые_визиты(домен: dict) -> tuple[dict, bool]:
    """{система: визиты} и признак «измерение было».

    Пустой список — это измеренный ноль поисковых визитов. Отсутствие
    измерения — другое дело, и оно возвращается отдельным признаком.
    """
    значение = измерение(домен, "search_engines")
    if значение is None:
        return {}, False
    итог: dict[str, float] = {}
    for строка in значение or []:
        имена = [(д.get("name") or "?") for д in (строка.get("dimensions") or [])]
        метрики = строка.get("metrics") or [0.0]
        итог[imena_первое(имена)] = итог.get(imena_первое(имена), 0.0) + метрики[0]
    return итог, True


def imena_первое(имена: list[str]) -> str:
    return имена[0] if имена else "?"


def люди_и_роботы(домен: dict) -> tuple[float, float, int]:
    """(визиты людей, визиты роботов, сколько РАЗНЫХ дат в разрезе).

    Делить на семь нельзя: разрез `ym:s:users × ym:s:date × ym:s:isRobot`
    приходит не ровно за окно снимка — в одном и том же снимке встречались
    даты с 03.10 по 15.10. Поэтому среднесуточное считается по фактическому
    числу дат, а само число дат печатается рядом: иначе «в сутки» было бы
    величиной с неизвестным знаменателем.
    """
    значение = измерение(домен, "daily_users")
    if значение is None:
        return 0.0, 0.0, 0
    по_дате: dict[str, list[float]] = {}
    for строка in значение or []:
        изм = строка.get("dimensions") or []
        дата = (изм[0].get("name") if изм else "") or ""
        if not дата:
            continue
        робот = any((д.get("id") == "yes") for д in изм)
        визиты = (строка.get("metrics") or [0.0, 0.0])
        число = визиты[1] if len(визиты) > 1 else визиты[0]
        пара = по_дате.setdefault(дата, [0.0, 0.0])
        пара[1 if робот else 0] += число
    if not по_дате:
        return 0.0, 0.0, 0
    # Берутся ПОСЛЕДНИЕ семь дат разреза: в снимке их бывает больше (встречались
    # 12–14), и среднее по всему разрезу размазало бы свежую неделю по старой.
    последние = sorted(по_дате)[-7:]
    люди = sum(по_дате[д][0] for д in последние)
    роботы = sum(по_дате[д][1] for д in последние)
    return люди, роботы, len(последние)


def посадочные(домен: dict) -> dict[str, float]:
    значение = измерение(домен, "landing_pages") or []
    итог = {}
    for строка in значение:
        имя = ((строка.get("dimensions") or [{}])[0]).get("name") or "?"
        итог[имя] = (строка.get("metrics") or [0.0])[0]
    return итог


def главная(аргв: list[str] | None = None) -> int:
    р = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    р.add_argument("--now", default="2026-10-17")
    р.add_argument("--prev", default="2026-10-10")
    р.add_argument("--out", default=str(Path(__file__).resolve().parents[2] /
                                        "var" / "seo" / "traffic-wow.json"))
    а = р.parse_args(аргв)

    п_сейчас, п_раньше = найти_снимок(а.now), найти_снимок(а.prev)
    if not п_сейчас:
        print(f"НЕТ ДАННЫХ: снимка {а.now} нет", file=sys.stderr)
        return 2
    сейчас = json.loads(п_сейчас.read_text(encoding="utf-8"))
    раньше = json.loads(п_раньше.read_text(encoding="utf-8")) if п_раньше else {}
    было = {д["domain"]: д for д in (раньше.get("domains") or [])}

    # Домен, у которого Метрика ответила 429, в текущем снимке «не измерен».
    # Это НЕ ноль трафика. Берём ближайший более ранний снимок, где он измерен,
    # и помечаем строку — лишних запросов к API при этом не делается.
    запас: dict[str, tuple[dict, str]] = {}
    прежние_снимки = []
    for каталог in СНИМКИ:
        прежние_снимки += sorted(каталог.glob("analytics-????-??-??.json"))
    прежние_снимки = sorted(прежние_снимки, key=lambda p: p.name, reverse=True)
    for д in сейчас.get("domains") or []:
        if измерение(д, "visits") is not None:
            continue
        for файл in прежние_снимки:
            if файл.name >= f"analytics-{а.now}.json":
                continue
            try:
                старый = json.loads(файл.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                continue
            для_домена = next((x for x in (старый.get("domains") or [])
                               if x["domain"] == д["domain"]), None)
            if для_домена and измерение(для_домена, "visits") is not None:
                запас[д["domain"]] = (для_домена, файл.name[10:20])
                break

    print(f"окно «сейчас»: снимок {а.now} (собран {сейчас.get('collected_at')}), "
          f"период {сейчас.get('period')}")
    if п_раньше:
        print(f"окно «раньше»: снимок {а.prev} (собран {раньше.get('collected_at')})")
    else:
        print("окно «раньше»: снимка нет — сравнение не делается")
    print("часовой пояс счётчиков — Europe/Moscow (паспорт счётчика)\n")

    строки = []
    print(f"{'домен':22} {'визиты7':>8} {'было':>6} {'Δ':>7} {'люди/сут':>9} "
          f"{'роботы/сут':>10} {'дат':>4} {'поиск':>6} до 5000/сут")
    for д in sorted(сейчас.get("domains") or [], key=lambda x: x["domain"]):
        домен = д["domain"]
        помета = ""
        if измерение(д, "visits") is None and домен in запас:
            д, дата_запаса = запас[домен]
            помета = f" (из снимка {дата_запаса}: в текущем Метрика ответила 429)"
        визиты = измерение(д, "visits")
        посетители = измерение(д, "visitors")
        люди, роботы, дат = люди_и_роботы(д)
        есть_разрез = дат > 0
        поиск, поиск_измерен = поисковые_визиты(д)
        прежние = было.get(домен)
        визиты_было = измерение(прежние, "visits") if прежние else None
        дельта = (визиты - визиты_было) if (визиты is not None
                                            and визиты_было is not None) else None
        в_сутки = (люди / дат) if есть_разрез else None
        разрыв = (ЦЕЛЬ_В_СУТКИ - в_сутки) if в_сутки is not None else None
        строки.append({
            "домен": домен, "визиты_7дн": визиты, "посетители_7дн": посетители,
            "визиты_7дн_прежние": визиты_было, "дельта_визитов": дельта,
            "люди_визитов_в_сутки": в_сутки, "роботы_визитов_в_сутки":
                (роботы / дат) if есть_разрез else None,
            "дат_в_разрезе": дат,
            "поиск_визитов": поиск, "поиск_измерен": поиск_измерен,
            "до_цели_в_сутки": разрыв,
            "посадочные": посадочные(д),
            "запасной_снимок": помета.strip() or None,
        })
        print(f"{домен:22} "
              f"{('—' if визиты is None else f'{визиты:.0f}'):>8} "
              f"{('—' if визиты_было is None else f'{визиты_было:.0f}'):>6} "
              f"{('—' if дельта is None else f'{дельта:+.0f}'):>7} "
              f"{('—' if в_сутки is None else f'{в_сутки:.1f}'):>9} "
              f"{('—' if not есть_разрез else f'{роботы / дат:.1f}'):>10} "
              f"{дат if дат else '—':>4} "
              f"{(sum(поиск.values()) if поиск_измерен else '—'):>6} "
              f"{('—' if разрыв is None else f'{разрыв:.0f}')}{помета}")

    с_поиском = [с for с in строки if с["поиск_измерен"] and с["поиск_визитов"]]
    print(f"\nдоменов с поисковыми визитами за неделю: {len(с_поиском)} из "
          f"{len(строки)}")
    for с in с_поиском:
        подробно = ", ".join(f"{к}: {v:.0f}" for к, v in с["поиск_визитов"].items())
        print(f"   {с['домен']}: {подробно}")

    п_вых = Path(а.out)
    п_вых.parent.mkdir(parents=True, exist_ok=True)
    п_вых.write_text(json.dumps(
        {"снимок_сейчас": а.now, "снимок_раньше": а.prev, "строки": строки},
        ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(f"\nсохранено: {п_вых}")
    return 0


if __name__ == "__main__":
    sys.exit(главная())
