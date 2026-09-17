"""Долговечное состояние индексации: revision, CAS, ABA, отказы и восстановление.

Дефект, ради которого всё это написано: решение «открыт ли сайт для поиска»
жило в трёх местах сразу, совпадало случайно, и обычная выкладка возвращала
посредника, безусловно закрывающего витрину. Живой сайт с поисковым трафиком
закрывался молча.

Здесь проверяется, что решение теперь одно, живёт в общем Action Ledger и
переживает всё, что с системой происходит штатно: выкладку, перезапуск, откат,
падение в любой точке и недоступность хранилища.

Ни одной записи в production: каждый тест работает на своей эфемерной базе.
"""

from __future__ import annotations

import contextlib
import json
import sqlite3
import threading
import uuid
from pathlib import Path

import pytest

from factory.site_engine.audit import indexing as idx
from factory.site_engine.audit import indexing_contract as контракт
from factory.site_engine.audit import ledger_store as store

#: Исключения ловятся как ``idx.LedgerError`` — то есть ровно тот класс,
#: который возбуждает проверяемый код. Соседние suite этого каталога поднимают
#: службу из ВЫЛОЖЕННОГО релиза, и при совместном прогоне
#: ``factory.site_engine.audit.ledger_store`` может оказаться другим объектом
#: модуля. Тогда ``pytest.raises(store.LedgerError)`` не перехватывает
#: ``release.LedgerError``, и тест падает на верном поведении.

ДЕВЯТЬ = {
    "lords-01", "lords-02", "lords-03",
    "yummyani-site", "yummyani-org", "yummyani-biz",
    "zona-01", "animedia-01", "animedia-02",
}
ОТКРЫТЫЙ = "yummyani-site"


# --- стенд ---------------------------------------------------------------------

def новая_база(путь: str | Path = ":memory:") -> sqlite3.Connection:
    соед = store.открыть(путь)
    idx.подготовить(соед)
    return соед


def одобрить(соед, site_id: str, целевое: str) -> str:
    """Разрешение владельца: отдельная запись отдельного актора.

    Владелец только AUTHORIZE — исполнять он не вправе. Это и есть
    maker-checker, а не формальность.
    """
    тип = idx.ТИП_ОТКРЫТЬ if целевое == idx.OPEN else idx.ТИП_ЗАКРЫТЬ
    итог = store.append(
        соед,
        {"event_type": тип, "phase": "AUTHORIZED", "result": "SUCCESS",
         "scope": "SITE", "site_id": site_id,
         "idempotency_key": str(uuid.uuid4()), "correlation_id": "corr",
         "summary": "разрешение владельца", "occurred_at": store.сейчас()},
        producer_service="human_owner", actor_id="owner", actor_type="HUMAN",
        authority="AUTHORIZE", известные_сайты=ДЕВЯТЬ,
    )
    return итог["event_id"]


def применить(соед, site_id: str, целевое: str, *, expected_revision: int,
              approval_id: str | None = None, key: str | None = None,
              reason: str = "решение владельца",
              occurred_at: str = "2026-09-16T00:00:00.000000Z") -> dict:
    """Применить команду.

    ``occurred_at`` задан постоянным намеренно: повтор после таймаута обязан
    прислать тот же запрос целиком, включая его время. Заново проставленное
    время делает повтор другим запросом с тем же ключом.
    """
    ап = approval_id or одобрить(соед, site_id, целевое)
    команда = idx.открыть_индексацию if целевое == idx.OPEN else idx.закрыть_индексацию
    return команда(
        соед, site_id=site_id, expected_revision=expected_revision,
        approval_id=ап, reason=reason, idempotency_key=key or str(uuid.uuid4()),
        correlation_id="corr", producer_service="architect", actor_id="integrator",
        actor_type="SERVICE", authority="EXECUTE", известные_сайты=ДЕВЯТЬ,
        occurred_at=occurred_at,
    )


