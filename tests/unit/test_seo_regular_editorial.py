"""REQ-SEO-REGULAR: шаг `editorial` регулярной проверки: подборки и анонсы против снимка каталога.

Поручение владельца 27.10: состав подборок должен пережить обновление каталога.
Шаг вызывает только читающий сценарий и не превращает его сбой в «дефектов 0».
"""

from __future__ import annotations

import json
import textwrap
from pathlib import Path

from seo_operator import regular


def _script(tmp_path: Path, body: str) -> Path:
    # сценарий ищет корень как parents[2] — повторяем ту же глубину
    p = tmp_path / "tree" / "automation" / "local" / "editorial-sets-validate.py"
    p.parent.mkdir(parents=True)
    p.write_text(textwrap.dedent(body), encoding="utf-8")
    return p


def test_not_connected_is_not_measured_not_zero():
    res = regular.editorial_sets(None)
    assert res["measured"] is False and "defects" not in res


def test_missing_script_is_named_failure(tmp_path):
    res = regular.editorial_sets(tmp_path / "nope.py")
    assert res["measured"] is False and res["reason"].startswith("СБОЙ")


def test_defect_is_counted_per_site(tmp_path):
    out = {
        "измерено": "2026-10-28T05:25:00Z",
        "витрины": [
            {"витрина": "zona-01",
             "подборки": {"исход": "найден дефект", "беды": ["luchshee-2026: id 1 нет в снимке"],
                          "ревизия каталога": "r2"},
             "анонсы": {"исход": "чисто", "беды": []}},
        ],
    }
    answer = tmp_path / "answer.json"
    answer.write_text(json.dumps(out, ensure_ascii=False), encoding="utf-8")
    script = _script(tmp_path, f"""
        import sys
        print(open({str(answer)!r}, encoding="utf-8").read())
        sys.exit(1)
    """)
    res = regular.editorial_sets(script)
    assert res["measured"] is True and res["rc"] == 1
    assert res["defects"] == 1
    assert res["sites"][0] == {"site": "zona-01", "kind": "подборки", "outcome": "найден дефект",
                               "defects": ["luchshee-2026: id 1 нет в снимке"], "revision": "r2"}


def test_non_json_answer_is_not_measured(tmp_path):
    script = _script(tmp_path, """
        import sys
        print("Traceback: снимок не читается")
        sys.exit(2)
    """)
    res = regular.editorial_sets(script)
    assert res["measured"] is False and res["rc"] == 2


def test_check_plan_runs_editorial_before_diff():
    names = [n for n, _ in regular.PLANS["check"]]
    assert names.index("editorial") < names.index("diff")


def test_memory_hungry_script_is_not_measured_and_parent_survives(tmp_path):
    # 27.10 17:25Z прогон оборвался на этом шаге без записи; валидатору нужно ~560 МБ
    # при MemoryMax=512M у юнита. Предел у дочернего процесса — его сбой, а не смерть прогона.
    script = _script(tmp_path, """
        blob = bytearray(600 << 20)
        print("{}")
    """)
    res = regular.editorial_sets(script, memory_mb=200)
    assert res["measured"] is False
    assert "памят" in res["reason"]


def test_step_marks_start_before_calling_script(tmp_path):
    events = []

    class J:
        def write(self, event, **kw):
            events.append(event)

    class Ctx:
        sources = {"editorial_validator": None}
        journal = J()

    regular.step_editorial(Ctx())
    assert events[:2] == ["editorial_started", "editorial_checked"]


def test_by_site_keeps_measured_sites_when_one_fails(tmp_path):
    # Zona упирается в память, Animedia — нет: частичное измерение лучше «не измерено» целиком.
    script = _script(tmp_path, """
        import json, sys
        site = sys.argv[sys.argv.index("--site") + 1]
        if site == "zona-01":
            raise MemoryError
        print(json.dumps({"измерено": "t", "витрины": [
            {"витрина": site, "подборки": {"исход": "чисто", "беды": []},
             "анонсы": {"исход": "чисто", "беды": []}}]}))
    """)
    res = regular.editorial_sets_by_site(script, ("animedia-01", "zona-01"))
    assert res["measured"] is False and res["defects"] == 0
    assert [x["site"] for x in res["sites"]] == ["animedia-01", "animedia-01"]
    assert res["unmeasured"] == [{"site": "zona-01",
                                  "reason": "не хватило памяти: предел 420 МБ, юниту дано 512 МБ"}]
