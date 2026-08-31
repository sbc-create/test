"""Контракт кэша. Каждый запрет соответствует уже случившемуся."""
import pytest

from factory.site_engine.cache import (
    CacheKey,
    CacheOutcome,
    CachePolicy,
    FileVersionCache,
    InMemoryCache,
    InvalidationRequest,
    LastKnownGoodStore,
    RequestCoalescer,
    UncacheableResponse,
    tags_for_event,
)


class Часы:
    def __init__(self) -> None:
        self.момент = 0.0

    def __call__(self) -> float:
        return self.момент

    def сдвинуть(self, на: float) -> None:
        self.момент += на


@pytest.fixture
def часы() -> Часы:
    return Часы()


@pytest.fixture
def кэш(часы) -> InMemoryCache:
    return InMemoryCache(clock=часы)


ПОЛИТИКА = CachePolicy(ttl_seconds=300, stale_while_revalidate_seconds=300, tags=("shelf",))
КЛЮЧ = CacheKey("lords-01", "shelves")


class TestВремяЖизни:
    def test_свежее_значение_отдаётся_без_обращения(self, кэш, часы):
        обращений = []
        кэш.get_or_load(КЛЮЧ, ПОЛИТИКА, lambda: обращений.append(1) or "значение")
        часы.сдвинуть(299)
        результат = кэш.get_or_load(КЛЮЧ, ПОЛИТИКА, lambda: обращений.append(1) or "другое")
        assert результат.outcome is CacheOutcome.HIT
        assert результат.value == "значение"
        assert len(обращений) == 1

    def test_в_окне_обновления_отдаётся_прежнее(self, кэш, часы):
        кэш.get_or_load(КЛЮЧ, ПОЛИТИКА, lambda: "первое")
        часы.сдвинуть(400)
        результат = кэш.get_or_load(КЛЮЧ, ПОЛИТИКА, lambda: "второе")
        assert результат.outcome is CacheOutcome.STALE
        assert результат.value == "первое"
        кэш.wait_for_refreshes()
        assert кэш.get_or_load(КЛЮЧ, ПОЛИТИКА, lambda: "третье").value == "второе"

    def test_посетитель_действительно_не_ждёт_источник(self, кэш, часы):
        """Утверждение проверяется измерением, а не чтением кода.

        Первая редакция вызывала загрузчик прямо в этой ветке и получалась
        худшая из возможных: посетитель ждал источник и всё равно получал
        устаревшее значение. Прежний тест этого не ловил — он сверял только
        отданное значение, то есть подтверждал реализацию, а не свойство.
        """
        import time

        def медленный():
            time.sleep(0.3)
            return "новое"

        кэш.get_or_load(КЛЮЧ, ПОЛИТИКА, медленный)
        часы.сдвинуть(400)
        начало = time.monotonic()
        результат = кэш.get_or_load(КЛЮЧ, ПОЛИТИКА, медленный)
        ожидание = time.monotonic() - начало
        assert результат.outcome is CacheOutcome.STALE
        assert ожидание < 0.1, f"посетитель прождал {ожидание:.3f} с при источнике в 0,3 с"
        кэш.wait_for_refreshes()

    def test_окно_обновления_не_плодит_потоки(self, кэш, часы):
        """Иначе популярная страница в момент устаревания порождает лавину потоков."""
        import threading
        import time

        обращения = []

        def медленный():
            обращения.append(threading.current_thread().name)
            time.sleep(0.2)
            return "новое"

        кэш.get_or_load(КЛЮЧ, ПОЛИТИКА, медленный)
        часы.сдвинуть(400)
        for _ in range(10):
            кэш.get_or_load(КЛЮЧ, ПОЛИТИКА, медленный)
        кэш.wait_for_refreshes()
        assert len(обращения) == 2, f"обращений к источнику: {len(обращения)}"

    def test_за_окном_ждём_свежего(self, кэш, часы):
        кэш.get_or_load(КЛЮЧ, ПОЛИТИКА, lambda: "первое")
        часы.сдвинуть(1000)
        результат = кэш.get_or_load(КЛЮЧ, ПОЛИТИКА, lambda: "второе")
        assert результат.outcome is CacheOutcome.MISS
        assert результат.value == "второе"

    def test_бессрочный_кэш_запрещён(self):
        with pytest.raises(ValueError, match="бессрочного"):
            CachePolicy(ttl_seconds=0)


