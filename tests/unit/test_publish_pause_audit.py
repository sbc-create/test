"""Пауза публикаций: ноль нарушений при нуле знания — не зелёный результат.

Повод — моя собственная ошибка 12.10, из-за которой инструмент и появился.
Событие `task_result` адреса НЕ содержит: его поля `at, attempts, event, gate,
next_attempt_at, outcome, owner, queue_status, status_after, status_before,
task_id, work_id`. Первая проба спрашивала адрес у него, все 69 успехов
попадали в корзину «адрес не указан», а счётчик считал эту корзину
распознанной и печатал «нарушений паузы 0» — то есть выдавал незнание за
доказательство.

Поэтому тесты закрепляют три вещи:

* адрес берётся из событий, которые его несут (`task_claimed`,
  `task_registered`, `task_reopened`, `task_published`), по `task_id`;
* соответствие ищется по ВСЕЙ истории, а не только внутри окна: задание могли
  выдать раньше окна и закрыть внутри него;
* если распознанных успехов нет вовсе, исход отдельный (код 2), и в выводе
  прямо сказано, что это не доказательство;
* если список приостановленных домéнов пуст, исход тоже отдельный (код 2).

Последнее закреплено 13.10 и **заменило прежнюю проверку**, которая требовала
обратного: `test_без_списка_паузы_инструмент_просто_считает` утверждала «без
`--paused` нарушать нечего, и код обязан быть нулевым». Это и была вторая
дыра того же рода: при пустом списке «на приостановленных домéнах: 0»
получается тождественно, сравнивать не с чем, а вывод выглядел зелёным — и
именно в таком виде инструмент был однажды запущен, а его вывод попал в отчёт.
Проверка не удалена, а исправлена: прежнее утверждение было неверным, и
причина записана здесь.

Сеть и живой журнал не используются: журнал подставляется файлом.
"""
from __future__ import annotations

import datetime as dt
import importlib.util
import io
import json
from contextlib import redirect_stdout
from pathlib import Path

import pytest

КОРЕНЬ = Path(__file__).resolve().parents[2]
ИСТОЧНИК = КОРЕНЬ / "automation" / "local" / "publish-pause-audit.py"
ПАУЗА = ["zonafilm.space", "lordfilm47.space"]


def _модуль():
    спец = importlib.util.spec_from_file_location("publish_pause_audit",
                                                  ИСТОЧНИК)
    м = importlib.util.module_from_spec(спец)
    спец.loader.exec_module(м)
    return м


@pytest.fixture(scope="module")
def м():
    return _модуль()


def _сейчас(минут_назад: int = 0) -> str:
    т = dt.datetime.now(dt.timezone.utc) - dt.timedelta(minutes=минут_назад)
    return т.strftime("%Y-%m-%dT%H:%M:%SZ")


def журнал(tmp_path: Path, события: list[dict]) -> Path:
    п = tmp_path / "queue_events.jsonl"
    п.write_text("".join(json.dumps(с, ensure_ascii=False) + "\n"
                         for с in события), encoding="utf-8")
    return п


def _запуск(м, путь: Path, *, часов: float = 24.0, пауза=None, объявление=None):
    буфер = io.StringIO()
    аргв = ["--journal", str(путь), "--hours", str(часов)]
    if объявление is not None:
        аргв += ["--paused-from", str(объявление)]
    for д in (ПАУЗА if пауза is None else пауза):
        аргв += ["--paused", д]
    with redirect_stdout(буфер):
        код = м.главное(аргв)
    return код, буфер.getvalue()


def test_успех_на_приостановленном_домене_виден(м, tmp_path):
    п = журнал(tmp_path, [
        {"event": "task_claimed", "at": _сейчас(70), "task_id": "t1",
         "canonical_url": "https://zonafilm.space/title/x/"},
        {"event": "task_result", "at": _сейчас(60), "task_id": "t1",
         "outcome": "TEXT_WRITTEN"},
    ])
    код, вывод = _запуск(м, п)
    assert код == 1
    assert "ДОМЕН НА ПАУЗЕ" in вывод
    assert "zonafilm.space" in вывод


def test_успех_на_разрешённом_домене_не_тревога(м, tmp_path):
    п = журнал(tmp_path, [
        {"event": "task_claimed", "at": _сейчас(70), "task_id": "t1",
         "canonical_url": "https://yummyani.site/anime/x/"},
        {"event": "task_result", "at": _сейчас(60), "task_id": "t1",
         "outcome": "TEXT_WRITTEN"},
    ])
    код, вывод = _запуск(м, п)
    assert код == 0
    assert "на приостановленных домена: 0" in вывод


