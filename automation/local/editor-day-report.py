#!/usr/bin/env python3
"""Календарный отчёт выпуска редактора за сутки по МСК: по доменам, с проверкой страниц.

Отличается от суточного отчёта seo-regular-daily (var/seo-regular/reports/daily/
<дата>.md): тот считает «сутки до формирования» (≈05:40 UTC → 05:40 UTC), этот —
календарный день Europe/Moscow 00:00–24:00. Оба нужны и не подменяют друг друга.

Источники и что из них берётся — каждый факт из своего, ни один не выводится
из другого:
* публикации описаний — история хранилищ доставки (editor_run.verify →
  publications), по одной записи на адрес; видимость — запрос страницы и поиск
  текста в видимой части (code 200 + text_visible);
* комментарии — журнал моста MCP (вызовы publish_comment с исходом); по доменам
  не делятся: журнал хранит имена аргументов, не значения — так и пишется;
* простой — решения шлюза var/editor-runs/gate.jsonl (тик ≈5 мин): «resources» —
  простой по ресурсам; «paused» — намеренная пауза между партиями, не простой;
* причины нулевого выпуска домена — исходы заданий очереди этого домена за день
  (queue_events), пауза публикации (PAUSED_PUBLISH) или «заданий не было».

    python3 automation/local/editor-day-report.py [--date ГГГГ-ММ-ДД] [--out файл.md]
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from seo_operator import editor_run as er  # noqa: E402

MSK = dt.timezone(dt.timedelta(hours=3))
UTC = dt.timezone.utc
RUNS = ROOT / "var" / "editor-runs" / "runs.jsonl"
GATE = ROOT / "var" / "editor-runs" / "gate.jsonl"
СЕТЬ = (
    "yummyani.site", "yummyani.org", "yummyani.biz", "yummyani7.site", "yummyani7.info",
    "an1mego.site", "animeg0.site", "an1meg0.site", "animedia.icu", "animedia.space",
    "lordserial33.biz", "lordfilm47.space", "1lordserials1.online", "lordserials22.info",
    "zonafilm.space", "zonafilm12.site", "zonafilm.cc",
)


def _iso(t: dt.datetime) -> str:
    return t.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def _строки(путь: Path) -> list[dict]:
    try:
        return [json.loads(с) for с in путь.read_text(encoding="utf-8").splitlines() if с.strip()]
    except OSError:
        return []


def собрать(день: dt.date) -> dict:
    начало = dt.datetime.combine(день, dt.time(0), tzinfo=MSK)
    конец = начало + dt.timedelta(days=1)
    н, к = _iso(начало), _iso(конец)
    партии = [r for r in _строки(RUNS) if н <= str(r.get("started_at", "")) < к and r.get("finished_at")]
    публикации, страницы, исходы_партий = [], {}, Counter()
    for r in партии:
        исходы_партий[r.get("verdict") or "без вердикта"] += 1
        v = er.verify(r["run_id"], r["started_at"], r["finished_at"])
        публикации += [{**p, "run": r["run_id"]} for p in v.get("publications") or []]
        for p in v.get("pages") or v.get("checks") or []:
            страницы[p.get("url")] = p
    комм = Counter(c.get("outcome") for c in er._bridge_calls(н, к) if c.get("tool") == "publish_comment")
    шлюз = [g for g in _строки(GATE) if н <= g.get("at", "") < к]
    состояния = Counter((g.get("gate") or {}).get("state") for g in шлюз)
    простой = [g["at"] for g in шлюз if (g.get("gate") or {}).get("state") == "resources"]
    задания = defaultdict(Counter)
    сайт_задания: dict[str, str] = {}
    for e in _строки(er.QUEUE_EVENTS):
        if e.get("site") and e.get("task_id"):
            сайт_задания[e["task_id"]] = e["site"]
        if e.get("event") == "task_result" and н <= e.get("at", "") < к:
            сайт = e.get("site") or сайт_задания.get(e.get("task_id") or "") or "?"
            задания[сайт][e.get("outcome") or "?"] += 1
    return {"день": день.isoformat(), "окно": [н, к], "партии": len(партии), "исходы_партий": исходы_партий,
            "публикации": публикации, "страницы": страницы, "комментарии": комм,
            "состояния_шлюза": состояния, "простой_тиков": len(простой),
            "простой_с": простой[0] if простой else None, "простой_по": простой[-1] if простой else None,
            "задания": задания}


def отрисовать(о: dict) -> str:
    по_доменам = Counter(p["site"] for p in о["публикации"])
    видно = sum(1 for p in о["публикации"]
                if (о["страницы"].get(p["url"]) or {}).get("status") == 200
                and (о["страницы"].get(p["url"]) or {}).get("text_visible"))
    стоят = getattr(er, "PAUSED_PUBLISH", {})
    строки = [
        f"# Выпуск редактора за {о['день']} (календарные сутки МСК)",
        "",
        f"Окно UTC: {о['окно'][0]} … {о['окно'][1]}. Не путать с суточным отчётом "
        "seo-regular-daily (сутки до формирования).",
        "",
        f"* Партий: {о['партии']} ({', '.join(f'{k} {v}' for k, v in о['исходы_партий'].most_common())}).",
        f"* Описаний опубликовано (история доставки): **{len(о['публикации'])}**; "
        f"видно на страницах: **{видно}** из {len(о['публикации'])}.",
        f"* Комментарии (журнал моста, publish_comment): "
        f"{', '.join(f'{k} {v}' for k, v in о['комментарии'].most_common()) or 'нет вызовов'}; "
        "по доменам журнал не делит — не измерено.",
        f"* Простой по ресурсам: {о['простой_тиков']} тиков шлюза ≈ {о['простой_тиков'] * 5} мин"
        + (f" (первый {о['простой_с']}, последний {о['простой_по']})" if о["простой_тиков"] else "")
        + f"; состояния шлюза: {dict(о['состояния_шлюза'])} (paused — пауза между партиями, не простой).",
        "",
        "| домен | описаний | видно | исходы заданий за день / причина нуля |",
        "| --- | --- | --- | --- |",
    ]
    for д in СЕТЬ:
        n = по_доменам.get(д, 0)
        в = sum(1 for p in о["публикации"] if p["site"] == д
                and (о["страницы"].get(p["url"]) or {}).get("text_visible"))
        исходы = о["задания"].get(д) or Counter()
        прич = (", ".join(f"{k} {v}" for k, v in исходы.most_common(5))
                if исходы else "заданий по домену за день не было")
        if not n and исходы:
            прич = "ни одного текста; исходы: " + прич
        if д in стоят:
            прич += f"; сейчас публикация приостановлена (PAUSED_PUBLISH): {стоят[д]}"
        строки.append(f"| {д} | {n} | {в} | {прич} |")
    прочие = sorted(set(по_доменам) - set(СЕТЬ))
    if прочие:
        строки.append(f"\nДомены вне перечня: {прочие}")
    строки += ["", "## Адреса", ""]
    for p in sorted(о["публикации"], key=lambda x: x["at"]):
        с = о["страницы"].get(p["url"]) or {}
        строки.append(f"* {p['at']} {p['url']} — {с.get('status')} "
                      f"{'видно' if с.get('text_visible') else 'НЕ ВИДНО'} (партия {p['run']})")
    return "\n".join(строки) + "\n"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--date", help="ГГГГ-ММ-ДД по МСК; по умолчанию вчера")
    ap.add_argument("--out")
    a = ap.parse_args(argv)
    день = (dt.date.fromisoformat(a.date) if a.date
            else (dt.datetime.now(MSK) - dt.timedelta(days=1)).date())
    текст = отрисовать(собрать(день))
    if a.out:
        Path(a.out).write_text(текст, encoding="utf-8")
    print(текст)
    return 0


if __name__ == "__main__":
    sys.exit(main())
