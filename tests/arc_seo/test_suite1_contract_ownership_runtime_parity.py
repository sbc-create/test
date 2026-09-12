"""Suite 1: contract_ownership_runtime_parity.

Доказывает, что объявленное и работающее — одно и то же, а роли разведены.
"""
from __future__ import annotations

import hashlib
import json
import os
import urllib.error
import urllib.request
from pathlib import Path

import pytest

from factory.site_engine.changeset import model as CM
from factory.site_engine.seo_authoring import schema as SCH
from factory.site_engine.seo_authoring import адаптер_подключён, подключить_адаптер
from factory.site_engine.seo_authoring.testing import собрать_заявку

КОРЕНЬ = Path(__file__).resolve().parents[2]
КАНДИДАТ = КОРЕНЬ / "contracts/control-plane/1.3.2"
ПРЕЖНИЙ = КОРЕНЬ / "contracts/control-plane/1.3.1"
БАЗА = os.environ.get("CANDIDATE_API_BASE", "")


def прочитать(путь: Path):
    return json.loads(путь.read_text(encoding="utf-8"))


def гет(путь: str):
    with urllib.request.urlopen(БАЗА + путь, timeout=20) as о:
        return о.status, json.loads(о.read() or b"{}")


# --- ресурс существует в каноническом наборе --------------------------------

def test_s1_01_вид_ресурса_в_матрице_владения():
    м = прочитать(КАНДИДАТ / "ownership-matrix.json")
    запись = next((r for r in м["resources"]
                   if r["resource"] == SCH.RESOURCE_KIND), None)
    assert запись is not None, "вида ресурса нет в матрице кандидата"
    assert запись["single_writer"] == "control-plane"
    assert запись["domain_owner"] == "seo"
    assert запись["content_author"] == "qwen"
    assert запись["approver"] != запись["requester"], \
        "одобряющий совпал с заказчиком"


def test_s1_02_строгая_схема_существует_и_закрыта():
    с = прочитать(КАНДИДАТ / "schemas" / "SeoContentProposal.v1.json")
    assert с["additionalProperties"] is False, "схема открыта для лишних полей"
    assert set(SCH.ОБЯЗАТЕЛЬНЫЕ) <= set(с["required"])
    for поле in SCH.ВЫВОДИМЫЕ:
        assert поле in с["properties"], f"{поле} не описан"
        assert поле not in с["required"], \
            f"{поле} выводится сервером и обязательным быть не может"
    # Поля, от которых зависит безопасность, обязательны — не опциональны.
    for поле in ("source_snapshot_sha256", "artifact_digest", "requested_by",
                 "idempotency_key", "policy_version"):
        assert поле in с["required"], f"{поле} обязано быть обязательным"


def test_s1_03_схема_реально_валидирует_рантайм(реестр, артефакты, модель):
    """Схема из набора и проверка в коде — одно и то же, а не два мнения."""
    jsonschema = pytest.importorskip("jsonschema")
    с = прочитать(КАНДИДАТ / "schemas" / "SeoContentProposal.v1.json")
    валидатор = jsonschema.Draft202012Validator(с)
    заявка = собрать_заявку(реестр=реестр, артефакты=артефакты, модель=модель)
    # Рантайм принимает.
    assert SCH.проверить(заявка)
    # И схема набора принимает то же самое.
    ошибки = sorted(валидатор.iter_errors(заявка), key=str)
    assert not ошибки, [e.message for e in ошибки][:3]
    # И отвергает то же самое: лишнее поле.
    плохая = dict(заявка, неизвестное_поле="x")
    assert list(валидатор.iter_errors(плохая)), "схема набора приняла лишнее поле"
    with pytest.raises(SCH.ProposalRejected) as ош:
        SCH.проверить(плохая)
    assert ош.value.error_code == "FIELD_UNKNOWN"


# --- каталог и матрица согласованы ------------------------------------------

def test_s1_04_каталог_и_матрица_согласованы():
    к = прочитать(КАНДИДАТ / "capability-catalog.json")
    м = прочитать(КАНДИДАТ / "ownership-matrix.json")
    имена = {c.get("capability_id") or c.get("id"): c for c in к["capabilities"]}
    assert "seo.content.proposal" in имена
    assert имена["seo.content.proposal"]["status"] == "AVAILABLE"
    assert имена["changeset.adapter.seo"]["status"] == "AVAILABLE", \
        "адаптер объявлен недоступным, хотя путь исполняется"
    запись = next(r for r in м["resources"] if r["resource"] == SCH.RESOURCE_KIND)
    # Владелец в каталоге и писатель в матрице — про одну и ту же службу.
    assert имена["seo.content.proposal"]["owner_service"] == запись["single_writer"]


