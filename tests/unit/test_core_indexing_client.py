"""SEO читает состояние индексации у Core и не владеет им.

Раньше решение «открыт ли сайт» жило в профиле сайта, в реестре оператора и в
списке доменов прямо в коде посредника. Совпадали они случайно, и обычная
выкладка закрывала живую витрину.

Теперь владелец один — Fleet Core. Здесь проверяется, что SEO именно читает:
не пишет, не додумывает при отказе и не считает себя актуальным, когда
состояние ушло вперёд.

Ответы Core подделываются, а не запрашиваются по сети: проверяется поведение
клиента, а не доступность чужой службы.
"""

from __future__ import annotations

import io
import json
import urllib.error
from pathlib import Path

import pytest

from factory.indexing import core_client as клиент

САЙТ = "yummyani-site"
СОСЕД = "yummyani-org"


def запись(site_id: str, состояние: str, revision: int, *, digest: str = "d1") -> dict:
    return {
        "site_id": site_id, "domain": f"{site_id}.example",
        "desired_state": состояние, "revision": revision,
        "last_known_good_revision": revision,
        "updated_at": "2026-09-16T00:00:00Z", "source_event_id": "e1",
        "approval_ref": "a1", "reason": "решение владельца",
        "snapshot_digest": digest, "schema_version": клиент.ПОДДЕРЖИВАЕМАЯ_СХЕМА,
        "registered": True,
    }


def ответ(*записи: dict, digest: str = "snap-1", **переопределения) -> dict:
    тело = {
        "contract_version": клиент.ПОДДЕРЖИВАЕМЫЙ_КОНТРАКТ,
        "schema_version": клиент.ПОДДЕРЖИВАЕМАЯ_СХЕМА,
        "provider_health": клиент.ЗДОРОВ,
        "snapshot_digest": digest,
        "taken_at": "2026-09-16T00:00:00Z",
        "sites": list(записи),
    }
    тело.update(переопределения)
    return тело


def поддельный(тело: dict | str):
    """Открыватель, отдающий заданный ответ вместо сети."""
    сырое = тело if isinstance(тело, str) else json.dumps(тело, ensure_ascii=False)

    class Ответ(io.BytesIO):
        def __enter__(self):
            return self

        def __exit__(self, *_a):
            self.close()
            return False

    def открыть(_запрос, timeout=None):
        return Ответ(сырое.encode("utf-8"))

    return открыть


def отказ(исключение):
    def открыть(_запрос, timeout=None):
        raise исключение

    return открыть


# --- чтение --------------------------------------------------------------------

def test_снимок_читается() -> None:
    e = клиент.прочитать("http://core", "t", opener=поддельный(
        ответ(запись(САЙТ, клиент.OPEN, 3), запись(СОСЕД, клиент.CLOSED, 1))))
    assert e.состояние(САЙТ) == клиент.OPEN
    assert e.revision(САЙТ) == 3
    assert e.matrix()["open_count"] == 1
    assert e.matrix()["closed_count"] == 1


def test_неизвестный_сайт_закрыт() -> None:
    """Разрешение выдаётся поимённо: умолчание «наверное, можно» однажды
    откроет домен, которого никто не проверял."""
    e = клиент.прочитать("http://core", "t", opener=поддельный(
        ответ(запись(САЙТ, клиент.OPEN, 1))))
    assert e.состояние("нет-такого") == клиент.CLOSED
    assert e.revision("нет-такого") == 0


def test_запись_детерминирована() -> None:
    e = клиент.прочитать("http://core", "t", opener=поддельный(ответ(запись(САЙТ, клиент.OPEN, 1))))
    assert e.to_json() == e.to_json()


# --- негодный ответ блокирует ---------------------------------------------------

def test_чужая_версия_контракта() -> None:
    with pytest.raises(клиент.ContractDrift, match="контракт"):
        клиент.прочитать("http://core", "t", opener=поддельный(
            ответ(запись(САЙТ, клиент.OPEN, 1), contract_version="иное/9.9")))


def test_чужая_версия_схемы() -> None:
    with pytest.raises(клиент.ContractDrift, match="схема"):
        клиент.прочитать("http://core", "t", opener=поддельный(
            ответ(запись(САЙТ, клиент.OPEN, 1), schema_version="иное/9.9")))


def test_снимок_без_отпечатка() -> None:
    with pytest.raises(клиент.ContractDrift, match="отпечатка"):
        клиент.прочитать("http://core", "t", opener=поддельный(
            ответ(запись(САЙТ, клиент.OPEN, 1), snapshot_digest="")))


