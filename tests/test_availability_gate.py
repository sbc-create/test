"""Карантин в публикации: что исчезает из витрины, что остаётся внутри."""

import json
import os
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from factory.lords import availability_gate as гейт  # noqa: E402
from factory.lords import source_availability as дост  # noqa: E402

КОРЕНЬ = Path(__file__).resolve().parents[1]

ЖИВОЙ = "0191511d-11fe-7daf-aebd-dfe84c6dbec7"
МЁРТВЫЙ = "019c047b-4f91-7b9b-aa1a-68c9fe926926"
НЕИЗВЕСТНЫЙ = "019d2028-88e3-79a4-9021-17173e4324a1"


def каталог_фикстура() -> dict:
    return {
        "site": "lords-01",
        "count": 3,
        "items": [
            {"slug": "zhivoy", "title": "Живой", "year": 2024, "kind": "Фильм",
             "poster": "p1", "url": "/title/zhivoy/"},
            {"slug": "mertvyy", "title": "Мёртвый", "year": 2023, "kind": "Фильм",
             "poster": "p2", "url": "/title/mertvyy/"},
            {"slug": "neizvestnyy", "title": "Неизвестный", "year": 2022,
             "kind": "Сериал", "poster": "p3", "url": "/title/neizvestnyy/"},
        ],
    }


def подробности_фикстура() -> dict:
    return {
        "catalog_revision": "r1",
        "details": {
            "zhivoy": {"id": ЖИВОЙ, "name": "Живой", "type": "movie",
                       "recommendation_ids": [МЁРТВЫЙ, НЕИЗВЕСТНЫЙ]},
            "mertvyy": {"id": МЁРТВЫЙ, "name": "Мёртвый", "type": "movie",
                        "recommendation_ids": [ЖИВОЙ]},
            "neizvestnyy": {"id": НЕИЗВЕСТНЫЙ, "name": "Неизвестный", "type": "tv",
                            "seasons": [{"n": 1, "eps": 2, "avail": 2}],
                            "recommendation_ids": [ЖИВОЙ, МЁРТВЫЙ]},
        },
    }


def статусы() -> dict[str, str]:
    return {ЖИВОЙ: дост.AVAILABLE,
            МЁРТВЫЙ: дост.SOURCE_UNAVAILABLE,
            НЕИЗВЕСТНЫЙ: дост.UNKNOWN}


def применить(включено: bool):
    карта = статусы()
    return гейт.применить(каталог_фикстура(), подробности_фикстура(),
                          lambda ид: карта.get(ид, дост.UNKNOWN),
                          включено=включено, site="lords-01")


# --- выключенный флаг ------------------------------------------------------

def test_флаг_выключен_каталог_не_меняется():
    каталог, подробности, отчёт = применить(False)
    assert [э["slug"] for э in каталог["items"]] == ["zhivoy", "mertvyy", "neizvestnyy"]
    assert каталог["count"] == 3
    assert каталог[гейт.ПОЛЕ_ФЛАГА] is False
    assert отчёт.enabled is False


def test_флаг_выключен_статусы_всё_равно_проставлены():
    """Внутренний каталог знает правду даже тогда, когда витрина её не показывает."""
    _, подробности, отчёт = применить(False)
    статусы_записей = {с: з[гейт.ПОЛЕ_СТАТУСА]
                       for с, з in подробности["details"].items()}
    assert статусы_записей == {"zhivoy": дост.AVAILABLE,
                               "mertvyy": дост.SOURCE_UNAVAILABLE,
                               "neizvestnyy": дост.UNKNOWN}
    assert отчёт.quarantined_titles == 1


def test_флаг_выключен_рекомендации_не_трогаются():
    _, подробности, отчёт = применить(False)
    assert подробности["details"]["zhivoy"]["recommendation_ids"] == [МЁРТВЫЙ, НЕИЗВЕСТНЫЙ]
    assert отчёт.recommendation_links_removed == 0


# --- включённый флаг -------------------------------------------------------

def test_карантин_исчезает_из_публичного_набора():
    каталог, _, отчёт = применить(True)
    слаги = [э["slug"] for э in каталог["items"]]
    assert "mertvyy" not in слаги
    assert отчёт.quarantined_slugs == ["mertvyy"]


def test_рабочие_карточки_не_теряются():
    каталог, _, _ = применить(True)
    слаги = {э["slug"] for э in каталог["items"]}
    assert {"zhivoy", "neizvestnyy"} <= слаги
    assert len(слаги) == 2


def test_запись_остаётся_во_внутреннем_каталоге():
    _, подробности, _ = применить(True)
    assert "mertvyy" in подробности["details"]
    assert подробности["details"]["mertvyy"][гейт.ПОЛЕ_СТАТУСА] == дост.SOURCE_UNAVAILABLE
    assert подробности["details"]["mertvyy"]["name"] == "Мёртвый"


