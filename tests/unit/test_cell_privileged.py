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


def test_появившееся_дополнение_не_считается_неизменным(tmp_path):
    """Повтор ошибки, уже исправленной в засеве: «не изменилось» про часть.

    Там «наполнено» считалось по одному каталогу — витрина выкладывалась без
    подробностей. Здесь тот же просчёт дал другой симптом: доставка отвечала
    `unchanged` и не привозила недельный снимок, появившийся у производителя
    впервые, потому что каталог не менялся. Наблюдалось на zona-01.
    """
    источник = tmp_path / "front"
    цель = tmp_path / "data"
    источник.mkdir()
    цель.mkdir()
    for имя in ("zona-01-catalog.json", "zona-01-details.json"):
        (источник / имя).write_text("{}", encoding="utf-8")
        (цель / имя).write_text("{}", encoding="utf-8")
    # Пара совпадает — до появления дополнения это и есть «не изменилось».
    assert privileged.снимок_совпадает(источник, цель, "zona-01") is True

    (источник / "zona-01-popular-weekly.json").write_text("[]", encoding="utf-8")
    assert privileged.снимок_совпадает(источник, цель, "zona-01") is False, (
        "появившееся дополнение обязано считаться изменением")

    (цель / "zona-01-popular-weekly.json").write_text("[]", encoding="utf-8")
    assert privileged.снимок_совпадает(источник, цель, "zona-01") is True


def test_происхождение_выпуска_лежит_рядом_с_кодом(tmp_path):
    """Каталог выпуска обязан сам отвечать, откуда он.

    `releases/<commit12>` называет двенадцать знаков коммита и больше ничего:
    ни digest, ни времени установки, ни метки, которую витрина объявит. Кто
    смотрит на сайт, а не в /var/lib/site-cells, проверить происхождение
    исполняемого выпуска не мог.

    Отдельная причина — затворы активации. Подтверждать выпуск заголовком
    `X-Site-Factory-Build-Id` нельзя там, где build_id берётся из манифеста
    ЗАКРЕПЛЁННОГО шаблона: это значение одинаково у всех выпусков витрины и
    даже у соседей семейства, то есть не различает то, что должно различать.
    Поэтому `live_build_id` читается из манифеста ЭТОГО дерева, а не собирается
    по правилу: правило может разойтись со сборщиком, манифест — нет.
    """
    import json

    выпуск = tmp_path / "выпуск"
    (выпуск / "config").mkdir(parents=True)
    (выпуск / "config" / "template-manifest.json").write_text(
        json.dumps({"build_id": "aaaaaaaaaaaa-zona-01"}), encoding="utf-8")
    (выпуск / "config" / "site.json").write_text(
        json.dumps({"entrypoint": "lords-frontend.py"}), encoding="utf-8")

    итог = privileged._записать_происхождение(
        выпуск, site_id="zona-01", commit="a" * 40,
        digest="sha256:" + "b" * 64, account="nobody")

    assert итог["file"] == privileged.ФАЙЛ_ПРОИСХОЖДЕНИЯ
    запись = json.loads((выпуск / итог["file"]).read_text(encoding="utf-8"))
    assert запись["commit"] == "a" * 40
    assert запись["digest"] == "sha256:" + "b" * 64
    assert запись["live_build_id"] == "aaaaaaaaaaaa-zona-01", (
        "метка выпуска обязана приходить из манифеста этого дерева")
    assert запись["entrypoint"] == "lords-frontend.py"
    assert запись["installed_by"] == "cell-executor"


def test_свой_манифест_не_затирает_чужой(tmp_path):
    """Артефакт мог принести файл с тем же именем — его данные не наши."""
    import json

    выпуск = tmp_path / "выпуск"
    выпуск.mkdir()
    чужой = {"это": "из артефакта"}
    (выпуск / privileged.ФАЙЛ_ПРОИСХОЖДЕНИЯ).write_text(
        json.dumps(чужой), encoding="utf-8")

    итог = privileged._записать_происхождение(
        выпуск, site_id="zona-01", commit="c" * 40,
        digest="sha256:" + "d" * 64, account="nobody")

    assert итог["file"] == privileged.ФАЙЛ_ПРОИСХОЖДЕНИЯ_ЗАПАСНОЙ
    assert json.loads((выпуск / privileged.ФАЙЛ_ПРОИСХОЖДЕНИЯ).read_text(
        encoding="utf-8")) == чужой, "файл из артефакта затёрт"
    своё = json.loads((выпуск / итог["file"]).read_text(encoding="utf-8"))
    assert своё["commit"] == "c" * 40


