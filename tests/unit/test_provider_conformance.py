"""REQ-CONTRACT-PROVIDER: схема сверяется с работающей службой, а не только с собой.

Проверка совместимости ловит расхождения между версиями схемы и ничего не знает
о том, делает ли служба то, что схема обещает. Именно это расхождение дороже
всего: клиент генерируется из схемы и ломается о реализацию.

Оба случая ниже взяты не из головы — они найдены 2026-09-03 на живом site-engine.
"""

from __future__ import annotations

from factory.contracts.provider_conformance import (
    blocking,
    check_provider,
    declared_get_paths,
    declares_security,
)


def schema(paths: dict, security: bool = False) -> dict:
    doc = {"openapi": "3.1.0", "paths": {p: {"get": {}} for p in paths}}
    if security:
        doc["components"] = {"securitySchemes": {"bearer": {"type": "http", "scheme": "bearer"}}}
    return doc


def responder(mapping: dict[str, int | None]):
    return lambda path: mapping.get(path)


def kinds(findings) -> set[str]:
    return {f.kind for f in findings}


def test_declared_endpoint_returning_404_is_reported_as_mismatch() -> None:
    """Реальный случай: /api/v1/ingestion/status объявлен и отвечает 404."""
    doc = schema(["/api/v1/health", "/api/v1/ingestion/status"], security=True)
    found = check_provider(doc, responder({"/api/v1/health": 200, "/api/v1/ingestion/status": 404}))
    assert "MISMATCH" in kinds(found)
    assert any("ingestion" in f.path for f in found)


def test_undeclared_auth_is_reported() -> None:
    """Реальный случай: служба отвечает 401, а securitySchemes в схеме нет.

    Клиент, сгенерированный из такой схемы, не пошлёт учётные данные.
    """
    doc = schema(["/api/v1/health", "/api/v1/sites"], security=False)
    found = check_provider(doc, responder({"/api/v1/health": 200, "/api/v1/sites": 401}))
    assert "UNDECLARED_AUTH" in kinds(found)


def test_declared_auth_that_nothing_enforces_is_reported() -> None:
    """Обратное расхождение не менее опасно: схема обещает защиту, которой нет."""
    doc = schema(["/api/v1/sites"], security=True)
    found = check_provider(doc, responder({"/api/v1/sites": 200}))
    assert "UNENFORCED_AUTH" in kinds(found)


def test_consistent_contract_yields_nothing() -> None:
    doc = schema(["/api/v1/health", "/api/v1/sites"], security=True)
    found = check_provider(doc, responder({"/api/v1/health": 200, "/api/v1/sites": 401}))
    assert blocking(found) == []


def test_unreachable_service_is_skipped_not_failed() -> None:
    """Провал по недоступности приучил бы игнорировать красный результат."""
    doc = schema(["/api/v1/sites"], security=True)
    found = check_provider(doc, responder({"/api/v1/sites": None}))
    assert kinds(found) == {"SKIPPED"}
    assert blocking(found) == []


def test_templated_paths_are_not_probed() -> None:
    """404 на подставленном идентификаторе значит «нет записи», а не «нет маршрута»."""
    doc = schema(["/api/v1/sites/{siteId}"], security=True)
    assert check_provider(doc, responder({})) == []


def test_only_get_paths_are_declared_for_probing() -> None:
    """Дёргать POST у живой службы нельзя: это изменило бы её состояние."""
    doc = {"openapi": "3.1.0", "paths": {"/a": {"get": {}}, "/b": {"post": {}}}}
    assert declared_get_paths(doc) == ["/a"]


def test_global_security_counts_as_declaration() -> None:
    doc = {"openapi": "3.1.0", "paths": {}, "security": [{"bearer": []}]}
    assert declares_security(doc) is True
    assert declares_security({"openapi": "3.1.0", "paths": {}}) is False


def test_access_denied_still_means_the_route_exists() -> None:
    """403 — это «нельзя», а не «нет»: маршрут объявлен не зря."""
    doc = schema(["/api/v1/sites"], security=True)
    found = check_provider(doc, responder({"/api/v1/sites": 403}))
    assert "MISMATCH" not in kinds(found)
