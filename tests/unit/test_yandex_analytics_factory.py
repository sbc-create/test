"""REQ-ANALYTICS-FACTORY: аналитика встроена в фабрику, а не приклеена сбоку.

Проверяется то, что видно снаружи: ворота конвейера, валидация пакета, разметка
страницы, реестр публичных идентификаторов и — отдельно — что индексация
остаётся выключенной, пока не выполнены все условия разом.
"""
from __future__ import annotations

import copy
import json

import pytest

from factory import validation
from factory.analytics import gate, registry, snippet
from factory.analytics.yandex import BLOCKED_DEPLOYMENT
from factory.paths import PATHS


@pytest.fixture(autouse=True)
def _no_live_check(monkeypatch):
    """Сеть в unit-тестах не трогается: живая проверка выключается явно."""
    monkeypatch.setenv(gate.LIVE_CHECK_ENV, "0")


def _package(**overrides) -> dict:
    package = {
        "domain": "yummyani.site",
        "environment": "production",
        "production_authorized": True,
        "fixture": False,
        "seo_indexing_enabled": False,
        "analytics": {
            "provider": "yandex_metrika",
            "enabled": True,
            "counter_id": 90000001,
            "allowed_hosts": ["yummyani.site"],
            "webvisor": False,
        },
        "webmaster": {"enabled": True, "verification_status": "PLANNED"},
    }
    for key, value in overrides.items():
        if isinstance(value, dict) and isinstance(package.get(key), dict):
            package[key] = {**package[key], **value}
        else:
            package[key] = value
    return package


# ------------------------------------------------------------------- ворота
def test_a_complete_package_passes_the_gate():
    assert gate.check(_package(), "production") == []


def test_missing_counter_blocks_production():
    blockers = gate.check(_package(analytics={"counter_id": None}), "production")
    assert [b["status"] for b in blockers] == ["BLOCKED_INPUT"]
    assert "analytics apply" in blockers[0]["required_input"]


def test_hostname_mismatch_blocks_production():
    blockers = gate.check(_package(analytics={"allowed_hosts": ["другой.tld"]}), "production")
    assert any("отсутствует в analytics.allowed_hosts" in b["reason"] for b in blockers)


def test_empty_allowed_hosts_blocks_production():
    blockers = gate.check(_package(analytics={"allowed_hosts": []}), "production")
    assert any("пуст" in b["reason"] for b in blockers)


def test_webvisor_blocks_everywhere():
    for environment in ("staging", "production"):
        blockers = gate.check(_package(analytics={"webvisor": True}), environment)
        assert any("Вебвизор" in b["reason"] for b in blockers), environment


def test_disabled_analytics_passes_the_gate_untouched():
    assert gate.check(_package(analytics={"enabled": False}), "production") == []


def test_unreachable_api_gives_its_own_status(monkeypatch):
    """Недоступный API — BLOCKED_ANALYTICS_ACCESS, а не BLOCKED_ACCESS и не DONE."""
    from factory.analytics.yandex import CredentialsReport

    monkeypatch.setenv(gate.LIVE_CHECK_ENV, "1")

    class Down:
        def validate_credentials(self):
            return CredentialsReport(token_file={}, metrika_status=503, metrika_ok=False)

    blockers = gate.check(_package(), "production", provider=Down())
    assert "BLOCKED_ANALYTICS_ACCESS" in [b["status"] for b in blockers]
    reason = next(b["reason"] for b in blockers if b["status"] == "BLOCKED_ANALYTICS_ACCESS")
    assert "503" in reason and "выдуманным" in reason


def test_the_gate_can_only_report_its_declared_statuses(monkeypatch):
    from factory import pipeline

    monkeypatch.setenv(gate.LIVE_CHECK_ENV, "0")
    produced = {b["status"] for b in gate.check(_package(analytics={"counter_id": None,
                                                                    "webvisor": True}),
                                                "production")}
    assert produced <= set(pipeline.ANALYTICS_GATE_STATUSES)


