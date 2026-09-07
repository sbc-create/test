"""REQ-RENDER-CONTRACT: описание отрисовки переживает границу процесса.

Подготовка к отделению рендерера, а не отделение. Ни нового процесса, ни
нового юнита: физическое отделение разрешено только после теневого прогона с
побайтовым сравнением артефактов и отдельного канареечного цикла.

Контракт нужен раньше отделения по простой причине: пока описания нет,
неизвестно даже, что придётся передавать через границу. Сейчас `render_site`
принимает семь разнородных аргументов, три из которых меняют смысл результата
своим отсутствием.

Проверяется то, чем контракт отличается от структуры данных: отказ вместо
догадки при чужой версии, отказ вместо тишины при неизвестном поле, и
устойчивость отпечатка состава — на нём держится всё теневое сравнение.
"""

from __future__ import annotations

import pytest

from factory.contracts import render_contract as рк


def описание(**over):
    основа = {
        "site_id": "lords-03",
        "package_ref": "sites/lords-03/package.yaml",
        "catalog_ref": "var/catalog/lords-03.json",
        "catalog_digest": "a" * 64,
        "template_revision": "41031da02cb7",
    }
    основа.update(over)
    return рк.RenderSpec(**основа)


def манифест(**over):
    основа = {
        "site_id": "lords-03",
        "template_revision": "41031da02cb7",
        "pages_digest": "b" * 64,
        "pages_total": 100,
        "html_total": 90,
        "catalog_digest": "a" * 64,
    }
    основа.update(over)
    return рк.ArtifactManifest(**основа)


class TestОписаниеНеДаётСоврать:
    def test_без_витрины_отвергается(self):
        with pytest.raises(рк.ContractError, match="отрисовывать нечего"):
            описание(site_id="")

    def test_без_ревизии_шаблона_отвергается(self):
        with pytest.raises(рк.ContractError, match="ревизии шаблона"):
            описание(template_revision="")

    def test_снимок_названный_наполовину_отвергается(self):
        with pytest.raises(рк.ContractError, match="наполовину"):
            описание(catalog_digest=None)
        with pytest.raises(рк.ContractError, match="наполовину"):
            описание(catalog_ref=None)

    def test_отсутствие_источника_законно_и_названо_целиком(self):
        """`catalog=None` у рендерера значит «источника нет», а не «пусто»."""
        с = описание(catalog_ref=None, catalog_digest=None)
        assert с.catalog_ref is None and с.catalog_digest is None


class TestГраницаПроцесса:
    def test_описание_переживает_обмен(self):
        с = описание()
        assert рк.RenderSpec.from_dict(с.as_dict()) == с

    def test_чужая_версия_отвергается_а_не_угадывается(self):
        данные = описание().as_dict()
        данные["contract_version"] = "render-contract/2.0.0"
        with pytest.raises(рк.ContractError, match="догадываться"):
            рк.RenderSpec.from_dict(данные)

    def test_неизвестное_поле_отвергается_а_не_проглатывается(self):
        данные = описание().as_dict()
        данные["хитрое_поле"] = 1
        with pytest.raises(рк.ContractError, match="неизвестные поля"):
            рк.RenderSpec.from_dict(данные)

    def test_манифест_переживает_обмен(self):
        м = манифест()
        assert рк.ArtifactManifest.from_dict(м.as_dict()) == м


class TestМанифестНеДаётСоврать:
    def test_документов_не_больше_чем_страниц(self):
        with pytest.raises(рк.ContractError, match="часть больше целого"):
            манифест(html_total=200, pages_total=100)

    def test_без_отпечатка_состава_отвергается(self):
        with pytest.raises(рк.ContractError, match="сравнить теневой прогон"):
            манифест(pages_digest="")

    def test_отрицательный_счёт_отвергается(self):
        with pytest.raises(рк.ContractError, match="отрицательное"):
            манифест(pages_total=-1, html_total=0)


class TestОтпечатокСоставаУстойчив:
    def test_порядок_страниц_не_влияет(self):
        один = рк.отпечаток_состава({"/a": "1", "/b": "2"})
        другой = рк.отпечаток_состава({"/b": "2", "/a": "1"})
        assert один == другой, "отпечаток зависит от порядка обхода словаря"

    def test_повторный_расчёт_даёт_то_же(self):
        страницы = {"/a": "1", "/b": "2"}
        assert рк.отпечаток_состава(страницы) == рк.отпечаток_состава(страницы)

    def test_изменение_содержимого_меняет_отпечаток(self):
        assert (рк.отпечаток_состава({"/a": "1"})
                != рк.отпечаток_состава({"/a": "2"}))

    def test_переименование_страницы_меняет_отпечаток(self):
        assert (рк.отпечаток_состава({"/a": "1"})
                != рк.отпечаток_состава({"/b": "1"}))

    def test_байты_и_строки_считаются_одинаково(self):
        assert (рк.отпечаток_состава({"/a": "текст"})
                == рк.отпечаток_состава({"/a": "текст".encode()}))


class TestСравнениеДляТеневогоПрогона:
    def test_одинаковые_манифесты_не_расходятся(self):
        assert рк.сравнить(манифест(), манифест()) == []

    def test_расхождение_называет_поле_и_обе_стороны(self):
        расхождения = рк.сравнить(манифест(), манифест(pages_total=101))
        assert len(расхождения) == 1
        assert "pages_total" in расхождения[0]
        assert "100" in расхождения[0] and "101" in расхождения[0]

    def test_состояния_типов_сравниваются(self):
        расхождения = рк.сравнить(
            манифест(type_states={"collections": "unsupported_by_source"}),
            манифест(type_states={"collections": "enabled"}))
        assert расхождения and "состояния типов" in расхождения[0]
