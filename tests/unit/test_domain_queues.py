"""Очереди по доменам: по одной на домен, без выдуманных задач.

Задание владельца требует, чтобы у каждого активного домена была СВОЯ очередь и
назначенный исполнитель, и чтобы ни один популярный сайт не занимал всю работу.
Здесь это закреплено проверками, а не обещанием. Отдельно закреплён отказ от
привязки недостатка к домену по тексту: она дважды дала ложную область.
"""
from __future__ import annotations

import importlib.util
import json
import pathlib

import pytest

jsonschema = pytest.importorskip("jsonschema")

КОРЕНЬ = pathlib.Path(__file__).resolve().parents[2]
СПИСОК = КОРЕНЬ / "config" / "active-domains.json"
СХЕМА = КОРЕНЬ / "schemas" / "domain-queue.schema.json"
ОЧЕРЕДИ = КОРЕНЬ / "config" / "domain-queues"

_сп = importlib.util.spec_from_file_location(
    "make_domain_queues",
    КОРЕНЬ / "automation" / "local" / "make-domain-queues.py")
сборка = importlib.util.module_from_spec(_сп)
_сп.loader.exec_module(сборка)


@pytest.fixture(scope="module")
def активные() -> list[dict]:
    return json.loads(СПИСОК.read_text(encoding="utf-8"))["domains"]


@pytest.fixture(scope="module")
def очереди() -> dict[str, dict]:
    return {ф.stem: json.loads(ф.read_text(encoding="utf-8"))
            for ф in sorted(ОЧЕРЕДИ.glob("*.json"))}


# --- наличие и согласованность -------------------------------------------

def test_у_каждого_активного_домена_есть_очередь(активные, очереди):
    нет = [з["domain"] for з in активные if з["domain"] not in очереди]
    assert not нет, нет


def test_очередей_не_больше_чем_домéнов(активные, очереди):
    """Очередь без домена — забытый файл, который будут читать как работу."""
    лишние = sorted(set(очереди) - {з["domain"] for з in активные})
    assert not лишние, лишние


def test_каждая_очередь_проходит_схему(очереди):
    схема = json.loads(СХЕМА.read_text(encoding="utf-8"))
    jsonschema.Draft7Validator.check_schema(схема)
    v = jsonschema.Draft7Validator(схема)
    плохие = {и: [о.message for о in v.iter_errors(о_)][:2]
              for и, о_ in очереди.items()
              if list(v.iter_errors(о_))}
    assert not плохие, плохие


def test_очередь_знает_свой_домен_и_семейство(активные, очереди):
    по_домену = {з["domain"]: з for з in активные}
    расхождения = {}
    for имя, о in очереди.items():
        ж = по_домену[имя]
        if (о["domain"], о["site_id"], о["family"]) != (
                ж["domain"], ж["site_id"], ж["family"]):
            расхождения[имя] = (о["site_id"], о["family"])
    assert not расхождения, расхождения


def test_у_каждой_очереди_назван_исполнитель(очереди):
    без = [и for и, о in очереди.items() if not о.get("executor")]
    assert not без, без


def test_у_каждой_очереди_есть_хотя_бы_одна_задача(очереди):
    """Пустая очередь означала бы домен без следующего шага."""
    пустые = [и for и, о in очереди.items() if not о["tasks"]]
    assert not пустые, пустые


def test_идентификаторы_задач_уникальны_внутри_домена(очереди):
    повторы = {}
    for имя, о in очереди.items():
        ид = [з["id"] for з in о["tasks"]]
        if len(set(ид)) != len(ид):
            повторы[имя] = ид
    assert not повторы, повторы


def test_каждая_задача_несёт_доказательство(очереди):
    """Утверждение без доказательства задачей не является."""
    плохие = [(и, з["id"]) for и, о in очереди.items() for з in о["tasks"]
              if len(з.get("evidence") or "") < 10]
    assert not плохие, плохие


