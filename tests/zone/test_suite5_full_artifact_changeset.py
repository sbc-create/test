"""SUITE_5 — полный артефакт на законном пути и поведение при авариях.

SUITE_2 доказала сам путь. Здесь проверяется то, что отличает R2: артефакт
полного каталога, повтор при потерянном ответе, два одновременных вызова и
падение по обе стороны от фиксации манифеста.
"""
from __future__ import annotations

import hashlib
import json
import pathlib
import threading

import pytest

from factory.lords import artifact as artifact_mod
from factory.lords import urlmap as um

КОРЕНЬ = pathlib.Path(__file__).resolve().parents[2]
ПОЛНАЯ = КОРЕНЬ / "var" / "build-a" / "zona-cinema"


def отпечаток_дерева(корень: pathlib.Path) -> str:
    """Правило одно на всех: `factory.lords.artifact`.

    Своя копия здесь была бы хуже дублирования: проверка считала бы отпечаток
    иначе, чем инструмент, и расхождение выглядело бы как дефект сборки.
    """
    return artifact_mod.отпечаток(корень)


@pytest.fixture(scope="module")
def артефакт():
    if not (ПОЛНАЯ / "route-map.json").is_file():
        pytest.skip(f"полной сборки нет: {ПОЛНАЯ}")
    карта = json.loads((ПОЛНАЯ / "route-map.json").read_text(encoding="utf-8"))
    return {"root": ПОЛНАЯ, "routes": карта["routes"],
            "route_map_sha256": um.построить(карта["routes"]).отпечаток,
            "artifact_sha256": отпечаток_дерева(ПОЛНАЯ)}


class ЖурналЦели:
    """Изолированная цель с наблюдаемой историей обращений."""

    def __init__(self) -> None:
        self.состояние: dict[str, str] = {}
        self.эффекты: list[tuple[str, str]] = []
        self.обращений = 0
        self._замок = threading.Lock()

    def применить(self, site_id: str, digest: str, ключ: str) -> dict:
        with self._замок:
            self.обращений += 1
            прежний = self.состояние.get(site_id)
            if прежний == digest:
                return {"changed": False, "effects": 0, "rollback_artifact": прежний}
            self.состояние[site_id] = digest
            self.эффекты.append((site_id, digest))
            return {"changed": True, "effects": 1, "rollback_artifact": прежний}

    def текущее(self, site_id: str) -> str | None:
        return self.состояние.get(site_id)


class Исполнитель:
    """Заявка фиксируется ДО обращения к цели.

    Порядок не косметический: заявка, записанная после эффекта, теряется при
    падении между ними, и повтор делает второй эффект. Поэтому сначала
    заявка, потом обращение, и только потом отметка об исходе.
    """

    def __init__(self, цель: ЖурналЦели) -> None:
        self.цель = цель
        self.заявки: dict[str, dict] = {}
        self._замок = threading.Lock()

    def выполнить(self, site_id: str, digest: str, ключ: str, *,
                  падение_после_эффекта: bool = False) -> dict:
        with self._замок:
            заявка = self.заявки.get(ключ)
            if заявка and заявка["status"] == "DONE":
                return {"replay": True, "effects": 0, "status": "DONE"}
            if заявка is None:
                self.заявки[ключ] = {"status": "CLAIMED", "site_id": site_id,
                                     "digest": digest}
        итог = self.цель.применить(site_id, digest, ключ)
        if падение_после_эффекта:
            raise RuntimeError("падение после эффекта, до отметки")
        with self._замок:
            self.заявки[ключ] = {"status": "DONE", "site_id": site_id,
                                 "digest": digest, "effects": итог["effects"]}
        return {"replay": False, "effects": итог["effects"], "status": "DONE"}

    def возобновить(self, ключ: str) -> dict:
        """После падения исход выясняется у цели, а не додумывается."""
        заявка = self.заявки.get(ключ)
        if заявка is None:
            return {"status": "UNKNOWN"}
        if заявка["status"] == "DONE":
            return {"status": "DONE", "effects": заявка.get("effects", 0)}
        применено = self.цель.текущее(заявка["site_id"]) == заявка["digest"]
        self.заявки[ключ] = {**заявка, "status": "DONE",
                             "effects": 1 if применено else 0}
        return {"status": "DONE", "effects": 1 if применено else 0,
                "recovered": True}


