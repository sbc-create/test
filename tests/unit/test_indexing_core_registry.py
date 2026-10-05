"""Реестр индексируемости семейства Yummy: чтение, запись и подключённость.

Что здесь защищается
--------------------

Режим этого семейства живёт не в нашем файле состояния, а в собственном
реестре площадки, который читает её же модуль. Операция индексации им
ПОЛЬЗУЕТСЯ, а не подменяет его — и ровно это проверяется:

* поддержкой механизма считается ПОДКЛЮЧЕНИЕ, а не наличие файла;
* запись одного домена не создаётся из ничего и не трогает чужие;
* пустой идентификатор разрешения владельца не проходит;
* операция объявлена в очереди, у исполнителя и в перечне защищённых данных —
  и объявлена В ОДНОМ смысле, а не тремя похожими перечнями.
"""
from __future__ import annotations

import json
import pathlib
import shutil

import pytest

from factory.cell import indexing_core

КОРЕНЬ = pathlib.Path(__file__).resolve().parents[2]
ОБРАЗЕЦ_ЧИТАТЕЛЯ = pathlib.Path("/srv/lords/.frontend/nova_core_indexability.py")

РЕЕСТР = {
    "schema": "indexing-core-registry/1.0",
    "domains": {
        "открытый.test": {
            "exact_domain": "открытый.test",
            "tenant_id": "один",
            "desired_state": "OPEN",
            "policy_revision": 3,
            "owner_authorization_id": "OWNER-1",
            "reason": "разрешено владельцем",
        },
        "закрытый.test": {
            "exact_domain": "закрытый.test",
            "tenant_id": "два",
            "desired_state": "CLOSED",
            "policy_revision": 1,
            "owner_authorization_id": "BOOTSTRAP-CLOSED",
            "reason": "решения владельца нет",
        },
    },
}

ТОЧКА_ВХОДА = '''#!/usr/bin/env python3
import nova_core_indexability as _nova
ИНДЕКСАЦИЯ_ОТКРЫТА = _nova.resolve_or_exit()
'''


@pytest.fixture
def площадка(tmp_path, monkeypatch):
    """Выпуск ячейки с НАСТОЯЩИМ читателем площадки и своим реестром.

    Читатель берётся побайтово у работающей витрины: проверять запись своей
    копией его алгоритма значило бы проверять не то, что читает витрина. Если
    файла на хосте нет — тест пропускается, а не подменяется заглушкой.
    """
    if not ОБРАЗЕЦ_ЧИТАТЕЛЯ.is_file():
        pytest.skip(f"нет образца читателя площадки {ОБРАЗЕЦ_ЧИТАТЕЛЯ}")
    выпуск = tmp_path / "current"
    (выпуск / "src").mkdir(parents=True)
    (выпуск / "config").mkdir()
    shutil.copyfile(ОБРАЗЕЦ_ЧИТАТЕЛЯ, выпуск / "src" / "nova_core_indexability.py")
    (выпуск / "src" / "yummy-frontend.py").write_text(ТОЧКА_ВХОДА, encoding="utf-8")
    реестр = tmp_path / "indexing-core-registry.json"
    реестр.write_text(json.dumps(РЕЕСТР, ensure_ascii=False, indent=2),
                      encoding="utf-8")
    (выпуск / "config" / "site.json").write_text(json.dumps({
        "site_id": "проба-01", "domain": "закрытый.test",
        "environment": {"INDEXING_CORE_REGISTRY": str(реестр)},
    }, ensure_ascii=False), encoding="utf-8")
    monkeypatch.setattr(indexing_core, "корни_выпуска",
                        lambda аккаунт: (выпуск,))
    return {"выпуск": выпуск, "реестр": реестр}


def test_подключением_считается_вызов_а_не_наличие_файла(площадка, monkeypatch):
    """Модуль, который никто не вызывает, режим не решает."""
    св = indexing_core.связанный_читатель("проба")
    assert св["connected"] is True, св
    assert св["calls"] is True

    точка = площадка["выпуск"] / "src" / "yummy-frontend.py"
    точка.write_text("import nova_core_indexability as _n  # и ничего\n",
                     encoding="utf-8")
    св = indexing_core.связанный_читатель("проба")
    assert св["connected"] is False
    assert "не вызывает" in св["reason"], св["reason"]