def test_адрес_ищется_по_всей_истории_а_не_в_окне(м, tmp_path):
    """Задание выдали позавчера, закрыли час назад — адрес обязан найтись."""
    п = журнал(tmp_path, [
        {"event": "task_claimed", "at": _сейчас(60 * 48), "task_id": "t1",
         "canonical_url": "https://zonafilm.space/title/x/"},
        {"event": "task_result", "at": _сейчас(60), "task_id": "t1",
         "outcome": "TEXT_WRITTEN"},
    ])
    код, вывод = _запуск(м, п)
    assert код == 1, "адрес из старого события обязан учитываться"
    assert "успехов без распознанного адреса: 0" in вывод


def test_незнание_не_выдаётся_за_доказательство(м, tmp_path):
    """Главный инвариант: ноль нарушений при нуле знания — код 2, не 0.

    Ровно эта ошибка и была допущена: успехи без адреса считались
    распознанными, и вывод «нарушений 0» читался как соблюдение паузы.
    """
    п = журнал(tmp_path, [
        {"event": "task_result", "at": _сейчас(60), "task_id": "t1",
         "outcome": "TEXT_WRITTEN"},
    ])
    код, вывод = _запуск(м, п)
    assert код == 2
    assert "НЕ доказательство" in вывод
    assert "успехов без распознанного адреса: 1" in вывод


def test_успех_на_паузе_не_объявляется_нарушением(м, tmp_path):
    """Инструмент сообщает факт и говорит, чего он НЕ доказывает.

    Успех на приостановленном домене мог предшествовать объявлению паузы, а
    публикация могла и не дойти до витрины. Вывод обязан это оговаривать,
    иначе цифра читается как обвинение.
    """
    п = журнал(tmp_path, [
        {"event": "task_claimed", "at": _сейчас(70), "task_id": "t1",
         "canonical_url": "https://zonafilm.space/title/x/"},
        {"event": "task_result", "at": _сейчас(60), "task_id": "t1",
         "outcome": "TEXT_WRITTEN"},
    ])
    _код, вывод = _запуск(м, п)
    assert "ещё не нарушение" in вывод


def test_site_используется_когда_адреса_нет(м, tmp_path):
    п = журнал(tmp_path, [
        {"event": "task_claimed", "at": _сейчас(70), "task_id": "t1",
         "site": "ZonaFilm.Space"},
        {"event": "task_result", "at": _сейчас(60), "task_id": "t1",
         "outcome": "TEXT_WRITTEN"},
    ])
    код, _вывод = _запуск(м, п)
    assert код == 1, "имя сайта тоже определяет домен, и регистр не мешает"


def test_отказ_успехом_не_считается(м, tmp_path):
    п = журнал(tmp_path, [
        {"event": "task_claimed", "at": _сейчас(70), "task_id": "t1",
         "canonical_url": "https://zonafilm.space/title/x/"},
        {"event": "task_result", "at": _сейчас(60), "task_id": "t1",
         "outcome": "SOURCES_MISSING"},
    ])
    код, вывод = _запуск(м, п)
    assert код == 0
    assert "на приостановленных домена: 0" in вывод


def test_правка_не_нужна_считается_успехом(м, tmp_path):
    """`NO_CHANGE_NEEDED` — доведённая работа, и на паузе она тоже значима."""
    п = журнал(tmp_path, [
        {"event": "task_claimed", "at": _сейчас(70), "task_id": "t1",
         "canonical_url": "https://lordfilm47.space/title/x/"},
        {"event": "task_result", "at": _сейчас(60), "task_id": "t1",
         "outcome": "NO_CHANGE_NEEDED"},
    ])
    assert _запуск(м, п)[0] == 1


def test_событие_вне_окна_не_считается(м, tmp_path):
    п = журнал(tmp_path, [
        {"event": "task_claimed", "at": _сейчас(60 * 50), "task_id": "t1",
         "canonical_url": "https://zonafilm.space/title/x/"},
        {"event": "task_result", "at": _сейчас(60 * 49), "task_id": "t1",
         "outcome": "TEXT_WRITTEN"},
    ])
    код, вывод = _запуск(м, п, часов=24.0)
    assert код == 0
    assert "на приостановленных домена: 0" in вывод