def test_неполная_запись_это_не_ответ() -> None:
    неполная = запись(САЙТ, клиент.OPEN, 1)
    del неполная["revision"]
    with pytest.raises(клиент.ContractDrift, match="неполна"):
        клиент.прочитать("http://core", "t", opener=поддельный(ответ(неполная)))


def test_неизвестное_состояние() -> None:
    плохая = {**запись(САЙТ, клиент.OPEN, 1), "desired_state": "MAYBE"}
    with pytest.raises(клиент.ContractDrift, match="не объявлено"):
        клиент.прочитать("http://core", "t", opener=поддельный(ответ(плохая)))


def test_дубликат_личности() -> None:
    with pytest.raises(клиент.ContractDrift, match="дважды"):
        клиент.прочитать("http://core", "t", opener=поддельный(
            ответ(запись(САЙТ, клиент.OPEN, 1), запись(САЙТ, клиент.CLOSED, 2))))


def test_нечитаемый_ответ() -> None:
    with pytest.raises(клиент.ContractDrift, match="не разбирается"):
        клиент.прочитать("http://core", "t", opener=поддельный("{не json"))


# --- старшинство ревизий и ABA --------------------------------------------------

def test_меньшая_ревизия_отклоняется() -> None:
    принят = клиент.прочитать("http://core", "t", opener=поддельный(
        ответ(запись(САЙТ, клиент.OPEN, 5))))
    старый = клиент.прочитать("http://core", "t", opener=поддельный(
        ответ(запись(САЙТ, клиент.OPEN, 3), digest="snap-0")))
    with pytest.raises(клиент.RevisionRegression, match="не переписывают"):
        клиент.сверить_ревизии(принят, старый)


def test_та_же_ревизия_тот_же_отпечаток_это_повтор() -> None:
    первый = клиент.прочитать("http://core", "t", opener=поддельный(
        ответ(запись(САЙТ, клиент.OPEN, 5, digest="x"))))
    второй = клиент.прочитать("http://core", "t", opener=поддельный(
        ответ(запись(САЙТ, клиент.OPEN, 5, digest="x"))))
    итог = клиент.сверить_ревизии(первый, второй)
    assert итог.revision(САЙТ) == 5


def test_та_же_ревизия_другой_отпечаток_это_конфликт() -> None:
    первый = клиент.прочитать("http://core", "t", opener=поддельный(
        ответ(запись(САЙТ, клиент.OPEN, 5, digest="x"))))
    иной = клиент.прочитать("http://core", "t", opener=поддельный(
        ответ(запись(САЙТ, клиент.OPEN, 5, digest="y"))))
    with pytest.raises(клиент.RevisionConflict, match="другим отпечатком"):
        клиент.сверить_ревизии(первый, иной)


def test_большая_ревизия_принимается_целиком() -> None:
    принят = клиент.прочитать("http://core", "t", opener=поддельный(
        ответ(запись(САЙТ, клиент.OPEN, 5))))
    новее = клиент.прочитать("http://core", "t", opener=поддельный(
        ответ(запись(САЙТ, клиент.CLOSED, 6, digest="z"), digest="snap-2")))
    итог = клиент.сверить_ревизии(принят, новее)
    assert итог.состояние(САЙТ) == клиент.CLOSED
    assert итог.revision(САЙТ) == 6


def test_ABA_различается_по_ревизии() -> None:
    """OPEN r10 → CLOSED r11 → OPEN r12.

    Значение снова OPEN, но клиент, уснувший на r10, актуальным не является.
    Сравнение по значению дало бы ложное согласие.
    """
    r10 = клиент.прочитать("http://core", "t", opener=поддельный(
        ответ(запись(САЙТ, клиент.OPEN, 10, digest="a"))))
    r12 = клиент.прочитать("http://core", "t", opener=поддельный(
        ответ(запись(САЙТ, клиент.OPEN, 12, digest="c"))))
    assert r10.состояние(САЙТ) == r12.состояние(САЙТ) == клиент.OPEN
    assert r10.revision(САЙТ) != r12.revision(САЙТ)
    with pytest.raises(клиент.RevisionRegression):
        клиент.сверить_ревизии(r12, r10)


# --- отказ Core -----------------------------------------------------------------

