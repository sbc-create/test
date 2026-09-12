"""SUITE_1 — жизненный цикл credentials, личности и защита службы подписи.

Проверяются следствия: отзывает ли ротация прежние значения, принимает ли
верификатор что-либо кроме выданного, различает ли журнал производителей и
можно ли уговорить службу подписи заверить не то.
"""
from __future__ import annotations

import datetime as _d
import hashlib
import json
import urllib.error
import urllib.request

import pytest

from factory.site_engine.approval import service as SIGNER
from factory.site_engine.audit import ledger_identity as ident
from factory.site_engine.audit import ledger_store as store
from factory.site_engine.changeset import engine as E
from factory.site_engine.changeset import fake_adapter as FA
from factory.site_engine.changeset import model as M
from factory.site_engine.changeset import store as S
from factory.site_engine.credentials import provision as PR

from .conftest import через_час


# =============================================================================
# A. Жизненный цикл учётных данных
# =============================================================================

@pytest.fixture()
def корень(tmp_path, monkeypatch):
    к = tmp_path / "cred"
    monkeypatch.setattr(PR, "КОРЕНЬ", к)
    monkeypatch.setattr(PR, "СТАРЫЙ_ОБЩИЙ", tmp_path / "нет.env")
    return к


class TestЖизненныйЦикл:
    def test_ротация_отзывает_прежние_значения(self, корень):
        до = PR.выдать(ротировать=True)
        реестр_до = json.loads((корень / PR.ОТПЕЧАТКИ).read_text("utf-8"))
        прежние = set(реестр_до["services"].values())
        после = PR.выдать(ротировать=True)
        реестр = json.loads((корень / PR.ОТПЕЧАТКИ).read_text("utf-8"))
        assert прежние <= set(реестр["revoked"]), "прежние значения не отозваны"
        assert до.активный_kid in после.отозванные_kid

    def test_действующее_значение_никогда_не_отозвано(self, корень):
        PR.выдать(ротировать=True)
        PR.выдать(ротировать=True)
        р = json.loads((корень / PR.ОТПЕЧАТКИ).read_text("utf-8"))
        assert not (set(р["services"].values()) & set(р["revoked"]))

    def test_ensure_не_ротирует(self, корень):
        a = PR.выдать(ротировать=False)
        b = PR.выдать(ротировать=False)
        assert a.активный_kid == b.активный_kid
        assert b.ротировано == []

    def test_у_каждой_личности_свой_файл(self, корень):
        PR.выдать(ротировать=True)
        имена = {п.name for п in корень.iterdir()}
        for личность in PR.ЛИЧНОСТИ:
            assert f"audit-token-{личность}" in имена
        for вызывающий in PR.ВЫЗЫВАЮЩИЕ:
            assert f"approval-caller-{вызывающий}" in имена
        assert "approval-signer-token" not in имена, (
            "общий токен вызывающего выведен из обращения вместе со схемой")

    def test_общий_токен_вызывающего_отзывается(self, корень):
        PR.выдать(ротировать=True)
        (корень / "approval-signer-token").write_text("прежний-общий",
                                                      encoding="utf-8")
        PR.выдать(ротировать=True)
        р = json.loads((корень / PR.ОТПЕЧАТКИ).read_text("utf-8"))
        отпечаток = hashlib.sha256("прежний-общий".encode()).hexdigest()
        assert отпечаток in р["revoked"]
        assert not (корень / "approval-signer-token").exists()


