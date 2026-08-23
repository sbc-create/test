"""REQ-IDEMPOTENT: повтор не создаёт дубль."""
import pytest

from factory import build as build_mod
from factory import inventory, validation
from factory.targets import build_target


def test_build_id_is_content_addressed():
    first = build_mod.build("pilot-local")
    second = build_mod.build("pilot-local")
    assert first.build_id == second.build_id
    assert first.output == second.output


def test_build_id_changes_when_package_changes(temp_site):
    site_a = temp_site()
    id_a = build_mod.compute_build_id(site_a, validation.load_package(site_a))
    site_b = temp_site(lambda p: p["brand"].__setitem__("name", "Другой бренд"))
    id_b = build_mod.compute_build_id(site_b, validation.load_package(site_b))
    assert id_a != id_b


def test_build_id_covers_renderer_source():
    """Регрессия: изменившийся рендер обязан менять адрес сборки, иначе деплой
    сочтёт релиз уже применённым и продолжит отдавать старое содержимое."""
    digest = build_mod.factory_source_digest()
    assert len(digest) == 64
    material = build_mod._canonical({"factory_source": digest})
    assert digest in material


@pytest.mark.slow
def test_repeated_deploy_is_noop(pilot_package):
    conf = inventory.target(pilot_package["target_ref"])
    target = build_target(conf, pilot_package)
    built = build_mod.build("pilot-local")
    first = target.deploy(built.output, built.build_id)
    second = target.deploy(built.output, built.build_id)
    assert second.idempotent_noop is True, "повторный деплой того же релиза не меняет содержимое"
    assert first.release_id == second.release_id
    releases = target.releases()
    assert len(releases) == len(set(releases)), "дублей релизов не возникает"
    assert target.current_release() == built.build_id