def test_s1_05_писатель_ровно_один():
    м = прочитать(КАНДИДАТ / "ownership-matrix.json")
    по_ресурсу: dict[str, set] = {}
    for r in м["resources"]:
        по_ресурсу.setdefault(r["resource"], set()).add(r["single_writer"])
    двойные = {k: v for k, v in по_ресурсу.items() if len(v) > 1}
    assert not двойные, f"ресурсы с двумя писателями: {двойные}"
    запись = next(r for r in м["resources"] if r["resource"] == SCH.RESOURCE_KIND)
    assert isinstance(запись["single_writer"], str)
    assert запись["single_writer"] == CM.ЕДИНСТВЕННЫЙ_ПИСАТЕЛЬ[SCH.RESOURCE_KIND], \
        "матрица контракта и матрица кода называют разных писателей"


def test_s1_06_роли_разведены():
    м = прочитать(КАНДИДАТ / "ownership-matrix.json")
    з = next(r for r in м["resources"] if r["resource"] == SCH.RESOURCE_KIND)
    роли = {"requester": з["requester"], "writer": з["single_writer"],
            "approver": з["approver"], "executor": з["executor"],
            "author": з["content_author"]}
    assert роли["requester"] != роли["approver"], "заказчик и одобряющий совпали"
    assert роли["author"] != роли["writer"], "автор содержимого стал писателем"
    assert роли["author"] != роли["approver"], "автор содержимого одобряет"


# --- границы Qwen ------------------------------------------------------------

def test_s1_07_qwen_не_постоянный_писатель():
    м = прочитать(КАНДИДАТ / "ownership-matrix.json")
    писатели = {r["resource"]: r["single_writer"] for r in м["resources"]}
    qwen_пишет = [k for k, v in писатели.items() if v == "qwen"]
    assert not qwen_пишет, f"qwen объявлен писателем ресурсов: {qwen_пишет}"
    # И противоречие 1.3.1 действительно устранено, а не обойдено.
    прежние = {r["resource"]: r["single_writer"]
               for r in прочитать(ПРЕЖНИЙ / "ownership-matrix.json")["resources"]}
    assert прежние.get("qwen.proposal") == "qwen", "предпосылка изменилась"
    assert писатели.get("qwen.proposal") == "control-plane"


def test_s1_08_qwen_не_имеет_исполнительных_ролей():
    assert CM.роли_службы("qwen") == frozenset({CM.PROPOSER})
    for роль in (CM.APPROVER, CM.EXECUTOR, CM.VALIDATOR, CM.OPERATOR):
        assert роль not in CM.роли_службы("qwen")
    for действие in ("approve", "apply", "rollback", "grant_authority"):
        assert действие in CM.ЗАПРЕЩЕНО_МОДЕЛИ


def test_s1_09_каталог_не_даёт_qwen_записи_и_секретов():
    к = прочитать(КАНДИДАТ / "capability-catalog.json")
    for c in к["capabilities"]:
        if c.get("owner_service") != "qwen":
            continue
        области = set(c.get("required_scopes") or [])
        запретные = {s for s in области
                     if any(x in s for x in ("write", "approve", "apply",
                                             "execute", "secret", "admin"))}
        assert not запретные, f"{c.get('capability_id')}: {запретные}"
        assert c.get("command_endpoint") in (None, ""), \
            "у qwen объявлена командная поверхность"


# --- кандидатский рантайм ----------------------------------------------------

@pytest.mark.skipif(not БАЗА, reason="кандидатский экземпляр не поднят")
def test_s1_10_рантайм_обслуживает_кандидатский_набор():
    к, версия = гет("/api/v1/control-plane/version")
    assert к == 200
    assert версия["control_plane_version"] == "1.3.2", версия
    к2, каталог = гет("/api/v1/capabilities")
    assert к2 == 200
    assert каталог["bundle_version"] == "1.3.2"
    имена = {c.get("capability_id") or c.get("id") for c in каталог["capabilities"]}
    assert "seo.content.proposal" in имена
    адаптер = next(c for c in каталог["capabilities"]
                   if (c.get("capability_id") or c.get("id")) == "changeset.adapter.seo")
    assert адаптер["status"] == "AVAILABLE"


