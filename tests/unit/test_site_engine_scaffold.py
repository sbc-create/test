"""Создание сайта нового рода: профиль собирается, а не копируется.

Проверяется не форма словаря, а то, что собранный профиль проходит настоящие
ворота — иначе «сайт создаётся из составляющих» остаётся утверждением.
"""
import json
from pathlib import Path

import pytest

from factory.site_engine import gate
from factory.site_engine.contracts import ContractError
from factory.site_engine.profiles import profile_from_dict
from factory.site_engine.scaffold import BASE_MODULES, scaffold_profile

ROOT = Path(__file__).resolve().parents[2]

ОБЩЕЕ = {
    "contact_email": "sbc.claude@yandex.ru",
    "owners": {"seo": "site-factory/seo", "renderer-adapters": "site-factory/platform"},
}


def потребитель_общего_api(**kw):
    """Витрина без своего загрузчика: контент приходит из общего API."""
    return scaffold_profile(
        site_id=kw.pop("site_id", "demo-recipes"),
        site_type=kw.pop("site_type", "recipe-catalog"),
        domain=kw.pop("domain", "demo-recipes.invalid"),
        theme="demo-warm",
        modules=("content-catalog", "homepage-shelves", "seo"),
        normalized_content_source={"kind": "site-engine-api", "ref": "site-engine/v1"},
        **ОБЩЕЕ,
        **kw,
    )


class TestСобранныйПрофиль:
    def test_проходит_настоящие_ворота(self, tmp_path: Path):
        """Ворота те же, что у шести действующих сайтов, а не облегчённые."""
        каталог = tmp_path / "config" / "site-profiles"
        каталог.mkdir(parents=True)
        for файл in (ROOT / "schemas").rglob("*.json"):
            цель = tmp_path / файл.relative_to(ROOT)
            цель.parent.mkdir(parents=True, exist_ok=True)
            цель.write_text(файл.read_text(encoding="utf-8"), encoding="utf-8")
        (tmp_path / "factory" / "site_engine").mkdir(parents=True)
        for файл in (ROOT / "factory" / "site_engine").glob("*.py"):
            (tmp_path / "factory" / "site_engine" / файл.name).write_text(
                файл.read_text(encoding="utf-8"), encoding="utf-8"
            )
        (tmp_path / "factory" / "site_engine" / "adapters").mkdir()
        for файл in (ROOT / "factory" / "site_engine" / "adapters").glob("*.py"):
            (tmp_path / "factory" / "site_engine" / "adapters" / файл.name).write_text(
                файл.read_text(encoding="utf-8"), encoding="utf-8"
            )
        профиль = потребитель_общего_api()
        (каталог / "demo-recipes.json").write_text(
            json.dumps(профиль, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        результат = gate.check_profile(профиль, tmp_path)
        assert результат.passed, результат.problems

    def test_читается_как_профиль(self):
        профиль = profile_from_dict(потребитель_общего_api())
        assert профиль.site_type == "recipe-catalog"
        assert профиль.normalized_content_kind() == "site-engine-api"
        assert not профиль.has("content-ingestion")

    def test_обязательные_модули_добавляются_сами(self):
        профиль = потребитель_общего_api()
        assert set(BASE_MODULES) <= set(профиль["enabled_modules"])

    def test_адаптер_поставщика_добавляется_тому_кто_к_нему_ходит(self):
        профиль = scaffold_profile(
            site_id="demo-feed", site_type="feed", domain="demo-feed.invalid",
            theme="demo", modules=("content-ingestion", "content-catalog"),
            providers=({"adapter": "some-adapter", "role": "primary",
                        "directions": ["news"], "credentials_ref": "some_token"},),
            **ОБЩЕЕ,
        )
        assert "provider-adapters" in профиль["enabled_modules"]


class TestНесогласованныеРешения:
    def test_ни_поставщика_ни_источника_отклоняется(self):
        """Сайт, которому нечего показывать, не должен собираться."""
        with pytest.raises(ContractError, match="показывать будет нечего"):
            scaffold_profile(site_id="demo-empty", site_type="x",
                             domain="demo-empty.invalid", theme="t",
                             modules=("content-catalog",), **ОБЩЕЕ)

    def test_адаптер_без_поставщика_отклоняется(self):
        with pytest.raises(ContractError, match="к поставщику не ходит"):
            scaffold_profile(site_id="demo-odd", site_type="x", domain="demo-odd.invalid",
                             theme="t", modules=("content-catalog", "provider-adapters"),
                             normalized_content_source={"kind": "site-engine-api",
                                                        "ref": "site-engine/v1"},
                             **ОБЩЕЕ)

    def test_без_домена_профиль_не_собирается(self):
        with pytest.raises(ContractError, match="идентификатор и домен"):
            scaffold_profile(site_id="demo", site_type="x", domain="", theme="t",
                             modules=("content-catalog",), **ОБЩЕЕ)


class TestОсторожныеУмолчания:
    def test_индексация_выключена(self):
        """Индексация — решение владельца, а не умолчание генератора."""
        assert потребитель_общего_api()["seo_profile"]["indexing_enabled"] is False

    def test_сбор_аналитики_не_разрешён(self):
        assert потребитель_общего_api()["analytics_profile"]["collection_authorized"] is False

    def test_рекламные_места_выключены(self):
        assert потребитель_общего_api()["feature_flags"]["ad_slots_enabled"] is False

    def test_три_запрета_кэша_на_месте(self):
        """Каждый куплен инцидентом и потому не настраивается."""
        запреты = потребитель_общего_api()["cache_policy"]["forbidden"]
        assert запреты == {"cache_errors": False, "empty_response_as_success": False,
                           "indefinite_html_cache": False}

    def test_хранится_два_релиза(self):
        assert потребитель_общего_api()["release_policy"]["keep_releases"] == 2

    def test_откат_готов_и_переключение_без_простоя(self):
        политика = потребитель_общего_api()["release_policy"]
        assert политика["rollback_ready"] and политика["zero_downtime_switch"]

    def test_домен_не_из_действующих(self):
        """Сгенерированный сайт не должен случайно забрать чужой домен."""
        живые = {"yummyani.site", "yummyani.org", "yummyani.biz", "lordfilm47.space",
                 "lordserial33.biz", "1lordserials1.online"}
        assert not (set(потребитель_общего_api()["domains"]) & живые)
