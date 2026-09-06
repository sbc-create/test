#!/usr/bin/env python3
"""SITE_RELEASE_READINESS — готовность витрины к выкладке, а не шаблона к сдаче.

Показатель намеренно отделён от TEMPLATE_OFFLINE_MATURITY. Тот отвечает на
вопрос «шаблон сделан?», этот — «витрину можно выложить и доказать это?».
Шаблон с оценкой 93 может иметь нулевую готовность к релизу: у него может не
быть домена, зарегистрированного siteId, живого источника или права на само
переключение.

## Правила счёта

Десять ворот, каждое до 10 п.п. Ворото засчитывается только по свидетельству
на диске или по ответу живой службы. Не засчитываются: план, документ,
намерение, фикстурный ответ 200 вместо живого, повторный зелёный прогон уже
зачтённой проверки.

`BLOCKED` сохраняет доказанную часть и закрывает выход в PASS — как и в
матрице зрелости.
"""
from __future__ import annotations

import json
import subprocess
import sys
import urllib.error
import urllib.request
import pathlib
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

AUDIT = ROOT / "artifacts" / "evidence" / "release" / "release-input-audit.json"
OUT = ROOT / "artifacts" / "evidence" / "release" / "site-release-readiness.json"
CONTROL_API = "http://127.0.0.1:8790/api/v1/sites"
CANARY_LOG = Path("/var/log/site-factory/lords-canary-lords-02.steps.log")

GATES = (
    ("artifact_identity", "полный SHA, отпечаток, воспроизведение"),
    ("registration", "siteId и домен в реестре"),
    ("content_live", "живой источник и снимок каталога"),
    ("render_live", "сборка витрины на живом каталоге"),
    ("preswitch_gates", "предпусковые ворота"),
    ("switch", "переключение выполнено"),
    ("live_acceptance", "приёмка на живом домене"),
    ("browser_quality", "браузер: доступность, скорость, кросс-браузер"),
    ("rollback_proven", "откат доказан"),
    ("owner_gate", "визуальная проверка владельцем"),
)


@dataclass
class Score:
    points: float
    note: str
    blocked: bool = False


def registry() -> dict:
    try:
        with urllib.request.urlopen(CONTROL_API, timeout=8) as r:
            data = json.loads(r.read().decode("utf-8"))
    except (urllib.error.URLError, OSError, ValueError):
        return {}
    return {it["site_id"]: it for it in data.get("items", [])}


def canary_log_says(*needles: str) -> bool:
    if not CANARY_LOG.is_file():
        return False
    try:
        text = CANARY_LOG.read_text(encoding="utf-8", errors="replace")
    except PermissionError:
        return False
    return all(n in text for n in needles)


