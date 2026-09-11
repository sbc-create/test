"""Витрина Yummy на контуре с данными: сквозная проверка, а не только компонент.

Модульные тесты доказывают, что компонент умеет рисовать. Здесь доказывается
другое — что **рантайм действительно доносит контракт до страницы**: сервер
поднимается на фикстурном контуре, страница тайтла запрашивается по HTTP, и в
ответе обязаны оказаться поля, рекомендации и внутренняя оценка.

Это ровно тот разрыв, который дороже всего обходился: код лежал в репозитории,
компонент был написан, тесты зелёные — а до публичной страницы ничего не
доходило. Проверка «файл существует» такое не ловит, проверка по HTTP ловит.

Живой контур сюда не подключается: он read-only и почти пуст, а фикстура
описывает контракт целиком. Приложение витрины тоже не нужно — проверяется
собственная страница представления.
"""

from __future__ import annotations

import json
import os
import re
import socket
import subprocess
import sqlite3
import sys
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest

КОРЕНЬ = Path(__file__).resolve().parents[2]
ХОСТ = КОРЕНЬ / "automation" / "host"
sys.path.insert(0, str(КОРЕНЬ / "tests" / "fixtures" / "yummy"))

import contract_fixture as ФИКСТУРА  # noqa: E402

#: Маршрут, под которым фикстурная сущность видна витрине.
ПУТЬ_ТАЙТЛА = "/anime/fixture-0001"


def _свободный_порт() -> int:
    с = socket.socket()
    с.bind(("127.0.0.1", 0))
    порт = с.getsockname()[1]
    с.close()
    return порт


#: Минимальная страница «витрины»: голова, шапка с настоящим меню, main и
#: подвал. Ровно те опорные точки, по которым рантайм вставляет навигацию и
#: дополнение карточки. Приложение целиком поднимать незачем — проверяется
#: рантайм, а не Next.js.
ЗАГЛУШКА = (
    '<!DOCTYPE html><html lang="ru"><head><title>Витрина</title>'
    '<meta name="robots" content="noindex, follow"></head><body>'
    '<header class="portal-header"><nav class="portal-nav" '
    'aria-label="Основное меню"><a class="portal-nav-link" href="/">'
    '<span class="portal-nav-text">Главная</span></a>'
    '<a class="portal-nav-link" href="/catalog/top">'
    '<span class="portal-nav-text">Топ-100</span></a></nav></header>'
    '<form class="portal-search-row" role="search">'
    '<input name="q" value=""><button type="submit">Найти</button></form>'
    '<main id="main-content" class="portal-container">'
    '<h1>Страница витрины</h1></main>'
    '<footer class="portal-footer">подвал</footer></body></html>')


class _Заглушка(BaseHTTPRequestHandler):
    def log_message(self, *а):
        pass

    def do_GET(self):
        тело = ЗАГЛУШКА.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(тело)))
        self.end_headers()
        self.wfile.write(тело)

    do_HEAD = do_GET


def _поднять_заглушку() -> tuple[ThreadingHTTPServer, str]:
    сервер = ThreadingHTTPServer(("127.0.0.1", 0), _Заглушка)
    threading.Thread(target=сервер.serve_forever, daemon=True).start()
    return сервер, f"127.0.0.1:{сервер.server_address[1]}"


def _манифест(куда: Path) -> Path:
    файл = куда / "template-manifest-test.json"
    файл.write_text(json.dumps({
        "schema_version": "1.0.0", "template_family": "yummy",
        "design_version": "0.0.0-test", "source_commit": "0" * 40,
        "build_id": "test", "artifact_sha256": "0" * 64,
        "profile": "test", "built_at": "2026-09-10T00:00:00Z"}), encoding="utf-8")
    return файл


def _база(куда: Path) -> Path:
    файл = куда / "readmodel.sqlite3"
    соед = sqlite3.connect(файл)
    ФИКСТУРА.построить(соед)
    соед.close()
    return файл


