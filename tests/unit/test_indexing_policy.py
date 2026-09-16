"""Единственный источник истины о политике индексации.

До этого решение жило в трёх независимых местах и совпадало случайно: обычный
deploy закрывал живую витрину. Здесь проверяется, что источник один и что он
ошибается только в безопасную сторону.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from factory.indexing import CLOSED, OPEN, PolicyError, compile_policy, normalize_domain
from factory.indexing.policy import apply_environment_override, load_profiles

КОРЕНЬ = Path(__file__).resolve().parents[2]
ПРОФИЛИ = КОРЕНЬ / "config" / "site-profiles"

ОТКРЫТ = "yummyani.site"
ЗАКРЫТЫЕ = (
    "yummyani.org", "yummyani.biz", "lordfilm47.space", "lordserial33.biz",
    "1lordserials1.online", "zonafilm.space", "animedia.icu", "animedia.space",
)


def профиль(**переопределения) -> dict:
    основа = {
        "schema_version": "1.0",
        "site_id": "test-site",
        "domains": ["test.example"],
        "canonical_domain": "test.example",
        "environment": "production",
        "profile_family": "test",
        "profile_version": "1.0",
        "seo_profile": {
            "indexing_expected": CLOSED,
            "indexing_reason": "основание для проверки",
        },
    }
    основа.update(переопределения)
    return основа


def каталог(tmp_path: Path, *профили: dict) -> Path:
    d = tmp_path / "profiles"
    d.mkdir(exist_ok=True)
    for i, p in enumerate(профили):
        (d / f"{p.get('site_id', 'site')}-{i}.json").write_text(
            json.dumps(p, ensure_ascii=False), encoding="utf-8"
        )
    return d


# --- фактический реестр -------------------------------------------------------

def test_реальные_профили_дают_матрицу_владельца() -> None:
    политика = compile_policy(ПРОФИЛИ)
    assert политика.open_domains == (ОТКРЫТ,)
    assert set(политика.closed_domains) == set(ЗАКРЫТЫЕ)
    assert политика.matrix()["open_count"] == 1
    assert политика.matrix()["closed_count"] == 8


def test_каждое_решение_объяснено() -> None:
    """Решение без основания нельзя ни проверить, ни пересмотреть."""
    for решение in compile_policy(ПРОФИЛИ).decisions.values():
        assert решение.reason.strip(), f"{решение.domain}: пустое основание"


def test_открытие_ссылается_на_решение_владельца() -> None:
    решение = compile_policy(ПРОФИЛИ).decide(ОТКРЫТ)
    assert решение.expected == OPEN
    assert "владельца" in решение.reason


def test_canonical_каждого_домена_указывает_на_себя() -> None:
    """Канонизация закрытой витрины на чужой домен — заряженное ружьё.

    В трёх профилях canonical_host указывал на lordfilm47.space. На живом сайте
    это не проявлялось, потому что рендер берёт хост запроса, но закреплять
    такое в версионируемом файле нельзя.
    """
    for решение in compile_policy(ПРОФИЛИ).decisions.values():
        assert решение.canonical_domain == решение.domain


# --- неизвестное закрыто ------------------------------------------------------

@pytest.mark.parametrize(
    "хост", ["example.invalid", "", "127.0.0.1", "unknown.yummyani.site", "evil.test"]
)
def test_неизвестный_хост_закрыт(хост: str) -> None:
    """Умолчание «наверное, можно» однажды откроет непроверенный домен."""
    политика = compile_policy(ПРОФИЛИ)
    assert политика.is_open(хост) is False
    assert политика.decide(хост) is None


def test_новый_домен_по_умолчанию_закрыт(tmp_path: Path) -> None:
    новый = профиль(site_id="new-site", domains=["new.example"],
                    canonical_domain="new.example")
    политика = compile_policy(каталог(tmp_path, новый))
    assert политика.is_open("new.example") is False


# --- нормализация -------------------------------------------------------------

@pytest.mark.parametrize(
    "вход, ожидание",
    [
        ("YummyAni.Site", "yummyani.site"),
        ("yummyani.site.", "yummyani.site"),
        ("www.yummyani.site", "yummyani.site"),
        ("WWW.YummyAni.Site.", "yummyani.site"),
        ("  yummyani.site  ", "yummyani.site"),
    ],
)
def test_домен_приводится_к_одному_написанию(вход: str, ожидание: str) -> None:
    assert normalize_domain(вход) == ожидание


def test_алиасы_открытого_домена_тоже_открыты() -> None:
    """www — тот же сайт. Иначе он попал бы под «неизвестный закрыт»."""
    политика = compile_policy(ПРОФИЛИ)
    for вариант in ("www.yummyani.site", "YUMMYANI.SITE", "yummyani.site."):
        assert политика.is_open(вариант) is True


# --- профиль как единственное разрешение --------------------------------------

def test_семейство_не_открывает_домен(tmp_path: Path) -> None:
    """Добавление сайта в семейство не должно его открывать."""
    открытый = профиль(site_id="open-one", domains=["a.example"],
                       canonical_domain="a.example", profile_family="общее",
                       seo_profile={"indexing_expected": OPEN, "indexing_reason": "решение"})
    новый = профиль(site_id="new-one", domains=["b.example"],
                    canonical_domain="b.example", profile_family="общее")
    политика = compile_policy(каталог(tmp_path, открытый, новый))
    assert политика.is_open("a.example") is True
    assert политика.is_open("b.example") is False


def test_окружение_не_может_открыть_закрытое(tmp_path: Path) -> None:
    """Глобальный флаг однажды открыл бы всё семейство общего рендерера."""
    политика = compile_policy(каталог(tmp_path, профиль()))
    сужено = apply_environment_override(политика, closes={"test.example"})
    assert сужено.is_open("test.example") is False
    # обратной операции в модуле нет вовсе
    assert not hasattr(апи := apply_environment_override, "opens"), апи


def test_окружение_может_сузить_разрешение(tmp_path: Path) -> None:
    открытый = профиль(site_id="o", domains=["o.example"], canonical_domain="o.example",
                       seo_profile={"indexing_expected": OPEN, "indexing_reason": "решение"})
    политика = compile_policy(каталог(tmp_path, открытый))
    assert политика.is_open("o.example") is True
    сужено = apply_environment_override(политика, closes={"o.example"})
    assert сужено.is_open("o.example") is False
    assert "закрыто окружением" in сужено.decide("o.example").reason


# --- сборка останавливается до изменений --------------------------------------

def test_известный_домен_без_профиля_блокирует(tmp_path: Path) -> None:
    with pytest.raises(PolicyError, match="без профиля"):
        compile_policy(каталог(tmp_path, профиль()),
                       expected_domains={"test.example", "нет-профиля.example"})


def test_пустой_профиль_блокирует(tmp_path: Path) -> None:
    d = каталог(tmp_path, профиль())
    (d / "empty.json").write_text("   ", encoding="utf-8")
    with pytest.raises(PolicyError, match="пуст"):
        compile_policy(d)


def test_повреждённый_профиль_блокирует(tmp_path: Path) -> None:
    d = каталог(tmp_path, профиль())
    (d / "broken.json").write_text('{"site_id": ', encoding="utf-8")
    with pytest.raises(PolicyError, match="не разбирается"):
        compile_policy(d)


def test_дубликат_домена_блокирует(tmp_path: Path) -> None:
    первый = профиль(site_id="one", domains=["dup.example"], canonical_domain="dup.example")
    второй = профиль(site_id="two", domains=["dup.example"], canonical_domain="dup.example",
                     seo_profile={"indexing_expected": OPEN, "indexing_reason": "иное решение"})
    with pytest.raises(PolicyError, match="объявлен дважды"):
        compile_policy(каталог(tmp_path, первый, второй))


def test_маска_в_домене_блокирует(tmp_path: Path) -> None:
    with pytest.raises(PolicyError, match="маска"):
        compile_policy(каталог(tmp_path, профиль(domains=["*.example"],
                                                 canonical_domain="*.example")))


def test_неизвестное_значение_indexing_expected_блокирует(tmp_path: Path) -> None:
    плохой = профиль(seo_profile={"indexing_expected": "maybe", "indexing_reason": "?"})
    with pytest.raises(PolicyError, match="indexing_expected"):
        compile_policy(каталог(tmp_path, плохой))


def test_неизвестное_окружение_блокирует(tmp_path: Path) -> None:
    with pytest.raises(PolicyError, match="environment"):
        compile_policy(каталог(tmp_path, профиль(environment="prod")))


@pytest.mark.parametrize("поле", ["schema_version", "canonical_domain", "profile_family"])
def test_отсутствие_обязательного_поля_блокирует(tmp_path: Path, поле: str) -> None:
    п = профиль()
    del п[поле]
    with pytest.raises(PolicyError, match=поле):
        compile_policy(каталог(tmp_path, п))


def test_отсутствие_основания_блокирует(tmp_path: Path) -> None:
    п = профиль(seo_profile={"indexing_expected": CLOSED})
    with pytest.raises(PolicyError, match="indexing_reason"):
        compile_policy(каталог(tmp_path, п))


def test_canonical_вне_списка_доменов_блокирует(tmp_path: Path) -> None:
    п = профиль(domains=["a.example"], canonical_domain="b.example")
    with pytest.raises(PolicyError, match="отсутствует в domains"):
        compile_policy(каталог(tmp_path, п))


# --- окружения не смешиваются -------------------------------------------------

def test_production_не_читает_staging(tmp_path: Path) -> None:
    prod = профиль(site_id="p", domains=["p.example"], canonical_domain="p.example")
    stage = профиль(site_id="s", domains=["s.example"], canonical_domain="s.example",
                    environment="staging",
                    seo_profile={"indexing_expected": OPEN, "indexing_reason": "стенд"})
    политика = compile_policy(каталог(tmp_path, prod, stage))
    assert политика.decide("s.example") is None
    assert политика.is_open("s.example") is False


def test_демонстрационный_профиль_не_попадает_в_production() -> None:
    политика = compile_policy(ПРОФИЛИ)
    assert политика.decide("demo-books.invalid") is None


def test_окружение_без_единого_профиля_блокирует(tmp_path: Path) -> None:
    stage = профиль(environment="staging")
    with pytest.raises(PolicyError, match="нет ни одного профиля"):
        compile_policy(каталог(tmp_path, stage))


def test_отсутствующий_каталог_блокирует(tmp_path: Path) -> None:
    with pytest.raises(PolicyError, match="не найден"):
        compile_policy(tmp_path / "нет-такого")


def test_загрузка_профилей_проверяет_каждый_файл(tmp_path: Path) -> None:
    """Проверка идёт до фильтра по окружению: сломанный staging тоже виден."""
    d = каталог(tmp_path, профиль())
    (d / "broken-stage.json").write_text(
        json.dumps(профиль(environment="staging", seo_profile={})), encoding="utf-8"
    )
    with pytest.raises(PolicyError, match="indexing_expected"):
        load_profiles(d)
