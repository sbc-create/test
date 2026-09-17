"""REQ-OPERABILITY: протокол запуска и жизненный цикл службы.

Протокол один для старта, выкладки и отката. Проверяется не то, что он
«вызывается», а то, что он различает фатальное и ограничивающее: служба,
падающая из-за одного испорченного профиля, превращает местную поломку в общую,
а служба, поднявшаяся без доступа к очереди, обманывает supervisor.
"""
import json
import threading
from pathlib import Path

import pytest

from factory.site_engine.api import startup
from factory.site_engine.api.lifecycle import Lifecycle, Notifier, watchdog_interval

REPO = Path(__file__).resolve().parents[2]


def профиль(**over):
    базовый = json.loads(
        (REPO / "config" / "site-profiles" / "lords-01.json").read_text(encoding="utf-8"))
    базовый.update(over)
    return базовый


@pytest.fixture
def корень(tmp_path):
    (tmp_path / "config" / "site-profiles").mkdir(parents=True)
    return tmp_path


def положить(корень, site_id, **over):
    путь = корень / "config" / "site-profiles" / f"{site_id}.json"
    путь.write_text(json.dumps(профиль(site_id=site_id, **over), ensure_ascii=False),
                    encoding="utf-8")
    return путь


# ---- различение фатального и ограничивающего --------------------------------

def test_без_профилей_запуск_невозможен(корень):
    отчёт = startup.run(корень, {})
    assert not отчёт.ok
    assert any(c.name == "profiles" for c in отчёт.fatal)


def test_испорченный_профиль_ограничивает_а_не_валит(корень):
    """Падать из-за одной витрины значит превращать местную поломку в общую."""
    положить(корень, "здоровая", domains=["a.test"])
    (корень / "config" / "site-profiles" / "битая.json").write_text("{не json",
                                                                    encoding="utf-8")
    отчёт = startup.run(корень, {})
    assert отчёт.ok, "служба обязана подняться"
    assert any(c.name == "profiles.readable" for c in отчёт.degraded)


def test_столкновение_доменов_фатально(корень):
    """Две витрины на одном домене — не «почти изоляция», а её отсутствие."""
    положить(корень, "первая", domains=["общий.test"])
    положить(корень, "вторая", domains=["общий.test"])
    отчёт = startup.run(корень, {})
    assert not отчёт.ok
    провал = next(c for c in отчёт.fatal if c.name == "isolation.domains")
    assert "общий.test" in провал.detail


def test_разные_домены_проходят(корень):
    положить(корень, "первая", domains=["a.test"])
    положить(корень, "вторая", domains=["b.test"])
    assert startup.run(корень, {}).ok


def test_несовместимый_контракт_ограничивает(корень):
    положить(корень, "старая", domains=["a.test"], cms_contract="99.0.0")
    отчёт = startup.run(корень, {})
    assert отчёт.ok
    assert any(c.name == "contract.incompatible" for c in отчёт.degraded)


def test_чужая_версия_схемы_профиля_ограничивает(корень):
    """Ворота миграции: движок прочитал бы поля не так, как задумал автор."""
    положить(корень, "будущая", domains=["a.test"], schema_version="9.9")
    отчёт = startup.run(корень, {})
    assert any(c.name == "profiles.schema_version" for c in отчёт.degraded)


# ---- секреты ----------------------------------------------------------------

def test_запись_без_токенов_фатальна(корень):
    """Служба принимала бы изменяющие запросы, отвергая каждый."""
    положить(корень, "витрина", domains=["a.test"])
    отчёт = startup.run(корень, {"SITE_ENGINE_CONTROL_WRITES": "1"})
    assert not отчёт.ok
    assert any(c.name == "secrets.tokens" for c in отчёт.fatal)


def test_значения_токенов_не_попадают_в_отчёт(корень):
    положить(корень, "витрина", domains=["a.test"])
    секрет = "очень-секретный-токен-12345"
    отчёт = startup.run(корень, {"SITE_ENGINE_CONTROL_WRITES": "1",
                                 "SITE_ENGINE_CONTROL_TOKENS": f"{секрет}=read"})
    целиком = json.dumps(отчёт.as_dict(), ensure_ascii=False) + отчёт.as_text()
    assert секрет not in целиком, "значение токена попало в отчёт о запуске"
    assert отчёт.ok


