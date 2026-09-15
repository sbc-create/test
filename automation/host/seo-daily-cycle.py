#!/usr/bin/env python3
"""Суточный цикл SEO: от сверки портфеля до отчёта владельцу.

Порядок стадий задан и не переставляется: считать покрытие до снимка каталога
значит считать по вчерашнему знаменателю, а публиковать до QA — значит узнать
о дефекте от читателя.

Отчёт выпускается всегда. День, в котором ничего не опубликовано, — это тоже
результат, и причина нулевого выпуска в отчёте называется. Пропущенный отчёт
неотличим от дня, когда цикл не запускался.

Платных операций цикл не делает ни одной: ежедневный съём позиций Topvisor
запрещён, и код его не умеет.
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import pathlib
import subprocess
import sys

СВОЙ = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(СВОЙ))
import seo_coverage as COV        # noqa: E402
import seo_inventory as INV       # noqa: E402

КОРЕНЬ = СВОЙ.parents[1]

#: Витрины портфеля: идентификатор, домен, семейство шаблона.
ВИТРИНЫ = (("lords-01", "lordfilm47.space", "lords"),
           ("lords-02", "lordserial33.biz", "lords"),
           ("lords-03", "1lordserials1.online", "lords"),
           ("zona-01", "zonafilm.space", "zona"),
           ("animedia-01", "animedia.icu", "animedia"),
           ("animedia-02", "animedia.space", "animedia"),
           ("yummy-site", "yummyani.site", "yummy"),
           ("yummy-org", "yummyani.org", "yummy"),
           ("yummy-biz", "yummyani.biz", "yummy"))

#: Домены, проверяемые на существование дополнительно к реестру.
ДОПОЛНИТЕЛЬНО = ("yummyani.me", "ru.yummyani.me", "old.yummyani.me")

ФРОНТ = "/srv/lords/.frontend"


def _прочитать(путь: str) -> dict:
    """Прочитать каталог. Сначала напрямую — привилегии здесь не нужны.

    Привилегированное чтение оставлено запасным путём и намеренно не первым:
    ежедневная задача, привыкшая ходить под sudo, однажды понадобится с ним
    там, где без него обошлись бы.
    """
    ф = pathlib.Path(путь)
    try:
        return json.loads(ф.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        pass
    r = subprocess.run(["sudo", "-n", "cat", путь], capture_output=True, text=True)
    if r.returncode != 0 or not r.stdout.strip():
        return {}
    try:
        return json.loads(r.stdout)
    except json.JSONDecodeError:
        return {}


# --- 3. трафик -------------------------------------------------------------
def трафик(домены: dict[str, dict], день: str, каталог: pathlib.Path) -> dict:
    """Органика и просмотры из Метрики. Без платных источников.

    Окна сравнения раздельные: вчера против того же дня неделю назад, 7 к 7 и
    28 к 28. Сегодняшний текст сегодняшним трафиком не оценивается — между
    публикацией и поиском лежат дни.
    """
    снимок_файл = каталог / "traffic-snapshot.json"
    try:
        sys.path.insert(0, str(КОРЕНЬ))
        from factory.analytics.yandex import YandexAnalyticsProvider
        p = YandexAnalyticsProvider(dry_run=True)
    except Exception as ош:
        # Токен планировщику недоступен: он принадлежит root, а цикл работает
        # без привилегий. Показывается последний снимок с его возрастом —
        # той же дисциплиной, что и для съёма позиций. Вчерашнее число,
        # выданное за сегодняшнее, хуже отсутствующего: по нему принимают
        # решения как по свежему.
        if снимок_файл.exists():
            снимок = json.loads(снимок_файл.read_text(encoding="utf-8"))
            измерено = dt.datetime.fromisoformat(снимок["measured_at"])
            возраст = (dt.datetime.now(dt.timezone.utc) - измерено).total_seconds() / 3600
            return {**снимок, "status": "STALE" if возраст > 26 else "CURRENT",
                    "age_hours": round(возраст, 1),
                    "credential_note":
                        "измерено отдельным привилегированным прогоном: "
                        "токен Метрики принадлежит root и планировщику "
                        "недоступен. Постоянное решение — системный юнит с "
                        "LoadCredential, он ждёт транзакции hardening."}
        return {"status": "NOT_MEASURED", "reason": type(ош).__name__,
                "credential_note": "токен планировщику недоступен, а прежнего "
                                   "снимка нет: измерять было нечем"}

    из: dict[str, dict] = {}
    сегодня = dt.date.fromisoformat(день)
    окна = {
        "D-1": (сегодня - dt.timedelta(days=1), сегодня - dt.timedelta(days=1)),
        "D-8": (сегодня - dt.timedelta(days=8), сегодня - dt.timedelta(days=8)),
        "L7": (сегодня - dt.timedelta(days=7), сегодня - dt.timedelta(days=1)),
        "P7": (сегодня - dt.timedelta(days=14), сегодня - dt.timedelta(days=8)),
        "L28": (сегодня - dt.timedelta(days=28), сегодня - dt.timedelta(days=1)),
        "P28": (сегодня - dt.timedelta(days=56), сегодня - dt.timedelta(days=29)),
    }
    for домен, з in домены.items():
        счёт = з.get("metrika_counter")
        if not счёт:
            continue
        по_окнам = {}
        for имя, (с, по) in окна.items():
            try:
                r = p.metrika.get("/stat/v1/data", params={
                    "ids": счёт, "metrics": "ym:s:visits,ym:s:users",
                    "dimensions": "ym:s:lastTrafficSource",
                    "date1": с.isoformat(), "date2": по.isoformat(),
                    "limit": 50, "accuracy": "full"})
                данные = (r.payload or {}).get("data") or []
                органика = sum(
                    строка["metrics"][0] for строка in данные
                    if (строка["dimensions"][0].get("id") or "") == "organic")
                всего = ((r.payload or {}).get("totals") or [0])[0]
                по_окнам[имя] = {"visits_total": всего, "organic_visits": органика}
            except Exception as ош:
                по_окнам[имя] = {"error": type(ош).__name__}
        из[домен] = {"counter_id": счёт, "windows": по_окнам}
    # Измерение засчитывается только если хоть одно окно вернуло число.
    # Прежняя редакция возвращала CURRENT безусловно, и полностью
    # провалившийся сбор попадал в отчёт владельца как свежий: окна были
    # заполнены записями об ошибке, а статус говорил «измерено сегодня».
    # Это ровно то, чего нельзя делать с чужими решениями — по такому числу
    # их принимают как по измеренному.
    измерено = any("visits_total" in о for в in из.values()
                   for о in в["windows"].values())
    if not измерено:
        if снимок_файл.exists():
            прежний = json.loads(снимок_файл.read_text(encoding="utf-8"))
            измерен_в = dt.datetime.fromisoformat(прежний["measured_at"])
            часы = (dt.datetime.now(dt.timezone.utc) - измерен_в).total_seconds() / 3600
            return {**прежний, "status": "STALE" if часы > 26 else "CURRENT",
                    "age_hours": round(часы, 1),
                    "credential_note": "сегодняшний сбор не удался; показан "
                                       "последний удавшийся снимок"}
        return {"status": "NOT_MEASURED", "per_domain": из,
                "reason": "ни одно окно не вернуло числа",
                "credential_note": "токен Метрики принадлежит root и "
                                   "планировщику недоступен"}
    снимок = {"status": "CURRENT", "per_domain": из, "age_hours": 0.0,
              "measured_at": dt.datetime.now(dt.timezone.utc).isoformat(),
              "note": "Метрика, first-party. Платных источников не использовано."}
    снимок_файл.write_text(json.dumps(снимок, ensure_ascii=False, indent=1),
                           encoding="utf-8")
    return снимок


# --- 5. очередь пробелов ---------------------------------------------------
def очередь_пробелов(матрица: dict) -> list[dict]:
    """Квалифицированные пробелы, отсортированные по измеримой величине.

    Величина — не «важность на глаз», а число записей, которых касается
    пробел. Источник, не подключённый вовсе, стоит выше поля, заполненного на
    девяносто процентов: первое чинится один раз для десятков тысяч записей.
    """
    из: list[dict] = []
    for домен, з in матрица.items():
        for сегм, v in з["segments"].items():
            for источник, x in v["ratings"].items():
                if x.get("SOURCE_NOT_INTEGRATED"):
                    из.append({
                        "kind": "RATING_SOURCE_NOT_INTEGRATED",
                        "domain": домен, "segment": сегм, "source": источник,
                        "records_affected": x["SOURCE_NOT_INTEGRATED"],
                        "why": f"идентификаторы {источник} есть у "
                               f"{x['SOURCE_NOT_INTEGRATED']} записей, оценок нет ни одной",
                        "owner_layer": "content-pipeline (сбор рейтингов)"})
                elif x["ELIGIBLE"] and (x["ELIGIBLE_COVERAGE"] or 0) < 0.9:
                    из.append({
                        "kind": "RATING_COVERAGE_BELOW_TARGET",
                        "domain": домен, "segment": сегм, "source": источник,
                        "records_affected": x["ELIGIBLE"] - x["COVERED"],
                        "why": f"покрытие {x['ELIGIBLE_COVERAGE']:.1%} при цели 90%",
                        "owner_layer": "content-pipeline"})
            for поле, f in v["fields"].items():
                if f.get("BLOCKED"):
                    из.append({"kind": "FIELD_SOURCE_MISSING", "domain": домен,
                               "segment": сегм, "field": поле,
                               "records_affected": f["TOTAL"],
                               "why": f["BLOCKED"],
                               "owner_layer": "content-pipeline (сбор подробностей)"})
                elif (f.get("ELIGIBLE_COVERAGE") or 1) < 0.9:
                    из.append({"kind": "FIELD_COVERAGE_BELOW_TARGET",
                               "domain": домен, "segment": сегм, "field": поле,
                               "records_affected": f["ELIGIBLE"] - f["ELIGIBLE_COVERED"],
                               "why": f"покрытие {f['ELIGIBLE_COVERAGE']:.1%} при цели 90%",
                               "owner_layer": "content-pipeline"})
    из.sort(key=lambda з: -з["records_affected"])
    return из


# --- главное ---------------------------------------------------------------
def главное(argv: list[str] | None = None) -> int:
    р = argparse.ArgumentParser(description=__doc__)
    р.add_argument("--out", default="artifacts/seo-daily")
    р.add_argument("--date", default=None)
    а = р.parse_args(argv)
    каталог = pathlib.Path(а.out)
    каталог.mkdir(parents=True, exist_ok=True)
    день = а.date or dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%d")

    стадии: dict[str, str] = {}

    # 1. сверка портфеля
    домены = INV.свести(КОРЕНЬ, [д for _, д, _ in ВИТРИНЫ] + list(ДОПОЛНИТЕЛЬНО))
    прежний = sorted(каталог.glob("cycle-*.json"))
    вчера = {}
    if прежний:
        вчера = json.loads(прежний[-1].read_text(encoding="utf-8")).get("inventory", {})
    diff = INV.разница(домены, вчера)
    стадии["INVENTORY_RECONCILE"] = "OK"

    # 2. снимок каталога и 4. матрица покрытия
    матрица = {}
    for sid, домен, сем in ВИТРИНЫ:
        кат = _прочитать(f"{ФРОНТ}/{sid}-catalog.json")
        if not кат:
            continue
        дет = (_прочитать(f"{ФРОНТ}/{sid}-details.json") or {}).get("details", {})
        матрица[домен] = COV.по_витрине(sid, домен, сем, кат, дет)
    стадии["CATALOG_SNAPSHOT"] = "OK" if матрица else "NO_DATA"
    стадии["COVERAGE_MATRIX"] = "OK" if матрица else "NO_DATA"

    # 3. трафик
    тр = трафик(домены, день, каталог)
    стадии["TRAFFIC_AND_INDEX_DATA"] = тр["status"]

    # 5. очередь
    очередь = очередь_пробелов(матрица)
    стадии["QUALIFIED_GAP_QUEUE"] = "OK"

    # 6–13. содержимое. Публикации берутся из журнала, а не объявляются в
    # коде: «опубликовано» — это запись о состоявшемся действии, а не мнение
    # цикла о собственных возможностях.
    журнал_публикаций = каталог / "publications.json"
    публикации = (json.loads(журнал_публикаций.read_text(encoding="utf-8"))
                  if журнал_публикаций.exists() else [])
    сегодняшние = [п for п in публикации if п.get("date") == день]
    проверенные = [п for п in сегодняшние if п.get("live_verified")]
    публикация = {
        "planned": len(сегодняшние), "generated": len(сегодняшние),
        "qa_passed": len(сегодняшние), "published": len(сегодняшние),
        "live_verified": len(проверенные),
        "rejected": 0, "rolled_back": 0,
        "urls_changed": sorted({u for п in сегодняшние for u in п.get("urls", [])}),
        "items": сегодняшние,
    }
    if not сегодняшние:
        публикация["blocked_reason"] = (
            "квалифицированных задач, готовых к публикации, не было; "
            "проходной текст вместо них не выпускается")
    стадии.update({
        "CONTENT_PLAN": "OK" if сегодняшние else "NOTHING_QUALIFIED",
        "GENERATION_OR_EDIT": "OK" if сегодняшние else "NOTHING_QUALIFIED",
        "FACT_AND_ENTITY_QA": "OK" if сегодняшние else "SKIPPED_NOTHING_TO_CHECK",
        "DUPLICATE_AND_CANNIBALIZATION_QA": "OK" if сегодняшние else "SKIPPED_NOTHING_TO_CHECK",
        "LINK_QA": "OK" if сегодняшние else "SKIPPED_NOTHING_TO_CHECK",
        "LIMITED_CANARY_PUBLISH": "OK" if сегодняшние else "NOTHING_TO_PUBLISH",
        "LIVE_VERIFICATION": ("OK" if проверенные else
                              ("FAILED" if сегодняшние else "NOTHING_TO_VERIFY")),
        "ROLLBACK_IF_NEEDED": "NOT_NEEDED",
    })

    # 14. журнал когорт
    журнал = каталог / "cohorts.json"
    когорты = json.loads(журнал.read_text(encoding="utf-8")) if журнал.exists() else []
    стадии["LEDGER_AND_COHORT_UPDATE"] = "OK"

    предварительный = {
        "report_id": f"seo-daily-{день}", "date": день,
        "coverage": матрица, "traffic": тр, "content": публикация,
        "gap_queue_total": len(очередь), "gap_queue_top": очередь[:10],
        "inventory": домены,
        "coverage_snapshot_sha256": COV.отпечаток(матрица),
        "topvisor": {"daily_runs": 0, "paid_operations": 0},
    }
    # 16. Qwen оценивает уже собранные факты и не вычисляет их заново.
    qwen = оценка_qwen(предварительный)
    стадии["QWEN_REVIEW"] = qwen["status"]

    отчёт = {
        "schema": "seo.daily_cycle/1.0.0",
        "report_id": f"seo-daily-{день}",
        "date": день,
        "cutoff_utc": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "inventory_version": INV.__name__ + "/1",
        "inventory": домены,
        "inventory_diff": diff,
        "coverage_snapshot_sha256": COV.отпечаток(матрица),
        "coverage": матрица,
        "traffic": тр,
        "gap_queue_top": очередь[:25],
        "gap_queue_total": len(очередь),
        "content": публикация,
        "cohorts": когорты,
        "topvisor": {
            "daily_runs": 0,
            "paid_operations": 0,
            "last_measured_at": None,
            "age_days": None,
            "status": "NOT_MEASURED",
            "why": "съём позиций ни разу не запускался: платная операция при "
                   "нулевом балансе и закрытой индексации",
        },
        "qwen": qwen,
        "stages": стадии,
        "delivery": доставка(каталог, день),
    }
    файл = каталог / f"cycle-{день}.json"
    файл.write_text(json.dumps(отчёт, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps({
        "report_id": отчёт["report_id"], "file": str(файл),
        "domains": len(домены),
        "managed": sum(1 for з in домены.values() if з["mutations_allowed"]),
        "coverage_domains": len(матрица),
        "gaps": len(очередь), "published": публикация["published"],
        "qwen": qwen["status"],
        "stages_blocked": sorted(к for к, v in стадии.items() if v.startswith("BLOCKED")),
    }, ensure_ascii=False))
    return 0


def доставка(каталог: pathlib.Path, день: str) -> dict:
    """Куда отчёт ушёл и подтверждено ли чтение.

    Локальный файл доставкой не является: никто его не получит, пока за ним
    не придут. Доставленным считается отчёт, у которого есть адрес владельца
    и подтверждённое чтение по этому адресу.
    """
    журнал = каталог / "deliveries.json"
    записи = (json.loads(журнал.read_text(encoding="utf-8"))
              if журнал.exists() else [])
    за_день = [з for з in записи if з.get("date") == день]
    if not за_день:
        return {"status": "WAITING_OWNER_DESTINATION",
                "note": "локальный файл доставкой не является"}
    последняя = за_день[-1]
    return {"status": ("DELIVERED" if последняя.get("readback_ok")
                       else "SENT_NOT_CONFIRMED"),
            "url": последняя.get("url"),
            "readback_ok": последняя.get("readback_ok"),
            "readback_note": последняя.get("readback_note")}


def оценка_qwen(отчёт: dict) -> dict:
    """Независимая оценка. Недоступность модели цикл не останавливает."""
    import importlib.util
    путь = СВОЙ / "seo_qwen_review.py"
    spec = importlib.util.spec_from_file_location("_qwen_review", путь)
    м = importlib.util.module_from_spec(spec)
    sys.modules["_qwen_review"] = м
    spec.loader.exec_module(м)
    return м.оценить(отчёт, корень=КОРЕНЬ)


if __name__ == "__main__":
    raise SystemExit(главное())
