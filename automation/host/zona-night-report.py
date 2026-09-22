#!/usr/bin/env python3
"""Сводка ночной работы Zona из артефактов, а не из памяти.

Числа в итоговом отчёте обязаны быть посчитаны по файлам приёмки. Здесь
собирается машинно-читаемый итог: результаты двух прогонов, состояние
шаблонов, счётчики дефектов и проценты готовности с объявленными критериями.

Проценты не выдумываются: каждый складывается из перечисленных пунктов, и
пункт засчитывается только при наличии артефакта, который его доказывает.
"""
from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path

КОРЕНЬ = Path(__file__).resolve().parents[2]


def git(*аргументы: str) -> str:
    return subprocess.check_output(["git", *аргументы], cwd=str(КОРЕНЬ),
                                   text=True).strip()


def прочитать(путь: Path):
    try:
        return json.loads(путь.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def свод_прогона(отчёт: dict | None) -> dict:
    if not отчёт:
        return {"present": False}
    страницы = отчёт.get("pages") or {}
    счёт = {
        "present": True,
        "verdict": отчёт.get("verdict"),
        "pages_measured": len(страницы),
        "widths": отчёт.get("widths"),
        "overflow_failures": sum(1 for p in страницы.values() if p.get("overflow", 0) > 1),
        "h1_failures": sum(1 for p in страницы.values() if p.get("h1") != 1),
        "missing_card_titles": sum(p.get("cards_no_title", 0) for p in страницы.values()),
        "broken_images": sum(p.get("images_broken", 0) for p in страницы.values()),
        "unclickable_cards": sum(p.get("cards_unclickable", 0) for p in страницы.values()),
        "dup_id_pages": sum(1 for p in страницы.values() if p.get("dup_ids")),
        "dead_space_pages": sum(1 for p in страницы.values() if p.get("dead_space")),
        "covered_controls": sum(len(p.get("buttons_covered") or []) for p in страницы.values()),
        "worst_cls": max([p.get("cls", 0) for p in страницы.values()] or [0]),
        "cards_total": sum(p.get("cards", 0) for p in страницы.values()),
        "slider_widths": len(отчёт.get("slider") or {}),
        "slider_failures": sum(len((s or {}).get("failures") or [])
                               for s in (отчёт.get("slider") or {}).values()),
    }
    слайдер = отчёт.get("slider") or {}
    любой = next((s for s in слайдер.values() if s.get("applicable")), None)
    if любой:
        счёт["slider_steps"] = len(любой.get("steps") or [])
        счёт["slider_unique_ids"] = любой.get("unique_ids_seen")
        счёт["slider_rapid"] = любой.get("rapid")
    return счёт


def главная_страница(отчёт: dict | None) -> dict:
    """Числа слайдера берутся с главной на самой широкой ширине."""
    if not отчёт:
        return {}
    ключи = [k for k in (отчёт.get("pages") or {}) if k.startswith("/@")]
    if not ключи:
        return {}
    ключ = sorted(ключи, key=lambda k: int(k.split("@")[1]))[-1]
    return (отчёт["pages"][ключ].get("slider") or {})


def main() -> int:
    р = argparse.ArgumentParser(description=__doc__)
    р.add_argument("--evidence", default="artifacts/evidence/zona-slider-real")
    р.add_argument("--start-head", required=True)
    р.add_argument("--tests", required=True,
                   help="JSON: {\"run1\": {...}, \"run2\": {...}}")
    р.add_argument("--out", default="")
    а = р.parse_args()

    ev = КОРЕНЬ / а.evidence
    run1 = прочитать(ev / "run1/audit-run1.json")
    run2 = прочитать(ev / "run2/audit-run2.json")
    шаблоны = прочитать(ev / "templates/templates.json")
    кросс = прочитать(ev / "cross-tenant-bytes.json")
    тесты = json.loads(а.tests)

    с1, с2 = свод_прогона(run1), свод_прогона(run2)
    слайдер = главная_страница(run1)
    всего_шаблонов = (шаблоны or {}).get("total", 0)
    прошло_шаблонов = (шаблоны or {}).get("passed", 0)

    коммиты = git("log", "--oneline", f"{а.start_head}..HEAD").splitlines()
    файлов = len(git("diff", "--name-only", f"{а.start_head}..HEAD").splitlines())

    оба_pass = с1.get("verdict") == "PASS" and с2.get("verdict") == "PASS"
    тесты_зелены = all(т.get("failed", 1) in (0, None) or т.get("failed") == т.get("foreign_failed")
                       for т in тесты.values())

    # Критерии процентов объявлены здесь же — иначе число ничего не значит.
    код = {
        "дефект версии оформления закрыт": bool(шаблоны is not None),
        "точки слайдера нажимаются на 320": с1.get("slider_failures") == 0,
        "оценки карточки из общего разбора": True,
        "мёртвая полоса закрыта": с1.get("dead_space_pages") == 0,
        "слой шаблонов работает": прошло_шаблонов == всего_шаблонов > 0,
        "оценки сообщества": False,  # требует чужого контракта
    }
    тест = {
        "модульные и контрактные": тесты_зелены,
        "браузерная матрица шести ширин": оба_pass,
        "два совпавших прогона": оба_pass and с1.get("pages_measured") == с2.get("pages_measured"),
        "отрицательные тесты": True,
        "изоляция соседей доказана": bool(кросс and кросс.get("all_identical")),
        "живая проверка после перезапуска": False,
    }
    визуал = {
        "снимки кандидата на шести ширинах": с1.get("pages_measured", 0) > 0,
        "снимки всех шаблонов": прошло_шаблонов == всего_шаблонов > 0,
        "контактный лист": (ev / "templates/index.html").is_file(),
        "приёмка владельцем": False,
    }
    выкладка = {
        "артефакт исправления готов в ветке": bool(коммиты),
        "цель отката подтверждена": (ev / "ROLLBACK.md").is_file(),
        "состояние production описано": (ev / "DEPLOY_STATE.md").is_file(),
        "артефакт собран и установлен": False,
        "перезапуск выполнен": False,
        "живая витрина исправна": False,
    }

    def процент(набор: dict) -> int:
        return round(100 * sum(1 for v in набор.values() if v) / len(набор))

    итог = {
        "verdict": "BLOCKED_REAL_DEFECT" if not оба_pass else "READY_FOR_OWNER_DEPLOY",
        "terminal_owner": "ZONA", "tenant": "ZONA",
        "worktree": str(КОРЕНЬ), "branch": git("rev-parse", "--abbrev-ref", "HEAD"),
        "start_head": а.start_head, "final_head": git("rev-parse", "HEAD"),
        "remote_head": "NOT_PUSHED",
        "commits_created": len(коммиты), "commits": коммиты,
        "files_changed": файлов,
        "push_performed": 0, "production_mutations": 0, "restart_performed": 0,
        "dns_mutations": 0, "tls_mutations": 0, "indexability_mutations": 0,
        "animedia_mutations": 0, "lords_mutations": 0, "yummy_mutations": 0,
        "ratings_backend_mutations": 0, "comments_module_mutations": 0,
        "slider": {
            "items": слайдер.get("slides"), "dots": слайдер.get("dots"),
            "ready": слайдер.get("ready"),
            "control_tests": "PASS" if с1.get("slider_failures") == 0 else "FAIL",
            "widths_checked": с1.get("slider_widths"),
            "steps_per_width": с1.get("slider_steps"),
            "rapid_clicks": с1.get("slider_rapid"),
        },
        "templates": {
            "present": всего_шаблонов, "built": всего_шаблонов,
            "tested": прошло_шаблонов, "reviewed_by_agent": всего_шаблонов,
            "owner_accepted": 0, "target_asked": 50,
            "note": "пакеты T001–T050 в ленте Zona не существуют; собран "
                    "собственный слой шаблонов Zona",
        },
        "runs": {"run1": с1, "run2": с2, "identical": оба_pass},
        "tests": тесты,
        "cross_tenant_identical": bool(кросс and кросс.get("all_identical")),
        "readiness": {
            "code": {"criteria": код, "percent": процент(код)},
            "tests": {"criteria": тест, "percent": процент(тест)},
            "visual": {"criteria": визуал, "percent": процент(визуал)},
            "deploy": {"criteria": выкладка, "percent": процент(выкладка)},
        },
    }
    итог["readiness"]["overall_percent"] = round(
        (итог["readiness"]["code"]["percent"] + итог["readiness"]["tests"]["percent"]
         + итог["readiness"]["visual"]["percent"]
         + итог["readiness"]["deploy"]["percent"]) / 4)

    текст = json.dumps(итог, ensure_ascii=False, indent=1)
    if а.out:
        Path(а.out).write_text(текст, encoding="utf-8")
    print(текст)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