def test_без_объявления_пути_реестр_не_подставляется(площадка):
    """Пустое поле — не разрешение взять похожий файл по соседству."""
    конфиг = площадка["выпуск"] / "config" / "site.json"
    конфиг.write_text(json.dumps({"environment": {}}), encoding="utf-8")
    св = indexing_core.связанный_читатель("проба")
    assert св["connected"] is False
    assert "INDEXING_CORE_REGISTRY" in св["reason"]
    файл, причина = indexing_core.путь_реестра("проба")
    assert файл is None
    assert "INDEXING_CORE_REGISTRY" in причина


def test_запись_отсутствующего_домена_не_создаётся(площадка):
    """Нет записи — нет решения владельца. Придумать её нельзя."""
    with pytest.raises(indexing_core.РеестрЯдра) as ош:
        indexing_core.запись(площадка["реестр"], "чужой.test")
    assert "решения владельца" in str(ош.value)
    with pytest.raises(indexing_core.РеестрЯдра):
        indexing_core.переписать(
            площадка["реестр"], "чужой.test", режим="OPEN",
            authorization_id="OWNER-2", причина="проба", аккаунт="проба",
            dry_run=False)


def test_пустое_разрешение_владельца_не_проходит(площадка):
    with pytest.raises(indexing_core.РеестрЯдра) as ош:
        indexing_core.переписать(
            площадка["реестр"], "закрытый.test", режим="OPEN",
            authorization_id="  ", причина="проба", аккаунт="проба",
            dry_run=True)
    assert "не придумывается" in str(ош.value)


def test_чужие_записи_остаются_байт_в_байт(площадка):
    """Файл общий на семейство: потеря чужой записи закрыла бы чужой сайт."""
    до = json.loads(площадка["реестр"].read_text(encoding="utf-8"))
    итог = indexing_core.переписать(
        площадка["реестр"], "закрытый.test", режим="OPEN",
        authorization_id="OWNER-2", причина="разрешение владельца OWNER-2",
        аккаунт="проба", dry_run=False)
    assert итог["changed"] is True
    после = json.loads(площадка["реестр"].read_text(encoding="utf-8"))
    assert после["domains"]["открытый.test"] == до["domains"]["открытый.test"]
    запись = после["domains"]["закрытый.test"]
    assert запись["desired_state"] == "OPEN"
    assert запись["policy_revision"] == 2, "ревизия политики обязана вырасти"
    assert запись["owner_authorization_id"] == "OWNER-2"
    assert запись["reason"] == "разрешение владельца OWNER-2"
    # Копия ДО подмены существует: возврат не зависит от чьей-то памяти.
    assert pathlib.Path(итог["backup"]).is_file()


def test_отпечаток_считается_алгоритмом_площадки(площадка):
    """Свой алгоритм разошёлся бы с её сторожем при первой же правке формата."""
    indexing_core.переписать(
        площадка["реестр"], "закрытый.test", режим="OPEN",
        authorization_id="OWNER-2", причина="проба", аккаунт="проба",
        dry_run=False)
    модуль = indexing_core._модуль_площадки("проба")
    данные = json.loads(площадка["реестр"].read_text(encoding="utf-8"))
    запись = данные["domains"]["закрытый.test"]
    assert запись["policy_digest"] == модуль._digest_entry(запись)
    # И сам читатель площадки видит новый режим.
    разобрано = модуль.load_domains(площадка["реестр"])
    assert разобрано["закрытый.test"]["indexing_open"] is True


def test_повтор_того_же_режима_ничего_не_пишет(площадка):
    было = площадка["реестр"].read_text(encoding="utf-8")
    итог = indexing_core.переписать(
        площадка["реестр"], "открытый.test", режим="OPEN",
        authorization_id="OWNER-1", причина="проба", аккаунт="проба",
        dry_run=False)
    assert итог["changed"] is False
    assert площадка["реестр"].read_text(encoding="utf-8") == было


