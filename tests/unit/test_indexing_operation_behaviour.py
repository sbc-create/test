"""Поведение штатной операции открытия — на изолированном окружении.

Пять случаев из задания владельца, и ни один не проверяется чтением кода:

  * отказ при отсутствии разрешения владельца;
  * отказ при несовпадении ожидаемого выпуска;
  * открытие и закрытие РАЗРЕШЁННОГО тестового сайта;
  * частичный сбой с восстановлением исходного состояния;
  * повтор операции без непредусмотренных изменений.

Живых доменов проверка не касается: свой реестр, свой каталог выпуска, свой
корень файлов состояния, своя конфигурация nginx и подставная очередь. Ни
одного обращения к сети: публичные сигналы задаёт сценарий — именно так
проверяется поведение операции, а не доступность сайта.
"""
from __future__ import annotations

import json
import pathlib

import pytest

from factory.cell import nginx_indexing
from factory.cell import queue as q
from factory.qwen import editorial, indexing, registry

ДОМЕН = "t.example"
САЙТ = "test-01"


def _репозиторий(tmp: pathlib.Path) -> str:
    """Подставной репозиторий сайта: по его точке входа выводится семейство.

    Семейство — не выдумка инструмента: оно берётся из `config/site.json`
    репозитория, и без него контракт режима неизвестен. Поэтому в песочнице
    репозиторий настоящий, просто свой.
    """
    репо = tmp / "var" / "site-repos" / САЙТ
    (репо / "config").mkdir(parents=True, exist_ok=True)
    (репо / "config" / "site.json").write_text(json.dumps({
        "site_id": САЙТ, "domain": ДОМЕН, "entrypoint": "lords-frontend.py",
    }, ensure_ascii=False), encoding="utf-8")
    return f"var/site-repos/{САЙТ}"


def _реестр(tmp: pathlib.Path, *, разрешено: bool) -> pathlib.Path:
    п = tmp / "site-cells.json"
    п.write_text(json.dumps({"cells": [{
        "site_id": САЙТ, "domain": ДОМЕН,
        "repo": {"path": _репозиторий(tmp)},
        "runtime": {"account": САЙТ, "port": 9999,
                    "unit": f"nova-{САЙТ}.service"},
        "template": {"template_id": "lords-animation"},
        "indexing": ({"open_authorized": True, "reason": "тестовый сайт"}
                     if разрешено else
                     {"desired_state": "CLOSED", "reason": "разрешения нет"}),
    }]}, ensure_ascii=False), encoding="utf-8")
    return п


def _выпуск(tmp: pathlib.Path, *, разрешает: bool) -> pathlib.Path:
    """Каталог «выложенного» выпуска с читателем и конфигурацией."""
    выпуск = tmp / "srv" / САЙТ / "current"
    (выпуск / "src").mkdir(parents=True)
    (выпуск / "config").mkdir(parents=True)
    общий = pathlib.Path(__file__).resolve().parents[2] / "automation" / "host" \
        / "indexing_mode.py"
    (выпуск / "src" / "indexing_mode.py").write_bytes(общий.read_bytes())
    (выпуск / "src" / "lords-frontend.py").write_text(
        "import indexing_mode  # читатель подключён\n", encoding="utf-8")
    (выпуск / "config" / "site.json").write_text(json.dumps({
        "site_id": САЙТ, "domain": ДОМЕН, "entrypoint": "lords-frontend.py",
        "indexing": {"release_permits_open": разрешает},
    }, ensure_ascii=False), encoding="utf-8")
    return выпуск


def _nginx(tmp: pathlib.Path, *, запрещает: bool) -> pathlib.Path:
    корень = tmp / "nginx"
    (корень / "lords").mkdir(parents=True)
    (корень / "cells").mkdir(parents=True)
    перем = nginx_indexing.имя_переменной(САЙТ)
    включаемый = корень / "cells" / f"{САЙТ}.robots"
    строка = (nginx_indexing.ФИКСИРОВАННАЯ if запрещает
              else f"add_header X-Robots-Tag ${перем} always;")
    объявление = ("" if запрещает else
                  f"map $uri ${перем} {{\n    include {включаемый};\n}}\n\n")
    (корень / "lords" / f"{САЙТ}.conf").write_text(
        объявление +
        "server {\n"
        f"    server_name {ДОМЕН};\n"
        f"    {строка}\n"
        "    location / { proxy_pass http://127.0.0.1:9999; }\n"
        "}\n", encoding="utf-8")
    if not запрещает:
        включаемый.write_text('default "";\n', encoding="utf-8")
    return корень


