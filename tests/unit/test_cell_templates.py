"""Пул шаблонов: атомарность, идемпотентность, необратимость назначения.

Проверяется не «функция возвращает словарь», а те три свойства, из-за нарушения
которых два домена однажды получили один профиль.

Доказывает: REQ-CELL-TEMPLATE.
"""
from __future__ import annotations

import json
import multiprocessing
from pathlib import Path

import pytest

from factory.cell import templates
from factory.cell.templates import PoolExhausted, TemplateError


def _pool(path: Path, count: int = 4, family: str = "lords") -> Path:
    path.write_text(json.dumps({
        "schema_version": "1.0",
        "families": {family: {"source_dir": "blueprints", "exclusive": True}},
        "templates": [
            {"template_id": f"{family}-{i:02d}", "family": family,
             "label": f"T{i}", "source": f"blueprints/{family}-{i:02d}.yaml",
             "status": "free", "assignment": None}
            for i in range(count)
        ],
    }, ensure_ascii=False), encoding="utf-8")
    return path


@pytest.fixture()
def pool(tmp_path: Path) -> Path:
    return _pool(tmp_path / "template-pool.json")


def test_reservation_takes_one_template_out_of_the_free_pool(pool: Path):
    before = templates.free_templates(pool)
    r = templates.reserve(order_id="o-1", site_id="s-1", domain="a.test", path=pool)
    after = templates.free_templates(pool)
    assert r.status == "reserved"
    assert r.template_id in before
    assert r.template_id not in after
    assert len(after) == len(before) - 1


def test_repeated_order_returns_the_same_template_and_spends_nothing(pool: Path):
    first = templates.reserve(order_id="o-1", site_id="s-1", domain="a.test", path=pool)
    free_after_first = templates.free_templates(pool)
    second = templates.reserve(order_id="o-1", site_id="s-1", domain="a.test", path=pool)
    assert second.template_id == first.template_id
    assert templates.free_templates(pool) == free_after_first


def test_one_site_never_holds_two_templates(pool: Path):
    templates.reserve(order_id="o-1", site_id="s-1", domain="a.test", path=pool)
    with pytest.raises(TemplateError, match="уже закреплён"):
        templates.reserve(order_id="o-2", site_id="s-1", domain="a.test", path=pool)


def test_assigned_template_leaves_the_pool_but_keeps_its_sources(pool: Path):
    r = templates.reserve(order_id="o-1", site_id="s-1", domain="a.test", path=pool)
    a = templates.assign(order_id="o-1", path=pool)
    assert a.is_assigned
    assert a.template_id == r.template_id
    assert a.template_id not in templates.free_templates(pool)
    entry = next(e for e in json.loads(pool.read_text())["templates"]
                 if e["template_id"] == a.template_id)
    # Назначение — это состояние, а не удаление: источник остаётся на месте.
    assert entry["source"]


def test_assign_is_idempotent(pool: Path):
    templates.reserve(order_id="o-1", site_id="s-1", domain="a.test", path=pool)
    first = templates.assign(order_id="o-1", path=pool)
    second = templates.assign(order_id="o-1", path=pool)
    assert second.template_id == first.template_id
    assert second.assigned_at == first.assigned_at


def test_exhausted_pool_says_so_instead_of_handing_out_a_used_template(pool: Path):
    for i in range(4):
        templates.reserve(order_id=f"o-{i}", site_id=f"s-{i}", domain="a.test", path=pool)
    with pytest.raises(PoolExhausted):
        templates.reserve(order_id="o-x", site_id="s-x", domain="a.test", path=pool)


def test_published_site_does_not_lose_its_template_to_a_release_call(pool: Path):
    templates.reserve(order_id="o-1", site_id="s-1", domain="a.test", path=pool)
    templates.assign(order_id="o-1", path=pool)
    with pytest.raises(TemplateError, match="назначен сайту"):
        templates.release_reservation(order_id="o-1", confirmed_no_pending=True,
                                      reason="уборка", path=pool)


def test_stale_reservation_is_released_only_with_explicit_confirmation(pool: Path):
    templates.reserve(order_id="o-1", site_id="s-1", domain="a.test", path=pool)
    with pytest.raises(TemplateError, match="подтвержд"):
        templates.release_reservation(order_id="o-1", confirmed_no_pending=False,
                                      reason="зависло", path=pool)
    freed = templates.release_reservation(order_id="o-1", confirmed_no_pending=True,
                                          reason="прогон прерван, действий нет", path=pool)
    assert freed.template_id in templates.free_templates(pool)


def _child(args):
    pool_path, order_id, site_id = args
    try:
        r = templates.reserve(order_id=order_id, site_id=site_id, domain="a.test",
                              path=Path(pool_path))
        return r.template_id
    except PoolExhausted:
        return None


def test_parallel_orders_never_receive_the_same_template(tmp_path: Path):
    """Настоящая гонка, а не её имитация.

    Восемь процессов подают восемь заказов на четыре шаблона одновременно.
    Правильный исход: четыре разных шаблона и четыре отказа — но ни одного
    шаблона, выданного дважды.
    """
    pool_path = _pool(tmp_path / "template-pool.json", count=4)
    args = [(str(pool_path), f"o-{i}", f"s-{i}") for i in range(8)]
    ctx = multiprocessing.get_context("fork")
    with ctx.Pool(8) as p:
        results = p.map(_child, args)
    handed_out = [t for t in results if t]
    assert len(handed_out) == 4, results
    assert len(set(handed_out)) == 4, f"один шаблон выдан дважды: {handed_out}"


def test_real_pool_is_only_mutated_through_the_module():
    """Реальный пул отражает действительность пакетов сайтов.

    Если кто-то впишет назначение руками мимо sites/<site_id>/package.yaml,
    расхождение будет видно здесь, а не на живом домене.
    """
    import yaml

    from factory.paths import PATHS

    pool = templates.load()
    for entry in pool["templates"]:
        holder = entry.get("assignment") or {}
        site_id = holder.get("site_id")
        if entry["status"] != "assigned" or not site_id:
            continue
        package = PATHS.site_package(site_id)
        if not package.exists():
            continue
        data = yaml.safe_load(package.read_text(encoding="utf-8"))
        assert (data.get("tenant") or {}).get("seo_profile") == entry["template_id"], (
            f"{site_id}: пул называет шаблон {entry['template_id']}, "
            "а пакет сайта — другой"
        )
