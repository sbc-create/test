"""Охват дублей у витрин-сестёр: посылка проверяется, а не принимается.

Измерено 25.10: слой различия по домену в рантайме не даёт ничего, поэтому
страница без размещённого редакционного текста несёт описание соседа
дословно. Отсюда охват считается по хранилищам — но ПОСЫЛКА обязана
проверяться живой выборкой, иначе «8 435 страниц без текста» было бы
утверждением о диске, а не о том, что видит посетитель.

Здесь закреплены три свойства: обе формы хранилища читаются, страница без
ТЕЛА за размещённую не считается, и несовпадение описаний в выборке роняет
вывод, а не прячется.
"""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path

ПУТЬ = (Path(__file__).resolve().parents[2] / "automation" / "local"
        / "sister-duplicate-scope.py")


def _модуль():
    спец = importlib.util.spec_from_file_location("sister_duplicate_scope", ПУТЬ)
    м = importlib.util.module_from_spec(спец)
    спец.loader.exec_module(м)
    return м


МОД = _модуль()


def _хранилище(tmp_path, домен, записи):
    к = tmp_path / "stand" / "runtime" / "overlays" / домен
    к.mkdir(parents=True, exist_ok=True)
    (к / "title-overlays.json").write_text(json.dumps({"items": записи},
                                                      ensure_ascii=False),
                                           encoding="utf-8")


def test_читается_форма_списка(tmp_path, monkeypatch):
    _хранилище(tmp_path, "a.test", [{"slug": "x", "body": "текст"}])
    monkeypatch.setattr(МОД, "НАЛОЖЕНИЯ", tmp_path)
    assert МОД.слаги_наложения("a.test") == {"x"}


def test_читается_форма_словаря(tmp_path, monkeypatch):
    _хранилище(tmp_path, "a.test", {"x": {"slug": "x", "body": "текст"}})
    monkeypatch.setattr(МОД, "НАЛОЖЕНИЯ", tmp_path)
    assert МОД.слаги_наложения("a.test") == {"x"}


def test_запись_без_тела_не_считается_размещённой(tmp_path, monkeypatch):
    """Пустое тело — это не размещённый текст, и путать их нельзя."""
    _хранилище(tmp_path, "a.test", [{"slug": "x", "body": "   "},
                                    {"slug": "y", "body": "есть"}])
    monkeypatch.setattr(МОД, "НАЛОЖЕНИЯ", tmp_path)
    assert МОД.слаги_наложения("a.test") == {"y"}


def test_несовпадение_в_выборке_роняет_вывод(tmp_path, monkeypatch, capsys):
    """Отрицательный контроль: посылка не подтверждается молча."""
    _хранилище(tmp_path, "a.test", [])
    _хранилище(tmp_path, "b.test", [])
    monkeypatch.setattr(МОД, "НАЛОЖЕНИЯ", tmp_path)
    monkeypatch.setattr(МОД, "слаги_карты", lambda д, т=90: (["s1", "s2"], ""))
    monkeypatch.setattr(МОД, "описание",
                        lambda домен, слаг, т=35: (f"описание {домен}", "200"))
    код = МОД.главное(["--domain", "a.test", "--domain", "b.test", "--sample", "2"])
    вывод = capsys.readouterr().out
    assert код == 1
    assert "посылка НЕ подтверждена" in вывод


def test_совпадение_в_выборке_подтверждает_охват(tmp_path, monkeypatch, capsys):
    _хранилище(tmp_path, "a.test", [])
    _хранилище(tmp_path, "b.test", [])
    monkeypatch.setattr(МОД, "НАЛОЖЕНИЯ", tmp_path)
    monkeypatch.setattr(МОД, "слаги_карты", lambda д, т=90: (["s1", "s2"], ""))
    monkeypatch.setattr(МОД, "описание", lambda домен, слаг, т=35: ("одно и то же", "200"))
    код = МОД.главное(["--domain", "a.test", "--domain", "b.test", "--sample", "2"])
    вывод = capsys.readouterr().out
    assert код == 0
    assert "несут описание соседа дословно" in вывод
    assert "2 страниц" in вывод or "2 страницы" in вывод


