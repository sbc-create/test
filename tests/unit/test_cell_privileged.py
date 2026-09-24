"""Граница привилегий исполнителя: что он может и чего не может от root.

Исходный дефект: исполнитель запускал `deploy/activate.sh` из репозитория сайта.
Репозиторий доступен на запись обычной учётной записи, исполнитель работает от
root — право писать в репозиторий превращалось в право выполнить что угодно от
root. Проверки коммита, чистого дерева и CI этого не закрывают: CI описан тем же
репозиторием.

Здесь проверяется, что привилегированная сторона не исполняет ничего пришедшего
из репозитория и не принимает путей, и что распаковка артефакта не может
записать за пределы каталога назначения.
"""
from __future__ import annotations

import io
import json
import shutil
import sys
import tarfile
from pathlib import Path

import pytest

КОРЕНЬ = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(КОРЕНЬ))

from factory.cell import privileged  # noqa: E402


def _архив(путь: Path, члены: list[tarfile.TarInfo],
           содержимое: dict[str, bytes] | None = None) -> Path:
    содержимое = содержимое or {}
    with tarfile.open(путь, "w:gz") as tf:
        for ч in члены:
            данные = содержимое.get(ч.name, b"")
            ч.size = len(данные)
            tf.addfile(ч, io.BytesIO(данные))
    return путь


def test_набор_операций_закрыт():
    """«Выполнить команду» отсутствует как понятие, а не запрещено проверкой."""
    assert set(privileged.ОПЕРАЦИИ) == {
        "prepare", "install_release", "stage_snapshot", "warm_up",
        "switch_route", "promote", "promote_snapshot", "verify", "rollback"}
    описание = privileged.описать_границу()
    assert описание["runs_repository_scripts"] is False
    assert описание["accepts_paths_from_request"] is False


def test_модуль_не_запускает_ничего_из_репозитория():
    """Проверка по исходнику: ни одного вызова сценария сайта."""
    import ast
    дерево = ast.parse((КОРЕНЬ / "factory" / "cell" / "privileged.py")
                       .read_text(encoding="utf-8"))
    # Смотрим на КОД, а не на текст: в документации имя сценария упомянуто
    # намеренно — там объясняется, почему его больше не запускают.
    вызовы = [у for у in ast.walk(дерево)
              if isinstance(у, ast.Call) and isinstance(у.func, ast.Attribute)
              and у.func.attr in {"run", "Popen", "call", "check_output", "system"}]
    аргументы = " ".join(ast.dump(в) for в in вызовы)
    for запрещённое in ("activate.sh", "rollback.sh", "shell=True"):
        assert запрещённое not in аргументы, (
            f"привилегированный код вызывает {запрещённое!r}")


def test_выход_за_каталог_отвергается(tmp_path):
    """Один такой член превращает распаковку в запись куда угодно от root."""
    архив = _архив(tmp_path / "evil.tar.gz",
                   [tarfile.TarInfo("../../etc/passwd")],
                   {"../../etc/passwd": b"root:x:0:0"})
    with tarfile.open(архив) as tf, pytest.raises(privileged.PrivilegedRefused) as ош:
        list(privileged.безопасные_члены(tf, tmp_path / "dest"))
    assert "за пределами" in str(ош.value)


def test_абсолютный_путь_отвергается(tmp_path):
    архив = _архив(tmp_path / "abs.tar.gz", [tarfile.TarInfo("/etc/shadow")])
    with tarfile.open(архив) as tf, pytest.raises(privileged.PrivilegedRefused):
        list(privileged.безопасные_члены(tf, tmp_path / "dest"))


def test_ссылка_наружу_отвергается(tmp_path):
    ссылка = tarfile.TarInfo("config/player.json")
    ссылка.type = tarfile.SYMTYPE
    ссылка.linkname = "/etc/shadow"
    архив = _архив(tmp_path / "link.tar.gz", [ссылка])
    with tarfile.open(архив) as tf, pytest.raises(privileged.PrivilegedRefused) as ош:
        list(privileged.безопасные_члены(tf, tmp_path / "dest"))
    assert "наружу" in str(ош.value)