@contextlib.contextmanager
def ожидать_отказ(код: str):
    """Ожидать отказ журнала с заданным кодом.

    Ловится не класс, а КОД. Соседние suite этого каталога поднимают службу из
    выложенного релиза, и при совместном прогоне
    ``factory.site_engine.audit.ledger_store`` оказывается другим объектом
    модуля: исключение, возбуждённое внутри ``append``, тогда не совпадает по
    классу с тем, что видит тест, и проверка падает на верном поведении.

    Код ошибки — и есть договор. Он не зависит от того, каким путём загрузился
    модуль, и именно на него смотрит HTTP-слой.
    """
    try:
        yield
    except Exception as ош:          # noqa: BLE001 — важен код, а не тип
        фактический = getattr(ош, "error_code", None)
        assert фактический == код, f"ожидался отказ {код}, получен {фактический}: {ош}"
    else:
        raise AssertionError(f"ожидался отказ {код}, но его не было")


@pytest.fixture
def соед():
    c = новая_база()
    yield c
    c.close()


# --- новый сайт ----------------------------------------------------------------

def test_новый_сайт_закрыт(соед) -> None:
    с = idx.состояние(соед, "tenth-site")
    assert с["desired_state"] == idx.CLOSED
    assert с["revision"] == 0
    assert с["registered"] is False
    assert с["reason"] == idx.БЕЗ_РЕШЕНИЯ


def test_незарегистрированный_и_недоступный_различаются(соед) -> None:
    """Разница, из-за которой закрывалась живая витрина."""
    есть = контракт.прочитать(соед)
    нет = контракт.прочитать(None)
    assert есть.provider_health == контракт.ЗДОРОВ
    assert нет.provider_health == контракт.НЕДОСТУПЕН
    assert нет.release_blocked is True


# --- переживание выкладки, перезапуска и отката --------------------------------

def перезапуск(путь: Path) -> sqlite3.Connection:
    """Служба поднимается заново и читает то же хранилище."""
    return store.открыть(путь)


@pytest.mark.parametrize("целевое", [idx.OPEN, idx.CLOSED])
def test_состояние_переживает_выкладку_перезапуск_и_откат(tmp_path, целевое) -> None:
    путь = tmp_path / "ledger.sqlite3"
    c = новая_база(путь)
    применить(c, ОТКРЫТЫЙ, целевое, expected_revision=0)
    ожидаемая = idx.состояние(c, ОТКРЫТЫЙ)["revision"]
    c.close()

    # выкладка нового артефакта: код сменился, хранилище то же
    c = перезапуск(путь)
    assert idx.состояние(c, ОТКРЫТЫЙ)["desired_state"] == целевое
    assert idx.состояние(c, ОТКРЫТЫЙ)["revision"] == ожидаемая
    c.close()

    # перезапуск службы
    c = перезапуск(путь)
    assert idx.состояние(c, ОТКРЫТЫЙ)["desired_state"] == целевое
    c.close()

    # откат приложения на прежний код
    c = перезапуск(путь)
    состояние = idx.состояние(c, ОТКРЫТЫЙ)
    assert состояние["desired_state"] == целевое
    assert состояние["revision"] == ожидаемая
    c.close()


# --- монотонность, CAS и ABA ---------------------------------------------------

def test_open_close_open_монотонна(соед) -> None:
    применить(соед, ОТКРЫТЫЙ, idx.OPEN, expected_revision=0)
    применить(соед, ОТКРЫТЫЙ, idx.CLOSED, expected_revision=1)
    применить(соед, ОТКРЫТЫЙ, idx.OPEN, expected_revision=2)
    assert idx.состояние(соед, ОТКРЫТЫЙ)["revision"] == 3
    assert idx.проверить_монотонность(соед)["ok"]


def test_устаревшая_expected_revision_отклоняется(соед) -> None:
    применить(соед, ОТКРЫТЫЙ, idx.OPEN, expected_revision=0)
    with ожидать_отказ("CAS_CONFLICT"):
            применить(соед, ОТКРЫТЫЙ, idx.CLOSED, expected_revision=0)
    assert idx.состояние(соед, ОТКРЫТЫЙ)["revision"] == 1


def test_ABA_закрыт(соед) -> None:
    """OPEN rev1 → CLOSED rev2 → OPEN rev3.

    Клиент, уснувший на revision 1, видит снова OPEN — и не имеет права
    применить команду. Сравнение идёт по ревизии, а не по значению.
    """
    применить(соед, ОТКРЫТЫЙ, idx.OPEN, expected_revision=0)
    применить(соед, ОТКРЫТЫЙ, idx.CLOSED, expected_revision=1)
    применить(соед, ОТКРЫТЫЙ, idx.OPEN, expected_revision=2)
    assert idx.состояние(соед, ОТКРЫТЫЙ)["desired_state"] == idx.OPEN

    with ожидать_отказ("CAS_CONFLICT"):
            применить(соед, ОТКРЫТЫЙ, idx.CLOSED, expected_revision=1)
    assert idx.состояние(соед, ОТКРЫТЫЙ)["revision"] == 3


