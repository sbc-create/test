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
        """Запрещено значение, а не имя.

        `CDNVIDEOHUB_API_TOKEN_CREDENTIAL` несёт имя credential'а — по нему
        factory находит файл, и ровно так же устроены lords-0X.service. Запрет
        обязан отличать имя от значения, иначе он запрещает штатную схему.
        """
        for value in unit_value(UNIT, "Environment"):
            name, _, content = value.partition("=")
            if name.strip() in ("CDNVIDEOHUB_API_TOKEN", "CDNVIDEOHUB_PUBLISHER_ID"):
                raise AssertionError(
                    f"{name} присвоено в окружении: оно видно в systemctl show и /proc"
                )
            if name.strip().endswith("_CREDENTIAL"):
                # Здесь допустимо только имя credential'а, а не путь и не значение.
                assert "/" not in content, f"{name} содержит путь, а не имя: {content}"

    def test_the_secrets_directory_stays_inaccessible(self):
        assert "/etc/site-factory/secrets" in " ".join(unit_value(UNIT, "InaccessiblePaths"))


class TestPrivilegeStaysConfined:
    def test_writes_are_limited(self):
        allowed = set(" ".join(unit_value(UNIT, "ReadWritePaths")).split())
        assert allowed <= {
            "/srv/lords",
            # Кэш каталога и отчёт о выборке — два разных дерева репозитория.
            "/srv/site-factory/repo/var",
            "/srv/site-factory/repo/artifacts",
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


class TestCredentialIdsMatchWhatTheCodeLooksFor:
    """REQ-LORDS-REFRESH-CREDENTIAL-ID: имя credential'а совпадает с искомым.

    Первый же запуск таймера отказал с сообщением «источник не ответил», хотя
    источник был ни при чём: в `LoadCredential` идентификатор был написан через
    дефис, а `factory` ищет его с подчёркиваниями. Имя файла-источника при этом
    действительно пишется через дефис — перепутать их легко, а отказ выглядит
    как проблема сети.
    """

    def _load_credentials(self) -> dict[str, str]:
        pairs = {}
        for value in unit_value(UNIT, "LoadCredential"):
            ident, _, source = value.partition(":")
            pairs[ident.strip()] = source.strip()
        return pairs

    def test_identifiers_use_the_names_factory_expects(self):
        from factory.lords.live_build import (
            DEFAULT_PUBLISHER_CREDENTIAL,
            DEFAULT_TOKEN_CREDENTIAL,
        )

        loaded = self._load_credentials()
        for expected in (DEFAULT_TOKEN_CREDENTIAL, DEFAULT_PUBLISHER_CREDENTIAL):
            assert expected in loaded, (
                f"credential {expected!r} не объявлен: factory будет искать файл "
                f"с этим именем и не найдёт его. Объявлено: {sorted(loaded)}"
            )

    def test_source_paths_point_at_files_that_exist_in_the_registry(self):
        """Путь-источник пишется через дефис — как файлы Secret Hub."""
        for source in self._load_credentials().values():
            assert source.startswith("/etc/site-factory/secrets/lords/"), source
            assert "cdnvideohub-" in source, (
                f"путь {source} не похож на файл реестра Secret Hub"
            )

    def test_the_same_identifiers_are_used_by_the_serving_units(self):
        """Разнобой между юнитами — это тот же отказ, только в другом месте."""
        serving = REPO / "automation" / "host" / "systemd" / "lords-01.service"
        if not serving.is_file():
            return
        ours = set(self._load_credentials())
        theirs = {v.partition(":")[0].strip() for v in unit_value(serving, "LoadCredential")}
        assert ours & theirs, (
            f"обновление и выдача используют разные имена credential'ов: {ours} против {theirs}"
        )


class TestEveryPathTheRefreshWritesToIsWritable:
    """REQ-LORDS-REFRESH-WRITABLE: sandbox не отрезает то, что сценарий пишет.

    Второй запуск отказал на `Read-only file system` при записи отчёта о
    выборке: `ReadWritePaths` перечислял кэш, но не artifacts, а
    `ProtectSystem=strict` делает всё остальное недоступным для записи.
    Выборка при этом проходила целиком — наружу отказ выглядел как «источник
    не ответил», хотя источник ответил и данные были получены.
    """

    def _writable(self) -> set[str]:
        return set(" ".join(unit_value(UNIT, "ReadWritePaths")).split())

    def test_catalogue_cache_is_writable(self):
        """Сравнивается положение кэша внутри репозитория, а не путь чекаута.

        `cache_file` считает путь от корня текущего дерева, и в рабочей копии он
        другой. Проверять надо, что нужная ветка репозитория объявлена
        доступной для записи, а не что совпала строка.
        """
        from factory.lords import live_site
        from factory.paths import PATHS

        relative = live_site.cache_file("lords-01").relative_to(PATHS.root)
        target = Path("/srv/site-factory/repo") / relative
        assert any(str(target).startswith(p) for p in self._writable()), (
            f"кэш каталога {target} недоступен для записи"
        )

    def test_selection_report_directory_is_writable(self):
        """`lords-live` пишет отчёт рядом с кэшем, но в другое дерево."""
        writable = self._writable()
        assert any(p.endswith("/artifacts") for p in writable), (
            "artifacts/ не в списке записи: выборка пройдёт и упадёт на отчёте"
        )

    def test_failure_message_does_not_blame_the_source_blindly(self):
        text = SCRIPT.read_text(encoding="utf-8")
        assert "источник не ответил;" not in text, (
            "сообщение об отказе обвиняет источник во всех случаях, включая "
            "отказ записи — это уводит диагностику в сторону"
        )


class TestPlayerFreezeGate:
    """REQ-LORDS-PLAYER-FREEZE: обновление каталога не имеет права снять плеер.

    Регрессия, ради которой это написано, прошла все прежние проверки. Юнит
    обновления объявлял каталог секретов недоступным — правильно объявлял, ему
    незачем читать оттуда напрямую, — но Publisher ID искался именно там. Он
    перестал находиться, и КАЖДАЯ страница тайтла тихо заменила плеер
    нейтральной фразой «Видео для этого тайтла временно недоступно».

    Снаружи всё выглядело исправным: HTTP 200, карточки на месте, приёмка по
    содержимому пройдена, свежий каталог доехал. Видео при этом не было ни на
    одном из трёх доменов, а сообщение выглядело как обычное отсутствие видео
    у отдельного тайтла.
    """

    def test_refresh_counts_players_before_and_after(self):
        text = SCRIPT.read_text(encoding="utf-8")
        assert "new_players" in text and "old_players" in text, (
            "обновление не считает плееры: потерю видео заметит только посетитель"
        )

    def test_a_collapse_in_coverage_rejects_the_release(self):
        text = SCRIPT.read_text(encoding="utf-8")
        assert "обновление отклонено" in text, (
            "нет отказа при обвале покрытия плеером"
        )
        assert "old_players * 90 / 100" in text, (
            "сравнение без допуска: источник вправе убрать видео у части тайтлов"
        )

    def test_acceptance_looks_at_a_title_page_not_only_the_home_page(self):
        text = SCRIPT.read_text(encoding="utf-8")
        assert "/title/" in text and "video-player" in text, (
            "приёмка смотрит только на главную, а плеер живёт на странице тайтла"
        )


class TestPublisherIdSurvivesTheSandbox:
    """Publisher ID приходит через systemd, а не читается из закрытого каталога."""

    def test_credentials_directory_is_tried_first(self):
        from factory.lords import live_site
        source = __import__("inspect").getsource(live_site.publisher_id_for)
        assert "_publisher_from_credentials" in source, (
            "значение ищется только в реестре: в sandbox каталог секретов закрыт, "
            "и плеер молча исчезнет со всех страниц"
        )

    def test_registry_remains_the_fallback(self):
        from factory.lords import live_site
        source = __import__("inspect").getsource(live_site.publisher_id_for)
        assert "_publisher_from_registry" in source, (
            "убран запасной путь: ручной запуск и тесты останутся без Publisher ID"
        )

    def test_the_unit_still_keeps_the_secrets_directory_closed(self):
        """Правильное решение — передать значение, а не открыть каталог."""
        assert "/etc/site-factory/secrets" in " ".join(unit_value(UNIT, "InaccessiblePaths")), (
            "каталог секретов открыли вместо того, чтобы передать значение"
        )