# --------------------------------------------------------------- индексация
def test_indexing_stays_off_by_default():
    allowed, reason = gate.indexing_allowed(_package(), "production")
    assert allowed is False
    assert "seo_indexing_enabled" in reason


@pytest.mark.parametrize("override,fragment", [
    ({"environment": "staging"}, "production"),
    ({"production_authorized": False}, "production_authorized"),
    ({"fixture": True}, "fixture"),
    ({"webmaster": {"enabled": False}}, "webmaster.enabled"),
    ({"webmaster": {"verification_status": "PLANNED"}}, "не подтверждены"),
    ({"webmaster": {"verification_status": "IN_PROGRESS"}}, "не подтверждены"),
])
def test_every_indexing_condition_is_required(override, fragment, monkeypatch):
    """Одно «почти выполнено» — это «нельзя»: индексация откатывается месяцами."""
    monkeypatch.setattr(registry, "indexing_enabled", lambda root=None: True)
    package = _package(seo_indexing_enabled=True,
                       webmaster={"enabled": True, "verification_status": "VERIFIED"})
    for key, value in override.items():
        if isinstance(value, dict):
            package[key] = {**package[key], **value}
        else:
            package[key] = value
    environment = package["environment"]
    allowed, reason = gate.indexing_allowed(package, environment)
    assert allowed is False, f"{override} не остановило индексацию"
    assert fragment in reason, reason


def test_indexing_is_allowed_only_when_everything_holds(monkeypatch):
    monkeypatch.setattr(registry, "indexing_enabled", lambda root=None: True)
    package = _package(seo_indexing_enabled=True,
                       webmaster={"enabled": True, "verification_status": "VERIFIED"})
    allowed, reason = gate.indexing_allowed(package, "production")
    assert allowed is True, reason


def test_the_committed_registry_keeps_indexing_off():
    """Файл в git обязан лежать с выключенной индексацией."""
    assert registry.indexing_enabled() is False
    for entry in registry.properties():
        assert entry.indexing_enabled is False, entry.domain


# --------------------------------------------------------------- валидация
def _validate(package: dict) -> list:
    blockers: list = []
    warnings: list[str] = []
    validation._check_analytics(package, blockers, warnings)
    return blockers


def test_verified_status_on_an_undeployed_domain_is_rejected():
    """Статус красивее реальности — самый опасный класс ошибки в этом слое."""
    blockers = _validate(_package(domain="yummyani.localhost",
                                  webmaster={"verification_status": "VERIFIED",
                                             "verification_marker": "abcdef123456"}))
    assert any("домен тестовый" in b.reason for b in blockers)


def test_verified_without_a_stored_marker_is_rejected():
    blockers = _validate(_package(webmaster={"verification_status": "VERIFIED",
                                             "verification_marker": None}))
    assert any("маркер не сохранён" in b.reason for b in blockers)


def test_test_hostname_in_allowed_hosts_is_rejected():
    blockers = _validate(_package(analytics={"allowed_hosts": ["site-a.localhost"]}))
    assert any("тестовый адрес" in b.reason for b in blockers)


def test_counter_bound_to_a_test_domain_is_rejected():
    blockers = _validate(_package(domain="pilot.localhost.test",
                                  analytics={"allowed_hosts": []}))
    assert any(b.field == "analytics.counter_id" for b in blockers)


def test_indexing_without_verified_rights_is_blocked_seo():
    blockers = _validate(_package(seo_indexing_enabled=True))
    statuses = {b.status for b in blockers}
    assert statuses == {"BLOCKED_SEO"}
    assert any("не подтверждены" in b.reason for b in blockers)


def test_real_site_packages_keep_indexing_off():
    """Ни один пакет в репозитории не должен приехать с включённой индексацией."""
    for path in sorted(PATHS.sites.glob("*/package.yaml")):
        import yaml

        package = yaml.safe_load(path.read_text(encoding="utf-8"))
        assert not package.get("seo_indexing_enabled"), path


# ---------------------------------------------------------------- разметка
def test_tag_is_absent_without_a_counter():
    assert snippet.analytics_script_tag(
        counter_id=None, allowed_hosts=["yummyani.site"],
        environment="production", enabled=True) == ""


