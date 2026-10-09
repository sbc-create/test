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


#: Идентификатор тайтла в приложении: блок комментариев карточки запрашивает
#: тред ИМЕННО по нему, а не по публичному слагу (измерено 2026-10-09).
ИД_ТАЙТЛА = "019d83b9-311a-7b38-b7af-9ac9c10fc9af"


@pytest.fixture()
def витрина(monkeypatch, tmp_path):
    monkeypatch.setattr(comments, "_сайт", lambda site: СайтYummy())
    monkeypatch.setattr(comments, "_каталог", lambda s: tmp_path)
    monkeypatch.setattr(editorial, "_каталог", lambda s: tmp_path)
    monkeypatch.setattr(editorial, "_известный_title_id",
                        lambda s, slug, текущее: ИД_ТАЙТЛА)
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


def test_площадка_без_места_для_комментария_отказывает(monkeypatch):
    """Нет ни приложения с комментариями, ни модуля сообщества в выпуске.

    Отказ обязан называть, ЧЕГО не хватает, и запрещать подмену новостью:
    инцидент 2026-10-09 начался именно с публикации комментария в /posts.
    """
    monkeypatch.setattr(comments, "_сайт", lambda site: СайтAnimeGo())
    monkeypatch.setattr(comments, "_модуль_ячейки", lambda s: None)
    with pytest.raises(comments.ОперацияОтклонена) as ош:
        comments.состояние("an1meg0.site", "любой")
    текст = str(ош.value)
    assert "community.py" in текст
    assert "/posts" in текст, "отказ обязан запрещать подмену новостью"


def test_ячейка_с_модулем_сообщества_публикует_своим_путём(monkeypatch, tmp_path):
    """У семейств с нашим рантаймом путь второй: заявка исполнителю.

    До 2026-10-10 операция отказывала всем, кроме Yummy: писать в хранилище
    сообщений посетителей было нечем. Теперь есть узкая операция исполнителя,
    и признак поддержки — МОДУЛЬ В ВЫПУСКЕ, а не название семейства: у lords
    он есть не у всех ячеек.
    """
    модуль = tmp_path / "community.py"
    модуль.write_text("# модуль сообщества\n", encoding="utf-8")
    monkeypatch.setattr(comments, "_сайт", lambda site: СайтAnimeGo())
    monkeypatch.setattr(comments, "_модуль_ячейки", lambda s: модуль)
    assert comments.способ(СайтAnimeGo()) == "cell"
    # Обратимость у этого пути есть по построению: снятие делает та же заявка
    # действием `retract`. Публикация без пути снятия запрещена правилом сети.
    снимается, чем = comments.путь_снятия(СайтAnimeGo())
    assert снимается is True and "retract" in чем


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
        # Публикация сперва спрашивает маршрут модерации: 401 означает, что
        # снятие возможно, и держать публикацию не за что.
        if "/api/admin/comments/" in адрес:
            return 401, json.dumps({"code": "unauthorized"})
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
        if "/api/admin/comments/" in адрес:
            return 401, json.dumps({"code": "unauthorized"})
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

def test_без_пути_снятия_публикации_нет(витрина, monkeypatch):
    """У изменения обязан быть откат, а у этого его нет — измерено.

    Приложение публикует комментарий сразу (`status: published`), а снимает
    только маршрут модерации при настроенном ADMIN_MODERATION_SECRET. 2026-10-09
    переменная не задана ни у web-org, ни у web-site: опубликованное сообщение
    снять было бы нечем. Отказ называет и чем измерено, и чем закрывается.
    """
    def подставной(адрес, *, тело=None, домен):
        if "/api/admin/comments/" in адрес:
            return 503, '{"code": "not_configured"}'
        return 200, json.dumps({"total": 0, "comments": []})

    monkeypatch.setattr(comments, "_запрос", подставной)
    monkeypatch.delenv(comments.СОГЛАСИЕ_НА_НЕОБРАТИМОСТЬ, raising=False)
    with pytest.raises(comments.ОперацияОтклонена) as ош:
        comments.опубликовать("yummyani.org", "кошка",
                              author="editor/claude/run-1", тело="Текст о героях.")
    текст = str(ош.value)
    assert "снять комментарий нечем" in текст and "not_configured" in текст
    assert "ADMIN_MODERATION_SECRET" in текст and "secret_ref" in текст


