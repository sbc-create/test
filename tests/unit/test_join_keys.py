"""REQ-JOIN-KEYS: связь между адресом страницы и записью каталога.

Три входящих handoff от SEO просят по сути одно и то же с разных сторон.

`023` просит состояние воспроизведения **по записи**, а не сводкой: сводка
отвечает на вопрос «сколько», а решение принимается по вопросу «эта страница —
какая».

`026` уточняет просьбу и делает её дешевле: учётные данные не нужны, нужен
**ключ связи** между адресом страницы витрины и записью каталога. Его нет ни в
очереди, ни в кэше, ни на самой странице.

`025` показывает, к чему приводит отсутствие связи: семь записей, где вид
противоречит собственному описанию, нашлись у SEO и не могли попасть в очередь
разбора ядра, потому что сопоставить их с записями каталога было нечем.

Ключ связи существует и лежит в состоянии отрисовки: `external_id → slug`.
Отдать его — вся работа. Сопоставлять по транслитерации названия нельзя: имена
не уникальны, и именно поэтому у ядра есть реестр адресов.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from factory.paths import PATHS
from factory.site_engine.api.control import ControlApi

SITE = "js-site"
ТОКЕН = "tok"
H = {"Authorization": f"Bearer {ТОКЕН}"}
ENV = {
    "SITE_ENGINE_CONTROL_WRITES": "1",
    "SITE_ENGINE_CONTROL_TOKENS": f"{ТОКЕН}=read,audit:read",
    "SITE_ENGINE_CATALOG_DIR": "var/lords/lords/catalog-cache",
    # Каталог адресов задаётся средой: он принадлежит сборке витрин, а не ядру.
    "SITE_ENGINE_RENDER_STATE_DIR": "var/lords/render-state",
}
REPO = Path(__file__).resolve().parents[2]

ЗАПИСИ = [
    {
        "external_id": "01a00000-0000-7000-8000-000000000001",
        "name": "Обречённые",
        "type": "movie",
        "playback": {"aggregator": "kp", "title_id": "1"},
    },
    {
        # Причина считается по политике, а не берётся из поля кэша: поля с
        # причиной в кэше поставщика нет, обновление перезаписывает записи
        # целиком. Запись без агрегатора и с одним запрещённым идентификатором
        # — ровно тот случай, о котором спрашивает handoff 023.
        "external_id": "01a00000-0000-7000-8000-000000000002",
        "name": "Эпизод 13",
        "type": "movie",
        "playback": None,
        "external_ids": {"imdb": "21328556"},
    },
    {
        "external_id": "01a00000-0000-7000-8000-000000000003",
        "name": "Без адреса",
        "type": "series",
        "playback": {"aggregator": "kp", "title_id": "3"},
    },
]


@pytest.fixture
def sandbox(tmp_path, monkeypatch):
    monkeypatch.setattr(PATHS, "root", tmp_path)
    профили = tmp_path / "config" / "site-profiles"
    профили.mkdir(parents=True)
    образец = json.loads(
        (REPO / "config" / "site-profiles" / "lords-01.json").read_text(encoding="utf-8")
    )
    образец.update({"site_id": SITE, "domains": ["js.test"], "canonical_host": "js.test"})
    (профили / f"{SITE}.json").write_text(json.dumps(образец, ensure_ascii=False), encoding="utf-8")
    кэш = tmp_path / "var" / "lords" / "lords" / "catalog-cache"
    кэш.mkdir(parents=True)
    (кэш / f"{SITE}.json").write_text(
        json.dumps({"fetched_at_ms": 0, "source": "test", "items": ЗАПИСИ}, ensure_ascii=False),
        encoding="utf-8",
    )
    состояние = tmp_path / "var" / "lords" / "render-state"
    состояние.mkdir(parents=True)
    (состояние / f"{SITE}.titles.json").write_text(
        json.dumps(
            {
                ЗАПИСИ[0]["external_id"]: {"slug": "obrechennye", "digest": "d1"},
                ЗАПИСИ[1]["external_id"]: {"slug": "epizod-13", "digest": "d2"},
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    for под in ("queue/inbox", "var/locks", "var/audit", "var/state"):
        (tmp_path / под).mkdir(parents=True, exist_ok=True)
    # Политика воспроизведения — часть поставки: причина показа считается по
    # ней, а не берётся из поля кэша. Без неё ответ честно назовётся
    # PLAYBACK_POLICY_UNREADABLE, но проверять надо рабочий случай.
    (tmp_path / "knowledge").symlink_to(REPO / "knowledge")
    (tmp_path / "config" / "playback-identifiers.yaml").symlink_to(
        REPO / "config" / "playback-identifiers.yaml"
    )
    return tmp_path


@pytest.fixture
def api(sandbox):
    return ControlApi(root=sandbox, env=ENV)


class TestКлючСвязи:
    def test_маршрут_существует(self, api):
        assert api.handle("GET", f"/api/v1/join-keys/{SITE}", headers=H).status == 200

    def test_адрес_страницы_связан_с_записью(self, api):
        тело = api.handle("GET", f"/api/v1/join-keys/{SITE}", headers=H).body
        строки = {с["path"]: с for с in тело["items"]}
        assert "/title/obrechennye/" in строки
        связь = строки["/title/obrechennye/"]
        assert связь["externalId"] == ЗАПИСИ[0]["external_id"]
        assert связь["slug"] == "obrechennye"
        assert связь["internalEntityId"] == f"{SITE}:{ЗАПИСИ[0]['external_id']}"

    def test_состояние_воспроизведения_по_записи(self, api):
        """Просьба handoff 023: код причины по записи, а не сводкой."""
        тело = api.handle("GET", f"/api/v1/join-keys/{SITE}", headers=H).body
        строки = {с["externalId"]: с for с in тело["items"]}
        играет = строки[ЗАПИСИ[0]["external_id"]]
        закрыт = строки[ЗАПИСИ[1]["external_id"]]
        assert играет["playbackReason"] == "PLAYABLE"
        assert закрыт["playbackReason"] == "IDENTIFIER_FORBIDDEN_BY_CONTRACT"
        assert закрыт["identifiers"] == ["imdb"]

    def test_запись_без_адреса_названа_а_не_пропущена(self, api):
        """Запись, которой нет в состоянии отрисовки, обязана быть видна.

        Молча выбросить её значило бы отдать SEO неполную карту и оставить
        расхождение необнаруженным.
        """
        тело = api.handle("GET", f"/api/v1/join-keys/{SITE}", headers=H).body
        без_адреса = [с for с in тело["items"] if not с["slug"]]
        assert [с["externalId"] for с in без_адреса] == [ЗАПИСИ[2]["external_id"]]
        assert тело["withoutPath"] == 1

    def test_вид_и_название_отданы_вместе_со_связью(self, api):
        тело = api.handle("GET", f"/api/v1/join-keys/{SITE}", headers=H).body
        строка = next(с for с in тело["items"] if с["externalId"] == ЗАПИСИ[1]["external_id"])
        assert строка["title"] == "Эпизод 13"
        assert строка["kind"]

    def test_страницы_не_пересекаются(self, api):
        первая = api.handle(
            "GET", f"/api/v1/join-keys/{SITE}", headers=H, body={"limit": 2}
        ).body
        вторая = api.handle(
            "GET", f"/api/v1/join-keys/{SITE}", headers=H, body={"limit": 2, "offset": 2}
        ).body
        assert первая["total"] == 3
        ключи = lambda т: {с["externalId"] for с in т["items"]}  # noqa: E731
        assert not (ключи(первая) & ключи(вторая))

    def test_неизвестная_витрина_отклонена(self, api):
        assert api.handle("GET", "/api/v1/join-keys/нет-такой", headers=H).status in (400, 404)

    def test_нет_состояния_отрисовки_это_названо(self, sandbox):
        """Отсутствие карты адресов — не пустая карта."""
        (sandbox / "var" / "lords" / "render-state" / f"{SITE}.titles.json").unlink()
        тело = ControlApi(root=sandbox, env=ENV).handle(
            "GET", f"/api/v1/join-keys/{SITE}", headers=H
        ).body
        assert тело["pathsAvailable"] is False
        assert тело["reason"]
        assert тело["total"] == 3, "записи каталога видны и без карты адресов"


class TestВидПротиворечитОписанию:
    """Просьба handoff 025: запись, называющая себя эпизодом, но помеченная фильмом."""

    def test_противоречие_попадает_в_спорные(self, api):
        тело = api.handle("GET", f"/api/v1/join-keys/{SITE}", headers=H).body
        строка = next(с for с in тело["items"] if с["externalId"] == ЗАПИСИ[1]["external_id"])
        assert строка["kindConflict"] == "KIND_CONTRADICTS_TITLE"
        assert "13" in строка["kindConflictDetail"]

    def test_обычная_запись_не_объявляется_спорной(self, api):
        тело = api.handle("GET", f"/api/v1/join-keys/{SITE}", headers=H).body
        строка = next(с for с in тело["items"] if с["externalId"] == ЗАПИСИ[0]["external_id"])
        assert not строка.get("kindConflict")


class TestРасписаниеSEO:
    """Входящий handoff 019: четыре задания цикла SEO на расписании."""

    ЕДИНИЦЫ = (
        ("seo-measurement-snapshot", "03:10", 300),
        ("seo-content-audit", "03:30", 1800),
        ("seo-scorecard-weekly", "04:00", 900),
        ("seo-scorecard-monthly", "04:30", 3600),
    )

    @pytest.mark.parametrize("имя,время,таймаут", ЕДИНИЦЫ)
    def test_единица_и_таймер_описаны(self, имя, время, таймаут):
        служба = REPO / "deploy" / "systemd" / f"{имя}.service"
        таймер = REPO / "deploy" / "systemd" / f"{имя}.timer"
        assert служба.is_file(), f"нет описания службы {имя}"
        assert таймер.is_file(), f"нет описания таймера {имя}"
        текст = служба.read_text(encoding="utf-8")
        assert f"TimeoutStartSec={таймаут}" in текст, "таймаут обязан совпадать с просьбой"
        assert время in таймер.read_text(encoding="utf-8"), "время обязано совпадать с просьбой"

    @pytest.mark.parametrize("имя,время,таймаут", ЕДИНИЦЫ)
    def test_один_повтор_через_пятнадцать_минут(self, имя, время, таймаут):
        текст = (REPO / "deploy" / "systemd" / f"{имя}.service").read_text(encoding="utf-8")
        assert "Restart=on-failure" in текст
        assert "RestartSec=900" in текст, "повтор через 15 минут"
        assert "StartLimitBurst=2" in текст, "один повтор, а не бесконечный"

    def test_ничего_не_публикуется_и_не_меняет_production(self):
        for имя, _, _ in self.ЕДИНИЦЫ:
            текст = (REPO / "deploy" / "systemd" / f"{имя}.service").read_text(encoding="utf-8")
            assert "ProtectSystem=strict" in текст
            assert "NoNewPrivileges=yes" in текст

    def test_установка_описана_и_не_выполняется_молча(self):
        руководство = REPO / "docs" / "runbooks" / "seo-schedule.md"
        assert руководство.is_file()
        текст = руководство.read_text(encoding="utf-8")
        assert "systemctl" in текст
        assert "владельц" in текст.lower(), "установка юнитов — действие владельца"