def test_tag_is_absent_on_staging():
    assert snippet.analytics_script_tag(
        counter_id=1, allowed_hosts=["yummyani.site"],
        environment="staging", enabled=True) == ""


def test_tag_carries_the_counter_and_the_hosts():
    tag = snippet.analytics_script_tag(
        counter_id=90000001, allowed_hosts=["yummyani.site"],
        environment="production", enabled=True)
    assert 'data-counter-id="90000001"' in tag
    assert 'data-allowed-hosts="yummyani.site"' in tag
    # Инлайнового кода нет: CSP не должна выбирать между аналитикой и плеером.
    assert "<script src=" in tag and "function" not in tag


def test_marker_markup_matches_the_documented_format():
    assert snippet.verification_meta("abcdef0123456789") == (
        '<meta name="yandex-verification" content="abcdef0123456789" />')
    name, body = snippet.verification_html_file("abcdef0123456789")
    assert name == "yandex_abcdef0123456789.html"
    assert "Verification: abcdef0123456789" in body


@pytest.mark.parametrize("marker", [
    None, "", "<script>alert(1)</script>", "код с пробелами", "x", "../../etc/passwd",
])
def test_a_marker_that_is_not_a_code_never_reaches_the_page(marker):
    assert snippet.verification_meta(marker) == ""
    assert snippet.verification_html_file(marker) is None


# ------------------------------------------------------------------ рендер
def _render(pilot_package, tmp_path, *, environment: str, **overrides) -> str:
    """Рендерит главную страницу пилотного пакета и возвращает её HTML.

    Рендер вызывается напрямую, а не через `factory build`: проверяется разметка,
    и подмешивать сюда production-валидацию пакета (лицензия, происхождение
    контента) значило бы проверять не то, что заявлено в имени теста.
    """
    from factory.render import SiteRenderer

    package = copy.deepcopy(pilot_package)
    package.update(overrides)
    renderer = SiteRenderer(package, "pilot-local", output=tmp_path / environment)
    renderer.render(environment)
    return (tmp_path / environment / "public" / "index.html").read_text(encoding="utf-8")


ANALYTICS_ON = {
    "provider": "yandex_metrika", "enabled": True, "counter_id": 90000123,
    "allowed_hosts": ["pilot.localhost.test"], "webvisor": False,
}


def test_rendered_page_carries_the_tag_and_the_marker(pilot_package, tmp_path):
    html = _render(
        pilot_package, tmp_path, environment="production",
        analytics=ANALYTICS_ON,
        webmaster={"enabled": True, "verification_status": "VERIFIED",
                   "verification_marker": "abcdef0123456789"},
    )
    assert 'data-counter-id="90000123"' in html
    assert 'data-allowed-hosts="pilot.localhost.test"' in html
    assert '<meta name="yandex-verification" content="abcdef0123456789" />' in html
    assert "/assets/analytics.js" in html
    assert (tmp_path / "production" / "public" / "assets" / "analytics.js").exists()


def test_staging_page_has_no_metrika_tag(pilot_package, tmp_path):
    """На стенде тега нет вовсе — не «есть, но выключен»."""
    html = _render(pilot_package, tmp_path, environment="staging", analytics=ANALYTICS_ON)
    assert "data-counter-id" not in html
    assert "mc.yandex.ru" not in html
    assert "analytics.js" not in html


def test_page_without_analytics_is_unchanged(pilot_package, tmp_path):
    html = _render(pilot_package, tmp_path, environment="production")
    assert "data-counter-id" not in html
    assert "yandex-verification" not in html


def test_marker_survives_a_rebuild(pilot_package, tmp_path):
    """Релиз, потерявший мета-тег, теряет и подтверждение прав."""
    webmaster = {"enabled": True, "verification_status": "VERIFIED",
                 "verification_marker": "abcdef0123456789"}
    first = _render(pilot_package, tmp_path / "a", environment="production",
                    analytics=ANALYTICS_ON, webmaster=webmaster)
    second = _render(pilot_package, tmp_path / "b", environment="production",
                     analytics=ANALYTICS_ON, webmaster=webmaster)
    assert 'content="abcdef0123456789"' in first
    assert 'content="abcdef0123456789"' in second


