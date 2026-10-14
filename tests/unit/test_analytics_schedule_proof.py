"""Подтверждение сбора аналитики РАСПИСАНИЕМ, а не ручным прогоном.

Проверяется не «считает правильно», а четыре вида подмены:

* ручной прогон за успех расписания — день, где единственная метка вне окна,
  обязан называться неотличимым, а не пройденным;
* отдельно названный утренний артефакт за отсутствие прогона — образец имени,
  закреплённый на `.json` сразу после даты, терял файл
  `analytics-<дата>.morning-0510.json` и объявлял подтверждённый день
  неотличимым;
* прежнее расписание за нынешнее — день до смены `OnCalendar` нельзя мерить
  нынешним окном, и сравнивать нужно момент смены, а не её дату: 08.10
  расписание сменили в 16:08Z, то есть утренний прогон того дня шёл ещё по
  старому времени;
* закомментированное расписание за действующее — в юните прежнее время
  оставлено в комментарии, и разбор, не отличающий комментарий от настройки,
  взял бы именно его;
* **недописанный прогон за непроисходивший** — 13.10 таймер сработал в
  05:03:28Z, а артефакта за сутки не было и через 19 минут; по артефактам это
  читается как `НЕ ЗАПУСКАЛСЯ`, тогда как процесс сбора шёл (pid 680414, старт
  секунда в секунду с меткой таймера, состояние `S` — ожидание сети). Эти два
  исхода разделяет только чтение `/proc`.
"""
from __future__ import annotations

import datetime as _dt
import importlib.util
import os
import sys
from pathlib import Path

import pytest

КОРЕНЬ = Path(__file__).resolve().parents[2]
ИСТОЧНИК = КОРЕНЬ / "automation" / "local" / "analytics-schedule-proof.py"
UTC = _dt.timezone.utc


def _модуль():
    спец = importlib.util.spec_from_file_location("analytics_schedule_proof",
                                                  ИСТОЧНИК)
    м = importlib.util.module_from_spec(спец)
    sys.modules["analytics_schedule_proof"] = м
    спец.loader.exec_module(м)
    return м


@pytest.fixture(scope="module")
def модуль():
    return _модуль()


ЮНИТ_ТЕКСТ = """# 05:00 UTC, а не 06:10. Прежняя строка оставлена в комментарии:
# OnCalendar=*-*-* 06:10:00 UTC
[Timer]
OnCalendar=*-*-* 05:00:00 UTC
Persistent=true
RandomizedDelaySec=300
Unit=analytics-cabinet.service
"""


def test_закомментированное_расписание_не_берётся(модуль):
    начало, задержка = модуль.окно_юнита(ЮНИТ_ТЕКСТ)
    assert начало == _dt.time(5, 0, 0), "взято время из комментария"
    assert задержка == 300


def test_без_строки_расписания_окно_не_выдумывается(модуль):
    начало, задержка = модуль.окно_юнита("[Timer]\nPersistent=true\n")
    assert начало is None
    assert задержка == 0


def _сутки(часы, минуты, секунды=0, день=(2026, 10, 12), имя=None):
    д = _dt.date(*день)
    м = _dt.datetime(*день, часы, минуты, секунды, tzinfo=UTC)
    return д, [(м, имя or f"analytics-{д}.json")]


def test_метка_в_окне_подтверждает(модуль):
    день, записи = _сутки(5, 7, 44)
    код, причина = модуль.исход(день, записи, _dt.time(5, 0), 1200,
                                _dt.datetime(2026, 10, 13, 4, 0, tzinfo=UTC))
    assert код == модуль.ПОДТВЕРЖДЁН
    assert "05:07:44Z" in причина


