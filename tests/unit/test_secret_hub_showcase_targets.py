"""Направления витрин Zona и Animedia/AMD: доставка, изоляция, отсутствие утечек.

Витрины Lords/Nova читают Publisher ID не из каталога credentials, а из
JSON-документа по пути ``LORDS_PLAYER_CONFIG`` — так устроен фронтенд
(``_конфиг_плеера``). Поэтому у Secret Hub появился третий способ доставки
``player_config``, и эти тесты стерегут именно его границы:

* витрине кладётся ровно Publisher ID и ничего больше;
* документ разбирается тем же способом, что и фронтендом, а не «на глаз»;
* в drop-in витрины не попадает ни значение, ни ``LoadCredential``;
* Lords остаётся ровно таким, каким был.

Отдельно проверяется, что визуальные референсы (``w140.zona.plus``,
``amd.online``) целями не стали: они не сайты, и запись о них в реестре
означала бы secret-хранилище для домена, которым фабрика не управляет.
"""
from __future__ import annotations

import json
import stat
from pathlib import Path

import jsonschema
import pytest

from factory.secret_hub import consumers as consumers_mod
from factory.secret_hub.crypto import Secret
from factory.secret_hub.panel import ui as ui_mod
from factory.secret_hub.registry import Consumer, Reload, load

#: Publisher ID числовой: фронтенд зовёт `Number(publisherId)` и нечисловое
#: значение превращает в NaN. Значение здесь синтетическое и настоящим не
#: является — в тесты настоящие credentials не попадают.
FAKE_PUBLISHER = "4242"
FAKE_TOKEN = "синтетический-токен-не-настоящий"


@pytest.fixture
def config(repo_root):
    return load(repo_root / "config" / "secret-hub.json")


@pytest.fixture
def schema(repo_root):
    return json.loads(
        (repo_root / "schemas" / "secret-hub.schema.json").read_text(encoding="utf-8"))


@pytest.fixture
def fake_systemd(monkeypatch):
    calls: list[list[str]] = []

    class Result:
        returncode = 0
        stdout = "unit-file loaded\n"

    monkeypatch.setattr(consumers_mod.subprocess, "run",
                        lambda command, **kw: (calls.append(list(command)), Result())[1])
    monkeypatch.setattr(consumers_mod, "_unit_exists", lambda unit: True)
    return calls


def showcase_consumer(tmp_path: Path, consumer_id: str = "zona-01") -> Consumer:
    return Consumer(
        id=consumer_id, kind="player_config", title=f"витрина {consumer_id}",
        directory=tmp_path / "secrets" / consumer_id,
        files={"publisher_id": "player.json"},
        owner="root", group="lords", file_mode=0o440, directory_mode=0o750,
        reload=Reload("systemd"), unit=f"nova-{consumer_id}.service",
        dropin=tmp_path / "systemd" / f"nova-{consumer_id}.service.d" / "10-player.conf",
    )


def values() -> dict:
    return {"api_token": Secret(FAKE_TOKEN, "t"),
            "publisher_id": Secret(FAKE_PUBLISHER, "p")}


