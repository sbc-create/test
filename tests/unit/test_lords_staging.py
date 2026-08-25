"""REQ-LORDS-STAGING: публикация трёх стендов Lords.

Проверяется конфигурация, которая поедет на сервер, и сценарий, который её
применит. Настоящий `nginx -t` здесь недоступен, и подменять его утверждением
нельзя: тесты проверяют то, что можно проверить разбором, а `nginx -t` остаётся
обязательным шагом сценария на хосте.
"""

from __future__ import annotations

import json
import re
import subprocess

import pytest
import yaml

from factory.lords import nginx_check
from factory.lords import staging as staging_mod
from factory.paths import PATHS

SCRIPT = PATHS.root / "automation/host/lords-staging-apply.sh"


@pytest.fixture(scope="module")
def sites():
    return staging_mod.sites()


@pytest.fixture(scope="module")
def configs(sites):
    return {
        "phase1": {f"{s.site_id}.conf": staging_mod.nginx_phase1(s) for s in sites}
        | {"00-default.conf": staging_mod.nginx_default_server(1)},
        "phase2": {f"{s.site_id}.conf": staging_mod.nginx_phase2(s) for s in sites}
        | {"00-default.conf": staging_mod.nginx_default_server(2)},
    }


# ---------------------------------------------------------------------------
# Реестр и пакеты — один источник истины
# ---------------------------------------------------------------------------
class TestRegistryAgreesWithPackages:
    def test_three_sites_are_published(self, sites):
        assert [s.site_id for s in sites] == ["lords-01", "lords-02", "lords-03"]

    def test_lords_04_is_not_published(self, sites):
        assert "lords-04" not in {s.site_id for s in sites}

    def test_ports_roots_and_hosts_are_unique(self, sites):
        assert len({s.port for s in sites}) == 3
        assert len({s.runtime_root for s in sites}) == 3
        assert len({s.apex for s in sites} | {s.www for s in sites}) == 6

    def test_ports_stay_inside_the_declared_range(self, sites):
        from factory import inventory
        low, high = inventory.target("lords-staging-control-01")["port_range"]
        for site in sites:
            assert low <= site.port <= high, f"{site.site_id}: порт вне диапазона цели"

    def test_a_domain_that_disagrees_with_the_package_is_refused(self, tmp_path):
        """Два источника, тихо разошедшихся в домене, — выкат на чужое имя."""
        root = tmp_path / "repo"
        (root / "config/directions").mkdir(parents=True)
        (root / "sites/lords-01").mkdir(parents=True)
        registry = json.loads(
            (PATHS.root / staging_mod.REGISTRY).read_text(encoding="utf-8"))
        registry["domains"] = registry["domains"][:1]
        registry["domains"][0]["apex"] = "someone-else.example"
        (root / staging_mod.REGISTRY).write_text(
            json.dumps(registry, ensure_ascii=False), encoding="utf-8")
        package = yaml.safe_load(
            (PATHS.sites / "lords-01/package.yaml").read_text(encoding="utf-8"))
        (root / "sites/lords-01/package.yaml").write_text(
            yaml.safe_dump(package, allow_unicode=True), encoding="utf-8")
        with pytest.raises(ValueError, match="не совпадают"):
            staging_mod.sites(root)

    def test_indexing_switched_on_refuses_to_publish(self, tmp_path):
        root = tmp_path / "repo"
        (root / "config/directions").mkdir(parents=True)
        (root / "sites/lords-01").mkdir(parents=True)
        registry = json.loads(
            (PATHS.root / staging_mod.REGISTRY).read_text(encoding="utf-8"))
        registry["domains"] = registry["domains"][:1]
        (root / staging_mod.REGISTRY).write_text(
            json.dumps(registry, ensure_ascii=False), encoding="utf-8")
        package = yaml.safe_load(
            (PATHS.sites / "lords-01/package.yaml").read_text(encoding="utf-8"))
        package["seo_indexing_enabled"] = True
        (root / "sites/lords-01/package.yaml").write_text(
            yaml.safe_dump(package, allow_unicode=True), encoding="utf-8")
        with pytest.raises(ValueError, match="индексация"):
            staging_mod.sites(root)


