"""Граница root: root-юнит обязан исполнять только код, принадлежащий root.

Служба, работающая от root и исполняющая код из каталога, открытого на запись
учётной записи агента, отдаёт root этой учётной записи: достаточно переписать
файл и дождаться таймера. Запреты профиля (`sudo`, `systemctl`) при этом
остаются на месте и ничего не значат — граница обходится мимо них.

Проверяется вся цепочка, а не только `ExecStart`: интерпретатор, `PYTHONPATH`,
`WorkingDirectory`, каталог инструментов, `EnvironmentFile`, шебанг и элементы
`PATH`. Реализация — `automation/hardening/audit_root_units.py`, общая с
установщиком: проверка и транзакция обязаны понимать «безопасно» одинаково,
иначе зелёный тест и успешная установка перестают означать одно и то же.

Тесты делятся на два рода, и разница между ними существенная:

* **контракт поставки** — над файлами ветки. Выполняется всегда и обязан быть
  зелёным: он проверяет, что закрепление описано полно и никуда не уводит код
  из-под root.
* **состояние хоста** — над установленной машиной. Пока транзакция владельца не
  выполнена, закреплённого рантайма на хосте нет, и проверка помечается
  SKIPPED с причиной. Пройденной она от этого не становится: дефект описан в
  `artifacts/evidence/.../FINDING-root-units-run-agent-writable-scripts.md`, и
  ровно эта проверка станет обязательной сразу после установки.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

HARDENING = Path(__file__).resolve().parents[2] / "automation" / "hardening"
sys.path.insert(0, str(HARDENING))

import audit_root_units as audit_mod  # noqa: E402

#: Пять юнитов, названных владельцем в задании. Расширять перечень можно,
#: сужать — нет: он фиксирует объём, который был согласован.
OWNER_NAMED = {
    "nova-daily-refresh.service",
    "site-factory-health.service",
    "site-factory-backup.service",
    "lords-canary-switch@.service",
    "site-factory-restore-proof.service",
}

#: Каталоги, принадлежащие агенту. Код root'а не имеет права резолвиться сюда
#: ни одним из способов — включая владение родительским каталогом: владелец
#: переименует подкаталог и подставит свой, какими бы ни были права на сам файл.
AGENT_ROOTS = ("/srv/site-factory", "/srv/sites", "/home/")


@pytest.fixture(scope="module")
def manifest() -> dict:
    return json.loads((HARDENING / "manifest.json").read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def release() -> dict:
    path = HARDENING / "release" / "release.json"
    if not path.exists():
        pytest.skip("бандл не собран в этом дереве: automation/hardening/release/release.json")
    return json.loads(path.read_text(encoding="utf-8"))


class TestShippedContract:
    """Над файлами ветки. Обязан быть зелёным всегда."""

    def test_every_owner_named_unit_is_covered(self, manifest):
        covered = {u["unit"] for u in manifest["units"]}
        missing = OWNER_NAMED - covered
        assert not missing, f"названные владельцем юниты не закреплены: {sorted(missing)}"

    def test_every_covered_unit_records_its_vector(self, manifest):
        """Запись без вектора — это «починили на всякий случай»."""
        for unit in manifest["units"]:
            assert unit.get("vector"), f"{unit['unit']}: не записано, чем именно он был уязвим"

    def test_no_pinned_path_resolves_into_agent_territory(self, manifest):
        """Ни один закрепляемый путь КОДА не ведёт в каталог агента."""
        pinned_root = manifest["release"]["pinned_root"]
        assert pinned_root.startswith("/opt/"), (
            "закрепление имеет смысл только там, где ни один родитель не "
            "принадлежит агенту")
        for unit in manifest["units"]:
            for key in ("exec_start", "working_directory"):
                value = unit.get(key) or ""
                assert not value.startswith(AGENT_ROOTS), f"{unit['unit']}.{key}: {value}"
            for name, value in (unit.get("environment") or {}).items():
                if name in ("FACTORY_REPO", "FACTORY_ROOT", "LORDS_ARTIFACT_ROOT",
                            "LORDS_CANARY_STAGING"):
                    # Это пути к ДАННЫМ: root их читает и пишет по назначению,
                    # а не исполняет. Их расположение — вопрос не этой границы.
                    continue
                assert not value.startswith(AGENT_ROOTS), (
                    f"{unit['unit']}: {name}={value} — код не может приходить отсюда")

    def test_path_is_pinned_for_every_unit(self, manifest):
        """`#!/usr/bin/env bash` ищет интерпретатор по PATH."""
        path_env = manifest["pinned_path_env"]
        assert path_env
        for entry in path_env.split(":"):
            assert not entry.startswith(AGENT_ROOTS), f"PATH содержит {entry}"

    def test_relocated_trees_keep_their_bytes(self, manifest):
        """Перенос прав не повод подменять версию боевого конвейера."""
        for item in manifest["relocate"]:
            assert item["from"].startswith(AGENT_ROOTS), (
                "переносить имеет смысл только то, что лежит у агента")
            assert "note" in item and item["note"]

    def test_nothing_affected_is_left_out_of_scope(self, manifest):
        """Ноль по «целевым» юнитам — не ноль.

        Граница root либо закрыта на хосте, либо нет. Юнит другого продукта,
        исполняющий от root файл `0664 claude:claude`, держит её открытой ровно
        так же, как свой. Поэтому перечень вне области обязан быть пуст, а
        причина этого — записана.
        """
        out = manifest["out_of_scope"]
        assert out["units"] == [], (
            "затронутые юниты выведены за область: "
            f"{out['units']} — это отчёт о нуле, которого нет")
        assert out["note"], "пустой перечень обязан объяснять, почему он пуст"

    def test_every_affected_host_unit_is_covered(self, manifest):
        """Сверка с фактическим хостом, а не с собственным перечнем."""
        if not audit_mod.UNIT_DIR.is_dir():
            pytest.skip("systemd на этой машине нет: состояние хоста не измерено")
        report = audit_mod.audit()
        affected = set(report["units_with_problems"])
        covered = {u["unit"] for u in manifest["units"]}
        missing = affected - covered
        assert not missing, (
            "затронуты, но не входят в транзакцию: " + ", ".join(sorted(missing)))

    def test_freezing_someone_elses_product_is_declared(self, manifest):
        """Заморозка чужого кода — последствие, а не деталь реализации."""
        coordination = manifest.get("coordination_required") or []
        assert coordination, (
            "перенос скриптов чужого продукта останавливает действие его выкладок; "
            "это обязано быть объявлено, а не обнаружено потом")
        for item in coordination:
            assert item["units"] and item["consequence"] and item["owner_action"]

    def test_no_archive_is_shipped(self):
        """Якорем доверия служит текстовый провенанс, а не архив.

        Правило репозитория «архивы в git не хранятся» проверяется отдельным
        тестом (`test_repo_hygiene`). Обходить его исключением в `.gitignore`
        было бы подгонкой под задачу, а пофайловый провенанс и без того
        строже: один общий хеш сказал бы «не сошлось», не назвав виновника.
        """
        assert not list((HARDENING / "release").glob("*.tar.gz"))
        assert not list((HARDENING / "release").glob("*.zip"))

    def test_aggregate_digest_matches_the_provenance(self, release):
        """Совокупный отпечаток обязан пересчитываться из провенанса."""
        import hashlib
        provenance = json.loads(
            (HARDENING / "release" / "provenance.json").read_text(encoding="utf-8"))
        digest = hashlib.sha256()
        for item in sorted(provenance["files"], key=lambda f: f["path"]):
            digest.update(item["path"].encode())
            digest.update(item["sha256"].encode())
        assert digest.hexdigest() == release["aggregate_sha256"], (
            "release.json и provenance.json разошлись: отпечаток, который не "
            "сходится, не является доказательством")
        assert provenance["file_count"] == release["file_count"]

    def test_every_file_records_its_source_commit(self):
        """Файл без провенанса в root-owned дереве — байт без ответа «откуда».

        `SELF` — законный источник: это коммит самой транзакции. Его хеша во
        время сборки ещё нет, и подставлять туда что-то похожее на хеш было бы
        враньём. Совпадение `SELF` с фактическим коммитом проверяет
        `verify-self-reference.sh` уже после фиксации.
        """
        provenance = json.loads(
            (HARDENING / "release" / "provenance.json").read_text(encoding="utf-8"))
        assert provenance["files"]
        for item in provenance["files"]:
            commit = item["source_commit"]
            assert commit == "SELF" or len(commit) == 40, item["path"]
            assert len(item["sha256"]) == 64, item["path"]

    def test_self_reference_is_verifiable_not_promised(self):
        """Самоссылка обязана иметь подтверждающий механизм."""
        verifier = HARDENING / "verify-self-reference.sh"
        assert verifier.exists(), (
            "манифест ссылается на SELF, но проверить это нечем — "
            "тогда совпадение коммитов остаётся обещанием")
        text = verifier.read_text(encoding="utf-8")
        assert "git" in text and "sha256" in text

    def test_all_transaction_commits_coincide_by_construction(self):
        """Источник кода и источник транзакции — один объект, а не два сверенных."""
        manifest = json.loads((HARDENING / "manifest.json").read_text(encoding="utf-8"))
        primary = manifest["sources"][0]
        assert primary["commit"] == "SELF", (
            "первичный источник обязан быть самоссылкой: иначе SOURCE_COMMIT и "
            "TRANSACTION_COMMIT — разные коммиты, и их идентичность пришлось бы "
            "доказывать отдельно на каждый файл")

    def test_transaction_does_not_publish_anything(self):
        """Закрепление не расширяет публичную поверхность.

        Закрепление сужает поверхность, публикация расширяет. В одной атомарной
        операции они несовместимы: отказ публикации откатил бы удавшееся
        закрепление, то есть вернул бы дыру из-за проблемы с nginx.

        Здесь проверяется, что установщик не изменяет конфигурацию nginx и не
        зовёт публикатор. Чтение `/etc/nginx` в бэкап разрешено: снять копию
        перед работой — не то же самое, что править.
        """
        text = (HARDENING / "pin-root-units.sh").read_text(encoding="utf-8")
        forbidden = (
            "install-secret-hub.sh",   # штатный публикатор
            "ensure_include",          # добавление include в vhost
            "nginx -s reload",
            "systemctl reload nginx",
            "systemctl restart nginx",
        )
        for token in forbidden:
            assert token not in text, (
                f"установщик содержит публикующую операцию «{token}»: "
                "закрепление и публикация обязаны оставаться разными шагами")

        for line in text.splitlines():
            stripped = line.strip()
            if stripped.startswith("#") or "/etc/nginx" not in stripped:
                continue
            assert stripped.startswith(("cp -a", "install -d")), (
                f"строка трогает /etc/nginx не только на чтение: {stripped}")

    def test_credential_units_are_covered(self, manifest):
        """Юнит с расшифрованными credentials — худший случай из всех."""
        holders = [u["unit"] for u in manifest["units"] if u.get("holds_credentials")]
        assert "site-factory-secret-hub.service" in holders, (
            "сам хаб импортирует factory из каталога агента — без него "
            "закрепление соседей было бы представлением")
        assert len(holders) >= 5


class TestSimulationProvesGlobalZero:
    """Каким станет хост — посчитано до того, как что-то тронуто.

    Установщик проверяет результат у себя, но получить такой отчёт можно только
    выполнив операцию, а отчёт операции о самой себе — слабейшее из
    доказательств. Симуляция отвечает на тот же вопрос заранее.
    """

    @pytest.fixture
    def report(self, manifest, release):
        import simulate_post_transaction as sim
        return sim.simulate(manifest, release["release_id"])

    def test_no_root_unit_keeps_agent_writable_code(self, report):
        assert report["global_clean"], (
            "после транзакции остались бы нарушения:\n"
            + "\n".join(f"  {f['unit']}: {f['kind']}={f['path']} — {f['reason']}"
                        for f in report["findings"][:10]))

    def test_every_root_unit_on_the_host_is_examined(self, report):
        assert report["root_units"] >= 27, (
            "симуляция обязана охватывать все root-юниты хоста, а не только "
            f"закрепляемые (охвачено {report['root_units']})")

    def test_credential_units_are_clean_after(self, report):
        dirty = [r["unit"] for r in report["rows"]
                 if r["credential_access"] and not r["clean"]]
        assert not dirty, f"юниты с credentials остались бы грязными: {dirty}"


class TestAuditImplementation:
    """Проверка обязана уметь падать: правило, которое ничего не ловит, — не правило."""

    def _unit_dir(self, tmp_path: Path, body: str, mode: int = 0o777) -> Path:
        script = tmp_path / "target.sh"
        script.write_text("#!/bin/sh\n", encoding="utf-8")
        os.chmod(script, mode)
        unit_dir = tmp_path / "units"
        unit_dir.mkdir()
        (unit_dir / "probe.service").write_text(body.format(exe=script), encoding="utf-8")
        return unit_dir

    def test_world_writable_target_is_detected(self, tmp_path):
        report = audit_mod.audit(self._unit_dir(tmp_path, "[Service]\nExecStart={exe}\n"))
        assert not report["clean"]

    def test_missing_user_means_root(self, tmp_path):
        report = audit_mod.audit(self._unit_dir(tmp_path, "[Service]\nExecStart={exe}\n"))
        assert report["root_units_audited"] == 1

    def test_non_root_unit_is_out_of_scope(self, tmp_path):
        report = audit_mod.audit(
            self._unit_dir(tmp_path, "[Service]\nUser=nobody\nExecStart={exe}\n"))
        assert report["clean"] and report["root_units_audited"] == 0

    def test_dropin_reset_is_honoured(self, tmp_path):
        """Без правила сброса закреплённый юнит числился бы нарушителем."""
        unit_dir = self._unit_dir(tmp_path, "[Service]\nExecStart={exe}\n")
        dropin = unit_dir / "probe.service.d"
        dropin.mkdir()
        (dropin / "10-pin.conf").write_text(
            "[Service]\nExecStart=\nExecStart=/bin/true\n", encoding="utf-8")
        report = audit_mod.audit(unit_dir)
        paths = {p["path"] for p in report["problems"]}
        assert not any(str(tmp_path) in p for p in paths), (
            "drop-in заменил команду — прежний ExecStart проверять не следует")

    def test_pythonpath_is_treated_as_code(self, tmp_path):
        """Подменённый модуль исполняется так же, как скрипт."""
        unit_dir = tmp_path / "units"
        unit_dir.mkdir()
        loose = tmp_path / "loose"
        loose.mkdir()
        os.chmod(loose, 0o777)
        (unit_dir / "probe.service").write_text(
            f"[Service]\nExecStart=/bin/true\nEnvironment=PYTHONPATH={loose}\n",
            encoding="utf-8")
        report = audit_mod.audit(unit_dir)
        assert any("PYTHONPATH" in p["reason"] for p in report["problems"])

    def test_symlink_mode_bits_are_not_a_finding(self, tmp_path):
        """У ссылки режим на Linux всегда 0777 и ни на что не влияет."""
        unit_dir = tmp_path / "units"
        unit_dir.mkdir()
        (unit_dir / "probe.service").write_text(
            "[Service]\nExecStart=/bin/true\nEnvironment=PATH=/usr/bin:/bin\n",
            encoding="utf-8")
        report = audit_mod.audit(unit_dir)
        assert report["clean"], (
            f"ложное срабатывание на системных ссылках: {report['problems'][:3]}")


def _pinned_installed(manifest: dict) -> Path | None:
    current = Path(manifest["release"]["current_link"])
    return current if current.exists() else None


class TestHostExecutionChain:
    """Над установленной машиной. Строгая — но только после транзакции."""

    def test_scoped_units_have_no_agent_writable_code(self, manifest):
        if _pinned_installed(manifest) is None:
            pytest.skip(
                "закреплённый рантайм ещё не установлен "
                f"({manifest['release']['current_link']} отсутствует). "
                "Транзакция владельца не выполнялась; цепочка исполнения root-юнитов "
                "на этом хосте ПО-ПРЕЖНЕМУ содержит код, доступный агенту на запись — "
                "дефект описан в artifacts/evidence/templates-secret-hub-cloud-access-006/"
                "FINDING-root-units-run-agent-writable-scripts.md. Пропуск здесь "
                "означает «ещё не исправлено», а не «исправно».")
        scope = {u["unit"] for u in manifest["units"]}
        report = audit_mod.audit(only=sorted(scope))
        assert report["clean"], (
            "после закрепления в целевых юнитах остались нарушения:\n"
            + "\n".join(f"  {p['unit']}: {p['path']} — {p['reason']}"
                        for p in report["problems"]))

    def test_no_credential_unit_runs_agent_writable_code(self, manifest):
        if _pinned_installed(manifest) is None:
            pytest.skip("закреплённый рантайм ещё не установлен — см. соседний тест")
        report = audit_mod.audit()
        assert not report["credential_units_with_problems"], (
            "юнит получает расшифрованные credentials и исполняет код, доступный "
            "агенту на запись: "
            + ", ".join(report["credential_units_with_problems"]))


class TestAuditRunsOnThisHost:
    """Аудит обязан отработать на живой машине и дать разбираемый ответ.

    Этот тест зелёный независимо от того, исправлен хост или нет: он проверяет
    работоспособность самой проверки, а не состояние хоста. Без него поломка
    аудита выглядела бы как «нарушений не найдено».
    """

    def test_audit_produces_a_parseable_report(self):
        if not Path("/etc/systemd/system").is_dir():
            pytest.skip("systemd на этой машине нет: состояние хоста не измерено")
        report = audit_mod.audit()
        assert report["root_units_audited"] > 0, "ни одного root-юнита не разобрано"
        for key in ("problem_count", "units_with_problems",
                    "credential_units_with_problems", "clean"):
            assert key in report

    def test_audit_cli_exits_nonzero_when_dirty(self, tmp_path):
        script = tmp_path / "t.sh"
        script.write_text("#!/bin/sh\n", encoding="utf-8")
        os.chmod(script, 0o777)
        unit_dir = tmp_path / "units"
        unit_dir.mkdir()
        (unit_dir / "p.service").write_text(
            f"[Service]\nExecStart={script}\n", encoding="utf-8")
        result = subprocess.run(
            [sys.executable, str(HARDENING / "audit_root_units.py"),
             "--unit-dir", str(unit_dir), "--json"],
            capture_output=True, text=True, timeout=60)
        assert result.returncode == 1, "грязный аудит обязан возвращать ненулевой код"
        assert json.loads(result.stdout)["clean"] is False