def test_одна_поздняя_метка_не_проходит_за_расписание(модуль):
    день, записи = _сутки(10, 11, 27)
    код, причина = модуль.исход(день, записи, _dt.time(5, 0), 1200,
                                _dt.datetime(2026, 10, 13, 4, 0, tzinfo=UTC))
    assert код == модуль.НЕОТЛИЧИМО, "ручной прогон зачтён за прогон по расписанию"
    assert код != модуль.НЕ_ЗАПУСКАЛСЯ, "неотличимое выдано за доказанный провал"
    assert "10:11:27Z" in причина


def test_метка_раньше_окна_называется_отдельно(модуль):
    день, записи = _сутки(3, 0)
    код, причина = модуль.исход(день, записи, _dt.time(5, 0), 1200,
                                _dt.datetime(2026, 10, 13, 4, 0, tzinfo=UTC))
    assert код == модуль.НЕОТЛИЧИМО
    assert "РАНЬШЕ" in причина


def test_отдельно_названный_утренний_файл_подтверждает_день(модуль):
    """Образец имени, закреплённый на `.json` сразу после даты, терял этот файл."""
    д = _dt.date(2026, 10, 10)
    записи = [
        (_dt.datetime(2026, 10, 10, 5, 10, 49, tzinfo=UTC),
         "analytics-2026-10-10.morning-0510.json"),
        (_dt.datetime(2026, 10, 10, 11, 9, 5, tzinfo=UTC),
         "analytics-2026-10-10.json"),
    ]
    код, причина = модуль.исход(д, записи, _dt.time(5, 0), 1200,
                                _dt.datetime(2026, 10, 13, 4, 0, tzinfo=UTC))
    assert код == модуль.ПОДТВЕРЖДЁН
    assert "morning-0510" in причина
    assert "записей за день: 2" in причина


def test_образец_имени_ловит_именованный_вариант(модуль, tmp_path):
    (tmp_path / "analytics-2026-10-10.json").write_text("{}")
    (tmp_path / "analytics-2026-10-10.morning-0510.json").write_text("{}")
    (tmp_path / "metrika-2026-10-11-attempt.csv").write_text("x")
    (tmp_path / "analytics.json").write_text("{}")
    по_дням = модуль.сутки_артефактов(tmp_path)
    assert list(по_дням) == [_dt.date(2026, 10, 10)]
    assert len(по_дням[_dt.date(2026, 10, 10)]) == 2, "именованный вариант потерян"


def test_день_до_смены_расписания_не_мерится_нынешним_окном(модуль):
    смена = _dt.datetime(2026, 10, 8, 16, 8, 14, tzinfo=UTC)
    день, записи = _сутки(6, 13, 0, день=(2026, 10, 7))
    код, причина = модуль.исход(день, записи, _dt.time(5, 0), 1200,
                                _dt.datetime(2026, 10, 13, 4, 0, tzinfo=UTC),
                                смена)
    assert код == модуль.ДРУГОЕ_РАСПИСАНИЕ
    assert модуль.НЕ_ИЗМЕРЕНО in причина


def test_утро_дня_смены_идёт_по_прежнему_расписанию(модуль):
    """Сравнивается момент смены, а не её дата: 08.10 сменили в 16:08Z."""
    смена = _dt.datetime(2026, 10, 8, 16, 8, 14, tzinfo=UTC)
    день, записи = _сутки(6, 19, 44, день=(2026, 10, 8))
    код, _ = модуль.исход(день, записи, _dt.time(5, 0), 1200,
                          _dt.datetime(2026, 10, 13, 4, 0, tzinfo=UTC), смена)
    assert код == модуль.ДРУГОЕ_РАСПИСАНИЕ, "утро дня смены измерено новым окном"


def test_вечер_дня_смены_уже_по_новому_расписанию(модуль):
    смена = _dt.datetime(2026, 10, 8, 4, 0, 0, tzinfo=UTC)
    день, записи = _сутки(5, 3, 0, день=(2026, 10, 8))
    код, _ = модуль.исход(день, записи, _dt.time(5, 0), 1200,
                          _dt.datetime(2026, 10, 13, 4, 0, tzinfo=UTC), смена)
    assert код == модуль.ПОДТВЕРЖДЁН


