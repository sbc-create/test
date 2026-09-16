"""Producer-тесты пакетов референсов: черновик обязан оставаться черновиком.

Пакет референса опаснее обычной документации ровно одним: он выглядит как
измерение. Числа в нём читают как замеры, снимки — как доказательства, а
статус — как готовность. Поэтому проверяется не только форма, но и то, что
пакет **не** утверждает лишнего:

* черновик не включает production и не включает индексацию;
* `latest` не используется нигде;
* снимков нет — значит, в индексе стоит BLOCKED, а не PASS;
* токены не заполнены, пока не на чем их измерить.

Последнее — главное. Заполнить `VISUAL_TOKENS` правдоподобными числами проще
всего, и именно поэтому это запрещено кодом, а не только договорённостью.
"""

from __future__ import annotations

import json
import re

import pytest
import yaml

from factory.paths import PATHS

PACKS_DIR = PATHS.root / "docs" / "reference-packs"
PACKS = ("zona-w140", "amd-online")

REQUIRED_FILES = (
    "README_AI.md",
    "TemplateManifest.yaml",
    "blocks.yaml",
    "ROUTES.yaml",
    "PAGE_MAP.md",
    "BLOCK_MAP.md",
    "VISUAL_TOKENS.yaml",
    "VISUAL_DECISIONS.md",
    "SCREENSHOT_INDEX.md",
    "STATES.md",
    "PLAYER_SHELL.md",
    "RATINGS.md",
    "AD_SLOTS.md",
    "ACCEPTANCE.md",
    "PREVIEW.md",
    "TEST_INVENTORY.md",
    "CHANGELOG.md",
    "fixtures/home.normal.json",
    "fixtures/title.normal.json",
    "fixtures/states.json",
)


def _pack(name: str):
    return PACKS_DIR / name


def _yaml(name: str, file: str) -> dict:
    return yaml.safe_load((_pack(name) / file).read_text(encoding="utf-8"))


def _access_status(name: str) -> str:
    """Состояние доступа к референсу по плану измерения.

    Именно оно решает, что пакету положено утверждать: пока доступа нет,
    заполненные токены запрещены; как только он появился, запрещена пустота.
    """
    plan = PATHS.root / "config" / "reference-packs" / f"reference-pack.{name}.json"
    if not plan.exists():
        return "unknown"
    return (json.loads(plan.read_text(encoding="utf-8")).get("access") or {}).get("status", "unknown")


@pytest.mark.parametrize("name", PACKS)
class TestPackShape:
    def test_every_required_file_exists(self, name):
        missing = [f for f in REQUIRED_FILES if not (_pack(name) / f).exists()]
        assert not missing, f"{name}: не хватает {missing}"

    def test_manifest_and_routes_agree(self, name):
        manifest = _yaml(name, "TemplateManifest.yaml")
        routes = _yaml(name, "ROUTES.yaml")
        manifest_ids = {r["routeId"] for r in manifest["routes"]}
        routes_ids = {r["routeId"] for r in routes["routes"]}
        assert manifest_ids == routes_ids, (
            f"{name}: манифест объявляет {sorted(manifest_ids)}, "
            f"ROUTES.yaml — {sorted(routes_ids)}")

    def test_route_ids_are_unique(self, name):
        routes = _yaml(name, "ROUTES.yaml")["routes"]
        ids = [r["routeId"] for r in routes]
        assert len(ids) == len(set(ids)), f"{name}: повторяются routeId"

    def test_block_ids_are_unique(self, name):
        blocks = _yaml(name, "blocks.yaml")["blocks"]
        ids = [b["blockId"] for b in blocks]
        assert len(ids) == len(set(ids)), f"{name}: повторяются blockId"

    def test_every_block_order_reference_exists(self, name):
        blocks = {b["blockId"] for b in _yaml(name, "blocks.yaml")["blocks"]}
        for route in _yaml(name, "ROUTES.yaml")["routes"]:
            unknown = [b for b in route["blockOrder"] if b not in blocks]
            assert not unknown, (
                f"{name}/{route['routeId']}: порядок ссылается на несуществующие "
                f"блоки {unknown}")

    def test_every_block_is_documented(self, name):
        for block in _yaml(name, "blocks.yaml")["blocks"]:
            for field in ("responsibility", "data", "states", "mustNot", "protectedBy"):
                assert block.get(field), (
                    f"{name}/{block['blockId']}: не заполнено поле {field}")