def test_недоступность_с_подтверждённым_снимком_сохраняет_состояние(tmp_path) -> None:
    снимок = клиент.прочитать("http://core", "t", opener=поддельный(
        ответ(запись(САЙТ, клиент.OPEN, 4), запись(СОСЕД, клиент.CLOSED, 2))))
    итог = клиент.разрешить("http://core", "t", last_known_good=снимок,
                            opener=отказ(urllib.error.URLError("нет связи")))
    assert итог.provider_health == клиент.НЕДОСТУПЕН
    assert итог.lkg_status == клиент.LKG_ПРИМЕНЁН
    assert итог.release_blocked is True, "выпуск не продвигается на подтверждённом снимке"
    assert итог.состояние(САЙТ) == клиент.OPEN, "подтверждённый OPEN не закрывается"
    assert итог.состояние(СОСЕД) == клиент.CLOSED, "подтверждённый CLOSED не открывается"


def test_недоступность_без_снимка_не_публикует_ничего() -> None:
    итог = клиент.разрешить("http://core", "t",
                            opener=отказ(urllib.error.URLError("нет связи")))
    assert итог.release_blocked is True
    assert итог.sites == {}, "пустая матрица не выдаётся за «все закрыты»"
    assert итог.lkg_status == клиент.LKG_ОТСУТСТВУЕТ


def test_пятисотый_это_недоступность() -> None:
    ошибка = urllib.error.HTTPError("http://core", 503, "unavailable", {}, None)
    итог = клиент.разрешить("http://core", "t", opener=отказ(ошибка))
    assert итог.provider_health == клиент.НЕДОСТУПЕН
    assert итог.release_blocked is True


def test_отказ_прав_не_маскируется_под_недоступность() -> None:
    ошибка = urllib.error.HTTPError("http://core", 403, "forbidden", {}, None)
    with pytest.raises(клиент.CoreError, match="403"):
        клиент.прочитать("http://core", "t", opener=отказ(ошибка))


# --- подтверждённый снимок ------------------------------------------------------

def test_снимок_переживает_запись_и_чтение(tmp_path: Path) -> None:
    снимок = клиент.прочитать("http://core", "t", opener=поддельный(
        ответ(запись(САЙТ, клиент.OPEN, 4))))
    путь = клиент.сохранить_lkg(снимок, tmp_path / "lkg.json")
    восстановлен = клиент.загрузить_lkg(путь)
    assert восстановлен.состояние(САЙТ) == клиент.OPEN
    assert восстановлен.revision(САЙТ) == 4
    assert восстановлен.lkg_status == клиент.LKG_ПРИМЕНЁН


@pytest.mark.parametrize(
    "содержимое, признак",
    [("", "пуст"), ("{не json", "не разбирается")],
)
def test_негодный_снимок_не_применяется(tmp_path: Path, содержимое, признак) -> None:
    путь = tmp_path / "lkg.json"
    путь.write_text(содержимое, encoding="utf-8")
    with pytest.raises(клиент.ContractDrift, match=признак):
        клиент.загрузить_lkg(путь)


def test_снимок_чужой_версии_не_применяется(tmp_path: Path) -> None:
    путь = tmp_path / "lkg.json"
    путь.write_text(json.dumps({
        "contract_version": "иное/9.9", "schema_version": клиент.ПОДДЕРЖИВАЕМАЯ_СХЕМА,
        "provider_health": клиент.ЗДОРОВ, "snapshot_digest": "d", "sites": {},
    }), encoding="utf-8")
    with pytest.raises(клиент.ContractDrift, match="контракт"):
        клиент.загрузить_lkg(путь)


# --- разделение ответственности --------------------------------------------------

def test_у_клиента_нет_способа_изменить_состояние() -> None:
    """Команды OPEN и CLOSE принадлежат Core. Здесь их быть не должно."""
    запретные = [имя for имя in dir(клиент)
                 if any(k in имя.lower() for k in
                        ("open_index", "close_index", "set_", "write_state",
                         "mutate", "apply_", "публиковать"))]
    assert not запретные, f"в клиенте появился писатель: {запретные}"


def test_клиент_обращается_только_к_маршруту_чтения() -> None:
    исходник = Path(клиент.__file__).read_text(encoding="utf-8")
    assert "/api/v1/indexing/state" in исходник
    for запрет in ("sqlite3", "indexing_state", "ledger_event", "outbox"):
        assert запрет not in исходник, (
            f"клиент знает о внутреннем устройстве Core: {запрет}")