def test_пустой_журнал_это_отказ(м, tmp_path):
    п = tmp_path / "нет.jsonl"
    assert м.главное(["--journal", str(п)]) == 2


def test_мусор_в_журнале_не_валит_разбор(м, tmp_path):
    п = tmp_path / "queue_events.jsonl"
    п.write_text("не json\n{битый\n"
                  + json.dumps({"event": "task_claimed", "at": _сейчас(70),
                                "task_id": "t1",
                                "canonical_url": "https://zonafilm.space/t/x/"})
                  + "\n"
                  + json.dumps({"event": "task_result", "at": _сейчас(60),
                                "task_id": "t1", "outcome": "TEXT_WRITTEN"})
                  + "\n", encoding="utf-8")
    assert _запуск(м, п)[0] == 1


def test_json_вывод_разбирается(м, tmp_path):
    п = журнал(tmp_path, [
        {"event": "task_claimed", "at": _сейчас(70), "task_id": "t1",
         "canonical_url": "https://zonafilm.space/title/x/"},
        {"event": "task_result", "at": _сейчас(60), "task_id": "t1",
         "outcome": "TEXT_WRITTEN"},
    ])
    буфер = io.StringIO()
    with redirect_stdout(буфер):
        м.главное(["--journal", str(п), "--paused", "zonafilm.space",
                   "--json"])
    данные = json.loads(буфер.getvalue())
    assert данные["распознано"] == 1
    assert данные["на_паузе"][0]["домен"] == "zonafilm.space"


def test_пустой_список_паузы_это_отказ(м, tmp_path):
    """Без списка сравнивать не с чем — зелёного исхода здесь быть не может."""
    п = журнал(tmp_path, [
        {"event": "task_claimed", "at": _сейчас(70), "task_id": "t1",
         "canonical_url": "https://zonafilm.space/title/x/"},
        {"event": "task_result", "at": _сейчас(60), "task_id": "t1",
         "outcome": "TEXT_WRITTEN"},
    ])
    пусто = tmp_path / "без-объявления.py"
    пусто.write_text("ДРУГОЕ = 1\n", encoding="utf-8")
    код, вывод = _запуск(м, п, пауза=[], объявление=пусто)
    assert код == 2, "пустой список паузы дал не-отказ"
    assert "ОТКАЗ" in вывод
    assert "сравнивать не с чем" in вывод


def test_список_паузы_берётся_из_объявления(м, tmp_path):
    """Имена не вписаны в инструмент: он читает их из объявления редактора."""
    объявление = tmp_path / "editor_run.py"
    объявление.write_text(
        'PAUSED_PUBLISH = {\n'
        '    d: "причина"\n'
        '    for d in ("zonafilm.space", "lordserial33.biz")\n'
        '}\n', encoding="utf-8")
    множество, откуда = м.пауза_из_объявления(объявление)
    assert множество == {"zonafilm.space", "lordserial33.biz"}
    assert "editor_run.py" in откуда


def test_прямой_литерал_тоже_разбирается(м, tmp_path):
    объявление = tmp_path / "editor_run.py"
    объявление.write_text('PAUSED_PUBLISH = {"a.site", "b.site"}\n',
                          encoding="utf-8")
    множество, _ = м.пауза_из_объявления(объявление)
    assert множество == {"a.site", "b.site"}


def test_нечитаемое_объявление_называет_причину(м, tmp_path):
    множество, откуда = м.пауза_из_объявления(tmp_path / "нет-файла.py")
    assert множество == set()
    assert "не прочитано" in откуда


def test_объявление_без_нужного_имени_называет_причину(м, tmp_path):
    объявление = tmp_path / "editor_run.py"
    объявление.write_text("ДРУГОЕ = {'a.site'}\n", encoding="utf-8")
    множество, откуда = м.пауза_из_объявления(объявление)
    assert множество == set()
    assert "нет присваивания" in откуда


def test_список_паузы_печатается_в_выводе(м, tmp_path):
    """Читатель должен видеть, с чем сравнивали, а не верить на слово."""
    п = журнал(tmp_path, [
        {"event": "task_claimed", "at": _сейчас(70), "task_id": "t1",
         "canonical_url": "https://yummyani.site/title/x/"},
        {"event": "task_result", "at": _сейчас(60), "task_id": "t1",
         "outcome": "TEXT_WRITTEN"},
    ])
    код, вывод = _запуск(м, п)
    assert код == 0
    assert "приостановленных домéнов: 2" in вывод
    for д in ПАУЗА:
        assert д in вывод
