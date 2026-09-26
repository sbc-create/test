"""Заявка на выпуск и её исполнитель: граница проходит по схеме, а не по правам.

Соблазнительное решение — разрешить владельцу один раз выполнить «любой скрипт
по такому-то пути от root». Оно не работает: кто может писать в этот путь, тот
выполняет код от root. Поэтому между непривилегированной стороной и root стоит
файл заявки, в котором нет и не может быть ни пути, ни команды.

Проверяется поведение: каждая негодная заявка отвергается ДО взятия замка и до
единой мутации, а повтор продолжает первую операцию, а не заводит вторую.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

КОРЕНЬ = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(КОРЕНЬ))

from factory.cell import executor, queue  # noqa: E402

КОММИТ = "a" * 40
ДАЙДЖЕСТ = "sha256:" + "b" * 64


def test_повтор_не_заводит_вторую_операцию(tmp_path):
    з = queue.собрать("zona-01", КОММИТ, ДАЙДЖЕСТ)
    assert queue.подать(з, база=tmp_path)["status"] == "queued"
    assert queue.подать(з, база=tmp_path)["status"] == "already-queued"
    # Ровно один файл заявки: обрыв сети у подающего не должен множить операции.
    assert len(list((tmp_path / "requests").glob("*.json"))) == 1


def test_идентификатор_устойчив_к_повтору():
    """Случайная часть в идентификаторе сломала бы идемпотентность."""
    a = queue.собрать("zona-01", КОММИТ, ДАЙДЖЕСТ).request_id
    b = queue.собрать("zona-01", КОММИТ, ДАЙДЖЕСТ).request_id
    assert a == b


def test_тот_же_идентификатор_с_другим_выпуском_отвергается(tmp_path):
    """Иначе повтор молча заменил бы идущую операцию другой."""
    з = queue.собрать("zona-01", КОММИТ, ДАЙДЖЕСТ)
    queue.подать(з, база=tmp_path)
    другой = queue.разобрать({**з.as_dict(), "commit": "c" * 40})
    with pytest.raises(queue.RequestRejected):
        queue.подать(другой, база=tmp_path)


@pytest.mark.parametrize("поле,значение", [
    ("site_id", "../etc"),
    ("site_id", "ZONA-01"),
    ("commit", "HEAD"),
    ("commit", "93a7106af2e0"),          # коротко: 12 знаков не доказывают коммит
    ("digest", "93a7106af2e0"),
    ("digest", "md5:" + "b" * 32),
    ("request_id", "x"),
    ("operation", "shell"),
])
def test_форма_проверяется_до_всего_остального(поле, значение):
    сырое = {"request_id": "zona-01-aaaaaaaaaaaa", "operation": "activate",
             "site_id": "zona-01", "commit": КОММИТ, "digest": ДАЙДЖЕСТ}
    сырое[поле] = значение
    with pytest.raises(queue.RequestRejected):
        queue.разобрать(сырое)


def test_свободных_полей_в_заявке_нет():
    """Заявка со свободными полями перестаёт быть договором."""
    сырое = {"request_id": "zona-01-aaaaaaaaaaaa", "operation": "activate",
             "site_id": "zona-01", "commit": КОММИТ, "digest": ДАЙДЖЕСТ,
             "script": "/tmp/evil.sh"}
    with pytest.raises(queue.RequestRejected) as ош:
        queue.разобрать(сырое)
    assert "script" in str(ош.value)


def test_незарегистрированный_сайт_отвергается_до_замка(tmp_path):
    з = queue.собрать("net-takogo", КОММИТ, ДАЙДЖЕСТ)
    queue.подать(з, база=tmp_path)
    итог = executor.обслужить_очередь(база=tmp_path, dry_run=True)[0]
    assert итог["status"] == "rejected"
    assert "реестре" in итог["error"]
    # Замок не брался: отказ наступил раньше любой мутации.
    assert not (tmp_path / "locks").exists()


def test_результат_пишется_раньше_снятия_заявки(tmp_path):
    """Обратный порядок терял бы операцию при гибели процесса между шагами."""
    з = queue.собрать("net-takogo", КОММИТ, ДАЙДЖЕСТ)
    queue.подать(з, база=tmp_path)
    executor.обслужить_очередь(база=tmp_path, dry_run=True)
    assert (tmp_path / "results" / f"{з.request_id}.json").is_file()
    assert not (tmp_path / "requests" / f"{з.request_id}.json").exists()


def test_неудавшаяся_заявка_подаётся_снова(tmp_path):
    """Один сбой не должен запирать выпуск этого коммита навсегда.

    Причина отказа устраняется, и заявка обязана быть повторяемой. Иначе
    единственным выходом стал бы новый коммит ради нового идентификатора.
    """
    з = queue.собрать("net-takogo", КОММИТ, ДАЙДЖЕСТ)
    queue.подать(з, база=tmp_path)
    executor.обслужить_очередь(база=tmp_path, dry_run=True)
    повтор = queue.подать(з, база=tmp_path)
    assert повтор["status"] == "requeued-after-failure"
    assert повтор["previous_status"] == "rejected"
    assert (tmp_path / "requests" / f"{з.request_id}.json").is_file()


def test_успешная_заявка_повторно_не_выкладывается(tmp_path):
    """Успех уже применён: второй прогон стал бы повторной выкладкой."""
    з = queue.собрать("zona-01", КОММИТ, ДАЙДЖЕСТ)
    queue.подать(з, база=tmp_path)
    queue.записать_атомарно(tmp_path / "results" / f"{з.request_id}.json",
                            {"request_id": з.request_id, "status": "ok"})
    (tmp_path / "requests" / f"{з.request_id}.json").unlink()
    assert queue.подать(з, база=tmp_path)["status"] == "already-finished"


def test_живой_замок_не_отнимается(tmp_path):
    """Возраст не доказывает смерть владельца — живого ждём."""
    замок = executor.взять_замок("zona-01", база=tmp_path, операция="activate")
    assert замок.владелец["pid"] > 0
    with pytest.raises(executor.ExecutorError) as ош:
        executor.взять_замок("zona-01", база=tmp_path, операция="update")
    assert "живой процесс" in str(ош.value)
    замок.снять()


def test_замок_без_отметки_старта_не_снимается_сам(tmp_path):
    """Ровно тот случай, который однажды потребовал решения человека."""
    каталог = tmp_path / "locks"
    каталог.mkdir(parents=True)
    (каталог / "zona-01.json").write_text(
        json.dumps({"pid": 999999, "site": "zona-01", "operation": "activate"}),
        encoding="utf-8")
    with pytest.raises(executor.ExecutorError) as ош:
        executor.взять_замок("zona-01", база=tmp_path, операция="activate")
    assert "отметки старта" in str(ош.value)


def test_замок_мёртвого_владельца_перехватывается(tmp_path):
    """Доказанная смерть — не догадка: pid не отвечает или это другой процесс."""
    каталог = tmp_path / "locks"
    каталог.mkdir(parents=True)
    (каталог / "zona-01.json").write_text(
        json.dumps({"pid": 999999, "starttime": "123456", "site": "zona-01",
                    "operation": "activate"}), encoding="utf-8")
    замок = executor.взять_замок("zona-01", база=tmp_path, операция="activate")
    assert замок.владелец["pid"] == __import__("os").getpid()
    замок.снять()


def test_испорченный_замок_требует_человека(tmp_path):
    """Испорченный замок хуже отсутствующего: он молча разрешает всё."""
    каталог = tmp_path / "locks"
    каталог.mkdir(parents=True)
    (каталог / "zona-01.json").write_text("{не json", encoding="utf-8")
    with pytest.raises(executor.ExecutorError) as ош:
        executor.взять_замок("zona-01", база=tmp_path, операция="activate")
    assert "нечитаем" in str(ош.value)


def test_журнал_переходов_переживает_процесс(tmp_path):
    """Восстановление начинается со сверки журнала с фактом, а не с догадки."""
    з = queue.собрать("zona-01", КОММИТ, ДАЙДЖЕСТ)
    queue.подать(з, база=tmp_path)
    файл = tmp_path / "requests" / f"{з.request_id}.json"
    queue.отметить(файл, "validated", {"remote": "…"})
    queue.отметить(файл, "artifact_verified")
    записано = json.loads(файл.read_text(encoding="utf-8"))["stages"]
    assert [s["stage"] for s in записано] == ["received", "validated", "artifact_verified"]
    assert all(s.get("at") for s in записано[1:])


def test_неизвестный_этап_не_записывается(tmp_path):
    з = queue.собрать("zona-01", КОММИТ, ДАЙДЖЕСТ)
    queue.подать(з, база=tmp_path)
    файл = tmp_path / "requests" / f"{з.request_id}.json"
    with pytest.raises(queue.RequestRejected):
        queue.отметить(файл, "почти_готово")


def test_грязное_дерево_не_выкладывается(monkeypatch, tmp_path):
    """Совпадение digest ничего не доказывает, если дерево правит подающий.

    И заявку, и рабочую копию правит одна непривилегированная сторона. Без
    этой проверки выложилось бы дерево с несохранённой правкой, а отчёт назвал
    бы коммит, которого на сайте нет.
    """
    from factory.cell import privileged, registry, runtime

    репо = tmp_path / "repo"
    (репо / "tools").mkdir(parents=True)
    (репо / "tools" / "build_release.py").write_text("", encoding="utf-8")
    monkeypatch.setattr(registry.Cell, "repo_path", property(lambda self: репо))
    monkeypatch.setattr(runtime, "размещение", lambda *a, **k: runtime.Размещение(
        site_id="zona-01", domain="zonafilm.space", data_dir="/srv/x/data",
        unit="u.service", previous_unit="p.service", port=9120,
        account="nobody", reload="mtime", managed_by="cell"))
    monkeypatch.setattr(privileged, "собрать_без_прав", lambda *a, **k: (
        tmp_path / "a.tar.gz",
        {"source_commit": КОММИТ, "digest": ДАЙДЖЕСТ, "source_dirty": True,
         "live_build_id": "aaaaaaaaaaaa-zona-01"}))

    з = queue.собрать("zona-01", КОММИТ, ДАЙДЖЕСТ)
    with pytest.raises(executor.ExecutorError) as ош:
        executor.активировать(з, файл=tmp_path / "нет.json", dry_run=True)
    assert "несохранённые" in str(ош.value)


def test_непроверяемое_происхождение_это_отказ(monkeypatch):
    """`checked: false` рядом с успешным выпуском — не проверка, а её вид.

    У root нет входа в gh, и связка «этот коммит прошёл этот прогон» тихо
    выключалась: результат выглядел одинаково и когда происхождение доказано,
    и когда его не спросили.
    """
    з = queue.собрать("zona-01", КОММИТ, ДАЙДЖЕСТ)  # без ci_run
    with pytest.raises(executor.ПроисхождениеНеПодтверждено, match="не называет прогон"):
        executor.проверить_ci(з, remote="https://github.com/o/r")


def test_молчание_github_не_пропускает_выпуск(monkeypatch):
    """Недоступный GitHub обязан останавливать, а не разрешать по умолчанию."""
    def нет_связи(*a, **k):
        class Р:
            returncode, stdout, stderr = 1, "", "gh: not logged in"
        return Р()
    monkeypatch.setattr(executor.subprocess, "run", нет_связи)
    з = queue.собрать("zona-01", КОММИТ, ДАЙДЖЕСТ, ci_run="123")
    with pytest.raises(executor.ПроисхождениеНеПодтверждено, match="GitHub не ответил"):
        executor.проверить_ci(з, remote="https://github.com/o/r")


@pytest.mark.parametrize("ответ,ожидание", [
    ({"status": "in_progress", "conclusion": None}, "ещё не завершён"),
    ({"status": "completed", "conclusion": "failure"}, "завершился как"),
    ({"status": "completed", "conclusion": "success", "headSha": "c" * 40},
     "ничего не доказывает"),
    ({"status": "completed", "conclusion": "success", "headSha": КОММИТ,
      "headBranch": "claude/experiment"}, "разрешён только с"),
])
def test_каждое_звено_связки_обязательно(monkeypatch, ответ, ожидание):
    """Репозиторий, ветка, точный коммит и успешный прогон — все четыре."""
    полный = {"headSha": КОММИТ, "headBranch": "main", "databaseId": 1,
              "workflowName": "release", **ответ}

    def ответил(*a, **k):
        class Р:
            returncode, stderr = 0, ""
            stdout = json.dumps(полный)
        return Р()
    monkeypatch.setattr(executor.subprocess, "run", ответил)
    з = queue.собрать("zona-01", КОММИТ, ДАЙДЖЕСТ, ci_run="123")
    with pytest.raises(executor.ExecutorError, match=ожидание):
        executor.проверить_ci(з, remote="https://github.com/o/r")


def test_проверка_спрашивает_репозиторий_из_реестра(monkeypatch):
    """Иначе прогон чужого проекта с подходящим SHA прошёл бы проверку."""
    снято = {}

    def ответил(cmd, *a, **k):
        снято["cmd"] = cmd
        class Р:
            returncode, stderr = 0, ""
            stdout = json.dumps({"headSha": КОММИТ, "headBranch": "main",
                                 "status": "completed", "conclusion": "success",
                                 "databaseId": 7, "workflowName": "release"})
        return Р()
    monkeypatch.setattr(executor.subprocess, "run", ответил)
    з = queue.собрать("zona-01", КОММИТ, ДАЙДЖЕСТ, ci_run="123")
    итог = executor.проверить_ci(з, remote="https://github.com/sbc-create/site-x.git")
    assert "-R" in снято["cmd"]
    assert снято["cmd"][снято["cmd"].index("-R") + 1] == "sbc-create/site-x"
    assert итог == {"checked": True, "repo": "sbc-create/site-x", "branch": "main",
                    "run": "7", "workflow": "release", "conclusion": "success"}


def test_отказ_наступает_до_замка_и_до_мутаций(tmp_path, monkeypatch):
    """Главное свойство: работающий сайт не трогают, пока связка не доказана."""
    def нет_связи(*a, **k):
        class Р:
            returncode, stdout, stderr = 1, "", "gh: not logged in"
        return Р()
    monkeypatch.setattr(executor.subprocess, "run", нет_связи)
    з = queue.собрать("zona-01", КОММИТ, ДАЙДЖЕСТ, ci_run="123")
    queue.подать(з, база=tmp_path)
    итог = executor.обслужить_очередь(база=tmp_path, dry_run=False)[0]
    assert итог["status"] == "rejected"
    assert "GitHub не ответил" in итог["error"]
    # Замка не было, значит не было и ни одной операции над витриной.
    assert not (tmp_path / "locks").exists()
    assert "outcome" not in итог


def test_ручная_активация_от_root_закрыта():
    """Второй путь выкладки — тот, что не спрашивает GitHub ни о чём.

    Он исполняет сценарий репозитория от root. Пока он оставался проходимым,
    «выкладка без доказанного происхождения» требовала одного лишнего флага.
    """
    from factory.cell import admin_exec
    with pytest.raises(admin_exec.ExecutorRefused, match="закрыта"):
        admin_exec.активировать("zona-01", commit=КОММИТ, dry_run=False)


def test_очередь_остаётся_единственным_путём_выпуска():
    """Ни одно место не должно звать активацию в обход проверки происхождения."""
    import ast
    корень = КОРЕНЬ / "factory" / "cell"
    # cli.py зовёт её ради сухого прогона; сам отказ живёт внутри
    # admin_exec.активировать, и проверяется он отдельным тестом. Здесь
    # сторожится появление НОВОГО вызывающего.
    разрешено = {"executor.py", "admin_exec.py", "cli.py"}
    for файл in sorted(корень.glob("*.py")):
        if файл.name in разрешено:
            continue
        дерево = ast.parse(файл.read_text(encoding="utf-8"))
        for узел in ast.walk(дерево):
            if (isinstance(узел, ast.Attribute) and узел.attr == "активировать"
                    and isinstance(узел.value, ast.Name)
                    and узел.value.id == "admin_exec"):
                raise AssertionError(f"{файл.name}: зовёт admin_exec.активировать")


def test_доставка_данных_не_требует_прогона_ci(monkeypatch):
    """Данные — не код. Требовать от них прогон значило бы остановить каталог.

    Подмены здесь нет: заявка на доставку не зовёт install_release вовсе, то
    есть операцией `deliver` нового исполняемого кода на сайт не поставить.
    """
    def не_должен_звать(*a, **k):
        raise AssertionError("доставка спрашивала GitHub")
    monkeypatch.setattr(executor.subprocess, "run", не_должен_звать)
    з = queue.собрать("zona-01", КОММИТ, ДАЙДЖЕСТ, operation="deliver")
    итог = executor.проверить_ci(з, remote="https://github.com/o/r", операция="deliver")
    assert итог == {"checked": False, "applicable": False,
                    "reason": "операция deliver не ставит новый код"}


def test_доставка_не_ставит_код():
    """Основание предыдущего теста, а не допущение: проверяется по исходнику."""
    import ast
    дерево = ast.parse((КОРЕНЬ / "factory" / "cell" / "executor.py")
                       .read_text(encoding="utf-8"))
    for узел in ast.walk(дерево):
        if isinstance(узел, ast.FunctionDef) and узел.name == "обновить_данные":
            вызовы = {у.func.attr for у in ast.walk(узел)
                      if isinstance(у, ast.Call) and isinstance(у.func, ast.Attribute)}
            assert "install_release" not in вызовы
            break
    else:
        raise AssertionError("обновить_данные не найдена")


def test_повтор_не_требует_удаления_прежнего_результата(tmp_path):
    """Подающая сторона результаты только читает — стирать их ей нечем.

    Каталог результатов принадлежит исполнителю именно затем, чтобы подающий
    не мог подменить или стереть чужой вывод. Пока подача пыталась убрать
    прежний файл, повтор неудачной заявки падал с EACCES на живом сервере.
    """
    з = queue.собрать("zona-01", КОММИТ, ДАЙДЖЕСТ)
    результат = tmp_path / "results" / f"{з.request_id}.json"
    queue.записать_атомарно(результат, {"request_id": з.request_id,
                                        "status": "rejected"})
    результаты = tmp_path / "results"
    режим = результаты.stat().st_mode
    результаты.chmod(0o550)                    # как на сервере: чтение без записи
    try:
        итог = queue.подать(з, база=tmp_path)
    finally:
        результаты.chmod(режим)
    assert итог["status"] == "requeued-after-failure"
    assert итог["previous_status"] == "rejected"
    assert (tmp_path / "requests" / f"{з.request_id}.json").is_file()
    assert результат.is_file(), "прежний результат должен уцелеть до перезаписи"


def test_первый_выпуск_засевает_хранилище(tmp_path, monkeypatch):
    """Выделенная ячейка начинает с пустым хранилищем, и кандидат в нём не встаёт.

    Витрина под монолитом читает общий каталог производителя; у ячейки он свой.
    Проверено сборкой lords-01 на пустом каталоге данных: «нет снимка каталога
    …: витрине нечего показывать» — отказ до первого запроса.
    """
    from factory.cell import privileged

    площадка = privileged.Площадка(
        site_id="lords-01", account="nobody", root=tmp_path,
        app=tmp_path / "app", data=tmp_path / "data", unit="u.service",
        previous_unit="p.service", port=9110)
    (tmp_path / "data").mkdir()
    monkeypatch.setattr(privileged.Площадка, "из_реестра",
                        staticmethod(lambda *a, **k: площадка))
    звали = []
    monkeypatch.setattr(privileged, "stage_snapshot",
                        lambda *a, **k: звали.append("stage") or {"ok": True})
    monkeypatch.setattr(privileged, "promote_snapshot",
                        lambda *a, **k: звали.append("promote") or {"ok": True})

    итог = executor._засеять_хранилище("lords-01", dry_run=True)
    assert итог["seeded"] is True and звали == ["stage", "promote"]

    # Один каталог наполненным хранилищем не считается: пятиминутный конвейер
    # кладёт в ячейку только его, и по нему витрина выложилась бы обеднённой —
    # 12 карточек вместо 48 и ноль ссылок на серии.
    (tmp_path / "data" / "lords-01-catalog.json").write_text("{}", encoding="utf-8")
    звали.clear()
    итог = executor._засеять_хранилище("lords-01", dry_run=True)
    assert итог["seeded"] is True and итог["missing"] == ["lords-01-details.json"]

    # Весь снимок на месте — выпуск кода данных не касается.
    (tmp_path / "data" / "lords-01-details.json").write_text("{}", encoding="utf-8")
    звали.clear()
    итог = executor._засеять_хранилище("lords-01", dry_run=True)
    assert итог["seeded"] is False and звали == []


def test_площадка_готовится_до_сборки():
    """Сборщик запускается под учётной записью САЙТА, а создаёт её prepare.

    При первом выпуске витрины учётной записи ещё нет, и сборка падала на
    getpwnam раньше, чем что-либо происходило. Проверено на lords-01:
    учётной записи lordfilm47-space не существовало, заявка уходила в
    бесконечный повтор по таймеру.
    """
    import inspect
    текст = inspect.getsource(executor.активировать)
    assert текст.index('шаги["prepare"]') < текст.index("собрать_без_прав"), (
        "сборка под учётной записью сайта не может идти раньше её создания")
    assert текст.index('шаги["seed_data"]') < текст.index("собрать_без_прав")


def test_непредвиденный_отказ_оставляет_результат(tmp_path, monkeypatch):
    """Заявка без результата повторяется таймером вечно.

    Снаружи это выглядит как «операция идёт»: заявка на месте, результата
    нет, в журнале службы раз в минуту одно и то же исключение.
    """
    def падает(*a, **k):
        raise KeyError("getpwnam(): name not found: lordfilm47-space")
    monkeypatch.setattr(executor, "проверить_заявку", падает)

    з = queue.собрать("zona-01", КОММИТ, ДАЙДЖЕСТ, ci_run="1")
    queue.подать(з, база=tmp_path)
    итог = executor.обслужить_очередь(база=tmp_path, dry_run=True)[0]
    assert итог["status"] == "rejected"
    assert "непредвиденный отказ KeyError" in итог["error"]
    # Заявка снята, результат на месте: повтора по таймеру не будет.
    assert not (tmp_path / "requests" / f"{з.request_id}.json").exists()
    assert (tmp_path / "results" / f"{з.request_id}.json").is_file()


def test_обход_очереди_виден_а_откат_обходом_не_считается(tmp_path, monkeypatch):
    """Выпуск, поставленный мимо очереди, обязан быть видимым.

    В репозитории каждой витрины остались `deploy/activate.sh` и
    `deploy/rollback.sh`: запуск от root кладёт выпуск мимо исполнителя, и ни
    ветка, ни коммит, ни прогон при этом не проверяются. Снаружи это
    неотличимо от штатного выпуска — сайт отвечает 200 и называет ожидаемый
    build-id.

    Отдельно сторожится ложное срабатывание: выпуск, который исполнитель
    развернул в попытке, ЗАКОНЧИВШЕЙСЯ ОТКАТОМ, остаётся в releases/ и обходом
    не является. На первом прогоне проверка назвала таким обходом zona-01.
    """
    from factory.cell import privileged
    from factory.cell import registry as рег

    корень = tmp_path / "srv"
    (корень / "releases" / "aaaaaaaaaaaa").mkdir(parents=True)   # успешный
    (корень / "releases" / "bbbbbbbbbbbb").mkdir()               # откат
    (корень / "releases" / "cccccccccccc").mkdir()               # мимо очереди
    (корень / "current").symlink_to(корень / "releases" / "cccccccccccc")
    п = privileged.Площадка(site_id="lords-02", account="nobody", root=корень,
                            app=корень / "app", data=корень / "data",
                            unit="u.service", previous_unit=None, port=9111)
    monkeypatch.setattr(privileged.Площадка, "из_реестра", staticmethod(lambda *a, **k: п))
    monkeypatch.setattr(рег, "extracted_sites", lambda: ["lords-02"])

    результаты = tmp_path / "results"
    результаты.mkdir()
    queue.записать_атомарно(результаты / "lords-02-code-aaaaaaaaaaaa.json",
                            {"commit": "a" * 40, "status": "ok"})
    queue.записать_атомарно(результаты / "lords-02-code-bbbbbbbbbbbb.json",
                            {"commit": "b" * 40, "status": "failed"})

    итог = executor.происхождение_выпусков(база=tmp_path)
    место = итог["sites"][0]
    assert место["outside_queue"] == ["cccccccccccc"], "откат обходом не считается"
    assert место["by_executor"] is False, "исполняется выпуск, которого нет в результатах"
    assert итог["bypassed"] == ["lords-02"]


def test_каждый_успешный_исход_исполнителя_назван_применённым():
    """Перечень применённых исходов не должен отставать от исполнителя.

    `ПРИМЕНЁННЫЕ_ИСХОДЫ` решает, что записать в результат: `ok` или `failed`.
    Пока через очередь шли только выпуски кода, перечень совпадал с
    действительностью случайно: `активировать` возвращает `activated`, и он
    там был. Операция `deliver` возвращает `delivered`, и его там не было —
    первая же успешная доставка данных получила бы `status: failed` при
    новом каталоге на витрине, а заявка считалась бы неприменённой и подалась
    бы снова.

    Проверка читает ИСХОДНИК исполнителя, а не повторяет перечень: разойтись
    они могут только вместе с новой операцией, и тогда тест назовёт её имя.
    Правило разделения: исход, доведённый до `live_verified` (или до
    `validated` в сухом прогоне), — применён; `failed` и `rolled_back` — нет.
    """
    import ast

    исходник = (КОРЕНЬ / "factory" / "cell" / "executor.py").read_text(encoding="utf-8")
    дерево = ast.parse(исходник)

    def значения(узел):
        """Литералы ветви: у `x if c else y` их два, и важны оба."""
        if isinstance(узел, ast.Constant):
            return [узел.value]
        if isinstance(узел, ast.IfExp):
            return значения(узел.body) + значения(узел.orelse)
        return []

    ОПЕРАЦИИ = {"активировать", "обновить_данные"}
    успешные: dict[str, str] = {}
    неуспешные: dict[str, str] = {}
    найдено = set()
    for узел in ast.walk(дерево):
        if not isinstance(узел, ast.FunctionDef) or узел.name not in ОПЕРАЦИИ:
            continue
        найдено.add(узел.name)
        for внутри in ast.walk(узел):
            if not isinstance(внутри, ast.Return) or not isinstance(внутри.value, ast.Dict):
                continue
            поля: dict[str, list] = {}
            for ключ, значение in zip(внутри.value.keys, внутри.value.values):
                if isinstance(ключ, ast.Constant) and ключ.value in ("status", "stage"):
                    поля[ключ.value] = значения(значение)
            статусы, этапы = поля.get("status", []), поля.get("stage", [])
            if not статусы or not этапы:
                continue
            куда = (успешные if set(этапы) <= {"live_verified", "validated"}
                    else неуспешные)
            for с in статусы:
                куда[с] = узел.name

    assert найдено == ОПЕРАЦИИ, f"в исполнителе нет операций: {ОПЕРАЦИИ - найдено}"
    assert успешные, "не нашли ни одного успешного исхода — разбор сломался"

    забыты = {с: ф for с, ф in успешные.items() if с not in queue.ПРИМЕНЁННЫЕ_ИСХОДЫ}
    assert not забыты, (
        "исход доведён до живой проверки, но не назван применённым: "
        + ", ".join(f"{с} (из {ф})" for с, ф in sorted(забыты.items()))
        + " — успешная операция будет записана как failed")

    лишние = {с: ф for с, ф in неуспешные.items()
              if с in queue.ПРИМЕНЁННЫЕ_ИСХОДЫ and с not in успешные}
    assert not лишние, (
        "исход откачен или провален, но назван применённым: "
        + ", ".join(f"{с} (из {ф})" for с, ф in sorted(лишние.items())))


def test_правки_применяются_только_те_что_подготовлены(tmp_path, monkeypatch):
    """Заявка не несёт содержимого — значит `digest` обязан его доказывать.

    Схема заявки закрытая: ни путей, ни правок в ней нет, и путь
    подготовленного обе стороны выводят из `site_id`. Единственное, что
    связывает решение админки с тем, что записал исполнитель, — отпечаток
    содержимого. Без сверки подмена подготовленного файла между подачей заявки
    и её исполнением прошла бы незамеченной.
    """
    from factory.cell import editorial_store, privileged

    monkeypatch.setattr(editorial_store, "БАЗА", tmp_path / "staging")
    готово = editorial_store.подготовить(
        "zona-01", {"01a0-a": {"fields": {"description": "Правка редактора"}}},
        actor="editor@example", reason="уточнение по просьбе владельца")

    записано = {}
    monkeypatch.setattr(privileged, "применить_правки",
                        lambda site_id, содержимое, **k: записано.update(
                            {"site": site_id, "entries": len(содержимое["overrides"])})
                        or {"operation": "editorial", "dry_run": k.get("dry_run")})

    з = queue.собрать("zona-01", КОММИТ, готово["digest"], operation="editorial")
    итог = executor.применить_правки(з, dry_run=True)
    assert итог["status"] == "dry-run"
    assert записано == {"site": "zona-01", "entries": 1}

    # Подмена подготовленного после подачи заявки: digest перестаёт сходиться.
    editorial_store.подготовить(
        "zona-01", {"01a0-a": {"fields": {"description": "ПОДМЕНА"}}},
        actor="chuzhoy@example", reason="подмена")
    with pytest.raises(executor.ExecutorError) as ош:
        executor.применить_правки(з, dry_run=True)
    assert "не совпал" in str(ош.value)


def test_правки_чужого_сайта_не_применяются(tmp_path, monkeypatch):
    """Область сайта входит в содержимое, а не проверяется где-то потом."""
    from factory.cell import editorial_store

    monkeypatch.setattr(editorial_store, "БАЗА", tmp_path / "staging")
    editorial_store.подготовить("lords-02", {"x": {"fields": {"name": "Чужое"}}},
                                actor="a@b", reason="проверка")
    # Файл lords-02 подсунут под именем zona-01.
    (tmp_path / "staging" / "zona-01.json").write_text(
        (tmp_path / "staging" / "lords-02.json").read_text(encoding="utf-8"),
        encoding="utf-8")
    with pytest.raises(executor.ExecutorError) as ош:
        executor.применить_правки(
            queue.собрать("zona-01", КОММИТ, "sha256:" + "0" * 64,
                          operation="editorial"), dry_run=True)
    assert "подготовлено для сайта" in str(ош.value)


def test_исход_правок_назван_применённым():
    """`edited` обязан значиться применённым — иначе успех запишется отказом."""
    assert "edited" in queue.ПРИМЕНЁННЫЕ_ИСХОДЫ