def test_нет_записи_и_окно_закрыто_это_провал(модуль):
    код, причина = модуль.исход(_dt.date(2026, 10, 11), [], _dt.time(5, 0), 1200,
                                _dt.datetime(2026, 10, 13, 4, 0, tzinfo=UTC))
    assert код == модуль.НЕ_ЗАПУСКАЛСЯ
    assert "05:20Z" in причина


def test_нет_записи_и_окно_не_наступило_это_не_провал(модуль):
    код, _ = модуль.исход(_dt.date(2026, 10, 13), [], _dt.time(5, 0), 1200,
                          _dt.datetime(2026, 10, 13, 4, 40, tzinfo=UTC))
    assert код == модуль.ЕЩЁ_НЕ_СРОК, "ещё не наступивший срок записан в провал"


def test_без_снимков_смена_не_выдумывается(модуль, tmp_path):
    юнит = tmp_path / "analytics-cabinet.timer"
    юнит.write_text(ЮНИТ_ТЕКСТ)
    когда, пояснение = модуль.расписание_в_силе_с(юнит)
    assert когда is None
    assert "снимков" in пояснение


def test_снимок_без_разборчивой_метки_называется_а_не_молчит(модуль, tmp_path):
    юнит = tmp_path / "analytics-cabinet.timer"
    юнит.write_text(ЮНИТ_ТЕКСТ)
    (tmp_path / "analytics-cabinet.timer.before-manual").write_text(ЮНИТ_ТЕКСТ)
    когда, пояснение = модуль.расписание_в_силе_с(юнит)
    assert когда is None
    assert "разборчивой метки" in пояснение


def test_берётся_последний_из_нескольких_снимков(модуль, tmp_path):
    юнит = tmp_path / "analytics-cabinet.timer"
    юнит.write_text(ЮНИТ_ТЕКСТ)
    for метка in ("20261008T123558Z", "20261008T160814Z"):
        (tmp_path / f"analytics-cabinet.timer.before-seo-regular-{метка}").write_text("x")
    когда, пояснение = модуль.расписание_в_силе_с(юнит)
    assert когда == _dt.datetime(2026, 10, 8, 16, 8, 14, tzinfo=UTC)
    assert "160814Z" in пояснение


def test_юнит_без_связи_с_target_это_отказ(модуль, tmp_path, capsys):
    юнит = tmp_path / "analytics-cabinet.timer"
    юнит.write_text(ЮНИТ_ТЕКСТ)
    артефакты = tmp_path / "analytics"
    артефакты.mkdir()
    (артефакты / "analytics-2026-10-12.json").write_text("{}")
    код = модуль.главная(["--unit", str(юнит),
                          "--wants", str(tmp_path / "нет-симлинка"),
                          "--stamp", str(tmp_path / "нет-метки"),
                          "--artifacts", str(артефакты)])
    напечатано = capsys.readouterr().out
    assert код == 2
    assert "НЕТ — юнит не запускается" in напечатано
    assert модуль.НЕ_ИЗМЕРЕНО in напечатано, "недоступная метка выдана за измеренную"


def test_нечитаемый_юнит_не_выдаётся_за_успех(модуль, tmp_path, capsys):
    код = модуль.главная(["--unit", str(tmp_path / "нет-юнита")])
    assert код == 2
    assert модуль.НЕ_ИЗМЕРЕНО in capsys.readouterr().out