def test_устройство_в_архиве_отвергается(tmp_path):
    """В артефакте сайта нет и не может быть узлов устройств."""
    узел = tarfile.TarInfo("dev/sda")
    узел.type = tarfile.BLKTYPE
    архив = _архив(tmp_path / "dev.tar.gz", [узел])
    with tarfile.open(архив) as tf, pytest.raises(privileged.PrivilegedRefused) as ош:
        list(privileged.безопасные_члены(tf, tmp_path / "dest"))
    assert "недопустимый тип" in str(ош.value)


def test_обычный_артефакт_проходит(tmp_path):
    архив = _архив(tmp_path / "ok.tar.gz",
                   [tarfile.TarInfo("run.py"), tarfile.TarInfo("src/app.py")],
                   {"run.py": b"print(1)", "src/app.py": b"print(2)"})
    with tarfile.open(архив) as tf:
        имена = [ч.name for ч in privileged.безопасные_члены(tf, tmp_path / "dest")]
    assert имена == ["run.py", "src/app.py"]


def test_несовпадение_digest_отменяет_установку(tmp_path):
    """Ставится тот выпуск, который проверен, или никакой."""
    архив = _архив(tmp_path / "ok.tar.gz", [tarfile.TarInfo("run.py")],
                   {"run.py": b"print(1)"})
    with pytest.raises(privileged.PrivilegedRefused) as ош:
        privileged.install_release("zona-01", архив, "sha256:" + "0" * 64, dry_run=True)
    assert "digest" in str(ош.value)


def test_площадка_выводится_из_реестра_а_не_из_аргумента():
    """Принимать путь аргументом значило бы позволить назвать любой каталог."""
    п = privileged.Площадка.из_реестра("zona-01")
    assert п.root == Path("/srv/zonafilm-space")
    assert п.app == Path("/srv/zonafilm-space/app")
    assert str(п.root).startswith("/srv/")


def test_незарегистрированный_сайт_не_имеет_площадки():
    with pytest.raises(Exception):  # noqa: B017 — любой отказ годится
        privileged.Площадка.из_реестра("net-takogo")


def test_мутация_требует_root(tmp_path):
    """Без root привилегированная операция отказывает, а не делает половину."""
    архив = _архив(tmp_path / "ok.tar.gz", [tarfile.TarInfo("run.py")],
                   {"run.py": b"print(1)"})
    import hashlib
    digest = "sha256:" + hashlib.sha256(архив.read_bytes()).hexdigest()
    if __import__("os").geteuid() == 0:
        pytest.skip("запущено от root — отказ проверить нечем")
    with pytest.raises(privileged.PrivilegedRefused) as ош:
        privileged.install_release("zona-01", архив, digest, dry_run=False)
    assert "root" in str(ош.value)


def _площадка(tmp_path, site_id="zona-01"):
    корень = tmp_path / "srv" / "site"
    (корень / "app" / "config").mkdir(parents=True)
    return privileged.Площадка(site_id=site_id, account="nobody", root=корень,
                               app=корень / "app", data=корень / "data",
                               unit="u.service", previous_unit="", port=9000)


def _выпуск(tmp_path, *, publisher="777"):
    выпуск = tmp_path / "release"
    (выпуск / "config").mkdir(parents=True)
    (выпуск / "config" / "site.json").write_text(
        json.dumps({"site_id": "zona-01", "publisher_id_expected": publisher}),
        encoding="utf-8")
    return выпуск


