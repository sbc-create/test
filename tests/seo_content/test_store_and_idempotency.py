"""Идемпотентность, конкуренция, окна аварии и отсутствие сирот.

Хранилище здесь собственное и эфемерное. Отдельная проверка подтверждает
измерением, что общий Changeset Store не открывается: не «мы его не трогаем»,
а «в базе контура его таблиц нет, а его файл не менялся».
"""
from __future__ import annotations

import hashlib
import os
import pathlib
import sqlite3
import threading

import pytest

from factory.seo_content import identity as ID
from factory.seo_content import store as ST
from factory.seo_content.draft import GateStatus, idempotency_key
from factory.seo_content.pipeline import ContentPipeline, SiteContext
from factory.seo_content.testing import пакет_тайтла

ОБЩЕЕ_ХРАНИЛИЩЕ = "/srv/site-factory/changeset-store/changesets.sqlite3"


def сайт() -> SiteContext:
    return SiteContext("seo-test-0001", "https://seo-test-0001.invalid",
                       own_angle="разбор устройства произведения")


def маршрут() -> ID.Route:
    return ID.Route(url="/title/tihaya-gavan/",
                    resolved_entity_id="title-0001",
                    canonical="/title/tihaya-gavan/")


class TestКлючИдемпотентности:
    def test_состав_ключа(self):
        основа = dict(site_id="s", entity_type="title", entity_id="e",
                      fact_pack_sha256="a" * 64, prompt_version="p",
                      locale="ru")
        базовый = idempotency_key(**основа)
        for поле, другое in (("site_id", "s2"), ("entity_type", "season"),
                             ("entity_id", "e2"),
                             ("fact_pack_sha256", "b" * 64),
                             ("prompt_version", "p2"), ("locale", "en")):
            assert idempotency_key(**{**основа, поле: другое}) != базовый, поле

    def test_ключ_устойчив(self):
        основа = dict(site_id="s", entity_type="title", entity_id="e",
                      fact_pack_sha256="a" * 64, prompt_version="p",
                      locale="ru")
        assert idempotency_key(**основа) == idempotency_key(**основа)


class TestПоследовательнаяИдемпотентность:
    def test_повтор_события_не_создаёт_второго_черновика(self, соединение):
        к = ContentPipeline()
        первый = к.run_pack(пакет_тайтла(), site=сайт(), route=маршрут(),
                            соед=соединение)
        второй = к.run_pack(пакет_тайтла(), site=сайт(), route=маршрут(),
                            соед=соединение)
        assert первый.created and not второй.created
        assert первый.draft_id == второй.draft_id
        assert ST.счётчики(соединение)["drafts"] == 1

    def test_двадцать_повторов_дают_одну_запись(self, соединение):
        к = ContentPipeline()
        ид = {к.run_pack(пакет_тайтла(), site=сайт(), route=маршрут(),
                         соед=соединение).draft_id for _ in range(20)}
        assert len(ид) == 1
        assert ST.счётчики(соединение)["drafts"] == 1

    def test_изменение_фактов_даёт_новую_запись(self, соединение):
        from factory.seo_content.testing import заменить_факт
        к = ContentPipeline()
        а = к.run_pack(пакет_тайтла(), site=сайт(), route=маршрут(),
                       соед=соединение)
        p2 = заменить_факт(пакет_тайтла(), "/year", 2020)
        б = к.run_pack(p2, site=сайт(), route=маршрут(), соед=соединение)
        assert а.draft_id != б.draft_id and б.created
        assert ST.счётчики(соединение)["drafts"] == 2

    def test_перезапуск_и_перечитывание(self, tmp_path):
        путь = tmp_path / "drafts.sqlite3"
        соед = ST.открыть(путь)
        к = ContentPipeline()
        р = к.run_pack(пакет_тайтла(), site=сайт(), route=маршрут(), соед=соед)
        ключ = р.draft.idempotency_key
        соед.close()

        снова = ST.открыть(путь)
        прочитанное = ST.по_ключу(снова, ключ)
        assert прочитанное is not None
        assert прочитанное["fact_pack_sha256"] == пакет_тайтла().sha256
        # И повтор после перезапуска второй записи не создаёт.
        повтор = ContentPipeline().run_pack(
            пакет_тайтла(), site=сайт(), route=маршрут(), соед=снова)
        assert not повтор.created
        снова.close()


