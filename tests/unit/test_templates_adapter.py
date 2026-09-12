"""Адаптер Templates и импорт аудита.

Проверяются следствия, а не факт вызова: сколько эффектов произвёл сухой
прогон, сколько — повтор применения, вернул ли откат прежний отпечаток и
отказал ли адаптер там, где отказать обязан.
"""
from __future__ import annotations

import json
import os
import pathlib
import sys

import pytest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2]))

from factory.templates_cp import adapter as A
from factory.templates_cp import audit_import as AI

РЕСУРС_ИД = "site-a:template-binding"


@pytest.fixture()
def ад(tmp_path):
    а = A.TemplatesAdapter(
        tmp_path / "adapter.sqlite3",
        окружения={"site-a": "test", "prod-1": "production"},
        домены={})
    yield а
    а.закрыть()


def _план(ад, изменение=None):
    н = ад.observe(site_id="site-a", resource_id=РЕСУРС_ИД)
    п = ад.plan(site_id="site-a", resource_id=РЕСУРС_ИД, operation="update",
                requested_change=изменение or {"design_version": "1.4.5"},
                observed=н)
    п["plan_hash"] = "тестовый-план"
    return п, н


class TestНаблюдение:
    def test_несвязанный_ресурс_не_выдумывается(self, ад):
        н = ад.observe(site_id="site-a", resource_id=РЕСУРС_ИД)
        assert н["state"]["bound"] is False
        assert н["state"]["binding"] is None
        assert н["fingerprint"].startswith("sha256:")

    def test_отпечаток_детерминирован(self, ад):
        a = ад.observe(site_id="site-a", resource_id=РЕСУРС_ИД)["fingerprint"]
        b = ад.observe(site_id="site-a", resource_id=РЕСУРС_ИД)["fingerprint"]
        assert a == b


class TestПлан:
    def test_план_детерминирован(self, ад):
        п1, _ = _план(ад)
        п2, _ = _план(ад)
        assert п1["expected_fingerprint"] == п2["expected_fingerprint"]
        assert п1["diff"] == п2["diff"]

    def test_незнакомое_поле_отвергается(self, ад):
        н = ад.observe(site_id="site-a", resource_id=РЕСУРС_ИД)
        with pytest.raises(A.AdapterError) as ош:
            ад.plan(site_id="site-a", resource_id=РЕСУРС_ИД, operation="update",
                    requested_change={"rm_rf": "/"}, observed=н)
        assert ош.value.error_code == "FIELD_UNKNOWN"

    def test_пустое_изменение_помечено_пустым(self, ад):
        п, _ = _план(ад)
        ад.apply(site_id="site-a", plan=п, fencing_token=1)
        п2, _ = _план(ад)
        assert п2["empty"] is True and п2["diff"] == {}


class TestСухойПрогон:
    def test_ни_одного_эффекта(self, ад):
        п, _ = _план(ад)
        до = ад.эффектов()
        р = ад.dry_run(site_id="site-a", plan=п)
        assert р["effects"] == 0
        assert ад.эффектов() == до
        # И состояние осталось несвязанным.
        assert ад.observe(site_id="site-a",
                          resource_id=РЕСУРС_ИД)["state"]["bound"] is False


class TestПрименение:
    def test_один_эффект(self, ад):
        п, _ = _план(ад)
        р = ад.apply(site_id="site-a", plan=п, fencing_token=1)
        assert р["effects"] == 1
        assert ад.эффектов("site-a") == 1

    def test_повтор_не_создаёт_второго_эффекта(self, ад):
        п, _ = _план(ад)
        ад.apply(site_id="site-a", plan=п, fencing_token=1)
        повтор = ад.apply(site_id="site-a", plan=п, fencing_token=1)
        assert повтор["idempotent_replay"] is True
        assert повтор["effects"] == 0
        assert ад.эффектов("site-a") == 1

    def test_production_отвергается(self, ад):
        п, _ = _план(ад)
        with pytest.raises(A.AdapterError) as ош:
            ад.apply(site_id="prod-1", plan=п, fencing_token=1)
        assert ош.value.error_code == "PRODUCTION_APPLY_FORBIDDEN"


class TestПроверка:
    def test_сошлось(self, ад):
        п, _ = _план(ад)
        ад.apply(site_id="site-a", plan=п, fencing_token=1)
        н = ад.observe(site_id="site-a", resource_id=РЕСУРС_ИД)
        р = ад.verify(site_id="site-a", plan=п, observed=н)
        assert р["ok"] is True and р["mismatch"] is None

    def test_подмена_ожидаемого_обнаружена(self, ад):
        п, _ = _план(ад)
        ад.apply(site_id="site-a", plan=п, fencing_token=1)
        н = ад.observe(site_id="site-a", resource_id=РЕСУРС_ИД)
        подделка = {**п, "expected_fingerprint": "sha256:" + "0" * 64}
        р = ад.verify(site_id="site-a", plan=подделка, observed=н)
        assert р["ok"] is False and р["reason"]

    def test_проверка_читает_состояние_заново(self, ад):
        """Подсунутое наблюдение не должно подтверждать успех."""
        п, до = _план(ад)
        # Ничего не применяли, но передаём «наблюдение», будто всё сошлось.
        ложное = {"state": п["expected_state"],
                  "fingerprint": п["expected_fingerprint"]}
        р = ад.verify(site_id="site-a", plan=п, observed=ложное)
        assert р["ok"] is False


