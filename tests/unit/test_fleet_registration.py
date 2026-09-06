"""REQ-FLEET-REGISTRATION: публичная регистрация посайтово.

Публичный контур уже разделён по витринам на уровне хранилища: личность
посетителя — это пара «витрина + адрес». Но снаружи он один: адрес `/account/*`
и одна витрина на процесс, заданная переменной среды. Для флота этого мало —
регистрация должна быть у каждого сайта своя и включаться настройкой сайта, а
не перезапуском службы с другой переменной.

Три правила.

**Адрес принадлежит сайту.** `/s/<siteId>/account/*`. Один адрес на все витрины
означает, что посетитель регистрируется неизвестно где.

**Признак включения — настройка витрины.** Регистрация, включаемая переменной
среды, включается сразу везде и выключается только перезапуском.

**Учётная запись не переходит между сайтами.** Один и тот же адрес почты на
двух витринах — два разных посетителя, и вход одного не работает на другой.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from factory.paths import PATHS

САЙТ_A = "reg-a"
САЙТ_B = "reg-b"
REPO = Path(__file__).resolve().parents[2]
ПОЧТА = "gость@test.example"
ПАРОЛЬ = "длинный-пароль-посетителя-1"


@pytest.fixture
def sandbox(tmp_path, monkeypatch):
    monkeypatch.setattr(PATHS, "root", tmp_path)
    профили = tmp_path / "config" / "site-profiles"
    профили.mkdir(parents=True)
    for сайт, включена in ((САЙТ_A, True), (САЙТ_B, False)):
        (профили / f"{сайт}.json").write_text(
            json.dumps(
                {
                    "site_id": сайт,
                    "domains": [f"{сайт}.test"],
                    "public_registration_enabled": включена,
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
    for под in ("var/state", "var/audit", "var/locks"):
        (tmp_path / под).mkdir(parents=True, exist_ok=True)
    (tmp_path / "var" / "mail").mkdir(parents=True, exist_ok=True)
    return tmp_path


@pytest.fixture
def сервер(sandbox):
    from factory.site_engine.fleet_accounts import FleetAccounts

    return FleetAccounts(
        sandbox,
        mail_dir=sandbox / "var" / "mail",
        allow_capture_mailer=True,
    )


class TestПризнакВитрины:
    def test_включена_там_где_объявлена(self, сервер):
        assert сервер.enabled(САЙТ_A) is True

    def test_выключена_там_где_не_объявлена(self, сервер):
        assert сервер.enabled(САЙТ_B) is False

    def test_неизвестная_витрина_не_включена(self, сервер):
        assert сервер.enabled("нет-такой") is False

    def test_состояние_называет_причину(self, сервер):
        состояние = сервер.status(САЙТ_B)
        assert состояние["enabled"] is False
        assert состояние["reason"], "выключенная регистрация обязана объяснить себя"


class TestМаршрутыСайта:
    def test_страница_регистрации_открывается(self, сервер):
        ответ = сервер.handle("GET", f"/s/{САЙТ_A}/account/register")
        assert ответ.status == 200
        assert 'name="password"' in ответ.html

    def test_на_выключенной_витрине_регистрации_нет(self, сервер):
        ответ = сервер.handle("GET", f"/s/{САЙТ_B}/account/register")
        assert ответ.status in (403, 404)

    def test_неизвестная_витрина_даёт_404(self, сервер):
        assert сервер.handle("GET", "/s/нет-такой/account/register").status == 404

    def test_регистрация_создаёт_запись_своей_витрины(self, сервер, sandbox):
        ответ = сервер.handle(
            "POST", f"/s/{САЙТ_A}/account/register",
            form={"email": ПОЧТА, "password": ПАРОЛЬ, "consent": "1"},
        )
        assert ответ.status in (200, 302, 303), ответ.status
        from factory.site_engine.accounts import AccountDirectory

        каталог = AccountDirectory(sandbox)
        assert каталог.by_email(САЙТ_A, ПОЧТА) is not None

    def test_запись_не_появляется_на_соседней_витрине(self, сервер, sandbox):
        сервер.handle(
            "POST", f"/s/{САЙТ_A}/account/register",
            form={"email": ПОЧТА, "password": ПАРОЛЬ, "consent": "1"},
        )
        from factory.site_engine.accounts import AccountDirectory

        каталог = AccountDirectory(sandbox)
        assert каталог.by_email(САЙТ_B, ПОЧТА) is None, (
            "посетитель одной витрины появился на другой"
        )


class TestНастройкаВитрины:
    def test_признак_есть_в_разрешённых_настройках(self):
        from factory.site_engine.settings_contract import SAFE_SETTINGS

        assert "public_registration_enabled" in SAFE_SETTINGS

    def test_признак_логический(self):
        from factory.site_engine.settings_contract import SAFE_SETTINGS

        assert SAFE_SETTINGS["public_registration_enabled"]["type"] is bool

    def test_смена_признака_видна_серверу(self, сервер, sandbox):
        """Настройка витрины, а не переменная среды: перезапуск не нужен."""
        путь = sandbox / "config" / "site-profiles" / f"{САЙТ_B}.json"
        профиль = json.loads(путь.read_text(encoding="utf-8"))
        профиль["public_registration_enabled"] = True
        путь.write_text(json.dumps(профиль, ensure_ascii=False), encoding="utf-8")
        assert сервер.enabled(САЙТ_B) is True