def test_владелец_может_разрешить_необратимую_публикацию(витрина, monkeypatch):
    """Решение владельца — явное и по домену, а не молчаливое исключение."""
    записи: list[dict] = []

    def подставной(адрес, *, тело=None, домен):
        if "/api/admin/comments/" in адрес:
            return 503, '{"code": "not_configured"}'
        if тело is None:
            return 200, json.dumps({"total": len(записи), "comments": записи})
        записи.append({"id": "c3", "authorName": "Редакция",
                       "createdAt": "2026-10-09T15:00:00Z", "body": тело["body"]})
        return 201, json.dumps({"id": "c3"})

    monkeypatch.setattr(comments, "_запрос", подставной)
    monkeypatch.setattr(comments.time, "sleep", lambda _с: None)
    monkeypatch.setenv(comments.СОГЛАСИЕ_НА_НЕОБРАТИМОСТЬ, "yummyani.org")
    итог = comments.опубликовать("yummyani.org", "кошка",
                                 author="editor/claude/run-1", тело="Текст о героях.")
    assert итог["state"] == "published" and итог["comment_id"] == "c3"


def test_настроенная_модерация_публикацию_не_держит(витрина, monkeypatch):
    """401 — модерация есть, снятие возможно: держать публикацию не за что."""
    записи: list[dict] = []

    def подставной(адрес, *, тело=None, домен):
        if "/api/admin/comments/" in адрес:
            return 401, '{"code": "unauthorized"}'
        if тело is None:
            return 200, json.dumps({"total": len(записи), "comments": записи})
        записи.append({"id": "c4", "authorName": "Редакция",
                       "createdAt": "2026-10-09T15:00:00Z", "body": тело["body"]})
        return 201, json.dumps({"id": "c4"})

    monkeypatch.setattr(comments, "_запрос", подставной)
    monkeypatch.setattr(comments.time, "sleep", lambda _с: None)
    monkeypatch.delenv(comments.СОГЛАСИЕ_НА_НЕОБРАТИМОСТЬ, raising=False)
    итог = comments.опубликовать("yummyani.org", "кошка",
                                 author="editor/claude/run-1", тело="Текст о героях.")
    assert итог["state"] == "published" and итог["comment_id"] == "c4"


def test_тред_называется_идентификатором_приложения(витрина, monkeypatch):
    """Публичный слаг создаёт тред, которого карточка не показывает.

    Измерено на себе 2026-10-09: комментарий, записанный с
    `titleSlug=chernaya-koshka-i-klass-vedm`, создался (id
    cmv17r4ap00i5p50145hr2oc7) и читался запросом по тому же слагу, но
    отрисовка карточки показала «Опубликованных комментариев пока нет»: блок
    запрашивает `titleSlug=019d83b9-311a-7b38-b7af-9ac9c10fc9af`. Операция при
    этом ответила «опубликовано» — то есть подтверждение чтением списка не
    спасает, если список запрашивается не тем ключом, что страница.
    """
    запросы: list[tuple[str, dict | None]] = []

    def подставной(адрес, *, тело=None, домен):
        запросы.append((адрес, тело))
        if "/api/admin/comments/" in адрес:
            return 401, json.dumps({"code": "unauthorized"})
        if тело is None:
            return 200, json.dumps({"total": 0, "comments": []})
        return 201, json.dumps({"id": "c11"})

    monkeypatch.setattr(comments, "_запрос", подставной)
    monkeypatch.setattr(comments.time, "sleep", lambda _с: None)
    with pytest.raises(comments.ОперацияОтклонена, match="не появился"):
        comments.опубликовать("yummyani.org", "публичный-слаг",
                              author="editor/claude/run-1", тело="Текст о героях.")
    чтения = [а for а, т in запросы if т is None and "admin" not in а]
    записи = [т for а, т in запросы if т and "admin" not in а]
    assert чтения and all(f"titleSlug={ИД_ТАЙТЛА}" in а for а in чтения), чтения
    assert записи and all(з["titleSlug"] == ИД_ТАЙТЛА for з in записи), записи
    assert all("публичный-слаг" not in str(з) for з in записи), (
        "в приложение уходит идентификатор, а публичный слаг — только в адрес")


def test_без_идентификатора_тайтла_комментарий_не_пишется(витрина, monkeypatch):
    """Ни накладка, ни last-good, ни поиск не ответили — это отказ, не догадка."""
    monkeypatch.setattr(editorial, "_известный_title_id",
                        lambda s, slug, текущее: "")
    with pytest.raises(comments.ОперацияОтклонена, match="идентификатор тайтла"):
        comments.состояние("yummyani.org", "кошка")


# --------------------------------------------------------- снятие комментария

