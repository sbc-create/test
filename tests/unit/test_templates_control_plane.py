"""Подключение Templates к Control Plane: проекция, курсор, сверка.

Все мутации — на эфемерном Registry в памяти процесса. Канонический
Registry, Ledger и ChangeSet Store здесь не участвуют: тест, который
проверяет себя на боевом реестре, однажды оставит там synthetic-сайт.

Проверяется поведение, а не существование модулей: что проекция следует за
Registry, что курсор переживает перезапуск, что разрыв последовательности
чинится сверкой, а недоступный Registry честно называется STALE.
"""

from __future__ import annotations

import io
import json
import sqlite3
import urllib.error

import pytest

from factory.templates_cp.consumer import Потребитель, Замок
from factory.templates_cp.projection import Проекция
from factory.templates_cp.registry_client import (RegistryClient,
                                                  RegistryUnavailable)


class ЭфемерныйRegistry:
    """Реестр в памяти: отвечает как объявленный контракт, ничего не хранит."""

    def __init__(self) -> None:
        self.сайты: dict[str, dict] = {}
        self.события: list[dict] = []
        # Монотонный счётчик, а не длина списка: удаление события из ленты
        # не должно перенумеровывать следующее, иначе разрыв исчезает и
        # проверка разрыва проверяет пустоту.
        self.seq = 0
        self.версия = 0
        self.доступен = True
        self.запросов = 0

    # --- изменения состояния (только в тесте) ---------------------------
    def зарегистрировать(self, site_id: str, family: str, домен: str,
                         окружение: str = "production", состояние: str = "ACTIVE") -> dict:
        self.версия += 1
        self.сайты[site_id] = {"site_id": site_id, "family": family,
                               "domains": [домен], "canonical_domain": домен,
                               "environment": окружение, "lifecycle_state": состояние}
        self.seq += 1
        с = {"seq": self.seq, "event_id": f"ev-{site_id}-{self.версия}",
             "event_type": "site.registered.v1", "site_id": site_id,
             "registry_version": self.версия}
        self.события.append(с)
        return с

    def вывести(self, site_id: str) -> dict:
        self.версия += 1
        self.сайты[site_id]["lifecycle_state"] = "RETIRED"
        self.seq += 1
        с = {"seq": self.seq, "event_id": f"ev-{site_id}-ret-{self.версия}",
             "event_type": "site.retired.v1", "site_id": site_id,
             "registry_version": self.версия}
        self.события.append(с)
        return с

    # --- транспорт -------------------------------------------------------
    def открыть(self, зпр, timeout=None):
        self.запросов += 1
        if not self.доступен:
            raise urllib.error.URLError("эфемерный реестр выключен")
        путь = зпр.full_url.split("127.0.0.1:0", 1)[-1]
        тело = self._ответ(путь)
        if тело is None:
            raise urllib.error.HTTPError(зпр.full_url, 404, "not found", {}, None)
        return _Ответ(json.dumps(тело, ensure_ascii=False).encode("utf-8"))

    def _ответ(self, путь: str):
        if путь.startswith("/api/v1/sites?"):
            элементы = [с for с in self.сайты.values()
                        if с["environment"] == "production" and с["lifecycle_state"] == "ACTIVE"]
            return {"items": элементы, "registry_version": self.версия}
        if путь.startswith("/api/v1/sites/"):
            сид = путь.rsplit("/", 1)[-1]
            return self.сайты.get(сид)
        if путь.startswith("/api/v1/registry/version"):
            return {"registry_version": self.версия}
        if путь.startswith("/api/v1/registry/snapshot"):
            элементы = [с for с in self.сайты.values()
                        if с["environment"] == "production" and с["lifecycle_state"] == "ACTIVE"]
            return {"registry_version": self.версия, "checksum": f"sum-{self.версия}",
                    "etag": f'W/"{self.версия}"', "count": len(элементы), "sites": элементы}
        if путь.startswith("/api/v1/events"):
            курсор = 0
            if "cursor=" in путь:
                курсор = int(путь.split("cursor=")[1].split("&")[0])
            хвост = [с for с in self.события if с["seq"] > курсор]
            return {"items": хвост, "next_cursor": хвост[-1]["seq"] if хвост else курсор}
        return None


