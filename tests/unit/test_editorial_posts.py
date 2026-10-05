"""Редакционные новости витрины: схема приложения, дубли, снятие.

Что именно защищается
---------------------

Раздел `/posts` и новостной блок отдаёт приложение Next.js, которое читает
`content/editorial-posts.json` ПРИ ОБРАБОТКЕ ЗАПРОСА и проверяет его схемой
Zod. Файл монтируется в контейнер из каталога доставки фабрики, поэтому цена
негодной записи — не «одна новость не вышла», а отказ разбора ВСЕГО файла:
раздел перестаёт отдаваться целиком.

Отсюда три проверки, без которых механизм нельзя считать работающим:

1. проверка фабрики повторяет схему приложения, а не приблизительную идею о
   ней. Доказательство — настоящий файл приложения: все его записи обязаны
   проходить нашу проверку, а перечни типов и состояний обязаны совпадать с
   объявленными в его исходнике;
2. повтор публикации не создаёт дубля: публичный адрес обязан быть один;
3. снятие публикации не теряет запись и не ломает файл.
"""
from __future__ import annotations

import json
import pathlib
import re

import pytest

from factory.qwen import posts

КОРЕНЬ = pathlib.Path(__file__).resolve().parents[2]
#: Исходник приложения витрины. Лежит вне этого репозитория: проверка
#: пропускается, если его здесь нет, и НЕ подменяется догадкой.
ИСХОДНИК_ПРИЛОЖЕНИЯ = pathlib.Path(
    "/home/claude/wt-yummy-mail-org/src/modules/editorial/editorial-post.ts")
ФАЙЛ_ПРИЛОЖЕНИЯ = pathlib.Path(
    "/home/claude/wt-yummy-mail-org/content/editorial-posts.json")


def _запись(**замены) -> dict:
    запись = {
        "slug": "proba-mehanizma", "type": "news", "status": "published",
        "title": "Проба механизма", "excerpt": "Короткое описание.",
        "body": ["Первый абзац.", "Второй абзац."],
        "publishedAt": "2026-10-05T09:00:00.000Z",
        "updatedAt": "2026-10-05T09:00:00.000Z",
        "authorName": "Редакция", "channelName": None,
        "externalUrl": None, "thumbnailUrl": None, "source": "editorial",
    }
    запись.update(замены)
    return запись


# --- 1. Схема повторяет схему приложения ----------------------------------

def test_перечни_совпадают_с_исходником_приложения():
    """Расхождение перечней — отказ разбора файла, а не «неизвестный тип»."""
    if not ИСХОДНИК_ПРИЛОЖЕНИЯ.is_file():
        pytest.skip(f"исходника приложения здесь нет: {ИСХОДНИК_ПРИЛОЖЕНИЯ}")
    текст = ИСХОДНИК_ПРИЛОЖЕНИЯ.read_text(encoding="utf-8")

    def перечень(имя: str) -> tuple[str, ...]:
        м = re.search(rf"{имя}\s*=\s*\[([^\]]*)\]", текст)
        assert м, f"в исходнике нет {имя}"
        return tuple(re.findall(r'"([^"]+)"', м.group(1)))

    assert перечень("EDITORIAL_POST_TYPES") == posts.ТИПЫ
    assert перечень("EDITORIAL_POST_STATUSES") == posts.СОСТОЯНИЯ
    assert перечень("EDITORIAL_SOURCES") == posts.ИСТОЧНИКИ
    # И путь, по которому приложение ждёт файл, — тот, что мы монтируем.
    assert 'join(process.cwd(), "content/editorial-posts.json")' in текст
    assert posts.ПУТЬ_В_КОНТЕЙНЕРЕ.endswith("content/editorial-posts.json")


def test_настоящий_файл_приложения_проходит_нашу_проверку():
    """Если наша проверка строже приложения, публикация ломалась бы на ровном."""
    if not ФАЙЛ_ПРИЛОЖЕНИЯ.is_file():
        pytest.skip(f"файла приложения здесь нет: {ФАЙЛ_ПРИЛОЖЕНИЯ}")
    данные = json.loads(ФАЙЛ_ПРИЛОЖЕНИЯ.read_text(encoding="utf-8"))
    assert posts.проверить_файл(данные) == []
    assert len(данные["posts"]) >= 1


@pytest.mark.parametrize("замена,ожидание", [
    ({"slug": "Проба Кириллицей"}, "slug"),
    ({"type": "podcast"}, "type"),
    ({"status": "hidden"}, "status"),
    ({"source": "wikipedia"}, "source"),
    ({"title": "  "}, "title"),
    ({"body": "строка вместо списка"}, "body"),
    ({"body": []}, "body пуст"),
    ({"publishedAt": "позавчера"}, "publishedAt"),
    ({"externalUrl": "http://example.com"}, "https"),
    ({"channelName": ""}, "channelName"),
])
def test_негодная_запись_называется_полем(замена, ожидание):
    беды = posts.проверить_запись(_запись(**замена))
    assert беды, f"запись с {замена} принята"
    assert any(ожидание in б for б in беды), беды