class TestВерификаторЖурнала:
    """Верификатор — разрешающий список, а не список запретов."""

    def _каталог(self, tmp_path, monkeypatch, службы, отозваны=()):
        к = tmp_path / "credentials"
        к.mkdir(exist_ok=True)
        (к / ident.ОТПЕЧАТКИ).write_text(
            json.dumps({"services": службы, "revoked": list(отозваны)}),
            encoding="utf-8")
        monkeypatch.setenv("CREDENTIALS_DIRECTORY", str(к))
        return к

    def test_сырых_значений_у_верификатора_нет(self, tmp_path, monkeypatch):
        токен = "значение-служебного-токена"
        к = self._каталог(tmp_path, monkeypatch,
                          {"templates": hashlib.sha256(токен.encode()).hexdigest()})
        содержимое = (к / ident.ОТПЕЧАТКИ).read_text("utf-8")
        assert токен not in содержимое
        assert ident.опознать({"authorization": f"Bearer {токен}"})[
            "producer_service"] == "templates"

    @pytest.mark.parametrize("чужое", [
        "старое-значение-из-общего-файла", "", "  ", "произвольная-строка",
        "Bearer", "0" * 64])
    def test_невыданное_значение_отвергается(self, tmp_path, monkeypatch, чужое):
        self._каталог(tmp_path, monkeypatch, {"templates": "a" * 64})
        with pytest.raises(ident.IdentityError) as ош:
            ident.опознать({"authorization": f"Bearer {чужое}"})
        assert ош.value.error_code == "UNAUTHENTICATED"

    def test_отозванное_значение_отличается_от_неизвестного(self, tmp_path,
                                                            monkeypatch):
        токен = "отозванный"
        х = hashlib.sha256(токен.encode()).hexdigest()
        self._каталог(tmp_path, monkeypatch, {"templates": х}, отозваны=[х])
        with pytest.raises(ident.IdentityError) as ош:
            ident.опознать({"authorization": f"Bearer {токен}"})
        assert ош.value.error_code == "TOKEN_REVOKED"


# =============================================================================
# B. Матрица личностей и полномочий
# =============================================================================

class TestМатрицаПолномочий:
    def test_общих_личностей_нет(self):
        assert "control-plane" not in store.ПРАВА_СЛУЖБ, (
            "общая личность двух процессов делает записи журнала "
            "неразличимыми по производителю")
        assert "audit-bridge" in store.ПРАВА_СЛУЖБ
        assert "changeset-worker" in store.ПРАВА_СЛУЖБ

    @pytest.mark.parametrize("служба", ["audit-bridge", "changeset-worker"])
    def test_публикующие_имеют_только_наблюдение(self, служба):
        assert store.ПРАВА_СЛУЖБ[служба] == {"OBSERVE"}, (
            f"{служба} не задаёт authority и фактически пишет наблюдение; "
            f"EXECUTE был бы неиспользуемым полномочием")

    def test_модель_не_получает_исполнительных_полномочий(self):
        assert store.ПРАВА_СЛУЖБ["qwen"] == {"OBSERVE", "PROPOSE"}
        assert ident.ТИП_АКТОРА["qwen"] == "MODEL"
        assert store.ФАЗЫ_ЗАПРЕЩЁННЫЕ_МОДЕЛИ >= {"AUTHORIZED", "SUCCEEDED"}

    def test_рабочий_процесс_не_получает_authorize(self):
        assert M.APPROVER not in M.ПРАВА["control-plane"]
        assert M.ПРАВА["control-plane"] == {M.VALIDATOR, M.EXECUTOR}

    def test_qwen_только_предлагает(self):
        assert M.ПРАВА["qwen"] == {M.PROPOSER}
        assert M.ЗАПРЕЩЕНО_МОДЕЛИ >= {"approve", "apply", "rollback"}

    def test_мост_обязан_назвать_личность(self, monkeypatch):
        from factory.site_engine.changeset import audit_bridge as AB
        monkeypatch.delenv(AB.ПЕРЕМЕННАЯ_ЛИЧНОСТИ, raising=False)
        with pytest.raises(AB.LedgerUnavailable) as ош:
            AB.личность()
        assert AB.ПЕРЕМЕННАЯ_ЛИЧНОСТИ in str(ош.value)

    def test_запасной_личности_нет(self, monkeypatch, tmp_path):
        """При сбое конфигурации служба молчит, а не пишет от чужого имени."""
        from factory.site_engine.changeset import audit_bridge as AB
        monkeypatch.setenv(AB.ПЕРЕМЕННАЯ_ЛИЧНОСТИ, "audit-bridge")
        monkeypatch.setenv("CREDENTIALS_DIRECTORY", str(tmp_path))
        with pytest.raises(AB.LedgerUnavailable) as ош:
            AB._токен()
        assert "CREDENTIAL_MISSING" in str(ош.value)