@pytest.fixture(scope="module")
def витрина(tmp_path_factory):
    """Рантайм на фикстурном контуре. Приложение витрины не поднимается."""
    куда = tmp_path_factory.mktemp("yummy-runtime")
    порт = _свободный_порт()
    (куда / "catalog.json").write_text('{"items": []}', encoding="utf-8")
    заглушка, адрес = _поднять_заглушку()
    окружение = dict(os.environ)
    окружение.update({
        "LORDS_TEMPLATE_MANIFEST": str(_манифест(куда)),
        "LORDS_CATALOG": str(куда / "catalog.json"),
        "LORDS_SITE_NAME": "YummyAnime",
        "LORDS_LEGACY_UPSTREAM": адрес,
        "LORDS_LEGACY_ROOT": str(куда / "нет-такого-каталога"),
        "YUMMY_VARIANT_DOMAIN": "yummyani.biz",
        "YUMMY_READMODEL": str(_база(куда)),
        # Компонент внутренней оценки включается флагом — здесь он включён,
        # чтобы проверить именно готовность к включению.
        "YUMMY_CAP_PERSONAL_RATING": "1",
        # Заглушка карточку не рисует — режим полный.
        "YUMMY_CARD_MODE": "full",
    })
    процесс = subprocess.Popen(
        [sys.executable, str(ХОСТ / "yummy-frontend.py"), "--port", str(порт)],
        env=окружение, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    основа = f"http://127.0.0.1:{порт}"
    try:
        for _ in range(100):
            if процесс.poll() is not None:
                вывод = процесс.stdout.read().decode("utf-8", "replace")
                pytest.fail(f"витрина не поднялась:\n{вывод}")
            try:
                urllib.request.urlopen(основа + "/healthz", timeout=1).read()
                break
            except (urllib.error.URLError, socket.timeout, ConnectionError):
                time.sleep(0.1)
        else:
            pytest.fail("витрина не ответила на /healthz")
        yield основа
    finally:
        процесс.terminate()
        процесс.wait(timeout=10)
        заглушка.shutdown()


def взять(основа: str, путь: str) -> tuple[int, str]:
    # Путь кодируется на стороне клиента: http.client пишет строку запроса в
    # ASCII, и кириллический адрес рушит сам тест, а не витрину.
    адрес = основа + urllib.parse.quote(путь, safe="/?&=")
    try:
        with urllib.request.urlopen(адрес, timeout=30) as о:
            return о.status, о.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as о:
        return о.code, о.read().decode("utf-8", "replace")


class TestОбъявлениеКонтракта:
    def test_витрина_объявляет_что_принимает(self, витрина):
        код, тело = взять(витрина, "/__contract")
        assert код == 200
        свод = json.loads(тело)
        assert свод["entity_view"] == "yummy-entity-view/1.0.0"
        assert свод["accepts"] == "yummy-read-model/1.x"
        assert свод["read_model"] == "yummy-read-model/1.1.0"
        assert свод["compatible"] is True

    def test_поверхности_названы_числом_а_не_словом(self, витрина):
        свод = json.loads(взять(витрина, "/__contract")[1])
        # Фикстура наполняет все шесть — значит, рантайм их действительно видит.
        assert свод["surfaces"]["new_episodes"] == 4
        assert свод["surfaces"]["ongoing"] == 4
        assert свод["surfaces"]["news"] == 3
        assert свод["surfaces"]["announcements"] == 2

    def test_каппы_видны_снаружи(self, витрина):
        свод = json.loads(взять(витрина, "/__contract")[1])
        assert свод["capabilities"]["personal_rating"] is True
        assert свод["variant"] == "editorial-guide"


@pytest.fixture(scope="module")
def страница(витрина):
    код, тело = взять(витрина, ПУТЬ_ТАЙТЛА)
    assert код == 200, f"страница тайтла ответила {код}"
    return тело


class TestКарточкаПоHTTP:
    """Поля контракта обязаны дойти до страницы, а не остаться в модуле."""


    @pytest.mark.parametrize("кусок", [
        "Fixture: Complete Entity", "フィクスチャ", "Сериал", "Выходит",
        "Япония", "Fixture Studio", "фантастика", "Фикстура Режиссёров",
        "16+", "24 мин", "8 из 24", "Fixture Dub Two",
    ])
    def test_поле_дошло_до_страницы(self, страница, кусок):
        assert кусок in страница

    def test_оценки_подписаны_провайдерами(self, страница):
        for имя in ("IMDb", "Кинопоиск", "Shikimori", "AniList"):
            assert имя in страница
        assert "84.0<small>/100" in страница, "чужая шкала приведена к десятке"

    def test_рекомендации_дошли(self, страница):
        assert страница.count('class="sf-rc"') >= 6
        assert "совпадение по жанру и студии" in страница

    def test_личная_оценка_дошла_за_флагом(self, страница):
        assert 'class="sf-pr"' in страница
        assert страница.count('class="sf-pr__b"') == 10

    def test_версия_и_закрытие_от_индексации(self, страница):
        assert 'name="site-factory-entity-view"' in страница
        assert len(re.findall(r'<meta name="robots"[^>]*>', страница)) == 1
        assert 'content="noindex, nofollow"' in страница

    def test_блок_приходит_в_конце_body(self, страница):
        """Чужой ребёнок в контейнере React ломает гидратацию.

        Блок кладётся в конец body — там React его переживает — и там же
        остаётся: перенос скриптом после гидратации — та же гонка, только
        позже.
        """
        карточка = страница.index('<section class="sf-entity"')
        подвал = страница.rfind("<footer")
        if подвал > 0:
            assert карточка > подвал, "блок встал в середину дерева React"
        хвост = страница[карточка:]
        assert "</body>" in хвост, "блок должен приходить последним"
        # После блока в разметке не остаётся ничего, кроме служебного бейджа
        # и закрывающих тегов: он действительно последний, а не «где-то там».
        assert "<main" not in хвост and "<header" not in хвост

    def test_адреса_канонические(self, страница):
        assert not re.search(
            r'--[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}',
            страница)


class TestНавигация:
    """Разделы витрины добавляются после гидратации и ничего не удаляют.

    Шапку рисует React. Пункт, положенный в разметку сервера, он при
    гидратации считает чужим ребёнком своего контейнера: `Minified React
    error #418`, пересборка поддерева — и вся клиентская часть страницы
    перестаёт работать, включая поиск. Снаружи это выглядело как «подсказки
    не кликаются и кнопка не работает», хотя поиск был цел.

    Поэтому здесь проверяется не наличие пунктов в HTML, а его отсутствие.
    """

    ЗАПРОШЕННЫЕ = ("/new/", "/top/", "/collections/", "/schedule/")

    @staticmethod
    def _шапка(тело: str) -> str:
        начало = тело.index('<nav class="portal-nav"')
        return тело[начало:тело.index("</nav>", начало)]

    def test_шапка_витрины_не_трогается(self, витрина):
        """В контейнер React не попадает ни одного нашего узла."""
        _, тело = взять(витрина, "/")
        шапка = self._шапка(тело)
        assert "sf-" not in шапка and "data-sf" not in шапка

    @staticmethod
    def _полоса(тело: str) -> str:
        начало = тело.index('<nav class="sf-nav"')
        return тело[начало:тело.index("</nav>", начало)]

    def test_индексация_закрыта_и_в_живом_DOM(self, витрина):
        """Витрина после гидратации добавляет свой тег robots.

        На yummyani.site он говорит `index, follow`: разметка сервера и
        заголовок X-Robots-Tag индексацию закрывают, а тег в DOM ей
        противоречит. Приводится только атрибут — удалять чужой узел нельзя,
        именно этим ломался React.
        """
        _, тело = взять(витрина, "/")
        assert 'data-sf-robots="1"' in тело
        скрипт = тело[тело.index('data-sf-robots'):]
        скрипт = скрипт[:скрипт.index("</script>")]
        assert "setAttribute" in скрипт
        for запрет in ("removeChild", "remove()", "MutationObserver", "createElement"):
            assert запрет not in скрипт, f"скрипт меняет структуру дерева: {запрет}"

    def test_навигации_нет_скрипта_вовсе(self, витрина):
        """Скрипт был причиной, а не решением.

        Он ждал `load`, но страница приходит потоком, и к этому моменту React
        ещё достраивает поздние границы. Наблюдатель вставлял пункты ровно
        тогда. Лечится не таймингом, а местом — поэтому скрипта нет.
        """
        _, тело = взять(витрина, "/")
        assert "data-sf-nav-script" not in тело
        assert "MutationObserver" not in тело
        # Проверяется то, что добавили мы: у самой витрины есть свой
        # `$RS`-помощник с removeChild, и он к делу не относится.
        наше = re.findall(r"<script data-sf-[^>]*>.*?</script>", тело, re.S)
        for с in наше:
            for запрет in ("removeChild", "replaceChild", "insertBefore", "MutationObserver"):
                assert запрет not in с, f"витрина разрушает чужой DOM: {запрет}"

    def test_полоса_последний_узел_body(self, витрина):
        """Узел в конце контейнера React переживает, в середине — нет."""
        _, тело = взять(витрина, "/")
        полоса = тело.index('<nav class="sf-nav"')
        подвал = тело.rfind("<footer")
        if подвал > 0:
            assert полоса > подвал, "полоса встала в середину дерева React"
        хвост = тело[полоса:]
        assert "<main" not in хвост and "<header" not in хвост

    def test_маршруты_есть_в_полосе(self, витрина):
        _, тело = взять(витрина, "/")
        адреса = re.findall(r'href="([^"]+)"', self._полоса(тело))
        assert set(адреса) == set(self.ЗАПРОШЕННЫЕ)

    def test_порядок_из_профиля_домена(self, витрина):
        _, тело = взять(витрина, "/")
        адреса = re.findall(r'href="([^"]+)"', self._полоса(тело))
        # editorial-guide ведёт подборками, а не расписанием.
        assert адреса[0] == "/collections/"

    def test_текущий_раздел_отмечен(self, витрина):
        _, тело = взять(витрина, "/new/")
        assert 'href="/new/" aria-current="page"' in self._полоса(тело)

    def test_навигация_работает_без_javascript(self, витрина):
        """Разметка, а не скрипт: без JavaScript разделы остаются доступны."""
        _, тело = взять(витрина, "/")
        полоса = self._полоса(тело)
        assert полоса.count("<a ") == len(self.ЗАПРОШЕННЫЕ)


class TestПоиск:
    """Поиск обязан работать и без JavaScript.

    Формы витрины отправляются только скриптом (`router.push`) и не имеют ни
    `action`, ни `method`. Пока клиентская часть цела, это незаметно; стоит ей
    упасть — и «Найти» не делает ничего, а пользователь остаётся на месте без
    объяснения. Серверный fallback добавляется атрибутами: ни одного нового
    узла, ни одного удалённого.
    """

    @staticmethod
    def _формы(тело: str) -> list[str]:
        return [ф for ф in re.findall(r"<form[^>]*>", тело)
                if "portal-search-row" in ф]

    def test_форма_поиска_отправляется_обычным_get(self, витрина):
        _, тело = взять(витрина, "/")
        формы = self._формы(тело)
        assert формы, "формы поиска не нашлось"
        for ф in формы:
            assert 'action="/search"' in ф, f"нет серверного адреса: {ф[:90]}"
            assert 'method="get"' in ф, f"нет метода: {ф[:90]}"

    def test_чужие_формы_не_трогаются(self, витрина):
        """Переписывается только форма поиска, а не всякая форма страницы."""
        исходник = (ХОСТ / "yummy-frontend.py").read_text(encoding="utf-8")
        assert "portal-search-row" in исходник
        assert "ФОРМА_ПОИСКА" in исходник

    def test_адрес_поиска_канонический(self, витрина):
        """Адрес берётся у витрины, а не придумывается шаблоном."""
        исходник = (ХОСТ / "yummy-frontend.py").read_text(encoding="utf-8")
        assert 'МАРШРУТ_ПОИСКА = "/search"' in исходник


class TestБезДанных:
    """Отсутствие сущности в контуре не должно ломать страницу."""

    def test_неизвестный_тайтл_не_рисует_пустую_карточку(self, витрина):
        код, тело = взять(витрина, "/anime/нет-такого-тайтла")
        assert '<section class="sf-entity"' not in тело
        assert 'class="sf-recs"' not in тело
