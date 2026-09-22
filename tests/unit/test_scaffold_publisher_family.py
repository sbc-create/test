"""Генератор нового сайта берёт Publisher ID из единого источника.

Без этого следующий сайт семейства заводится вручную, и ровно в этот момент
проверка семейства бессильна: у профиля просто нет поля `family`, по которому
её можно применить. Дефект выглядел бы как «политика есть, а новый сайт мимо
неё» — и обнаружился бы после выкладки.

Проверяется:

* профиль семейства получает `family` и блок `player` из config/publisher-ids.yaml;
* ручное значение другого семейства генератор не принимает;
* сайт без семейства заводится как прежде — Lords и Yummy не задеты;
* сгенерированный профиль проходит собственный гейт.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from factory.site_engine import gate, publisher_policy as политика
from factory.site_engine.contracts import ContractError
from factory.site_engine.scaffold import scaffold_profile

ROOT = Path(__file__).resolve().parents[2]

ОБЩЕЕ = dict(
    site_type="video-showcase",
    theme="lords-showcase",
    modules=("content-ingestion", "seo"),
    contact_email="ops@example.tld",
    owners={"site-configuration": "ARCHITECT"},
    providers=({"adapter": "cdnvideohub-public-v1", "role": "primary",
                "directions": ["movie"]},),
)


@pytest.fixture(autouse=True)
def _чистый_кэш():
    политика.сбросить_кэш()
    yield
    политика.сбросить_кэш()


def test_новый_animedia_получает_10252():
    п = scaffold_profile(site_id="animedia-03", domain="animedia.example",
                         family="animedia", root=ROOT, **ОБЩЕЕ)
    assert п["family"] == "animedia"
    assert п["player"]["credential_profile"] == "yami"
    assert политика.ожидаемый(п["family"], root=ROOT) == "10252"


def test_новый_zona_получает_10238():
    п = scaffold_profile(site_id="zona-02", domain="zonafilm.cc",
                         family="zona", root=ROOT, **ОБЩЕЕ)
    assert п["family"] == "zona"
    assert п["player"]["credential_profile"] == "lords"
    assert политика.ожидаемый(п["family"], root=ROOT) == "10238"


def test_закреплённый_домен_даёт_семейство_сам():
    """zonafilm.cc закреплён за zona: семейство можно не называть."""
    п = scaffold_profile(site_id="zona-02", domain="zonafilm.cc", root=ROOT, **ОБЩЕЕ)
    assert п["family"] == "zona"


def test_закреплённый_домен_под_чужим_семейством_отвергается():
    with pytest.raises(ContractError) as отказ:
        scaffold_profile(site_id="zona-02", domain="zonafilm.cc",
                         family="animedia", root=ROOT, **ОБЩЕЕ)
    assert "zonafilm.cc" in str(отказ.value)


@pytest.mark.parametrize("чужое", ["10238", "10333", "10331"])
def test_ручное_чужое_значение_отвергается(чужое):
    with pytest.raises(ContractError) as отказ:
        scaffold_profile(site_id="animedia-03", domain="animedia.example",
                         family="animedia", publisher_id=чужое, root=ROOT, **ОБЩЕЕ)
    assert чужое in str(отказ.value)


def test_ручное_своё_значение_принимается():
    п = scaffold_profile(site_id="animedia-03", domain="animedia.example",
                         family="animedia", publisher_id="10252", root=ROOT, **ОБЩЕЕ)
    assert п["player"]["publisher_id"] == "10252"


def test_неизвестное_семейство_отвергается():
    """Выдумывать семейство и его значение генератор не вправе."""
    with pytest.raises(ContractError):
        scaffold_profile(site_id="x-01", domain="x.example",
                         family="выдуманное", root=ROOT, **ОБЩЕЕ)


def test_сайт_без_семейства_заводится_как_прежде():
    """Lords, Yummy и сайты вне семейств политика не касается."""
    п = scaffold_profile(site_id="books-01", domain="books.example", root=ROOT, **ОБЩЕЕ)
    assert "family" not in п
    assert "player" not in п


def test_сгенерированный_профиль_проходит_гейт():
    п = scaffold_profile(site_id="animedia-03", domain="animedia.example",
                         family="animedia", root=ROOT, **ОБЩЕЕ)
    результат = gate.check_profile(п, ROOT)
    assert результат.passed, результат.problems