def test_происхождение_без_манифеста_шаблона_не_падает(tmp_path):
    """Не у каждого семейства есть манифест шаблона: Yummy обходится без него.

    Отказ здесь означал бы, что выпуск не установится вовсе из-за отсутствия
    необязательного файла.
    """
    import json

    выпуск = tmp_path / "выпуск"
    выпуск.mkdir()
    итог = privileged._записать_происхождение(
        выпуск, site_id="yummy-biz", commit="e" * 40,
        digest="sha256:" + "f" * 64, account="nobody")
    запись = json.loads((выпуск / итог["file"]).read_text(encoding="utf-8"))
    assert запись["live_build_id"] == ""
    assert запись["entrypoint"] == ""


def _площадка_для_контракта(tmp_path, account="nobody"):
    корень = tmp_path / "srv"
    (корень / "data").mkdir(parents=True)
    (корень / "app").mkdir(parents=True)
    return privileged.Площадка(
        site_id="yummy-site", account=account, root=корень,
        app=корень / "app", data=корень / "data",
        unit="u.service", previous_unit=None, port=9132)


def test_контракт_данных_объявляется_сайтом(tmp_path):
    """Набор файлов принадлежит сайту, а не общей таблице фабрики.

    У семейства Yummy нет файла подробностей в природе. Общий набор
    (`{site}-catalog.json` + `{site}-details.json`) отказал бы выпуску на
    отсутствии файла, которого никто не производит, — то есть требование
    полноты снимка сработало бы против витрины, у которой снимок полон.
    """
    import json

    репо = tmp_path / "repo" / "config"
    репо.mkdir(parents=True)
    (репо / "site.json").write_text(json.dumps({
        "site_id": "yummy-site",
        "data_contract": {"delivered": ["{site}-catalog.json"],
                          "user_writable": ["site-data", "yummy-readmodel.sqlite3"]},
    }), encoding="utf-8")

    к = privileged.контракт_данных("yummy-site", репозиторий=репо.parent)
    assert к["delivered"] == ("{site}-catalog.json",)
    assert "yummy-readmodel.sqlite3" in к["user_writable"]

    # Без объявления действует прежний общий набор. Пример берётся заведомо
    # несуществующий: у настоящих витрин объявление уже появилось, и проверять
    # умолчание на них значило бы проверять их конфигурацию, а не умолчание.
    по_умолчанию = privileged.контракт_данных("нет-такой-витрины")
    assert по_умолчанию["delivered"] == privileged.СНИМОК
    assert по_умолчанию["user_writable"] == (privileged.ПОЛЬЗОВАТЕЛЬСКИЕ,)


def test_установленный_выпуск_важнее_репозитория(tmp_path):
    """Доставка следует контракту РАБОТАЮЩЕГО кода, а не будущего.

    Иначе правка контракта в репозитории меняла бы доставку до того, как этот
    код выложен, — то есть данные приезжали бы по описанию, которого на сайте
    ещё нет.
    """
    import json

    п = _площадка_для_контракта(tmp_path)
    выпуск = tmp_path / "srv" / "releases" / "aaaaaaaaaaaa"
    (выпуск / "config").mkdir(parents=True)
    (выпуск / "config" / "site.json").write_text(json.dumps({
        "data_contract": {"delivered": ["живой-{site}.json"], "user_writable": ["site-data"]},
    }), encoding="utf-8")
    п.current.symlink_to(выпуск)

    репо = tmp_path / "repo" / "config"
    репо.mkdir(parents=True)
    (репо / "site.json").write_text(json.dumps({
        "data_contract": {"delivered": ["будущий-{site}.json"], "user_writable": ["site-data"]},
    }), encoding="utf-8")

    к = privileged.контракт_данных("yummy-site", площадка=п, репозиторий=репо.parent)
    assert к["delivered"] == ("живой-{site}.json",), к


