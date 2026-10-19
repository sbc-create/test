"""REQ-CONTENT-RECONCILE: проверенный текст либо на витрине, либо с причиной.

Повод (19.10): в реестре оператора содержания 640 записей `READY_VERIFIED`, и
семь из них не числятся в учёте витрин — шесть на yummyani.site, одна на
yummyani.org. У последней `canonical_url` вообще относительный
(`/anime/ledyanaya-stena-2`), такой адрес не открывается ни доставкой, ни
проверкой.

Закрепляется главное, в чём легко ошибиться:

* ключ сверки — slug из `canonical_url`, а НЕ `title_id`: у animedia в
  `title_id` лежит slug, у yummyani UUID, и сверка по нему даёт ложные
  «172 вне накладки» (ошибка уже сделана и исправлена);
* нет учёта витрины — «не измерено» с причиной, а не «всё на месте»;
* записи с другим статусом в сверку не идут.
"""
from __future__ import annotations

import importlib.util
import json
import pathlib
import types

КОРЕНЬ = pathlib.Path(__file__).resolve().parents[2]
_путь = КОРЕНЬ / "automation/local/content-registry-vs-live.py"
_спец = importlib.util.spec_from_file_location("content_registry_vs_live", _путь)
ИНСТР = importlib.util.module_from_spec(_спец)
_спец.loader.exec_module(ИНСТР)


def _реестр(tmp_path: pathlib.Path, записи: list[dict]) -> pathlib.Path:
    п = tmp_path / "registry.json"
    п.write_text(json.dumps({"items": записи}), encoding="utf-8")
    return п


def _запись(домен: str, slug: str, статус: str = "READY_VERIFIED",
            title_id: str | None = None, адрес: str | None = None) -> dict:
    return {"target_site": домен, "status": статус,
            "title_id": title_id if title_id is not None else f"uuid-{slug}",
            "canonical_url": адрес if адрес is not None else f"https://{домен}/anime/{slug}",
            "body": "текст записи длиной больше шестидесяти знаков, чтобы отрезок был полным"}


def test_slug_берётся_из_canonical_url():
    и = _запись("a.test", "x", title_id="uuid-отличается")
    assert ИНСТР.slug_записи(и) == "x"


def test_относительный_адрес_тоже_даёт_slug():
    и = _запись("a.test", "x", адрес="/anime/ledyanaya-stena-2")
    assert ИНСТР.slug_записи(и) == "ledyanaya-stena-2"


def test_в_сверку_идут_только_проверенные(tmp_path):
    п = _реестр(tmp_path, [
        _запись("a.test", "x"),
        _запись("a.test", "y", статус="BLOCKED_INSUFFICIENT_FACTS"),
        _запись("a.test", "z", статус="ALREADY_LIVE"),
    ])
    по_домену, беда = ИНСТР.из_реестра(п)
    assert беда == ""
    assert [ИНСТР.slug_записи(и) for и in по_домену["a.test"]] == ["x"]


def test_нет_проверенных_не_измерено(tmp_path):
    п = _реестр(tmp_path, [_запись("a.test", "x", статус="DRAFT")])
    по_домену, беда = ИНСТР.из_реестра(п)
    assert по_домену == {} and "READY_VERIFIED" in беда


def test_битый_реестр_не_измерено(tmp_path):
    п = tmp_path / "registry.json"
    п.write_text("не json", encoding="utf-8")
    по_домену, беда = ИНСТР.из_реестра(п)
    assert по_домену == {} and "не прочитан" in беда


def _сайт(adapter: str = "animedia", домен: str = "a.test"):
    return types.SimpleNamespace(domain=домен, adapter=adapter, site_id="c-01")


def test_учёт_приложения_читается(tmp_path, monkeypatch):
    корень = tmp_path / "overlays"
    (корень / "a.test").mkdir(parents=True)
    (корень / "a.test" / "title-overlays.json").write_text(
        json.dumps({"items": [{"slug": "x"}, {"slug": "y"}]}), encoding="utf-8")
    monkeypatch.setattr(ИНСТР.registry, "путь_доставки",
                        lambda s: str(корень / s.domain / "title-overlays.json"))
    monkeypatch.setattr(ИНСТР.registry, "корень_хранилища", lambda a: str(корень))
    слаги, беда = ИНСТР.наш_учёт("a.test", {"a.test": _сайт()})
    assert слаги == {"x", "y"} and беда == ""