class TestАртефактПолногоКаталога:
    def test_маршруты_покрывают_все_публикуемые_сущности(self, артефакт):
        """Маршрутов столько, сколько витрина публикует, и ни одним меньше.

        Не 53 344: витрина публикует не все виды произведений. Проверяется не
        совпадение с числом записей каталога, а то, что ни одна опубликованная
        сущность не осталась без адреса и ни один адрес не выдуман.
        """
        отчёт = json.loads(
            (артефакт["root"] / "preview-report.json").read_text("utf-8"))
        записей = отчёт["data_provenance"]["records"]
        страниц = len([x for x in (артефакт["root"] / "title").iterdir()
                       if (x / "index.html").is_file()])
        assert len(артефакт["routes"]) == страниц == отчёт["title_pages"]
        assert 0 < страниц <= записей
        assert отчёт["route_map"]["orphan_targets"] == 0

    def test_отпечаток_карты_считается_по_содержимому(self, артефакт):
        повтор = um.построить(артефакт["routes"]).отпечаток
        assert повтор == артефакт["route_map_sha256"]

    def test_отпечаток_дерева_устойчив(self, артефакт):
        assert отпечаток_дерева(артефакт["root"]) == артефакт["artifact_sha256"]


class TestИдемпотентность:
    def test_повтор_не_добавляет_эффекта(self):
        цель = ЖурналЦели(); исп = Исполнитель(цель)
        первый = исп.выполнить("zona-01", "sha-A", "k1")
        второй = исп.выполнить("zona-01", "sha-A", "k1")
        assert (первый["effects"], второй["effects"]) == (1, 0)
        assert второй["replay"] is True
        assert len(цель.эффекты) == 1

    def test_потерянный_ответ_и_повтор(self):
        """Ответ не дошёл, вызывающий повторил тем же ключом."""
        цель = ЖурналЦели(); исп = Исполнитель(цель)
        исп.выполнить("zona-01", "sha-A", "k-lost")
        повтор = исп.выполнить("zona-01", "sha-A", "k-lost")
        assert повтор["effects"] == 0 and len(цель.эффекты) == 1

    def test_два_одновременных_одинаковых_вызова(self):
        цель = ЖурналЦели(); исп = Исполнитель(цель)
        исходы = []
        барьер = threading.Barrier(2)

        def гонка():
            барьер.wait()
            исходы.append(исп.выполнить("zona-01", "sha-A", "k-race"))

        нити = [threading.Thread(target=гонка) for _ in range(2)]
        for н in нити:
            н.start()
        for н in нити:
            н.join()
        assert sum(и["effects"] for и in исходы) == 1
        assert len(цель.эффекты) == 1

    def test_падение_до_фиксации_манифеста(self):
        """Заявка есть, эффекта нет: возобновление не должно его придумать."""
        цель = ЖурналЦели(); исп = Исполнитель(цель)
        исп.заявки["k-crash"] = {"status": "CLAIMED", "site_id": "zona-01",
                                 "digest": "sha-A"}
        итог = исп.возобновить("k-crash")
        assert итог["effects"] == 0 and len(цель.эффекты) == 0

    def test_падение_после_эффекта_до_отметки(self):
        """Эффект есть, отметки нет: возобновление узнаёт это у цели."""
        цель = ЖурналЦели(); исп = Исполнитель(цель)
        with pytest.raises(RuntimeError):
            исп.выполнить("zona-01", "sha-A", "k-after",
                          падение_после_эффекта=True)
        assert len(цель.эффекты) == 1
        итог = исп.возобновить("k-after")
        assert итог["effects"] == 1 and итог["recovered"] is True
        снова = исп.выполнить("zona-01", "sha-A", "k-after")
        assert снова["effects"] == 0 and len(цель.эффекты) == 1


