"""Доставка содержимого: битый источник, чужие данные и один источник пути.

Три свойства, каждое куплено наблюдением на стенде нового сайта.

**Битый источник не публикуется.** Запись доставки атомарна, поэтому половина
файла у витрины не окажется — но целиком битый ИСТОЧНИК публиковался как есть,
и витрина падала на первом же разборе, потеряв рабочий снимок. Правило
модуля — «устаревшее целое лучше свежей половины» — теперь применяется на шаг
раньше, к источнику.

**Голоса и комментарии не доставляются.** Хранилище сообщества витрина читает
из своего каталога данных, поэтому оно попадает в перечень наравне со снимком.
Доставка затёрла бы его файлом из общего каталога, окажись там однажды файл с
тем же именем, и пользовательские записи не пережили бы такую перезапись.

**Каталог данных берётся из реестра.** Он выводился здесь заново, из домена. У
сегодняшних ячеек оба способа совпадают, и расхождение было невидимым — ровно
до первой ячейки, чьё размещение отличается от соглашения об именах.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from factory.cell import delivery, registry


def _ячейка(tmp_path: Path, *, data_dir: Path | None, site_id: str = "lords-99",
            domain: str = "lords99.example") -> registry.Cell:
    репо = tmp_path / "repo"
    (репо / "config").mkdir(parents=True, exist_ok=True)
    (репо / "config" / "site.json").write_text(json.dumps({
        "site_id": site_id,
        "environment": {
            "LORDS_CATALOG": f"<data>/{site_id}-catalog.json",
            "LORDS_DETAILS": f"<data>/{site_id}-details.json",
            "LORDS_99_COMMUNITY": f"<data>/{site_id}-community.json",
            "LORDS_LEGACY_ROOT": "<data>/site",
        },
    }, ensure_ascii=False), encoding="utf-8")
    return registry.Cell(
        site_id=site_id, domain=domain, aliases=(),
        repo={"kind": "remote", "path": str(репо),
              "remote": f"https://github.com/sbc-create/site-{site_id}"},
        template={}, pins={}, deploy_target={}, publisher={}, data={},
        runtime={"data_dir": str(data_dir) if data_dir else None,
                 "unit": "u.service", "reload": "restart"},
    )


@pytest.fixture()
def стенд(tmp_path, monkeypatch):
    данные = tmp_path / "cell-data"
    данные.mkdir()
    общий = tmp_path / "shared"
    общий.mkdir()
    ячейка = _ячейка(tmp_path, data_dir=данные)
    monkeypatch.setattr(registry, "resolve", lambda *a, **k: ячейка)
    return ячейка, данные, общий


def _снимок(путь: Path, revision: str, записей: int = 2) -> None:
    путь.write_text(json.dumps({
        "revision": revision,
        "items": [{"slug": f"t{i}", "title": f"Т{i}"} for i in range(записей)],
    }, ensure_ascii=False), encoding="utf-8")


# --- каталог данных ---------------------------------------------------------

def test_каталог_данных_берётся_из_реестра(стенд):
    ячейка, данные, _ = стенд
    assert delivery.каталог_данных(ячейка) == данные


def test_без_объявленного_размещения_действует_соглашение(tmp_path, monkeypatch):
    """Запасной путь остаётся: доставка работает и до заполнения реестра."""
    ячейка = _ячейка(tmp_path, data_dir=None)
    # Каталога по соглашению нет — значит ячейка не активирована.
    assert delivery.каталог_данных(ячейка) is None


def test_объявленный_но_отсутствующий_каталог_это_не_активированная_ячейка(tmp_path):
    ячейка = _ячейка(tmp_path, data_dir=tmp_path / "нет-такого")
    assert delivery.каталог_данных(ячейка) is None


# --- битый источник ---------------------------------------------------------

def test_битый_источник_не_публикуется_и_прежний_файл_цел(стенд):
    ячейка, данные, общий = стенд
    _снимок(данные / "lords-99-catalog.json", "rev-1")
    рабочий = (данные / "lords-99-catalog.json").read_bytes()
    (общий / "lords-99-catalog.json").write_bytes(b'{"revision": "rev-2", "items": [')
    _снимок(общий / "lords-99-details.json", "rev-2")

    итог = delivery.доставить("lords-99", общий=общий)

    assert "lords-99-catalog.json" in итог.rejected
    assert "lords-99-catalog.json" not in итог.delivered
    assert итог.ok is False, "доставка с отвергнутым источником не состоялась"
    assert (данные / "lords-99-catalog.json").read_bytes() == рабочий
    # Остальное доставлено: отказ одного файла не отменяет других.
    assert "lords-99-details.json" in итог.delivered


def test_целый_источник_публикуется(стенд):
    ячейка, данные, общий = стенд
    _снимок(данные / "lords-99-catalog.json", "rev-1")
    _снимок(общий / "lords-99-catalog.json", "rev-2", записей=3)

    итог = delivery.доставить("lords-99", общий=общий)

    assert итог.ok is True
    assert "lords-99-catalog.json" in итог.delivered
    внутри = json.loads((данные / "lords-99-catalog.json").read_text(encoding="utf-8"))
    assert внутри["revision"] == "rev-2"


def test_повторная_доставка_ничего_не_переписывает(стенд):
    ячейка, данные, общий = стенд
    _снимок(общий / "lords-99-catalog.json", "rev-2")
    первая = delivery.доставить("lords-99", общий=общий)
    assert "lords-99-catalog.json" in первая.delivered
    вторая = delivery.доставить("lords-99", общий=общий)
    assert вторая.delivered == []
    assert "lords-99-catalog.json" in вторая.unchanged


# --- собственные данные витрины ---------------------------------------------

def test_хранилище_сообщества_не_доставляется(стенд):
    ячейка, данные, общий = стенд
    своё = данные / "lords-99-community.json"
    своё.write_text(json.dumps({"site_id": "lords-99", "titles": {"a": 1}}),
                    encoding="utf-8")
    было = своё.read_bytes()
    # Производитель случайно положил файл с тем же именем.
    (общий / "lords-99-community.json").write_text(
        json.dumps({"site_id": "чужой", "titles": {}}), encoding="utf-8")
    _снимок(общий / "lords-99-catalog.json", "rev-2")

    итог = delivery.доставить("lords-99", общий=общий)

    assert "lords-99-community.json" in итог.site_owned
    assert "lords-99-community.json" not in итог.delivered
    assert своё.read_bytes() == было, "голоса посетителей затёрты доставкой"


def test_перечень_собственных_данных_объявлен_явно():
    """Правило — список, а не догадка по имени в коде доставки."""
    assert delivery.принадлежит_витрине("lords-90-community.json")
    assert not delivery.принадлежит_витрине("lords-90-catalog.json")
    assert not delivery.принадлежит_витрине("lords-90-details.json")


# --- отчёт ------------------------------------------------------------------

def test_отчёт_называет_отвергнутое_и_своё(стенд):
    ячейка, данные, общий = стенд
    (общий / "lords-99-catalog.json").write_bytes("не json".encode())
    словарь = delivery.доставить("lords-99", общий=общий).as_dict()
    assert словарь["rejected"] == ["lords-99-catalog.json"]
    assert словарь["site_owned"] == ["lords-99-community.json"]
    assert словарь["ok"] is False