class Очередь:
    """Подставная очередь: записывает заявки и МЕНЯЕТ состояние слоя.

    Исполнитель здесь не настоящий, но его роль та же: по заявке он
    переключает слой. Иначе проверялась бы не петля операции, а набор
    подмен — и «слой переключился» нельзя было бы отличить от «мы так
    сказали».
    """

    def __init__(self, слой: dict, исход: str = "applied"):
        self.заявки: list[dict] = []
        self.исход = исход
        self.слой = слой

    def собрать(self, site_id, commit, digest, **kw):
        return q.собрать(site_id, commit, digest, **kw)

    def подать(self, заявка, **kw):
        self.заявки.append(заявка.as_dict())
        if self.исход == "applied":
            self.слой["режим"] = заявка.mode
        return {"status": "queued", "request_id": заявка.request_id}

    def состояние(self, request_id):
        return {"status": "finished",
                "result": {"status": "ok" if self.исход == "applied" else "rejected",
                           "outcome": {"status": self.исход},
                           "error": "" if self.исход == "applied"
                                    else "nginx -t отказал"}}


@pytest.fixture
def площадка(tmp_path, monkeypatch):
    """Изолированная площадка. Возвращает функцию настройки сценария."""
    def собрать_площадку(*, разрешено: bool, разрешает_выпуск: bool,
                         nginx_запрещает: bool, публично: str,
                         исход_очереди: str = "applied") -> dict:
        # Корень фабрики — песочница: по нему реестр находит репозиторий сайта,
        # а по его точке входа — семейство и контракт режима.
        monkeypatch.setattr(registry, "КОРЕНЬ", tmp_path)
        monkeypatch.setattr(registry, "РЕЕСТР_ЯЧЕЕК",
                            _реестр(tmp_path, разрешено=разрешено))
        # Сетевой список — пустой, но ЧИТАЕМЫЙ: нечитаемый теперь честно
        # отказывает, а здесь проверяется операция, а не доступность файла.
        сетевой = tmp_path / "network-allowlist.yaml"
        сетевой.write_text("targets: []\n", encoding="utf-8")
        monkeypatch.setattr(registry, "СЕТЕВОЙ_СПИСОК", сетевой)
        # Ни одного обращения к сети: страница отвечает канонически.
        monkeypatch.setattr(registry, "_страница",
                            lambda url, таймаут=15: ("200", "<html></html>"))
        выпуск = _выпуск(tmp_path, разрешает=разрешает_выпуск)
        monkeypatch.setattr(indexing, "корни_выпуска",
                            lambda аккаунт: (str(выпуск),))
        monkeypatch.setattr(nginx_indexing, "КОРЕНЬ_NGINX",
                            _nginx(tmp_path, запрещает=nginx_запрещает))
        monkeypatch.setattr(nginx_indexing, "КАТАЛОГ_ВКЛЮЧАЕМЫХ",
                            tmp_path / "nginx" / "cells")
        monkeypatch.setattr(indexing, "ЖУРНАЛ", tmp_path / "log")
        monkeypatch.setattr(indexing, "порт_приложения", lambda site_id: 0)
        # Публичные сигналы задаёт сценарий: проверяется операция, а не сеть.
        состояние_сети = {"режим": публично}

        def сигналы(домен, *, порт=0):
            закрыт = состояние_сети["режим"] == "CLOSED"
            return {
                "domain": домен, "at": "тест",
                "home_http": "200",
                "x_robots_values": (["noindex, nofollow"] if закрыт else []),
                "x_robots_count": 1 if закрыт else 0,
                "x_robots_values_http80": [],
                "x_robots_count_service": 1 if закрыт else 1,
                "meta_robots_home": ("noindex, nofollow" if закрыт
                                     else "index, follow"),
                "canonical_home": f"https://{домен}/",
                "robots_txt": ("User-agent: *\nDisallow: /\n" if закрыт
                               else "User-agent: *\nAllow: /\n"),
                "robots_txt_http": "200", "sitemap_http": "404",
                "service_path": "/healthz", "service_path_http": "200",
                "x_robots_values_service": ["noindex, nofollow"],
            }
        monkeypatch.setattr(indexing, "сигналы", сигналы)
        слой = {"режим": "CLOSED" if nginx_запрещает else "OPEN"}

        def слой_nginx(site_id, домен, сиг=None):
            закрыт = слой["режим"] == "CLOSED"
            return {"site_id": site_id, "mode": "closed" if закрыт else "open",
                    "denying": закрыт,
                    "managed_by_this_operation": not nginx_запрещает,
                    "evidence": f"песочница: слой {слой['режим']}"}
        monkeypatch.setattr(indexing, "слой_nginx", слой_nginx)
        очередь = Очередь(слой, исход_очереди)
        monkeypatch.setattr(q, "подать", очередь.подать)
        monkeypatch.setattr(q, "состояние", очередь.состояние)
        return {"корень_состояния": tmp_path / "indexing", "очередь": очередь,
                "сеть": состояние_сети, "слой": слой, "выпуск": выпуск,
                "tmp": tmp_path}
    return собрать_площадку


