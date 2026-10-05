"""Файл доставки новостей обновляется БЕЗ смены inode, и это проверяется записью.

Что измерено и почему эти тесты существуют
------------------------------------------

2026-10-05 на производстве: редактор опубликовал новость, инструмент ответил
`status=created`, `mounted=true`, `posts=13`, а `/posts/100kano-radio-57`
отдавал 404. Сверка хоста и контейнера:

    хост       /srv/.../overlays/yummyani.org/editorial-posts.json
               23 715 Б, 13 записей, inode 3356117
    контейнер  /app/content/editorial-posts.json
               22 025 Б, 12 записей, inode 3356113

Причина: файл смонтирован контейнеру ОТДЕЛЬНЫМ ФАЙЛОМ, такое монтирование
привязано к inode, а запись шла через `os.replace` — то есть каждая
публикация давала новый inode, и контейнер навсегда оставался на прежнем.

Воспроизведено в изоляции на своём контейнере `alpine`: после `os.replace`
контейнер продолжал читать прежний inode со старым содержимым; запись НА МЕСТЕ
одним `pwrite` видна ему сразу и без перезапуска.

Отсюда два инварианта, и оба проверяются ДЕЙСТВИЕМ, а не чтением кода:

1. последовательные публикации не меняют inode файла доставки;
2. файл после каждой записи разбирается как JSON — приложение на негодном
   JSON возбуждает исключение и теряет раздел целиком, поэтому укорачивание
   файла заменено дополнением хвостовыми пробелами.
"""
from __future__ import annotations

import json
import pathlib
import shutil
import subprocess

import pytest

from factory.qwen import posts, registry

ДОМЕН = "proba.example"


def _сайт() -> registry.Сайт:
    return registry.Сайт(site_id="proba", domain=ДОМЕН, adapter="yummy",
                         account="proba-acct", public_http="200",
                         published_release="deadbeef")


@pytest.fixture
def площадка(tmp_path, monkeypatch):
    """Изолированное хранилище. Производственных путей не касается."""
    monkeypatch.setenv("QWEN_EDITORIAL_ROOT", str(tmp_path / "overlays"))
    s = _сайт()
    monkeypatch.setattr(posts, "_сайт", lambda _site: s)
    # Контейнера здесь нет: сверка с ним проверяется отдельно и только при
    # наличии docker. Подтверждение публичного адреса подменяется сценарием.
    monkeypatch.setattr(posts, "_смонтировано", lambda _s: False)
    monkeypatch.setattr(posts, "доставка_в_контейнер",
                        lambda _s: {"in_sync": False, "reason": "стенд"})
    return s


def _файл(данные: dict) -> dict:
    return {"version": posts.ВЕРСИЯ_ФАЙЛА, "posts": данные["posts"]}


def _запись(slug: str, тело: list[str]) -> dict:
    return {"slug": slug, "type": "news", "status": "published",
            "title": f"Заголовок {slug}", "excerpt": "Одно предложение.",
            "body": тело, "publishedAt": "2026-10-05T00:00:00Z",
            "updatedAt": "2026-10-05T00:00:00Z", "authorName": "Редакция",
            "channelName": None, "externalUrl": None, "thumbnailUrl": None,
            "source": "editorial"}


def test_последовательные_записи_не_меняют_inode(площадка):
    s = площадка
    путь = posts.путь_доставки(s)
    inodes, размеры = [], []
    for номер in range(1, 6):
        записи = [_запись(f"novost-{н}", [f"Абзац {н}.{номер}"] * номер)
                  for н in range(1, номер + 1)]
        шаги = posts._записать_доставку(s, {"version": 1, "posts": записи},
                                        author="тест", операция="publish-post",
                                        slug=f"novost-{номер}")
        св = путь.stat()
        inodes.append(св.st_ino)
        размеры.append(св.st_size)
        # После КАЖДОЙ записи файл обязан разбираться.
        прочитано = json.loads(путь.read_text(encoding="utf-8"))
        assert len(прочитано["posts"]) == номер, прочитано
        assert шаги["inode_preserved"] is True, шаги

    assert len(set(inodes)) == 1, (
        f"inode менялся между записями: {inodes} — монтирование одного файла "
        "оторвалось бы от доставки на первой же публикации")