def test_ссылки_на_карантин_убраны_из_рекомендаций():
    """Иначе одна спрятанная карточка превращается в десяток битых ссылок."""
    _, подробности, отчёт = применить(True)
    for слаг, запись in подробности["details"].items():
        assert МЁРТВЫЙ not in (запись.get("recommendation_ids") or []), слаг
    assert подробности["details"]["zhivoy"]["recommendation_ids"] == [НЕИЗВЕСТНЫЙ]
    assert отчёт.recommendation_links_removed == 2


def test_count_и_контрольная_сумма_пересчитаны():
    каталог, _, отчёт = применить(True)
    assert каталог["count"] == 2
    assert каталог["published_checksum"] == гейт.контрольная_сумма(["zhivoy", "neizvestnyy"])
    assert отчёт.published_checksum == каталог["published_checksum"]


def test_контрольная_сумма_не_зависит_от_порядка():
    assert (гейт.контрольная_сумма(["b", "a"]) == гейт.контрольная_сумма(["a", "b"]))


def test_карта_сайта_строится_из_опубликованного_набора():
    """Карта сайта собирается из `items`, поэтому карантин в неё не попадает."""
    каталог, _, _ = применить(True)
    карта = [f"https://lordfilm47.space{э['url']}" for э in каталог["items"]]
    assert not [u for u in карта if "mertvyy" in u]
    assert len(карта) == 2


def test_неизвестный_статус_не_снимает_карточку():
    каталог, _, _ = применить(True)
    assert "neizvestnyy" in {э["slug"] for э in каталог["items"]}


def test_покрытие_считается_по_опубликованным():
    _, _, отчёт = применить(True)
    # Опубликованы две записи, достоверно играет одна: неизвестность в
    # числитель не идёт.
    assert отчёт.published_titles == 2
    assert отчёт.available_titles == 1
    assert отчёт.unknown_titles == 1
    assert отчёт.как_словарь()["PUBLISHED_PLAYABLE_COVERAGE"] == 50.0


def test_исходные_словари_не_изменяются():
    исходный = каталог_фикстура()
    карта = статусы()
    гейт.применить(исходный, подробности_фикстура(), lambda ид: карта.get(ид, дост.UNKNOWN),
                   включено=True, site="lords-01")
    assert len(исходный["items"]) == 3


# --- доказательный снимок --------------------------------------------------

def test_снимок_разрыва_поставщика_по_шести_витринам():
    """Зафиксированный разрыв: 316 URL, 74 тайтла, 86 пар «профиль + идентификатор».

    Три числа намеренно разные. URL считаются по витринам, тайтлы — по
    произведениям, записи реестра — по парам с профилем: двенадцать аниме
    проверяются и под Lords, и под YamiAnime.
    """
    файл = (КОРЕНЬ / "artifacts" / "evidence" / "arch-player-content-010"
            / "residual-no-content.json")
    данные = json.loads(файл.read_text(encoding="utf-8"))
    остаток = данные["residual"]
    по_витринам: dict[str, int] = {}
    for r in остаток:
        по_витринам[r["domain"]] = по_витринам.get(r["domain"], 0) + 1

    assert по_витринам == {
        "lordfilm47.space": 74, "lordserial33.biz": 72,
        "1lordserials1.online": 72, "zonafilm.space": 74,
        "animedia.icu": 12, "animedia.space": 12,
    }
    assert len(остаток) == 316
    assert len({r["slug"] for r in остаток}) == 74
    assert all(r["provider_http"] == 204 for r in остаток)


# --- живой рендерер --------------------------------------------------------

def свободный_порт() -> int:
    с = socket.socket()
    с.bind(("127.0.0.1", 0))
    порт = с.getsockname()[1]
    с.close()
    return порт


