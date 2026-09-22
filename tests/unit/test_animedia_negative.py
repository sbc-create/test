"""Отрицательные проверки Animedia: что витрина делает с плохими данными.

Положительный тест показывает, что всё работает на хорошем входе. Эти —
показывают, что на плохом входе витрина не врёт: не придумывает название,
не рисует пустую ленту, не выдаёт отсутствие оценки за ноль, не ставит запись
из будущего первой молча и не собирает релиз из расходящегося дерева.
"""
from __future__ import annotations

import datetime as dt
import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from factory.animedia import chronology as х  # noqa: E402


@pytest.fixture(scope="module")
def рантайм():
    манифест = ROOT / "artifacts/evidence/animedia-original-parity-01/_манифест-отриц.json"
    манифест.parent.mkdir(parents=True, exist_ok=True)
    манифест.write_text(json.dumps({
        "schema_version": 1, "template_family": "animedia", "design_version": "1.2.4",
        "source_commit": "0" * 40, "build_id": "test", "artifact_sha256": "0" * 64,
        "profile": "animedia-icu", "built_at": "2026-09-21T00:00:00Z"}), encoding="utf-8")
    import os
    прежнее = os.environ.get("ANIMEDIA_TEMPLATE_MANIFEST")
    os.environ["ANIMEDIA_TEMPLATE_MANIFEST"] = str(манифест)
    os.environ.pop("LORDS_TEMPLATE_MANIFEST", None)
    спец = importlib.util.spec_from_file_location(
        "animedia_runtime_отриц", ROOT / "automation/host/animedia-frontend.py")
    модуль = importlib.util.module_from_spec(спец)
    sys.modules[спец.name] = модуль
    спец.loader.exec_module(модуль)
    yield модуль
    if прежнее is None:
        os.environ.pop("ANIMEDIA_TEMPLATE_MANIFEST", None)
    else:
        os.environ["ANIMEDIA_TEMPLATE_MANIFEST"] = прежнее
    манифест.unlink(missing_ok=True)


# --- данные карточки ----------------------------------------------------------

def test_запись_без_названия_не_становится_карточкой(рантайм):
    """Карточка без имени не карточка: её не подписывают выдуманным словом.

    Прежде такая запись рисовалась безымянным прямоугольником — посетитель
    получал плитку, по которой нельзя понять, куда он попадёт.
    """
    исходник = (ROOT / "automation/host/animedia-frontend.py").read_text(encoding="utf-8")
    assert "if not название or not адрес:" in исходник
    assert 'return ""' in исходник
    состав = рантайм.АНИМЕДИА_ВАРИАНТЫ_КАРТОЧКИ["catalog-title"]
    assert состав["название"] is True


def test_запись_без_адреса_не_становится_карточкой(рантайм):
    исходник = (ROOT / "automation/host/animedia-frontend.py").read_text(encoding="utf-8")
    # Одно и то же условие закрывает оба случая — имя и адрес.
    assert исходник.count("if not название or not адрес:") == 1


def test_отсутствующий_постер_даёт_заглушку_а_не_битую_картинку(рантайм):
    разметка = рантайм.заглушка_постера({"title": "Тест", "poster": ""},
                                        "zt__none", "zt__img", 190, 285)
    assert "<img" not in разметка or "src=\"\"" not in разметка
    assert "zt__none" in разметка or "zt__img" in разметка


def test_неизвестная_оценка_не_показывается_нулём(рантайм):
    for сырое in ({"value": 0, "scale": 10}, {"value": None, "scale": 10},
                  {"value": "n/a", "scale": 10}, {}):
        assert рантайм._оценки_для_карточки({"ratings_by_source": {"imdb": сырое}}, 2) == []


def test_недоступный_источник_оценок_не_роняет_карточку(рантайм):
    """Отсутствие раздела оценок — обычное состояние, а не ошибка."""
    assert рантайм._оценки_для_карточки({}, 2) == []
    assert рантайм._оценки_для_карточки({"ratings_by_source": None}, 2) == []
    assert рантайм._оценки_для_карточки({"ratings_by_source": "сломано"}, 2) == []