# ---------------------------------------------------------------------------
# Nginx
# ---------------------------------------------------------------------------
class TestNginxConfiguration:
    def test_both_phases_pass_the_offline_check(self, configs):
        for phase, expect_tls in (("phase1", False), ("phase2", True)):
            report = nginx_check.check_bundle(configs[phase], expect_tls=expect_tls)
            problems = {n: r["problems"] for n, r in report.items() if not r["ok"]}
            assert not problems, f"{phase}: {problems}"

    def test_no_directive_newer_than_the_target_version(self, configs):
        """`nginx -t` на свежем бинарнике этой разницы не поймает.

        Он молча примет `http2 on;`, а на целевом 1.18 это отказ запуска.
        """
        for phase in configs.values():
            for name, text in phase.items():
                for directive in nginx_check.INTRODUCED_AFTER_1_18:
                    assert not re.search(rf"^\s*{directive}\s", text, re.M), \
                        f"{name}: директива {directive} новее 1.18"

    def test_http2_is_a_listen_parameter_not_a_directive(self, configs):
        text = configs["phase2"]["lords-01.conf"]
        assert "listen 443 ssl http2;" in text
        assert not re.search(r"^\s*http2\s+on;", text, re.M)

    def test_phase_one_has_no_certificate(self, configs):
        for name, text in configs["phase1"].items():
            assert "ssl_certificate" not in text, f"{name}: сертификата ещё не существует"

    def test_phase_two_serves_tls_for_every_site(self, sites, configs):
        for site in sites:
            text = configs["phase2"][f"{site.site_id}.conf"]
            assert f"/etc/letsencrypt/live/{site.apex}/fullchain.pem" in text
            assert "ssl_protocols TLSv1.2 TLSv1.3;" in text

    def test_www_redirects_to_apex_with_308(self, sites, configs):
        for site in sites:
            text = configs["phase2"][f"{site.site_id}.conf"]
            assert f"return 308 https://{site.apex}$request_uri;" in text
            assert "return 301" not in text, "301 не сохраняет метод запроса"

    def test_http_redirects_to_https(self, sites, configs):
        for site in sites:
            assert "return 308 https://$host$request_uri;" in \
                configs["phase2"][f"{site.site_id}.conf"]

    def test_unknown_host_gets_421(self, configs):
        for phase in ("phase1", "phase2"):
            assert "return 421" in configs[phase]["00-default.conf"]
            assert "default_server" in configs[phase]["00-default.conf"]

    def test_no_site_is_behind_a_password(self, sites, configs):
        """Сайты публичны: пароль снят навсегда решением владельца."""
        for site in sites:
            text = configs["phase2"][f"{site.site_id}.conf"]
            assert 'auth_basic "' not in text, site.site_id
            assert "auth_basic_user_file" not in text, site.site_id

    def test_noindex_header_is_always_present(self, configs):
        for phase in configs.values():
            for name, text in phase.items():
                assert 'add_header X-Robots-Tag "noindex, nofollow" always;' in text, name

    def test_every_add_header_is_marked_always(self, configs):
        """Без `always` заголовок не попадёт на 404 и 5xx."""
        for phase in configs.values():
            for name, text in phase.items():
                for line in re.findall(r"^\s*add_header[^;]+;", text, re.M):
                    assert "always" in line, f"{name}: {line.strip()}"

    def test_a_site_proxies_only_to_its_own_port(self, sites, configs):
        for site in sites:
            text = configs["phase2"][f"{site.site_id}.conf"]
            targets = set(re.findall(r"proxy_pass http://127\.0\.0\.1:(\d+)", text))
            assert targets == {str(site.port)}, f"{site.site_id}: {targets}"

    def test_a_site_config_never_mentions_another_site(self, sites, configs):
        for site in sites:
            text = configs["phase2"][f"{site.site_id}.conf"]
            for other in sites:
                if other.site_id == site.site_id:
                    continue
                assert other.apex not in text, f"{site.site_id}: чужой домен {other.apex}"
                assert f":{other.port}" not in text, f"{site.site_id}: чужой порт"

    def test_configuration_carries_no_secret(self, configs):
        for phase in configs.values():
            for name, text in phase.items():
                assert "secret://" not in text, name
                assert "CDNVIDEOHUB" not in text, name


# ---------------------------------------------------------------------------
# systemd
# ---------------------------------------------------------------------------
class TestSystemdUnits:
    def test_runtime_listens_only_on_loopback(self, sites):
        for site in sites:
            unit = staging_mod.systemd_unit(site)
            assert "Environment=LORDS_HOST=127.0.0.1" in unit
            assert f"Environment=LORDS_PORT={site.port}" in unit

    def test_runtime_is_not_root_and_is_confined(self, sites):
        for site in sites:
            unit = staging_mod.systemd_unit(site)
            assert "User=lords" in unit and "User=root" not in unit
            for hardening in ("NoNewPrivileges=true", "ProtectSystem=strict",
                              "ProtectHome=true", "PrivateTmp=true"):
                assert hardening in unit, f"{site.site_id}: нет {hardening}"

    def test_each_unit_writes_only_into_its_own_data_directory(self, sites):
        for site in sites:
            unit = staging_mod.systemd_unit(site)
            paths = re.findall(r"^ReadWritePaths=(.+)$", unit, re.M)
            assert paths == [site.data_dir]
            for other in sites:
                if other.site_id != site.site_id:
                    assert other.runtime_root not in unit