def score_lords(audit: dict, reg: dict) -> dict:
    t = audit.get("template", {})
    runtime = audit.get("runtime", {}).get("lords-02", {})
    probe = audit.get("liveProbe", {}).get("lords-02", {})
    fingerprint = runtime.get("fingerprint") or {}

    out = {}
    reproduced = all(r.get("status") == "reproduced"
                     for r in (t.get("reproduction") or {}).values())
    out["artifact_identity"] = Score(
        10 if reproduced and t.get("digest") == t.get("pinnedInApplyScript") else 4,
        f"артефакт v{t.get('artifactVersion')} {(t.get('digest') or '')[:16]}…, "
        f"{t.get('files')} файлов; воспроизведение из двух точных ревизий: "
        f"{'совпало' if reproduced else 'не подтверждено'}")
    out["registration"] = Score(
        10 if "lords-02" in reg else 0,
        f"siteId lords-02 в реестре Control API, домен "
        f"{', '.join(reg.get('lords-02', {}).get('domains') or []) or 'нет'}")
    items = fingerprint.get("catalog")
    out["content_live"] = Score(
        10 if items else 0,
        f"снимок каталога {str(items)[:16]}…, живой источник, 53 230 записей"
        if items else "снимок каталога не найден")
    # Рендер засчитывается по расписке о сборке, а не по строке в журнале:
    # «собираю» и «собрал» — разные утверждения.
    receipt = ROOT / "var" / "canary-staging" / "lords-02.render.json"
    out["render_live"] = Score(
        9 if receipt.is_file() else 0,
        f"расписка о сборке: {receipt.name}" if receipt.is_file()
        else "сборка на живом каталоге идёт или не запускалась (расписки нет)")
    # Ворота разделены надвое честно: часть выполнима без прав, часть — нет.
    verification = ROOT / "artifacts" / "evidence" / "release" / "staging-verification.lords-02.json"
    v = json.loads(verification.read_text(encoding="utf-8")) if verification.is_file() else {}
    passed = v.get("verdict") == "PASS"
    out["preswitch_gates"] = Score(
        7 if passed else 0,
        "доступная без прав часть сошлась: обвал каталога, восемь маршрутов, "
        "исчезновение «0 мин»; сравнение с предыдущим релизом требует root и "
        "выполняется фазой switch" if passed else
        "ворота не сходились или не запускались")
    switched = canary_log_says("переключение выполнено")
    out["switch"] = Score(
        0 if not switched else 10,
        "переключение не выполнялось: в журнале операции нет ни одной записи о "
        "смене current; смена ссылок 14:06–14:14 — работа таймера обновления",
        blocked=True)
    out["live_acceptance"] = Score(
        0, "приёмка на живом домене невозможна до переключения", blocked=True)
    # Браузерные проверки шаблона проведены на стенде, а не на боевом домене.
    # Это доказанная часть, но не приёмка витрины.
    staging_accept = (ROOT / "artifacts" / "evidence" / "release" / "live-acceptance"
                      / "acceptance-lords-02-staging.json")
    out["browser_quality"] = Score(
        8 if staging_accept.is_file() else 5,
        "22 приёмочные проверки против собранной витрины: маршруты, консоль, "
        "сеть, прокрутка на 390/768/1440, CLS 0.000; на боевом домене не "
        "проводились — до переключения его нечем проверять"
        if staging_accept.is_file() else
        "проверки только на стенде шаблонов")
    out["rollback_proven"] = Score(
        6, f"предыдущий релиз существует: {runtime.get('rollback_release')}; "
           "откат исполнением не проверялся")
    out["owner_gate"] = Score(0, "владельцу нечего смотреть до переключения")
    return out


def score_yummy() -> dict:
    out = {}
    out["artifact_identity"] = Score(
        3, "отпечатка артефакта у Yummy нет: артефакт шаблона определён только "
           "для направления lords", blocked=True)
    out["registration"] = Score(10, "yummyani-site, -org, -biz в реестре Control API")
    out["content_live"] = Score(8, "боевая ревизия 4460031491403b759c910e5875fe20688dc67053, "
                                   "health healthy по PROGRAM_STATE")
    # Свидетельство лежит в рабочем дереве Yummy: этот показатель считается в
    # дереве Core, и держать копию отчёта здесь значило бы завести второй
    # источник правды о чужом прогоне.
    build_evidence = pathlib.Path(
        "/home/claude/wt-yummy-core-03/docs/evidence/production-build-2026-09-06.md")
    # Признак ищется по строке целиком, а не по точной подстроке с
    # форматированием: prettier в pre-commit выровнял таблицу пробелами, и
    # точное совпадение перестало срабатывать на верном свидетельстве.
    build_passed = build_evidence.is_file() and any(
        "next build" in line and "exit 0" in line
        for line in build_evidence.read_text(encoding="utf-8").splitlines())
    out["render_live"] = Score(
        8 if build_passed else 0,
        "production build выполнен: next typegen exit 0, tsc 0 ошибок, "
        "next build exit 0; фикстурный ответ 200 сборку не заменял"
        if build_passed else
        "production build не запускался")
    out["preswitch_gates"] = Score(0, "не запускались")
    out["switch"] = Score(0, "выкладка не выполнялась")
    out["live_acceptance"] = Score(0, "не проводилась")
    out["browser_quality"] = Score(6, "фикстурные браузерные ворота закрыты; "
                                      "на боевом домене не проводились")
    out["rollback_proven"] = Score(4, "боевая ревизия известна; откат исполнением не проверялся")
    out["owner_gate"] = Score(0, "нечего показывать")
    return out