def test_expected_revision_обязателен(соед) -> None:
    ап = одобрить(соед, ОТКРЫТЫЙ, idx.OPEN)
    with ожидать_отказ("EXPECTED_REVISION_REQUIRED"):
            idx.открыть_индексацию(
                соед, site_id=ОТКРЫТЫЙ, expected_revision=None, approval_id=ап,
                reason="без CAS", idempotency_key=str(uuid.uuid4()),
                correlation_id="c", producer_service="architect", actor_id="i",
                actor_type="SERVICE", authority="EXECUTE", известные_сайты=ДЕВЯТЬ)


# --- идемпотентность -----------------------------------------------------------

def test_повтор_после_таймаута_не_создаёт_вторую_revision(соед) -> None:
    ап = одобрить(соед, ОТКРЫТЫЙ, idx.OPEN)
    ключ = "повтор-1"
    первый = применить(соед, ОТКРЫТЫЙ, idx.OPEN, expected_revision=0,
                       approval_id=ап, key=ключ)
    второй = применить(соед, ОТКРЫТЫЙ, idx.OPEN, expected_revision=0,
                       approval_id=ап, key=ключ)
    assert второй["idempotent_replay"] is True
    assert первый["event_id"] == второй["event_id"]
    assert idx.состояние(соед, ОТКРЫТЫЙ)["revision"] == 1
    assert len(list(соед.execute(
        "SELECT 1 FROM indexing_revision WHERE site_id=?", (ОТКРЫТЫЙ,)))) == 1


def test_тот_же_ключ_с_другим_содержимым_конфликт(соед) -> None:
    ап = одобрить(соед, ОТКРЫТЫЙ, idx.OPEN)
    применить(соед, ОТКРЫТЫЙ, idx.OPEN, expected_revision=0, approval_id=ап,
              key="k", reason="первое основание")
    with ожидать_отказ("IDEMPOTENCY_CONFLICT"):
            применить(соед, ОТКРЫТЫЙ, idx.OPEN, expected_revision=0, approval_id=ап,
                      key="k", reason="другое основание")


# --- maker-checker и полномочия ------------------------------------------------

def test_seo_не_может_исполнить_команду(соед) -> None:
    """У службы seo нет EXECUTE — это ограничение модели, а не договорённость."""
    ап = одобрить(соед, ОТКРЫТЫЙ, idx.OPEN)
    with ожидать_отказ("AUTHORITY_DENIED"):
            idx.открыть_индексацию(
                соед, site_id=ОТКРЫТЫЙ, expected_revision=0, approval_id=ап,
                reason="попытка SEO", idempotency_key=str(uuid.uuid4()),
                correlation_id="c", producer_service="seo", actor_id="seo-bot",
                actor_type="SERVICE", authority="EXECUTE", известные_сайты=ДЕВЯТЬ)


def test_без_разрешения_владельца_нельзя(соед) -> None:
    with ожидать_отказ("APPROVAL_NOT_FOUND"):
            применить(соед, ОТКРЫТЫЙ, idx.OPEN, expected_revision=0,
                      approval_id=str(uuid.uuid4()))


def test_разрешение_на_чужой_сайт_не_годится(соед) -> None:
    чужое = одобрить(соед, "yummyani-org", idx.OPEN)
    with ожидать_отказ("APPROVAL_SITE_MISMATCH"):
            применить(соед, ОТКРЫТЫЙ, idx.OPEN, expected_revision=0, approval_id=чужое)


def test_разрешение_открыть_не_является_разрешением_закрыть(соед) -> None:
    ап = одобрить(соед, ОТКРЫТЫЙ, idx.OPEN)
    with ожидать_отказ("APPROVAL_TARGET_MISMATCH"):
            применить(соед, ОТКРЫТЫЙ, idx.CLOSED, expected_revision=0, approval_id=ап)


