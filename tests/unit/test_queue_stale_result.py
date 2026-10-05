"""Результат ПРОШЛОЙ попытки не выдаётся за итог текущей.

Случай измерен 2026-10-04. Идентификатор заявки на слой индексации
детерминированный (`<site>-idx-<mode>`), и результат прошлой попытки лежит в
каталоге исполнителя. Отклонённую заявку очередь перепоставляет правильно
(`requeued-after-failure`, `retry_after: rejected`), но ожидание читает
состояние СРАЗУ: файл результата уже есть — от прошлой попытки, — и `состояние`
отвечает `finished`. Ожидание принимает его за итог своей заявки и отдаёт
старый отказ.

Пока причина отказа не менялась, подмену не видно: текст совпадает. Опасна она
ровно тогда, когда причину устранили — первая же попытка после исправления
вернула бы прошлый отказ, и исправление выглядело бы не подействовавшим.

Поэтому `состояние` принимает `не_раньше`: результат старше поданной заявки —
это ещё не её результат.
"""
from __future__ import annotations

import json
import pathlib

import pytest

from factory.cell import queue as q


@pytest.fixture()
def база(tmp_path: pathlib.Path) -> pathlib.Path:
    (tmp_path / "requests").mkdir()
    (tmp_path / "results").mkdir()
    return tmp_path


def _результат(база: pathlib.Path, когда: str, статус: str = "rejected") -> None:
    (база / "results" / "lords-05-idx-open.json").write_text(json.dumps({
        "request_id": "lords-05-idx-open", "site_id": "lords-05",
        "operation": "indexing-nginx", "status": статус, "started_at": когда,
        "error": "открытие слоя nginx запрещено — в реестре ячеек "
                 "indexing.open_authorized не равно true",
    }, ensure_ascii=False), encoding="utf-8")


def _заявка(база: pathlib.Path, когда: str) -> None:
    (база / "requests" / "lords-05-idx-open.json").write_text(json.dumps({
        "request_id": "lords-05-idx-open", "site_id": "lords-05",
        "operation": "indexing-nginx", "mode": "OPEN", "commit": "",
        "submitted_at": когда,
        "stages": [{"stage": "received", "at": когда, "retry_after": "rejected"}],
    }, ensure_ascii=False), encoding="utf-8")


def test_старый_результат_не_считается_итогом_новой_заявки(база):
    _результат(база, "2026-10-04T08:36:00+00:00")
    _заявка(база, "2026-10-04T09:09:01+00:00")
    с = q.состояние("lords-05-idx-open", база=база,
                    не_раньше="2026-10-04T09:09:01+00:00")
    assert с["status"] == "queued", (
        "ожидание приняло результат прошлой попытки за итог текущей: "
        f"{с.get('status')!r}")
    assert с.get("stale_result"), "подмену нужно называть, а не скрывать"
    assert "08:36" in str(с["stale_result"].get("started_at"))


def test_свежий_результат_принимается(база):
    _результат(база, "2026-10-04T09:10:01+00:00")
    _заявка(база, "2026-10-04T09:09:01+00:00")
    с = q.состояние("lords-05-idx-open", база=база,
                    не_раньше="2026-10-04T09:09:01+00:00")
    assert с["status"] == "finished"
    assert с["result"]["status"] == "rejected", "исход обязан сохраниться как есть"


def test_без_не_раньше_поведение_прежнее(база):
    """Совместимость: `operation_result` показывает последний результат как есть."""
    _результат(база, "2026-10-04T08:36:00+00:00")
    _заявка(база, "2026-10-04T09:09:01+00:00")
    assert q.состояние("lords-05-idx-open", база=база)["status"] == "finished"


def test_нечитаемое_время_не_отбрасывает_результат(база):
    """Результат без `started_at` судить по времени нельзя — считаем свежим.

    Молчаливое «ещё не готово» на старых результатах подвесило бы ожидание на
    полный таймаут, а это та самая ошибка, из-за которой `состояние` появилось.
    """
    (база / "results" / "lords-05-idx-open.json").write_text(
        json.dumps({"request_id": "lords-05-idx-open", "status": "ok"}),
        encoding="utf-8")
    _заявка(база, "2026-10-04T09:09:01+00:00")
    с = q.состояние("lords-05-idx-open", база=база,
                    не_раньше="2026-10-04T09:09:01+00:00")
    assert с["status"] == "finished"


