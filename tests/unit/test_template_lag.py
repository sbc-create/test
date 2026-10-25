"""Отставание закрепления измеряется, а неизвестное называется неизвестным.

Повод измерен 25.10. Общее исправление доезжает до сайта не правкой файла, а
продвижением версии: проект собирается из шаблона репозитория и закрепляет его
коммит в `pins.lock.json`. Пока закрепление не поднято, сайт живёт на старом
рантайме, и то же исправление делают второй раз руками.

Числа того дня: восемь проектов партии K2 закреплены на `96222882` — 1 549
коммитов назад; живые витрины Lords и Zona — 2 507–2 702 коммита назад; три
витрины закреплены на коммитах, которых в этом репозитории нет; у пяти витрин
Yummy `source_commit` равен `null`.

Главное требование к инструменту: «не знаю» и «ноль» — разные ответы.
Витрина, чьё происхождение не записано, не должна выглядеть свежей.
"""
from __future__ import annotations

import importlib.util
import json
import pathlib
import sys

КОРЕНЬ = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(КОРЕНЬ))
_путь = КОРЕНЬ / "automation/local/template-lag.py"
_спец = importlib.util.spec_from_file_location("template_lag", _путь)
ЛАГ = importlib.util.module_from_spec(_спец)
_спец.loader.exec_module(ЛАГ)


def test_рантайм_берётся_из_генератора() -> None:
    """Два перечня файлов рантайма мерили бы разные вещи."""
    from factory.cell import newsite
    assert ЛАГ.канонический_рантайм() == tuple(newsite.РАНТАЙМ_LORDS)


def test_отставание_своего_коммита_ноль() -> None:
    о = ЛАГ.отставание(ЛАГ._git("rev-parse", "HEAD"))
    assert о["в_репозитории"] is True and о["отставание"] == 0 and not о["почему"]


def test_чужой_коммит_это_не_измерено() -> None:
    о = ЛАГ.отставание("0" * 40)
    assert о["в_репозитории"] is False and о["отставание"] is None
    assert "другого дерева" in о["почему"]


def test_пустое_закрепление_называет_причину() -> None:
    о = ЛАГ.отставание("")
    assert о["отставание"] is None and "не записано" in о["почему"]


def test_закреплённый_коммит_читается_из_трёх_форм() -> None:
    assert ЛАГ.закреплённый_коммит({"pins": {"source_commit": "aaa"}}) == "aaa"
    assert ЛАГ.закреплённый_коммит({"commit": "bbb"}) == "bbb"
    assert ЛАГ.закреплённый_коммит({"pins": {"common_core": "ccc"}}) == "ccc"
    assert ЛАГ.закреплённый_коммит({"pins": {"source_commit": None}}) == ""


def test_замок_находится_и_во_вложенном_каталоге(tmp_path) -> None:
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "pins.lock.json").write_text('{"commit": "ddd"}', encoding="utf-8")
    assert ЛАГ.замок(tmp_path).get("commit") == "ddd"


def test_битый_замок_не_роняет_разбор(tmp_path) -> None:
    (tmp_path / "pins.lock.json").write_text("{не json", encoding="utf-8")
    assert ЛАГ.замок(tmp_path) == {}


def test_расхождения_считаются_по_канону(tmp_path) -> None:
    канон = ЛАГ.ХОСТ / "seo_layer.py"
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "seo_layer.py").write_bytes(канон.read_bytes())
    (tmp_path / "src" / "indexing_mode.py").write_text("# своя правка\n", encoding="utf-8")
    р = ЛАГ.расхождения(tmp_path, ("seo_layer.py", "indexing_mode.py", "lords_sections.py"))
    assert р["совпало"] == ["seo_layer.py"]
    assert р["разошлось"] == ["indexing_mode.py"]
    assert р["нет_файла"] == ["lords_sections.py"]


def test_экземпляры_берут_выпуск_по_ссылке_current(tmp_path) -> None:
    srv = tmp_path / "srv"
    выпуск = srv / "сайт" / "releases" / "abc123"
    выпуск.mkdir(parents=True)
    (srv / "сайт" / "current").symlink_to(выпуск)
    (srv / "без-релизов").mkdir()
    найдено = [(в, и) for в, и, _ in ЛАГ.экземпляры(srv)]
    assert ("витрина", "сайт") in найдено
    assert ("витрина", "без-релизов") not in найдено


def test_свод_не_придумывает_отставания(tmp_path) -> None:
    srv = tmp_path / "srv"
    выпуск = srv / "сайт" / "releases" / "abc123"
    выпуск.mkdir(parents=True)
    (srv / "сайт" / "current").symlink_to(выпуск)
    (выпуск / "pins.lock.json").write_text(
        json.dumps({"pins": {"source_commit": None}}), encoding="utf-8")
    с = ЛАГ.свод(srv)
    строка = next(з for з in с["строки"] if з["имя"] == "сайт")
    assert строка["отставание"] is None and строка["в_репозитории"] is False