# ---------------------------------------------------------------------------
# Сценарий применения
# ---------------------------------------------------------------------------
class TestApplyScript:
    def test_script_is_valid_bash(self):
        result = subprocess.run(["bash", "-n", str(SCRIPT)], capture_output=True, text=True)
        assert result.returncode == 0, result.stderr

    def test_script_stops_on_error(self):
        text = SCRIPT.read_text(encoding="utf-8")
        assert "set -Eeuo pipefail" in text
        assert "trap " in text

    def test_nginx_is_verified_before_every_reload(self):
        """Перезагрузка без проверки оставила бы сервер со сломанным конфигом."""
        text = SCRIPT.read_text(encoding="utf-8")
        body = text.split("install_phase() {", 1)[1]
        check_at = body.index("nginx -t")
        reload_at = body.index("systemctl reload nginx")
        assert check_at < reload_at, "reload стоит раньше проверки"
        assert "|| die" in body[check_at:reload_at], "провал nginx -t не останавливает сценарий"

    def test_script_never_prints_a_secret(self):
        text = SCRIPT.read_text(encoding="utf-8")
        for line in text.splitlines():
            stripped = line.strip()
            if stripped.startswith(("log ", "warn ", "echo ")):
                assert "${password}" not in stripped, stripped
                assert "${API_TOKEN}" not in stripped, stripped
    def test_credentials_file_is_root_only(self):
        """Файла с паролем больше не существует — создавать его нечему."""
        text = SCRIPT.read_text(encoding="utf-8")
        assert "lords-staging-credentials" not in text
    def test_script_refuses_a_port_held_by_a_stranger(self):
        text = SCRIPT.read_text(encoding="utf-8")
        assert "занят посторонним процессом" in text

    def test_script_does_not_fight_over_the_default_server(self):
        """Два default_server на одном порту — отказ nginx -t."""
        text = SCRIPT.read_text(encoding="utf-8")
        assert "INSTALL_DEFAULT=0" in text
        assert "default_server" in text

    def test_script_touches_only_its_own_paths(self):
        text = SCRIPT.read_text(encoding="utf-8")
        for destructive in re.findall(r"^\s*rm -rf?[^\n]*", text, re.M):
            assert any(marker in destructive for marker in
                       ("${stale}", "${NGINX_DIR}", "${target}")), destructive

    def test_script_is_idempotent_where_it_matters(self):
        text = SCRIPT.read_text(encoding="utf-8")
        # Пользователь, пароль, сертификат и релиз создаются только при отсутствии.
        assert 'if ! id -u "${SERVICE_USER}"' in text
        assert 'if [[ -d "${target}" ]]' in text
        # Сертификат: существующая линия переиспользуется, а не выпускается
        # заново, и обязана покрывать оба имени.
        assert 'chain="/etc/letsencrypt/live/${apex}/fullchain.pem"' in text
        assert 'if [[ -s "${chain}" ]]' in text
        assert 'cert_covers "${chain}" "${apex}"' in text

    def test_renewal_reloads_nginx(self):
        text = SCRIPT.read_text(encoding="utf-8")
        hook = text.split("renewal-hooks/deploy/lords-nginx-reload.sh", 1)[1]
        assert "nginx -t" in hook and "systemctl reload nginx" in hook

    def test_script_does_not_enable_indexing_or_analytics(self):
        text = SCRIPT.read_text(encoding="utf-8").lower()
        for forbidden in ("seo_indexing_enabled=true", "metrika", "webmaster",
                          "yandex", "production"):
            assert forbidden not in text.replace("не выкатывает production", ""), forbidden


class TestApplyScriptChecksCommit:
    """Выкатывается объявленный commit, а не то, что лежит в рабочем каталоге."""

    def test_script_compares_head_against_an_expected_sha(self):
        text = SCRIPT.read_text(encoding="utf-8")
        assert "LORDS_EXPECT_SHA" in text
        assert "rev-parse HEAD" in text
        assert "ожидался commit" in text

    def test_script_refuses_a_dirty_worktree(self):
        """Грязное дерево означает, что выложится не то, что в commit."""
        text = SCRIPT.read_text(encoding="utf-8")
        assert "status --porcelain" in text
        assert "рабочее дерево грязное" in text