# --- 1. отказ без разрешения владельца -------------------------------------

def test_без_разрешения_владельца_операция_отказывает(площадка):
    п = площадка(разрешено=False, разрешает_выпуск=True,
                 nginx_запрещает=False, публично="CLOSED")
    with pytest.raises(indexing.Отказано) as ош:
        indexing.установить(ДОМЕН, mode="open", author="тест",
                            корень=п["корень_состояния"])
    assert "владелец не разрешал открытие" in str(ош.value)
    # Ни файла состояния, ни заявки в очередь.
    assert not (п["корень_состояния"] / f"{ДОМЕН}.json").exists()
    assert п["очередь"].заявки == []


# --- 2. отказ при несовпадении ожидаемого выпуска --------------------------

def test_несовпадение_ожидаемого_выпуска_останавливает(площадка):
    п = площадка(разрешено=True, разрешает_выпуск=True,
                 nginx_запрещает=False, публично="CLOSED")
    with pytest.raises(indexing.Отказано) as ош:
        indexing.установить(ДОМЕН, mode="open", author="тест",
                            expect_release="deadbeef1234",
                            корень=п["корень_состояния"])
    текст = str(ош.value)
    assert "ожидался" in текст and "deadbeef1234" in текст
    assert not (п["корень_состояния"] / f"{ДОМЕН}.json").exists()
    assert п["очередь"].заявки == []


# --- 3. открытие и закрытие разрешённого сайта -----------------------------

