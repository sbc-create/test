"""Сборщик ячейки штампует ДВЕ цифры, и каждая закрепляет своё (D207).

`artifact_sha256` — весь рантайм, `code_file_sha256` — исполняемая точка
входа. Прежде сборщик писал в `artifact_sha256` сумму одной точки входа, и
правка соседнего модуля цифру не меняла: измерено 12.10 на живой ячейке, где
такая правка оставила цифру точки входа верной, а артефакт разошёлся.

Главный тест здесь — не «поля заполнены», а что цифра артефакта РЕАГИРУЕТ на
правку соседнего модуля, а цифра точки входа — нет.
"""
from __future__ import annotations

import hashlib
import importlib.util
from pathlib import Path

import pytest

КОРЕНЬ = Path(__file__).resolve().parents[2]
ИСТОЧНИК = КОРЕНЬ / "factory" / "cell" / "site_checks" / "build_release.py"


@pytest.fixture(scope="module")
def м():
    спец = importlib.util.spec_from_file_location("build_release", ИСТОЧНИК)
    модуль = importlib.util.module_from_spec(спец)
    спец.loader.exec_module(модуль)
    return модуль


def ячейка(tmp_path: Path, *, оформление: str = "тема\n") -> Path:
    корень = tmp_path / "ячейка"
    (корень / "src").mkdir(parents=True, exist_ok=True)
    (корень / "src" / "frontend.py").write_text("точка входа\n", encoding="utf-8")
    (корень / "src" / "theme.py").write_text(оформление, encoding="utf-8")
    (корень / "run.py").write_text("пускатель\n", encoding="utf-8")
    return корень


def test_цифра_артефакта_меняется_от_правки_соседнего_модуля(м, tmp_path):
    """То, ради чего определение и сменили."""
    было = м.сумма_рантайма(ячейка(tmp_path, оформление="тема\n"))
    стало = м.сумма_рантайма(ячейка(tmp_path, оформление="тема другая\n"))
    assert было != стало


def test_цифра_точки_входа_от_правки_соседнего_модуля_не_меняется(м, tmp_path):
    """Она закрепляет СВОЙ файл — иначе два имени были бы об одном и том же."""
    первая = ячейка(tmp_path / "a", оформление="тема\n")
    вторая = ячейка(tmp_path / "b", оформление="тема другая\n")
    точка = lambda к: hashlib.sha256(  # noqa: E731
        (к / "src" / "frontend.py").read_bytes()).hexdigest()
    assert точка(первая) == точка(вторая)
    assert м.сумма_рантайма(первая) != м.сумма_рантайма(вторая)


def test_переименование_модуля_меняет_цифру(м, tmp_path):
    """Имя входит в сумму: иначе переименование прошло бы незаметно."""
    корень = ячейка(tmp_path)
    было = м.сумма_рантайма(корень)
    (корень / "src" / "theme.py").rename(корень / "src" / "design.py")
    assert м.сумма_рантайма(корень) != было


def test_пускатель_входит_в_сумму(м, tmp_path):
    корень = ячейка(tmp_path)
    было = м.сумма_рантайма(корень)
    (корень / "run.py").write_text("пускатель другой\n", encoding="utf-8")
    assert м.сумма_рантайма(корень) != было


def test_штамп_заполняет_оба_имени(м, tmp_path, monkeypatch):
    корень = ячейка(tmp_path)
    monkeypatch.setattr(м, "ROOT", корень)
    monkeypatch.setattr(м, "commit_time", lambda commit: "2026-10-12T00:00:00Z")
    cfg = {"site_id": "проба-01", "entrypoint": "frontend.py",
           "deployment": {"release_parent": "/srv/проба/releases",
                          "current_link": "/srv/проба/current"}}
    pins = {"pins": {"source_commit": "a" * 40}}
    готовый = м.штамп({}, cfg, pins, "b" * 40, dirty=False)
    assert готовый["artifact_sha256"] == м.сумма_рантайма(корень)
    assert готовый["code_file_sha256"] == hashlib.sha256(
        (корень / "src" / "frontend.py").read_bytes()).hexdigest()
    assert готовый["artifact_sha256"] != готовый["code_file_sha256"], (
        "две цифры совпали — значит одна из них считается не по своему правилу")


def test_оба_имени_объявлены_полями_выпуска(м):
    """Иначе проверка потребует пустоты в репозитории не от того поля."""
    assert "artifact_sha256" in м.ПОЛЯ_ВЫПУСКА
    assert "code_file_sha256" in м.ПОЛЯ_ВЫПУСКА


def test_проверка_требует_пустоты_обоих_в_репозитории():
    """Заполненное в коммите значение пережило бы свой выпуск.

    Проверка здесь СТРУКТУРНАЯ, и это сказано прямо: `manifest_stamp.py` —
    сценарий, который исполняется только внутри ячейки с её pins, манифестом
    и раскладкой, поэтому целиком он проверяется прогоном по живым
    репозиториям, а не здесь. Задача этого теста узкая: не дать новому имени
    потеряться в перечне полей, которые обязаны быть пусты в коммите.
    """
    источник = (КОРЕНЬ / "factory" / "cell" / "site_checks"
                / "manifest_stamp.py").read_text(encoding="utf-8")
    начало = источник.index("ПУСТЫЕ_В_РЕПО")
    перечень = источник[начало:источник.index(")", начало)]
    assert "artifact_sha256" in перечень, перечень
    assert "code_file_sha256" in перечень, перечень