class TestShippedShowcaseTargets:
    """Что именно описано в поставляемом реестре."""

    def test_zona_is_bound_to_the_canonical_production_site(self, config):
        zona = config.portfolio("zona")
        assert [c.id for c in zona.consumers] == ["zona-01"]
        assert zona.consumers[0].unit == "nova-zona-01.service"

    def test_animedia_covers_both_canonical_production_sites(self, config):
        animedia = config.portfolio("animedia")
        assert [c.id for c in animedia.consumers] == ["animedia-01", "animedia-02"]
        assert [c.unit for c in animedia.consumers] == [
            "nova-animedia-01.service", "nova-animedia-02.service"]

    def test_animedia_sites_share_one_credential_set(self, config):
        """Модель контракта: один набор на направление, а не на домен.

        Так же устроен Lords: три сайта — один набор. Раздельные наборы на
        домен потребовали бы раздельных направлений, а такого решения в
        конфигурации нет и придумывать его нельзя.
        """
        animedia = config.portfolio("animedia")
        assert len(animedia.consumers) == 2
        assert len({c.directory for c in animedia.consumers}) == 2, (
            "каталоги обязаны различаться: общий каталог у двух потребителей "
            "означал бы, что второй перезаписывает первого")

    def test_showcase_targets_deliver_only_the_publisher_id(self, config):
        for portfolio_id in ("zona", "animedia"):
            for consumer in config.portfolio(portfolio_id).consumers:
                assert consumer.kind == "player_config"
                assert consumer.fields == ("publisher_id",)
                assert "api_token" not in consumer.files

    def test_visual_references_are_not_targets(self, repo_root):
        """`w140.zona.plus` и `amd.online` — референсы, а не сайты."""
        text = (repo_root / "config" / "secret-hub.json").read_text(encoding="utf-8")
        assert "w140.zona.plus" not in text
        assert "amd.online" not in text

    def test_lords_is_untouched(self, config):
        """Lords остаётся тем же: способ доставки, unit'ы, каталоги, имена."""
        lords = config.portfolio("lords")
        assert [c.id for c in lords.consumers] == ["lords-01", "lords-02", "lords-03"]
        assert {c.kind for c in lords.consumers} == {"systemd_credential"}
        assert [c.unit for c in lords.consumers] == [
            "lords-01.service", "lords-02.service", "lords-03.service"]
        for consumer in lords.consumers:
            assert consumer.fields == ("api_token", "publisher_id")
            assert consumer.file_mode == 0o400
            assert consumer.credential_names == {
                "api_token": "cdnvideohub_api_token",
                "publisher_id": "cdnvideohub_publisher_id"}
            assert str(consumer.directory).startswith("/etc/site-factory/secrets/lords/")

    def test_directions_do_not_share_units_or_directories(self, config):
        """Изоляция направлений: применение одного не задевает другое."""
        seen_units: dict[str, str] = {}
        seen_dirs: dict[str, str] = {}
        for portfolio in config.portfolios:
            for consumer in portfolio.consumers:
                if consumer.unit:
                    assert seen_units.setdefault(consumer.unit, portfolio.id) == portfolio.id
                key = str(consumer.directory)
                assert seen_dirs.setdefault(key, portfolio.id) == portfolio.id


class TestSchemaBoundsTheNewKind:
    """Схема — источник истины, и она обязана отвергать неверную запись."""

    def _consumer(self, **overrides) -> dict:
        base = {
            "id": "zona-01", "kind": "player_config", "title": "витрина",
            "directory": "/etc/site-factory/secrets/zona/zona-01",
            "files": {"publisher_id": "player.json"},
            "owner": "root", "group": "lords",
            "file_mode": "0440", "directory_mode": "0750",
            "unit": "nova-zona-01.service",
            "dropin": "/etc/systemd/system/nova-zona-01.service.d/10-player.conf",
            "reload": {"kind": "systemd"},
        }
        base.update(overrides)
        return base

    def _errors(self, schema: dict, consumer: dict) -> list:
        document = {
            "version": 1, "store_dir": "/var/lib/x", "socket_path": "/run/x.sock",
            "provider": {"name": "cdnvideohub", "verify": {
                "base_url": "https://example.invalid/", "path": "countries",
                "method": "GET", "auth_header": "Authorization",
                "auth_scheme": "Bearer",
                "provenance": "фикстура теста, адрес недействителен"}},
            "portfolios": [{"id": "zona", "title": "Zona", "enabled": True,
                            "consumers": [consumer]}],
        }
        return list(jsonschema.Draft202012Validator(schema).iter_errors(document))

    def test_valid_showcase_consumer_is_accepted(self, schema):
        assert self._errors(schema, self._consumer()) == []

    def test_api_token_file_is_rejected_for_a_showcase(self, schema):
        """Файл токена у витрины — копия секрета без потребителя."""
        bad = self._consumer(files={"api_token": "api-token",
                                    "publisher_id": "player.json"})
        assert self._errors(schema, bad)

    def test_showcase_without_a_unit_is_rejected(self, schema):
        bad = self._consumer()
        del bad["unit"]
        assert self._errors(schema, bad)

    def test_showcase_without_a_dropin_is_rejected(self, schema):
        bad = self._consumer()
        del bad["dropin"]
        assert self._errors(schema, bad)

    def test_raw_delivery_still_requires_both_fields(self, schema):
        """Послабление для витрины не должно распространиться на Lords."""
        bad = self._consumer(kind="systemd_credential",
                             credential_names={"api_token": "a", "publisher_id": "p"})
        assert self._errors(schema, bad), (
            "systemd_credential обязан нести оба поля: витринное послабление "
            "не должно было стать общим")