class TestОткатИВозвратВперёд:
    def test_откат_возвращает_прежний_артефакт(self):
        цель = ЖурналЦели(); исп = Исполнитель(цель)
        цель.состояние["zona-01"] = "sha-прежний"
        исп.выполнить("zona-01", "sha-новый", "k")
        assert цель.текущее("zona-01") == "sha-новый"
        цель.состояние["zona-01"] = "sha-прежний"      # откат
        assert цель.текущее("zona-01") == "sha-прежний"

    def test_возврат_вперёд_даёт_один_эффект(self):
        цель = ЖурналЦели(); исп = Исполнитель(цель)
        цель.состояние["zona-01"] = "sha-прежний"
        исп.выполнить("zona-01", "sha-новый", "k1")
        цель.состояние["zona-01"] = "sha-прежний"
        до = len(цель.эффекты)
        исп.выполнить("zona-01", "sha-новый", "k2")     # новый ключ — новая попытка
        assert len(цель.эффекты) == до + 1
        assert цель.текущее("zona-01") == "sha-новый"

    def test_после_возврата_манифест_маршрутов_тот_же(self, артефакт):
        """Перечень маршрутов не зависит от того, откатывали ли выкладку."""
        снова = um.построить(артефакт["routes"]).отпечаток
        assert снова == артефакт["route_map_sha256"]


ВТОРАЯ = КОРЕНЬ / "var" / "build-b" / "zona-cinema"
ПЕРЕМЕШАННАЯ = КОРЕНЬ / "var" / "build-shuffled" / "zona-cinema"


class TestДвеЧистыеСборки:
    """Один и тот же вход обязан давать один и тот же артефакт.

    Сравниваются обе величины: перечень маршрутов и дерево целиком. Совпадение
    только карты маршрутов не доказывает, что страницы одинаковы.
    """

    @pytest.fixture(scope="class")
    def вторая(self):
        if not (ВТОРАЯ / "route-map.json").is_file():
            pytest.skip(f"второй сборки нет: {ВТОРАЯ}")
        return ВТОРАЯ

    def test_карта_маршрутов_совпадает(self, артефакт, вторая):
        карта = json.loads((вторая / "route-map.json").read_text("utf-8"))["routes"]
        assert um.построить(карта).отпечаток == артефакт["route_map_sha256"]
        assert карта == артефакт["routes"]

    def test_дерево_совпадает_побайтно(self, артефакт, вторая):
        assert отпечаток_дерева(вторая) == артефакт["artifact_sha256"]

    def test_число_страниц_совпадает(self, артефакт, вторая):
        а = len([x for x in (артефакт["root"] / "title").iterdir()
                 if (x / "index.html").is_file()])
        б = len([x for x in (вторая / "title").iterdir()
                 if (x / "index.html").is_file()])
        assert а == б > 50000


class TestПерестановкаВходаНичегоНеМеняет:
    """Собрано из тех же записей в другом порядке — артефакт обязан совпасть.

    Проверяется именно артефакт, а не только карта маршрутов: совпадение карты
    доказывает лишь то, что адреса не поехали, но не то, что страницы собраны
    одинаково.
    """

    @pytest.fixture(scope="class")
    def перемешанная(self):
        if not (ПЕРЕМЕШАННАЯ / "route-map.json").is_file():
            pytest.skip(f"перемешанной сборки нет: {ПЕРЕМЕШАННАЯ}")
        return ПЕРЕМЕШАННАЯ

    def test_вход_действительно_был_переставлен(self, перемешанная):
        отчёт = json.loads((перемешанная / "preview-report.json").read_text("utf-8"))
        assert отчёт["data_provenance"]["shuffle_seed"] is not None
        assert отчёт["data_provenance"]["records"] == 53344

    def test_карта_маршрутов_совпадает(self, артефакт, перемешанная):
        карта = json.loads((перемешанная / "route-map.json").read_text("utf-8"))["routes"]
        assert карта == артефакт["routes"]

    def test_дерево_совпадает_побайтно(self, артефакт, перемешанная):
        assert отпечаток_дерева(перемешанная) == артефакт["artifact_sha256"]
