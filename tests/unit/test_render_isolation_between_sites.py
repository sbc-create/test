"""Правка одного сайта не меняет ни одной страницы соседнего.

Изоляция на уровне выкладки уже проверена: canary трогает одну витрину, а
`test_lords_canary.py` следит за тем, чтобы соседние каталоги остались
нетронутыми. Но это про файлы. Про **содержимое** проверки не было.

Разница существенная. Выкладка может честно записать только свою витрину — а
страницы в ней окажутся другими, потому что общий рендерер прочитал чужую
настройку: тему, набор разделов, тексты, канонический адрес. Такая утечка не
видна ни по числу файлов, ни по каталогам: она видна только по содержимому.

Здесь мерой служит отпечаток вывода. Каждая витрина собирается дважды — до и
после изолированной правки соседней, — и совпасть обязаны все, кроме
изменённой. Заодно проверяется обратное: правка вообще должна что-то менять,
иначе совпадение доказывало бы лишь то, что мы сравниваем одно и то же.
"""

from __future__ import annotations

import copy
import hashlib
import sys
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from factory.lords import fixtures as fx  # noqa: E402
from factory.lords import render as render_mod  # noqa: E402
from factory.paths import PATHS  # noqa: E402

САЙТЫ = ("lords-01", "lords-02", "lords-03", "lords-04")


@pytest.fixture(scope="module")
def каталог():
    return fx.build_catalog()


def _пакет(site_id: str) -> dict:
    return yaml.safe_load(PATHS.site_package(site_id).read_text(encoding="utf-8"))


def _отпечаток(site_id: str, каталог, пакет: dict | None = None) -> str:
    site = render_mod.render_site(пакет or _пакет(site_id), catalog=каталог,
                                  environ={}, publisher_id="1")
    digest = hashlib.sha256()
    for path, page in sorted(site.pages.items()):
        digest.update(path.encode("utf-8"))
        digest.update(b"\0")
        digest.update(page.payload)
    return digest.hexdigest()


@pytest.fixture(scope="module")
def исходные(каталог) -> dict[str, str]:
    return {s: _отпечаток(s, каталог) for s in САЙТЫ}


class TestОтпечаткиРазличаются:
    def test_витрины_не_одинаковы(self, исходные):
        """Иначе изоляцию доказывать не на чем: сравнивались бы копии."""
        assert len(set(исходные.values())) == len(САЙТЫ), (
            "две витрины дают одинаковый вывод — проверка изоляции была бы пустой")


class TestПравкаТемыНеУходитКСоседям:
    def test_смена_темы_меняет_только_свою_витрину(self, каталог, исходные):
        # Значение берётся из перечня схемы, а не выдумывается. Первая
        # редакция подставила `lords_night`: такого значения схема не
        # допускает, а `palette_of` узнаёт лишь окончания `_light` и `_dark`,
        # поэтому вывод не изменился и проверка ничего не доказывала.
        пакет = copy.deepcopy(_пакет("lords-01"))
        tenant = пакет.setdefault("tenant", {})
        tenant["theme"] = "lords_light" if tenant.get("theme") == "lords_dark" else "lords_dark"

        свой = _отпечаток("lords-01", каталог, пакет)
        assert свой != исходные["lords-01"], (
            "смена темы не изменила вывод: проверка ничего не доказывает")

        for сосед in САЙТЫ[1:]:
            assert _отпечаток(сосед, каталог) == исходные[сосед], (
                f"правка lords-01 изменила вывод {сосед}")


class TestПравкаДоменаНеУходитКСоседям:
    def test_смена_домена_меняет_только_свою_витрину(self, каталог, исходные):
        """Канонический адрес соседа — худший вид утечки: он уводит поиск."""
        пакет = copy.deepcopy(_пакет("lords-02"))
        пакет["domain"] = "изолированная-проверка.invalid"
        пакет["canonical_url"] = "https://изолированная-проверка.invalid/"

        свой = _отпечаток("lords-02", каталог, пакет)
        assert свой != исходные["lords-02"]

        for сосед in ("lords-01", "lords-03", "lords-04"):
            assert _отпечаток(сосед, каталог) == исходные[сосед], (
                f"правка домена lords-02 изменила вывод {сосед}")