class TestОткат:
    def test_возвращает_прежний_отпечаток(self, ад):
        п, до = _план(ад)
        ад.apply(site_id="site-a", plan=п, fencing_token=1)
        р = ад.rollback(site_id="site-a", plan=п,
                        before_fingerprint=п["before_fingerprint"],
                        fencing_token=1)
        assert р["rolled_back"] is True
        assert ад.observe(site_id="site-a",
                          resource_id=РЕСУРС_ИД)["fingerprint"] == до["fingerprint"]

    def test_повторный_откат_без_эффекта(self, ад):
        п, _ = _план(ад)
        ад.apply(site_id="site-a", plan=п, fencing_token=1)
        ад.rollback(site_id="site-a", plan=п,
                    before_fingerprint=п["before_fingerprint"], fencing_token=1)
        второй = ад.rollback(site_id="site-a", plan=п,
                             before_fingerprint=п["before_fingerprint"],
                             fencing_token=1)
        assert второй["effects"] == 0

    def test_production_откат_отвергается(self, ад):
        п, _ = _план(ад)
        with pytest.raises(A.AdapterError) as ош:
            ад.rollback(site_id="prod-1", plan=п,
                        before_fingerprint=п["before_fingerprint"],
                        fencing_token=1)
        assert ош.value.error_code == "PRODUCTION_APPLY_FORBIDDEN"


class TestВозможности:
    def test_владелец_и_операции(self, ад):
        в = ад.capabilities()
        assert в["owner_service"] == "templates"
        assert в["production_apply"] is False
        assert {"create", "update", "rollback"} <= set(в["operations"])


# --- импорт аудита ----------------------------------------------------------

def _манифест(tmp_path, записей=2):
    к = tmp_path / "fleet-audit"
    к.mkdir(parents=True)
    данные = {"schema_version": "fleet-audit/1.0.0", "prompt_id": "FLEET-TPL-005",
              "prompt_rev": "R1", "generated_at": "2026-09-11T16:00:00Z",
              "records": [{"site_id": f"s-{i}", "defect_id": f"D-{i:03d}",
                           "severity": "P1"} for i in range(записей)]}
    (к / "audit-manifest.json").write_text(json.dumps(данные, ensure_ascii=False))
    return к


class TestИмпортАудита:
    def test_ключ_выводится_из_содержимого(self, tmp_path):
        к = _манифест(tmp_path)
        a = AI.собрать(к)["event"]["idempotency_key"]
        b = AI.собрать(к)["event"]["idempotency_key"]
        assert a == b, "повторная сборка обязана дать тот же ключ"

    def test_другой_манифест_даёт_другой_ключ(self, tmp_path):
        a = AI.собрать(_манифест(tmp_path / "a", 2))["event"]["idempotency_key"]
        b = AI.собрать(_манифест(tmp_path / "b", 3))["event"]["idempotency_key"]
        assert a != b

    def test_событие_наблюдательное(self, tmp_path):
        с = AI.собрать(_манифест(tmp_path))["event"]
        assert с["phase"] == "OBSERVED"
        assert с["authority"] == "OBSERVE"
        assert с["scope"] == "FLEET"

    def test_одно_событие_на_весь_аудит(self, tmp_path):
        с = AI.собрать(_манифест(tmp_path, 7))
        assert с["records"] == 7
        assert isinstance(с["event"], dict)

    def test_без_внедрённого_токена_отказ(self, tmp_path, monkeypatch):
        monkeypatch.delenv(AI.ПЕРЕМЕННАЯ, raising=False)
        с = AI.собрать(_манифест(tmp_path))
        with pytest.raises(AI.ImportError_) as ош:
            AI.отправить(с["event"])
        assert ош.value.error_code == "SERVICE_TOKEN_MISSING"

    def test_секретов_в_событии_нет(self, tmp_path):
        сырое = json.dumps(AI.собрать(_манифест(tmp_path))["event"],
                           ensure_ascii=False)
        for опасное in ("AUDIT_TOKEN", "Bearer ", "PRIVATE KEY", "password"):
            assert опасное not in сырое


class TestИзоляцияУчётныхДанных:
    """Процесс импорта не вправе держать чужую личность и ключ подписи."""

    def test_чужие_токены_и_ключ_подписи_убираются(self, monkeypatch):
        monkeypatch.setenv(AI.ПЕРЕМЕННАЯ, "своё")
        monkeypatch.setenv("AUDIT_TOKEN_ARCHITECT", "чужое")
        monkeypatch.setenv("AUDIT_TOKEN_QWEN", "чужое")
        monkeypatch.setenv("CHANGESET_APPROVAL_KEY", "приватный")
        убрано = AI.изолировать_окружение()
        assert "AUDIT_TOKEN_ARCHITECT" in убрано
        assert "CHANGESET_APPROVAL_KEY" in убрано
        assert os.environ.get("AUDIT_TOKEN_ARCHITECT") is None
        assert os.environ.get("CHANGESET_APPROVAL_KEY") is None
        # Своя личность обязана остаться — иначе импорт нечем подписать.
        assert os.environ.get(AI.ПЕРЕМЕННАЯ) == "своё"

    def test_потомок_не_унаследует_ключ(self, monkeypatch):
        monkeypatch.setenv(AI.ПЕРЕМЕННАЯ, "своё")
        monkeypatch.setenv("CHANGESET_APPROVAL_KEY", "приватный")
        AI.изолировать_окружение()
        import subprocess
        вывод = subprocess.run(
            [sys.executable, "-c",
             "import os; print(os.environ.get('CHANGESET_APPROVAL_KEY'))"],
            capture_output=True, text=True).stdout.strip()
        assert вывод == "None"