def test_учёт_lords_читается_из_published(tmp_path, monkeypatch):
    ячейка = tmp_path / "srv" / "data"
    ячейка.mkdir(parents=True)
    (ячейка / "editorial-overrides.json").write_text('{"overrides":{}}', encoding="utf-8")
    корень = tmp_path / "overlays"
    (корень / "a.test").mkdir(parents=True)
    (корень / "a.test" / "published.json").write_text(
        json.dumps({"items": [{"slug": "c"}]}), encoding="utf-8")
    monkeypatch.setattr(ИНСТР.registry, "путь_доставки",
                        lambda s: str(ячейка / "editorial-overrides.json"))
    monkeypatch.setattr(ИНСТР.registry, "корень_хранилища", lambda a: str(корень))
    слаги, беда = ИНСТР.наш_учёт("a.test", {"a.test": _сайт("lords")})
    assert слаги == {"c"} and беда == ""


def test_нет_учёта_даёт_причину(tmp_path, monkeypatch):
    monkeypatch.setattr(ИНСТР.registry, "путь_доставки",
                        lambda s: str(tmp_path / "нет.json"))
    monkeypatch.setattr(ИНСТР.registry, "корень_хранилища", lambda a: str(tmp_path))
    слаги, беда = ИНСТР.наш_учёт("a.test", {"a.test": _сайт()})
    assert слаги == set() and беда


def test_домена_нет_в_реестре_ячеек():
    слаги, беда = ИНСТР.наш_учёт("нет.test", {})
    assert слаги == set() and "нет в реестре" in беда


def test_main_находит_недостающие(tmp_path, monkeypatch, capsys):
    корень = tmp_path / "overlays"
    (корень / "a.test").mkdir(parents=True)
    (корень / "a.test" / "title-overlays.json").write_text(
        json.dumps({"items": [{"slug": "x"}]}), encoding="utf-8")
    monkeypatch.setattr(ИНСТР.registry, "собрать", lambda **кв: [_сайт()])
    monkeypatch.setattr(ИНСТР.registry, "путь_доставки",
                        lambda s: str(корень / s.domain / "title-overlays.json"))
    monkeypatch.setattr(ИНСТР.registry, "корень_хранилища", lambda a: str(корень))
    п = _реестр(tmp_path, [_запись("a.test", "x"), _запись("a.test", "пропал")])
    код = ИНСТР.main(["--file", str(п)])
    вывод = capsys.readouterr().out
    assert код == 1
    assert "недостающих   1" in вывод and "пропал" in вывод


def test_main_всё_на_месте_код_0(tmp_path, monkeypatch, capsys):
    корень = tmp_path / "overlays"
    (корень / "a.test").mkdir(parents=True)
    (корень / "a.test" / "title-overlays.json").write_text(
        json.dumps({"items": [{"slug": "x"}]}), encoding="utf-8")
    monkeypatch.setattr(ИНСТР.registry, "собрать", lambda **кв: [_сайт()])
    monkeypatch.setattr(ИНСТР.registry, "путь_доставки",
                        lambda s: str(корень / s.domain / "title-overlays.json"))
    monkeypatch.setattr(ИНСТР.registry, "корень_хранилища", lambda a: str(корень))
    п = _реестр(tmp_path, [_запись("a.test", "x")])
    assert ИНСТР.main(["--file", str(п)]) == 0
    assert "недостающих 0" in capsys.readouterr().out


def test_живая_сеть_сверяется(capsys):
    """Отрицательный контроль: на этом хосте инструмент что-то измеряет."""
    код = ИНСТР.main([])
    вывод = capsys.readouterr().out
    assert код in (0, 1), вывод
    assert "проверенных текстов" in вывод
