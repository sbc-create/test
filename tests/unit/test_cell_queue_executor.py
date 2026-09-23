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
