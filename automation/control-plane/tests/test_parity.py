"""Regression: OpenAPI не вправе объявлять параметр, который провайдер не применяет.

Именно этот разрыв и сделал R1 непринимаемым. Проверка существует, чтобы он
не мог вернуться незамеченным: она сравнивает объявленное с поведением, а не
описание с описанием.
"""
from __future__ import annotations
import json, urllib.error, urllib.request
import pytest

Б = "http://127.0.0.1:8790"


def дай(путь: str):
    try:
        with urllib.request.urlopen(Б + путь, timeout=15) as о:
            return о.status, json.loads(о.read() or b"{}")
    except urllib.error.HTTPError as e:
        try:
            return e.code, json.loads(e.read() or b"{}")
        except Exception:  # noqa: BLE001
            return e.code, {}


@pytest.fixture(scope="module")
def openapi():
    к, т = дай("/api/v1/contracts/openapi")
    assert к == 200
    return т


def test_объявленные_параметры_действительно_применяются(openapi):
    """Для каждого объявленного enum-параметра проверяем влияние на выдачу."""
    парам = {p["name"]: p for p in
             openapi["paths"]["/api/v1/sites"]["get"].get("parameters", [])}
    assert парам, "параметры не объявлены"
    к, полный = дай("/api/v1/sites")
    всего = len(полный["items"])
    for имя, p in парам.items():
        значения = (p.get("schema") or {}).get("enum") or []
        assert значения, f"{имя}: объявлен без enum"
        # Хотя бы одно значение обязано сузить выдачу — иначе параметр
        # объявлен, но не применяется, и контракт лжёт.
        сузил = False
        for v in значения:
            к2, т2 = дай(f"/api/v1/sites?{имя}={v}")
            assert к2 == 200, f"{имя}={v} -> {к2}"
            if len(т2["items"]) < всего:
                сузил = True
            for з in т2["items"]:
                assert str(з.get(имя)) == v, \
                    f"{имя}={v}: в выдаче запись со значением {з.get(имя)!r}"
        assert сузил, f"{имя}: объявлен, но ни одно значение не сузило выдачу"


def test_объявленный_enum_совпадает_с_принимаемым(openapi):
    """Значение вне enum обязано отвергаться, значение из enum — приниматься."""
    парам = {p["name"]: p for p in
             openapi["paths"]["/api/v1/sites"]["get"]["parameters"]}
    for имя, p in парам.items():
        for v in (p["schema"]["enum"]):
            к, _ = дай(f"/api/v1/sites?{имя}={v}")
            assert к == 200, f"{имя}={v} из enum отвергнут: {к}"
        к, т = дай(f"/api/v1/sites?{имя}=__not_in_enum__")
        assert к == 422, f"{имя}: значение вне enum принято с {к}"
        assert т.get("error_code") == "FILTER_VALUE_UNKNOWN"


def test_фильтр_и_снимок_дают_одно_множество():
    """Расхождение предиката означало бы два источника правды."""
    к1, ф = дай("/api/v1/sites?environment=production&lifecycle_state=ACTIVE")
    к2, сн = дай("/api/v1/registry/snapshot")
    assert к1 == 200 and к2 == 200
    a = {i["site_id"] for i in ф["items"]}
    b = {s["site_id"] for s in сн["sites"]}
    assert a == b, f"расхождение: {sorted(a ^ b)}"
    assert len(a) == 9, f"боевых действующих {len(a)}"


def test_семантика_and_объявлена_и_соблюдается(openapi):
    сем = openapi["paths"]["/api/v1/sites"]["get"].get("x-filter-semantics", {})
    assert сем.get("combination") == "AND"
    assert сем.get("applied") == "server-side"
    assert сем.get("silent_ignore") is False
    к, только_среда = дай("/api/v1/sites?environment=production")
    к, оба = дай("/api/v1/sites?environment=production&lifecycle_state=DRAFT")
    # AND обязан сузить относительно одиночного фильтра, а не расширить.
    assert len(оба["items"]) <= len(только_среда["items"])
    for з in оба["items"]:
        assert з["environment"] == "production" and з["lifecycle_state"] == "DRAFT"


def test_известный_разрыв_закрыт(openapi):
    """x-known-gap про неприменяемый фильтр не должен вернуться."""
    узел = openapi["paths"]["/api/v1/sites"]["get"]
    assert "x-known-gap" not in узел, "разрыв снова объявлен в контракте"


def test_capability_фильтра_available():
    к, кат = дай("/api/v1/capabilities/registry.sites.filter")
    assert к == 200, "возможности фильтра нет в каталоге"
    assert кат["status"] == "AVAILABLE", кат["status"]
    assert кат["last_verified_at"] and кат["evidence_ref"]
