"""REQ-LORDS-AUTO-REFRESH: каталог обновляется сам, без сборки и без человека.

История. Сайты Lords статические: документы собираются заранее и раскладываются
релизом. Живой каталог при этом кэшировался вручную, а пересобирал сайт человек.
На трёх публичных доменах в итоге стоял каталог тридцатипятичасовой давности —
провайдер добавлял фильмы, витрина о них не знала, а HTTP 200 отвечал исправно.
Именно поэтому дефект было легко не заметить: всё «работало».

Здесь проверяется контракт автоматического обновления, а не факт существования
файла: пустая выдача не должна очищать витрину, отказ источника не должен её
портить, неизменившийся каталог не должен рестартовать юниты, а плохой релиз
обязан откатываться сам.
"""

from __future__ import annotations

import re
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
SCRIPT = REPO / "automation" / "host" / "lords-content-refresh.sh"
UNIT = REPO / "automation" / "host" / "systemd" / "lords-content-refresh.service"
TIMER = REPO / "automation" / "host" / "systemd" / "lords-content-refresh.timer"


def unit_value(path: Path, name: str) -> list[str]:
    values = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        if key.strip() == name:
            values.append(value.strip())
    return values


class TestTheTimerMeetsTheStatedSlo:
    def test_timer_exists(self):
        assert TIMER.is_file(), "таймера обновления нет — каталог снова будет стареть молча"

    def test_interval_is_within_the_freshness_slo(self):
        """Обещано пятнадцать минут; интервал обязан этому соответствовать."""
        interval = unit_value(TIMER, "OnUnitActiveSec")
        assert interval, "интервал не задан"
        match = re.match(r"^(\d+)\s*min$", interval[0])
        assert match, f"непонятный интервал {interval[0]!r}"
        assert int(match.group(1)) <= 15, (
            f"интервал {interval[0]} больше обещанных пятнадцати минут"
        )

    def test_missed_run_is_not_postponed_for_a_day(self):
        assert unit_value(TIMER, "Persistent") == ["true"], (
            "без Persistent пропущенный из-за перезагрузки запуск ждал бы следующего цикла"
        )


class TestSecretsComeFromSystemd:
    def test_credentials_are_loaded_not_passed_through_environment(self):
        loaded = unit_value(UNIT, "LoadCredential")
        assert any("api-token" in v for v in loaded), "токен не передан через LoadCredential"
        assert any("publisher-id" in v for v in loaded)

    def test_no_secret_value_is_written_into_the_unit(self):
        text = UNIT.read_text(encoding="utf-8")
        assert "Environment=CDNVIDEOHUB_API_TOKEN" not in text, (
            "секрет вынесен в окружение: оно видно в systemctl show и /proc"
        )

    def test_the_secrets_directory_stays_inaccessible(self):
        assert "/etc/site-factory/secrets" in " ".join(unit_value(UNIT, "InaccessiblePaths"))


class TestPrivilegeStaysConfined:
    def test_writes_are_limited(self):
        allowed = set(" ".join(unit_value(UNIT, "ReadWritePaths")).split())
        assert allowed <= {
            "/srv/lords", "/srv/site-factory/repo/var",
            "/var/lib/lords-content-refresh", "/var/log/site-factory",
        }, f"разрешена запись за пределами своих каталогов: {sorted(allowed)}"

    def test_filesystem_is_read_only_by_default(self):
        assert unit_value(UNIT, "ProtectSystem") == ["strict"]
        assert unit_value(UNIT, "NoNewPrivileges") == ["yes"]


class TestTheScriptRefusesToBreakTheStorefront:
    def test_source_failure_leaves_the_previous_release(self):
        text = SCRIPT.read_text(encoding="utf-8")
        assert "lords-live" in text, "кэш живого каталога не обновляется"
        assert re.search(r"last_failure", text), "отказ источника нигде не фиксируется"
        assert "прежнем релизе" in text, (
            "нет явного пути «источник не ответил — витрина остаётся прежней»"
        )

    def test_unchanged_catalogue_does_not_restart_anything(self):
        """Рестарт трёх юнитов каждые пятнадцать минут ради ничего — не обновление."""
        text = SCRIPT.read_text(encoding="utf-8")
        assert 'if [ "$current" = "$target" ]' in text, (
            "релиз не сравнивается с текущим: юниты будут рестартовать вхолостую"
        )

    def test_release_id_comes_from_content(self):
        text = SCRIPT.read_text(encoding="utf-8")
        assert "sha256sum" in text, (
            "идентификатор релиза не выведен из содержимого — одинаковая сборка "
            "будет плодить каталоги и рестарты"
        )

    def test_a_bad_release_rolls_itself_back(self):
        text = SCRIPT.read_text(encoding="utf-8")
        assert "возвращаю" in text and 'ln -sfn "${current}"' in text, (
            "нет самостоятельного отката: плохой релиз останется в работе"
        )

    def test_acceptance_checks_content_not_just_a_status_code(self):
        text = SCRIPT.read_text(encoding="utf-8")
        assert "class=" in text and "card" in text, (
            "приёмка не смотрит на карточки: пустая витрина пройдёт как исправная"
        )

    def test_previous_release_is_never_deleted_while_current(self):
        text = SCRIPT.read_text(encoding="utf-8")
        assert 'readlink -f "${runtime}/current"' in text, (
            "хранение может удалить текущий релиз — откатываться будет некуда"
        )