def _проц(tmp_path, *, btime: int, записи: dict[int, tuple[str, int]]) -> Path:
    """Поддельный /proc: общий `stat` с `btime` и каталоги процессов.

    `записи` — pid → (командная строка, поле 22 в тиках).
    """
    корень = tmp_path / "proc"
    корень.mkdir()
    (корень / "stat").write_text(
        f"cpu  1 2 3\nbtime {btime}\nprocesses 42\n", encoding="utf-8")
    for pid, (команда, тики) in записи.items():
        д = корень / str(pid)
        д.mkdir()
        (д / "cmdline").write_bytes(команда.replace(" ", "\0").encode())
        поля = ["0"] * 52
        поля[0] = str(pid)
        поля[1] = "(python3)"
        поля[2] = "S"
        поля[21] = str(тики)
        (д / "stat").write_text(" ".join(поля), encoding="utf-8")
    # Посторонние записи, которые не должны мешать.
    (корень / "uptime").write_text("1000.0 900.0", encoding="utf-8")
    (корень / "self").mkdir()
    return корень


def test_идущий_прогон_находится_со_своим_моментом_старта(модуль, tmp_path):
    корень = _проц(tmp_path, btime=1_760_000_000,
                   записи={4242: ("python3 -m seo_operator.cli analytics-collect "
                                  "--json --out /x.json", 12_345)})
    найдено, _ = модуль.прогоны_сбора(корень, свои=())
    assert len(найдено) == 1
    pid, когда = найдено[0]
    assert pid == 4242
    ожидаемо = _dt.datetime.fromtimestamp(1_760_000_000 + 123.45, tz=UTC)
    assert abs((когда - ожидаемо).total_seconds()) < 1


def test_чужой_процесс_за_сбор_не_считается(модуль, tmp_path):
    корень = _проц(tmp_path, btime=1_760_000_000,
                   записи={7: ("python3 -m pytest tests", 100)})
    найдено, пояснение = модуль.прогоны_сбора(корень, свои=())
    assert найдено == []
    assert "analytics-collect" in пояснение, "признак поиска не назван"


def test_без_btime_момент_старта_не_выдумывается(модуль, tmp_path):
    корень = tmp_path / "proc"
    корень.mkdir()
    (корень / "stat").write_text("cpu 1 2 3\n", encoding="utf-8")
    найдено, пояснение = модуль.прогоны_сбора(корень, свои=())
    assert найдено == []
    assert модуль.НЕ_ИЗМЕРЕНО in пояснение


def test_идущий_прогон_снимает_вердикт_не_запускался(модуль, tmp_path, capsys):
    """Главная причина этой стадии: окно закрылось, а прогон ещё идёт."""
    юнит = tmp_path / "analytics-cabinet.timer"
    юнит.write_text(ЮНИТ_ТЕКСТ)
    wants = tmp_path / "wants"
    wants.write_text("x")
    артефакты = tmp_path / "analytics"
    артефакты.mkdir()
    (артефакты / "analytics-2026-10-01.json").write_text("{}")
    корень = _проц(tmp_path, btime=1_760_000_000,
                   записи={99: ("python3 -m seo_operator.cli analytics-collect", 1)})
    код = модуль.главная(["--unit", str(юнит), "--wants", str(wants),
                          "--stamp", str(tmp_path / "нет"), "--days", "1",
                          "--artifacts", str(артефакты), "--proc", str(корень)])
    напечатано = capsys.readouterr().out
    assert "прогон ИДЁТ прямо сейчас: pid 99" in напечатано
    assert модуль.НЕ_ЗАПУСКАЛСЯ not in напечатано, "недописанный прогон назван провалом"
    assert код != 1 or модуль.ЕЩЁ_НЕ_СРОК in напечатано


def test_без_идущего_прогона_так_и_сказано(модуль, tmp_path, capsys):
    юнит = tmp_path / "analytics-cabinet.timer"
    юнит.write_text(ЮНИТ_ТЕКСТ)
    wants = tmp_path / "wants"
    wants.write_text("x")
    артефакты = tmp_path / "analytics"
    артефакты.mkdir()
    (артефакты / "analytics-2026-10-01.json").write_text("{}")
    корень = _проц(tmp_path, btime=1_760_000_000, записи={})
    модуль.главная(["--unit", str(юнит), "--wants", str(wants),
                    "--stamp", str(tmp_path / "нет"), "--days", "1",
                    "--artifacts", str(артефакты), "--proc", str(корень)])
    напечатано = capsys.readouterr().out
    assert "идущих прогонов не найдено" in напечатано