class _Ответ(io.BytesIO):
    status = 200
    headers: dict = {}

    def __enter__(self):
        return self

    def __exit__(self, *а):
        self.close()
        return False


@pytest.fixture()
def среда(tmp_path):
    реестр = ЭфемерныйRegistry()
    клиент = RegistryClient("http://127.0.0.1:0", открывашка=реестр.открыть)
    проекция = Проекция(str(tmp_path / "proj.sqlite3"))
    for i in range(1, 4):
        реестр.зарегистрировать(f"site-{i}", "lords", f"site{i}.test")
    yield реестр, клиент, проекция
    проекция.закрыть()


class TestИсточникСайтов:
    def test_производственные_приходят_из_api(self, среда):
        реестр, клиент, _ = среда
        снимок = клиент.производственные()
        assert снимок.идентификаторы == {"site-1", "site-2", "site-3"}
        assert реестр.запросов > 0, "список взят не из API"

    def test_серверный_фильтр_а_не_клиентский(self, среда):
        """Посторонняя запись в ответе — это расхождение контракта."""
        реестр, клиент, _ = среда
        реестр.сайты["site-1"]["environment"] = "staging"
        # Эфемерный сервер честно фильтрует, поэтому запись просто исчезает.
        assert клиент.производственные().идентификаторы == {"site-2", "site-3"}

    def test_клиент_не_доверяет_чужому_множеству(self, среда):
        """Если сервер вернул не то, что просили, это отказ, а не фильтр."""
        реестр, клиент, _ = среда

        def кривой(путь):
            if путь.startswith("/api/v1/sites?"):
                return {"items": [{"site_id": "x", "domains": ["x.test"],
                                   "environment": "staging", "lifecycle_state": "ACTIVE"}],
                        "registry_version": реестр.версия}
            return реестр._ответ(путь)

        реестр._ответ = кривой
        with pytest.raises(RegistryUnavailable):
            клиент.производственные()

    def test_в_коде_нет_статического_списка(self):
        """Ни одного зашитого домена и ни одного чтения статического списка.

        Проверяется исполняемый код, а не текст пояснений: упоминание
        `FLEET-REGISTRY.json` в комментарии объясняет, почему файл НЕ
        читается, и запрещать такое объяснение бессмысленно.
        """
        import ast
        import pathlib
        корень = pathlib.Path("factory/templates_cp")
        for файл in sorted(корень.glob("*.py")):
            дерево = ast.parse(файл.read_text(encoding="utf-8"))
            строки = [у.value for у in ast.walk(дерево)
                      if isinstance(у, ast.Constant) and isinstance(у.value, str)]
            # Строки-докстринги исключаются: они не исполняются.
            докстринги = set()
            for у in ast.walk(дерево):
                if isinstance(у, (ast.Module, ast.ClassDef, ast.FunctionDef,
                                  ast.AsyncFunctionDef)):
                    д = ast.get_docstring(у, clean=False)
                    if д:
                        докстринги.add(д)
            рабочие = [с for с in строки if с not in докстринги]
            for с in рабочие:
                assert "FLEET-REGISTRY" not in с, f"{файл}: читает статический список"
                for домен in ("lordfilm47.space", "zonafilm.space", "animedia.icu",
                              "animedia.space", "lordserial33.biz", "yummyani.site",
                              "yummyani.biz", "yummyani.org", "1lordserials1.online"):
                    assert домен not in с, f"{файл}: зашит домен {домен}"


