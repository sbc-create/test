"""Комментарий под карточкой — отдельная сущность, и путь у него свой.

Инцидент 2026-10-09: черновик КОММЕНТАРИЯ опубликовали НОВОСТЬЮ
(`yummyani.org/posts/chernaya-koshka-i-klass-vedm-comment`), и на сайте
появился текст, который комментарием не был. Решение владельца: посты и
комментарии не смешивать, `posts-edit` для этой задачи не добавлять.

Проверки держат то, что иначе разъедется молча: своё хранилище черновиков,
отказ для семейств без поддержки, проверку повтора ДО записи, подпись
«Редакция» и подтверждение чтением списка, а не ответом на запись.
"""

from __future__ import annotations

import json

import pytest

from factory.qwen import actors, comments, editorial


class СайтYummy:
    domain = "yummyani.org"
    site_id = "yummy-org"
    adapter = "yummy"
    account = "yummyani-org"


class СайтAnimeGo:
    domain = "an1meg0.site"
    site_id = "animego-04"
    adapter = "animego"
    account = "an1meg0-site"


@pytest.fixture()
def витрина(monkeypatch, tmp_path):
    monkeypatch.setattr(comments, "_сайт", lambda site: СайтYummy())
    monkeypatch.setattr(comments, "_каталог", lambda s: tmp_path)
    monkeypatch.setattr(editorial, "_каталог", lambda s: tmp_path)
    monkeypatch.setattr(comments.registry, "адрес_тайтла",
                        lambda s, slug: f"https://{s.domain}/anime/{slug}")
    return tmp_path


def test_черновик_лежит_отдельно_от_постов(витрина):
    итог = comments.подготовить("yummyani.org", "кошка", "Полезное пояснение о героях.",
                                author="editor/claude/run-1")
    assert итог["state"] == "drafted"
    файл = витрина / comments.ЧЕРНОВИКИ
    assert файл.is_file(), "черновики комментариев живут в своём файле"
    assert comments.ЧЕРНОВИКИ != "post-drafts.json"
    запись = json.loads(файл.read_text(encoding="utf-8"))["items"]["кошка"]
    assert запись["author"] == "Редакция", "подпись задаётся сетью, а не вызовом"
    assert запись["prepared_by"] == "editor/claude/run-1"


def test_семейство_без_поддержки_отказывает_и_называет_блокер(monkeypatch):
    monkeypatch.setattr(comments, "_сайт", lambda site: СайтAnimeGo())
    with pytest.raises(comments.ОперацияОтклонена) as ош:
        comments.состояние("an1meg0.site", "любой")
    текст = str(ош.value)
    assert "community.py" in текст and "RUNTIME_DATA_OWNERSHIP" in текст
    assert "/posts" in текст, "отказ обязан запрещать подмену новостью"


def test_повтор_не_записывается(витрина, monkeypatch):
    тело = "Спика и кот — два героя этой истории."
    monkeypatch.setattr(comments, "состояние", lambda site, slug: {
        "site": "yummyani.org", "slug": slug, "total": 1,
        "comments": [{"id": "c1", "author": "Редакция",
                      "created_at": "2026-10-09T14:00:00Z", "body": тело}]})
    with pytest.raises(comments.ОперацияОтклонена, match="уже есть"):
        comments.опубликовать("yummyani.org", "кошка", author="editor/claude/run-1",
                              тело=тело)


def test_без_текста_публикации_нет(витрина):
    with pytest.raises(comments.ОперацияОтклонена, match="публиковать нечего"):
        comments.опубликовать("yummyani.org", "без-черновика",
                              author="editor/claude/run-1")


def test_подтверждение_берётся_из_списка(витрина, monkeypatch):
    """Ответ на запись говорит «принято», а посетителю важно «отдаётся»."""
    тело = "Короткое пояснение о героях карточки."
    записи: list[dict] = []

    def запрос(адрес, *, тело_запроса=None, домен=None, **кв):
        raise AssertionError("должен вызываться подменённый _запрос")

    def подставной(адрес, *, тело=None, домен):
        if тело is None:
            return 200, json.dumps({"total": len(записи), "comments": записи})
        записи.append({"id": "c7", "authorName": "Редакция",
                       "createdAt": "2026-10-09T14:05:00Z", "body": тело["body"]})
        return 201, json.dumps({"id": "c7"})

    monkeypatch.setattr(comments, "_запрос", подставной)
    monkeypatch.setattr(comments.time, "sleep", lambda _с: None)
    итог = comments.опубликовать("yummyani.org", "кошка",
                                 author="editor/claude/run-1", тело=тело)
    assert итог["state"] == "published" and итог["comment_id"] == "c7"
    assert итог["author"] == "Редакция" and итог["visible_in_list"] is True
    # Журнал витрины получает запись об операции — иначе публикацию не найти.
    журнал = (витрина / "history.jsonl").read_text(encoding="utf-8")
    assert "publish-comment" in журнал and "c7" in журнал


def test_невидимый_комментарий_это_отказ(витрина, monkeypatch):
    """Записали, но список не отдаёт — отказ, а не «опубликовано»."""
    def подставной(адрес, *, тело=None, домен):
        if тело is None:
            return 200, json.dumps({"total": 0, "comments": []})
        return 201, json.dumps({"id": "c9"})

    monkeypatch.setattr(comments, "_запрос", подставной)
    monkeypatch.setattr(comments.time, "sleep", lambda _с: None)
    with pytest.raises(comments.ОперацияОтклонена, match="не появился"):
        comments.опубликовать("yummyani.org", "кошка",
                              author="editor/claude/run-1", тело="Текст о героях.")


def test_границы_тела_перенесены_из_приложения(витрина):
    with pytest.raises(comments.ОперацияОтклонена, match="принимает от"):
        comments.подготовить("yummyani.org", "кошка", "ок",
                             author="editor/claude/run-1")
    длинное = "а" * (comments.МАКСИМУМ_ТЕЛА + 1)
    with pytest.raises(comments.ОперацияОтклонена, match="принимает от"):
        comments.подготовить("yummyani.org", "кошка", длинное,
                             author="editor/claude/run-1")


def test_права_qwen_на_комментарии(витрина):
    """Готовить — можно, публиковать — нет: это и есть ограничение после инцидента."""
    comments.подготовить("yummyani.org", "кошка", "Пояснение о героях карточки.",
                         author="qwen/editor-automation/run-3")
    with pytest.raises(actors.ОперацияНеРазрешена):
        comments.опубликовать("yummyani.org", "кошка",
                              author="qwen/editor-automation/run-3")
