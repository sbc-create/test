"""Юниты обработчика обновлений ставятся из выпуска и только проверенными.

Держит найденную причину 2026-10-05: юнит обработчика animedia.icu был
поставлен руками 27.09 и исполнял `/srv/animedia-icu/app`, пока витрина
жила на `current`. Шаги карты сайта и допуска не исполнялись, журнал говорил
«проблем: 0». Исполнитель теперь ставит юнит из выпуска при каждом promote.
"""
from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from factory.cell import updater_units as uu

CURRENT = Path("/srv/animedia-icu/current")
DATA = Path("/srv/animedia-icu/data")
CRED = "cdnvideohub_api_token:/etc/site-factory/secrets/lords/lords-01/cdnvideohub-api-token"

#: Юнит из выпуска 2bb2091 (deploy/animedia-icu-update.service), без комментариев.
ВЫПУСК = """[Unit]
Description=animedia.icu: доставка каталога
After=network-online.target

[Service]
Type=oneshot
User=animedia-icu
Group=animedia-icu
WorkingDirectory=/srv/animedia-icu/current
ExecStart=/usr/bin/python3 /srv/animedia-icu/current/automation/animedia-data-update.py \\
    --site animedia-01 --domain animedia.icu \\
    --data-dir /srv/animedia-icu/data \\
    --source-dir /srv/lords/.frontend
LoadCredential=cdnvideohub_api_token:/etc/site-factory/secrets/lords/lords-01/cdnvideohub-api-token
SuccessExitStatus=0 1 75
TimeoutStartSec=600
NoNewPrivileges=true
PrivateTmp=true
ProtectSystem=strict
ProtectHome=true
ReadWritePaths=/srv/animedia-icu/data
ProtectKernelTunables=true
ProtectControlGroups=true
RestrictSUIDSGID=true

[Install]
WantedBy=multi-user.target
"""
#: Установленный на хосте 27.09 — исполняет `app`.
УСТАНОВЛЕННЫЙ_APP = ВЫПУСК.replace("/srv/animedia-icu/current", "/srv/animedia-icu/app")
ТАЙМЕР = """[Unit]
Description=animedia.icu: регулярное обновление
[Timer]
OnBootSec=3min
OnUnitActiveSec=10min
Persistent=true
[Install]
WantedBy=timers.target
"""
ОБЪЯВЛЕНИЕ = uu.Объявление("animedia-icu-update.service", "animedia-icu-update.timer",
                           frozenset({CRED}))


def проверить(текст: str) -> uu.Юнит:
    return uu.проверить_службу(текст, account="animedia-icu", current=CURRENT,
                               data=DATA, учётные={CRED})


def test_юнит_выпуска_принимается():
    юнит = проверить(ВЫПУСК)
    assert юнит.одно("Service", "WorkingDirectory") == str(CURRENT)
    assert "--source-dir /srv/lords/.frontend" in юнит.одно("Service", "ExecStart")


def test_юнит_на_app_отклоняется():
    with pytest.raises(uu.UpdaterUnitRefused, match="вне /srv/animedia-icu/current"):
        проверить(УСТАНОВЛЕННЫЙ_APP)


@pytest.mark.parametrize("правка, причина", [
    (("User=animedia-icu", "User=root"), "User обязан"),
    (("ExecStart=/usr/bin/python3", "ExecStart=+/usr/bin/python3"), "префиксы"),
    (("ExecStart=/usr/bin/python3", "ExecStart=/bin/sh"), "интерпретатор"),
    (("ReadWritePaths=/srv/animedia-icu/data", "ReadWritePaths=/etc"), "ReadWritePaths"),
    (("RestrictSUIDSGID=true", "RestrictSUIDSGID=true\nExecStartPre=/bin/true"), "ExecStartPre"),
    (("RestrictSUIDSGID=true", "RestrictSUIDSGID=true\nAmbientCapabilities=CAP_SYS_ADMIN"),
     "AmbientCapabilities"),
    (("NoNewPrivileges=true", "NoNewPrivileges=false"), "NoNewPrivileges"),
    (("cdnvideohub-api-token", "other-secret"), "LoadCredential"),
])
def test_опасные_правки_отклоняются(правка, причина):
    with pytest.raises(uu.UpdaterUnitRefused, match=причина):
        проверить(ВЫПУСК.replace(*правка))


def test_таймер_на_чужую_службу_отклоняется():
    with pytest.raises(uu.UpdaterUnitRefused, match="запускает"):
        uu.проверить_таймер(ТАЙМЕР + "[Timer]\nUnit=other.service\n",
                            служба="animedia-icu-update.service")


class Systemctl:
    def __init__(self):
        self.вызовы: list[tuple[str, ...]] = []

    def __call__(self, *args, проверять=True):
        self.вызовы.append(args)
        return subprocess.CompletedProcess(args, 0, "", "")