# ------------------------------------------------------------------ реестр
def test_registry_matches_its_schema():
    registry.validate(registry.load())


#: Все домены реестра и их счётчики. Список задан явно, а не выведен из файла:
#: тест, читающий тот же файл, что и проверяет, согласится с любой правкой — в
#: том числе с потерянным доменом или подменённым счётчиком.
LIVE_COUNTERS = {
    "yummyani.site": 111881037,
    "yummyani.org": 111881038,
    "yummyani.biz": 111881039,
    # Три направления Lords заведены 2026-08-27. Профили у доменов разные
    # (lords-general / lords-new / lords-curated), поэтому и счётчики разные:
    # объединять их зеркалами запрещено ровно по той же причине, что и у Yummy.
    "lordfilm47.space": 112010269,
    "lordserial33.biz": 112010274,
    "1lordserials1.online": 112010277,
}


def test_registry_holds_exactly_the_known_domains():
    domains = [p.domain for p in registry.properties()]
    assert domains == list(LIVE_COUNTERS)


def test_each_domain_is_independent():
    """Домены не зеркала: у каждого свой счётчик и свой список hostname."""
    entries = registry.properties()
    hosts = [tuple(e.allowed_hosts) for e in entries]
    assert len(set(hosts)) == len(entries)
    # Счётчик, попавший на два домена, собирал бы чужие визиты в чужой отчёт.
    counters = [e.counter_id for e in entries]
    assert len(set(counters)) == len(counters), f"счётчик повторяется: {counters}"
    for entry in entries:
        assert entry.allowed_hosts == [entry.domain]


def test_registry_never_stores_a_secret():
    """Проверяются значения, а не слова: в пояснении слово «токен» уместно.

    Тест на подстроку запретил бы объяснить в комментарии, чего в файле не
    бывает, и при этом пропустил бы секрет, лежащий в поле с невинным именем.
    """
    from datetime import datetime

    from factory.redaction import SENSITIVE_KEY_RE, _looks_like_secret

    def _is_timestamp(value: str) -> bool:
        """Метка времени ISO-8601 — не секрет.

        Эвристика `_looks_like_secret` смотрит на длину и разнообразие
        символов, и `2026-08-23T20:49:56Z` под неё подходит. В самой редакции
        это безвредно (она применяет эвристику только к значениям переменных
        окружения), но здесь дало бы ложную тревогу на каждом реестре.
        """
        try:
            datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return False
        return True

    data = json.loads((PATHS.root / registry.REGISTRY_PATH).read_text(encoding="utf-8"))
    findings: list[str] = []

    def walk(node, path="") -> None:
        if isinstance(node, dict):
            for key, value in node.items():
                if SENSITIVE_KEY_RE.search(key):
                    findings.append(f"{path}/{key}: имя поля выглядит секретным")
                walk(value, f"{path}/{key}")
        elif isinstance(node, list):
            for index, item in enumerate(node):
                walk(item, f"{path}[{index}]")
        elif (isinstance(node, str) and path.rsplit("/", 1)[-1] != "note"
              and not _is_timestamp(node) and _looks_like_secret(node)):
            findings.append(f"{path}: значение выглядит секретом")

    walk(data)
    assert findings == [], findings


def test_webmaster_starts_blocked_not_done():
    for entry in registry.properties():
        assert entry.webmaster_status == BLOCKED_DEPLOYMENT
        assert entry.webmaster_status != "DONE"


