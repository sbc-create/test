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

    def test_адреса_канонические(self, страница):
        assert not re.search(
            r'--[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}',
            страница)


class TestНавигация:
    """Маршруты витрины обязаны быть в меню, а не только отвечать 200."""

    @staticmethod
    def _меню(тело: str) -> list[str]:
        блок = тело[тело.index('<nav class="portal-nav"'):]
        return re.findall(r'href="([^"]+)"', блок[:блок.index("</nav>")])

    def test_маршруты_есть_в_шапке(self, витрина):
        _, тело = взять(витрина, "/")
        адреса = set(self._меню(тело))
        assert {"/new/", "/top/", "/collections/", "/schedule/"} <= адреса

    def test_существующий_пункт_перенаправлен_а_не_удвоен(self, витрина):
        """У витрины уже есть «Топ-100»; второй такой пункт — дефект меню."""
        _, тело = взять(витрина, "/")
        адреса = self._меню(тело)
        assert "/catalog/top" not in адреса
        assert адреса.count("/top/") == 1
        assert 'data-sf-nav="1" href="/top/"' not in тело

    def test_порядок_из_профиля_домена(self, витрина):
        _, тело = взять(витрина, "/")
        свои = re.findall(r'data-sf-nav="1" href="([^"]+)"', тело)
        # editorial-guide ведёт подборками, а не расписанием.
        assert свои[0] == "/collections/"

    def test_текущий_раздел_отмечен(self, витрина):
        _, тело = взять(витрина, "/new/")
        assert re.search(r'data-sf-nav="1" href="/new/" aria-current="page"', тело)

    def test_пункты_не_удваиваются(self, витрина):
        _, тело = взять(витрина, "/")
        # Считаются ссылки, а не вхождения метки: она есть и в скрипте,
        # который возвращает пункты после гидратации.
        # Своих пунктов три: «Топ-100» витрины перенаправлен, а не продублирован.
        assert len(re.findall(r'<a class="portal-nav-link" data-sf-nav="1"', тело)) == 3

    def test_пункты_возвращаются_после_гидратации(self, витрина):
        """Шапку рисует React и при гидратации удаляет чужие узлы.

        Разметка сервера при этом верна, и проверка по HTTP такое пропускает:
        в исходнике пункты есть, в браузере через долю секунды их нет. Здесь
        закрепляется наличие возвращающего скрипта; сам факт видимости в
        браузере проверяется прогоном `var/yummy-accept.js`.
        """
        _, тело = взять(витрина, "/")
        assert 'data-sf-nav-script="1"' in тело
        assert "MutationObserver" in тело
        for адрес in ("/new/", "/top/", "/collections/", "/schedule/"):
            assert адрес in тело


class TestБезДанных:
    """Отсутствие сущности в контуре не должно ломать страницу."""

    def test_неизвестный_тайтл_не_рисует_пустую_карточку(self, витрина):
        код, тело = взять(витрина, "/anime/нет-такого-тайтла")
        assert '<section class="sf-entity"' not in тело
        assert 'class="sf-recs"' not in тело