def test_негодный_перечень_токенов_фатален(корень):
    положить(корень, "витрина", domains=["a.test"])
    отчёт = startup.run(корень, {"SITE_ENGINE_CONTROL_WRITES": "1",
                                 "SITE_ENGINE_CONTROL_TOKENS": "t=read,опечатка"})
    assert not отчёт.ok


# ---- каталоги состояния -----------------------------------------------------

def test_недоступный_каталог_состояния_фатален(корень, monkeypatch):
    положить(корень, "витрина", domains=["a.test"])
    (корень / "queue").mkdir(parents=True, exist_ok=True)
    (корень / "queue" / "inbox").write_text("это файл, а не каталог", encoding="utf-8")
    отчёт = startup.run(корень, {})
    assert not отчёт.ok
    assert any(c.name == "state.queue" for c in отчёт.fatal)


def test_отчёт_читается_человеком(корень):
    положить(корень, "витрина", domains=["a.test"])
    текст = startup.run(корень, {}).as_text()
    assert "PASS" in текст and "итог:" in текст


# ---- жизненный цикл ---------------------------------------------------------

def test_слив_перестаёт_принимать_запросы():
    ж = Lifecycle()
    assert ж.enter()
    ж.leave()
    ж.begin_drain()
    assert not ж.enter(), "после начала слива запросы принимать нельзя"


def test_слив_дожидается_начатых():
    """Обрыв изменяющей операции оставил бы состояние, о котором клиент не узнает."""
    ж = Lifecycle(drain_timeout=5.0)
    assert ж.enter()
    ж.begin_drain()
    завершилось = threading.Event()

    def ждать():
        завершилось.set() if ж.wait_drained(timeout=3.0) else None

    поток = threading.Thread(target=ждать, daemon=True)
    поток.start()
    assert not завершилось.wait(timeout=0.3), "слив завершился, не дождавшись запроса"
    ж.leave()
    поток.join(timeout=3)
    assert завершилось.is_set()


def test_слив_не_ждёт_вечно():
    """systemd всё равно пришлёт SIGKILL: бесконечное ожидание бессмысленно."""
    ж = Lifecycle(drain_timeout=0.2)
    assert ж.enter()
    ж.begin_drain()
    assert ж.wait_drained() is False


def test_счётчик_начатых_не_уходит_в_минус():
    ж = Lifecycle()
    ж.leave()
    assert ж.inflight == 0


# ---- уведомления systemd ----------------------------------------------------

def test_без_systemd_уведомления_безвредны(monkeypatch):
    """Службу нужно уметь запускать руками для отладки."""
    monkeypatch.delenv("NOTIFY_SOCKET", raising=False)
    n = Notifier(address="")
    assert n.active is False
    assert n.ready() is False and n.watchdog() is False


def test_период_сторожа_вдвое_меньше_назначенного(monkeypatch):
    """Отметка ровно к сроку приходит после него при малейшей задержке."""
    monkeypatch.setenv("WATCHDOG_USEC", "60000000")
    assert watchdog_interval() == pytest.approx(30.0)


def test_без_назначенного_срока_сторож_не_работает(monkeypatch):
    monkeypatch.delenv("WATCHDOG_USEC", raising=False)
    assert watchdog_interval() == 0.0


def test_протокол_запуска_совпадает_у_службы_и_выкладки():
    """Отдельного облегчённого входа быть не должно.

    Скрипт выкладки и точка входа службы обязаны звать один и тот же startup.run.
    """
    скрипт = (REPO / "automation" / "host" / "deploy-control-api.sh").read_text(encoding="utf-8")
    сервер = (REPO / "factory" / "site_engine" / "api" / "server.py").read_text(encoding="utf-8")
    assert "startup.run" in скрипт, "выкладка не вызывает протокол запуска"
    assert "startup_protocol.run" in сервер, "служба не вызывает протокол запуска"
    assert скрипт.count("startup.run") >= 2, "откат обязан проходить тот же протокол"


# ---- профили только для чтения ----------------------------------------------

def test_закрытые_на_запись_профили_ограничивают_а_не_валят(корень):
    """Чтение, задания и инвалидация записи не требуют — падать не из-за чего."""
    положить(корень, "витрина", domains=["a.test"])
    каталог = корень / "config" / "site-profiles"
    прежние = каталог.stat().st_mode
    каталог.chmod(0o555)
    try:
        отчёт = startup.run(корень, {})
    finally:
        каталог.chmod(прежние)
    assert отчёт.ok, "служба обязана подняться"
    предупреждение = next(c for c in отчёт.degraded if c.name == "config.writable")
    assert предупреждение.facts["writable"] is False