# =============================================================================
# C. Служба подписи не является сервисом подписи произвольных данных
# =============================================================================

def _запрос(база: str, путь: str, тело: dict, токен: str | None):
    заголовки = {"Content-Type": "application/json"}
    if токен:
        заголовки["Authorization"] = "Bearer " + токен
    зпр = urllib.request.Request(
        база + путь, method="POST",
        data=json.dumps(тело, ensure_ascii=False).encode(), headers=заголовки)
    try:
        with urllib.request.urlopen(зпр, timeout=10) as о:
            return о.status, json.loads(о.read() or b"{}")
    except urllib.error.HTTPError as ош:
        return ош.code, json.loads(ош.read() or b"{}")


def _заявка(site_id="s-1", ключ="k-1"):
    return {"resource_type": "fake.resource", "resource_id": "r-1",
            "operation_type": "update", "target_site_ids": [site_id],
            "idempotency_key": ключ, "correlation_id": "corr-r2",
            "requested_change": {"title": "проба"}}


def _довести(стенд, до: str, *, site_id="s-1", ключ="k-1", monkeypatch=None):
    """Создать набор и довести до нужного состояния каноническим движком."""
    соед = стенд["соед"]
    реестр = стенд["реестр"]
    if реестр.сайт(site_id) is None:
        реестр.добавить(site_id)
    адаптер = FA.FakeAdapter(стенд["tmp"] / "fake.sqlite3")
    создано = S.создать(соед, _заявка(site_id, ключ),
                        producer_service="templates",
                        actor_id="service:templates", actor_type="SERVICE")
    cid = создано["changeset_id"]
    движок = E.Engine(соед, адаптер=адаптер, реестр=реестр,
                      требовать_журнал=False)
    if до == M.PROPOSED:
        return cid, движок
    движок.валидировать(cid, actor_id="service:control-plane",
                        служба="control-plane")
    движок.запросить_одобрение(cid, actor_id="service:templates",
                               служба="templates", expires_at=через_час())
    if до == M.AWAITING_APPROVAL:
        return cid, движок
    движок.одобрить(cid, approver_id="human:owner", служба="human_owner",
                    actor_type="HUMAN", expires_at=через_час())
    return cid, движок