def test_страница_не_отдалась_не_считается_совпадением(tmp_path, monkeypatch, capsys):
    _хранилище(tmp_path, "a.test", [])
    _хранилище(tmp_path, "b.test", [])
    monkeypatch.setattr(МОД, "НАЛОЖЕНИЯ", tmp_path)
    monkeypatch.setattr(МОД, "слаги_карты", lambda д, т=90: (["s1"], ""))
    monkeypatch.setattr(МОД, "описание", lambda домен, слаг, т=35: ("", "503"))
    код = МОД.главное(["--domain", "a.test", "--domain", "b.test", "--sample", "1"])
    вывод = capsys.readouterr().out
    assert код == 3 and "НЕ ИЗМЕРЕНО" in вывод


def test_одной_витрины_недостаточно(capsys):
    код = МОД.главное(["--domain", "a.test"])
    assert код == 2
    assert "не меньше двух" in capsys.readouterr().err


def test_карта_не_отдалась_это_не_измерено(tmp_path, monkeypatch, capsys):
    _хранилище(tmp_path, "a.test", [])
    _хранилище(tmp_path, "b.test", [])
    monkeypatch.setattr(МОД, "НАЛОЖЕНИЯ", tmp_path)
    monkeypatch.setattr(МОД, "слаги_карты",
                        lambda д, т=90: ([], "карта не отдалась: код 503"))
    код = МОД.главное(["--domain", "a.test", "--domain", "b.test"])
    assert код == 2 and "НЕ ИЗМЕРЕНО" in capsys.readouterr().err


def test_накладка_по_title_id_даёт_отказ_а_не_завышение(tmp_path, monkeypatch, capsys):
    """Семейства Lords и Zona ставят текст накладкой, и слага в ней нет.

    Если читать только наложение, у них «текста нет» выйдет у ВСЕХ работ, и
    охват дублей будет завышен. Поэтому мера отказывается считать, а не
    домысливает сопоставление `title_id` → слаг.
    """
    (tmp_path / "zonafilm12-site" / "data").mkdir(parents=True)
    (tmp_path / "zonafilm12-site" / "data" / "editorial-overrides.json").write_text(
        json.dumps({"overrides": {
            "019151ff-2b5f-7270-80ed-4b2b8a8f5326": {
                "actor": "editor/claude-auto/run-1",
                "fields": {"description": "текст без слага"}},
        }}, ensure_ascii=False), encoding="utf-8")
    monkeypatch.setattr(МОД, "НАКЛАДКИ", tmp_path)
    monkeypatch.setattr(МОД, "НАЛОЖЕНИЯ", tmp_path / "нет")
    код = МОД.главное(["--domain", "zonafilm12.site", "--domain", "zonafilm.cc"])
    assert код == 2
    ошибка = capsys.readouterr().err
    assert "НЕ ИЗМЕРЕНО" in ошибка and "title_id" in ошибка


def test_накладка_со_слагом_читается(tmp_path, monkeypatch):
    (tmp_path / "x-test" / "data").mkdir(parents=True)
    (tmp_path / "x-test" / "data" / "editorial-overrides.json").write_text(
        json.dumps({"overrides": [
            {"slug": "a", "fields": {"description": "есть"}},
            {"slug": "b", "fields": {"description": "  "}},
        ]}, ensure_ascii=False), encoding="utf-8")
    monkeypatch.setattr(МОД, "НАКЛАДКИ", tmp_path)
    monkeypatch.setattr(МОД, "НАЛОЖЕНИЯ", tmp_path / "нет")
    слаги, без_слага = МОД.размещено_накладкой("x.test")
    assert слаги == {"a"} and без_слага == 0