def test_проба_без_записи_файл_не_меняет(площадка):
    было = площадка["реестр"].read_text(encoding="utf-8")
    итог = indexing_core.переписать(
        площадка["реестр"], "закрытый.test", режим="OPEN",
        authorization_id="OWNER-2", причина="проба", аккаунт="проба",
        dry_run=True)
    assert итог["dry_run"] is True
    assert итог["changed"] is False
    assert итог["after"]["desired_state"] == "OPEN", "что будет — сказано"
    assert площадка["реестр"].read_text(encoding="utf-8") == было


def test_операция_объявлена_во_всех_перечнях():
    """Три похожих перечня — повод для расхождения; оно уже случалось."""
    from factory.cell import executor, protected, queue

    assert "indexing-core" in queue.ОПЕРАЦИИ
    assert "indexing-core" in queue.ОПЕРАЦИИ_БЕЗ_ВЫПУСКА
    assert "indexing-core" in executor.ОПЕРАЦИИ_БЕЗ_РЕПОЗИТОРИЯ
    assert "indexing_core_applied" in queue.ЭТАПЫ
    assert protected.ВЛАДЕЛЬЦЫ_ВИДОВ["indexing_core"] == ("indexing_core",)
    assert protected.ЧИТАТЕЛИ["indexing_core"] == ("src/nova_core_indexability.py",)
    # Диспетчер исполнителя обязан звать обработчик, а не падать «ещё не
    # реализована»: заявка дошла бы до него и была бы отвергнута.
    текст = (КОРЕНЬ / "factory" / "cell" / "executor.py").read_text("utf-8")
    assert 'заявка.operation == "indexing-core"' in текст
    assert "переключить_ядро_индексации(заявка" in текст


def test_идентификатор_заявки_называет_реестр_а_не_слой():
    """Слой nginx и реестр ядра — разная работа, и идентификаторы разные."""
    from factory.cell import queue

    слой = queue.собрать("yummy-08", "", "", operation="indexing-nginx",
                         mode="OPEN")
    ядро = queue.собрать("yummy-08", "", "", operation="indexing-core",
                         mode="OPEN")
    assert слой.request_id == "yummy-08-idx-open"
    assert ядро.request_id == "yummy-08-core-open"


def test_согласие_владельца_спрашивается_одной_функцией():
    """Две копии проверки разошлись бы — и в сторону более слабого условия."""
    текст = (КОРЕНЬ / "factory" / "cell" / "executor.py").read_text("utf-8")
    общая = текст.split("def _требовать_согласия", 1)[1].split("\ndef ", 1)[0]
    assert "owner_consent.проверить(" in общая, (
        "общая проверка обязана спрашивать именно якорь согласия")
    for функция in ("переключить_слой_индексации", "переключить_ядро_индексации"):
        тело = текст.split(f"def {функция}", 1)[1].split("\ndef ", 1)[0]
        assert "owner_consent.проверить(" not in тело, (
            f"{функция} держит свою копию проверки согласия: две копии "
            "разойдутся, и разойдутся в сторону более слабого условия")
        тело = текст.split(f"def {функция}", 1)[1].split("\ndef ", 1)[0]
        assert "_требовать_согласия(заявка" in тело, функция


def test_закрытие_сохраняет_прежнее_разрешение(площадка):
    """Закрытие не отменяет того, кто когда-то разрешил."""
    indexing_core.переписать(
        площадка["реестр"], "открытый.test", режим="CLOSED",
        authorization_id="OWNER-1", причина="закрыто операцией",
        аккаунт="проба", dry_run=False)
    запись = indexing_core.запись(площадка["реестр"], "открытый.test")
    assert запись["desired_state"] == "CLOSED"
    assert запись["owner_authorization_id"] == "OWNER-1"
    assert запись["policy_revision"] == 4


