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


class TestЧужаяРазметкаНеТрогается:
    """Ответ приложения доходит до клиента байт в байт.

    Посредник дописывал в чужую страницу мета-теги версии, стиль, атрибуты на
    `<html>`, атрибуты формы, мета-тег robots, скрипт, полосу разделов, бейдж
    и дополнение карточки. Каждое из этого — чужой узел или чужой атрибут в
    дереве React, и на них ломалось восстановление страницы: `Minified React
    error #418`, а следом отказ всей клиентской части, включая поиск.

    Проверка прямая: тело ответа сравнивается с телом заглушки. Косвенная
    проверка («нет такого-то класса») пропустила бы новую вставку, эта — нет.
    """

    def test_ответ_приложения_не_изменён(self, витрина):
        _, тело = взять(витрина, "/")
        assert тело == ЗАГЛУШКА, "посредник изменил чужую разметку"

    def test_страница_тайтла_не_изменена(self, витрина):
        _, тело = взять(витрина, ПУТЬ_ТАЙТЛА)
        assert тело == ЗАГЛУШКА

    def test_выдача_поиска_не_изменена(self, витрина):
        _, тело = взять(витрина, "/search?q=%D0%B4%D0%B0%D1%80%D0%B0")
        assert тело == ЗАГЛУШКА

    def test_в_витрине_не_осталось_вставок(self):
        """Ни одного места, где посредник правит чужую разметку."""
        исходник = (ХОСТ / "yummy-frontend.py").read_text(encoding="utf-8")
        for запрет in ("data-sf-nav", "data-sf-robots", "sf-mobnav",
                       "MutationObserver", "removeChild",
                       "portal-search-row", "portal-nav-link"):
            assert запрет not in исходник, f"осталась вставка в чужую разметку: {запрет}"

    def test_дополнение_карточки_не_выводится(self, витрина):
        """Блок готов и проверен фикстурой, но наружу отдельным узлом не идёт."""
        _, тело = взять(витрина, ПУТЬ_ТАЙТЛА)
        assert '<section class="sf-entity"' not in тело


class TestСобственныеСтраницы:
    """Версию объявляет тот, кто рисует страницу.

    Собственные страницы витрины (`/top/`, `/new/`, `/collections/`,
    `/schedule/`) собирает она сама — там чужого дерева нет, и объявление
    версии на них её собственная разметка, а не вставка в чужую.
    """

    def test_признак_своей_страницы(self, витрина):
        код, тело = взять(витрина, "/top/")
        assert код == 200
        assert 'data-sf-own="1"' in тело

    def test_версия_объявлена(self, витрина):
        _, тело = взять(витрина, "/top/")
        assert 'data-template-version="0.0.0-test"' in тело
        assert 'name="site-factory-design-version"' in тело

    def test_индексация_закрыта(self, витрина):
        _, тело = взять(витрина, "/top/")
        assert тело.count('name="robots"') == 1
        assert 'content="noindex, nofollow"' in тело

    def test_бейдж_виден(self, витрина):
        _, тело = взять(витрина, "/top/")
        assert 'class="sf-vbadge"' in тело


class TestБезДанных:
    """Отсутствие сущности в контуре не должно ломать страницу."""

    def test_неизвестный_тайтл_не_рисует_пустую_карточку(self, витрина):
        код, тело = взять(витрина, "/anime/нет-такого-тайтла")
        assert '<section class="sf-entity"' not in тело
        assert 'class="sf-recs"' not in тело
