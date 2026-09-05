"""REQ-TEMPLATE-CONTRACT: шаблон описывается манифестом, а манифест — проверяем.

Набор держит три обещания контракта:

1. манифест валиден по схеме, и невалидный отвергается;
2. обязательные блоки на месте — и в манифесте, и в выданной разметке;
3. шаблон, объявивший блок, который рендерер не умеет рисовать, отвергается.

Третье — самое важное. До контракта такой блок молча пропадал: цепочка `elif`
в `render.py _home()` не имеет ветки `else`, и неизвестное имя просто не
совпадало ни с чем. Так в направлении и жили `hero_timeline` у `lords-new` и
`hero_editorial` у `lords-curated` — объявленные, но никем не рисуемые.
"""

from __future__ import annotations

import copy
import json
import os
import shutil
from pathlib import Path

import pytest
import yaml

from factory.lords import theme as theme_mod
from factory.paths import PATHS
from factory.templates import contract
from factory.templates import fixture as fixture_mod
from factory.templates import scaffold as scaffold_mod


@pytest.fixture(scope="module")
def schema() -> dict:
    return contract.schema()


@pytest.fixture(scope="module")
def blueprint() -> dict:
    return yaml.safe_load((PATHS.root / contract.BLUEPRINT_FILE).read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def manifests() -> dict[str, dict]:
    return {contract.load_manifest(p)["profile"]: contract.load_manifest(p)
            for p in contract.manifest_paths()}


@pytest.fixture
def sandbox(tmp_path) -> Path:
    """Корень, в котором scaffold можно запускать по-настоящему.

    Рендерер подключается ссылкой: он читается, а не правится, и копировать сто
    килобайт исходника ради проверки манифеста незачем.
    """
    root = tmp_path / "root"
    (root / "schemas").mkdir(parents=True)
    (root / "blueprints" / "lords" / "profiles").mkdir(parents=True)
    for name in (contract.SCHEMA_FILE, contract.PACKAGE_SCHEMA_FILE):
        shutil.copy2(PATHS.root / "schemas" / name, root / "schemas" / name)
    shutil.copy2(PATHS.root / contract.BLUEPRINT_FILE, root / contract.BLUEPRINT_FILE)
    for path in (PATHS.root / contract.PROFILE_DIR).glob("*.yaml"):
        shutil.copy2(path, root / contract.PROFILE_DIR / path.name)
    os.symlink(PATHS.root / "factory", root / "factory")
    return root


class TestRegistryMatchesTheRenderer:
    """Реестр блоков не должен расходиться с кодом, который их рисует."""

    def test_every_registered_block_has_a_branch(self):
        assert set(contract.BLOCKS) == set(contract.renderer_blocks())

    def test_schema_enumerates_exactly_the_registered_blocks(self, schema):
        enum = set(schema["$defs"]["home_block"]["enum"])
        assert enum == set(contract.BLOCKS)

    def test_schema_enumerates_exactly_the_blueprint_sections(self, schema, blueprint):
        assert set(schema["$defs"]["section_name"]["enum"]) == set(blueprint["sections"])

    def test_density_enum_matches_the_stylesheet(self, schema):
        enum = set(schema["properties"]["layout"]["properties"]["density"]["enum"])
        assert enum == set(theme_mod.DENSITY)

    def test_token_names_match_the_stylesheet(self, schema):
        names = set(schema["$defs"]["design_tokens"]["properties"])
        assert names == set(theme_mod.DEFAULT_TOKENS)

    def test_breakpoints_are_the_ones_the_packages_promise(self):
        # Пакеты сайтов объявляют ширины приёмки доступности; три ширины
        # контракта обязаны быть среди них, иначе проверяется не то, что обещано.
        package = yaml.safe_load(
            (PATHS.sites / "lords-01" / "package.yaml").read_text(encoding="utf-8"))
        promised = set(package["acceptance"]["accessibility"]["viewports"])
        assert set(contract.BREAKPOINTS) <= promised


class TestWorkingTemplatesPass:
    def test_every_template_of_the_direction_is_accepted(self):
        problems = contract.validate_repository()
        assert problems == [], "\n".join(str(p) for p in problems)

    def test_each_template_declares_a_card_block(self, manifests):
        for name, manifest in manifests.items():
            blocks = set(manifest["layout"]["home_blocks"])
            assert blocks & contract.CARD_BLOCKS, name


class TestABadManifestIsRejected:
    @pytest.fixture
    def manifest(self, manifests) -> dict:
        return copy.deepcopy(manifests["lords-general"])

    def test_a_block_the_renderer_cannot_draw_is_rejected(self, manifest):
        manifest["layout"]["home_blocks"].append("hero_timeline")
        problems = [str(p) for p in contract.validate_manifest(manifest)]
        assert any("hero_timeline" in p for p in problems), problems

    def test_a_block_the_renderer_can_draw_but_the_registry_ignores_is_reported(self, manifest):
        # Реестр отстал от кода: блок рисуется, но контракт о нём не знает.
        # Расхождение обязано быть видно, а не разрешено по умолчанию.
        problems = [str(p) for p in contract.validate_repository()]
        assert problems == []
        saved = contract.BLOCKS.pop("editor_note")
        try:
            problems = [str(p) for p in contract.validate_repository()]
            assert any("editor_note" in p for p in problems), problems
        finally:
            contract.BLOCKS["editor_note"] = saved

    def test_a_hero_block_listed_after_the_stream_is_rejected(self, manifest):
        # Первый экран рисуется до цикла по home_blocks, поэтому порядок в
        # манифесте обязан начинаться с его блоков — иначе манифест обещает
        # расстановку, которой на странице не будет.
        manifest["layout"]["home_blocks"] = [
            "top_carousel", "hero_search", "latest_grid", "genre_chips"]
        problems = [str(p) for p in contract.validate_manifest(manifest)]
        assert any("hero_search" in p for p in problems), problems

    def test_a_home_without_cards_is_rejected(self, manifest):
        manifest["layout"]["home_blocks"] = ["hero_search", "genre_chips", "year_grid"]
        problems = [str(p) for p in contract.validate_manifest(manifest)]
        assert any("class=\"card" in p for p in problems), problems

    def test_a_flagged_block_without_its_flag_is_rejected(self, manifest):
        manifest["layout"]["home_blocks"].append("calendar")
        manifest["layout"]["show_calendar"] = False
        problems = [str(p) for p in contract.validate_manifest(manifest)]
        assert any("show_calendar" in p for p in problems), problems

    def test_an_owned_section_without_texts_is_rejected(self, manifest):
        manifest["sections"].pop("movies_index")
        problems = [str(p) for p in contract.validate_manifest(manifest)]
        assert any("movies_index" in p for p in problems), problems

    def test_texts_for_a_section_the_template_does_not_own_are_rejected(self, manifest):
        manifest["sections"]["new_index"] = {
            "title": "Новое", "h1": "Новое", "description": "Новые поступления каталога."}
        problems = [str(p) for p in contract.validate_manifest(manifest)]
        assert any("new_index" in p for p in problems), problems

    def test_columns_that_shrink_with_the_screen_are_rejected(self, manifest):
        manifest["layout"]["columns"] = {"mobile": 4, "tablet": 4, "desktop": 3}
        problems = [str(p) for p in contract.validate_manifest(manifest)]
        assert any("колонки" in p for p in problems), problems

    def test_an_unknown_field_is_rejected(self, manifest):
        manifest["shadow_setting"] = True
        assert contract.validate_manifest(manifest)

    def test_a_token_the_stylesheet_never_reads_is_rejected(self, manifest):
        manifest["theme"]["tokens"]["shadow"] = "#000000"
        assert contract.validate_manifest(manifest)

    def test_a_theme_the_blueprint_does_not_declare_is_rejected(self, manifest):
        manifest["theme"]["name"] = "lords_neon"
        problems = [str(p) for p in contract.validate_manifest(manifest)]
        assert any("lords_neon" in p for p in problems), problems

    def test_title_page_ownership_without_templates_is_rejected(self, manifest):
        manifest.pop("title_page")
        problems = [str(p) for p in contract.validate_manifest(manifest)]
        assert any("title_page" in p for p in problems), problems

    def test_two_templates_cannot_own_the_same_section(self, sandbox, manifests):
        clash = copy.deepcopy(manifests["lords-curated"])
        clash["profile"] = "lords-clash"
        clash["label"] = "Lords Clash"
        (sandbox / contract.PROFILE_DIR / "lords-clash.yaml").write_text(
            yaml.safe_dump(clash, allow_unicode=True, sort_keys=False), encoding="utf-8")
        problems = [str(p) for p in contract.validate_repository(sandbox)]
        assert any("collections_index" in p for p in problems), problems


class TestScaffold:
    def _manifest(self) -> dict:
        manifest = scaffold_mod.example_manifest("lords-shelf")
        manifest["label"] = "Lords Shelf"
        manifest["purpose"] = "Проверочный шаблон контракта: полка, сетка и плашки жанров."
        manifest["layout"]["home_blocks"] = [
            "hero_search", "top_carousel", "latest_grid", "genre_chips"]
        manifest["layout"]["carousel_heading"] = "Свежее"
        return manifest

    def test_the_example_manifest_passes_the_contract(self):
        assert contract.validate_manifest(scaffold_mod.example_manifest()) == []

    def test_a_new_template_lands_in_every_registry(self, sandbox):
        result = scaffold_mod.scaffold(self._manifest(), root=sandbox)
        assert result.ok, [str(p) for p in result.problems]
        touched = {path for path, _ in result.changes}
        assert touched == {
            "blueprints/lords/profiles/lords-shelf.yaml",
            "blueprints/lords/blueprint.yaml",
            "schemas/site-package.schema.json",
        }
        blueprint = yaml.safe_load(
            (sandbox / contract.BLUEPRINT_FILE).read_text(encoding="utf-8"))
        assert "lords-shelf" in blueprint["profiles"]
        package_schema = json.loads(
            (sandbox / "schemas" / contract.PACKAGE_SCHEMA_FILE).read_text(encoding="utf-8"))
        tenant = package_schema["properties"]["tenant"]["properties"]
        assert "lords-shelf" in tenant["seo_profile"]["enum"]

    def test_nothing_outside_the_registries_is_created(self, sandbox):
        before = {p for p in sandbox.rglob("*") if p.is_file()}
        scaffold_mod.scaffold(self._manifest(), root=sandbox)
        after = {p for p in sandbox.rglob("*") if p.is_file()}
        created = {p.relative_to(sandbox).as_posix() for p in after - before}
        # Ни пакета сайта, ни копии ingestion, ни второго рендерера.
        assert created == {"blueprints/lords/profiles/lords-shelf.yaml"}

    def test_the_scaffolded_template_passes_the_contract(self, sandbox):
        scaffold_mod.scaffold(self._manifest(), root=sandbox)
        problems = contract.validate_repository(sandbox)
        assert problems == [], "\n".join(str(p) for p in problems)

    def test_an_invalid_manifest_writes_nothing(self, sandbox):
        manifest = self._manifest()
        manifest["layout"]["home_blocks"] = ["hero_search", "hero_timeline"]
        before = sorted(p.name for p in (sandbox / contract.PROFILE_DIR).glob("*.yaml"))
        result = scaffold_mod.scaffold(manifest, root=sandbox)
        assert not result.ok
        assert result.changes == []
        after = sorted(p.name for p in (sandbox / contract.PROFILE_DIR).glob("*.yaml"))
        assert before == after

    def test_an_existing_template_is_not_overwritten_by_accident(self, sandbox):
        manifest = self._manifest()
        assert scaffold_mod.scaffold(manifest, root=sandbox).ok
        again = scaffold_mod.scaffold(manifest, root=sandbox)
        assert not again.ok
        assert any("--force" in str(p) for p in again.problems)

    def test_a_dry_run_changes_nothing(self, sandbox):
        digest = {p: p.read_bytes() for p in sandbox.rglob("*") if p.is_file()}
        result = scaffold_mod.scaffold(self._manifest(), root=sandbox, dry_run=True)
        assert result.ok and len(result.changes) == 3
        assert {p: p.read_bytes() for p in sandbox.rglob("*") if p.is_file()} == digest


@pytest.fixture(scope="module")
def homes(tmp_path_factory) -> dict[str, str]:
    """Главная каждого шаблона направления, собранная на fixture-каталоге."""
    out = {}
    base = tmp_path_factory.mktemp("templates")
    for path in contract.manifest_paths():
        manifest = contract.load_manifest(path)
        name = manifest["profile"]
        site = fixture_mod.render_fixture_site(manifest, base=base / name)
        out[name] = site.pages["/"].body
    return out


class TestDeclaredBlocksReachTheMarkup:
    """Объявленный блок обязан появиться в разметке, а не только в манифесте."""

    def test_every_declared_block_is_marked_in_the_html(self, homes, manifests):
        missing = []
        for name, html in homes.items():
            for block in manifests[name]["layout"]["home_blocks"]:
                if f'data-block="{block}"' not in html:
                    missing.append(f"{name}: {block}")
        assert missing == [], missing

    def test_the_hero_is_always_marked(self, homes):
        for name, html in homes.items():
            assert 'data-block="hero"' in html, name

    def test_no_block_appears_that_the_manifest_did_not_ask_for(self, homes, manifests):
        import re

        for name, html in homes.items():
            shown = set(re.findall(r'data-block="([a-z_]+)"', html)) - {"hero"}
            declared = set(manifests[name]["layout"]["home_blocks"])
            assert shown <= declared, (name, sorted(shown - declared))

    def test_the_release_gate_would_accept_every_template(self, homes):
        # automation/host/lords-content-refresh.sh:233 — тот же порог, что и на
        # хосте: главная больше 4000 байт и с карточками.
        for name, html in homes.items():
            assert len(html.encode("utf-8")) > contract.RELEASE_GATE_HOME_BYTES, name
            assert contract.RELEASE_GATE_MARKER in html, name
