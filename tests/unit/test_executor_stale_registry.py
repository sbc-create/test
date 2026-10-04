"""Устаревший реестр у исполнителя — отдельная причина, а не «нет разрешения».

Случай измерен 2026-10-04 и стоил целой операции. Владелец выдал разрешение на
открытие домена в 08:32:42 — запись легла в авторитетный реестр
`/home/claude/wt-portable-site-cell-01/config/site-cells.json`. Инструмент и
предпроверка читали именно его и отвечали «разрешено». Исполнитель читал СВОЮ
копию, снятую установкой пакета в 07:10:34, и отказал словами
«indexing.open_authorized не равно true». Один и тот же путь внутри пакета
указывал на два разных файла.

Исправлено в двух местах доставки (ссылка вместо копии в
`install-cell-executor.sh` и `SITE_CELLS_REGISTRY` в юните исполнителя), но
этого мало: такой отказ обязан НАЗЫВАТЬ себя. Подтверждение владельца лежит в
каталоге root и устареть не может — если оно есть, а прочитанный реестр его не
знает, дело не в разрешении.
"""
from __future__ import annotations

import json
import pathlib

import pytest

from factory.cell import executor, owner_consent


class _Ячейка:
    """Минимальный паспорт сайта: исполнителю здесь нужен только indexing."""

    def __init__(self, indexing: dict):
        self.site_id = "lords-05"
        self.domain = "lordserials22.info"
        self.indexing = indexing


def _подтверждение(каталог: pathlib.Path, ид: str) -> pathlib.Path:
    каталог.mkdir(parents=True, exist_ok=True)
    п = каталог / "lordserials22.info.json"
    п.write_text(json.dumps({
        "schema_version": 1, "domain": "lordserials22.info",
        "site_id": "lords-05", "authorized": True, "by": "owner",
        "at": "2026-10-04T08:32:42Z", "id": ид}, ensure_ascii=False),
        encoding="utf-8")
    return п


@pytest.fixture()
def согласие(tmp_path, monkeypatch):
    каталог = tmp_path / "owner-consent"
    monkeypatch.setattr(owner_consent, "КОРЕНЬ", каталог)
    # Проверка владельца файла закреплена отдельно (test_owner_consent);
    # здесь интересна логика исполнителя.
    monkeypatch.setattr(owner_consent, "_права", lambda путь: (True, ""))
    return каталог


def _проверить_разрешение(cell) -> None:
    """Тот же участок исполнителя, что решает про открытие слоя."""
    домен = cell.domain
    подтверждение, почему_подтв, запись_подтв = owner_consent.проверить(
        cell.site_id, домен)
    объявлено = (cell.indexing or {}).get("open_authorized")
    ид_реестра = str((cell.indexing or {}).get("open_authorization_id") or "")
    ид_подтв = str((запись_подтв or {}).get("id") or "")
    if подтверждение and (объявлено is not True
                          or (ид_подтв and ид_реестра != ид_подтв)):
        raise executor.ExecutorError(
            f"{cell.site_id}: подтверждение владельца ЕСТЬ ({ид_подтв}), а "
            f"прочитанный реестр его не знает: open_authorized = {объявлено!r}, "
            f"open_authorization_id = {ид_реестра or 'нет'}. Это устаревший "
            "снимок реестра, а не отсутствие разрешения")
    if объявлено is not True:
        raise executor.ExecutorError(
            f"{cell.site_id}: открытие слоя nginx запрещено — в реестре ячеек "
            "indexing.open_authorized не равно true")
    if not подтверждение:
        raise executor.ExecutorError(
            f"{cell.site_id}: подтверждения владельца нет: {почему_подтв}")


def test_устаревший_реестр_называет_себя(согласие):
    """Подтверждение есть, реестр о нём не знает — это снимок, а не отказ."""
    _подтверждение(согласие, "7eb319e0-2a7d-4647-a432-9dfa6d47326a")
    with pytest.raises(executor.ExecutorError) as ош:
        _проверить_разрешение(_Ячейка({"desired_state": "CLOSED"}))
    текст = str(ош.value)
    assert "устаревший снимок реестра" in текст, текст
    assert "7eb319e0" in текст, "в причине нет идентификатора подтверждения"
    assert "не отсутствие разрешения" in текст


def test_несовпадение_идентификаторов_тоже_снимок(согласие):
    """Реестр разрешает, но называет ДРУГОЕ подтверждение."""
    _подтверждение(согласие, "new-id-0001")
    with pytest.raises(executor.ExecutorError) as ош:
        _проверить_разрешение(_Ячейка({
            "open_authorized": True, "open_authorization_id": "old-id-0000"}))
    assert "устаревший снимок" in str(ош.value)


def test_совпадение_пропускает(согласие):
    ид = "7eb319e0-2a7d-4647-a432-9dfa6d47326a"
    _подтверждение(согласие, ид)
    _проверить_разрешение(_Ячейка({
        "open_authorized": True, "open_authorization_id": ид}))


def test_без_подтверждения_прежний_отказ_остаётся(согласие):
    """Флаг без подтверждения — по-прежнему не разрешение."""
    with pytest.raises(executor.ExecutorError) as ош:
        _проверить_разрешение(_Ячейка({"open_authorized": True}))
    assert "подтверждения владельца нет" in str(ош.value)


def test_доставка_больше_не_копирует_реестр():
    """Установщик делает ссылку, а юнит называет авторитетный путь."""
    корень = pathlib.Path(__file__).resolve().parents[2]
    установщик = (корень / "automation" / "host"
                  / "install-cell-executor.sh").read_text(encoding="utf-8")
    assert 'ln -s "$SRC_ROOT/config/site-cells.json"' in установщик, (
        "установщик по-прежнему оставляет копию реестра")
    юнит = (корень / "automation" / "host"
            / "site-cell-executor.service").read_text(encoding="utf-8")
    assert "SITE_CELLS_REGISTRY=" in юнит, "в юните нет авторитетного пути реестра"
    assert "config/site-cells.json" in юнит