class TestSignerНеОракул:
    def test_01_готовое_тело_не_принимается(self, стенд):
        база = стенд["signer"]["base"]
        токен = стенд["signer"]["caller_tokens"]["control-api"]
        код, тело = _запрос(база, "/approval",
                            {"changeset_id": "x", "body": "что угодно"}, токен)
        assert код == 400 and тело["error_code"] == "RAW_PAYLOAD_REJECTED"

    def test_02_маршрут_подписи_произвольного_удалён(self, стенд):
        база = стенд["signer"]["base"]
        токен = стенд["signer"]["caller_tokens"]["control-api"]
        код, тело = _запрос(база, "/sign", {"body": "что угодно"}, токен)
        assert код == 410 and тело["error_code"] == "RAW_SIGNING_REMOVED"

    def test_03_неизвестный_набор(self, стенд):
        база = стенд["signer"]["base"]
        токен = стенд["signer"]["caller_tokens"]["control-api"]
        код, тело = _запрос(база, "/approval", {
            "changeset_id": "нет-такого", "approver_id": "human:owner",
            "approver_service": "human_owner", "approver_type": "HUMAN",
            "expires_at": через_час()}, токен)
        assert код == 404 and тело["error_code"] == "CHANGESET_NOT_FOUND"

    def test_04_proposed_вместо_awaiting(self, стенд):
        cid, _ = _довести(стенд, M.PROPOSED)
        база = стенд["signer"]["base"]
        токен = стенд["signer"]["caller_tokens"]["control-api"]
        код, тело = _запрос(база, "/approval", {
            "changeset_id": cid, "approver_id": "human:owner",
            "approver_service": "human_owner", "approver_type": "HUMAN",
            "expires_at": через_час()}, токен)
        assert код == 409 and тело["error_code"] == "CHANGESET_STATE_INVALID"

    def test_05_предложивший_не_одобряет_сам_себя(self, стенд):
        cid, _ = _довести(стенд, M.AWAITING_APPROVAL)
        база = стенд["signer"]["base"]
        токен = стенд["signer"]["caller_tokens"]["control-api"]
        код, тело = _запрос(база, "/approval", {
            "changeset_id": cid, "approver_id": "service:templates",
            "approver_service": "human_owner", "approver_type": "HUMAN",
            "expires_at": через_час()}, токен)
        assert код == 403 and тело["error_code"] == "SEPARATION_OF_DUTIES"

    def test_06_модель_не_одобряет(self, стенд):
        cid, _ = _довести(стенд, M.AWAITING_APPROVAL)
        база = стенд["signer"]["base"]
        токен = стенд["signer"]["caller_tokens"]["control-api"]
        код, тело = _запрос(база, "/approval", {
            "changeset_id": cid, "approver_id": "service:qwen",
            "approver_service": "qwen", "approver_type": "MODEL",
            "expires_at": через_час()}, токен)
        assert код == 403 and тело["error_code"] == "MODEL_ACTION_DENIED"

    def test_07_служба_без_роли_approver(self, стенд):
        cid, _ = _довести(стенд, M.AWAITING_APPROVAL)
        база = стенд["signer"]["base"]
        токен = стенд["signer"]["caller_tokens"]["control-api"]
        код, тело = _запрос(база, "/approval", {
            "changeset_id": cid, "approver_id": "service:templates-2",
            "approver_service": "templates", "approver_type": "SERVICE",
            "expires_at": через_час()}, токен)
        assert код == 403 and тело["error_code"] == "ROLE_NOT_GRANTED"

    def test_08_срок_одобрения_ограничен(self, стенд):
        cid, _ = _довести(стенд, M.AWAITING_APPROVAL)
        далеко = (_d.datetime.now(_d.timezone.utc)
                  + _d.timedelta(days=30)).isoformat().replace("+00:00", "Z")
        база = стенд["signer"]["base"]
        токен = стенд["signer"]["caller_tokens"]["control-api"]
        код, тело = _запрос(база, "/approval", {
            "changeset_id": cid, "approver_id": "human:owner",
            "approver_service": "human_owner", "approver_type": "HUMAN",
            "expires_at": далеко}, токен)
        assert код == 422 and тело["error_code"] == "APPROVAL_EXPIRY_TOO_FAR"

    @pytest.mark.parametrize("личность", ["qwen", "templates", "integrations"])
    def test_09_чужая_служба_не_допущена(self, стенд, личность):
        """Qwen, Templates и адаптеры провайдеров службе подписи неизвестны."""
        cid, _ = _довести(стенд, M.AWAITING_APPROVAL)
        база = стенд["signer"]["base"]
        код, тело = _запрос(база, "/approval", {
            "changeset_id": cid, "approver_id": "human:owner",
            "approver_service": "human_owner", "approver_type": "HUMAN",
            "expires_at": через_час()}, f"service-token-{личность}")
        assert код == 401 and тело["error_code"] == "UNAUTHENTICATED"

    def test_10_без_токена_вызывающего(self, стенд):
        cid, _ = _довести(стенд, M.AWAITING_APPROVAL)
        код, тело = _запрос(стенд["signer"]["base"], "/approval",
                            {"changeset_id": cid}, None)
        assert код == 401 and тело["error_code"] == "UNAUTHENTICATED"

    def test_11_исполнитель_не_вправе_просить_подпись_одобрения(self, стенд):
        cid, _ = _довести(стенд, M.AWAITING_APPROVAL)
        токен = стенд["signer"]["caller_tokens"]["changeset-worker"]
        код, тело = _запрос(стенд["signer"]["base"], "/approval", {
            "changeset_id": cid, "approver_id": "human:owner",
            "approver_service": "human_owner", "approver_type": "HUMAN",
            "expires_at": через_час()}, токен)
        assert код == 403 and тело["error_code"] == "CALLER_NOT_ALLOWED"

    def test_12_разрешение_только_одобренному(self, стенд):
        cid, _ = _довести(стенд, M.AWAITING_APPROVAL)
        аренда = S.взять_аренду(стенд["соед"], cid, "changeset-worker")
        токен = стенд["signer"]["caller_tokens"]["changeset-worker"]
        код, тело = _запрос(стенд["signer"]["base"], "/grant", {
            "changeset_id": cid, "audience": "changeset-worker",
            "fencing_token": аренда["fencing_token"]}, токен)
        assert код == 409 and тело["error_code"] == "CHANGESET_STATE_INVALID"

    def test_13_чужая_аудитория(self, стенд):
        cid, _ = _довести(стенд, M.APPROVED)
        аренда = S.взять_аренду(стенд["соед"], cid, "changeset-worker")
        токен = стенд["signer"]["caller_tokens"]["changeset-worker"]
        код, тело = _запрос(стенд["signer"]["base"], "/grant", {
            "changeset_id": cid, "audience": "qwen",
            "fencing_token": аренда["fencing_token"]}, токен)
        assert код == 403 and тело["error_code"] == "AUDIENCE_NOT_ALLOWED"

    def test_14_устаревший_маркер_ограждения(self, стенд):
        cid, _ = _довести(стенд, M.APPROVED)
        первая = S.взять_аренду(стенд["соед"], cid, "changeset-worker")
        S.взять_аренду(стенд["соед"], cid, "changeset-worker")   # маркер вырос
        токен = стенд["signer"]["caller_tokens"]["changeset-worker"]
        код, тело = _запрос(стенд["signer"]["base"], "/grant", {
            "changeset_id": cid, "audience": "changeset-worker",
            "fencing_token": первая["fencing_token"]}, токен)
        assert код == 409 and тело["error_code"] == "FENCING_TOKEN_STALE"

    def test_15_план_изменён_после_одобрения(self, стенд):
        """Повтор после правки одобренного плана обязан быть отвергнут."""
        cid, _ = _довести(стенд, M.APPROVED)
        аренда = S.взять_аренду(стенд["соед"], cid, "changeset-worker")
        стенд["соед"].execute(
            "UPDATE changeset SET plan_hash=? WHERE changeset_id=?",
            ("подменённый-план", cid))
        токен = стенд["signer"]["caller_tokens"]["changeset-worker"]
        код, тело = _запрос(стенд["signer"]["base"], "/grant", {
            "changeset_id": cid, "audience": "changeset-worker",
            "fencing_token": аренда["fencing_token"]}, токен)
        assert код == 403
        assert тело["error_code"] in ("APPROVAL_BINDING_MISMATCH",
                                      "APPROVAL_SIGNATURE_INVALID")

    def test_16_цели_изменены_после_одобрения(self, стенд):
        cid, _ = _довести(стенд, M.APPROVED)
        аренда = S.взять_аренду(стенд["соед"], cid, "changeset-worker")
        стенд["соед"].execute(
            "UPDATE changeset SET target_site_ids=? WHERE changeset_id=?",
            (json.dumps(["другой-сайт"]), cid))
        токен = стенд["signer"]["caller_tokens"]["changeset-worker"]
        код, тело = _запрос(стенд["signer"]["base"], "/grant", {
            "changeset_id": cid, "audience": "changeset-worker",
            "fencing_token": аренда["fencing_token"]}, токен)
        assert код == 403

    def test_17_отпечаток_ресурса_изменён(self, стенд):
        cid, _ = _довести(стенд, M.APPROVED)
        аренда = S.взять_аренду(стенд["соед"], cid, "changeset-worker")
        стенд["соед"].execute(
            "UPDATE changeset SET expected_resource_fingerprint=? "
            "WHERE changeset_id=?", ("подменённый-отпечаток", cid))
        токен = стенд["signer"]["caller_tokens"]["changeset-worker"]
        код, тело = _запрос(стенд["signer"]["base"], "/grant", {
            "changeset_id": cid, "audience": "changeset-worker",
            "fencing_token": аренда["fencing_token"]}, токен)
        assert код == 403

    def test_18_версия_реестра_устарела(self, стенд):
        cid, _ = _довести(стенд, M.APPROVED)
        аренда = S.взять_аренду(стенд["соед"], cid, "changeset-worker")
        стенд["соед"].execute(
            "UPDATE changeset SET base_registry_version=? WHERE changeset_id=?",
            (1, cid))
        токен = стенд["signer"]["caller_tokens"]["changeset-worker"]
        код, тело = _запрос(стенд["signer"]["base"], "/grant", {
            "changeset_id": cid, "audience": "changeset-worker",
            "fencing_token": аренда["fencing_token"]}, токен)
        assert код in (409, 403)

    def test_19_отозванное_одобрение(self, стенд):
        cid, движок = _довести(стенд, M.APPROVED)
        аренда = S.взять_аренду(стенд["соед"], cid, "changeset-worker")
        движок.отозвать_одобрение(cid, actor_id="human:owner")
        токен = стенд["signer"]["caller_tokens"]["changeset-worker"]
        код, тело = _запрос(стенд["signer"]["base"], "/grant", {
            "changeset_id": cid, "audience": "changeset-worker",
            "fencing_token": аренда["fencing_token"]}, токен)
        assert код == 403 and тело["error_code"] == "APPROVAL_REVOKED"

    def test_20_законный_путь_выдаёт_короткоживущее_разрешение(self, стенд):
        """Отрицательные проверки бессмысленны, если не работает и законный путь."""
        cid, _ = _довести(стенд, M.APPROVED)
        аренда = S.взять_аренду(стенд["соед"], cid, "changeset-worker")
        токен = стенд["signer"]["caller_tokens"]["changeset-worker"]
        код, тело = _запрос(стенд["signer"]["base"], "/grant", {
            "changeset_id": cid, "audience": "changeset-worker",
            "fencing_token": аренда["fencing_token"]}, токен)
        assert код == 200, тело
        assert тело["grant"]["typ"] == "execution-grant"
        assert тело["grant"]["audience"] == "changeset-worker"
        срок = _d.datetime.fromisoformat(
            тело["grant"]["expires_at"].replace("Z", "+00:00"))
        осталось = (срок - _d.datetime.now(_d.timezone.utc)).total_seconds()
        assert 0 < осталось <= SIGNER.СРОК_РАЗРЕШЕНИЯ_СЕК + 5

    def test_21_ни_одно_отрицание_не_создало_разрешения(self, стенд):
        """Счётчик службы: отказы не должны порождать подписей."""
        база = стенд["signer"]["base"]
        токен = стенд["signer"]["caller_tokens"]["changeset-worker"]
        for тело_запроса in ({"changeset_id": "нет"},
                             {"changeset_id": "нет", "audience": "qwen",
                              "fencing_token": 1},
                             {"changeset_id": "нет", "audience":
                              "changeset-worker", "fencing_token": "не-число"}):
            _запрос(база, "/grant", тело_запроса, токен)
        with urllib.request.urlopen(база + "/healthz", timeout=10) as о:
            здоровье = json.loads(о.read())
        assert здоровье["grants_issued"] == 0
        assert здоровье["accepts_raw_payload"] is False
        assert здоровье["refusals"] >= 3


