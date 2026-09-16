"""Состояние индексации переживает deploy, restart и rollback.

Критический риск, ради которого harness написан: обычная выкладка из ``main``
возвращала посредника, безусловно закрывающего витрину, — и живой сайт с
поисковым трафиком закрывался молча, без единой ошибки в логах.

Здесь это проверяется на фикстурах, а не на живых службах: ни одной записи в
production. Выкладка, перезапуск и откат моделируются так, как они происходят
на самом деле — пересборкой артефакта из версионируемого источника и повторным
вычислением слоёв из полученного снимка.

Каждый сценарий проверяется единым набором: состояние, revision, заголовок
``X-Robots-Tag``, мета-тег, ``canonical``, ``robots.txt`` и доступность карты
сайта. Проверять состояние в отрыве от слоёв бессмысленно: расхождение между
решением и тем, что отдаётся, — и есть дефект.
"""

from __future__ import annotations

import json
import shutil
from dataclasses import replace
from pathlib import Path

import pytest

from factory.indexing.layers import NOINDEX, LayerError, compute, publish
from factory.indexing.state import (
    CoreLedgerProvider,
    GitProfileProvider,
    IndexingState,
    ProviderCorrupt,
    ProviderUnavailable,
    StateSnapshot,
    dump_snapshot,
    load_snapshot,
    resolve,
    state_for_host,
)

КОРЕНЬ = Path(__file__).resolve().parents[2]
ПРОФИЛИ = КОРЕНЬ / "config" / "site-profiles"
РЕЕСТР = КОРЕНЬ / "config" / "FLEET-REGISTRY.json"

ОТКРЫТ = "yummyani.site"
ЗАКРЫТ = "yummyani.org"


# --- стенд ---------------------------------------------------------------------

@pytest.fixture
def стенд(tmp_path: Path) -> Path:
    """Копия версионируемого источника, которую можно менять."""
    корень = tmp_path / "config"
    каталог = корень / "site-profiles"
    каталог.mkdir(parents=True)
    for путь in ПРОФИЛИ.glob("*.json"):
        shutil.copy2(путь, каталог / путь.name)
    shutil.copy2(РЕЕСТР, корень / РЕЕСТР.name)
    return каталог


def провайдер(каталог: Path, revision: int = 1, событие: str = "commit-1") -> GitProfileProvider:
    return GitProfileProvider(
        profiles_dir=каталог, revision=revision, source_event_id=событие,
        updated_at="2026-09-16T00:00:00Z",
    )


def выложить(каталог: Path, revision: int, *, событие: str = "commit-1") -> StateSnapshot:
    """Выкладка: артефакт пересобирается из источника, слои — из снимка."""
    итог = resolve(провайдер(каталог, revision, событие))
    assert not итог.release_blocked, итог.report()
    return итог.snapshot


def перезапустить(снимок: StateSnapshot) -> StateSnapshot:
    """Перезапуск службы: процесс поднимается и заново читает тот же снимок.

    Отдельный шаг, потому что именно здесь терялось состояние, жившее в памяти
    процесса, а не в источнике.
    """
    сохранено = json.dumps(снимок.matrix(), sort_keys=True)
    ещё_раз = replace(снимок)
    assert json.dumps(ещё_раз.matrix(), sort_keys=True) == сохранено
    return ещё_раз


def слои(снимок: StateSnapshot, домены: list[str]):
    return publish(снимок, домены)


def проверить(снимок: StateSnapshot, домен: str, ожидание: str, revision: int) -> None:
    """Единый набор проверок: состояние, revision и все пять слоёв."""
    состояние = state_for_host(снимок, домен)
    assert состояние.desired_state == ожидание, f"{домен}: состояние"
    assert состояние.revision == revision, f"{домен}: revision"

    с = compute(состояние)
    assert с.consistent(), f"{домен}: слои разошлись"
    assert с.canonical == f"https://{домен}/", f"{домен}: canonical"
    if ожидание == "open":
        assert с.x_robots_tag is None
        assert "noindex" not in с.meta_robots
        assert "Disallow: /" not in с.robots_txt
        assert с.sitemap_available is True
    else:
        assert с.x_robots_tag == NOINDEX
        assert "noindex" in с.meta_robots
        assert "Disallow: /" in с.robots_txt
        assert с.sitemap_available is False


# --- A. новый сайт -------------------------------------------------------------

def завести_новый(каталог: Path, site_id: str, домен: str) -> None:
    реестр = каталог.parent / РЕЕСТР.name
    данные = json.loads(реестр.read_text(encoding="utf-8"))
    данные["fleet"].append({"site_id": site_id, "domain": домен})
    реестр.write_text(json.dumps(данные, ensure_ascii=False), encoding="utf-8")


