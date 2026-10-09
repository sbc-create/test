"""Права исполнителя: роль решает, что он меняет в production.

Инцидент 2026-10-09. Исполнитель Qwen при действующем запрете опубликовал на
yummyani.org пост `chernaya-koshka-i-klass-vedm-comment`, в теле которого лежал
вопрос к редакции про радиостанцию, и через пять минут снял его (журнал
витрины: `publish-post` 13:30:07Z, `unpublish-post` 13:35:36Z). Публикация
прошла не через объявленный read-only мост: установленный юнит запускает его с
`--read-only`, а работающий процесс был запущен без ключа. То есть запрет
держался на договорённости, а код его не проверял.

Отсюда свойства, которые закрепляют эти проверки:

* ограничение живёт в САМИХ операциях, а не в канале: сменить мост на CLI или
  на прямой вызов модуля — не способ обойти;
* подготовка черновиков Qwen остаётся: запрет касается изменений production;
* роль, которой ограничения не объявлены, не трогается — иначе остановились бы
  действующие редакторы;
* отказ — исключение с названной причиной, а не пустой успех: «ничего не
  сделал» в журнале неотличимо от «сделал».
"""

from __future__ import annotations

import inspect

import pytest

from factory.qwen import actors, editorial, posts, queue_bridge


def test_роль_читается_как_у_очереди():
    """Разметка имени одна на оба места: второй способ разошёлся бы с первым."""
    assert actors.роль("qwen/editor-automation/run-7") == ("qwen", True)
    assert actors.роль("Редакция") == ("редакция", False)
    assert actors.роль("") == ("", False)
    # Та же разметка, что у заставы очереди.
    assert queue_bridge.роль_владельца("qwen/x/run-1")[0] == "qwen"


@pytest.mark.parametrize("операция", ["prepare", "posts-prepare"])
def test_qwen_готовит_черновики(операция):
    actors.проверить("qwen/editor-automation/run-7", операция)


@pytest.mark.parametrize("операция", [
    "publish", "unpublish", "restore", "posts-publish", "posts-unpublish",
    "queue-next", "queue-result", "queue-register", "queue-reopen", "queue-annul",
])
def test_qwen_не_меняет_production(операция):
    with pytest.raises(actors.ОперацияНеРазрешена) as ош:
        actors.проверить("qwen/editor-automation/run-7", операция)
    текст = str(ош.value)
    assert операция in текст
    assert "Разрешено: prepare" in текст, "отказ обязан называть, что МОЖНО"
    assert "chernaya-koshka" in текст, "основание названо: инцидент, а не вкус"


def test_имена_с_приставкой_тоже_ограничены():
    """`qwen-editor`, `qwen_run` — та же сторона, иначе запрет обходится дефисом."""
    for имя in ("qwen-editor/run-1", "qwen_auto/run-2"):
        with pytest.raises(actors.ОперацияНеРазрешена):
            actors.проверить(имя, "publish")


def test_чужая_роль_не_ограничивается():
    """Редактор и архитектор работают как раньше: им ограничений не объявлено."""
    for имя in ("editor/claude-indexing-operation-02", "cell/wt-portable-site-cell-01",
                "Редакция"):
        for операция in actors.ОПЕРАЦИИ:
            actors.проверить(имя, операция)


def test_владелец_может_снять_на_одну_смену(monkeypatch):
    monkeypatch.setenv(actors.СНЯТИЕ, "qwen:publish")
    actors.проверить("qwen/x/run-1", "publish")
    with pytest.raises(actors.ОперацияНеРазрешена):
        actors.проверить("qwen/x/run-1", "unpublish")
    monkeypatch.setenv(actors.СНЯТИЕ, "qwen:*")
    actors.проверить("qwen/x/run-1", "unpublish")


def test_неизвестная_операция_это_ошибка_вызова():
    """Опечатка в имени операции не должна выглядеть как разрешение."""
    with pytest.raises(ValueError, match="неизвестная операция"):
        actors.проверить("qwen/x/run-1", "publish-post")


@pytest.mark.parametrize("модуль,имя,операция", [
    (editorial, "подготовить", "prepare"),
    (editorial, "публиковать", "publish"),
    (editorial, "снять", "unpublish"),
    (editorial, "восстановить", "restore"),
    (posts, "подготовить", "posts-prepare"),
    (posts, "опубликовать", "posts-publish"),
    (posts, "снять", "posts-unpublish"),
    (queue_bridge, "взять", "queue-next"),
    (queue_bridge, "записать", "queue-result"),
])
def test_застава_стоит_в_самой_операции(модуль, имя, операция):
    """Застава в канале обходится сменой канала — она обязана быть в операции."""
    тело = inspect.getsource(getattr(модуль, имя))
    assert f"actors.проверить(" in тело, f"{модуль.__name__}.{имя} без заставы"
    assert операция in тело, f"{модуль.__name__}.{имя}: не та операция"


def test_qwen_не_опубликует_описание_даже_с_готовым_черновиком(monkeypatch):
    """Сквозная проверка: отказ наступает ДО любой записи."""
    следы = []
    monkeypatch.setattr(editorial, "_сайт", lambda *а, **к: следы.append("сайт"))
    with pytest.raises(actors.ОперацияНеРазрешена):
        editorial.публиковать("yummyani.org", "009-1", author="qwen/auto/run-9")
    assert следы == [], "до реестра и хранилища дело доходить не должно"


def test_состояние_ограничений_читается_машинно():
    св = actors.сведения()
    assert св["roles"]["qwen"] == ["prepare", "posts-prepare"]
    assert "publish" in св["operations"] and "queue-annul" in св["operations"]
    assert св["override_env"] == "FACTORY_ACTOR_ALLOW"