def test_годная_запись_проходит():
    assert posts.проверить_запись(_запись()) == []


def test_лишнее_поле_отвергается():
    """Приложение разбирает объект строго: лишнее поле — отказ файла."""
    беды = posts.проверить_запись(_запись(extra="что-то"))
    assert any("неизвестные поля" in б for б in беды), беды


def test_повтор_слага_в_файле_называется():
    файл = {"version": 1, "posts": [_запись(), _запись()]}
    беды = posts.проверить_файл(файл)
    assert any("повторяется" in б for б in беды), беды


def test_версия_файла_проверяется():
    беды = posts.проверить_файл({"version": 2, "posts": []})
    assert any("version" in б for б in беды), беды


# --- 2. Отпечаток: повтор отличается от правки ----------------------------

def test_отпечаток_не_зависит_от_времени():
    """Иначе повторная подача того же текста выглядела бы новой работой."""
    а = _запись()
    б = _запись(updatedAt="2026-10-06T10:00:00.000Z",
                publishedAt="2026-10-06T10:00:00.000Z")
    assert posts.отпечаток(а) == posts.отпечаток(б)


def test_отпечаток_меняется_от_текста():
    а = _запись()
    б = _запись(body=["Другой текст."])
    assert posts.отпечаток(а) != posts.отпечаток(б)


# --- 3. Публикация, повтор и снятие на изолированном корне ----------------

@pytest.fixture
def изолированно(tmp_path, monkeypatch):
    """Свой корень доставки и свой посев: production не задействован."""
    from factory.qwen import editorial, registry

    корень = tmp_path / "overlays"
    monkeypatch.setenv("QWEN_EDITORIAL_ROOT", str(корень))
    monkeypatch.setattr(registry, "корень_хранилища", lambda adapter: корень)
    # Каталог черновиков фабрики тоже уводится в стенд: иначе проба писала бы
    # в хранилище production.
    monkeypatch.setattr(editorial, "_каталог",
                        lambda s: (корень / s.domain))
    (корень / "yummyani.org").mkdir(parents=True, exist_ok=True)
    editorial.сбросить_кэш_реестра()

    # Посев берётся не из контейнера: тест не зависит от работающего хоста.
    посеяно = {"version": 1, "posts": [_запись(slug="staraya-novost")]}
    monkeypatch.setattr(posts, "посев", lambda s: json.loads(json.dumps(посеяно)))
    monkeypatch.setattr(posts, "_смонтировано", lambda s: True)
    monkeypatch.setattr(posts, "контейнер", lambda s: "проба")
    yield корень
    editorial.сбросить_кэш_реестра()


def _сайт_есть() -> bool:
    from factory.qwen import editorial
    try:
        editorial._сайт("yummyani.org", опрашивать_сеть=False)
        return True
    except Exception:  # noqa: BLE001
        return False


def test_публикация_повтор_и_снятие(изолированно):
    if not _сайт_есть():
        pytest.skip("витрины yummyani.org нет в прочитанном реестре")
    из_черновика = posts.подготовить(
        "yummyani.org", "novaya-novost", title="Новая новость",
        excerpt="Описание.", body=["Абзац."], author="Редакция")
    assert из_черновика["state"] == "verified", из_черновика
    assert из_черновика["public"] is False

    первая = posts.опубликовать("yummyani.org", "novaya-novost", author="Редакция")
    assert первая["status"] == "created", первая
    assert первая["posts"] == 2, "прежняя запись обязана остаться"
    assert первая["public_url"].endswith("/posts/novaya-novost")

    # ДУБЛЯ НЕТ: то же содержание — не работа.
    вторая = posts.опубликовать("yummyani.org", "novaya-novost", author="Редакция")
    assert вторая["status"] == "nothing-to-do", вторая

    снятие = posts.снять("yummyani.org", "novaya-novost", author="Редакция")
    assert снятие["status"] == "unpublished", снятие
    файл = json.loads((изолированно / "yummyani.org" / posts.ИМЯ_ДОСТАВКИ)
                      .read_text(encoding="utf-8"))
    assert len(файл["posts"]) == 2, "снятие не удаляет запись"
    снятая = [з for з in файл["posts"] if з["slug"] == "novaya-novost"][0]
    assert снятая["status"] == "draft"
    assert posts.проверить_файл(файл) == []

    повтор = posts.снять("yummyani.org", "novaya-novost", author="Редакция")
    assert повтор["status"] == "nothing-to-do", повтор