class TestShowcaseDelivery:
    """Что реально оказывается на диске после применения."""

    def test_document_is_what_the_frontend_parses(self, tmp_path, fake_systemd):
        consumer = showcase_consumer(tmp_path)
        result = consumers_mod.apply_consumer(consumer, values(),
                                              backup_root=tmp_path / "backups")
        assert result.status == "applied", result.detail
        path = consumer.path_for("publisher_id")
        document = json.loads(path.read_text(encoding="utf-8"))
        # Ровно та проверка, которую делает фронтенд: значение есть, строка,
        # состоит из цифр и не начинается с нуля.
        publisher = str(document.get("publisher_id") or "").strip()
        assert publisher.isdigit() and not publisher.startswith("0")
        assert publisher == FAKE_PUBLISHER

    def test_no_api_token_file_is_created(self, tmp_path, fake_systemd):
        consumer = showcase_consumer(tmp_path)
        consumers_mod.apply_consumer(consumer, values(), backup_root=tmp_path / "backups")
        written = {p.name for p in consumer.directory.iterdir()}
        assert written == {"player.json"}

    def test_api_token_value_is_nowhere_on_disk(self, tmp_path, fake_systemd):
        """Токен не должен просочиться ни в документ, ни в drop-in."""
        consumer = showcase_consumer(tmp_path)
        consumers_mod.apply_consumer(consumer, values(), backup_root=tmp_path / "backups")
        for path in tmp_path.rglob("*"):
            if path.is_file():
                assert FAKE_TOKEN not in path.read_text(encoding="utf-8", errors="replace")

    def test_permissions_let_the_site_user_read_and_nobody_else(self, tmp_path, fake_systemd):
        consumer = showcase_consumer(tmp_path)
        consumers_mod.apply_consumer(consumer, values(), backup_root=tmp_path / "backups")
        mode = stat.S_IMODE(consumer.path_for("publisher_id").stat().st_mode)
        assert mode == 0o440
        assert not mode & 0o007, "файл не открывается миру ни при каком режиме"

    def test_dropin_carries_a_path_and_no_value(self, tmp_path, fake_systemd):
        consumer = showcase_consumer(tmp_path)
        consumers_mod.apply_consumer(consumer, values(), backup_root=tmp_path / "backups")
        text = consumer.dropin.read_text(encoding="utf-8")
        assert f"Environment=LORDS_PLAYER_CONFIG={consumer.path_for('publisher_id')}" in text
        assert FAKE_PUBLISHER not in text
        assert FAKE_TOKEN not in text

    def test_dropin_has_no_loadcredential(self, tmp_path, fake_systemd):
        """`LoadCredential` на витрине превратил бы пропажу файла в отказ старта."""
        consumer = showcase_consumer(tmp_path)
        consumers_mod.apply_consumer(consumer, values(), backup_root=tmp_path / "backups")
        assert "LoadCredential=" not in consumer.dropin.read_text(encoding="utf-8")

    def test_only_this_unit_is_restarted(self, tmp_path, fake_systemd):
        consumer = showcase_consumer(tmp_path)
        result = consumers_mod.apply_consumer(consumer, values(),
                                              backup_root=tmp_path / "backups")
        assert result.restarted == ("nova-zona-01.service",)
        restarts = [c for c in fake_systemd if c[:2] == ["systemctl", "restart"]]
        assert restarts == [["systemctl", "restart", "nova-zona-01.service"]]

    def test_second_apply_is_idempotent(self, tmp_path, fake_systemd):
        """Повторная отправка не создаёт второго состояния."""
        consumer = showcase_consumer(tmp_path)
        consumers_mod.apply_consumer(consumer, values(), backup_root=tmp_path / "backups")
        first = consumer.path_for("publisher_id").read_text(encoding="utf-8")
        consumers_mod.apply_consumer(consumer, values(), backup_root=tmp_path / "backups")
        assert consumer.path_for("publisher_id").read_text(encoding="utf-8") == first

    def test_status_reports_no_missing_token_file(self, tmp_path, fake_systemd):
        """`describe` не должен отчитываться о ненайденном файле токена.

        Витрина его не получает, и «нет того, чего не обещали» — не дефект.
        """
        from factory.secret_hub.registry import Portfolio
        consumer = showcase_consumer(tmp_path)
        consumers_mod.apply_consumer(consumer, values(), backup_root=tmp_path / "backups")
        portfolio = Portfolio(id="zona", title="Zona", enabled=True,
                              consumers=(consumer,))
        described = consumers_mod.describe(portfolio)
        fields = [f["field"] for f in described[0]["files"]]
        assert fields == ["publisher_id"]
        assert described[0]["target_ok"], described[0]["problems"]