def test_укорачивание_не_ломает_разбор(площадка):
    """Запись стала короче — файл всё равно обязан быть годным JSON."""
    s = площадка
    путь = posts.путь_доставки(s)
    длинные = [_запись("a", ["Очень длинный абзац. " * 40]),
               _запись("b", ["И второй такой же. " * 40])]
    posts._записать_доставку(s, {"version": 1, "posts": длинные},
                             author="тест", операция="publish-post", slug="a")
    было = путь.stat()

    короткое = [_запись("a", ["Коротко."])]
    posts._записать_доставку(s, {"version": 1, "posts": короткое},
                             author="тест", операция="publish-post", slug="a")
    стало = путь.stat()

    assert стало.st_ino == было.st_ino
    assert стало.st_size >= было.st_size, (
        "файл укоротился: между усечением и записью читатель увидел бы "
        "неполный JSON, а приложение на этом возбуждает исключение")
    прочитано = json.loads(путь.read_text(encoding="utf-8"))
    assert [з["slug"] for з in прочитано["posts"]] == ["a"]
    assert прочитано["posts"][0]["body"] == ["Коротко."]


def test_замена_файла_не_используется(площадка, monkeypatch):
    """`os.replace` на файле доставки запрещён — проверяется запретом вызова."""
    s = площадка
    posts._записать_доставку(s, {"version": 1, "posts": [_запись("a", ["Текст."])]},
                             author="тест", операция="publish-post", slug="a")

    def запрещено(*_а, **_и):
        raise AssertionError("файл доставки заменён, а не перезаписан на месте")

    monkeypatch.setattr(posts.os, "replace", запрещено)
    posts._записать_доставку(s, {"version": 1, "posts": [_запись("a", ["Другой."])]},
                             author="тест", операция="publish-post", slug="a")
    прочитано = json.loads(posts.путь_доставки(s).read_text(encoding="utf-8"))
    assert прочитано["posts"][0]["body"] == ["Другой."]


def test_негодный_файл_не_записывается(площадка):
    """Отклонённое содержимое не должно попасть в файл даже частично."""
    s = площадка
    posts._записать_доставку(s, {"version": 1, "posts": [_запись("a", ["Текст."])]},
                             author="тест", операция="publish-post", slug="a")
    до = posts.путь_доставки(s).read_bytes()
    плохая = _запись("a", ["Текст."])
    плохая["status"] = "неизвестно"
    with pytest.raises(posts.ОперацияОтклонена):
        posts._записать_доставку(s, {"version": 1, "posts": [плохая]},
                                 author="тест", операция="publish-post", slug="a")
    assert posts.путь_доставки(s).read_bytes() == до


# --- подтверждение публичного результата -----------------------------------

def test_запись_без_публичного_подтверждения_не_успех(площадка, monkeypatch):
    """404 на публичном адресе не должен выглядеть успешной публикацией."""
    s = площадка
    к = posts._каталог_черновиков(s)
    posts.подготовить(ДОМЕН, "novost", title="Заголовок новости",
                      excerpt="Одно предложение описания.",
                      body=["Первый абзац.", "Второй абзац."],
                      author="Редакция")
    monkeypatch.setattr(posts, "посев", lambda _s: {"version": 1, "posts": []})
    monkeypatch.setattr(posts, "подтвердить_публично",
                        lambda _s, _slug, **_и: {
                            "url": f"https://{ДОМЕН}/posts/novost",
                            "http": "404", "attempts": 1, "confirmed": False,
                            "listed_in_section": False,
                            "reason": f"https://{ДОМЕН}/posts/novost отвечает 404"})
    итог = posts.опубликовать(ДОМЕН, "novost", author="Редакция")
    assert итог["status"] == "created"
    assert итог["written"] is True
    assert итог["public_confirmed"] is False
    assert "НЕ ПОДТВЕРЖДЕНО" in итог["note"], итог["note"]
    assert к.is_dir()


def test_подтверждённая_публикация_называется_подтверждённой(площадка, monkeypatch):
    s = площадка
    posts.подготовить(ДОМЕН, "novost", title="Заголовок новости",
                      excerpt="Одно предложение описания.",
                      body=["Первый абзац.", "Второй абзац."],
                      author="Редакция")
    monkeypatch.setattr(posts, "посев", lambda _s: {"version": 1, "posts": []})
    monkeypatch.setattr(posts, "подтвердить_публично",
                        lambda _s, _slug, **_и: {
                            "url": f"https://{ДОМЕН}/posts/novost",
                            "http": "200", "attempts": 1, "confirmed": True,
                            "listed_in_section": True,
                            "reason": "страница отвечает 200 и ссылка есть в /posts"})
    итог = posts.опубликовать(ДОМЕН, "novost", author="Редакция")
    assert итог["public_confirmed"] is True
    assert "ПОДТВЕРЖДЕНА" in итог["note"]