def test_registry_round_trips_without_losing_fields(tmp_path):
    """Обновление одного поля не должно стирать остальные — это и есть откат конфигурации."""
    import shutil

    root = tmp_path / "repo"
    (root / "config").mkdir(parents=True)
    (root / "schemas").mkdir()
    shutil.copy(PATHS.root / registry.REGISTRY_PATH, root / registry.REGISTRY_PATH)
    shutil.copy(PATHS.root / registry.SCHEMA_PATH, root / registry.SCHEMA_PATH)

    before = registry.load(root)
    registry.upsert({"domain": "yummyani.org", "counter_id": 90000002,
                     "counter_state": "created"}, root)
    after = registry.load(root)

    changed = next(p for p in after["properties"] if p["domain"] == "yummyani.org")
    assert changed["counter_id"] == 90000002
    assert changed["counter_name"] == "YummyAnime — yummyani.org"
    assert changed["allowed_hosts"] == ["yummyani.org"]
    assert changed["webmaster"]["verification_status"] == BLOCKED_DEPLOYMENT
    untouched = [p for p in after["properties"] if p["domain"] != "yummyani.org"]
    assert untouched == [p for p in before["properties"] if p["domain"] != "yummyani.org"]


def test_registry_refuses_data_that_breaks_the_schema(tmp_path):
    """Схему под данные не подгоняют — данные обязаны ей соответствовать."""
    import shutil

    from factory.errors import BlockedInput

    root = tmp_path / "repo"
    (root / "config").mkdir(parents=True)
    (root / "schemas").mkdir()
    shutil.copy(PATHS.root / registry.REGISTRY_PATH, root / registry.REGISTRY_PATH)
    shutil.copy(PATHS.root / registry.SCHEMA_PATH, root / registry.SCHEMA_PATH)

    broken = registry.load(root)
    broken["properties"][0]["webmaster"]["verification_status"] = "DONE"
    with pytest.raises(BlockedInput):
        registry.save(broken, root)


# --------------------------------------------------------------------------
# Зафиксированный результат боевой настройки
# --------------------------------------------------------------------------
#: Счётчики, фактически созданные в аккаунте владельца. Не «пример», а состояние
#: продакшена: расхождение означает, что счётчик подменили или пересоздали, и
#: заметить это должен тест, а не отчёт Метрики через месяц.
def test_registry_records_the_live_counters():
    for entry in registry.properties():
        assert entry.counter_id == LIVE_COUNTERS[entry.domain], entry.domain
        # `created` допустим только для счётчиков, заведённых в этом же цикле;
        # повторный прогон обязан их переиспользовать, а не завести второй.
        assert entry.raw["counter_state"] in ("reused", "created"), (
            f"{entry.domain}: состояние {entry.raw['counter_state']!r} означает, что "
            "счётчик не подтверждён Метрикой"
        )


def test_every_counter_has_all_nine_goals_with_numeric_ids():
    """Девять целей и девять числовых идентификаторов — иначе конверсии не измерить."""
    from factory.analytics import events

    total = 0
    for entry in registry.properties():
        goals = entry.raw["goals"]
        goal_ids = entry.raw["goal_ids"]
        assert set(goals) == set(events.EVENT_IDS), entry.domain
        assert set(goal_ids) == set(events.EVENT_IDS), entry.domain
        assert all(isinstance(value, int) and value > 0 for value in goal_ids.values())
        total += len(goal_ids)
    expected = 9 * len(LIVE_COUNTERS)
    assert total == expected, (
        f"ожидалось {expected} идентификаторов целей на {len(LIVE_COUNTERS)} счётчиков, "
        f"записано {total}"
    )


def test_session_recording_is_off_on_every_live_counter():
    """Требование задания, дважды нарушенное по дороге. Теперь оно под тестом."""
    for entry in registry.properties():
        assert entry.raw["webvisor"] is False, entry.domain
        assert entry.raw["problems"] == [], (
            f"{entry.domain}: настройка завершена, а в problems что-то осталось: "
            f"{entry.raw['problems']}"
        )


def test_setup_is_complete_but_indexing_and_webmaster_are_not():
    """Готовность аналитики не означает готовности поиска — это разные ворота."""
    assert registry.indexing_enabled() is False
    for entry in registry.properties():
        assert entry.indexing_enabled is False, entry.domain
        assert entry.webmaster_status == BLOCKED_DEPLOYMENT, entry.domain
        assert entry.raw["webmaster"]["sitemap_submitted"] is False, entry.domain
