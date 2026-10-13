"""Несуществующий путь в `ReadWritePaths` валит юнит целиком — это надо ловить.

Случай измерен и стоил суточного обновления СЕМИ витрин: в `ReadWritePaths`
обработчиков стоял `/srv/animedia-icu/data`, которого на диске не было, и
рядом три таких же пути Yummy. systemd отказывает на подготовке namespace
кодом 226/NAMESPACE — целиком. Снаружи это выглядело как «таймер есть, значит
обновляется», и потому не замечалось.

Здесь закрепляется поведение проверки: что она ловит, что НЕ называет бедой
(префикс `-`, шаблоны `%i`, закрытый правами родитель) и что действующий хост
её проходит.
"""
from __future__ import annotations

import importlib.util
import pathlib

import pytest

КОРЕНЬ = pathlib.Path(__file__).resolve().parents[2]
ИНСТРУМЕНТ = КОРЕНЬ / "automation" / "local" / "check-readwritepaths.py"


def _модуль():
    spec = importlib.util.spec_from_file_location("check_readwritepaths", ИНСТРУМЕНТ)
    м = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(м)
    return м


def _юнит(каталог: pathlib.Path, имя: str, значение: str) -> pathlib.Path:
    п = каталог / имя
    п.write_text("[Unit]\nDescription=проба\n\n[Service]\n"
                 f"ReadWritePaths={значение}\n", encoding="utf-8")
    return п


def test_несуществующий_путь_это_беда(tmp_path):
    м = _модуль()
    _юнит(tmp_path, "проба.service", str(tmp_path / "нет-такого"))
    беды, недоступные, юнитов, путей = м.разобрать(tmp_path)
    assert юнитов == 1 and путей == 1
    assert len(беды) == 1 and "нет-такого" in беды[0], беды
    assert недоступные == []


def test_существующий_путь_не_беда(tmp_path):
    м = _модуль()
    (tmp_path / "данные").mkdir()
    _юнит(tmp_path, "проба.service", str(tmp_path / "данные"))
    беды, _, _, _ = м.разобрать(tmp_path)
    assert беды == []


def test_минус_означает_необязательный_путь(tmp_path):
    """systemd такой путь пропускает намеренно — отказ по нему был бы зря."""
    м = _модуль()
    _юнит(tmp_path, "проба.service", "-" + str(tmp_path / "нет-такого"))
    беды, _, _, путей = м.разобрать(tmp_path)
    assert беды == [] and путей == 1


def test_несколько_путей_в_одной_строке_разбираются(tmp_path):
    м = _модуль()
    (tmp_path / "есть").mkdir()
    _юнит(tmp_path, "проба.service",
          f"{tmp_path / 'есть'} {tmp_path / 'нет-1'} {tmp_path / 'нет-2'}")
    беды, _, _, путей = м.разобрать(tmp_path)
    assert путей == 3
    assert len(беды) == 2, беды


def test_шаблон_не_разрешается_статически(tmp_path):
    """`%i` и `$VAR` подставляет systemd; статически это не путь."""
    м = _модуль()
    _юнит(tmp_path, "шаблон@.service", "/srv/%i/data")
    _юнит(tmp_path, "перем.service", "$STATE_DIRECTORY/data")
    беды, _, _, _ = м.разобрать(tmp_path)
    assert беды == [], беды


def test_закрытый_правами_родитель_это_не_отсутствие(tmp_path, monkeypatch):
    """«Не дали посмотреть» и «нет» — разные вещи; склейка прячет настоящее."""
    м = _модуль()
    _юнит(tmp_path, "проба.service", "/etc/закрыто/данные")

    настоящий = pathlib.Path.exists

    def подмена(self):
        if str(self) == "/etc/закрыто/данные":
            raise PermissionError(13, "Permission denied")
        return настоящий(self)

    monkeypatch.setattr(pathlib.Path, "exists", подмена)
    беды, недоступные, _, _ = м.разобрать(tmp_path)
    assert беды == []
    assert len(недоступные) == 1 and "закрыто" in недоступные[0]


def test_код_возврата_1_только_при_настоящих_бедах(tmp_path, monkeypatch, capsys):
    м = _модуль()
    _юнит(tmp_path, "проба.service", str(tmp_path / "нет-такого"))
    monkeypatch.setattr("sys.argv", ["c", "--units", str(tmp_path)])
    assert м.main() == 1
    assert "226/NAMESPACE" in capsys.readouterr().out

    (tmp_path / "данные").mkdir()
    _юнит(tmp_path, "проба.service", str(tmp_path / "данные"))
    assert м.main() == 0
    assert "все обязательные пути существуют" in capsys.readouterr().out


@pytest.mark.skipif(not pathlib.Path("/etc/systemd/system").is_dir(),
                    reason="каталога юнитов на этой машине нет")
def test_действующий_хост_проходит():
    """Измерение, а не украшение: на хосте 87 юнитов и 122 пути."""
    м = _модуль()
    беды, _, юнитов, путей = м.разобрать(pathlib.Path("/etc/systemd/system"))
    assert беды == [], "\n".join(беды)
    assert юнитов >= 50 and путей >= 100, (юнитов, путей)


@pytest.mark.skipif(not pathlib.Path("/etc/systemd/system/animedia-icu-update.service").is_file(),
                    reason="юнита обновления animedia.icu на этой машине нет")
def test_каталог_данных_animedia_icu_существует_для_обработчика():
    """Именно та пара, из-за которой семь витрин не обновлялись."""
    м = _модуль()
    for имя in ("animedia-icu-update.service", "nova-animedia-icu.service"):
        п = pathlib.Path("/etc/systemd/system") / имя
        if not п.is_file():
            continue
        пути = м.пути_юнита(п.read_text(encoding="utf-8", errors="replace"))
        assert пути, f"{имя}: ReadWritePaths не объявлен"
        for путь in пути:
            чистый = путь.lstrip("-")
            assert pathlib.Path(чистый).exists(), f"{имя}: {чистый} нет на диске"
