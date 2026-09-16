"""Разделение прав службы Templates.

Проверяется не наличие строк в скрипте ради наличия, а то, что определяет
последствия: под какой учётной записью пойдёт служба, какие каталоги ей
доступны на запись и может ли она повысить права. Служба, вернувшаяся под
`claude`, получила бы группу claude — а вместе с ней чтение файла с девятью
служебными токенами и приватным ключом подписи, сокет docker и право
перезапускать юниты витрин.
"""
from __future__ import annotations

import pathlib
import re

import pytest

КОРЕНЬ = pathlib.Path(__file__).resolve().parents[2]
УСТАНОВЩИК = КОРЕНЬ / "automation/host/install-templates-cp.sh"
ЮНИТ = pathlib.Path("/etc/systemd/system/templates-cp-consumer.service")


@pytest.fixture(scope="module")
def скрипт() -> str:
    return УСТАНОВЩИК.read_text(encoding="utf-8")


def _раздел(текст: str, имя: str) -> str:
    куски = re.split(r"^\[(\w+)\]$", текст, flags=re.M)
    for i in range(1, len(куски), 2):
        if куски[i] == имя:
            return куски[i + 1]
    return ""


class TestУчётнаяЗапись:
    def test_служба_не_под_claude(self, скрипт):
        assert "User=claude" not in скрипт, (
            "служба под claude получает группу claude, а с ней — чтение "
            "/etc/site-factory/control-api.env")
        assert "SERVICE_USER=templates-cp" in скрипт

    def test_учётная_запись_создаётся_без_оболочки(self, скрипт):
        assert "--shell /usr/sbin/nologin" in скрипт
        assert "--system" in скрипт

    def test_дополнительных_групп_нет(self, скрипт):
        # Членство в docker, lords или claude вернуло бы путь в production.
        assert 'usermod -G "" "$SERVICE_USER"' in скрипт


class TestПесочница:
    ОБЯЗАТЕЛЬНЫЕ = ("NoNewPrivileges=true", "ProtectSystem=strict",
                    "ProtectHome=true", "CapabilityBoundingSet=",
                    "RestrictNamespaces=true", "RestrictSUIDSGID=true")

    @pytest.mark.parametrize("директива", ОБЯЗАТЕЛЬНЫЕ)
    def test_директива_объявлена(self, скрипт, директива):
        assert директива in скрипт

    def test_на_запись_открыто_только_состояние(self, скрипт):
        совпадения = re.findall(r"^ReadWritePaths=(.+)$", скрипт, flags=re.M)
        assert совпадения, "ReadWritePaths обязан быть задан явно"
        for строка in совпадения:
            пути = строка.split()
            assert пути == ["${STATE}"], (
                f"на запись открыто лишнее: {пути}")


class TestПорядокУстановки:
    def test_служба_останавливается_до_смены_владельца(self, скрипт):
        стоп = скрипт.find("systemctl stop templates-cp-consumer")
        chown = скрипт.find('install -d -o "$SERVICE_USER"')
        assert стоп != -1 and chown != -1
        assert стоп < chown, (
            "смена владельца под работающей службой роняет её на записи")


@pytest.mark.skipif(not ЮНИТ.exists() or not __import__("os").access(ЮНИТ, 4),
                    reason="юнит не установлен или недоступен для чтения")
class TestУстановленныйЮнит:
    """Что фактически записано на хосте, а не только в скрипте."""

    @pytest.fixture(scope="class")
    def юнит(self) -> str:
        return ЮНИТ.read_text(encoding="utf-8")

    def test_пользователь_не_claude(self, юнит):
        сервис = _раздел(юнит, "Service")
        assert "User=claude" not in сервис
        assert "User=templates-cp" in сервис

    def test_песочница_на_месте(self, юнит):
        сервис = _раздел(юнит, "Service")
        for д in ("NoNewPrivileges=true", "ProtectSystem=strict"):
            assert д in сервис

    def test_бюджет_рестартов_в_unit_а_не_service(self, юнит):
        # В [Service] systemd игнорирует эти ключи с предупреждением.
        assert "StartLimitIntervalSec" in _раздел(юнит, "Unit")
        assert "StartLimitIntervalSec" not in _раздел(юнит, "Service")