def площадка(tmp_path: Path, *, служба_выпуска: str = ВЫПУСК,
             установлено: str | None = None):
    выпуск = tmp_path / "release"
    (выпуск / "deploy").mkdir(parents=True)
    (выпуск / "deploy" / ОБЪЯВЛЕНИЕ.service).write_text(служба_выпуска, encoding="utf-8")
    (выпуск / "deploy" / ОБЪЯВЛЕНИЕ.timer).write_text(ТАЙМЕР, encoding="utf-8")
    каталог = tmp_path / "units"
    каталог.mkdir()
    if установлено is not None:
        (каталог / ОБЪЯВЛЕНИЕ.service).write_text(установлено, encoding="utf-8")
    return выпуск, каталог


def установить(выпуск, каталог, sc):
    return uu.установить(ОБЪЯВЛЕНИЕ, выпуск=выпуск, account="animedia-icu",
                         current=CURRENT, data=DATA, каталог=каталог,
                         systemctl=sc, метка="T")


def test_первичная_установка(tmp_path):
    выпуск, каталог = площадка(tmp_path)
    sc = Systemctl()
    итог = установить(выпуск, каталог, sc)
    assert итог["ok"] and итог["after"]["согласован"]
    assert (каталог / ОБЪЯВЛЕНИЕ.service).read_text() == ВЫПУСК
    assert ("enable", "--now", ОБЪЯВЛЕНИЕ.timer) in sc.вызовы


def test_обновление_заменяет_app_и_сохраняет_копию(tmp_path):
    выпуск, каталог = площадка(tmp_path, установлено=УСТАНОВЛЕННЫЙ_APP)
    до = uu.сверить(ОБЪЯВЛЕНИЕ, выпуск=выпуск, account="animedia-icu", current=CURRENT,
                    data=DATA, каталог=каталог)
    assert до["исполняет_current"] is False      # ровно состояние animedia.icu
    итог = установить(выпуск, каталог, Systemctl())
    assert итог["after"]["исполняет_current"] is True
    assert (каталог / f"{ОБЪЯВЛЕНИЕ.service}.bak.T").read_text() == УСТАНОВЛЕННЫЙ_APP
    assert "daemon-reload" in итог["steps"]


def test_повтор_ничего_не_меняет(tmp_path):
    выпуск, каталог = площадка(tmp_path)
    установить(выпуск, каталог, Systemctl())
    итог = установить(выпуск, каталог, Systemctl())
    assert итог["plan"]["действие"] == "без изменений"
    assert not list(каталог.glob("*.bak.*"))


def test_откат_на_выпуск_с_юнитом_app_оставляет_установленный(tmp_path):
    # Выпуски до 01.10 несли юнит на `app`. Возврат к такому выпуску не должен
    # ломать установленный юнит, который уже исполняет `current`.
    выпуск, каталог = площадка(tmp_path, служба_выпуска=УСТАНОВЛЕННЫЙ_APP,
                               установлено=ВЫПУСК)
    итог = установить(выпуск, каталог, Systemctl())
    assert итог["plan"]["действие"] == "оставить установленный"
    assert (каталог / ОБЪЯВЛЕНИЕ.service).read_text() == ВЫПУСК
    assert итог["ok"]


def test_оба_неверны_отказ(tmp_path):
    выпуск, каталог = площадка(tmp_path, служба_выпуска=УСТАНОВЛЕННЫЙ_APP,
                               установлено=УСТАНОВЛЕННЫЙ_APP)
    with pytest.raises(uu.UpdaterUnitRefused, match="не исполняют"):
        установить(выпуск, каталог, Systemctl())
    assert (каталог / ОБЪЯВЛЕНИЕ.service).read_text() == УСТАНОВЛЕННЫЙ_APP


def test_объявление_реестра_обеих_animedia():
    from factory.cell import registry
    for site, account in (("animedia-01", "animedia-icu"), ("animedia-02", "animedia-space")):
        объявл = uu.Объявление.из_блока(registry.resolve(site).runtime.get("updater"))
        assert объявл.service == f"{account}-update.service"
        assert объявл.timer == f"{account}-update.timer"


def test_реестр_с_обработчиком_валиден_по_схеме():
    # У `runtime` в схеме additionalProperties: false. Поле, не объявленное в
    # схеме, делает реестр невалидным целиком — так и было в первой версии
    # этой правки (нашла соседняя сессия до установки).
    import json

    import jsonschema
    корень = Path(__file__).resolve().parents[2]
    реестр = json.loads((корень / "config" / "site-cells.json").read_text(encoding="utf-8"))
    схема = json.loads((корень / "schemas" / "site-cells.schema.json").read_text(encoding="utf-8"))
    jsonschema.validate(реестр, схема)
    assert any((c.get("runtime") or {}).get("updater") for c in реестр["cells"])