class TestДинамическийРост:
    def test_n_plus_one_без_правки_кода(self, среда):
        """Новый сайт появляется в проекции сам, кодом его не добавляли."""
        реестр, клиент, проекция = среда
        потребитель = Потребитель(клиент, проекция, сон=lambda _: None)
        потребитель.сверить(причина="startup")
        было = проекция.производственные(True, "snapshot").идентификаторы
        assert len(было) == 3

        реестр.зарегистрировать("site-4", "zona", "site4.test")
        потребитель.один_проход()
        стало = проекция.производственные(True, "events").идентификаторы
        assert стало == было | {"site-4"}, "N+1 не подхвачен"

    def test_вывод_из_production_возвращает_к_n(self, среда):
        реестр, клиент, проекция = среда
        потребитель = Потребитель(клиент, проекция, сон=lambda _: None)
        потребитель.сверить(причина="startup")
        реестр.зарегистрировать("site-4", "zona", "site4.test")
        потребитель.один_проход()
        assert len(проекция.производственные(True, "e").идентификаторы) == 4

        реестр.вывести("site-4")
        потребитель.один_проход()
        активные = проекция.производственные(True, "e").идентификаторы
        assert активные == {"site-1", "site-2", "site-3"}
        # Запись не удалена: Registry её помнит, и проекция помнит тоже.
        все = {с["site_id"] for с in проекция.все()}
        assert "site-4" in все


class TestНадёжностьЛенты:
    def test_повтор_не_создаёт_второй_эффект(self, среда):
        реестр, клиент, проекция = среда
        потребитель = Потребитель(клиент, проекция, сон=lambda _: None)
        потребитель.сверить(причина="startup")
        событие = реестр.зарегистрировать("site-9", "zona", "site9.test")
        первый = потребитель.обработать(событие, "9")
        второй = потребитель.обработать(событие, "9")
        assert (первый, второй) == ("applied", "duplicate")
        assert потребитель.дубликатов == 1
        строки = проекция.соед.execute(
            "SELECT COUNT(*) c FROM site WHERE site_id='site-9'").fetchone()["c"]
        assert строки == 1

    def test_курсор_переживает_перезапуск(self, среда, tmp_path):
        реестр, клиент, проекция = среда
        потребитель = Потребитель(клиент, проекция, сон=lambda _: None)
        потребитель.сверить(причина="startup")
        потребитель.один_проход()
        курсор = проекция.курсор
        assert курсор is not None
        проекция.закрыть()

        снова = Проекция(str(tmp_path / "proj.sqlite3"))
        assert снова.курсор == курсор, "курсор не пережил перезапуск"
        снова.закрыть()

    def test_падение_до_подтверждения_не_теряет_событие(self, среда, tmp_path):
        """Курсор двигается только вместе с проекцией, иначе — потеря."""
        реестр, клиент, проекция = среда
        потребитель = Потребитель(клиент, проекция, сон=lambda _: None)
        потребитель.сверить(причина="startup")
        событие = реестр.зарегистрировать("site-5", "lords", "site5.test")

        def падение(_):
            raise RuntimeError("падение до записи")

        потребитель._применить = падение
        потребитель.обработать(событие, "99")   # уйдёт в DLQ после попыток
        assert проекция.глубина_dlq == 1
        # Событие не потеряно молча: оно лежит в DLQ с причиной.
        строка = проекция.соед.execute("SELECT * FROM dlq").fetchone()
        assert "падение" in строка["reason"]

    def test_разрыв_последовательности_чинится_сверкой(self, среда):
        реестр, клиент, проекция = среда
        потребитель = Потребитель(клиент, проекция, сон=lambda _: None)
        потребитель.сверить(причина="startup")
        # Сайт добавлен, а его событие из ленты пропало — классический разрыв.
        реестр.зарегистрировать("site-7", "animedia", "site7.test")
        реестр.события.pop()                  # событие исчезло
        реестр.зарегистрировать("site-8", "animedia", "site8.test")

        потребитель.один_проход()
        активные = проекция.производственные(True, "e").идентификаторы
        assert {"site-7", "site-8"} <= активные, "пропущенный сайт не найден сверкой"
        assert потребитель.разрывов >= 1, "разрыв не замечен"

    def test_событие_не_по_порядку_учитывается(self, среда):
        реестр, клиент, проекция = среда
        потребитель = Потребитель(клиент, проекция, сон=lambda _: None)
        потребитель.сверить(причина="startup")
        потребитель.один_проход()
        старое = dict(реестр.события[0])
        потребитель.обработать(старое, старое["seq"])
        assert потребитель.дубликатов >= 1

    def test_неизвестный_тип_не_роняет_потребителя(self, среда):
        реестр, клиент, проекция = среда
        потребитель = Потребитель(клиент, проекция, сон=lambda _: None)
        видел = []
        потребитель.журнал = lambda вид, д: видел.append(вид)
        исход = потребитель.обработать(
            {"event_id": "ev-x", "seq": 999, "event_type": "site.teleported.v9"}, "999")
        assert исход == "applied"
        assert "event.ignored" in видел


