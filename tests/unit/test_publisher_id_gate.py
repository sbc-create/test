"""Ворота: чужой Publisher ID не доходит до сборки.

Проверка в операции подключения плеера закрывает запись бокового файла — то
есть последний шаг. Но профиль заводится раньше, и ошибку в нём дешевле поймать
до сборки, чем после выкладки. Здесь проверяется именно это окно:

* профиль семейства с чужим или снятым значением не проходит гейт;
* домен, закреплённый за семейством до выкладки, не заводится под другим;
* один домен принадлежит одному тенанту — второй профиль с тем же доменом
  отвергается, иначе два шаблона начнут спорить за один сайт;
* семейства вне политики (Lords, Yummy) гейт не трогает.

Проверка намеренно не зависит от результата схемы: профиль может не проходить
схему по совершенно другой причине, и терять из-за этого сообщение о чужом
Publisher ID нельзя — именно его читает человек, заводящий сайт.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from factory.site_engine import gate, publisher_policy as политика

ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture(autouse=True)
def _чистый_кэш():
    политика.сбросить_кэш()
    yield
    политика.сбросить_кэш()


def профиль(**правки) -> dict:
    основа = {
        "schema_version": "1.0",
        "site_id": "animedia-03",
        "site_type": "video-showcase",
        "domains": ["animedia.example"],
        "family": "animedia",
        "player": {
            "provider": "cdnvideohub",
            "credential_profile": "yami",
            "publisher_id_ref": "secret://cdnvideohub/yami/publisher-id",
            "source_mode": "provider-id",
        },
    }
    основа.update(правки)
    return основа


# --- чужое и снятое значение до сборки ------------------------------------


def test_чужое_значение_в_профиле_отвергается():
    п = профиль()
    п["player"]["publisher_id"] = "10238"          # значение семейства zona
    проблемы = политика.проблемы_профиля(п, root=ROOT)
    assert проблемы and any("10238" in с for с in проблемы)


@pytest.mark.parametrize("снятый", ["10331", "10332", "10333"])
def test_снятое_значение_в_профиле_отвергается(снятый):
    п = профиль()
    п["player"]["publisher_id"] = снятый
    проблемы = политика.проблемы_профиля(п, root=ROOT)
    assert проблемы and any(снятый in с for с in проблемы)


def test_своё_значение_проходит():
    п = профиль()
    п["player"]["publisher_id"] = "10252"
    assert политика.проблемы_профиля(п, root=ROOT) == []


def test_профиль_без_явного_значения_проходит():
    """Обычный случай: значение приезжает ссылкой, а не числом в git."""
    assert политика.проблемы_профиля(профиль(), root=ROOT) == []


def test_чужая_пара_учётных_данных_отвергается():
    п = профиль()
    п["player"]["credential_profile"] = "lords"    # пара семейства zona/lords
    проблемы = политика.проблемы_профиля(п, root=ROOT)
    assert проблемы and any("credential_profile" in с for с in проблемы)


# --- онбординг ------------------------------------------------------------


def test_закреплённый_домен_под_чужим_семейством_отвергается():
    п = профиль(site_id="zonafilm-cc", domains=["zonafilm.cc"])
    проблемы = политика.проблемы_профиля(п, root=ROOT)
    assert проблемы and any("zonafilm.cc" in с for с in проблемы)


def test_закреплённый_домен_под_своим_семейством_проходит():
    п = профиль(
        site_id="zona-02", domains=["zonafilm.cc"], family="zona",
        player={"provider": "cdnvideohub", "credential_profile": "lords",
                "publisher_id_ref": "secret://cdnvideohub/lords/lords-01/publisher-id",
                "source_mode": "provider-id", "publisher_id": "10238"},
    )
    assert политика.проблемы_профиля(п, root=ROOT) == []


# --- семейства вне политики ------------------------------------------------


@pytest.mark.parametrize("семейство", ["lords", "yummy", None])
def test_семейство_вне_политики_не_трогается(семейство):
    п = профиль(family=семейство)
    п["player"]["publisher_id"] = "10238"
    п["player"]["credential_profile"] = "lords"
    if семейство is None:
        del п["family"]
    assert политика.проблемы_профиля(п, root=ROOT) == []


def test_живые_профили_lords_и_yummy_проходят_политику():
    """Действующие профили не ведомых семейств обязаны проходить без правок."""
    for имя in ("lords-01", "lords-02", "lords-03"):
        п = json.loads((ROOT / "config/site-profiles" / f"{имя}.json").read_text("utf-8"))
        assert политика.проблемы_профиля(п, root=ROOT) == [], имя


def test_живые_профили_animedia_и_zona_проходят_политику():
    for имя in ("animedia-01", "animedia-02", "zona-01"):
        п = json.loads((ROOT / "config/site-profiles" / f"{имя}.json").read_text("utf-8"))
        assert политика.проблемы_профиля(п, root=ROOT) == [], имя


# --- один домен = один тенант ---------------------------------------------


def test_домен_принадлежит_одному_тенанту():
    первый = профиль(site_id="animedia-03", domains=["animedia.example"])
    второй = профиль(site_id="animedia-04", domains=["animedia.example"])
    столкновения = политика.столкновения_доменов([первый, второй])
    assert столкновения and any("animedia.example" in с for с in столкновения)


def test_разные_домены_не_сталкиваются():
    первый = профиль(site_id="animedia-03", domains=["a.example"])
    второй = профиль(site_id="animedia-04", domains=["b.example"])
    assert политика.столкновения_доменов([первый, второй]) == []


def test_живые_профили_не_делят_доменов():
    профили = [json.loads(p.read_text("utf-8"))
               for p in sorted((ROOT / "config/site-profiles").glob("*.json"))]
    assert политика.столкновения_доменов(профили) == []


# --- гейт вызывает политику ------------------------------------------------


def test_гейт_сообщает_о_чужом_значении():
    """Проверка обязана стоять В гейте, а не только существовать рядом."""
    п = профиль()
    п["player"]["publisher_id"] = "10238"
    результат = gate.check_profile(п, ROOT)
    assert not результат.passed
    assert any("10238" in с for с in результат.problems)


def test_гейт_сообщает_о_чужом_значении_даже_при_негодной_схеме():
    """Профиль может не проходить схему по иной причине — сообщение не теряется."""
    п = профиль()
    п["player"]["publisher_id"] = "10333"
    del п["schema_version"]
    результат = gate.check_profile(п, ROOT)
    assert any("10333" in с for с in результат.problems)


# --- каталог без файла политики --------------------------------------------


def test_профиль_без_семейства_проходит_без_файла_политики(tmp_path):
    """Гейт применяют и к каталогам, где политики нет вовсе.

    Ронять его там по причине, не имеющей отношения к профилю, нельзя: сборка
    профиля в тесте и проверка черновика идут именно в таком каталоге.
    """
    п = профиль()
    del п["family"]
    del п["player"]
    assert политика.проблемы_профиля(п, root=tmp_path) == []


def test_профиль_с_семейством_без_файла_политики_не_проходит(tmp_path):
    """Обратное послабление было бы дырой: сверять семейство не с чем."""
    with pytest.raises(политика.PublisherIdОтклонён):
        политика.проблемы_профиля(профиль(), root=tmp_path)


# --- схема знает о family и player -----------------------------------------


def test_схема_допускает_family_и_player():
    """Иначе сгенерированный профиль семейства не прошёл бы собственный гейт."""
    схема = json.loads(
        (ROOT / "schemas/site-engine/site-profile.schema.json").read_text("utf-8"))
    assert "family" in схема["properties"]
    assert "player" in схема["properties"]
    игрок = схема["properties"]["player"]["properties"]
    assert {"provider", "credential_profile", "publisher_id_ref", "source_mode"} <= set(игрок)