@pytest.mark.parametrize("name", PACKS)
class TestDraftClaimsNothingExtra:
    def test_draft_does_not_enable_production_or_indexing(self, name):
        manifest = _yaml(name, "TemplateManifest.yaml")
        assert manifest["status"] == "draft", f"{name}: статус не draft"
        assert manifest["productionEnabled"] is False, f"{name}: включён production"
        assert manifest["indexingEnabled"] is False, f"{name}: включена индексация"

    def test_latest_is_never_used_as_a_version(self, name):
        """Запрещено значение `latest`, а не слово.

        Первая версия проверки искала подстроку и падала на собственном поле
        `allowLatest: false`, то есть на объявлении запрета. Проверять надо
        значение: `version: latest` — это молчаливый переход на что попало.
        """
        import re

        pattern = re.compile(r":\s*['\"]?latest['\"]?\s*$", re.IGNORECASE | re.MULTILINE)
        for path in _pack(name).rglob("*"):
            if not path.is_file():
                continue
            text = path.read_text(encoding="utf-8", errors="ignore")
            assert not pattern.search(text), (
                f"{name}/{path.name}: версия объявлена как latest")

    def test_visual_tokens_match_reference_access(self, name):
        """Токены заполнены тогда и только тогда, когда референс доступен.

        Прежняя редакция утверждала пустоту безусловно — тогда оба референса
        были закрыты профилем, и это совпадало со смыслом. После открытия
        доступа такая проверка начала запрещать сам замер, то есть защищать
        форму вместо смысла. Условие стало двусторонним: пока доступа нет,
        правдоподобные числа запрещены; как только он появился, пустота
        перестаёт быть честной и требует замера с происхождением.
        """
        tokens = _yaml(name, "VISUAL_TOKENS.yaml")
        if _access_status(name) != "reachable":
            assert tokens["status"] == "blocked", f"{name}: токены объявлены измеренными"
            assert not tokens["tokens"], (
                f"{name}: токены заполнены, хотя референс недоступен — "
                "правдоподобное число в поле замера неотличимо от замера")
            return
        assert tokens["status"] == "measured", (
            f"{name}: референс доступен, а токены объявлены заблокированными")
        assert tokens["tokens"], f"{name}: референс доступен, а замеров нет"
        for т in tokens["tokens"]:
            assert т.get("evidence"), f"{name}: токен {т.get('name')} без доказательства"
            assert т.get("status") == "measured_by_factory", (
                f"{name}: токен {т.get('name')} без статуса замера")

    def test_screenshot_index_matches_reference_access(self, name):
        """Индекс снимков говорит правду о том, снято ли что-нибудь."""
        text = (_pack(name) / "SCREENSHOT_INDEX.md").read_text(encoding="utf-8")
        rows = [line for line in text.splitlines() if line.strip().startswith("|")]
        if _access_status(name) != "reachable":
            assert "BLOCKED" in text, f"{name}: индекс снимков не отмечает недоступность"
            # Проверяется строка таблицы, а не слово в тексте: фраза «ни одна
            # строка не помечена PASS» сама содержит PASS, и наивный поиск
            # подстроки падал на объяснении запрета.
            marked = [line for line in rows if "PASS" in line]
            assert not marked, (
                f"{name}: строка индекса помечена PASS, хотя снимков нет: {marked}")
            return
        # Доступен — значит снимки перечислены с дайджестами, иначе независимый
        # проверяющий не сможет сверить ни один из них.
        digests = [line for line in rows if re.search(r"[0-9a-f]{64}", line)]
        assert len(digests) >= 9, (
            f"{name}: референс доступен, а строк с дайджестами всего {len(digests)}")

    def test_fixtures_are_deterministic_and_synthetic(self, name):
        for fixture in ("home.normal", "title.normal", "states"):
            data = json.loads(
                (_pack(name) / "fixtures" / f"{fixture}.json").read_text(encoding="utf-8"))
            assert data["deterministic"] is True, f"{name}/{fixture}: не детерминирована"
            assert data["synthetic"] is True, f"{name}/{fixture}: не помечена синтетической"
            assert data["fixtureVersion"], f"{name}/{fixture}: нет версии"
            assert data["generatedAt"], f"{name}/{fixture}: нет времени порождения"

    def test_compatibility_stays_pending_until_versions_are_published(self, name):
        manifest = _yaml(name, "TemplateManifest.yaml")
        compat = manifest["compatibility"]
        assert compat["onIncompatibleContract"] == "fail_build", (
            f"{name}: несовместимость не останавливает сборку")
        assert compat["allowLatest"] is False, f"{name}: разрешён latest"
        assert compat["status"] == "pending", (
            f"{name}: совместимость объявлена подтверждённой, хотя версий контракта нет")


class TestPackRegistrationMatchesInventory:
    def test_every_pack_has_a_registered_source(self):
        """Пакет существует только для источника, переданного владельцем."""
        inventory = yaml.safe_load(
            (PATHS.root / "inventory" / "reference-sources.yaml").read_text(encoding="utf-8"))
        registered = {s["ref"] for s in inventory["sources"]}
        for name in PACKS:
            assert name in registered, (
                f"{name}: пакет есть, а источник не зарегистрирован — "
                "список источников не расширяется по инициативе агента")
