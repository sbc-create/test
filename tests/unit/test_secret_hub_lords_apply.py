"""Почему credentials Lords не применялись — и почему панель это скрывала.

Боевой симптом: направление Lords сохранено и проверено (версия 2), но все три
потребителя показаны как «цель недоступна», а итог — «Сохранено, но применить
не удалось: неизвестная причина».

Два дефекта, независимых друг от друга:

1. **Проверка цели была строже действия, которое охраняла.** `check_target`
   требовала, чтобы непосредственный родительский каталог уже существовал, а
   `_ensure_directory` создаёт всю цепочку через ``mkdir(parents=True)``.
   Каталог ``/etc/site-factory/secrets/lords`` не создаёт никто: установщик
   делает только ``/etc/site-factory/secrets``. Yami работал лишь потому, что
   его родитель существует по другой причине — то есть проверка ловила не
   дефект, а собственную строгость.

2. **Причина терялась по дороге.** Отчёт применения не имел поля `reason`;
   причина оставалась в `consumers[].detail`, а панель писала «неизвестная
   причина». Это была не нехватка сведений, а их потеря.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from factory.secret_hub import consumers as consumers_mod
from factory.secret_hub.crypto import Secret
from factory.secret_hub.registry import Consumer, Portfolio
from factory.secret_hub.registry import load as load_config

LORDS_IDS = ("lords-01", "lords-02", "lords-03")


def values() -> dict:
    return {"api_token": Secret("СОХРАНЁННЫЙ-ТОКЕН-LORDS", "t"),
            "publisher_id": Secret("pub-lords", "p")}


@pytest.fixture
def lords(repo_root):
    return load_config(repo_root / "config" / "secret-hub.json").portfolio("lords")


@pytest.fixture
def fake_systemd(monkeypatch):
    calls: list[list[str]] = []

    class Result:
        returncode = 0
        stdout = "loaded\n"

    monkeypatch.setattr(consumers_mod.subprocess, "run",
                        lambda cmd, **kw: (calls.append(list(cmd)), Result())[1])
    monkeypatch.setattr(consumers_mod, "_unit_exists", lambda unit: True)
    return calls


class TestRegistryMatchesTheHost:
    """Имена в реестре обязаны совпадать с тем, что стоит на машине."""

    def test_three_consumers_are_described(self, lords):
        assert [c.id for c in lords.consumers] == list(LORDS_IDS)

    def test_units_match_consumer_ids(self, lords):
        for consumer in lords.consumers:
            assert consumer.unit == f"{consumer.id}.service"

    def test_all_use_systemd_credentials(self, lords):
        assert {c.kind for c in lords.consumers} == {"systemd_credential"}

    def test_each_declares_loadcredential_names(self, lords):
        for consumer in lords.consumers:
            assert set(consumer.credential_names) == {"api_token", "publisher_id"}
            assert consumer.dropin is not None

    def test_all_three_share_one_credential_set(self, lords):
        """Один набор на направление, а не копия на сайт."""
        assert len({c.files["api_token"] for c in lords.consumers}) == 1

    def test_units_exist_on_this_host(self, lords):
        """Фактическая проверка машины, а не реестра."""
        missing = [c.unit for c in lords.consumers
                   if not Path(f"/etc/systemd/system/{c.unit}").exists()]
        if missing:
            pytest.skip(f"unit'ы отсутствуют на этом хосте: {missing}")
        assert missing == []


class TestTargetIsCreatableNotPreexisting:
    """Главный дефект: проверка требовала того, что действие создаёт само."""

    def test_missing_parent_does_not_block(self, tmp_path, fake_systemd, lords):
        """Ровно боевой случай: `/etc/site-factory/secrets` есть, `/lords` нет."""
        secrets = tmp_path / "etc" / "site-factory" / "secrets"
        secrets.mkdir(parents=True)
        assert not (secrets / "lords").exists()

        for source in lords.consumers:
            consumer = Consumer(**{**source.__dict__,
                                   "directory": secrets / "lords" / source.id,
                                   "dropin": tmp_path / "systemd" / "d.conf"})
            assert consumers_mod.check_target(consumer) == [], \
                f"{source.id}: цель считается недоступной, хотя создаётся"

    def test_ancestor_that_is_a_file_does_block(self, tmp_path):
        """Настоящее препятствие остаётся препятствием."""
        blocker = tmp_path / "lords"
        blocker.write_text("не каталог", encoding="utf-8")
        reason = consumers_mod._creatable(blocker / "lords-01")
        assert reason is not None
        assert "не является каталогом" in reason

    def test_unreadable_ancestor_is_not_treated_as_absent(self, tmp_path, monkeypatch):
        """Закрытый каталог измеряет root; блокировать по неизмеренному нельзя."""
        monkeypatch.setattr(consumers_mod, "_probe",
                            lambda path: ("unmeasured", None))
        assert consumers_mod._creatable(tmp_path / "x" / "y") is None

    def test_enotdir_is_absent_not_unmeasured(self, tmp_path):
        """ENOTDIR означает «не существует», а не «не удалось измерить».

        Именно из-за этой путаницы обход предков останавливался на первом же
        шаге и не доходил до настоящего препятствия.
        """
        blocker = tmp_path / "file"
        blocker.write_text("x", encoding="utf-8")
        state, _ = consumers_mod._probe(blocker / "child")
        assert state == "absent"


class TestAllThreeConsumersApply:
    def _moved(self, lords, tmp_path):
        root = tmp_path / "etc" / "site-factory" / "secrets"
        root.mkdir(parents=True)
        return Portfolio(lords.id, lords.title, True, tuple(
            Consumer(**{**c.__dict__,
                        "directory": root / "lords" / c.id,
                        "dropin": tmp_path / "systemd" / f"{c.unit}.d" / "10-cred.conf"})
            for c in lords.consumers))

    def test_apply_reaches_all_three(self, lords, tmp_path, fake_systemd):
        portfolio = self._moved(lords, tmp_path)
        report = consumers_mod.apply_portfolio(portfolio, values(), version=2,
                                               backup_root=tmp_path / "backups")
        assert report.ok, report.reason
        assert [r.consumer_id for r in report.results] == list(LORDS_IDS)
        assert all(r.status == "applied" for r in report.results)

    def test_each_consumer_gets_both_files_closed(self, lords, tmp_path, fake_systemd):
        portfolio = self._moved(lords, tmp_path)
        consumers_mod.apply_portfolio(portfolio, values(), version=2,
                                      backup_root=tmp_path / "backups")
        import stat as stat_mod

        for consumer in portfolio.consumers:
            for field in ("api_token", "publisher_id"):
                path = consumer.path_for(field)
                assert path.exists(), f"{consumer.id}: нет {field}"
                assert stat_mod.S_IMODE(path.stat().st_mode) == 0o400

    def test_dropin_carries_loadcredential_not_values(self, lords, tmp_path, fake_systemd):
        portfolio = self._moved(lords, tmp_path)
        consumers_mod.apply_portfolio(portfolio, values(), version=2,
                                      backup_root=tmp_path / "backups")
        for consumer in portfolio.consumers:
            text = consumer.dropin.read_text(encoding="utf-8")
            assert "LoadCredential=" in text
            assert "СОХРАНЁННЫЙ-ТОКЕН-LORDS" not in text

    def test_only_lords_units_are_restarted(self, lords, tmp_path, fake_systemd):
        portfolio = self._moved(lords, tmp_path)
        consumers_mod.apply_portfolio(portfolio, values(), version=2,
                                      backup_root=tmp_path / "backups")
        restarted = [c[2] for c in fake_systemd if len(c) > 2 and c[1] == "restart"]
        assert restarted == [f"{i}.service" for i in LORDS_IDS]
        assert not any("yummyani" in u or "yami" in u for u in restarted)

    def test_report_contains_no_values(self, lords, tmp_path, fake_systemd):
        portfolio = self._moved(lords, tmp_path)
        report = consumers_mod.apply_portfolio(portfolio, values(), version=2,
                                               backup_root=tmp_path / "backups")
        assert "СОХРАНЁННЫЙ-ТОКЕН-LORDS" not in str(report.as_dict())


class TestStructuredReasonInsteadOfUnknown:
    """«Неизвестная причина» была потерей сведений, а не их отсутствием."""

    def test_report_names_the_blocked_consumers(self, lords, tmp_path, monkeypatch):
        monkeypatch.setattr(consumers_mod, "_unit_exists", lambda unit: False)
        root = tmp_path / "secrets"
        root.mkdir()
        portfolio = Portfolio(lords.id, lords.title, True, tuple(
            Consumer(**{**c.__dict__, "directory": root / c.id,
                        "dropin": tmp_path / "d.conf"})
            for c in lords.consumers))

        report = consumers_mod.apply_portfolio(portfolio, values(), version=2,
                                               backup_root=tmp_path / "backups")
        assert not report.ok
        assert report.reason, "отчёт снова без причины"
        assert "lords-01" in report.reason
        assert "не найден в systemd" in report.reason
        assert "reason" in report.as_dict()

    def test_panel_never_says_unknown_reason(self):
        """Формулировка удалена из кода панели."""
        from factory.secret_hub.panel import server as panel_server

        source = Path(panel_server.__file__).read_text(encoding="utf-8")
        for line in source.splitlines():
            if line.strip().startswith("#"):
                continue
            assert '"неизвестная причина"' not in line, \
                "панель снова может показать «неизвестная причина»"

    def test_panel_builds_reason_from_consumers(self):
        from factory.secret_hub.panel.server import _apply_reason

        message = _apply_reason({
            "ok": False,
            "consumers": [
                {"consumer": "lords-01", "status": "blocked",
                 "detail": "unit lords-01.service не найден в systemd"},
                {"consumer": "lords-02", "status": "applied", "detail": ""},
            ],
        })
        assert "lords-01" in message
        assert "цель недоступна" in message
        assert "неизвестн" not in message.lower()

    def test_panel_prefers_the_hub_reason_when_present(self):
        from factory.secret_hub.panel.server import _apply_reason

        assert "провайдер" in _apply_reason(
            {"ok": False, "reason": "провайдер отверг credentials"}).lower() \
            or "не принял" in _apply_reason(
                {"ok": False, "reason": "провайдер отверг credentials"}).lower()

    def test_panel_says_it_is_a_defect_when_hub_is_silent(self):
        """Если причины нет вообще — это дефект отчёта, и так и сказано."""
        from factory.secret_hub.panel.server import _apply_reason

        message = _apply_reason({"ok": False})
        assert "дефект отчёта" in message

    def test_consumer_problem_is_exposed_for_the_card(self, lords, monkeypatch):
        """Причина недоступности цели доезжает до карточки направления."""
        monkeypatch.setattr(consumers_mod, "_unit_exists", lambda unit: False)
        rows = consumers_mod.describe(lords)
        assert rows, "нет описания потребителей"
        for row in rows:
            assert row["target_ok"] is False
            assert row["problem"], "карточке нечего показать, кроме «цель недоступна»"
            assert "не найден в systemd" in row["problem"]


class TestInstallerCreatesTargetParents:
    def test_installer_creates_parents_from_the_registry(self, repo_root):
        text = (repo_root / "automation" / "secret-hub"
                / "install.sh").read_text(encoding="utf-8")
        assert "каталоги цел" in text.lower() or "каталог цели" in text
        assert "load().portfolios" in text, \
            "список каталогов перечислен руками и разъедется с реестром"

    def test_installer_does_not_hardcode_lords(self, repo_root):
        """Направления добавляются конфигурацией — установщик не исключение."""
        text = (repo_root / "automation" / "secret-hub"
                / "install.sh").read_text(encoding="utf-8")
        assert "secrets/lords" not in text


class TestUpdateActuallyTakesEffect:
    """Обновление кода без перезапуска — это обновление, которого не было."""

    def _launcher(self, repo_root) -> str:
        return (repo_root / "automation" / "secret-hub" / "install-secret-hub.sh").read_text(encoding="utf-8")

    def test_panel_is_restarted_not_just_enabled(self, repo_root):
        text = self._launcher(repo_root)
        assert 'systemctl restart "$PANEL_UNIT"' in text, \
            "после обновления панель продолжила бы крутить прежний код"

    def test_hub_is_restarted_too(self, repo_root):
        text = (repo_root / "automation" / "secret-hub"
                / "install.sh").read_text(encoding="utf-8")
        assert 'systemctl restart "$UNIT"' in text

    def test_both_waits_are_bounded(self, repo_root):
        """Ожидание с проверкой, а не фиксированная пауза."""
        for text in (self._launcher(repo_root),
                     (repo_root / "automation" / "secret-hub"
                      / "install.sh").read_text(encoding="utf-8")):
            assert "for _ in $(seq 1 15); do" in text