def test_публикация_без_черновика_отказывает(изолированно):
    if not _сайт_есть():
        pytest.skip("витрины yummyani.org нет в прочитанном реестре")
    with pytest.raises(posts.ОперацияОтклонена) as ош:
        posts.опубликовать("yummyani.org", "net-chernovika", author="Редакция")
    assert "черновика" in str(ош.value)


def test_негодный_слаг_черновика_не_пишется(изолированно):
    """Слаг — личность записи: черновик под негодным ключом бесполезен."""
    if not _сайт_есть():
        pytest.skip("витрины yummyani.org нет в прочитанном реестре")
    with pytest.raises(posts.ОперацияОтклонена) as ош:
        posts.подготовить("yummyani.org", "Проба Кириллицей", title="Проба",
                          excerpt="", body=["Абзац."], author="Редакция")
    assert "slug" in str(ош.value)


def test_посев_пустым_списком_запрещён(monkeypatch):
    """Монтирование заменяет файл образа: пустой посев снял бы всё с публикации."""
    # Фикстура `изолированно` здесь НЕ берётся сознательно: она подменяет сам
    # посев, и проверять его отказ стало бы невозможно.
    if not _сайт_есть():
        pytest.skip("витрины yummyani.org нет в прочитанном реестре")
    from factory.qwen import editorial
    import factory.qwen.posts as модуль

    s = editorial._сайт("yummyani.org", опрашивать_сеть=False)
    # Контейнер не определён — читать исходные новости нечем, и операция
    # обязана отказать, а не начать с пустого списка.
    monkeypatch.setattr(модуль, "контейнер", lambda сайт: "")
    with pytest.raises(модуль.ОперацияОтклонена) as ош:
        модуль.посев(s)
    assert "контейнер витрины не определён" in str(ош.value)
    assert "снял бы с" in str(ош.value)


# --- 4. Связь витрины с её приложением: по порту, а не по имени ------------

def test_контейнер_определяется_портом_апстрима(monkeypatch):
    """Поиск по имени давал ЧУЖОЙ контейнер — это cross-site утечка.

    Измерено 2026-10-05 на первой версии этой функции: подстрочный поиск
    возвращал `yummyani-staging-web-org-1` для всех пяти витрин семейства, и
    посев новостей взял бы содержимое чужого сайта.
    """
    import types

    class Сайт:
        account = "проба"
        domain = "proba.test"
        adapter = "yummy"

    monkeypatch.setattr(posts, "апстрим", lambda s: "127.0.0.1:3104")

    выводы = {
        "ps": "yummyani-staging-web-org-1\t127.0.0.1:3102->3000/tcp\n"
              "yummyani7-site-web-1\t127.0.0.1:3104->3000/tcp\n"
              "yummyani7-info-web-1\t127.0.0.1:3105->3000/tcp\n",
    }

    def запуск(команда, **кв):
        return types.SimpleNamespace(returncode=0, stdout=выводы["ps"], stderr="")

    monkeypatch.setattr(posts.subprocess, "run", запуск)
    assert posts.контейнер(Сайт()) == "yummyani7-site-web-1"

    # Порт, который никто не публикует: приложение витрины не запущено, и это
    # ДРУГОЙ ответ, чем «нашли чужое».
    monkeypatch.setattr(posts, "апстрим", lambda s: "127.0.0.1:3999")
    assert posts.контейнер(Сайт()) == ""

    # Апстрим не объявлен — искать нечем.
    monkeypatch.setattr(posts, "апстрим", lambda s: "")
    assert posts.контейнер(Сайт()) == ""


def test_апстрим_читается_из_выпуска(tmp_path, monkeypatch):
    """Значение берётся у ВЫЛОЖЕННОГО кода, а не из рабочей копии."""
    class Сайт:
        account = "проба-апстрим"
        domain = "proba.test"
        adapter = "yummy"

    корень = tmp_path / "srv" / "проба-апстрим" / "current" / "config"
    корень.mkdir(parents=True)
    (корень / "site.json").write_text(json.dumps(
        {"environment": {"LORDS_LEGACY_UPSTREAM": "127.0.0.1:3107"}}),
        encoding="utf-8")
    исходная = posts.апстрим

    def подмена(s):
        п = корень / "site.json"
        д = json.loads(п.read_text(encoding="utf-8"))
        return str((д.get("environment") or {}).get("LORDS_LEGACY_UPSTREAM") or "")

    monkeypatch.setattr(posts, "апстрим", подмена)
    assert posts.апстрим(Сайт()) == "127.0.0.1:3107"
    # И настоящая функция читает именно это поле — проверяется по исходнику.
    тело = (КОРЕНЬ / "factory" / "qwen" / "posts.py").read_text("utf-8")
    тело_функции = тело.split("def апстрим", 1)[1].split("\ndef ", 1)[0]
    assert "LORDS_LEGACY_UPSTREAM" in тело_функции
    assert "/current" in тело_функции and "/app" in тело_функции
    assert исходная is not None