class TestПравкаНавигацииНеУходитКСоседям:
    def test_смена_названия_меняет_только_свою_витрину(self, каталог, исходные):
        пакет = copy.deepcopy(_пакет("lords-03"))
        пакет.setdefault("brand", {})["name"] = "Проверка изоляции"

        assert _отпечаток("lords-03", каталог, пакет) != исходные["lords-03"]
        for сосед in ("lords-01", "lords-02", "lords-04"):
            assert _отпечаток(сосед, каталог) == исходные[сосед], сосед


class TestЧужиеИдентификаторыНеПопадаютВСтраницы:
    def test_в_странице_нет_домена_соседа(self, каталог):
        домены = {s: str(_пакет(s).get("domain") or "") for s in САЙТЫ}
        for site_id in САЙТЫ:
            site = render_mod.render_site(_пакет(site_id), catalog=каталог,
                                          environ={}, publisher_id="1")
            свой = домены[site_id]
            чужие = [d for s, d in домены.items() if s != site_id and d and d != свой]
            склеено = b"".join(page.payload for _, page in sorted(site.pages.items()))
            текст = склеено.decode("utf-8", "replace")
            найдены = [d for d in чужие if d in текст]
            assert найдены == [], f"{site_id}: в страницах найден домен соседа {найдены}"


class TestТемаИзПеречняЧтоТоЗначит:
    """Значение, которое схема допускает, не должно быть немым в обоих движках.

    У фабрики два движка, и перечень тем — общий на оба. `palette_of` рендерера
    Lords узнаёт объявленную тему по окончанию `_light` или `_dark` и иначе
    оставляет тему профиля; у движка multisite тема применяется иначе.

    Первая редакция этой проверки смотрела только профили Lords и объявила
    немыми `pulse` и `editorial`. Они не немые — это темы витрин site-b и
    site-c на движке `payload-next-multisite`. Проверка, не знающая о втором
    движке, объявляет осмысленное ошибкой, а это хуже пропуска: по такому
    отчёту удаляют работающее.

    Опасен же обратный случай: значение, добавленное в перечень и не
    применяемое нигде. Манифест говорит одно, витрина выглядит иначе, и никто
    не предупреждён.
    """

    def test_каждое_значение_перечня_где_то_применяется(self):
        import json

        схема = json.loads((ROOT / "schemas" / "site-package.schema.json")
                           .read_text(encoding="utf-8"))
        перечень = схема["properties"]["tenant"]["properties"]["theme"]["enum"]

        профильные = set()
        for path in sorted((ROOT / "blueprints" / "lords" / "profiles").glob("*.yaml")):
            профиль = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
            имя = str((профиль.get("theme") or {}).get("name") or "")
            if имя:
                профильные.add(имя)

        объявленные = {}
        for path in sorted(PATHS.sites.glob("*/package.yaml")):
            пакет = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
            тема = (пакет.get("tenant") or {}).get("theme")
            if тема:
                объявленные.setdefault(str(тема), set()).add(str(пакет.get("blueprint")))

        немые = []
        for тема in перечень:
            узнаётся_lords = тема.endswith(("_light", "_dark")) or тема in профильные
            движки = объявленные.get(тема, set())
            применяется_иначе = bool(движки - {"lords", "None", "null"})
            if not (узнаётся_lords or применяется_иначе):
                немые.append(тема)

        assert немые == [], (
            f"значения темы допускаются схемой, но не применяются ни одним "
            f"движком: {немые}")

    def test_у_каждой_темы_lords_есть_свой_профиль_или_правило(self):
        """Отдельно и строже — про свой движок, где правило нам известно."""
        import json

        from factory.lords import theme as theme_mod

        схема = json.loads((ROOT / "schemas" / "site-package.schema.json")
                           .read_text(encoding="utf-8"))
        перечень = схема["properties"]["tenant"]["properties"]["theme"]["enum"]
        lords_темы = {t for t in перечень
                      if any(t == (yaml.safe_load(p.read_text(encoding="utf-8")) or {})
                             .get("theme", {}).get("name")
                             for p in (ROOT / "blueprints" / "lords" / "profiles").glob("*.yaml"))}
        for тема in lords_темы:
            поверхность = "light" if тема.endswith("_light") else (
                "dark" if тема.endswith("_dark") else None)
            assert поверхность is None or поверхность in theme_mod.SURFACE_PALETTES, тема