def test_подмена_сохраняет_владельца_и_права(площадка):
    """Файл реестра ОБЩИЙ: пять витрин читают его, инструменты правят.

    Операцию исполняет root, и новый файл по умолчанию достался бы root с его
    umask. Смена владельца сделала бы следующую правку невозможной, а сужение
    прав — чтение. Поэтому режим берётся у ПРЕЖНЕГО файла.
    """
    площадка["реестр"].chmod(0o664)
    было = площадка["реестр"].stat()
    indexing_core.переписать(
        площадка["реестр"], "закрытый.test", режим="OPEN",
        authorization_id="OWNER-2", причина="проба", аккаунт="проба",
        dry_run=False)
    стало = площадка["реестр"].stat()
    assert стало.st_mode & 0o7777 == было.st_mode & 0o7777
    assert (стало.st_uid, стало.st_gid) == (было.st_uid, было.st_gid)


def test_запрет_в_теле_ищется_тегом_а_не_подстрокой():
    """`"noindex":false` во встроенном JSON — не запрет индексации.

    Проверка исполнителя искала слово `noindex` подстрокой по первым 4 КБ
    тела. У приложения Yummy во встроенном JSON есть ключи вида
    `"noindex":false`, и такой поиск объявил бы запрет там, где его нет —
    то есть отказал бы открытию по признаку, к режиму не относящемуся.

    Проверяется ПОВЕДЕНИЕ: функция вызывается против настоящего HTTP-ответа.
    """
    import http.server
    import threading

    from factory.cell import executor

    тела = {
        "/ложный": b'<html><head><script>{"seo":{"noindex":false}}</script>'
                   b'</head><body>ok</body></html>',
        "/настоящий": b'<html><head><meta name="robots" content="noindex, follow">'
                      b'</head><body>ok</body></html>',
        "/открытый": b'<html><head><meta name="robots" content="index, follow">'
                     b'</head><body>ok</body></html>',
    }

    class Обработчик(http.server.BaseHTTPRequestHandler):
        путь_тела = "/ложный"

        def do_GET(self):
            тело = тела[Обработчик.путь_тела]
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(тело)))
            self.end_headers()
            self.wfile.write(тело)

        def log_message(self, *а):
            pass

    сервер = http.server.HTTPServer(("127.0.0.1", 0), Обработчик)
    поток = threading.Thread(target=сервер.serve_forever, daemon=True)
    поток.start()
    try:
        порт = сервер.server_address[1]
        Обработчик.путь_тела = "/ложный"
        ответ = executor._заголовок_робота(порт)
        assert ответ["read"] is True, ответ
        assert ответ["noindex"] is False, (
            f"ключ JSON принят за запрет индексации: {ответ}")
        assert ответ["meta"] is None, ответ

        Обработчик.путь_тела = "/настоящий"
        ответ = executor._заголовок_робота(порт)
        assert ответ["noindex"] is True, ответ
        assert ответ["meta"] == "noindex, follow", ответ

        Обработчик.путь_тела = "/открытый"
        ответ = executor._заголовок_робота(порт)
        assert ответ["noindex"] is False, ответ
        assert ответ["meta"] == "index, follow", ответ
    finally:
        сервер.shutdown()
        сервер.server_close()


def test_незагружаемые_конфигурации_не_считаются_живыми():
    """`sites-available` nginx не включает, и объявление map туда ставить нельзя.

    Измерено 2026-10-05 на yummyani.biz: объявление переменной попадало в
    `sites-available/yummyani.biz.conf`, использование — в загружаемый
    `sites-enabled`, и nginx отказал: `unknown "cell_robots_yummy_biz"
    variable`. Слой не переключился, домен остался полуоткрытым.
    """
    from factory.cell import nginx_indexing as ни
    assert "sites-available" not in ни.КАТАЛОГИ_NGINX, (
        "незагружаемый каталог снова считается живым")
    assert "sites-enabled" in ни.КАТАЛОГИ_NGINX
    assert "sites-available" in ни.КАТАЛОГИ_ВНЕ_ЗАГРУЗКИ
    # И расхождение двойника обязано называться, а не умалчиваться.
    assert callable(ни.копии_вне_загрузки)
