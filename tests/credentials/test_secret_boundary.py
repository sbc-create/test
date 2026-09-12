"""Граница учётных данных: что именно доказывается.

Не «файлы созданы», а следствия: значение из окружения не берётся, чужая
личность не опознаётся, отозванный токен отвергается отдельным кодом,
одобрение перестаёт действовать после отзыва ключа, а повторный `ensure` не
меняет ключ подписи молча.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path

import pytest

from factory.site_engine.approval import keyring as K
from factory.site_engine.approval import testing as ПТ
from factory.site_engine.credentials import overlay as OV
from factory.site_engine.credentials import provision as PR
from factory.site_engine.credentials import store as C


@pytest.fixture()
def каталог(tmp_path, monkeypatch):
    к = tmp_path / "credentials"
    к.mkdir()
    monkeypatch.setenv("CREDENTIALS_DIRECTORY", str(к))
    return к


class TestИсточникЗначений:
    def test_значение_берётся_из_credential(self, каталог):
        (каталог / "tok").write_text("значение\n", encoding="utf-8")
        assert C.получить("tok") == "значение"

    def test_окружение_отвергается(self, каталог, monkeypatch):
        monkeypatch.setenv("TOK_ENV", "значение")
        with pytest.raises(C.CredentialError) as ош:
            C.получить("tok", запасная_переменная="TOK_ENV")
        assert ош.value.error_code == "CREDENTIAL_ENV_FORBIDDEN"

    def test_послабление_только_явное(self, каталог, monkeypatch):
        monkeypatch.setenv("TOK_ENV", "значение")
        monkeypatch.setenv(C.ПОСЛАБЛЕНИЕ, "1")
        assert C.получить("tok", запасная_переменная="TOK_ENV") == "значение"

    def test_отсутствие_объяснимо(self, каталог):
        with pytest.raises(C.CredentialError) as ош:
            C.получить("нет")
        assert ош.value.error_code == "CREDENTIAL_MISSING"
        assert "LoadCredential" in ош.value.detail

    def test_пустой_credential_не_считается_значением(self, каталог):
        (каталог / "tok").write_text("   \n", encoding="utf-8")
        with pytest.raises(C.CredentialError) as ош:
            C.получить("tok")
        assert ош.value.error_code == "CREDENTIAL_EMPTY"

    def test_отпечаток_не_раскрывает(self, каталог):
        о = C.отпечаток("секрет")
        assert len(о) == 12 and "секрет" not in о


class TestКонфигурация:
    def test_секрет_не_берётся_из_окружения(self, каталог):
        настройки = {"SITE_ENGINE_CONTROL_TOKENS": "из-окружения"}
        # credential отсутствует — значение из окружения остаётся видимым,
        # но модуль обязан назвать это дефектом, а не промолчать.
        assert OV.секреты_в_окружении(настройки) == ["SITE_ENGINE_CONTROL_TOKENS"]

    def test_credential_перекрывает_окружение(self, каталог):
        (каталог / "site-engine-control-tokens").write_text("из-credential",
                                                            encoding="utf-8")
        итог = OV.наложить({"SITE_ENGINE_CONTROL_TOKENS": "из-окружения"})
        assert итог["SITE_ENGINE_CONTROL_TOKENS"] == "из-credential"
        assert OV.секреты_в_окружении({"SITE_ENGINE_CONTROL_TOKENS": "x"}) == []


class TestПодпись:
    def test_подпись_проверяется_публичным_ключом(self):
        kid, pem, публичный = K.создать_ключ()
        п = K.подписать(pem, "тело")
        набор = K.НаборКлючей([K.Ключ(kid, публичный, "ACTIVE")])
        assert набор.проверить(п, "тело")["kid"] == kid

    def test_подмена_тела_обнаружена(self):
        kid, pem, публичный = K.создать_ключ()
        п = K.подписать(pem, "тело")
        набор = K.НаборКлючей([K.Ключ(kid, публичный, "ACTIVE")])
        with pytest.raises(K.KeyringError) as ош:
            набор.проверить(п, "другое тело")
        assert ош.value.error_code == "APPROVAL_SIGNATURE_INVALID"

    def test_отозванный_ключ_отличается_от_подделки(self):
        kid, pem, публичный = K.создать_ключ()
        п = K.подписать(pem, "тело")
        набор = K.НаборКлючей([K.Ключ(kid, публичный, "REVOKED")])
        with pytest.raises(K.KeyringError) as ош:
            набор.проверить(п, "тело")
        assert ош.value.error_code == "APPROVAL_KEY_REVOKED"

    def test_чужой_ключ_неизвестен(self):
        _, pem, _ = K.создать_ключ()
        kid2, _, пуб2 = K.создать_ключ()
        п = K.подписать(pem, "тело")
        набор = K.НаборКлючей([K.Ключ(kid2, пуб2, "ACTIVE")])
        with pytest.raises(K.KeyringError) as ош:
            набор.проверить(п, "тело")
        assert ош.value.error_code == "SIGNATURE_KEY_UNKNOWN"

    def test_kid_выводится_из_ключа(self):
        kid, pem, _ = K.создать_ключ()
        повтор = K.kid_публичного(K.приватный_из_pem(pem).public_key())
        assert kid == повтор


class TestОдобрениеПослеОтзыва:
    """Ротация без отзыва оставила бы вчерашние разрешения в силе."""

    def test_одобрение_перестаёт_действовать(self, tmp_path, monkeypatch):
        from factory.site_engine.changeset import policy as POL
        набор_данных = {
            "changeset_id": "cs-1", "plan_hash": "ph", "actor_id": "service:templates",
            "target_site_ids": ["s1"], "canary_site_ids": [],
            "resource_type": "template.build", "resource_id": "r1",
            "operation_type": "update", "base_registry_version": 32,
            "expected_resource_fingerprint": "fp", "policy_version": "policy/1.0.0",
            "risk_class": "LOW", "verification_plan": {}, "rollback_plan": {},
        }
        каталог = tmp_path / "credentials"
        with ПТ.эфемерный_signer(каталог, monkeypatch):
            запись = POL.одобрить(набор_данных, approver_id="human:owner",
                                  approver_service="human_owner",
                                  approver_type="HUMAN",
                                  expires_at="2099-01-01T00:00:00Z")
            полный = {**набор_данных, "approval": запись}
            POL.проверить_одобрение(полный, сейчас_utc="2026-09-12T00:00:00Z")

            # Ключ выводится из обращения — вчерашнее разрешение обязано
            # перестать действовать, а не остаться верным арифметически.
            ПТ.отозвать_активный(каталог)
            from factory.site_engine.approval import client as CL
            CL._набор_кэш = None
            with pytest.raises(Exception) as ош:
                POL.проверить_одобрение(полный, сейчас_utc="2026-09-12T00:00:00Z")
            assert getattr(ош.value, "error_code", "") == "APPROVAL_KEY_REVOKED"


class TestОпознаниеПоОтпечаткам:
    def test_сырые_токены_верификатору_не_нужны(self, каталог):
        from factory.site_engine.audit import ledger_identity as ident
        токен = "токен-службы-templates"
        (каталог / ident.ОТПЕЧАТКИ).write_text(json.dumps({
            "services": {"templates": hashlib.sha256(токен.encode()).hexdigest()},
            "revoked": []}), encoding="utf-8")
        кто = ident.опознать({"authorization": f"Bearer {токен}"})
        assert кто["producer_service"] == "templates"
        # В файле отпечатков сырого значения нет.
        assert токен not in (каталог / ident.ОТПЕЧАТКИ).read_text("utf-8")

    def test_отозванный_отпечаток_отвергается(self, каталог):
        from factory.site_engine.audit import ledger_identity as ident
        токен = "отозванный"
        х = hashlib.sha256(токен.encode()).hexdigest()
        (каталог / ident.ОТПЕЧАТКИ).write_text(json.dumps({
            "services": {"templates": х}, "revoked": [х]}), encoding="utf-8")
        with pytest.raises(ident.IdentityError) as ош:
            ident.опознать({"authorization": f"Bearer {токен}"})
        assert ош.value.error_code == "TOKEN_REVOKED"

    def test_чужой_токен_не_опознан(self, каталог):
        from factory.site_engine.audit import ledger_identity as ident
        (каталог / ident.ОТПЕЧАТКИ).write_text(json.dumps({
            "services": {"templates": "0" * 64}, "revoked": []}), encoding="utf-8")
        with pytest.raises(ident.IdentityError) as ош:
            ident.опознать({"authorization": "Bearer чужой"})
        assert ош.value.error_code == "UNAUTHENTICATED"

    def test_без_credential_запись_не_включается_молча(self, каталог):
        from factory.site_engine.audit import ledger_identity as ident
        with pytest.raises(ident.IdentityError) as ош:
            ident.опознать({"authorization": "Bearer что-то"})
        assert ош.value.error_code == "LEDGER_IDENTITY_NOT_PROVISIONED"


class TestВыдача:
    @pytest.fixture()
    def корень(self, tmp_path, monkeypatch):
        к = tmp_path / "cred"
        monkeypatch.setattr(PR, "КОРЕНЬ", к)
        monkeypatch.setattr(PR, "СТАРЫЙ_ОБЩИЙ", tmp_path / "нет.env")
        return к

    def test_каждой_личности_свой_файл(self, корень):
        PR.выдать(ротировать=True)
        файлы = {п.name for п in корень.iterdir()}
        for личность in PR.ЛИЧНОСТИ:
            assert f"audit-token-{личность}" in файлы

    def test_каталог_закрыт(self, корень):
        PR.выдать(ротировать=True)
        assert oct(корень.stat().st_mode)[-3:] == "700"
        assert oct((корень / "approval-signing-key").stat().st_mode)[-3:] == "400"

    def test_ensure_не_меняет_ключ(self, корень):
        первый = PR.выдать(ротировать=False).активный_kid
        второй = PR.выдать(ротировать=False).активный_kid
        assert первый == второй, "повторный ensure не вправе ротировать ключ"

    def test_ротация_отзывает_прежнее(self, корень):
        до = PR.выдать(ротировать=True)
        после = PR.выдать(ротировать=True)
        assert после.активный_kid != до.активный_kid
        assert до.активный_kid in после.отозванные_kid
        assert после.отозвано_отпечатков >= len(PR.ЛИЧНОСТИ)

    def test_действующее_значение_не_отзывается(self, корень):
        PR.выдать(ротировать=True)
        PR.выдать(ротировать=True)
        реестр = json.loads((корень / PR.ОТПЕЧАТКИ).read_text("utf-8"))
        пересечение = set(реестр["services"].values()) & set(реестр["revoked"])
        assert not пересечение, "действующий токен не может быть отозванным"