# =============================================================================
# D. Токены управляющего слоя: ротация с сохранением прав и атрибуция
# =============================================================================

class TestПринципалыУправляющегоСлоя:
    """Отзыв здесь — это ЗАМЕНА значения: Control API сверяет само значение."""

    @pytest.fixture()
    def файл(self, tmp_path):
        from factory.site_engine.credentials import control_principals as CP
        п = tmp_path / "site-engine-control-tokens"
        п.write_text("ops-token-aaaa=read,jobs:write,config:write|"
                     "ro-token-bbbb=read\n", encoding="utf-8")
        return п

    def test_ротация_меняет_значения(self, файл):
        from factory.site_engine.credentials import control_principals as CP
        до = CP.состояние(файл)
        итог = CP.ротировать(файл)
        после = CP.состояние(файл)
        assert итог["rotated"] == 2
        assert {з["fingerprint"] for з in до} & {з["fingerprint"] for з in после} == set()

    def test_области_переносятся_дословно(self, файл):
        from factory.site_engine.credentials import control_principals as CP
        до = [з["scopes"] for з in CP.состояние(файл)]
        CP.ротировать(файл)
        после = [з["scopes"] for з in CP.состояние(файл)]
        assert до == после, (
            "ротация, попутно меняющая права, — это изменение доступа, "
            "и обнаруживают его тогда, когда что-то перестало работать")

    def test_прежнее_значение_перестаёт_быть_принципалом(self, файл):
        from factory.site_engine.credentials import control_principals as CP
        прежние = {т for т, _ in CP.разобрать(файл.read_text("utf-8"))}
        CP.ротировать(файл)
        текущие = {т for т, _ in CP.разобрать(файл.read_text("utf-8"))}
        assert прежние & текущие == set()

    def test_файл_остаётся_закрытым(self, файл):
        import stat as _stat
        from factory.site_engine.credentials import control_principals as CP
        CP.ротировать(файл)
        assert oct(_stat.S_IMODE(файл.stat().st_mode)) == "0o400"

    def test_отсутствие_принципалов_названо(self, tmp_path):
        from factory.site_engine.credentials import control_principals as CP
        п = tmp_path / "нет"
        with pytest.raises(CP.PrincipalError) as ош:
            CP.ротировать(п)
        assert ош.value.error_code == "PRINCIPALS_MISSING"

    def test_значения_не_печатаются(self, файл):
        from factory.site_engine.credentials import control_principals as CP
        итог = CP.ротировать(файл)
        сырое = json.dumps(итог, ensure_ascii=False)
        for т, _ in CP.разобрать(файл.read_text("utf-8")):
            assert т not in сырое, "значение попало в вывод инструмента"