class TestПоследнееХорошееЗначение:
    def test_отказ_источника_не_стирает_хорошее(self, кэш, часы):
        кэш.get_or_load(КЛЮЧ, ПОЛИТИКА, lambda: "хорошее")
        часы.сдвинуть(1000)

        def падает():
            raise UncacheableResponse("источник недоступен")

        результат = кэш.get_or_load(КЛЮЧ, ПОЛИТИКА, падает)
        assert результат.outcome is CacheOutcome.ERROR_KEPT_GOOD
        assert результат.value == "хорошее"

    def test_без_единого_удачного_ответа_отказ_виден(self, кэш):
        def падает():
            raise UncacheableResponse("источник недоступен")

        with pytest.raises(UncacheableResponse):
            кэш.get_or_load(КЛЮЧ, ПОЛИТИКА, падает)

    def test_отказ_при_фоновом_обновлении_не_портит_хорошее(self, кэш, часы):
        кэш.get_or_load(КЛЮЧ, ПОЛИТИКА, lambda: "хорошее")
        часы.сдвинуть(400)

        def падает():
            raise UncacheableResponse("источник недоступен")

        assert кэш.get_or_load(КЛЮЧ, ПОЛИТИКА, падает).value == "хорошее"
        кэш.wait_for_refreshes()
        часы.сдвинуть(1)
        assert кэш.get_or_load(КЛЮЧ, ПОЛИТИКА, падает).value == "хорошее"


class TestОбластьСайта:
    def test_сброс_не_задевает_соседний_сайт(self, кэш):
        свой = CacheKey("lords-01", "shelves")
        чужой = CacheKey("lords-02", "shelves")
        кэш.get_or_load(свой, ПОЛИТИКА, lambda: "своё")
        кэш.get_or_load(чужой, ПОЛИТИКА, lambda: "чужое")
        сброшено = кэш.invalidate(InvalidationRequest("lords-01", ("shelf",), "тест"))
        assert сброшено == ("lords-01:shelves",)
        assert кэш.get_or_load(чужой, ПОЛИТИКА, lambda: "новое").value == "чужое"

    def test_ключи_разных_сайтов_различны(self):
        assert str(CacheKey("a", "s")) != str(CacheKey("b", "s"))


class TestСухойПрогонИнвалидации:
    def test_сухой_прогон_показывает_но_не_сбрасывает(self, кэш):
        кэш.get_or_load(КЛЮЧ, ПОЛИТИКА, lambda: "значение")
        затронуто = кэш.invalidate(InvalidationRequest("lords-01", ("shelf",), "проба",
                                                       dry_run=True))
        assert затронуто == ("lords-01:shelves",)
        assert кэш.get_or_load(КЛЮЧ, ПОЛИТИКА, lambda: "другое").value == "значение"


class TestСхлопываниеПромахов:
    def test_одновременные_промахи_дают_одно_обращение(self, кэш):
        import threading

        обращения = []

        def медленно():
            обращения.append(1)
            import time

            time.sleep(0.05)
            return "значение"

        потоки = [threading.Thread(target=lambda: кэш.get_or_load(КЛЮЧ, ПОЛИТИКА, медленно))
                  for _ in range(5)]
        for t in потоки:
            t.start()
        for t in потоки:
            t.join()
        assert len(обращения) == 1


class TestКэшПоВерсииФайла:
    def test_разбор_повторяется_только_после_изменения(self):
        кэш = FileVersionCache()
        ключ = CacheKey("yummy", "watcher")
        разборы = []

        def разобрать():
            разборы.append(1)
            return "разобрано"

        кэш.get_or_load(ключ, "версия-1", разобрать)
        кэш.get_or_load(ключ, "версия-1", разобрать)
        assert len(разборы) == 1
        кэш.get_or_load(ключ, "версия-2", разобрать)
        assert len(разборы) == 2, "новая версия файла обязана быть разобрана заново"

    def test_свежесть_не_зависит_от_часов(self):
        """Новая серия появляется тем же запросом, а не через TTL."""
        кэш = FileVersionCache()
        ключ = CacheKey("yummy", "watcher")
        кэш.get_or_load(ключ, "v1", lambda: "старое")
        assert кэш.get_or_load(ключ, "v2", lambda: "новое") == "новое"


class TestНаблюдаемость:
    def test_счётчики_различают_исходы(self, кэш, часы):
        кэш.get_or_load(КЛЮЧ, ПОЛИТИКА, lambda: "значение")
        кэш.get_or_load(КЛЮЧ, ПОЛИТИКА, lambda: "значение")
        часы.сдвинуть(400)
        кэш.get_or_load(КЛЮЧ, ПОЛИТИКА, lambda: "значение")
        статистика = кэш.stats()
        assert статистика["miss"] == 1
        assert статистика["hit"] == 1
        assert статистика["stale"] == 1


class TestСвязьССобытиями:
    def test_выход_серии_сбрасывает_полку_новых_серий(self):
        assert "shelf:new-episodes" in tags_for_event("EPISODE_ADDED")

    def test_неизвестное_событие_ничего_не_сбрасывает(self):
        assert tags_for_event("ЧТО-ТО-НЕ-ТО") == ()


class TestВспомогательные:
    def test_хранилище_последнего_хорошего_помнит_по_ключу(self):
        store = LastKnownGoodStore()
        store.remember(CacheKey("s", "a"), 1)
        assert store.recall(CacheKey("s", "a")) == 1
        assert store.recall(CacheKey("s", "b")) is None

    def test_замок_на_ключ_один_и_тот_же(self):
        c = RequestCoalescer()
        assert c.lock_for(CacheKey("s", "a")) is c.lock_for(CacheKey("s", "a"))