def test_одно_разрешение_нельзя_применить_дважды(соед) -> None:
    ап = одобрить(соед, ОТКРЫТЫЙ, idx.OPEN)
    применить(соед, ОТКРЫТЫЙ, idx.OPEN, expected_revision=0, approval_id=ап)
    применить(соед, ОТКРЫТЫЙ, idx.CLOSED, expected_revision=1)
    with ожидать_отказ("APPROVAL_ALREADY_USED"):
            применить(соед, ОТКРЫТЫЙ, idx.OPEN, expected_revision=2, approval_id=ап)


def test_решение_без_основания_отклоняется(соед) -> None:
    ап = одобрить(соед, ОТКРЫТЫЙ, idx.OPEN)
    with ожидать_отказ("REASON_REQUIRED"):
            применить(соед, ОТКРЫТЫЙ, idx.OPEN, expected_revision=0,
                      approval_id=ап, reason="   ")


# --- дрейф ---------------------------------------------------------------------

def test_дрейф_не_меняет_желаемое(соед) -> None:
    применить(соед, ОТКРЫТЫЙ, idx.OPEN, expected_revision=0)
    idx.записать_дрейф(
        соед, site_id=ОТКРЫТЫЙ, observed=idx.CLOSED, desired=idx.OPEN,
        idempotency_key=str(uuid.uuid4()), correlation_id="c",
        producer_service="seo", actor_id="seo-bot", actor_type="SERVICE",
        authority="OBSERVE", известные_сайты=ДЕВЯТЬ)
    с = idx.состояние(соед, ОТКРЫТЫЙ)
    assert с["desired_state"] == idx.OPEN, "наблюдение не меняет решение"
    assert с["revision"] == 1, "дрейф не порождает ревизию"


# --- падения и восстановление --------------------------------------------------

def test_падение_внутри_проекции_не_оставляет_события(tmp_path) -> None:
    """Падение после записи события, но до проекции: откатывается всё."""
    путь = tmp_path / "l.sqlite3"
    c = новая_база(путь)
    ап = одобрить(c, ОТКРЫТЫЙ, idx.OPEN)
    было = c.execute("SELECT count(*) n FROM ledger_event").fetchone()["n"]

    def падающий(соед, тело, seq):
        raise RuntimeError("падение до фиксации")

    событие = {"event_type": idx.ТИП_ОТКРЫТЬ, "phase": "SUCCEEDED",
               "result": "SUCCESS", "scope": "SITE", "site_id": ОТКРЫТЫЙ,
               "idempotency_key": str(uuid.uuid4()), "correlation_id": "c",
               "approval_ref": ап, "occurred_at": store.сейчас()}
    with pytest.raises(RuntimeError):
        store.append(c, событие, producer_service="architect", actor_id="i",
                     actor_type="SERVICE", authority="EXECUTE",
                     известные_сайты=ДЕВЯТЬ, проекция=падающий)

    стало = c.execute("SELECT count(*) n FROM ledger_event").fetchone()["n"]
    assert стало == было, "событие не должно остаться без своей проекции"
    assert idx.состояние(c, ОТКРЫТЫЙ)["revision"] == 0
    c.close()


def test_CAS_конфликт_не_оставляет_события(соед) -> None:
    """Отклонённая команда не оставляет следа.

    Считаются события самой команды, а не все подряд: запись разрешения
    владельца законна и появляется до попытки применения.
    """
    применить(соед, ОТКРЫТЫЙ, idx.OPEN, expected_revision=0)
    # Фаза важна: разрешение владельца несёт ТОТ ЖЕ тип события, что и
    # команда, и без разделения по фазе попало бы в счёт применённых.
    команд = ("SELECT count(*) n FROM ledger_event "
              "WHERE event_type IN (?,?) AND phase='SUCCEEDED'")
    типы = (idx.ТИП_ОТКРЫТЬ, idx.ТИП_ЗАКРЫТЬ)
    было = соед.execute(команд, типы).fetchone()["n"]
    ап = одобрить(соед, ОТКРЫТЫЙ, idx.CLOSED)
    with ожидать_отказ("CAS_CONFLICT"):
        применить(соед, ОТКРЫТЫЙ, idx.CLOSED, expected_revision=0, approval_id=ап)
    стало = соед.execute(команд, типы).fetchone()["n"]
    assert стало == было, "отклонённая команда не пишется в журнал"


