"""apply-ga4-runpy.py: GA4 из analytics site.json — независимо от Метрики, только для своего домена."""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
спец = importlib.util.spec_from_file_location("apply_ga4_runpy", ROOT / "automation" / "host" / "apply-ga4-runpy.py")
инструмент = importlib.util.module_from_spec(спец)
спец.loader.exec_module(инструмент)

ОБРАЗЕЦ = '''import os


def окружение(конфиг: dict, данные) -> dict[str, str]:
    среда = {"X": "1"}
    аналитика = конфиг.get("analytics") or {}
    из_конфига = str(аналитика.get("counter_id") or "").strip()
    счётчик = os.environ.get("ANIMEGO_METRIKA_COUNTER") or (
        из_конфига if аналитика.get("enabled") else "")
    if счётчик:
        среда["LORDS_METRIKA_COUNTER"] = счётчик
    return среда
'''
ID = "G-TESTSTREAM1"


def _окружение(конфиг: dict, образец: str = ОБРАЗЕЦ) -> dict:
    новый, n = инструмент.привести(образец)
    assert n == 1
    п: dict = {}
    exec(новый, п)  # noqa: S102
    return п["окружение"](конфиг, None)


def _конфиг(**аналитика) -> dict:
    return {"domain": "a.test", "analytics": аналитика}


def test_exports_ga4_for_own_domain():
    с = _окружение(_конфиг(ga4_measurement_id=ID, ga4_allowed_hosts=["a.test", "WWW.a.test"]))
    assert с["LORDS_GA4_MEASUREMENT_ID"] == ID
    assert с["LORDS_GA4_ALLOWED_HOSTS"] == "a.test,www.a.test"


def test_independent_of_metrika():
    # Метрика выключена и без счётчика — GA4 всё равно есть.
    с = _окружение(_конфиг(enabled=False, ga4_measurement_id=ID, ga4_allowed_hosts=["a.test"]))
    assert "LORDS_METRIKA_COUNTER" not in с and с["LORDS_GA4_MEASUREMENT_ID"] == ID
    # и наоборот: Метрика есть, GA4 нет — Метрика не задета.
    с = _окружение(_конфиг(enabled=True, counter_id="123"))
    assert с["LORDS_METRIKA_COUNTER"] == "123" and "LORDS_GA4_MEASUREMENT_ID" not in с


@pytest.mark.parametrize("аналитика", [
    {"ga4_measurement_id": ID},                                     # нет списка хостов
    {"ga4_allowed_hosts": ["a.test"]},                              # нет ID
    {"ga4_measurement_id": ID, "ga4_allowed_hosts": ["b.test"]},    # ID соседа: домен не в списке
    {"ga4_measurement_id": " ", "ga4_allowed_hosts": ["a.test"]},
])
def test_refusals_leave_no_variables(аналитика):
    с = _окружение({"domain": "a.test", "analytics": аналитика})
    assert "LORDS_GA4_MEASUREMENT_ID" not in с and "LORDS_GA4_ALLOWED_HOSTS" not in с


def test_rerun_no_op_and_refusals():
    новый, _ = инструмент.привести(ОБРАЗЕЦ)
    assert инструмент.привести(новый) == (новый, 0)
    with pytest.raises(ValueError):
        инструмент.привести(ОБРАЗЕЦ.replace("    return среда\n", "    return dict(среда)\n"))
    with pytest.raises(ValueError):
        инструмент.привести(ОБРАЗЕЦ.replace("def окружение(", "def другое("))


@pytest.mark.parametrize("репо", ["an1mego-site", "animeg0-site", "an1meg0-site", "animedia-icu", "animedia-space"])
def test_real_run_py_anchor_and_compiles(репо):
    путь = ROOT / "var" / "site-repos" / репо / "run.py"
    if not путь.exists():
        pytest.skip(f"нет рабочей копии {репо}")
    новый, n = инструмент.привести(путь.read_text(encoding="utf-8"))
    assert n == 1
    compile(новый, str(путь), "exec")