@pytest.mark.skipif(not БАЗА, reason="кандидатский экземпляр не поднят")
def test_s1_11_схема_отдаётся_рантаймом():
    к, с = гет("/api/v1/contracts/schemas/SeoContentProposal.v1")
    assert к == 200, с
    assert с["additionalProperties"] is False
    # Отданное рантаймом совпадает с файлом набора побайтно по содержанию.
    файл = прочитать(КАНДИДАТ / "schemas" / "SeoContentProposal.v1.json")
    assert с == файл, "рантайм отдаёт не то, что лежит в наборе"


@pytest.mark.skipif(not БАЗА, reason="кандидатский экземпляр не поднят")
def test_s1_12_цепочка_коммит_артефакт_рантайм():
    """Один и тот же набор в источнике, в артефакте и в рантайме."""
    суммы = прочитать(КАНДИДАТ / "checksums.json")
    общий = hashlib.sha256(
        json.dumps(суммы["files"], sort_keys=True).encode()).hexdigest()
    объявленный = os.environ.get("CANDIDATE_BUNDLE_SHA256", "")
    assert объявленный, "отпечаток кандидата не передан прогоном"
    assert общий == объявленный, "отпечаток набора разошёлся с переданным"
    к, каталог = гет("/api/v1/capabilities")
    файл = прочитать(КАНДИДАТ / "capability-catalog.json")
    assert каталог == файл, "рантайм обслуживает не тот каталог"


# --- обратная совместимость --------------------------------------------------

def test_s1_13_ресурсы_1_3_1_не_тронуты():
    старая = {r["resource"]: r for r in
              прочитать(ПРЕЖНИЙ / "ownership-matrix.json")["resources"]}
    новая = {r["resource"]: r for r in
             прочитать(КАНДИДАТ / "ownership-matrix.json")["resources"]}
    assert set(старая) <= set(новая), "ресурсы исчезли"
    for имя, было in старая.items():
        стало = новая[имя]
        # Единственное исправление названо отдельно и обосновано в
        # COMPATIBILITY: qwen не был вправе быть писателем и по политике 1.3.1.
        if имя == "qwen.proposal":
            assert стало["single_writer"] == "control-plane"
            continue
        assert стало["single_writer"] == было["single_writer"], имя
        assert set(было["fields"]) <= set(стало["fields"]), имя


def test_s1_14_новые_поля_не_ломают_старых_потребителей():
    """Старый потребитель читает только знакомые ключи и не спотыкается."""
    старая = прочитать(ПРЕЖНИЙ / "ownership-matrix.json")
    новая = прочитать(КАНДИДАТ / "ownership-matrix.json")
    знакомые = set(старая["resources"][0])
    for r in новая["resources"]:
        # Все ключи, которые старый потребитель обязан найти, на месте.
        assert знакомые <= set(r), f"{r['resource']}: не хватает {знакомые - set(r)}"
    политика = прочитать(КАНДИДАТ / "manifest.json")["compatibility_policy"]
    assert политика["consumers_must_tolerate_unknown_optional"] is True
    assert политика["additive_optional_ok_within_major"] is True


def test_s1_15_каналы_1_3_1_остались_доступны():
    было = {k for k, v in прочитать(ПРЕЖНИЙ / "asyncapi.json")["channels"].items()
            if v["subscribe"].get("x-status") == "AVAILABLE"}
    стало = {k for k, v in прочитать(КАНДИДАТ / "asyncapi.json")["channels"].items()
             if v["subscribe"].get("x-status") == "AVAILABLE"}
    assert было <= стало, f"каналы потеряли доступность: {sorted(было - стало)}"


def test_s1_16_адаптер_подключается_и_объявляет_того_же_владельца(tmp_path):
    подключить_адаптер(tmp_path / "probe.sqlite3")
    assert адаптер_подключён()
    from factory.site_engine.changeset import adapter as A
    а = A.получить(SCH.RESOURCE_KIND)
    assert а.owner_service == CM.ЕДИНСТВЕННЫЙ_ПИСАТЕЛЬ[SCH.RESOURCE_KIND]
    возм = а.capabilities()
    assert возм["supports_dry_run"] and возм["supports_rollback"]
    assert возм["live_writes"] is False, "адаптер объявляет живые записи"