def test_снятие_идёт_по_одному_идентификатору(витрина, monkeypatch):
    """Маршрут приложения принимает ОДИН id — сообщения посетителей целы."""
    обращения: list[tuple[str, dict | None]] = []

    def подставной(адрес, *, тело=None, домен, добавить=None):
        обращения.append((адрес, тело))
        if "/api/admin/comments/" in адрес:
            return 200, json.dumps({"id": "cmv-мой", "status": "deleted",
                                    "titleSlug": "019d83b9"})
        if "?titleSlug=" in адрес:
            return 200, json.dumps({"total": 1, "comments": [
                {"id": "cmv-гость", "authorName": "Гость", "body": "привет"}]})
        return 200, "{}"

    def сессия(адрес, *, тело=None, домен, добавить=None, вернуть_заголовки=False):
        return 200, "{}", {"Set-Cookie": "yami_moderation=подпись; Path=/"}

    monkeypatch.setattr(comments, "_запрос", подставной)
    monkeypatch.setattr(comments, "_послать", сессия)
    monkeypatch.setattr(comments, "_секрет_модерации", lambda s: "секрет-не-короче-16")
    итог = comments.снять("yummyani.org", "cmv-мой",
                          author="cell/wt-portable-site-cell-01")
    assert итог["state"] == "unpublished" and итог["status"] == "deleted"
    # Снимается ровно один адрес, и он содержит наш id.
    пишущие = [а for а, т in обращения if т is not None]
    assert пишущие == ["https://yummyani.org/api/admin/comments/cmv-мой"], пишущие
    # Подтверждение читает тред ИЗ ОТВЕТА, а не из догадки.
    чтения = [а for а, т in обращения if т is None]
    assert any("titleSlug=019d83b9" in а for а in чтения), чтения
    # Комментарий гостя остался в списке и операцией не затронут.
    assert итог["remaining_in_thread"] == 1


def test_без_секрета_снятия_нет(витрина, monkeypatch):
    monkeypatch.setattr(comments, "_секрет_модерации", lambda s: "")
    with pytest.raises(comments.ОперацияОтклонена, match="секрет модерации не прочитан"):
        comments.снять("yummyani.org", "cmv-мой", author="editor/claude/run-1")


def test_без_cookie_сессии_снятия_нет(витрина, monkeypatch):
    """Успех открытия сессии без cookie — не разрешение: снимать нечем."""
    monkeypatch.setattr(comments, "_секрет_модерации", lambda s: "секрет-не-короче-16")
    monkeypatch.setattr(comments, "_послать",
                        lambda адрес, **кв: (200, "{}", {"Content-Type": "application/json"}))
    with pytest.raises(comments.ОперацияОтклонена, match="cookie"):
        comments.снять("yummyani.org", "cmv-мой", author="editor/claude/run-1")


def test_успех_приложения_без_исчезновения_из_списка_это_отказ(витрина, monkeypatch):
    """«Сняли» обязано значить «не отдаётся», а не «ответило 200»."""
    def подставной(адрес, *, тело=None, домен, добавить=None):
        if адрес.endswith("/api/admin/comments/cmv-мой"):
            return 200, json.dumps({"id": "cmv-мой", "status": "deleted",
                                    "titleSlug": "019d83b9"})
        return 200, json.dumps({"total": 1, "comments": [{"id": "cmv-мой"}]})

    monkeypatch.setattr(comments, "_запрос", подставной)
    monkeypatch.setattr(comments, "_послать",
                        lambda адрес, **кв: (200, "{}", {"Set-Cookie": "yami_moderation=п"}))
    monkeypatch.setattr(comments, "_секрет_модерации", lambda s: "секрет-не-короче-16")
    with pytest.raises(comments.ОперацияОтклонена, match="всё ещё в списке"):
        comments.снять("yummyani.org", "cmv-мой", author="editor/claude/run-1")


def test_qwen_не_снимает(витрина, monkeypatch):
    monkeypatch.setattr(comments, "_секрет_модерации", lambda s: "секрет-не-короче-16")
    with pytest.raises(actors.ОперацияНеРазрешена):
        comments.снять("yummyani.org", "cmv-мой", author="qwen/editor-automation/run-3")


def test_секрет_не_попадает_в_журнал(витрина, monkeypatch):
    СЕКРЕТ = "секрет-не-короче-16-знаков"
    monkeypatch.setattr(comments, "_секрет_модерации", lambda s: СЕКРЕТ)
    monkeypatch.setattr(comments, "_послать",
                        lambda адрес, **кв: (200, "{}", {"Set-Cookie": "yami_moderation=п"}))
    monkeypatch.setattr(comments, "_запрос", lambda адрес, **кв: (
        (200, json.dumps({"id": "cmv-мой", "status": "deleted", "titleSlug": "т"}))
        if "admin" in адрес else (200, json.dumps({"total": 0, "comments": []}))))
    comments.снять("yummyani.org", "cmv-мой", author="editor/claude/run-1")
    журнал = (витрина / "history.jsonl").read_text(encoding="utf-8")
    assert "unpublish-comment" in журнал and "cmv-мой" in журнал
    assert СЕКРЕТ not in журнал, "значение секрета в журнале — утечка"