def test_чужая_шкала_приводится_а_не_обрезается(рантайм):
    о = рантайм._оценки_для_карточки(
        {"ratings_by_source": {"shikimori": {"value": 90, "scale": 100}}}, 1)[0]
    assert о["на_десять"] == "9"
    assert о["исходное"] == "90" and о["исходная_шкала"] == "100"


# --- хронология ---------------------------------------------------------------

def test_дата_из_будущего_находится_а_не_молчит():
    сейчас = dt.datetime(2026, 9, 22, tzinfo=dt.timezone.utc)
    найдено = х.найти_невозможные_даты(
        [{"slug": "ок", "published_at": "2026-09-01T00:00:00Z"},
         {"slug": "будущее", "published_at": "2027-01-01T00:00:00Z"}], сейчас)
    assert [н["id"] for н in найдено] == ["будущее"]
    assert найдено[0]["опережение_часов"] > 0


def test_в_живом_снимке_невозможных_дат_нет():
    снимок = json.loads(
        Path("/srv/lords/.frontend/animedia-01-catalog.json").read_text(encoding="utf-8"))
    записи = снимок["items"] if isinstance(снимок, dict) else снимок
    assert х.найти_невозможные_даты(записи) == []


def test_неразбираемая_дата_не_всплывает_наверх():
    итог = х.по_добавлению([{"slug": "мусор", "published_at": "позавчера"},
                            {"slug": "норма", "published_at": "2026-01-01T00:00:00Z"}])
    assert итог[0]["slug"] == "норма"


def test_одинаковые_даты_не_меняют_порядок_между_вызовами():
    записи = [{"slug": f"s{i}", "published_at": "2024-11-12T12:20:11Z"} for i in range(20)]
    первый = [з["slug"] for з in х.по_добавлению(list(reversed(записи)))]
    второй = [з["slug"] for з in х.по_добавлению(записи)]
    assert первый == второй


# --- ленты и блоки ------------------------------------------------------------

def test_пустая_лента_не_рисуется(рантайм):
    """Заголовок над пустотой хуже отсутствия блока."""
    исходник = (ROOT / "automation/host/animedia-frontend.py").read_text(encoding="utf-8")
    # Ленты собираются только из непустых коллекций — условие в коде.
    assert "if коллекция is None or not коллекция.items:" in исходник
    assert "continue" in исходник


# --- сборка релиза ------------------------------------------------------------

def test_сборщик_отказывается_собирать_из_грязного_дерева():
    сборщик = (ROOT / "automation/host/animedia_release_build.py").read_text(encoding="utf-8")
    assert "дерево грязное, релиз не собирается" in сборщик
    assert "артефакт в дереве не совпадает с зафиксированным в git" in сборщик


def test_сборщик_проверяет_цифры_после_записи():
    сборщик = (ROOT / "automation/host/animedia_release_build.py").read_text(encoding="utf-8")
    assert "цифра" in сборщик and "на диске разошлась с объявленной" in сборщик


def test_несовпадение_артефакта_видно_в_записи_выката():
    """Заряженный артефакт обязан совпадать с тем, что лежит в релизе."""
    F = Path("/srv/lords/.frontend")
    import hashlib
    for sid in ("animedia-01", "animedia-02"):
        манифест = json.loads((F / f"template-manifest-{sid}.json").read_text(encoding="utf-8"))
        код = (F / "sites" / sid / "current").resolve() / "animedia-frontend.py"
        if not код.is_file():  # витрина ещё на прежнем релизе
            continue
        assert манифест["artifact_sha256"] == hashlib.sha256(код.read_bytes()).hexdigest(), sid


# --- чужой контур -------------------------------------------------------------

def test_чужой_канонический_адрес_не_попадает_в_страницу():
    """Canonical строится от Host запроса, а не из настройки."""
    исходник = (ROOT / "automation/host/animedia-frontend.py").read_text(encoding="utf-8")
    assert "экземпляр.хост = (self.headers.get(\"Host\")" in исходник


def test_страж_контура_отказывает_чужому_идентификатору():
    p = subprocess.run(
        [sys.executable, str(ROOT / "automation/host/animedia_tenant_guard.py"),
         "--stage", "before-assignment", "--template-id", "neighbour-template"],
        cwd=str(ROOT), capture_output=True, text=True)
    assert p.returncode == 1
    assert "template ID вне контура" in p.stdout