def test_пользовательское_засевается_один_раз(tmp_path):
    """Повторный засев затёр бы принятые оценки.

    База оценок Yummy — не снимок: слой витрины в неё пишет. Значит второй
    засев означает потерю того, что посетители успели поставить.
    """
    import json
    import sqlite3

    п = _площадка_для_контракта(tmp_path)
    (п.app / "config").mkdir(parents=True, exist_ok=True)
    (п.app / "config" / "site.json").write_text(json.dumps({
        "data_contract": {"delivered": ["{site}-catalog.json"],
                          "user_writable": ["yummy-readmodel.sqlite3"]},
    }), encoding="utf-8")

    источник = tmp_path / "front"
    источник.mkdir()
    бд = источник / "yummy-readmodel.sqlite3"
    соед = sqlite3.connect(str(бд))
    соед.execute("create table user_rating(user_id text, value int)")
    соед.execute("insert into user_rating values ('u1', 7)")
    соед.commit()
    соед.close()

    итог = privileged.засеять_пользовательское(
        "yummy-site", источник, dry_run=True, площадка=п)
    assert итог["entries"][0]["would_seed"].endswith("yummy-readmodel.sqlite3")
    assert not (п.data / "yummy-readmodel.sqlite3").exists(), "сухой прогон записал файл"

    # Настоящий засев требует root; поведение «уже на месте» проверяется без него.
    (п.data / "yummy-readmodel.sqlite3").write_bytes("уже принятые оценки".encode())
    повтор = privileged.засеять_пользовательское(
        "yummy-site", источник, dry_run=False, площадка=п)
    assert повтор["entries"][0]["skipped"] == "уже на месте"
    assert (п.data / "yummy-readmodel.sqlite3").read_bytes() == "уже принятые оценки".encode(), (
        "повторный засев затёр пользовательские данные")


def test_база_оценок_подключается_ссылкой_а_не_копией(tmp_path, monkeypatch):
    """Копия означала бы потерю оценок, принятых во время прогрева.

    `site-data` не копируется именно по этой причине; база оценок Yummy — тот
    же случай, только это файл, а не каталог. Проверка сторожит, что различие
    «файл или каталог» на решение не влияет.
    """
    import json

    п = _площадка_для_контракта(tmp_path)
    (п.app / "config").mkdir(parents=True, exist_ok=True)
    (п.app / "config" / "site.json").write_text(json.dumps({
        "data_contract": {"delivered": ["{site}-catalog.json"],
                          "user_writable": ["site-data", "yummy-readmodel.sqlite3"]},
    }), encoding="utf-8")
    (п.data / "yummy-site-catalog.json").write_text('{"items": []}', encoding="utf-8")
    (п.data / "yummy-readmodel.sqlite3").write_bytes("оценки".encode())
    (п.data / "site-data").mkdir()

    источник = tmp_path / "front"
    источник.mkdir()
    (источник / "yummy-site-catalog.json").write_text('{"items": [1]}', encoding="utf-8")

    monkeypatch.setattr(privileged.Площадка, "из_реестра",
                        staticmethod(lambda *a, **k: п))
    monkeypatch.setattr(privileged, "_нужен_root", lambda: None)
    monkeypatch.setattr(privileged.shutil, "chown", lambda *a, **k: None)

    итог = privileged.stage_snapshot("yummy-site", источник, dry_run=False)
    assert итог["unchanged"] is False, итог
    кандидат = п.data_candidate
    assert (кандидат / "yummy-readmodel.sqlite3").is_symlink(), (
        "база оценок скопирована, а не подключена ссылкой")
    assert (кандидат / "site-data").is_symlink()
    assert not (кандидат / "yummy-site-catalog.json").is_symlink(), (
        "снимок обязан быть копией: кандидат не должен править живые данные")


