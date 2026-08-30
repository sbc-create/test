"""Нормализованное хранилище и профили сайтов."""
from datetime import datetime, timezone
from pathlib import Path

import pytest

from factory.site_engine.contracts import ContractError, Title
from factory.site_engine.profiles import (
    NormalizedContentSource,
    ProfileInvalid,
    ProfileNotFound,
    load_all,
    load_profile,
)
from factory.site_engine.store import (
    MAX_LIMIT,
    InMemoryStore,
    TitleNotFound,
    WriteNotPermitted,
    WriteToken,
)

ROOT = Path(__file__).resolve().parents[2]
MOMENT = datetime(2026, 8, 30, 12, 0, tzinfo=timezone.utc)


def тайтлы(сколько: int, **kw):
    return [
        Title(canonical_id=f"p:{i}", provider="p", provider_id=str(i), name=f"Т{i}",
              observed_at=MOMENT, year=2000 + i, genres=("драма",) if i % 2 else (),
              **kw)
        for i in range(сколько)
    ]


@pytest.fixture
def хранилище() -> InMemoryStore:
    store = InMemoryStore("site")
    store.put(WriteToken("run", "site"), тайтлы(30))
    return store


class TestПравоЗаписи:
    def test_без_токена_писать_нельзя(self):
        """«Один модуль не пишет в хранилище другого» выражено кодом, а не соглашением."""
        with pytest.raises(WriteNotPermitted):
            InMemoryStore("site").put(None, тайтлы(1))

    def test_чужой_токен_не_подходит(self):
        with pytest.raises(WriteNotPermitted):
            InMemoryStore("site").put(WriteToken("run", "другой-сайт"), тайтлы(1))


class TestЧтение:
    def test_несуществующий_тайтл(self, хранилище):
        with pytest.raises(TitleNotFound):
            хранилище.get("нет-такого")

    def test_страница_знает_общее_число(self, хранилище):
        страница = хранилище.query(offset=0, limit=10)
        assert len(страница.items) == 10
        assert страница.total == 30
        assert страница.has_more is True

    def test_предел_страницы_не_превышается(self, хранилище):
        assert хранилище.query(limit=10_000).limit == MAX_LIMIT

    def test_фильтр_по_жанру(self, хранилище):
        страница = хранилище.query(genre="драма", limit=MAX_LIMIT)
        assert страница.total == 15

    @pytest.mark.parametrize("kw", [{"offset": -1}, {"limit": 0}])
    def test_негодные_границы_отклоняются(self, хранилище, kw):
        with pytest.raises(ContractError):
            хранилище.query(**kw)

    def test_порядок_записи_сохраняется(self, хранилище):
        имена = [t.name for t in хранилище.query(limit=3).items]
        assert имена == ["Т0", "Т1", "Т2"]


class TestПолнота:
    def test_без_заявленного_числа_полнота_неизвестна(self, хранилище):
        отчёт = хранилище.coverage()
        assert отчёт.source_total is None
        assert отчёт.complete is None

    def test_заявленное_число_делает_недобор_видимым(self):
        store = InMemoryStore("site")
        токен = WriteToken("run", "site")
        store.declare_source_total(токен, 100)
        store.put(токен, тайтлы(30))
        отчёт = store.coverage()
        assert отчёт.complete is False
        assert отчёт.missing == 70


class TestПрофили:
    def test_все_профили_читаются(self):
        профили = load_all(ROOT)
        assert len(профили) >= 6
        assert {p.site_id for p in профили} >= {"lords-01", "yummyani-site", "demo-books"}

    def test_несуществующий_профиль(self):
        with pytest.raises(ProfileNotFound):
            load_profile("нет-такого", ROOT)

    def test_имя_файла_и_идентификатор_обязаны_совпадать(self, tmp_path):
        """Иначе профиль правит не тот сайт, что ожидали."""
        каталог = tmp_path / "config" / "site-profiles"
        каталог.mkdir(parents=True)
        (каталог / "первый.json").write_text('{"site_id": "второй"}', encoding="utf-8")
        with pytest.raises(ProfileInvalid, match="site_id"):
            load_profile("первый", tmp_path)

    def test_источник_без_ссылки_отклоняется(self):
        with pytest.raises(ProfileInvalid, match="без ссылки"):
            NormalizedContentSource(kind="site-engine-api", ref="  ")

    def test_неизвестный_вид_источника_отклоняется(self):
        with pytest.raises(ProfileInvalid, match="не из числа разрешённых"):
            NormalizedContentSource(kind="скрейпинг", ref="откуда-то")

    def test_локальный_загрузчик_закрывает_требование_сам(self):
        профиль = load_profile("lords-01", ROOT)
        assert профиль.normalized_content_kind() == "content-ingestion"

    def test_сайт_без_загрузчика_объявляет_источник(self):
        профиль = load_profile("demo-books", ROOT)
        assert not профиль.has("content-ingestion")
        assert профиль.normalized_content_kind() == "site-engine-api"

    def test_политика_хранения_релизов_одинакова(self):
        assert {p.keep_releases for p in load_all(ROOT)} == {2}