def test_ожидание_слоя_передаёт_время_подачи():
    """Исправление бесполезно, если ожидание о нём не знает."""
    текст = pathlib.Path("factory/qwen/indexing.py").read_text(encoding="utf-8")
    assert "не_раньше=заявка.submitted_at" in текст, (
        "ожидание слоя nginx читает состояние без времени подачи и снова "
        "примет прошлый отказ за итог текущей попытки")


def test_отказ_проверки_доступа_называет_инструмент_моста(tmp_path, monkeypatch):
    """Совет, недоступный читателю отказа, равен отсутствию совета.

    Оператор через MCP-мост получал «Повторить: python3 -m factory cell submit
    …» — команду, которой у него нет. Действие у него есть, и оно штатное:
    инструмент `refresh_executor_access`. Отказ обязан называть оба пути.
    """
    monkeypatch.setattr(q, "БАЗА", tmp_path)
    (tmp_path / "results").mkdir()
    with pytest.raises(q.RequestRejected) as ош:
        q.проверить_доступ_исполнителя("lords-01")
    текст = str(ош.value)
    assert "refresh_executor_access" in текст, текст
    assert "factory cell submit" in текст, "второй путь тоже обязан быть назван"


def test_уже_выполнено_не_означает_что_слой_в_нужном_режиме(monkeypatch, tmp_path):
    """«Уже выполнено» — утверждение о ЗАЯВКЕ, а не о состоянии слоя.

    Случай измерен 2026-10-04 на lordserials22.info и стоил второй попытки
    открытия. Последовательность:

      12:25:00  заявка `lords-05-idx-open` — исполнитель ПРИМЕНИЛ открытие;
      12:26     операция откатила открытие по своей причине и закрыла слой
                заявкой с суффиксом (`lords-05-idx-closed-rst122505`);
      12:31     новая попытка открытия получила от очереди `already-finished`
                по тому же идентификатору `lords-05-idx-open`, исполнителя не
                спросила вовсе — и операция сообщила «слой остался closed».

    Очередь права: успешную операцию она не повторяет. Но предмет здесь —
    РЕЖИМ, и его законно просить снова после того, как его вернули назад.
    Поэтому `already-finished` обязан проверяться чтением слоя, а не считаться
    доказательством: не в том режиме — подать заново с суффиксом, ровно тем же
    приёмом, которым пользуется возврат.
    """
    from factory.qwen import indexing

    class Сайт:
        site_id = "lords-05"
        domain = "t-idem.example"

    поданные: list[dict] = []

    def собрать(site_id, commit, digest, *, operation, mode, suffix="", note=""):
        class З:
            request_id = f"{site_id}-idx-{mode.lower()}" + (f"-{suffix}" if suffix else "")
            submitted_at = "2026-10-04T12:31:00+00:00"
        return З()

    def подать(заявка, **kw):
        поданные.append({"id": заявка.request_id})
        # Без суффикса очередь отвечает «уже выполнено» (прежний успех),
        # с суффиксом — принимает заявку. Суффикс и есть всё, что идёт после
        # базового идентификатора режима.
        if заявка.request_id == "lords-05-idx-open":
            return {"status": "already-finished", "request_id": заявка.request_id}
        return {"status": "queued", "request_id": заявка.request_id}

    слой = {"режим": "CLOSED"}

    def состояние(request_id, *, база=None, не_раньше=""):
        # Исполнитель применил режим по заявке с суффиксом.
        слой["режим"] = "OPEN"
        return {"status": "finished",
                "result": {"status": "ok", "outcome": {"status": "applied"},
                           "started_at": "2026-10-04T12:31:30+00:00"}}

    monkeypatch.setattr(q, "собрать", собрать)
    monkeypatch.setattr(q, "подать", подать)
    monkeypatch.setattr(q, "состояние", состояние)
    monkeypatch.setattr(indexing, "слой_nginx", lambda sid, d, сиг=None: {
        "mode": "closed" if слой["режим"] == "CLOSED" else "open",
        "denying": слой["режим"] == "CLOSED", "evidence": "стенд"})
    monkeypatch.setattr(indexing, "сигналы", lambda д, *, порт=0: {"domain": д})
    monkeypatch.setattr(indexing, "порт_приложения", lambda sid: 0)

    итог = indexing.переключить_слой(Сайт(), режим="OPEN", author="тест")
    assert слой["режим"] == "OPEN", (
        f"слой не переключён: {итог}; подано {поданные}")
    assert len(поданные) == 2, (
        f"повторная подача с суффиксом не сделана: {поданные}")
    assert поданные[0]["id"] == "lords-05-idx-open"
    assert поданные[1]["id"] != поданные[0]["id"], "суффикс не добавлен"
    assert итог.get("outcome") == "applied", итог