def test_контракт_находит_репозиторий_сам_на_первом_выпуске(tmp_path, monkeypatch):
    """У первого выпуска нет установленного релиза — контракт брать неоткуда.

    Поймано первым же настоящим переносом Yummy, а не рассуждением. Исполнитель
    отказал: «yummy-biz: в источнике нет файлов снимка
    ['yummy-biz-details.json']; половина снимка хуже прежнего целого» — то есть
    взял умолчание фабрики вместо контракта сайта.

    Причина: `stage_snapshot` разрешает контракт заново и путь репозитория до
    него не доезжал. `_засеять_хранилище` передавал его, а вызванный из засева
    `stage_snapshot` — нет, и на первом выпуске (когда `current` и `app` пусты)
    оставалось только умолчание. Поэтому контракт ищет репозиторий сам, а
    параметр остаётся для проверок и вызова с чужим деревом.
    """
    import json

    репо = tmp_path / "repo"
    (репо / "config").mkdir(parents=True)
    (репо / "config" / "site.json").write_text(json.dumps({
        "site_id": "yummy-biz",
        "data_contract": {"delivered": ["{site}-catalog.json"],
                          "user_writable": ["site-data", "yummy-readmodel.sqlite3"]},
    }), encoding="utf-8")

    class ФиктивнаяЯчейка:
        repo_path = репо

    from factory.cell import registry as рег
    monkeypatch.setattr(рег, "resolve", lambda site_id: ФиктивнаяЯчейка())

    # Площадка первого выпуска: ни current, ни app ещё не заполнены.
    корень = tmp_path / "srv"
    (корень / "data").mkdir(parents=True)
    (корень / "app").mkdir(parents=True)
    п = privileged.Площадка(site_id="yummy-biz", account="nobody", root=корень,
                            app=корень / "app", data=корень / "data",
                            unit="u.service", previous_unit=None, port=9130)

    к = privileged.контракт_данных("yummy-biz", площадка=п)
    assert к["delivered"] == ("{site}-catalog.json",), (
        "на первом выпуске взято умолчание фабрики вместо контракта сайта: "
        f"{к}")
    assert "yummy-readmodel.sqlite3" in к["user_writable"]
    assert str(репо) in к["source"]


def test_приёмка_читает_build_id_у_семейства_без_мета_тега(tmp_path, monkeypatch):
    """Заголовок отдают все семейства, мета-тег — только пишущие разметку.

    Поймано на первом переносе yummy-biz: кандидат поднялся за 3 с, `/` отдал
    200 (274 973 байта), `/healthz` 200 — и приёмка всё равно откатила выпуск,
    потому что `build_id` оказался `null`. Причина не в витрине: Yummy ставит
    перед собой прокси над сторонним приложением, разметку не пишет и мета-тега
    не имеет. Проверка умела читать только мета-тег, то есть предполагала
    разметку одного семейства.

    Ослаблять сверку нельзя: именно она отличает «ответ 200» от «работает
    нужный выпуск». Поэтому источник расширен, а не требование снято.
    """
    import threading
    from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

    def поднять(обработчик):
        сервер = ThreadingHTTPServer(("127.0.0.1", 0), обработчик)
        threading.Thread(target=сервер.serve_forever, daemon=True).start()
        return сервер

    class ТолькоЗаголовок(BaseHTTPRequestHandler):
        def do_GET(self):  # noqa: N802
            тело = "<html><body>прокси без мета-тега</body></html>".encode()
            self.send_response(200)
            self.send_header("X-Site-Factory-Build-Id", "9d25994c1762-yummy-biz")
            self.send_header("Content-Length", str(len(тело)))
            self.end_headers()
            self.wfile.write(тело)

        def log_message(self, *a):
            pass

    class ТолькоМетаТег(BaseHTTPRequestHandler):
        def do_GET(self):  # noqa: N802
            тело = b'<meta name="site-factory-build-id" content="abc123-zona-01">'
            self.send_response(200)
            self.send_header("Content-Length", str(len(тело)))
            self.end_headers()
            self.wfile.write(тело)

        def log_message(self, *a):
            pass

    class ОбаИсточника(BaseHTTPRequestHandler):
        """Витрина, у которой заголовок называет ШАБЛОН, а мета-тег — выпуск.

        Так устроена zona-02: `X-Site-Factory-Build-Id` берётся из манифеста
        закреплённого шаблона и одинаков у всех её выпусков, а метку самого
        выпуска процесс пишет в разметку. Кандидат из нужного коммита, отвечавший
        200 на обоих маршрутах, был откачен именно потому, что приёмка
        спрашивала сначала заголовок.
        """

        def do_GET(self):  # noqa: N802
            тело = b'<meta name="site-factory-release-id" content="060149731561-zona-02">'
            self.send_response(200)
            self.send_header("X-Site-Factory-Build-Id", "zona-02-0fb857b26f85")
            self.send_header("Content-Length", str(len(тело)))
            self.end_headers()
            self.wfile.write(тело)

        def log_message(self, *a):
            pass

    for обработчик, ожидаемый, источник in (
            (ТолькоЗаголовок, "9d25994c1762-yummy-biz",
             "заголовок (ревизия шаблона, не выпуска)"),
            (ТолькоМетаТег, "abc123-zona-01", "мета-тег"),
            (ОбаИсточника, "060149731561-zona-02", "мета-тег")):
        сервер = поднять(обработчик)
        порт = сервер.server_address[1]
        п = privileged.Площадка(site_id="проверка", account="nobody",
                                root=tmp_path, app=tmp_path / "app",
                                data=tmp_path / "data", unit="u.service",
                                previous_unit=None, port=порт)
        monkeypatch.setattr(privileged.Площадка, "из_реестра",
                            staticmethod(lambda *a, площадка=п, **k: площадка))
        try:
            итог = privileged.verify("проверка", ожидаемый_build=ожидаемый,
                                     маршруты=("/",))
        finally:
            сервер.shutdown()
        assert итог["build_id"] == ожидаемый, итог
        assert итог["build_id_source"] == источник, итог
        assert итог["build_matches"] is True, итог
        assert итог["ok"] is True, итог