def test_после_перезапуска_состояние_то_же(tmp_path) -> None:
    путь = tmp_path / "l.sqlite3"
    c = новая_база(путь)
    применить(c, ОТКРЫТЫЙ, idx.OPEN, expected_revision=0)
    отпечаток = idx.снимок(c)["snapshot_digest"]
    c.close()

    c = перезапуск(путь)
    assert idx.снимок(c)["snapshot_digest"] == отпечаток
    assert store.проверить_цепь(c)["ok"] is True
    c.close()


def test_цепь_хэшей_остаётся_валидной(соед) -> None:
    применить(соед, ОТКРЫТЫЙ, idx.OPEN, expected_revision=0)
    применить(соед, "yummyani-org", idx.CLOSED, expected_revision=0)
    assert store.проверить_цепь(соед)["ok"] is True


def test_outbox_получает_по_событию_на_изменение(соед) -> None:
    применить(соед, ОТКРЫТЫЙ, idx.OPEN, expected_revision=0)
    применить(соед, ОТКРЫТЫЙ, idx.CLOSED, expected_revision=1)
    строки = list(соед.execute(
        "SELECT * FROM indexing_outbox WHERE site_id=? ORDER BY seq", (ОТКРЫТЫЙ,)))
    assert len(строки) == 2
    assert [json.loads(с["payload"])["revision"] for с in строки] == [1, 2]


def test_повторная_доставка_outbox_не_дублирует_логическое_событие(соед) -> None:
    """Повтор публикации не создаёт вторую запись: ключ по event_id."""
    ап = одобрить(соед, ОТКРЫТЫЙ, idx.OPEN)
    применить(соед, ОТКРЫТЫЙ, idx.OPEN, expected_revision=0, approval_id=ап, key="k")
    применить(соед, ОТКРЫТЫЙ, idx.OPEN, expected_revision=0, approval_id=ап, key="k")
    assert соед.execute(
        "SELECT count(*) n FROM indexing_outbox").fetchone()["n"] == 1


# --- конкуренция ---------------------------------------------------------------

def test_сто_конкурентных_команд_дают_один_победитель(tmp_path) -> None:
    """Сто попыток с одной ожидаемой ревизией: победитель ровно один.

    Конкуренцию разрешает хранилище (``BEGIN IMMEDIATE``), а не блокировка
    внутри процесса: два экземпляра писателя её не разделяют.
    """
    путь = tmp_path / "l.sqlite3"
    c = новая_база(путь)
    одобрения = [одобрить(c, ОТКРЫТЫЙ, idx.OPEN) for _ in range(100)]
    c.close()

    успехи: list[dict] = []
    конфликты: list[str] = []
    замок = threading.Lock()

    def попытка(n: int) -> None:
        # Открытие соединения тоже внутри try: снаружи его отказ убил бы нить
        # бесследно, и тест показал бы ноль конфликтов вместо девяноста девяти.
        своё = None
        try:
            своё = store.открыть(путь)
            своё.execute("PRAGMA busy_timeout=5000")
            итог = idx.открыть_индексацию(
                своё, site_id=ОТКРЫТЫЙ, expected_revision=0,
                approval_id=одобрения[n], reason=f"попытка {n}",
                idempotency_key=f"key-{n}", correlation_id="c",
                producer_service="architect", actor_id=f"writer-{n}",
                actor_type="SERVICE", authority="EXECUTE", известные_сайты=ДЕВЯТЬ)
            with замок:
                успехи.append(итог)
        except idx.LedgerError as ош:
            with замок:
                конфликты.append(ош.error_code)
        except Exception as ош:   # любая иная неудача — тоже не победа
            with замок:
                конфликты.append(f"{type(ош).__name__}:{ош}")
        finally:
            if своё is not None:
                своё.close()

    нити = [threading.Thread(target=попытка, args=(i,)) for i in range(100)]
    for н in нити:
        н.start()
    for н in нити:
        н.join()

    c = store.открыть(путь)
    состояние = idx.состояние(c, ОТКРЫТЫЙ)
    ревизии = [r["revision"] for r in c.execute(
        "SELECT revision FROM indexing_revision WHERE site_id=? ORDER BY revision",
        (ОТКРЫТЫЙ,))]
    монотонность = idx.проверить_монотонность(c)
    цепь = store.проверить_цепь(c)
    c.close()

    assert len(успехи) == 1, f"успехов {len(успехи)}, а должен быть один"
    assert len(конфликты) == 99
    assert состояние["revision"] == 1
    assert ревизии == [1], "пропусков и дублей ревизий быть не должно"
    assert монотонность["ok"]
    assert цепь["ok"] is True


