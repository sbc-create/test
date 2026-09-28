"""Разметка рендерера совпадает с тем, что переписывает nginx.

Постеры на публичных витринах отдаются не с хоста поставщика, а через
локальный кэширующий прокси. Переписывание живёт в конфигурации nginx и
устроено подстрокой:

    sub_filter 'src="https://poster.cdnvideohub.com/' 'src="/poster/';

То есть договор между двумя слоями держится на точном совпадении текста.
Рендерер о нём не знает и знать не обязан — но стоит ему выдать адрес чуть
иначе, и переписывание перестаёт срабатывать: постеры уйдут напрямую к
поставщику, мимо кэша, без защиты от его отказа и без нашей заглушки.

Отказ будет тихим. Страница соберётся, изображения загрузятся, ничего не
упадёт — просто исчезнет слой, ради которого он заводился.

Случай не выдуманный: в этой же ветке адрес постера начал проходить через
проверку схемы, и вопрос «а совпадает ли он ещё с фильтром» пришлось задавать
руками. Здесь он задаётся сам.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

NGINX = Path("/etc/nginx")

from factory.lords import fixtures as fx  # noqa: E402
from factory.lords import live_catalog as lc  # noqa: E402
from factory.lords import render as render_mod  # noqa: E402
from factory.paths import PATHS  # noqa: E402


def _фильтры() -> list[tuple[str, str]]:
    """Пары «что ищем → на что меняем» из конфигурации витрин."""
    найдено = []
    if not NGINX.is_dir():
        return найдено
    for path in sorted(NGINX.rglob("*.conf")):
        try:
            текст = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        for m in re.finditer(r"sub_filter\s+'([^']+)'\s+'([^']*)'", текст):
            найдено.append((m.group(1), m.group(2)))
    return найдено


@pytest.fixture(scope="module")
def страница() -> str:
    """Главная витрины на живых записях: постеры есть только у них."""
    import json

    снимок = Path("/srv/site-factory/repo/var/lords/lords/catalog-cache/lords-02.json")
    if not снимок.is_file():
        pytest.skip("снимка боевого каталога нет: постеров в фикстуре не бывает")
    raw = json.loads(снимок.read_text(encoding="utf-8"))
    записи = (raw["items"] if isinstance(raw, dict) else raw)[:300]
    каталог = lc.catalog_from_live(записи)
    пакет = yaml.safe_load(PATHS.site_package("lords-02").read_text(encoding="utf-8"))
    site = render_mod.render_site(пакет, catalog=каталог, environ={}, publisher_id="1")
    return site.pages["/"].body


class TestДоговорСПрокси:
    def test_фильтр_постеров_объявлен(self):
        постерные = [f for f in _фильтры() if "poster" in f[0]]
        if not NGINX.is_dir():
            pytest.skip("конфигурация nginx доступна только на управляющем хосте")
        assert постерные, ("в конфигурации нет переписывания постеров: либо оно снято, "
                           "либо витрины отдают адреса поставщика напрямую")

    def test_разметка_совпадает_с_фильтром(self, страница):
        постерные = [f for f in _фильтры() if "poster" in f[0]]
        if not постерные:
            pytest.skip("переписывания постеров в конфигурации нет")
        совпало = [искомое for искомое, _ in постерные if искомое in страница]
        образцы = re.findall(r'<img[^>]+src="[^"]{0,60}', страница)[:2]
        ищут = [и for и, _ in постерные][:3]
        assert совпало, (
            "ни один из фильтров nginx не находит своей подстроки в разметке: "
            f"фильтры ищут {ищут}, а рендерер выдаёт {образцы}. "
            "Переписывание перестало срабатывать, и постеры пойдут мимо кэша")

    def test_адрес_поставщика_доходит_до_разметки(self, страница):
        """Если рендерер перестал выдавать адрес вовсе, фильтру нечего искать."""
        assert "poster.cdnvideohub.com" in страница, (
            "адреса постеров в разметке нет: проверка выше прошла бы впустую")


class TestЗаменаБезопасна:
    def test_замена_ведёт_на_свой_же_хост(self):
        for искомое, замена in _фильтры():
            if "poster" not in искомое:
                continue
            assert замена.startswith('src="/') or замена.startswith('"poster":"/'), (
                f"замена уводит на внешний адрес: {замена!r}")