@pytest.fixture()
def витрина(tmp_path):
    """Поднимает настоящий рендерер на фикстурном каталоге.

    Проверять код ответа на живом сервере, а не на функции: именно здесь
    отличается настоящая 404 от мягкой двухсотки с сообщением об ошибке.
    """
    каталог, подробности, _ = применить(True)
    (tmp_path / "fx-catalog.json").write_text(
        json.dumps(каталог, ensure_ascii=False), encoding="utf-8")
    (tmp_path / "fx-details.json").write_text(
        json.dumps(подробности, ensure_ascii=False), encoding="utf-8")
    манифест = tmp_path / "manifest.json"
    манифест.write_text(json.dumps({
        "schema_version": 1, "template_family": "lords", "design_version": "1.1.0",
        "source_commit": "test", "build_id": "test", "artifact_sha256": "0" * 64,
        "profile": "test", "built_at": "2026-01-01T00:00:00Z",
    }), encoding="utf-8")

    # Рендерер подключает SEO-слой файлом рядом с собой. В репозитории его нет
    # (он принадлежит отдельному контуру), а предмет этого теста — маршруты и
    # коды ответа. Поэтому рядом кладётся заглушка: импорт проходит, поведение
    # маршрутов остаётся настоящим.
    (tmp_path / "seo_layer.py").write_text(
        "def обогатить(тело, тип, **_):\n    return тело\n", encoding="utf-8")

    порт = свободный_порт()
    окружение = dict(os.environ)
    окружение["PYTHONPATH"] = str(tmp_path) + os.pathsep + окружение.get("PYTHONPATH", "")
    окружение.update({
        "LORDS_CATALOG": str(tmp_path / "fx-catalog.json"),
        "LORDS_DETAILS": str(tmp_path / "fx-details.json"),
        "LORDS_TEMPLATE_MANIFEST": str(манифест),
        "LORDS_SITE_NAME": "Fixture",
        "LORDS_LEGACY_ROOT": str(tmp_path / "legacy"),
        "LORDS_SITEMAP_DIR": "",
    })
    процесс = subprocess.Popen(
        [sys.executable, str(КОРЕНЬ / "automation" / "host" / "lords-frontend.py"),
         "--port", str(порт)],
        env=окружение, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    предел = time.time() + 30
    while time.time() < предел:
        try:
            urllib.request.urlopen(f"http://127.0.0.1:{порт}/", timeout=2).read()
            break
        except urllib.error.HTTPError:
            break
        except Exception:
            if процесс.poll() is not None:
                вывод = (процесс.stdout.read() or b"").decode("utf-8", "replace")
                pytest.fail(f"рендерер не поднялся: {вывод[:500]}")
            time.sleep(0.3)
    else:
        процесс.kill()
        pytest.fail("рендерер не ответил за 30 секунд")
    yield порт
    процесс.kill()
    процесс.wait(timeout=10)


def код(порт: int, путь: str) -> int:
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{порт}{путь}", timeout=10) as о:
            return о.status
    except urllib.error.HTTPError as e:
        return e.code


@pytest.mark.parametrize("путь", [
    "/title/mertvyy/",
    "/title/mertvyy/season-1/",
    "/title/mertvyy/season-1/episode-1/",
])
def test_карантин_отдаёт_настоящую_404(витрина, путь):
    assert код(витрина, путь) == 404


def test_соседние_рабочие_адреса_отдают_200(витрина):
    assert код(витрина, "/title/zhivoy/") == 200
    assert код(витрина, "/title/neizvestnyy/") == 200
    assert код(витрина, "/title/neizvestnyy/season-1/episode-1/") == 200


def test_главная_не_показывает_карантин(витрина):
    with urllib.request.urlopen(f"http://127.0.0.1:{витрина}/", timeout=10) as о:
        страница = о.read().decode("utf-8", "replace")
    assert "mertvyy" not in страница
    assert "zhivoy" in страница


@pytest.fixture()
def витрина_с_устаревшим_каталогом(tmp_path):
    """Каталог ещё перечисляет запись, подробности уже знают о карантине.

    Это не выдуманный случай: каталог и подробности выкладываются двумя
    файлами, и между ними есть окно. В этом окне посетитель не должен увидеть
    карточку с плеером, которому нечего показать.
    """
    _, подробности, _ = применить(True)
    каталог = каталог_фикстура()
    каталог[гейт.ПОЛЕ_ФЛАГА] = True
    (tmp_path / "fx-catalog.json").write_text(
        json.dumps(каталог, ensure_ascii=False), encoding="utf-8")
    (tmp_path / "fx-details.json").write_text(
        json.dumps(подробности, ensure_ascii=False), encoding="utf-8")
    (tmp_path / "manifest.json").write_text(json.dumps({
        "schema_version": 1, "template_family": "lords", "design_version": "1.1.0",
        "source_commit": "test", "build_id": "test", "artifact_sha256": "0" * 64,
        "profile": "test", "built_at": "2026-01-01T00:00:00Z",
    }), encoding="utf-8")
    (tmp_path / "seo_layer.py").write_text(
        "def обогатить(тело, тип, **_):\n    return тело\n", encoding="utf-8")

    порт = свободный_порт()
    окружение = dict(os.environ)
    окружение.update({
        "LORDS_CATALOG": str(tmp_path / "fx-catalog.json"),
        "LORDS_DETAILS": str(tmp_path / "fx-details.json"),
        "LORDS_TEMPLATE_MANIFEST": str(tmp_path / "manifest.json"),
        "LORDS_SITE_NAME": "Fixture",
        "LORDS_LEGACY_ROOT": str(tmp_path / "legacy"),
        "LORDS_SITEMAP_DIR": "",
        "PYTHONPATH": str(tmp_path) + os.pathsep + окружение.get("PYTHONPATH", ""),
    })
    процесс = subprocess.Popen(
        [sys.executable, str(КОРЕНЬ / "automation" / "host" / "lords-frontend.py"),
         "--port", str(порт)],
        env=окружение, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    предел = time.time() + 30
    while time.time() < предел:
        try:
            urllib.request.urlopen(f"http://127.0.0.1:{порт}/", timeout=2).read()
            break
        except urllib.error.HTTPError:
            break
        except Exception:
            if процесс.poll() is not None:
                вывод = (процесс.stdout.read() or b"").decode("utf-8", "replace")
                pytest.fail(f"рендерер не поднялся: {вывод[:500]}")
            time.sleep(0.3)
    else:
        процесс.kill()
        pytest.fail("рендерер не ответил за 30 секунд")
    yield порт
    процесс.kill()
    процесс.wait(timeout=10)


@pytest.mark.parametrize("путь", [
    "/title/mertvyy/",
    "/title/mertvyy/season-1/",
    "/title/mertvyy/season-1/episode-1/",
])
def test_устаревший_каталог_всё_равно_даёт_404(витрина_с_устаревшим_каталогом, путь):
    assert код(витрина_с_устаревшим_каталогом, путь) == 404


def test_устаревший_каталог_не_ломает_рабочие_адреса(витрина_с_устаревшим_каталогом):
    assert код(витрина_с_устаревшим_каталогом, "/title/zhivoy/") == 200


# --- пер-доменный флаг -----------------------------------------------------

ВИТРИНЫ = ("lords-01", "lords-02", "lords-03", "zona-01", "animedia-01", "animedia-02")


def загрузить_модуль_применения():
    """CLI лежит вне пакета, поэтому подключается по пути."""
    import importlib.util
    путь = КОРЕНЬ / "automation" / "host" / "nova-availability-apply.py"
    спец = importlib.util.spec_from_file_location("nova_availability_apply", путь)
    модуль = importlib.util.module_from_spec(спец)
    sys.modules["nova_availability_apply"] = модуль
    спец.loader.exec_module(модуль)
    return модуль


@pytest.mark.parametrize("сайт", ВИТРИНЫ)
def test_флаг_выключен_во_всех_профилях(сайт):
    """Включение карантина — отдельное решение владельца, а не состояние по умолчанию."""
    профиль = json.loads((КОРЕНЬ / "config" / "site-profiles" / f"{сайт}.json")
                         .read_text(encoding="utf-8"))
    assert профиль["feature_flags"]["availability_gate_enabled"] is False


@pytest.mark.parametrize("сайт", ВИТРИНЫ)
def test_читатель_флага_видит_выключено(сайт):
    модуль = загрузить_модуль_применения()
    assert модуль.флаг_витрины(сайт) is False


def test_флаг_неизвестной_витрины_выключен():
    модуль = загрузить_модуль_применения()
    assert модуль.флаг_витрины("нет-такой-витрины") is False


def test_витрины_делятся_на_два_профиля_поставщика():
    """Аниме-витрины не имеют права наследовать карантин семейства Lords."""
    модуль = загрузить_модуль_применения()
    assert модуль.ПРОФИЛЬ_ВИТРИНЫ == {
        "lords-01": "lords", "lords-02": "lords", "lords-03": "lords",
        "zona-01": "lords", "animedia-01": "yami", "animedia-02": "yami",
    }


def test_метрики_показывают_разрыв_отдельной_строкой():
    """Сто процентов среди опубликованных не должны прятать разрыв поставщика."""
    модуль = загрузить_модуль_применения()
    отчёт = гейт.Отчёт(site="lords-01", enabled=True, total_canonical_titles=100,
                       published_titles=90, available_titles=90, quarantined_titles=10)
    м = модуль.метрики([отчёт], карантин_url=316, уникальных_тайтлов=74,
                       записей_реестра=86)
    assert м["PUBLISHED_PLAYABLE_COVERAGE"] == 100.0
    assert м["PROVIDER_SOURCE_GAP_TITLES"] == 74
    assert м["PROVIDER_SOURCE_GAP_URLS"] == 316
    assert м["QUARANTINED_REGISTRY_ENTRIES"] == 86
    assert м["FINAL_STATUS"] == "PARTIAL_PROVIDER"


def test_без_разрыва_статус_не_частичный():
    модуль = загрузить_модуль_применения()
    отчёт = гейт.Отчёт(site="lords-01", enabled=True, total_canonical_titles=10,
                       published_titles=10, available_titles=10)
    м = модуль.метрики([отчёт], карантин_url=0, уникальных_тайтлов=0, записей_реестра=0)
    assert м["FINAL_STATUS"] == "FULL"