class TestApplyScriptBacksUpAndRollsBack:
    """Любой отказ возвращает nginx и systemd в исходное состояние."""

    def test_script_snapshots_before_the_first_mutation(self):
        text = SCRIPT.read_text(encoding="utf-8")
        assert "BACKUP_ROOT" in text
        assert "etc-nginx.tar.gz" in text
        # Снимок обязан быть готов раньше, чем скрипт начнёт что-то менять.
        snapshot = text.index("ROLLBACK_READY=1")
        first_install = text.index('install_phase phase1')
        assert snapshot < first_install, "снимок делается после первой мутации"

    def test_rollback_restores_config_units_and_include(self):
        text = SCRIPT.read_text(encoding="utf-8")
        rollback = text.split("rollback() {", 1)[1].split("\non_error()", 1)[0]
        assert "nginx-lords" in rollback
        assert "lords-include.conf" in rollback
        assert "systemctl daemon-reload" in rollback
        assert "nginx -t" in rollback, "откат перезагружает nginx без проверки"

    def test_rollback_does_not_reload_nginx_on_a_broken_config(self):
        text = SCRIPT.read_text(encoding="utf-8")
        rollback = text.split("rollback() {", 1)[1].split("\non_error()", 1)[0]
        assert "if nginx -t" in rollback
        assert "Reload НЕ выполнялся" in rollback

    def test_failed_acceptance_triggers_a_rollback(self):
        """Применилось, но отвечает не тем — тоже повод откатиться."""
        text = SCRIPT.read_text(encoding="utf-8")
        tail = text.split("публичная приёмка не прошла", 1)[1]
        assert "rollback" in tail
        assert "откачен" in tail

    def test_rollback_keeps_previous_releases(self):
        """Откатываться некуда, если откат сносит прежний релиз."""
        text = SCRIPT.read_text(encoding="utf-8")
        rollback = text.split("rollback() {", 1)[1].split("\non_error()", 1)[0]
        assert "RUNTIME_ROOT" not in rollback, "откат трогает каталог релизов"


class TestNoBasicAuthEverAgain:
    """Пароля нет и не появляется.

    Прежний набор проверял, что сценарий создаёт bcrypt-пароль и бережно его
    хранит. Решение владельца отменило саму задачу: пароль когда-то завёл этот
    же сценарий, а не человек, и теперь он его не заводит. Проверяется
    обратное — что ни одна ветка не создаёт Basic Auth заново.
    """

    def test_the_apply_script_creates_no_password(self):
        text = SCRIPT.read_text(encoding="utf-8")
        for forbidden in ("htpasswd -bcB", "apache2-utils", "lords-staging-credentials"):
            assert forbidden not in text, forbidden

    def test_the_apply_script_does_not_reference_a_password_file(self):
        text = SCRIPT.read_text(encoding="utf-8")
        assert "auth_basic_user_file" not in text

    def test_the_generated_config_has_no_password(self):
        for site in staging_mod.sites():
            config = staging_mod.nginx_phase2(site)
            assert 'auth_basic "' not in config, site.site_id
            assert "auth_basic_user_file" not in config, site.site_id

    def test_phase_one_also_has_no_password(self):
        for site in staging_mod.sites():
            config = staging_mod.nginx_phase1(site)
            assert 'auth_basic "' not in config, site.site_id

    def test_indexing_stays_closed_without_the_password(self):
        """От роботов сайт закрыт заголовком и robots.txt, а не паролем."""
        for site in staging_mod.sites():
            config = staging_mod.nginx_phase2(site)
            assert "noindex, nofollow" in config, site.site_id

    def test_no_function_can_bring_the_password_back(self):
        """Параметра, включающего пароль, не существует намеренно."""
        import inspect
        signature = inspect.signature(staging_mod.nginx_phase2)
        assert "basic_auth" not in signature.parameters


class TestApplyScriptAcceptance:
    """После запуска сценарий проверяет то, что получилось, а не заявляет это."""

    def test_acceptance_expects_a_public_site(self):
        text = SCRIPT.read_text(encoding="utf-8")
        assert "сайт публичен" in text
        assert "вернулся Basic Auth" in text, "приёмка не замечает возврата пароля"

    def test_acceptance_checks_indexing_is_closed_on_a_public_response(self):
        text = SCRIPT.read_text(encoding="utf-8")
        assert "x-robots-tag:.*noindex" in text
        assert "Disallow: /" in text

    def test_acceptance_checks_the_runtime_serves_in_parallel(self):
        """Однопоточный рантайм обязан быть замечен на хосте, а не только в тестах."""
        text = SCRIPT.read_text(encoding="utf-8")
        assert "параллельных запросов" in text

    def test_acceptance_verifies_the_neighbours_default_deny(self):
        """Чужой default_server проверяется, а не предполагается."""
        text = SCRIPT.read_text(encoding="utf-8")
        tail = text.split("Неизвестный Host", 1)[1]
        assert "no-such-host.invalid" in tail
        assert "не отдаёт содержимое Lords" in tail