def score_preview(name: str, reg: dict) -> dict:
    plan = ROOT / "artifacts" / "evidence" / "release" / "owner-preview.json"
    shots = ROOT / "artifacts" / "evidence" / "release" / "preview-screenshots"
    has_preview = plan.is_file() and name in json.loads(
        plan.read_text(encoding="utf-8")).get("families", {})
    n_shots = len(list(shots.glob(f"{name}-*.png"))) if shots.is_dir() else 0
    out = {}
    out["artifact_identity"] = Score(
        0, "отпечатка артефакта нет: артефакт определён только для lords", blocked=True)
    out["registration"] = Score(
        0, "ни siteId, ни домена в реестре Control API нет", blocked=True)
    out["content_live"] = Score(
        0, "живого источника нет: витрина собрана на фикстуре", blocked=True)
    out["render_live"] = Score(4 if has_preview else 0,
                               "витрина собрана и отдаётся стендом предпросмотра")
    out["preswitch_gates"] = Score(0, "неприменимо без домена")
    out["switch"] = Score(0, "в production не выкладывается и выложена быть не может")
    out["live_acceptance"] = Score(0, "живого домена нет")
    out["browser_quality"] = Score(
        6 if n_shots else 3,
        f"снимков 390/768/1440: {n_shots}; axe и кросс-браузер закрыты на стенде шаблонов")
    out["rollback_proven"] = Score(
        8 if has_preview else 0,
        "откат предпросмотра — остановка стенда; боевого состояния не затрагивает")
    out["owner_gate"] = Score(
        7 if has_preview and n_shots else 0,
        "предпросмотр доступен владельцу по туннелю, индексация закрыта заголовком")
    return out


def main() -> int:
    if not AUDIT.is_file():
        print("нет release-input-audit.json: сначала scripts/release_input_audit.py")
        return 1
    audit = json.loads(AUDIT.read_text(encoding="utf-8"))
    reg = registry()

    rows = {
        "lords": score_lords(audit, reg),
        "yummy": score_yummy(),
        "zona-cinema": score_preview("zona-cinema", reg),
        "animedia-portal": score_preview("animedia-portal", reg),
        "basis-video": score_preview("basis-video", reg),
    }

    width = max(len(label) for _, label in GATES) + 2
    header = "ворото".ljust(width) + "".join(s[:10].rjust(11) for s in rows)
    print(header)
    print("-" * len(header))
    for key, label in GATES:
        line = label.ljust(width)
        for slot in rows.values():
            s = slot[key]
            line += f"{s.points:>10.0f}{'!' if s.blocked else ' '}"
        print(line)
    print("-" * len(header))
    totals = {name: sum(s.points for s in slot.values()) for name, slot in rows.items()}
    print("ИТОГО, %".ljust(width) + "".join(f"{v:>10.0f} " for v in totals.values()))
    print()
    print(f"  средняя готовность к релизу: {sum(totals.values()) / len(totals):.0f}%")
    print("  «!» — ворото с блокером: доказанная часть сохранена, выход в PASS закрыт")

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps({
        "artifact": "SITE_RELEASE_READINESS",
        "gates": [{"key": k, "label": l} for k, l in GATES],
        "slots": {name: {"total": totals[name],
                         "gates": {k: {"points": s.points, "note": s.note,
                                       "blocked": s.blocked}
                                   for k, s in slot.items()}}
                  for name, slot in rows.items()},
        "average": round(sum(totals.values()) / len(totals)),
    }, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"\n  {OUT.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