class TestНедоступныйRegistry:
    def test_проекция_честно_называет_себя_stale(self, среда):
        реестр, клиент, проекция = среда
        потребитель = Потребитель(клиент, проекция, сон=lambda _: None)
        потребитель.сверить(причина="startup")
        реестр.доступен = False

        assert потребитель.сверить(причина="periodic") is False
        ответ = проекция.производственные(свежая=False, источник="projection")
        assert ответ.свежая is False
        assert len(ответ.сайты) == 3, "кэш обязан продолжать отвечать"

    def test_клиент_отказывает_а_не_возвращает_пустое(self, среда):
        реестр, клиент, _ = среда
        реестр.доступен = False
        with pytest.raises(RegistryUnavailable):
            клиент.производственные()


class TestОдинЭкземпляр:
    def test_второй_потребитель_не_запускается(self, tmp_path):
        путь = str(tmp_path / "lock.sqlite3")
        первый, второй = Замок(путь), Замок(путь)
        assert первый.захватить() is True
        assert второй.захватить() is False, "две ленты двигали бы один курсор"
        первый.отпустить()
        assert второй.захватить() is True
        второй.отпустить()


class TestРазборОтложенных:
    """DLQ существует, чтобы её разбирали после починки причины."""

    def test_отложенное_событие_применяется_после_починки(self, среда):
        реестр, клиент, проекция = среда
        потребитель = Потребитель(клиент, проекция, сон=lambda _: None)
        потребитель.сверить(причина="startup")
        событие = реестр.зарегистрировать("site-7", "zona", "site7.test")

        # Причина отказа: временно недоступный снимок.
        def падать():
            raise RegistryUnavailable("снимок недоступен")

        рабочий = потребитель.клиент.снимок
        потребитель.клиент.снимок = падать
        assert потребитель.обработать(событие, "7") == "dlq"
        assert проекция.глубина_dlq == 1

        # Причина устранена — очередь обязана разобраться.
        потребитель.клиент.снимок = рабочий
        свод = потребитель.разобрать_dlq()
        assert свод == {"reprocessed": 1, "still_failing": 0, "total": 1}
        assert проекция.глубина_dlq == 0
        есть = проекция.соед.execute(
            "SELECT COUNT(*) c FROM site WHERE site_id='site-7'").fetchone()["c"]
        assert есть == 1, "разобранное событие обязано попасть в проекцию"

    def test_всё_ещё_ломающееся_остаётся_в_очереди(self, среда):
        реестр, клиент, проекция = среда
        потребитель = Потребитель(клиент, проекция, сон=lambda _: None)
        потребитель.сверить(причина="startup")
        событие = реестр.зарегистрировать("site-8", "zona", "site8.test")

        def падать():
            raise RegistryUnavailable("снимок недоступен")

        потребитель.клиент.снимок = падать
        потребитель.обработать(событие, "8")
        свод = потребитель.разобрать_dlq()
        assert свод["still_failing"] == 1 and свод["reprocessed"] == 0
        assert проекция.глубина_dlq == 1, "молча выбрасывать отложенное нельзя"