def test_повышение_включает_службу():
    """Автозапуск — часть выпуска, а не обязанность владельца.

    Без `enable` сайт работает до первой перезагрузки, а потом не поднимается
    вовсе либо возвращается прежняя служба из общего дерева. Измерено 27.09:
    ячейки lordfilm47.space и 1lordserials1.online обслуживали домены, не будучи
    включёнными, и снаружи это выглядело завершённым выпуском.
    """
    from pathlib import Path as _Path

    from factory.cell import privileged as pr

    # Полный promote требует настоящей площадки и root. Здесь проверяется
    # контракт порядка: enable вызывается и вызывается ДО restart. Подделка
    # systemctl этого не добавила бы — она проверяла бы саму подделку.
    текст = _Path(pr.__file__).read_text(encoding="utf-8")
    место_enable = текст.find('_systemctl("enable", п.unit')
    место_restart = текст.find('_systemctl("restart", п.unit)')
    assert место_enable != -1, "promote не включает службу"
    assert место_restart != -1
    assert место_enable < место_restart, "enable обязан идти до restart"


def test_плеер_нужен_и_по_ссылке_на_секрет(tmp_path):
    """Ссылка на секрет — такой же признак «плеер нужен», как ожидаемое значение.

    Пока условие смотрело только на `publisher_id_expected`, витрина с
    `publisher_id_ref` не получала файла плеера вовсе: исполнитель считал его
    ненужным, а рантайм витрины отказывался стартовать словами «нет
    config/player.json». Кандидат lords-05 так и не поднялся, и причина
    выглядела как поломка выпуска, а не как несогласованность двух условий.
    """
    from factory.cell import privileged

    выпуск = tmp_path / "release"
    (выпуск / "config").mkdir(parents=True)
    конфиг = выпуск / "config" / "site.json"

    конфиг.write_text(json.dumps({"publisher_id_expected": None,
                                  "publisher_id_ref": "secret://cdnvideohub/lords/publisher-id"},
                                 ensure_ascii=False), encoding="utf-8")
    assert privileged._плеер_обязателен(выпуск) is True

    конфиг.write_text(json.dumps({"publisher_id_expected": "10261"}, ensure_ascii=False),
                      encoding="utf-8")
    assert privileged._плеер_обязателен(выпуск) is True

    # У витрин Yummy воспроизведением занимается верхний поток: ни того, ни
    # другого поля нет, и требовать плеер нельзя.
    конфиг.write_text(json.dumps({"domain": "yummyani7.site"}, ensure_ascii=False),
                      encoding="utf-8")
    assert privileged._плеер_обязателен(выпуск) is False


def test_приёмка_не_сдаётся_после_первого_таймаута(monkeypatch):
    """Холодный старт крупной витрины дольше одного предела — это не отказ.

    Повод: выпуск lords-05 объявлен провалившимся, потому что `verify` получил
    TimeoutError на обоих маршрутах сразу после перезапуска. Сработал откат — и
    его собственная проверка, дошедшая до сайта на пять минут позже, увидела
    HTTP 200. Откат по нетерпению выключает работающий сайт.
    """
    import urllib.request

    from factory.cell import privileged

    попытки: list[float] = []

    class Ответ:
        status = 200
        headers = {"X-Site-Factory-Build-Id": "abc-lords-05"}

        def read(self, _n=None):
            return b"<html></html>"

        def __enter__(self):
            return self

        def __exit__(self, *_):
            return False

    def открыть(url, timeout=None):
        попытки.append(timeout)
        # Первые два предела истекают, третий отвечает — как у холодной витрины.
        if len(попытки) <= 2:
            raise TimeoutError("cold start")
        return Ответ()

    monkeypatch.setattr(urllib.request, "urlopen", открыть)
    итог = privileged.verify("lords-05", порт=9113, маршруты=("/",))
    assert итог["routes"]["/"]["status"] == 200, итог
    assert итог["routes"]["/"]["попытка"] == 3
    assert попытки == [30, 60, 120], попытки
    assert итог["ok"] is True