class TestКонкурентнаяИдемпотентность:
    def test_шестнадцать_одинаковых_запросов_дают_одного_победителя(
            self, tmp_path):
        путь = tmp_path / "drafts.sqlite3"
        ST.открыть(путь).close()
        результаты: list[tuple[str, bool]] = []
        замок = threading.Lock()
        барьер = threading.Barrier(16)

        def работа():
            соед = ST.открыть(путь)
            к = ContentPipeline()
            барьер.wait()
            р = к.run_pack(пакет_тайтла(), site=сайт(), route=маршрут(),
                           соед=соед)
            with замок:
                результаты.append((р.draft_id, р.created))
            соед.close()

        потоки = [threading.Thread(target=работа) for _ in range(16)]
        for п in потоки:
            п.start()
        for п in потоки:
            п.join()

        assert len(результаты) == 16
        assert len({и for и, _ in результаты}) == 1, "победитель должен быть один"
        assert sum(1 for _, создан in результаты if создан) == 1

        соед = ST.открыть(путь)
        счёт = ST.счётчики(соед)
        assert счёт["drafts"] == 1 and счёт["duplicate_drafts"] == 0
        assert счёт["orphan_records"] == 0
        соед.close()


ОКНА = ("after_fact_pack", "after_draft", "after_notes", "after_event")


class TestОкнаАварии:
    @pytest.mark.parametrize("окно", ОКНА)
    def test_смерть_в_окне_не_оставляет_половины(self, tmp_path, окно):
        путь = tmp_path / f"crash-{окно}.sqlite3"
        соед = ST.открыть(путь)

        def умереть(точка):
            if точка == окно:
                raise RuntimeError(f"процесс умер в {точка}")

        к = ContentPipeline()
        with pytest.raises(RuntimeError):
            к.run_pack(пакет_тайтла(), site=сайт(), route=маршрут(),
                       соед=соед, crash_hook=умереть)
        соед.close()

        # Перезапуск: состояние обязано быть целым.
        снова = ST.открыть(путь)
        счёт = ST.счётчики(снова)
        assert счёт["orphan_records"] == 0, окно
        assert счёт["duplicate_drafts"] == 0
        # Повтор после аварии доводит запись до конца.
        р = ContentPipeline().run_pack(пакет_тайтла(), site=сайт(),
                                       route=маршрут(), соед=снова)
        assert р.created
        итог = ST.счётчики(снова)
        assert итог["drafts"] == 1 and итог["orphan_records"] == 0
        снова.close()


class TestОбщееХранилищеНеТрогаем:
    def test_в_базе_контура_нет_чужих_таблиц(self, соединение):
        таблицы = {r[0] for r in соединение.execute(
            "SELECT name FROM sqlite_master WHERE type='table'")}
        assert not (таблицы & {"changeset", "changeset_outbox",
                               "changeset_target", "seo_content_proposal"})

    @pytest.mark.skipif(not os.path.exists(ОБЩЕЕ_ХРАНИЛИЩЕ),
                        reason="общего хранилища нет в этом окружении")
    def test_общая_база_не_меняется_прогоном(self, tmp_path):
        """Измерение, а не обещание: отпечаток файла до и после."""
        def отпечаток() -> tuple[str, int]:
            данные = pathlib.Path(ОБЩЕЕ_ХРАНИЛИЩЕ).read_bytes()
            return hashlib.sha256(данные).hexdigest(), len(данные)

        до = отпечаток()
        соед = ST.открыть(tmp_path / "drafts.sqlite3")
        ContentPipeline().run_pack(пакет_тайтла(), site=сайт(),
                                   route=маршрут(), соед=соед)
        соед.close()
        assert отпечаток() == до


class TestСостояниеХранилища:
    def test_исходы_разложены_по_счётчикам(self, соединение):
        к = ContentPipeline()
        к.run_pack(пакет_тайтла(), site=сайт(), route=маршрут(),
                   соед=соединение)
        счёт = ST.счётчики(соединение)
        assert счёт["status_passed"] + счёт["status_rejected"] \
            + счёт["status_needs_facts"] + счёт["status_review_required"] \
            + счёт["status_fact_conflict"] + счёт["status_omit"] \
            + счёт["status_noindex_recommended"] == счёт["drafts"]

    def test_заметки_привязаны_к_черновику(self, соединение):
        к = ContentPipeline()
        р = к.run_pack(пакет_тайтла(), site=сайт(), route=маршрут(),
                       соед=соединение)
        строки = соединение.execute(
            "SELECT draft_id FROM seo_editorial_note").fetchall()
        assert all(с["draft_id"] == р.draft_id for с in строки)
        assert ST.счётчики(соединение)["orphan_notes"] == 0