def test_настройка_места_переносится_из_действующего_выпуска(tmp_path, monkeypatch):
    """`config/player.json` в артефакт не входит намеренно, а без него не стартуют.

    Сборщик исключает его явно: он содержит publisher_id витрины и не живёт в
    репозитории. Первый настоящий выпуск из-за этого развернулся, но кандидат
    не поднялся — «плеер без publisher_id не заработает».
    """
    п = _площадка(tmp_path)
    (п.app / "config" / "player.json").write_text("{}", encoding="utf-8")
    выпуск = _выпуск(tmp_path)
    monkeypatch.setattr(privileged.shutil, "chown", lambda *a, **k: None)
    assert privileged._перенести_локальную_настройку(выпуск, п) == ["config/player.json"]
    перенесённый = выпуск / "config" / "player.json"
    assert перенесённый.is_file()
    assert перенесённый.stat().st_mode & 0o777 == 0o600, "режим настройки не ослабляется"


def test_первый_выпуск_берёт_плеер_у_производителя(tmp_path, monkeypatch):
    """Действующего выпуска ещё нет — переносить неоткуда, но файл существует."""
    п = _площадка(tmp_path)
    произв = tmp_path / "frontend"
    произв.mkdir()
    (произв / "player-zona-01.json").write_text("{}", encoding="utf-8")
    monkeypatch.setattr(privileged, "ПЛЕЕР_ПРОИЗВОДИТЕЛЯ", произв)
    monkeypatch.setattr(privileged.shutil, "chown", lambda *a, **k: None)
    assert privileged._перенести_локальную_настройку(_выпуск(tmp_path), п) == [
        "config/player.json"]


def test_витрина_без_плеера_не_требует_его(tmp_path):
    """У Yummy воспроизведением занимается верхний поток: своего плеера нет.

    Требовать его со всех значило бы заваливать исправную конфигурацию.
    """
    п = _площадка(tmp_path, site_id="yummy-biz")
    assert privileged._перенести_локальную_настройку(
        _выпуск(tmp_path, publisher=""), п) == []


def test_отсутствие_настройки_места_это_отказ(tmp_path, monkeypatch):
    """Молча поставить выпуск, который не стартует, хуже отказа."""
    п = _площадка(tmp_path)
    monkeypatch.setattr(privileged, "ПЛЕЕР_ПРОИЗВОДИТЕЛЯ", tmp_path / "нет")
    with pytest.raises(privileged.PrivilegedRefused, match="витрина не стартует"):
        privileged._перенести_локальную_настройку(_выпуск(tmp_path), п)


def test_настройка_из_артефакта_не_подменяется(tmp_path):
    """Если выпуск принёс файл сам — он и остаётся; перенос ничего не затирает."""
    п = _площадка(tmp_path)
    (п.app / "config" / "player.json").write_text("старое", encoding="utf-8")
    выпуск = _выпуск(tmp_path)
    (выпуск / "config" / "player.json").write_text("своё", encoding="utf-8")
    assert privileged._перенести_локальную_настройку(выпуск, п) == []
    assert (выпуск / "config" / "player.json").read_text(encoding="utf-8") == "своё"


def _площадка_с_прежней(tmp_path, monkeypatch):
    корень = tmp_path / "srv" / "site"
    (корень / "app").mkdir(parents=True)
    monkeypatch.setenv("SITE_UNIT_DIR", str(tmp_path / "units"))
    (tmp_path / "units").mkdir()
    return privileged.Площадка(
        site_id="lords-01", account="lordfilm47-space", root=корень,
        app=корень / "app", data=корень / "data", unit="nova-new.service",
        previous_unit="lords-nova-01.service", port=9110)


def test_прежняя_служба_гасится_и_не_поднимается_сама(tmp_path, monkeypatch):
    """Новый юнит слушает ТОТ ЖЕ порт, и пока прежняя жива — она держит сокет.

    На lords-01 на порту 9110 оказались два процесса: приёмка увидела
    `20260921T134330Z-515fcf0-cardfix` вместо `c323e1822308-lords-01` при
    честном 200 и откатилась.
    """
    п = _площадка_с_прежней(tmp_path, monkeypatch)
    звали = []
    monkeypatch.setattr(privileged, "_systemctl",
                        lambda *a, **k: звали.append(" ".join(a)) or type(
                            "Р", (), {"returncode": 0})())
    шаги = privileged.погасить_прежнюю(п)
    assert "stop lords-nova-01.service" in звали
    assert "disable lords-nova-01.service" in звали
    дропин = tmp_path / "units" / "lords-nova-01.service.d" / "cell-port-owner.conf"
    assert дропин.is_file(), "без drop-in конвейер содержимого вернёт службу на порт"
    assert "RefuseManualStart=yes" in дропин.read_text(encoding="utf-8")
    assert any("RefuseManualStart" in ш for ш in шаги)