def test_повторная_проверка_ограничена(monkeypatch):
    """Ожидание обязано быть конечным: иначе отказ превращается в зависание."""
    вызовы = {"страниц": 0, "сна": 0}

    def страница(url, таймаут=15):
        вызовы["страниц"] += 1
        return ("404", "")

    monkeypatch.setattr(registry, "_страница", страница)
    import time as _time
    monkeypatch.setattr(_time, "sleep", lambda с: вызовы.__setitem__("сна", вызовы["сна"] + 1))
    итог = posts.подтвердить_публично(_сайт(), "novost", попыток=3, пауза=0)
    assert итог["confirmed"] is False
    assert итог["attempts"] == 3
    assert вызовы["страниц"] == 6, "по два запроса на попытку: адрес и раздел"


def test_страница_200_без_ссылки_в_разделе_не_подтверждение(monkeypatch):
    """Два признака нужны оба: страница может ответить 200 вне перечня."""
    def страница(url, таймаут=15):
        return ("200", "<html>совсем другое</html>")

    monkeypatch.setattr(registry, "_страница", страница)
    итог = posts.подтвердить_публично(_сайт(), "novost", попыток=1, пауза=0)
    assert итог["confirmed"] is False
    assert "ссылки" in итог["reason"]


# --- сверка с НАСТОЯЩИМ контейнером ----------------------------------------

@pytest.mark.skipif(shutil.which("docker") is None, reason="docker недоступен")
def test_контейнер_видит_запись_на_месте_и_не_видит_замену(tmp_path):
    """Тот же опыт, что дал причину, но в тесте: свой контейнер, свой файл.

    Порядок шагов важен, и первая версия теста его перепутала: она сперва
    заменяла файл, а потом ждала, что запись на месте дойдёт до контейнера.
    Не дойдёт — после замены путь на хосте ведёт к НОВОМУ inode, а контейнер
    держит прежний. Именно поэтому одна перепривязка (`docker restart`) нужна
    ровно один раз, и только после неё механизм работает сам.

    Поэтому проверяются три утверждения в их настоящем порядке:

      1. запись НА МЕСТЕ видна контейнеру сразу — это инвариант механизма;
      2. ЗАМЕНА файла контейнеру не видна — это доказанная причина отказа;
      3. `docker restart` перепривязывает монтирование к текущему inode — это
         обоснование однократного действия владельца.
    """
    образ = "alpine:3"
    есть = subprocess.run(["docker", "image", "inspect", образ],
                          capture_output=True)
    if есть.returncode != 0:
        pytest.skip(f"образа {образ} на этой машине нет")
    файл = tmp_path / "file.json"
    файл.write_text('{"version":1,"posts":["first"]}\n', encoding="utf-8")
    имя = "sf-posts-inode-test"
    subprocess.run(["docker", "rm", имя], capture_output=True)
    создан = subprocess.run(
        ["docker", "run", "-d", "--name", имя,
         "-v", f"{файл}:/mnt/file.json:ro", образ,
         "sh", "-c", "while true; do sleep 3600; done"],
        capture_output=True, text=True)
    if создан.returncode != 0:
        pytest.skip(f"контейнер не создан: {создан.stderr[:200]}")
    try:
        def в_контейнере() -> str:
            о = subprocess.run(["docker", "exec", имя, "cat", "/mnt/file.json"],
                               capture_output=True, text=True, timeout=30)
            return о.stdout

        assert "first" in в_контейнере()

        # 1. ЗАПИСЬ НА МЕСТЕ тем же кодом, что в бою, — видна сразу.
        posts._записать_сохранив_inode(
            файл, b'{"version":1,"posts":["second"]}\n')
        assert "second" in в_контейнере(), (
            "запись на месте не дошла до контейнера — механизм доставки не "
            "работает")
        # И повторно: механизм обязан работать не один раз.
        posts._записать_сохранив_inode(
            файл, b'{"version":1,"posts":["third","fourth"]}\n')
        assert "fourth" in в_контейнере()

        # 2. ЗАМЕНА — контейнер остаётся на прежнем inode. Это причина отказа.
        врем = tmp_path / "file.json.tmp"
        врем.write_text('{"version":1,"posts":["replaced"]}\n', encoding="utf-8")
        import os as _os
        _os.replace(врем, файл)
        assert "replaced" not in в_контейнере(), (
            "предпосылка опыта не воспроизвелась: замена файла оказалась "
            "видна контейнеру — тогда причина была бы другой")
        assert "fourth" in в_контейнере(), "контейнер держит прежний inode"

        # 3. ПЕРЕПРИВЯЗКА перезапуском — обоснование однократного действия.
        subprocess.run(["docker", "restart", имя], capture_output=True,
                       timeout=90)
        assert "replaced" in в_контейнере(), (
            "перезапуск не перепривязал монтирование — тогда однократное "
            "действие владельца не помогло бы")
    finally:
        subprocess.run(["docker", "stop", имя], capture_output=True)
        subprocess.run(["docker", "rm", имя], capture_output=True)