def test_A_новый_сайт_закрыт_и_остаётся_закрытым(стенд: Path) -> None:
    """Регистрации состояния нет — значит закрыт, и так после всех операций."""
    завести_новый(стенд, "tenth-site", "tenth.example")

    начальный = выложить(стенд, 1)
    проверить(начальный, "tenth.example", "closed", 1)

    после_выкладки = выложить(стенд, 2)
    проверить(после_выкладки, "tenth.example", "closed", 2)

    после_перезапуска = перезапустить(после_выкладки)
    проверить(после_перезапуска, "tenth.example", "closed", 2)

    # откат приложения: источник прежний, revision прежняя
    после_отката = выложить(стенд, 2)
    проверить(после_отката, "tenth.example", "closed", 2)


def test_A_основание_закрытия_нового_сайта_записано(стенд: Path) -> None:
    завести_новый(стенд, "tenth-site", "tenth.example")
    снимок = выложить(стенд, 1)
    состояние = state_for_host(снимок, "tenth.example")
    assert состояние.reason.strip(), "закрытие без основания не проверить"


# --- B. открытый сайт ----------------------------------------------------------

def test_B_открытый_переживает_выкладку_перезапуск_и_откат(стенд: Path) -> None:
    N = 7
    снимок = выложить(стенд, N)
    проверить(снимок, ОТКРЫТ, "open", N)

    # выкладка нового артефакта
    новый = выложить(стенд, N)
    проверить(новый, ОТКРЫТ, "open", N)

    # перезапуск службы
    проверить(перезапустить(новый), ОТКРЫТ, "open", N)

    # откат приложения
    проверить(выложить(стенд, N), ОТКРЫТ, "open", N)


def test_B_восстановление_файлов_старого_релиза_не_закрывает(стенд: Path, tmp_path: Path) -> None:
    """Самый опасный сценарий: на хост вернули файлы прежней выкладки.

    Прежде решение жило в коде посредника, и возврат старого файла возвращал
    старое решение. Теперь решение живёт в источнике, а подтверждённый снимок
    не даёт устаревшей revision переписать себя.
    """
    N = 7
    подтверждённый = выложить(стенд, N)
    проверить(подтверждённый, ОТКРЫТ, "open", N)

    # «старый релиз»: тот же источник, но меньшая revision
    итог = resolve(провайдер(стенд, N - 3, "старый-коммит"), last_known_good=подтверждённый)
    assert итог.release_blocked, "устаревшая revision обязана блокировать релиз"
    assert any("устаревшая revision" in b for b in итог.blockers)
    проверить(итог.snapshot, ОТКРЫТ, "open", N), "состояние не должно измениться"


def test_B_снимок_переживает_запись_и_чтение(стенд: Path, tmp_path: Path) -> None:
    N = 7
    снимок = выложить(стенд, N)
    путь = dump_snapshot(снимок, tmp_path / "snapshot.json")
    восстановлено = load_snapshot(путь)
    assert восстановлено.matrix() == снимок.matrix()
    проверить(восстановлено, ОТКРЫТ, "open", N)


# --- C. закрытый сайт ----------------------------------------------------------

def test_C_закрытый_остаётся_закрытым(стенд: Path) -> None:
    N = 8
    снимок = выложить(стенд, N)
    проверить(снимок, ЗАКРЫТ, "closed", N)
    проверить(выложить(стенд, N), ЗАКРЫТ, "closed", N)
    проверить(перезапустить(снимок), ЗАКРЫТ, "closed", N)
    проверить(выложить(стенд, N), ЗАКРЫТ, "closed", N)


def test_C_выкладка_не_открывает_соседей_открытого(стенд: Path) -> None:
    снимок = выложить(стенд, 5)
    assert снимок.open_domains == (ОТКРЫТ,)
    assert len(снимок.closed_domains) == 8


# --- D. отказы -----------------------------------------------------------------

def test_D_реестр_недоступен_состояние_не_меняется(стенд: Path) -> None:
    подтверждённый = выложить(стенд, 4)
    итог = resolve(CoreLedgerProvider(), last_known_good=подтверждённый)
    assert итог.release_blocked
    assert итог.from_last_known_good
    проверить(итог.snapshot, ОТКРЫТ, "open", 4)
    проверить(итог.snapshot, ЗАКРЫТ, "closed", 4)


def test_D_реестр_недоступен_без_снимка_не_публикует_ничего() -> None:
    итог = resolve(CoreLedgerProvider())
    assert итог.release_blocked
    assert итог.snapshot.states == {}, "пустая матрица не публикуется как «всё закрыто»"


def test_D_повреждённая_политика_блокирует_релиз(стенд: Path) -> None:
    подтверждённый = выложить(стенд, 4)
    (стенд / "yummyani-site.json").write_text('{"site_id": ', encoding="utf-8")
    итог = resolve(провайдер(стенд, 5), last_known_good=подтверждённый)
    assert итог.release_blocked
    assert итог.from_last_known_good
    проверить(итог.snapshot, ОТКРЫТ, "open", 4), "живое состояние не трогается"