class TestАтрибуцияДействий:
    """Журнал обязан отвечать на вопрос «кто действовал»."""

    def test_отпечаток_действующего_сохраняется(self):
        from factory.redaction import redact_obj
        итог = redact_obj({"extra": {"actor_token": "c88b18c1fc56"}})
        assert итог["extra"]["actor_token"] == "c88b18c1fc56", (
            "затирая отпечаток, система перестаёт отвечать на вопрос, "
            "ради которого он и заводился")

    def test_сырой_токен_в_том_же_поле_затирается(self):
        from factory.redaction import redact_obj
        итог = redact_obj({"actor_token": "Ab3xK9zQmR7tLpW2vNc5YsD8fG1hJ4eU"})
        assert итог["actor_token"] != "Ab3xK9zQmR7tLpW2vNc5YsD8fG1hJ4eU"

    def test_разрешение_не_по_одной_лишь_форме(self):
        """Двенадцать шестнадцатеричных знаков может быть и коротким паролем."""
        from factory.redaction import redact_obj
        assert redact_obj({"password": "c88b18c1fc56"})["password"] != "c88b18c1fc56"

    def test_перечень_полей_отпечатков_закрыт(self):
        from factory.redaction import ПОЛЯ_ОТПЕЧАТКОВ
        assert "actor_token" in ПОЛЯ_ОТПЕЧАТКОВ
        assert "password" not in ПОЛЯ_ОТПЕЧАТКОВ
        assert "secret" not in ПОЛЯ_ОТПЕЧАТКОВ
