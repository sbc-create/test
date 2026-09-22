"""Операция подключения плеера сверяет семейство, а не только пригодность.

Проверяется, что сверка стоит В ОПЕРАЦИИ, а не только существует рядом с ней.
Модуль политики может быть исправен и полностью покрыт тестами, оставаясь
невызванным: ровно так дефект и выглядел бы — пара профиля прочитана, значение
числовое, боковой файл записан, витрина отвечает 200 и показывает чужой каталог.

Секреты здесь не читаются: пара профиля подменяется файлом во временном
каталоге, и наружу не уходит ни одно действующее значение.
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
СКРИПТ = ROOT / "automation" / "host" / "nova-player-configure.py"


@pytest.fixture
def операция(tmp_path, monkeypatch):
    """Загружает операцию, указав ей корень временной копии репозитория."""
    копия = tmp_path / "repo"
    (копия / "config" / "site-profiles").mkdir(parents=True)
    (копия / "factory").symlink_to(ROOT / "factory")
    (копия / "config" / "publisher-ids.yaml").write_text(
        (ROOT / "config" / "publisher-ids.yaml").read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    monkeypatch.setenv("NOVA_REPO_ROOT", str(копия))

    имя = "nova_player_configure_под_тестом"
    spec = importlib.util.spec_from_file_location(имя, СКРИПТ)
    модуль = importlib.util.module_from_spec(spec)
    sys.modules[имя] = модуль
    spec.loader.exec_module(модуль)
    модуль.публикация.сбросить_кэш()
    yield модуль, копия
    sys.modules.pop(имя, None)
    модуль.публикация.сбросить_кэш()


def витрина(копия: Path, site_id: str, family: str | None) -> None:
    профиль: dict = {"schema_version": "1.0", "site_id": site_id}
    if family is not None:
        профиль["family"] = family
    (копия / "config" / "site-profiles" / f"{site_id}.json").write_text(
        json.dumps(профиль, ensure_ascii=False), encoding="utf-8"
    )


def пара(tmp_path: Path, значение: str) -> str:
    файл = tmp_path / "пара-профиля"
    файл.write_text(значение + "\n", encoding="utf-8")
    return str(файл)


def цель(модуль, site_id: str, профиль: str):
    return модуль.Цель(site_id, "example.invalid", f"{site_id}.service", профиль, site_id)


def подставить_пару(модуль, монkeypatch_, путь: str, профиль: str) -> None:
    монkeypatch_.setitem(модуль.ПРОФИЛИ, профиль, путь)


def test_чужая_пара_у_animedia_отвергается(операция, tmp_path, monkeypatch):
    """Витрине Animedia досталась пара семейства Zona — операция обязана встать."""
    модуль, копия = операция
    витрина(копия, "animedia-01", "animedia")
    подставить_пару(модуль, monkeypatch, пара(tmp_path, "10238"), "yami")
    with pytest.raises(модуль.публикация.PublisherIdОтклонён):
        модуль.издатель(цель(модуль, "animedia-01", "yami"))


def test_чужая_пара_у_zona_отвергается(операция, tmp_path, monkeypatch):
    модуль, копия = операция
    витрина(копия, "zona-01", "zona")
    подставить_пару(модуль, monkeypatch, пара(tmp_path, "10252"), "lords")
    with pytest.raises(модуль.публикация.PublisherIdОтклонён):
        модуль.издатель(цель(модуль, "zona-01", "lords"))


@pytest.mark.parametrize("снятый", ["10331", "10332", "10333"])
def test_снятая_пара_отвергается(операция, tmp_path, monkeypatch, снятый):
    модуль, копия = операция
    витрина(копия, "animedia-02", "animedia")
    подставить_пару(модуль, monkeypatch, пара(tmp_path, снятый), "yami")
    with pytest.raises(модуль.публикация.PublisherIdОтклонён):
        модуль.издатель(цель(модуль, "animedia-02", "yami"))


def test_своя_пара_проходит(операция, tmp_path, monkeypatch):
    модуль, копия = операция
    витрина(копия, "animedia-01", "animedia")
    подставить_пару(модуль, monkeypatch, пара(tmp_path, "10252"), "yami")
    assert модуль.издатель(цель(модуль, "animedia-01", "yami")) == "10252"

    витрина(копия, "zona-01", "zona")
    подставить_пару(модуль, monkeypatch, пара(tmp_path, "10238"), "lords")
    assert модуль.издатель(цель(модуль, "zona-01", "lords")) == "10238"


def test_lords_проходит_прежним_поведением(операция, tmp_path, monkeypatch):
    """Витрины вне ведомых семейств операция не трогает: поведение прежнее."""
    модуль, копия = операция
    витрина(копия, "lords-01", None)
    подставить_пару(модуль, monkeypatch, пара(tmp_path, "10238"), "lords")
    assert модуль.издатель(цель(модуль, "lords-01", "lords")) == "10238"


def test_yummy_проходит_прежним_поведением(операция, tmp_path, monkeypatch):
    модуль, копия = операция
    витрина(копия, "yummyani-site", "yummy")
    подставить_пару(модуль, monkeypatch, пара(tmp_path, "10999"), "yami")
    assert модуль.издатель(цель(модуль, "yummyani-site", "yami")) == "10999"


def test_непригодная_пара_по_прежнему_останавливает(операция, tmp_path, monkeypatch):
    """Прежняя проверка не потеряна: нечисловое значение — по-прежнему SystemExit."""
    модуль, копия = операция
    витрина(копия, "animedia-01", "animedia")
    подставить_пару(модуль, monkeypatch, пара(tmp_path, "не-число"), "yami")
    with pytest.raises(SystemExit):
        модуль.издатель(цель(модуль, "animedia-01", "yami"))


@pytest.mark.parametrize(
    "site_id, family, чужое",
    [
        ("animedia-03", "animedia", "10238"),   # значение семейства zona
        ("animedia-03", "animedia", "10333"),   # снятое
        ("zona-02", "zona", "10252"),           # значение семейства animedia
        ("zona-02", "zona", "10331"),           # снятое
    ],
)
def test_новая_витрина_семейства_не_получает_чужого(
    операция, tmp_path, monkeypatch, site_id, family, чужое
):
    """Требование относится не только к шести существующим витринам.

    Витрины с такими идентификаторами ещё нет: проверка обязана сработать на
    профиле семейства как таковом, иначе следующий сайт семейства заведут мимо
    неё — ровно в тот момент, когда сверять уже некому.
    """
    модуль, копия = операция
    витрина(копия, site_id, family)
    профиль = "yami" if family == "animedia" else "lords"
    подставить_пару(модуль, monkeypatch, пара(tmp_path, чужое), профиль)
    with pytest.raises(модуль.публикация.PublisherIdОтклонён):
        модуль.издатель(цель(модуль, site_id, профиль))


@pytest.mark.parametrize(
    "site_id, family, своё", [("animedia-03", "animedia", "10252"), ("zona-02", "zona", "10238")]
)
def test_новая_витрина_семейства_получает_своё(
    операция, tmp_path, monkeypatch, site_id, family, своё
):
    модуль, копия = операция
    витрина(копия, site_id, family)
    профиль = "yami" if family == "animedia" else "lords"
    подставить_пару(модуль, monkeypatch, пара(tmp_path, своё), профиль)
    assert модуль.издатель(цель(модуль, site_id, профиль)) == своё


def test_шесть_целей_остались_закрытым_перечнем(операция):
    """Область операции не расширена: zonafilm.cc сюда не добавлен."""
    модуль, _ = операция
    assert set(модуль.ЦЕЛИ) == {
        "lords-01", "lords-02", "lords-03", "zona-01", "animedia-01", "animedia-02",
    }
