"""Реестр ячеек: задача попадает в нужный проект или никуда.

Доказывает: REQ-CELL-ROUTING, REQ-CELL-PUBID.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from factory.cell import registry
from factory.cell.registry import (
    AmbiguousCell,
    Cell,
    RegistryError,
    RetiredPublisherId,
    UnknownCell,
)


def _cell(site_id: str, domain: str, **kw) -> Cell:
    base = {
        "site_id": site_id, "domain": domain, "aliases": (),
        "repo": {"kind": "local", "path": f"var/site-repos/{site_id}"},
        "template": {"template_id": "lords-general", "order_id": "o-1"},
        "pins": {"common_core": "abc123", "template": "1.0"},
        "deploy_target": {"ref": "local-disposable", "server": None},
        "publisher": {"provider": "cdnvideohub", "publisher_id_ref": "secret://x"},
        "data": {"database": "data/site.sqlite3"},
    }
    base.update(kw)
    return Cell(**base)


@pytest.fixture()
def reg(tmp_path: Path) -> Path:
    return tmp_path / "site-cells.json"


def test_resolves_by_site_id_and_by_domain(reg: Path):
    registry.register(_cell("alpha", "alpha.test"), path=reg)
    assert registry.resolve("alpha", path=reg).site_id == "alpha"
    assert registry.resolve("alpha.test", path=reg).site_id == "alpha"


def test_alias_resolves_to_the_same_cell(reg: Path):
    registry.register(_cell("alpha", "alpha.test", aliases=("www.alpha.test",)), path=reg)
    assert registry.resolve("www.alpha.test", path=reg).site_id == "alpha"


def test_unknown_name_is_refused_and_never_guessed(reg: Path):
    registry.register(_cell("animedia-01", "animedia.icu"), path=reg)
    registry.register(_cell("animedia-02", "animedia.space"), path=reg)
    with pytest.raises(UnknownCell) as exc:
        registry.resolve("animedia", path=reg)
    # Похожие названы, но выбор не сделан: угадывать сайт нельзя.
    assert "animedia-01" in str(exc.value)
    assert "animedia-02" in str(exc.value)


def test_ambiguity_stops_instead_of_picking_the_first(reg: Path, tmp_path: Path):
    import json
    reg.write_text(json.dumps({"schema_version": "1.0", "cells": [
        _cell("one", "shared.test").to_dict(),
        _cell("two", "other.test", aliases=("shared.test",)).to_dict(),
    ]}, ensure_ascii=False), encoding="utf-8")
    with pytest.raises(AmbiguousCell):
        registry.resolve("shared.test", path=reg)


def test_one_domain_belongs_to_exactly_one_cell(reg: Path):
    registry.register(_cell("alpha", "alpha.test"), path=reg)
    with pytest.raises(RegistryError, match="один домен — один сайт"):
        registry.register(_cell("beta", "alpha.test"), path=reg)


def test_alias_cannot_steal_another_cells_domain(reg: Path):
    registry.register(_cell("alpha", "alpha.test"), path=reg)
    with pytest.raises(RegistryError, match="один домен — один сайт"):
        registry.register(_cell("beta", "beta.test", aliases=("alpha.test",)), path=reg)


def test_re_registering_requires_explicit_replace(reg: Path):
    registry.register(_cell("alpha", "alpha.test"), path=reg)
    with pytest.raises(RegistryError, match="уже зарегистрирована"):
        registry.register(_cell("alpha", "alpha.test"), path=reg)
    registry.register(_cell("alpha", "alpha.test"), path=reg, replace=True)


@pytest.mark.parametrize("retired", ["10331", "10333"])
def test_retired_publisher_id_is_refused(reg: Path, retired: str):
    with pytest.raises(RetiredPublisherId):
        registry.register(
            _cell("alpha", "alpha.test",
                  publisher={"provider": "cdnvideohub", "publisher_id": retired}),
            path=reg)


def test_retired_set_shrinks_only_by_a_named_decision():
    """Набор отозванных сокращается решением владельца, а не ради выпуска.

    Проверка существует потому, что соблазн конкретный: 2026-10-01 владелец
    назначил animedia.icu идентификатор 10332, который до того состоял в
    запрете. Короткий путь — удалить проверку или добавить обход; правильный —
    назвать изменение и зафиксировать его состав.

    Снаружи отличить работающий идентификатор от несуществующего нечем:
    плейлист провайдера отвечает HTTP 200 и на 10332, и на выдуманный 99999, а
    список дорожек от издателя не зависит вовсе. Значит единственное основание
    исключить значение из запрета — указание владельца, и оно обязано быть
    записанным. Отсюда и форма проверки: не «набор непустой», а «набор ровно
    такой, и 10332 исключён осознанно».
    """
    assert registry.RETIRED_PUBLISHER_IDS == frozenset({"10331", "10333"}), (
        "состав отозванных изменился без решения: 10331 и 10333 отвергаются, "
        "10332 исключён решением D120 от 2026-10-01 (animedia.icu). Любое "
        "другое изменение набора — отдельное решение с записью в DECISIONS.md")
    assert "10332" not in registry.RETIRED_PUBLISHER_IDS


def test_owner_assigned_publisher_id_registers(reg: Path):
    """10332 регистрируется: домен назначен владельцем, а не подобран."""
    cell = _cell("alpha", "alpha.test",
                 publisher={"provider": "cdnvideohub", "publisher_id": "10332"})
    registry.register(cell, path=reg)
    assert registry.resolve("alpha", path=reg).publisher["publisher_id"] == "10332"


@pytest.mark.parametrize("allowed", ["10252", "10238", "10373", "10375",
                                     "10377", "10378"])
def test_named_publisher_ids_pass(reg: Path, allowed: str):
    cell = _cell("alpha", "alpha.test",
                 publisher={"provider": "cdnvideohub", "publisher_id": allowed})
    registry.register(cell, path=reg)
    assert registry.resolve("alpha", path=reg).publisher["publisher_id"] == allowed


def test_empty_publisher_id_is_blocked_not_defaulted():
    with pytest.raises(RegistryError, match="подставлять значение"):
        registry.check_publisher_id("")


def test_route_gives_the_executor_exactly_the_destination(reg: Path):
    registry.register(_cell("alpha", "alpha.test"), path=reg)
    r = registry.route("alpha.test", path=reg)
    assert r["site_id"] == "alpha"
    assert r["repo"] == "var/site-repos/alpha"
    assert r["template_id"] == "lords-general"
    assert r["deploy_target"] == "local-disposable"


def test_update_touches_only_named_fields(reg: Path):
    registry.register(_cell("alpha", "alpha.test"), path=reg)
    updated = registry.update("alpha", {"deployed": {"release_digest": "sha256:aa"}}, path=reg)
    assert updated.deployed["release_digest"] == "sha256:aa"
    assert updated.template["template_id"] == "lords-general"
    with pytest.raises(RegistryError, match="не обновляются"):
        registry.update("alpha", {"site_id": "beta"}, path=reg)


def test_update_of_missing_cell_is_an_error_not_a_create(reg: Path):
    with pytest.raises(UnknownCell):
        registry.update("ghost", {"status": "live"}, path=reg)


def test_порты_ячеек_не_пересекаются():
    """Порт витрины и порт её кандидата обязаны быть уникальны по всему реестру.

    Кандидат поднимается на порту+1000; совпадение с чужим основным портом
    означает, что прогрев нового выпуска занимает порт соседнего сайта.
    """
    import json as _json
    from pathlib import Path as _Path

    корень = _Path(__file__).resolve().parents[2]
    ячейки = _json.loads((корень / "config" / "site-cells.json").read_text(encoding="utf-8"))["cells"]
    занято: dict[int, str] = {}
    for c in ячейки:
        порт = (c.get("runtime") or {}).get("port")
        if not порт:
            continue
        for п, роль in ((int(порт), "основной"), (int(порт) + 1000, "кандидат")):
            прежний = занято.get(п)
            assert прежний is None, (
                f"порт {п} ({роль} у {c['site_id']}) уже занят {прежний}")
            занято[п] = f"{c['site_id']}/{роль}"


def test_незапущенные_домены_называют_недостающие_входы():
    """Пустое поле обязано быть объяснено, иначе его не отличить от забытого.

    У записи со status=planned и пустым template_id или publisher_id в note
    должно быть сказано, чего именно не хватает и от кого это вход.
    """
    import json as _json
    from pathlib import Path as _Path

    корень = _Path(__file__).resolve().parents[2]
    ячейки = _json.loads((корень / "config" / "site-cells.json").read_text(encoding="utf-8"))["cells"]
    for c in ячейки:
        if c.get("status") != "planned":
            continue
        for блок, поле in (("template", "template_id"), ("publisher", "publisher_id")):
            раздел = c.get(блок) or {}
            if раздел.get(поле):
                continue
            # Пустое значение объясняется одним из двух способов, и это разные
            # состояния, а не одно с разной формулировкой:
            #
            #  * рядом стоит ссылка на секрет (`<поле>_ref`) — значение НЕ
            #    хранится в реестре по построению, вход владельца не нужен, и
            #    требовать слова «владелец» значило бы требовать неправду;
            #  * ссылки нет — значение действительно ждут, и от кого, обязано
            #    быть сказано.
            #
            # Первый случай появился, когда семейство Lords перешло на
            # publisher_id_ref: пять доменов делят один идентификатор в Secret
            # Hub, и подстановка числа в реестр была бы копией секрета.
            ссылка = раздел.get(f"{поле}_ref")
            примечание = (раздел.get("note") or "").lower()
            if ссылка:
                assert str(ссылка).startswith("secret://"), (
                    f"{c['site_id']}: {блок}.{поле}_ref не ссылка на секрет: {ссылка!r}")
                continue
            assert примечание, f"{c['site_id']}: {блок}.{поле} пусто и не объяснено"
            assert "вход владельца" in примечание or "владельц" in примечание, (
                f"{c['site_id']}: {блок}.{поле} пусто, ссылки на секрет нет, "
                "и не сказано, чей это вход")