def test_последняя_заявка_находится_вместе_с_суффиксом(база):
    """Повторная подача различается суффиксом — и показывать надо ЕЁ.

    Расхождение измерено 2026-10-04: `indexing_journal` называл
    `lords-05-idx-open`, тогда как слой фактически применила
    `lords-05-idx-open-rep123904`. Инструмент спрашивал только
    детерминированное имя, а повторная заявка его не носит — иначе очередь
    ответила бы «уже выполнено» (ровно то, из-за чего суффикс и появился).
    Операция, связанная не с той заявкой, не проверяема: по ней читают исход
    чужой попытки.
    """
    (база / "results" / "lords-05-idx-open.json").write_text(json.dumps({
        "request_id": "lords-05-idx-open", "status": "ok",
        "outcome": {"status": "applied"},
        "started_at": "2026-10-04T12:25:00+00:00"}), encoding="utf-8")
    (база / "results" / "lords-05-idx-open-rep123904.json").write_text(json.dumps({
        "request_id": "lords-05-idx-open-rep123904", "status": "ok",
        "outcome": {"status": "applied"},
        "started_at": "2026-10-04T12:40:00+00:00"}), encoding="utf-8")
    # Соседний режим не должен попадать в ответ по основе «open».
    (база / "results" / "lords-05-idx-closed-rst122505.json").write_text(json.dumps({
        "request_id": "lords-05-idx-closed-rst122505", "status": "ok",
        "outcome": {"status": "applied"},
        "started_at": "2026-10-04T12:26:00+00:00"}), encoding="utf-8")

    последняя, все = q.последняя_заявка("lords-05-idx-open", база=база)
    assert последняя == "lords-05-idx-open-rep123904", последняя
    assert все == ["lords-05-idx-open", "lords-05-idx-open-rep123904"], все


def test_последняя_заявка_без_результатов_отдаёт_основу(база):
    последняя, все = q.последняя_заявка("lords-05-idx-open", база=база)
    assert последняя == "lords-05-idx-open"
    assert все == []


def test_инструмент_журнала_показывает_исполнившую_заявку():
    """Исправление бесполезно, если инструмент о нём не знает."""
    текст = pathlib.Path("factory/qwen/mcp.py").read_text(encoding="utf-8")
    assert "последняя_заявка" in текст, (
        "indexing_journal снова называет детерминированное имя и покажет не ту "
        "заявку")


def test_результат_без_started_at_судится_по_времени_файла(tmp_path):
    """Чужой отказ прежнего исполнителя не выдаётся за ответ новой попытки.

    Измерено 2026-10-05 на yummy-08: исполнитель прежней версии отверг
    операцию `indexing-core`, которой не знал, и записал результат БЕЗ
    `started_at`. Новая попытка читала этот файл и получала чужой отказ —
    слово в слово тот же текст, по которому старую неудачу от новой не
    отличить.
    """
    import os
    import time as _time

    (tmp_path / "requests").mkdir()
    (tmp_path / "results").mkdir()
    результат = tmp_path / "results" / "проба-01.json"
    результат.write_text(json.dumps({
        "request_id": "проба-01", "status": "rejected",
        "error": "operation='indexing-core'; разрешены [...]"}),
        encoding="utf-8")
    # Файл СТАРШЕ подачи: на час назад.
    старое = _time.time() - 3600
    os.utime(результат, (старое, старое))

    подача = _time.strftime("%Y-%m-%dT%H:%M:%S+00:00", _time.gmtime())
    с = q.состояние("проба-01", база=tmp_path, не_раньше=подача)
    assert с["status"] == "queued", с
    assert с["stale_result"]["status"] == "rejected"

    # Тот же файл, но СВЕЖЕЕ подачи — ответ свой.
    свежее = _time.time() + 5
    os.utime(результат, (свежее, свежее))
    с = q.состояние("проба-01", база=tmp_path, не_раньше=подача)
    assert с["status"] == "finished", с