def test_обещание_доступности_в_комментарии_не_проходит(витрина, monkeypatch):
    """Те же запрещённые обороты, что у описаний: комментарий — тоже текст сети.

    До 2026-10-09 у комментария проверялась только длина, и обещание
    «доступны все озвучки» прошло бы. Подтвердить его нечем, а посетителю оно
    обещает то, чего может не быть.
    """
    плохой = ("Полезное наблюдение о героях этой истории, и к нему приписано: "
              "доступны все озвучки и субтитры, смотрите в любом качестве.")
    итог = comments.подготовить("yummyani.org", "кошка", плохой,
                                author="editor/claude/run-1")
    assert итог["state"] == "needs-fix", итог
    assert итог["quality_problems"], итог
    # И публикация прямо переданного тела тоже отказывает — до любой записи.
    monkeypatch.setattr(comments, "_запрос",
                        lambda *а, **к: pytest.fail("записи быть не должно"))
    with pytest.raises(comments.ОперацияОтклонена, match="не прошёл проверку текста"):
        comments.опубликовать("yummyani.org", "кошка",
                              author="editor/claude/run-1", тело=плохой)


def test_годные_тексты_партии_проверку_проходят(витрина):
    """Опубликованные 2026-10-09 комментарии проверку проходят — иначе застава
    ловила бы не обороты, а живую работу."""
    годный = ("Это второй сезон, и у него есть особенность, важная для выбора: "
              "манга-первоисточник уже завершена, поэтому сезон не остановится "
              "там, где у автора кончился материал.")
    итог = comments.подготовить("yummyani.org", "стена", годный,
                                author="editor/claude/run-1")
    assert итог["state"] == "drafted" and итог["quality_problems"] == []

def test_второй_комментарий_под_карточкой_требует_основания(витрина, monkeypatch):
    """Повтор ловился только дословный, а правило запрещает и второй текст.

    Измерено на себе 2026-10-09: под карточкой
    `yummyani.org/mir-otome-igr-eto-tyazhelyy-mir-dlya-mobov-2` в 22:32 и 22:37
    оказались два НАШИХ комментария — один от ночного захода, другой от
    часового запуска. Тексты разные и оба содержательные, но правило владельца
    запрещает несколько комментариев под одной карточкой без новой
    содержательной причины. Лишний был снят, а запрет выражен этой проверкой.
    """
    monkeypatch.setattr(comments, "состояние", lambda site, slug: {
        "site": "yummyani.org", "slug": slug, "total": 1,
        "comments": [{"id": "c1", "author": "Редакция",
                      "created_at": "2026-10-09T22:32:25Z",
                      "body": "Первый содержательный комментарий о названии."}]})
    monkeypatch.delenv(comments.ОСНОВАНИЕ_ВТОРОГО, raising=False)
    with pytest.raises(comments.ОперацияОтклонена) as ош:
        comments.опубликовать("yummyani.org", "кошка", author="editor/claude/run-1",
                              тело="Совершенно другой текст про первоисточник.")
    текст = str(ош.value)
    assert comments.ОСНОВАНИЕ_ВТОРОГО in текст, "отказ обязан называть, чем он снимается"
    assert "объём" in текст

    # С НАЗВАННЫМ основанием второй комментарий возможен: решение осознанное.
    monkeypatch.setenv(comments.ОСНОВАНИЕ_ВТОРОГО, "вышел второй сезон, факт новый")
    записано = {}
    monkeypatch.setattr(comments, "_запрос",
                        lambda адрес, **k: записано.update({"адрес": адрес, "тело": k.get("тело")})
                        or (201, '{"id": "c2"}'))
    monkeypatch.setattr(comments, "путь_снятия", lambda s: (True, "проверка"))
    # До записи под карточкой один наш комментарий, после — два: подтверждение
    # операция берёт из СПИСКА, поэтому состояние обязано меняться.
    вызовы = {"n": 0}

    def состояние(site, slug):
        вызовы["n"] += 1
        записи = [{"id": "c1", "author": "Редакция", "created_at": "t",
                   "body": "Первый содержательный комментарий о названии."}]
        if вызовы["n"] > 1:
            записи.append({"id": "c2", "author": "Редакция", "created_at": "t",
                           "body": "Совершенно другой текст про первоисточник."})
        return {"site": "yummyani.org", "slug": slug, "total": len(записи),
                "comments": записи}

    monkeypatch.setattr(comments, "состояние", состояние)
    итог = comments.опубликовать("yummyani.org", "кошка", author="editor/claude/run-1",
                                 тело="Совершенно другой текст про первоисточник.")
    assert итог["state"] == "published"
    assert записано["тело"]["authorName"] == "Редакция"