def test_два_писателя_не_теряют_изменение(tmp_path) -> None:
    """Последовательные писатели из разных соединений: ревизии идут подряд."""
    путь = tmp_path / "l.sqlite3"
    c = новая_база(путь)
    c.close()

    for n, целевое in enumerate([idx.OPEN, idx.CLOSED, idx.OPEN, idx.CLOSED]):
        своё = store.открыть(путь)
        применить(своё, ОТКРЫТЫЙ, целевое, expected_revision=n)
        своё.close()

    c = store.открыть(путь)
    assert idx.состояние(c, ОТКРЫТЫЙ)["revision"] == 4
    assert idx.проверить_монотонность(c)["ok"]
    c.close()


# --- контракт для потребителя --------------------------------------------------

def test_контракт_детерминирован(соед) -> None:
    применить(соед, ОТКРЫТЫЙ, idx.OPEN, expected_revision=0)
    первый = контракт.прочитать(соед)
    второй = контракт.прочитать(соед)
    # taken_at отличается по определению; сравниваются поля решения
    first_sites, second_sites = первый.sites, второй.sites
    assert first_sites == second_sites
    assert первый.snapshot_digest == второй.snapshot_digest
    assert json.loads(первый.to_json())["sites"] == json.loads(второй.to_json())["sites"]


def test_контракт_отдаёт_все_объявленные_поля(соед) -> None:
    применить(соед, ОТКРЫТЫЙ, idx.OPEN, expected_revision=0)
    сайт = контракт.прочитать(соед).sites[0]
    для_seo = {"site_id", "desired_state", "revision", "updated_at",
               "source_event_id", "approval_ref", "reason", "snapshot_digest",
               "schema_version", "registered"}
    assert для_seo <= set(сайт)


def test_неизвестный_site_id_это_ошибка_а_не_closed(соед) -> None:
    with pytest.raises(контракт.UnknownSite):
        контракт.прочитать_сайт(соед, "нет-такого", известные_сайты=ДЕВЯТЬ)


def test_у_контракта_нет_методов_изменения() -> None:
    запретные = [
        имя for имя in dir(контракт)
        if any(к in имя.lower() for к in ("open_index", "close_index", "set_",
                                          "write_state", "mutate", "apply_"))
    ]
    assert not запретные, f"в read-контракте появился писатель: {запретные}"


# --- LKG и недоступность -------------------------------------------------------

def test_подтверждённый_lkg_применяется_только_для_чтения(соед, tmp_path) -> None:
    применить(соед, ОТКРЫТЫЙ, idx.OPEN, expected_revision=0)
    снимок = контракт.прочитать(соед)
    путь = контракт.сохранить_lkg(снимок, tmp_path / "lkg.json")

    восстановлен = контракт.загрузить_lkg(путь)
    ответ = контракт.прочитать(None, last_known_good=восстановлен)
    assert ответ.lkg_status == контракт.LKG_ПРИМЕНЁН
    assert ответ.release_blocked is True, "релиз не продвигается на подтверждённом снимке"
    assert контракт.состояние_для_потребителя(ответ, ОТКРЫТЫЙ) == idx.OPEN


def test_без_lkg_ничего_не_публикуется() -> None:
    ответ = контракт.прочитать(None)
    assert ответ.sites == [], "пустая матрица не выдаётся за «всё закрыто»"
    assert ответ.lkg_status == контракт.LKG_ОТСУТСТВУЕТ
    assert ответ.release_blocked is True


@pytest.mark.parametrize(
    "содержимое, признак",
    [("", "пуст"), ("{не json", "не разбирается"),
     ('{"contract_version":"иное/9.9","schema_version":"x","provider_health":"H",'
      '"lkg_status":"N","snapshot_digest":"d"}', "чужая версия"),
     ('{"contract_version":"fleet-indexing-read/1.0.0","schema_version":"x",'
      '"provider_health":"H","lkg_status":"N","snapshot_digest":""}', "нет отпечатка")],
)
def test_повреждённый_lkg_не_применяется(tmp_path, содержимое: str, признак: str) -> None:
    путь = tmp_path / "lkg.json"
    путь.write_text(содержимое, encoding="utf-8")
    with pytest.raises(контракт.ContractError, match=признак):
        контракт.загрузить_lkg(путь)