def test_приёмка_отказывает_после_всех_попыток(monkeypatch):
    """Исчерпав пределы, проверка называет число попыток и суммарное ожидание."""
    import urllib.request

    from factory.cell import privileged

    def открыть(url, timeout=None):
        raise TimeoutError("always cold")

    monkeypatch.setattr(urllib.request, "urlopen", открыть)
    итог = privileged.verify("lords-05", порт=9113, маршруты=("/",))
    запись = итог["routes"]["/"]
    assert запись["error"] == "TimeoutError"
    assert запись["попыток"] == 3
    assert запись["суммарное_ожидание_с"] == 210
    assert итог["ok"] is False


def test_смена_издателя_не_откатывается_переносом(tmp_path, monkeypatch):
    """Витрина сменила издателя — перенос обязан взять НОВОЕ значение.

    Измерено на zonafilm.space: владелец назначил домену publisher 10252 вместо
    10238, а исполнитель на каждом выпуске копировал `config/player.json` из
    ДЕЙСТВУЮЩЕГО выпуска — то есть ровно прежнее значение. Выкладка молча
    возвращала бы старое назначение каждый раз, и сменить его штатным способом
    было бы нельзя вовсе.

    Источник, расходящийся с объявлением выпуска, пропускается, и перебор идёт
    дальше — к каталогу производителя, где значение и меняют.
    """
    п = _площадка(tmp_path)
    (п.app / "config" / "player.json").write_text(
        json.dumps({"publisher_id": "10238"}), encoding="utf-8")
    произв = tmp_path / "frontend"
    произв.mkdir()
    (произв / "player-zona-01.json").write_text(
        json.dumps({"publisher_id": "10252"}), encoding="utf-8")
    monkeypatch.setattr(privileged, "ПЛЕЕР_ПРОИЗВОДИТЕЛЯ", произв)
    monkeypatch.setattr(privileged.shutil, "chown", lambda *a, **k: None)
    выпуск = _выпуск(tmp_path, publisher="10252")
    assert privileged._перенести_локальную_настройку(выпуск, п) == ["config/player.json"]
    легло = json.loads((выпуск / "config" / "player.json").read_text(encoding="utf-8"))
    assert легло["publisher_id"] == "10252", "перенос вернул прежнего издателя"


def test_смена_издателя_без_нового_значения_это_отказ(tmp_path, monkeypatch):
    """Ни один источник не знает нового издателя — отказ с названными числами.

    Поставить прежнее значение значило бы выложить выпуск, который тут же
    провалит собственную проверку готовности: `run.py --check` отвечает
    «publisher_id X, а сайт объявляет Y» и служба не поднимается. Отказ здесь
    честнее: он называет, где именно значение не обновили.
    """
    п = _площадка(tmp_path)
    (п.app / "config" / "player.json").write_text(
        json.dumps({"publisher_id": "10238"}), encoding="utf-8")
    произв = tmp_path / "frontend"
    произв.mkdir()
    (произв / "player-zona-01.json").write_text(
        json.dumps({"publisher_id": "10238"}), encoding="utf-8")
    monkeypatch.setattr(privileged, "ПЛЕЕР_ПРОИЗВОДИТЕЛЯ", произв)
    with pytest.raises(privileged.PrivilegedRefused, match="10252"):
        privileged._перенести_локальную_настройку(
            _выпуск(tmp_path, publisher="10252"), п)


def test_файл_без_издателя_переносится_как_прежде(tmp_path, monkeypatch):
    """Пустой или нечитаемый файл плеера не отбраковывается.

    «Сказать нечего» — не то же самое, что «сказано другое»: прежнее поведение
    для таких источников сохраняется, иначе первый выпуск витрины, у которой
    боковой файл ещё заготовка, стал бы отказом на ровном месте.
    """
    п = _площадка(tmp_path)
    (п.app / "config" / "player.json").write_text("{}", encoding="utf-8")
    monkeypatch.setattr(privileged.shutil, "chown", lambda *a, **k: None)
    assert privileged._перенести_локальную_настройку(
        _выпуск(tmp_path, publisher="10252"), п) == ["config/player.json"]