def _rows_from(config) -> list[dict]:
    """Строки страницы в той форме, в какой их отдаёт `status` хаба.

    Значений в них нет и быть не может: операция `status` их не возвращает.
    Здесь воспроизводится именно эта форма — отпечаток, дата, список целей.
    """
    rows = []
    for portfolio in config.portfolios:
        rows.append({
            "portfolio": portfolio.id,
            "title": portfolio.title,
            "subtitle": "",
            "configured": False,
            "status": (portfolio.blocked_target.status
                       if portfolio.blocked_target else "unconfigured"),
            "consumers": [{"consumer": c.id, "title": c.title, "target_ok": True}
                          for c in portfolio.consumers],
        })
    return rows


class TestPanelShowsTheNewTargets:
    """Что владелец увидит в авторизованной форме."""

    @pytest.fixture
    def html(self, config):
        return ui_mod.page(_rows_from(config), "csrf-token-for-test", "/__factory-secrets")

    def test_every_direction_has_its_own_card(self, html):
        for portfolio_id in ("yami", "lords", "zona", "animedia", "amedia"):
            assert f'data-portfolio="{portfolio_id}"' in html

    def test_zona_and_animedia_are_distinguishable_by_their_domains(self, html):
        """Две похожие карточки — способ ввести секрет не туда."""
        assert "zonafilm.space" in html
        assert "animedia.icu" in html
        assert "animedia.space" in html

    def test_both_credential_fields_are_offered(self, html):
        assert html.count("CDNVideoHub API Token") == 5
        assert html.count("CDNVideoHub Publisher ID") == 5

    def test_api_token_field_is_a_password_field(self, html):
        assert html.count('class="f-token" type="password"') == 5

    def test_no_field_is_prefilled(self, html):
        """Существующее значение нельзя подставить: его неоткуда взять."""
        assert "value=" not in html

    def test_the_three_actions_are_present(self, html):
        assert "Проверить и сохранить" in html
        # «Заменить» и «Применить» появляются на настроенном направлении —
        # на ненастроенном их быть не должно, иначе кнопка обещает действие,
        # которого нет.
        assert "Заменить credentials" not in html
        assert "Применить к сайтам" not in html

    def test_configured_direction_offers_replace_and_apply(self, config):
        rows = _rows_from(config)
        for row in rows:
            if row["portfolio"] in {"zona", "animedia"}:
                row["configured"] = True
        html = ui_mod.page(rows, "csrf-token-for-test", "/__factory-secrets")
        assert html.count("Заменить credentials") == 2
        assert html.count("Применить к сайтам") == 2

    def test_blocked_direction_gets_no_apply_button(self, config):
        """У `amedia` применять по-прежнему некуда — кнопки быть не должно."""
        rows = _rows_from(config)
        for row in rows:
            row["configured"] = True
        html = ui_mod.page(rows, "csrf-token-for-test", "/__factory-secrets")
        # Пять направлений настроены, кнопка — у четырёх: amedia остаётся
        # BLOCKED_TARGET, и кнопка обещала бы действие, которого нет.
        assert html.count("Применить к сайтам") == 4
        amedia_card = html.split('data-portfolio="amedia"')[1].split("</section>")[0]
        assert "Применить к сайтам" not in amedia_card
        assert "Сайты этого направления ещё не переданы" in amedia_card

    def test_visual_references_never_reach_the_page(self, html):
        assert "w140.zona.plus" not in html
        assert "amd.online" not in html