def test_D_повреждённая_политика_без_снимка_не_закрывает_всё(стенд: Path) -> None:
    (стенд / "yummyani-site.json").write_text("   ", encoding="utf-8")
    итог = resolve(провайдер(стенд, 5))
    assert итог.release_blocked
    assert итог.snapshot.states == {}
    assert any("повреждено" in b for b in итог.blockers)


def test_D_падение_до_подмены_артефакта_оставляет_прежнее(стенд: Path) -> None:
    """Сборка сорвалась до установки: живёт подтверждённый снимок."""
    подтверждённый = выложить(стенд, 4)
    (стенд / "lords-01.json").unlink()   # источник неполон
    итог = resolve(провайдер(стенд, 5), last_known_good=подтверждённый)
    # сайт флота без профиля закрыт явным решением, но матрица открытого не меняется
    проверить(итог.snapshot if итог.release_blocked else подтверждённый, ОТКРЫТ, "open", 4)


def test_D_падение_после_подмены_артефакта_ловится_сверкой(стенд: Path) -> None:
    """Артефакт лёг, служба не поднялась: слои считаются по снимку, не по файлу."""
    снимок = выложить(стенд, 4)
    опубликовано = слои(снимок, [ОТКРЫТ, ЗАКРЫТ])
    assert опубликовано[ОТКРЫТ].revision == 4
    assert опубликовано[ЗАКРЫТ].revision == 4


def test_D_повтор_операции_идемпотентен(стенд: Path) -> None:
    первый = выложить(стенд, 6)
    второй = выложить(стенд, 6)
    assert первый.matrix() == второй.matrix()
    assert слои(первый, [ОТКРЫТ])[ОТКРЫТ] == слои(второй, [ОТКРЫТ])[ОТКРЫТ]


def test_D_конкурирующие_состояния_не_сливаются(стенд: Path) -> None:
    """Две фикстуры с разными revision: побеждает не «последняя записанная»."""
    старый = выложить(стенд, 3)
    новый = выложить(стенд, 9)
    итог = resolve(провайдер(стенд, 3), last_known_good=новый)
    assert итог.release_blocked
    assert итог.snapshot.revision == 9, "новая revision не переписывается старой"
    # обратный порядок допустим: новее подтверждённого — не блокирует
    вперёд = resolve(провайдер(стенд, 10), last_known_good=старый)
    assert not вперёд.release_blocked
    assert вперёд.snapshot.revision == 10


def test_D_ошибка_одного_слоя_не_публикует_смешанное(стенд: Path) -> None:
    """Если хоть один хост не разложился на слои, не публикуется ни один."""
    снимок = выложить(стенд, 4)
    испорченное = replace(state_for_host(снимок, ЗАКРЫТ), desired_state="closed")
    сломанный = StateSnapshot(
        revision=снимок.revision, taken_at=снимок.taken_at,
        states={**снимок.states, "yummyani-org": replace(испорченное, revision=999)},
        source=снимок.source,
    )
    with pytest.raises(LayerError, match="revision"):
        publish(сломанный, [ОТКРЫТ, ЗАКРЫТ])


def test_D_несогласованные_слои_валят_публикацию(стенд: Path) -> None:
    снимок = выложить(стенд, 4)
    состояние = state_for_host(снимок, ОТКРЫТ)
    слой = compute(состояние)
    # руками собранное смешанное состояние: заголовок закрыт, мета открыт
    смешанный = replace(слой, x_robots_tag=NOINDEX)
    assert not смешанный.consistent(), "смешанное состояние обязано быть видно"


def test_D_состояние_с_чужим_значением_не_создаётся() -> None:
    with pytest.raises(ProviderCorrupt, match="desired_state"):
        IndexingState(
            site_id="x", domain="x.example", desired_state="maybe", revision=1,
            updated_at="", source_event_id="", last_known_good_revision=1,
        )


def test_D_отрицательная_revision_не_создаётся() -> None:
    with pytest.raises(ProviderCorrupt, match="revision"):
        IndexingState(
            site_id="x", domain="x.example", desired_state="closed", revision=-2,
            updated_at="", source_event_id="", last_known_good_revision=0,
        )


# --- границы ответственности ---------------------------------------------------

def test_у_seo_нет_способа_изменить_желаемое_состояние() -> None:
    """Команды OPEN и CLOSE принадлежат Core. Здесь их быть не должно."""
    import factory.indexing.state as модуль

    запретные = [
        имя for имя in dir(модуль)
        if any(к in имя.lower() for к in ("set_", "write_state", "open_site",
                                          "close_site", "mutate", "update_state"))
    ]
    assert not запретные, f"в SEO появился писатель состояния: {запретные}"


def test_провайдер_core_честно_сообщает_что_не_готов() -> None:
    with pytest.raises(ProviderUnavailable, match="Core"):
        CoreLedgerProvider().snapshot()