def test_почти_одновременный_результат_считается_своим(tmp_path):
    """Результат, записанный сразу после подачи, — СВОЙ, а не чужой.

    Время подачи берётся у часов процесса, а время файла — у файловой
    системы: это разные источники, и совпадать с точностью до миллисекунд они
    не обязаны. Измерено 2026-10-05: результат, записанный ПОСЛЕ подачи,
    получил mtime на 5,4 мс РАНЬШЕ `submitted_at`, чтение объявило свой же
    свежий результат чужим, и ожидание повисло на полный таймаут, сообщив
    «исполнитель не ответил» об успешно выполненной работе.

    Проверяется тем же порядком действий, что в бою: сначала заявка, потом
    запись результата — без подкрутки времён.
    """
    (tmp_path / "requests").mkdir()
    (tmp_path / "results").mkdir()
    заявка = q.собрать("stand-01", "", "", operation="indexing-nginx",
                       mode="OPEN")
    q.записать_атомарно(
        tmp_path / "results" / f"{заявка.request_id}.json",
        {"request_id": заявка.request_id, "status": "ok",
         "outcome": {"status": "applied", "stage": "indexing_layer_applied"}})
    с = q.состояние(заявка.request_id, база=tmp_path,
                    не_раньше=заявка.submitted_at)
    assert с["status"] == "finished", с
    assert "stale_result" not in с


def test_запас_не_прячет_результат_прошлой_попытки(tmp_path):
    """Запас покрывает грубость отметок времени, а не минуты разницы."""
    import os
    import time as _time

    (tmp_path / "requests").mkdir()
    (tmp_path / "results").mkdir()
    заявка = q.собрать("stand-01", "", "", operation="indexing-nginx",
                       mode="OPEN")
    файл = tmp_path / "results" / f"{заявка.request_id}.json"
    q.записать_атомарно(файл, {"request_id": заявка.request_id,
                               "status": "rejected",
                               "error": "отказ прошлой попытки"})
    # Ровно на запас — всё ещё свой: это граница грубости, а не давности.
    на_запас = _time.time() - q.ЗАПАС_ВРЕМЕНИ_ФАЙЛА_С + 0.5
    os.utime(файл, (на_запас, на_запас))
    assert q.состояние(заявка.request_id, база=tmp_path,
                       не_раньше=заявка.submitted_at)["status"] == "finished"
    # Минута — уже чужой.
    минуту_назад = _time.time() - 60
    os.utime(файл, (минуту_назад, минуту_назад))
    с = q.состояние(заявка.request_id, база=tmp_path,
                    не_раньше=заявка.submitted_at)
    assert с["status"] == "queued", с
    assert с["stale_result"]["error"] == "отказ прошлой попытки"


def test_написание_отметки_не_влияет_на_порядок():
    """`'…Z'` и `'…+00:00'` — одно время. Как СТРОКИ они сравниваются иначе."""
    assert '2026-10-05T15:00:00+00:00' < '2026-10-05T15:00:00Z', (
        "предпосылка теста: как строки эти отметки упорядочены неверно")
    assert q._раньше("2026-10-05T15:00:00+00:00", "2026-10-05T15:00:00Z") is False
    assert q._раньше("2026-10-05T14:00:00Z", "2026-10-05T15:00:00+00:00") is True
    # Неразбираемая отметка о порядке не говорит ничего — и «раньше» не значит.
    assert q._раньше("не время", "2026-10-05T15:00:00Z") is False
    assert q._раньше("2026-10-05T15:00:00Z", "не время") is False
