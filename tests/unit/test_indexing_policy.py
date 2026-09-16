"""Единственный источник истины о политике индексации.

До этого решение жило в трёх независимых местах и совпадало случайно: обычный
deploy закрывал живую витрину. Здесь проверяется, что источник один и что он
ошибается только в безопасную сторону.

Источник собран из того, что в репозитории уже было: перечень обслуживаемых
доменов — ``config/FLEET-REGISTRY.json``, решение по сайту —
``seo_profile.indexing_enabled`` его профиля, собственный домен —
``seo_profile.canonical_host`` там же. Добавлено одно поле: ``indexing_reason``.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from factory.indexing import OPEN, PolicyError, compile_policy, normalize_domain
from factory.indexing.policy import apply_environment_override, load_fleet, load_profiles

КОРЕНЬ = Path(__file__).resolve().parents[2]
ПРОФИЛИ = КОРЕНЬ / "config" / "site-profiles"

ОТКРЫТ = "yummyani.site"
ЗАКРЫТЫЕ = (
    "yummyani.org", "yummyani.biz", "lordfilm47.space", "lordserial33.biz",
    "1lordserials1.online", "zonafilm.space", "animedia.icu", "animedia.space",
)
#: Домены флота, у которых профиля сайта в репозитории нет.
БЕЗ_ПРОФИЛЯ = ("zonafilm.space", "animedia.icu", "animedia.space")


def профиль(**переопределения) -> dict:
    """Профиль формы ``site-profile.schema.json`` — тех полей, что читает политика."""
    seo = {
        "enabled": True,
        "indexing_enabled": False,
        "canonical_host": "test.example",
        "indexing_reason": "основание для проверки",
    }
    основа = {
        "schema_version": "1.0",
        "site_id": "test-site",
        "site_type": "video-showcase",
        "domains": ["test.example"],
        "seo_profile": seo,
    }
    основа.update(переопределения)
    return основа


def открытый(**переопределения) -> dict:
    """Профиль с принятым решением об открытии."""
    п = профиль(**переопределения)
    п["seo_profile"] = {
        **п["seo_profile"],
        "indexing_enabled": True,
        "indexing_reason": "решение владельца",
    }
    return п


def каталог(tmp_path: Path, *профили: dict, флот: list | None = None) -> Path:
    """Каталог профилей и реестр флота рядом с ним — как в репозитории."""
    корень = tmp_path / "config"
    d = корень / "site-profiles"
    d.mkdir(parents=True, exist_ok=True)
    for i, p in enumerate(профили):
        (d / f"{p.get('site_id', 'site')}-{i}.json").write_text(
            json.dumps(p, ensure_ascii=False), encoding="utf-8"
        )
    записи = флот if флот is not None else [
        {"site_id": p["site_id"], "domain": p["domains"][0]} for p in профили
    ]
    (корень / "FLEET-REGISTRY.json").write_text(
        json.dumps({"schema_version": "1.0", "fleet": записи}, ensure_ascii=False),
        encoding="utf-8",
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
    """Канонизация закрытой витрины на чужой домен — заряженное ружьё."""
    for решение in compile_policy(ПРОФИЛИ).decisions.values():
        assert решение.canonical_domain == решение.domain


def test_решение_читается_из_существующего_поля_профиля() -> None:
    """Политика не заводит своего поля: она читает ``indexing_enabled``.

    Второе поле с тем же смыслом — это та же вторая запись истины, ради
    устранения которой всё и затевалось.
    """
    профиль_текст = (ПРОФИЛИ / "yummyani-site.json").read_text(encoding="utf-8")
    seo = json.loads(профиль_текст)["seo_profile"]
    assert seo["indexing_enabled"] is True
    assert "indexing_expected" not in seo, "поле-дубликат вернулось в профиль"


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
    новый = профиль(site_id="new-site", domains=["new.example"])
    новый["seo_profile"]["canonical_host"] = "new.example"
    политика = compile_policy(каталог(tmp_path, новый))
    assert политика.is_open("new.example") is False


# --- сайт флота без профиля ---------------------------------------------------

@pytest.mark.parametrize("домен", БЕЗ_ПРОФИЛЯ)
def test_сайт_флота_без_профиля_закрыт(домен: str) -> None:
    """Три домена обслуживаются, но профиля сайта у них нет.

    Это не повод остановить сборку: решения об их открытии не принимали, и
    закрытое решение с явным основанием — правильный ответ. Если такой домен
    вдруг окажется открытым на живом сервере, разницу покажут ворота релиза.
    """
    решение = compile_policy(ПРОФИЛИ).decide(домен)
    assert решение is not None, "домен флота обязан попасть в матрицу"
    assert решение.open is False
    assert "профиля сайта нет" in решение.reason


def test_домен_вне_флота_без_решения_блокирует(tmp_path: Path) -> None:
    """Инвентарь называет домен, которого нет ни в реестре, ни в профилях."""
    with pytest.raises(PolicyError, match="без решения"):
        compile_policy(каталог(tmp_path, профиль()),
                       expected_domains={"test.example", "нет-решения.example"})


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
    один = открытый(site_id="open-one", domains=["a.example"], site_type="общее")
    один["seo_profile"]["canonical_host"] = "a.example"
    новый = профиль(site_id="new-one", domains=["b.example"], site_type="общее")
    новый["seo_profile"]["canonical_host"] = "b.example"
    политика = compile_policy(каталог(tmp_path, один, новый))
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
    о = открытый(site_id="o", domains=["o.example"])
    о["seo_profile"]["canonical_host"] = "o.example"
    политика = compile_policy(каталог(tmp_path, о))
    assert политика.is_open("o.example") is True
    сужено = apply_environment_override(политика, closes={"o.example"})
    assert сужено.is_open("o.example") is False
    assert "закрыто окружением" in сужено.decide("o.example").reason


# --- сборка останавливается до изменений --------------------------------------

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
    первый = профиль(site_id="one", domains=["dup.example"])
    первый["seo_profile"]["canonical_host"] = "dup.example"
    второй = открытый(site_id="two", domains=["dup.example"])
    второй["seo_profile"]["canonical_host"] = "dup.example"
    with pytest.raises(PolicyError, match="объявлен дважды"):
        compile_policy(каталог(tmp_path, первый, второй))


def test_маска_в_домене_блокирует(tmp_path: Path) -> None:
    п = профиль(domains=["*.example"])
    with pytest.raises(PolicyError, match="маска"):
        compile_policy(каталог(tmp_path, п, флот=[{"site_id": "test-site",
                                                   "domain": "test.example"}]))


def test_нелогическое_значение_решения_блокирует(tmp_path: Path) -> None:
    """``"да"`` — не решение: истинность строки зависит от языка, а не от смысла."""
    п = профиль()
    п["seo_profile"]["indexing_enabled"] = "да"
    with pytest.raises(PolicyError, match="indexing_enabled"):
        compile_policy(каталог(tmp_path, п))


def test_неизвестное_окружение_блокирует(tmp_path: Path) -> None:
    with pytest.raises(PolicyError, match="environment"):
        compile_policy(каталог(tmp_path, профиль()), environment="prod")


@pytest.mark.parametrize("поле", ["schema_version", "site_type", "domains"])
def test_отсутствие_обязательного_поля_блокирует(tmp_path: Path, поле: str) -> None:
    п = профиль()
    del п[поле]
    with pytest.raises(PolicyError, match=поле):
        compile_policy(каталог(tmp_path, п, флот=[{"site_id": "test-site",
                                                   "domain": "test.example"}]))


def test_отсутствие_основания_блокирует(tmp_path: Path) -> None:
    п = профиль()
    del п["seo_profile"]["indexing_reason"]
    with pytest.raises(PolicyError, match="indexing_reason"):
        compile_policy(каталог(tmp_path, п))


def test_canonical_вне_списка_доменов_блокирует(tmp_path: Path) -> None:
    п = профиль(domains=["a.example"])
    п["seo_profile"]["canonical_host"] = "b.example"
    with pytest.raises(PolicyError, match="отсутствует в domains"):
        compile_policy(каталог(tmp_path, п, флот=[{"site_id": "test-site",
                                                   "domain": "a.example"}]))


def test_профиль_не_знающий_домен_реестра_блокирует(tmp_path: Path) -> None:
    """Реестр обслуживает один домен, профиль знает другой — молчать нельзя."""
    п = профиль(domains=["a.example"])
    п["seo_profile"]["canonical_host"] = "a.example"
    with pytest.raises(PolicyError, match="реестр флота обслуживает"):
        compile_policy(каталог(tmp_path, п, флот=[{"site_id": "test-site",
                                                   "domain": "иной.example"}]))


# --- реестр флота -------------------------------------------------------------

def test_реальный_реестр_перечисляет_девять_сайтов() -> None:
    флот = load_fleet(КОРЕНЬ / "config" / "FLEET-REGISTRY.json")
    assert len(флот) == 9
    assert set(флот.values()) == {ОТКРЫТ, *ЗАКРЫТЫЕ}


def test_отсутствующий_реестр_блокирует(tmp_path: Path) -> None:
    with pytest.raises(PolicyError, match="реестр флота не найден"):
        load_fleet(tmp_path / "нет-такого.json")


def test_пустой_реестр_блокирует(tmp_path: Path) -> None:
    п = tmp_path / "FLEET-REGISTRY.json"
    п.write_text("  ", encoding="utf-8")
    with pytest.raises(PolicyError, match="пуст"):
        load_fleet(п)


def test_реестр_без_списка_блокирует(tmp_path: Path) -> None:
    п = tmp_path / "FLEET-REGISTRY.json"
    п.write_text(json.dumps({"schema_version": "1.0"}), encoding="utf-8")
    with pytest.raises(PolicyError, match="нет списка fleet"):
        load_fleet(п)


def test_дубликат_сайта_в_реестре_блокирует(tmp_path: Path) -> None:
    п = tmp_path / "FLEET-REGISTRY.json"
    п.write_text(json.dumps({"fleet": [
        {"site_id": "one", "domain": "a.example"},
        {"site_id": "one", "domain": "b.example"},
    ]}), encoding="utf-8")
    with pytest.raises(PolicyError, match="объявлен дважды"):
        load_fleet(п)


# --- окружения не смешиваются -------------------------------------------------

def test_профиль_вне_флота_не_попадает_в_production(tmp_path: Path) -> None:
    боевой = профиль(site_id="p", domains=["p.example"])
    боевой["seo_profile"]["canonical_host"] = "p.example"
    посторонний = открытый(site_id="s", domains=["s.example"])
    посторонний["seo_profile"]["canonical_host"] = "s.example"
    политика = compile_policy(
        каталог(tmp_path, боевой, посторонний,
                флот=[{"site_id": "p", "domain": "p.example"}])
    )
    assert политика.decide("s.example") is None
    assert политика.is_open("s.example") is False


def test_демонстрационный_профиль_не_попадает_в_production() -> None:
    политика = compile_policy(ПРОФИЛИ)
    assert политика.decide("demo-books.invalid") is None


def test_демонстрационное_окружение_видит_только_его() -> None:
    политика = compile_policy(ПРОФИЛИ, environment="demo")
    assert set(политика.decisions) == {"demo-books.invalid"}
    assert политика.is_open("demo-books.invalid") is False


def test_пустой_каталог_профилей_блокирует(tmp_path: Path) -> None:
    d = tmp_path / "config" / "site-profiles"
    d.mkdir(parents=True)
    (tmp_path / "config" / "FLEET-REGISTRY.json").write_text(
        json.dumps({"fleet": [{"site_id": "x", "domain": "x.example"}]}), encoding="utf-8"
    )
    with pytest.raises(PolicyError, match="нет ни одного профиля"):
        compile_policy(d)


def test_отсутствующий_каталог_блокирует(tmp_path: Path) -> None:
    with pytest.raises(PolicyError, match="не найден"):
        compile_policy(tmp_path / "нет-такого")


def test_загрузка_профилей_проверяет_каждый_файл(tmp_path: Path) -> None:
    """Проверка идёт по всем файлам каталога, а не только по нужным флоту."""
    d = каталог(tmp_path, профиль())
    (d / "broken-other.json").write_text(
        json.dumps(профиль(site_id="other", seo_profile={})), encoding="utf-8"
    )
    with pytest.raises(PolicyError, match="indexing_enabled"):
        load_profiles(d)