def test_одной_подстроки_для_зачёта_не_хватает(модуль, tmp_path):
    """Измерено 13.10: мой же разбор /proc попал в собственный список.

    Командная строка содержала слово `analytics-collect`, и признак из одной
    подстроки отвечал на вопрос «встречается ли слово», а не «идёт ли прогон».
    """
    корень = _проц(tmp_path, btime=1_760_000_000, записи={
        11: ("python3 -c разбор-с-текстом-analytics-collect-внутри", 100),
        12: ("python3 -m seo_operator.cli analytics-collect --json", 200),
    })
    найдено, _ = модуль.прогоны_сбора(корень, свои=())
    assert [pid for pid, _ in найдено] == [12], "признак поймал посторонний процесс"


def test_свой_процесс_в_перечень_не_попадает(модуль, tmp_path):
    """Инструмент, который находит себя, печатает «прогон идёт» всегда."""
    корень = _проц(tmp_path, btime=1_760_000_000, записи={
        21: ("python3 -m seo_operator.cli analytics-collect", 100),
        22: ("python3 -m seo_operator.cli analytics-collect", 200),
    })
    найдено, пояснение = модуль.прогоны_сбора(корень, свои=(21,))
    assert [pid for pid, _ in найдено] == [22]
    assert "21" in пояснение, "исключённые процессы не названы"


def test_по_умолчанию_исключается_свой_pid(модуль, tmp_path):
    import os

    корень = _проц(tmp_path, btime=1_760_000_000, записи={
        os.getpid(): ("python3 -m seo_operator.cli analytics-collect", 100),
    })
    найдено, пояснение = модуль.прогоны_сбора(корень)
    assert найдено == []
    assert str(os.getpid()) in пояснение

def _юнит_и_окружение(tmp_path, *, артефакты: dict[str, int], метка: float | None):
    """Собрать юнит, каталог артефактов и метку срабатывания для прогона главной."""
    юнит = tmp_path / "analytics-cabinet.timer"
    юнит.write_text(ЮНИТ_ТЕКСТ)
    wants = tmp_path / "wants"
    wants.write_text("x")
    каталог = tmp_path / "analytics"
    каталог.mkdir()
    for имя, когда in артефакты.items():
        ф = каталог / имя
        ф.write_text("{}")
        os.utime(ф, (когда, когда))
    stamp = tmp_path / "stamp"
    if метка is not None:
        stamp.write_text("x")
        os.utime(stamp, (метка, метка))
    пусто = _проц(tmp_path, btime=1_760_000_000, записи={})
    return юнит, wants, каталог, stamp, пусто


def _сегодня_и_окно() -> tuple[_dt.date, _dt.datetime]:
    """Сутки для прогона с `--days 1` — ТЕКУЩИЕ, а не записанные в код.

    Инструмент разбирает последние N суток от сегодняшнего дня
    (`дни = [сейчас.date() - ...]`). Тесты окна были написаны 13 октября и
    закрепили эту дату числом, поэтому на следующий же день строка суток в
    выводе не находилась вовсе, и падение выглядело как дефект инструмента,
    хотя сломались сами проверки. Сценарий окна от календарной даты не
    зависит: важна только ширина окна и смещения внутри него.
    """
    день = _dt.datetime.now(tz=UTC).date()
    return день, _dt.datetime(день.year, день.month, день.day, 5, 0, tzinfo=UTC)