def test_ссылка_на_недостаток_существует_в_реестре(очереди):
    реестр = json.loads(
        (КОРЕНЬ / "config" / "seo-module-defects.json").read_text(
            encoding="utf-8"))
    есть = {з["id"] for з in реестр["defects"]}
    битые = [(и, з["defect"]) for и, о in очереди.items() for з in о["tasks"]
             if з.get("defect") and з["defect"] not in есть]
    assert not битые, битые


def test_этап_первый_только_при_открытом_препятствии(очереди):
    """Исправному сайту искусственная задержка перед ростом не создаётся."""
    без_причины = [и for и, о in очереди.items()
                   if о["stage"] == 1 and "препятств" not in о["stage_reason"]
                   and "не измерено" not in о["stage_reason"]]
    assert not без_причины, без_причины


def test_работа_не_выдаётся_за_результат(очереди):
    """Опубликованная задача обязана назвать живой адрес."""
    плохие = [(и, з["id"]) for и, о in очереди.items() for з in о["tasks"]
              if з["state"] in ("опубликовано", "эффект измерен")
              and not з.get("published_url")]
    assert not плохие, плохие


# --- привязка недостатка к домену: только по разметке ---------------------

def test_неразмеченный_недостаток_не_приписывается_никому():
    з = {"id": "MOD-99", "state": "measured", "priority": "P1",
         "title": "дефект на a.test", "verify_live": "проверять на a.test"}
    assert сборка.касается(з, "a.test") is False


def test_размеченная_область_решает():
    з = {"id": "MOD-99", "state": "measured", "priority": "P1",
         "title": "дефект", "domains": ["a.test"]}
    assert сборка.касается(з, "a.test") is True
    assert сборка.касается(з, "b.test") is False


def test_домен_названный_исключением_в_область_не_попадает():
    """Ровно та ошибка, из-за которой привязка по тексту отменена.

    Заголовок MOD-114 называет `zonafilm.cc` единственной витриной, которая
    делает ПРАВИЛЬНО, — и привязка по тексту объявляла её пострадавшей.
    """
    з = {"id": "MOD-114", "state": "measured", "priority": "P1",
         "title": ("an1meg0.site и an1mego.site отдают одну главную;"
                   " и только zonafilm.cc его разводит"),
         "domains": ["an1meg0.site", "an1mego.site"]}
    assert сборка.касается(з, "zonafilm.cc") is False
    assert сборка.касается(з, "an1meg0.site") is True


def test_закрытый_недостаток_в_очередь_не_идёт():
    все = [{"id": "MOD-1", "state": "verified", "priority": "P0",
            "title": "закрыт", "domains": ["a.test"]},
           {"id": "MOD-2", "state": "measured", "priority": "P1",
            "title": "открыт", "domains": ["a.test"]}]
    найдено = сборка.недостатки_домена(все, "a.test")
    assert [з["id"] for з in найдено] == ["MOD-2"]


def test_недостатки_сортируются_по_весу():
    все = [{"id": "MOD-2", "state": "measured", "priority": "P2",
            "title": "t", "domains": ["a.test"]},
           {"id": "MOD-1", "state": "measured", "priority": "P0",
            "title": "t", "domains": ["a.test"]}]
    assert [з["id"] for з in сборка.недостатки_домена(все, "a.test")] == [
        "MOD-1", "MOD-2"]


# --- этап -----------------------------------------------------------------

def test_без_замера_этап_первый():
    ступень, причина = сборка.этап([], None)
    assert ступень == 1
    assert "не измерено" in причина


def test_открытое_P0_даёт_первый_этап():
    ступень, причина = сборка.этап(
        [{"id": "MOD-1", "priority": "P0"}], {"код": "200"})
    assert ступень == 1
    assert "MOD-1" in причина


def test_только_P2_не_задерживает_рост():
    ступень, причина = сборка.этап(
        [{"id": "MOD-9", "priority": "P2"}], {"код": "200"})
    assert ступень == 2
    assert "не блокируют" in причина


def test_исправный_сайт_сразу_на_втором_этапе():
    ступень, причина = сборка.этап([], {"код": "200"})
    assert ступень == 2
    assert "задержка" in причина