def test_откат_поднимает_прежнюю_до_возврата_маршрута(tmp_path, monkeypatch):
    """Обратный порядок вернул бы посетителей на порт, где уже никого нет."""
    п = _площадка_с_прежней(tmp_path, monkeypatch)
    дропин = tmp_path / "units" / "lords-nova-01.service.d" / "cell-port-owner.conf"
    дропин.parent.mkdir(parents=True)
    дропин.write_text("[Unit]\nRefuseManualStart=yes\n", encoding="utf-8")
    звали = []
    monkeypatch.setattr(privileged, "_systemctl",
                        lambda *a, **k: звали.append(" ".join(a)) or type(
                            "Р", (), {"returncode": 0})())
    monkeypatch.setattr(privileged, "готов", lambda *a, **k: {"ready": True})
    итог = privileged.вернуть_прежнюю(п, предел=5)
    assert итог["restored"] is True
    assert not дропин.exists(), "запрет ручного пуска обязан сниматься"
    assert "start lords-nova-01.service" in звали


def test_витрина_без_прежней_службы_не_ломается(tmp_path, monkeypatch):
    """Не у каждой витрины есть прежний юнит — это не повод падать."""
    п = _площадка_с_прежней(tmp_path, monkeypatch)
    п = privileged.Площадка(site_id=п.site_id, account=п.account, root=п.root,
                            app=п.app, data=п.data, unit=п.unit,
                            previous_unit=None, port=п.port)
    assert privileged.погасить_прежнюю(п) == []
    assert privileged.вернуть_прежнюю(п, предел=5)["restored"] is False


def test_недельный_снимок_переносится_но_не_обязателен(tmp_path, monkeypatch):
    """Витрина ищет его РЯДОМ С КАТАЛОГОМ, то есть в своём хранилище.

    Производитель кладёт его в общий каталог, и у выделенной витрины он туда
    не попадал вовсе: блок недельного выбора оставался пустым без единой
    ошибки — страница отвечала 200, раздела просто не было.

    Обязательным его делать нельзя: у части витрин такого файла нет в
    принципе, и требование уронило бы им обновление каталога целиком.
    """
    источник = tmp_path / "front"
    источник.mkdir()
    for имя in ("zona-01-catalog.json", "zona-01-details.json",
                "zona-01-popular-weekly.json"):
        (источник / имя).write_text("{}", encoding="utf-8")
    корень = tmp_path / "srv"
    (корень / "data").mkdir(parents=True)
    п = privileged.Площадка(site_id="zona-01", account="nobody", root=корень,
                            app=корень / "app", data=корень / "data",
                            unit="u.service", previous_unit=None, port=9120)
    monkeypatch.setattr(privileged.Площадка, "из_реестра",
                        staticmethod(lambda *a, **k: п))
    monkeypatch.setattr(privileged, "_нужен_root", lambda: None)
    monkeypatch.setattr(privileged.shutil, "chown", lambda *a, **k: None)

    privileged.stage_snapshot("zona-01", источник, dry_run=False)
    assert (п.data_candidate / "zona-01-popular-weekly.json").is_file()

    # Без дополнения снимок всё равно собирается: обновление каталога важнее
    # одного блока.
    (источник / "zona-01-popular-weekly.json").unlink()
    if п.data_candidate.exists():
        shutil.rmtree(п.data_candidate)
    итог = privileged.stage_snapshot("zona-01", источник, dry_run=False)
    assert итог["operation"] == "stage_snapshot"
    assert not (п.data_candidate / "zona-01-popular-weekly.json").exists()