def test_холодный_старт_с_lkg_не_создаёт_решения(соед, tmp_path) -> None:
    """Реестр временно недоступен: подтверждённый снимок читается, но ревизия
    не появляется — нового решения никто не принимал."""
    применить(соед, ОТКРЫТЫЙ, idx.OPEN, expected_revision=0)
    путь = контракт.сохранить_lkg(контракт.прочитать(соед), tmp_path / "lkg.json")
    было = idx.состояние(соед, ОТКРЫТЫЙ)["revision"]

    ответ = контракт.прочитать(None, last_known_good=контракт.загрузить_lkg(путь))
    assert ответ.release_blocked
    assert idx.состояние(соед, ОТКРЫТЫЙ)["revision"] == было


# --- устаревшие источники ------------------------------------------------------

def test_старый_снимок_не_уменьшает_ревизию(соед, tmp_path) -> None:
    """Старый artifact, cache или backup не могут понизить ревизию."""
    применить(соед, ОТКРЫТЫЙ, idx.OPEN, expected_revision=0)
    старый = контракт.сохранить_lkg(контракт.прочитать(соед), tmp_path / "old.json")
    применить(соед, ОТКРЫТЫЙ, idx.CLOSED, expected_revision=1)
    применить(соед, ОТКРЫТЫЙ, idx.OPEN, expected_revision=2)

    прежний = контракт.загрузить_lkg(старый)
    живое = контракт.прочитать(соед)
    assert живое.sites[0]["revision"] == 3
    assert прежний.sites[0]["revision"] == 1
    # применить старую ревизию нельзя: CAS сравнивает по ревизии
    with ожидать_отказ("CAS_CONFLICT"):
            применить(соед, ОТКРЫТЫЙ, idx.CLOSED, expected_revision=1)
    assert idx.состояние(соед, ОТКРЫТЫЙ)["revision"] == 3


# --- миграция девяти сайтов ----------------------------------------------------

КОРЕНЬ = Path(__file__).resolve().parents[2]


def test_миграция_вхолостую_даёт_один_открытый_и_восемь_закрытых(соед) -> None:
    """Сухой прогон: девять сайтов, матрица 1 OPEN + 8 CLOSED, drift = 0.

    Production не меняется: всё происходит на эфемерной базе.
    """
    batch = "migration-" + str(uuid.uuid4())[:8]
    ожидание = {s: (idx.OPEN if s == ОТКРЫТЫЙ else idx.CLOSED) for s in sorted(ДЕВЯТЬ)}

    for site_id, целевое in ожидание.items():
        ап = одобрить(соед, site_id, целевое)
        команда = (idx.открыть_индексацию if целевое == idx.OPEN
                   else idx.закрыть_индексацию)
        команда(соед, site_id=site_id, expected_revision=0, approval_id=ап,
                reason=f"перенос начального состояния, партия {batch}",
                idempotency_key=f"{batch}:{site_id}", correlation_id=batch,
                producer_service="architect", actor_id="migrator",
                actor_type="SERVICE", authority="EXECUTE", известные_сайты=ДЕВЯТЬ,
                migration_batch_id=batch)

    снимок = idx.снимок(соед)
    assert снимок["open_count"] == 1
    assert снимок["closed_count"] == 8
    assert снимок["open"] == [ОТКРЫТЫЙ]
    assert all(с["migration_batch_id"] == batch for с in снимок["sites"])
    assert all(с["reason"].strip() for с in снимок["sites"]), "происхождение у каждого"
    assert idx.проверить_монотонность(соед)["ok"]


def test_повтор_партии_идемпотентен(соед) -> None:
    batch = "migration-повтор"
    ап = одобрить(соед, ОТКРЫТЫЙ, idx.OPEN)
    for _ in range(2):
        idx.открыть_индексацию(
            соед, site_id=ОТКРЫТЫЙ, expected_revision=0, approval_id=ап,
            reason="перенос", idempotency_key=f"{batch}:{ОТКРЫТЫЙ}",
            correlation_id=batch, producer_service="architect",
            actor_id="migrator", actor_type="SERVICE", authority="EXECUTE",
            известные_сайты=ДЕВЯТЬ, migration_batch_id=batch,
            occurred_at="2026-09-16T00:00:00.000000Z")
    assert idx.состояние(соед, ОТКРЫТЫЙ)["revision"] == 1