def test_открытие_и_закрытие_разрешённого_сайта(площадка):
    """Петля целиком: заявка в очередь, слой переключён, ответ подтверждён."""
    п = площадка(разрешено=True, разрешает_выпуск=True,
                 nginx_запрещает=True, публично="CLOSED")
    assert п["слой"]["режим"] == "CLOSED"

    # Открытие. Публичный ответ станет открытым, как только слой переключён —
    # ровно это и означает «подтверждено на live».
    п["сеть"]["режим"] = "OPEN"
    итог = indexing.установить(ДОМЕН, mode="open", author="тест",
                               корень=п["корень_состояния"])
    assert итог["confirmed"] is True, итог
    assert итог["changed"] is True and итог["revision"] == 1
    assert итог["nginx_switch"]["needed"] is True
    assert итог["nginx_switch"]["before"]["denying"] is True
    assert итог["nginx_switch"]["after"]["denying"] is False
    заявка = п["очередь"].заявки[-1]
    assert заявка["operation"] == "indexing-nginx"
    assert заявка["mode"] == "OPEN" and заявка["site_id"] == САЙТ
    assert заявка["commit"] == "" and заявка["digest"] == "", (
        "операция слоя кода не ставит: коммит и digest ей не нужны")
    assert п["слой"]["режим"] == "OPEN"
    состояние = json.loads(
        (п["корень_состояния"] / f"{ДОМЕН}.json").read_text("utf-8"))
    assert состояние["desired_state"] == "OPEN"
    assert состояние["revision"] == 1

    # Закрытие — ТЕМ ЖЕ интерфейсом, без второго инструмента.
    п["сеть"]["режим"] = "CLOSED"
    итог2 = indexing.установить(ДОМЕН, mode="closed", author="тест",
                                корень=п["корень_состояния"])
    assert итог2["confirmed"] is True, итог2
    assert итог2["revision"] == 2
    assert итог2["nginx_switch"]["needed"] is True
    assert итог2["nginx_switch"]["after"]["denying"] is True
    assert п["очередь"].заявки[-1]["mode"] == "CLOSED"
    assert п["слой"]["режим"] == "CLOSED"
    assert json.loads((п["корень_состояния"] / f"{ДОМЕН}.json")
                      .read_text("utf-8"))["desired_state"] == "CLOSED"


# --- 4. частичный сбой с восстановлением -----------------------------------

def test_частичный_сбой_возвращает_исходное_состояние(площадка):
    """Исполнитель отказал на слое — состояние приложения возвращается."""
    п = площадка(разрешено=True, разрешает_выпуск=True,
                 nginx_запрещает=True, публично="CLOSED",
                 исход_очереди="rejected")
    with pytest.raises(indexing.Отказано) as ош:
        indexing.установить(ДОМЕН, mode="open", author="тест",
                            корень=п["корень_состояния"])
    assert "не применил слой nginx" in str(ош.value)
    # Файла состояния не осталось: до операции его не было.
    assert not (п["корень_состояния"] / f"{ДОМЕН}.json").exists()
    # И восстановление записано в журнал операций.
    журнал = (п["корень_состояния"] / "_log" / "operations.jsonl")
    if журнал.exists():
        записи = [json.loads(с) for с in журнал.read_text("utf-8").splitlines() if с]
        assert any(з.get("op") == "restore" for з in записи), записи


def test_слой_переключился_но_остался_закрытым_возврат(площадка):
    """Исполнитель ответил «применено», а слой всё ещё запрещает."""
    п = площадка(разрешено=True, разрешает_выпуск=True,
                 nginx_запрещает=True, публично="CLOSED",
                 исход_очереди="nothing-to-do")
    with pytest.raises(indexing.Отказано) as ош:
        indexing.установить(ДОМЕН, mode="open", author="тест",
                            корень=п["корень_состояния"])
    текст = str(ош.value)
    assert "остался" in текст and "возвращено" in текст
    assert not (п["корень_состояния"] / f"{ДОМЕН}.json").exists()


# --- 5. повтор без непредусмотренных изменений -----------------------------

def test_повтор_в_том_же_режиме_ничего_не_меняет(площадка):
    п = площадка(разрешено=True, разрешает_выпуск=True,
                 nginx_запрещает=False, публично="OPEN")
    первый = indexing.установить(ДОМЕН, mode="open", author="тест",
                                 корень=п["корень_состояния"])
    assert первый["changed"] is True
    файл = п["корень_состояния"] / f"{ДОМЕН}.json"
    было = файл.read_text("utf-8")
    время = файл.stat().st_mtime_ns
    заявок = len(п["очередь"].заявки)

    второй = indexing.установить(ДОМЕН, mode="open", author="тест",
                                 корень=п["корень_состояния"])
    assert второй["changed"] is False
    assert "запись не велась" in второй["note"]
    assert файл.read_text("utf-8") == было, "повтор не вправе менять файл"
    assert файл.stat().st_mtime_ns == время, "и не вправе двигать его время"
    assert len(п["очередь"].заявки) == заявок, (
        "повтор не вправе подавать вторую заявку на слой")