def test_окно_уже_сбора_называется_отдельной_строкой(модуль, tmp_path, capsys):
    """13.10 прогон шёл 25+ мин: при ширине 15 мин артефакт вышел бы за окно."""
    день, открылось = _сегодня_и_окно()
    срабатывание = открылось + _dt.timedelta(minutes=3, seconds=28)
    артефакт = открылось + _dt.timedelta(minutes=34)
    юнит, wants, каталог, stamp, проц = _юнит_и_окружение(
        tmp_path,
        артефакты={f"analytics-{день}.json": артефакт.timestamp()},
        метка=срабатывание.timestamp())
    модуль.главная(["--unit", str(юнит), "--wants", str(wants),
                    "--stamp", str(stamp), "--days", "1",
                    "--artifacts", str(каталог), "--proc", str(проц)])
    напечатано = capsys.readouterr().out
    assert "ПРЕДЕЛ ОКНА" in напечатано
    assert "нужно не меньше 34 мин" in напечатано
    # Проверять «ПОДТВЕРЖДЁН нет в выводе» нельзя: это слово стоит в заголовке
    # инструмента. Смотрю строку самих суток.
    строка = next(с for с in напечатано.splitlines()
                  if с.startswith(f"  {день}  "))
    assert модуль.НЕОТЛИЧИМО in строка, f"вердикт суток подменён: {строка}"
    assert модуль.ПОДТВЕРЖДЁН not in строка


def test_предел_окна_молчит_когда_артефакт_внутри_окна(модуль, tmp_path, capsys):
    день, открылось = _сегодня_и_окно()
    юнит, wants, каталог, stamp, проц = _юнит_и_окружение(
        tmp_path,
        артефакты={f"analytics-{день}.json":
                   (открылось + _dt.timedelta(minutes=7)).timestamp()},
        метка=(открылось + _dt.timedelta(minutes=3)).timestamp())
    модуль.главная(["--unit", str(юнит), "--wants", str(wants),
                    "--stamp", str(stamp), "--days", "1",
                    "--artifacts", str(каталог), "--proc", str(проц)])
    напечатано = capsys.readouterr().out
    assert "ПРЕДЕЛ ОКНА" not in напечатано
    assert модуль.ПОДТВЕРЖДЁН in напечатано


def test_предел_окна_молчит_когда_таймер_не_срабатывал_в_окне(модуль, tmp_path, capsys):
    """Метка вне окна — значит это не затянувшийся прогон по расписанию."""
    день, открылось = _сегодня_и_окно()
    юнит, wants, каталог, stamp, проц = _юнит_и_окружение(
        tmp_path,
        артефакты={f"analytics-{день}.json":
                   (открылось + _dt.timedelta(minutes=40)).timestamp()},
        метка=(открылось + _dt.timedelta(hours=5)).timestamp())
    модуль.главная(["--unit", str(юнит), "--wants", str(wants),
                    "--stamp", str(stamp), "--days", "1",
                    "--artifacts", str(каталог), "--proc", str(проц)])
    напечатано = capsys.readouterr().out
    assert "ПРЕДЕЛ ОКНА" not in напечатано


def test_длительность_идущего_прогона_печатается(модуль, tmp_path, capsys):
    юнит = tmp_path / "analytics-cabinet.timer"
    юнит.write_text(ЮНИТ_ТЕКСТ)
    wants = tmp_path / "wants"
    wants.write_text("x")
    каталог = tmp_path / "analytics"
    каталог.mkdir()
    (каталог / "analytics-2026-10-01.json").write_text("{}")
    # Старт процесса — 10 минут назад от текущего момента.
    uptime = float(Path("/proc/uptime").read_text().split()[0])
    btime = int(_dt.datetime.now(tz=UTC).timestamp() - uptime)
    тики = int((uptime - 600) * 100)
    проц = _проц(tmp_path, btime=btime,
                 записи={31337: ("python3 -m seo_operator.cli analytics-collect",
                                 max(тики, 0))})
    модуль.главная(["--unit", str(юнит), "--wants", str(wants),
                    "--stamp", str(tmp_path / "нет"), "--days", "1",
                    "--artifacts", str(каталог), "--proc", str(проц)])
    напечатано = capsys.readouterr().out
    assert "прогон ИДЁТ прямо сейчас: pid 31337" in напечатано
    assert "идёт 10 мин" in напечатано