def test_домен_не_является_ключом(соед) -> None:
    """Первичный идентификатор — site_id. Домен меняется, идентификатор нет."""
    with ожидать_отказ("SITE_ID_UNKNOWN"):
            применить(соед, "yummyani.site", idx.OPEN, expected_revision=0)


# --- резервная копия и восстановление ------------------------------------------

def test_восстановление_из_копии_сохраняет_состояние_и_цепь(tmp_path) -> None:
    путь = tmp_path / "l.sqlite3"
    c = новая_база(путь)
    применить(c, ОТКРЫТЫЙ, idx.OPEN, expected_revision=0)
    применить(c, "yummyani-org", idx.CLOSED, expected_revision=0)
    отпечаток = idx.снимок(c)["snapshot_digest"]
    c.close()

    копия = tmp_path / "backup.sqlite3"
    копия.write_bytes(путь.read_bytes())

    восстановлено = store.открыть(копия)
    idx.подготовить(восстановлено)
    assert idx.снимок(восстановлено)["snapshot_digest"] == отпечаток
    assert store.проверить_цепь(восстановлено)["ok"] is True
    assert idx.проверить_монотонность(восстановлено)["ok"]
    assert восстановлено.execute(
        "SELECT count(*) n FROM indexing_outbox").fetchone()["n"] == 2
    восстановлено.close()


def test_старая_копия_не_перезаписывает_более_новую_ревизию(tmp_path) -> None:
    путь = tmp_path / "l.sqlite3"
    c = новая_база(путь)
    применить(c, ОТКРЫТЫЙ, idx.OPEN, expected_revision=0)
    копия = tmp_path / "backup.sqlite3"
    копия.write_bytes(путь.read_bytes())          # снимок на ревизии 1
    применить(c, ОТКРЫТЫЙ, idx.CLOSED, expected_revision=1)
    c.close()

    старая = store.открыть(копия)
    idx.подготовить(старая)
    ревизия_копии = idx.состояние(старая, ОТКРЫТЫЙ)["revision"]
    старая.close()

    живое = store.открыть(путь)
    ревизия_живого = idx.состояние(живое, ОТКРЫТЫЙ)["revision"]
    # Восстановление старой копии поверх живого — операция владельца, и она
    # обязана быть замечена: ревизия копии меньше живой.
    assert ревизия_копии < ревизия_живого
    with ожидать_отказ("CAS_CONFLICT"):
            применить(живое, ОТКРЫТЫЙ, idx.OPEN, expected_revision=ревизия_копии)
    живое.close()


# --- совместимость с handoff SEO -----------------------------------------------

#: Поля, которые SEO объявил в docs/seo/CORE-HANDOFF-PERSISTENT-INDEXING.md
#: на коммите 08ad06880c91f8056f4c49f485e4933e443a9e2f. Список зафиксирован
#: здесь намеренно: контракт, совместимость которого проверяется по памяти,
#: перестаёт быть контрактом.
ПОЛЯ_HANDOFF = {
    "site_id", "domain", "desired_state", "revision", "updated_at",
    "source_event_id", "last_known_good_revision",
}


def test_контракт_покрывает_поля_handoff_seo(соед) -> None:
    применить(соед, ОТКРЫТЫЙ, idx.OPEN, expected_revision=0)
    домены = {ОТКРЫТЫЙ: "yummyani.site"}
    сайт = контракт.прочитать(соед, домены=домены).sites[0]
    нет = ПОЛЯ_HANDOFF - set(сайт)
    assert not нет, f"контракт не отдаёт поля, объявленные SEO: {sorted(нет)}"
    assert сайт["domain"] == "yummyani.site"
    assert сайт["last_known_good_revision"] == сайт["revision"]


def test_домен_производный_и_не_обязателен(соед) -> None:
    """Без реестра домен неизвестен — и это честный None, а не выдумка."""
    применить(соед, ОТКРЫТЫЙ, idx.OPEN, expected_revision=0)
    сайт = контракт.прочитать(соед).sites[0]
    assert сайт["domain"] is None
    assert сайт["site_id"] == ОТКРЫТЫЙ, "ключом остаётся site_id"
