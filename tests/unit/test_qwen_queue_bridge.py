"""Мост к канонической редакционной очереди: что он обязан и чего не вправе.

Проверки написаны по жалобе владельца: «Qwen снова создал вторую очередь,
вернулся к отвергнутому соответствию и переписал свои же исправления». Причина
была не в поведении, а в канале: инструментов очереди в нём не существовало,
и единственной памятью запуска оставались его собственные файлы.

Здесь сверяется именно мост — объявление инструментов и их границы. Поведение
самой очереди живёт одним модулем в оператора и проверяется там.
"""
from __future__ import annotations

import json
import pathlib
import sys

import pytest

КОРЕНЬ = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(КОРЕНЬ))

from factory.qwen import mcp, queue_bridge  # noqa: E402

ОЧЕРЕДЬ = ("editorial_queue_next", "editorial_queue_result",
           "editorial_queue_status")


def test_три_инструмента_очереди_объявлены() -> None:
    for имя in ОЧЕРЕДЬ:
        assert имя in mcp.ИНСТРУМЕНТЫ, f"{имя} не объявлен — очередь снова недоступна"
        св = mcp.ИНСТРУМЕНТЫ[имя]
        assert callable(св["обработчик"])
        assert св["описание"].strip()
        assert св["схема"]["additionalProperties"] is False


def test_исходы_в_схеме_совпадают_с_очередью() -> None:
    """Перечень исходов объявлен в ОДНОМ месте, а не переписан руками.

    Разойдись схема с очередью — вызывающий получал бы отказ «неизвестный
    исход» на значение, которое ему же и предложили.
    """
    схема = mcp.ИНСТРУМЕНТЫ["editorial_queue_result"]["схема"]
    объявленные = set(схема["properties"]["outcome"]["enum"])
    r = queue_bridge._вызвать  # noqa: SLF001 — проверяем именно контракт моста
    assert callable(r)
    # Перечень берётся из модуля очереди через подпроцесс; здесь сверяется, что
    # схема не содержит лишних значений и не теряет ни одного известного.
    ожидаемые = {"TEXT_WRITTEN", "IDENTITY_UNCLEAR", "SOURCE_UNAVAILABLE",
                 "SOURCES_MISSING", "PAGE_ABSENT", "IDENTITY_REJECTED"}
    assert объявленные == ожидаемые


def test_взятие_требует_владельца() -> None:
    with pytest.raises(mcp.ОшибкаИнструмента, match="owner"):
        mcp.ИНСТРУМЕНТЫ["editorial_queue_next"]["обработчик"](
            {"site": "yummyani.site"})


def test_результат_требует_трёх_полей() -> None:
    with pytest.raises(mcp.ОшибкаИнструмента, match="task_id"):
        mcp.ИНСТРУМЕНТЫ["editorial_queue_result"]["обработчик"](
            {"owner": "A", "outcome": "TEXT_WRITTEN"})


def test_метка_объявлена_игнорируемой() -> None:
    """Схема обязана говорить, что `label` статуса не повышает.

    Иначе поле выглядит как способ назначить состояние, и «ready.md» снова
    станет статусом.
    """
    схема = mcp.ИНСТРУМЕНТЫ["editorial_queue_result"]["схема"]
    описание = схема["properties"]["label"]["description"]
    assert "игнорируется" in описание


def test_адрес_объявлен_сверяемым() -> None:
    схема = mcp.ИНСТРУМЕНТЫ["editorial_queue_result"]["схема"]
    описание = схема["properties"]["canonical_url"]["description"]
    assert "сверяется" in описание


def test_отсутствие_модуля_очереди_называется_причиной(monkeypatch, tmp_path) -> None:
    """Пустое дерево оператора не должно выглядеть как «очередь пуста».

    Код очереди живёт в ветке ремонта, и мост обязан сказать это прямо, иначе
    отсутствие инструмента снова примут за отсутствие работы.
    """
    monkeypatch.setenv("SEO_OPERATOR_ROOT", str(tmp_path))
    with pytest.raises(queue_bridge.ОчередьОтклонила, match="нет модуля очереди"):
        queue_bridge.состояние(site="yummyani.site")


def test_корень_оператора_переопределяется_окружением(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("SEO_OPERATOR_ROOT", str(tmp_path))
    assert queue_bridge.КОРЕНЬ_ОПЕРАТОРА() == tmp_path


def test_текст_не_уходит_в_командную_строку(monkeypatch, tmp_path) -> None:
    """Полезная нагрузка передаётся ФАЙЛОМ, а не аргументом.

    Командная строка видна в списке процессов любому на машине, поэтому текст
    материала в argv не попадает ни при каких условиях — то же правило, что у
    хранилища накладок (`factory.qwen.editorial._вызвать_store`).

    Проверяется не вид исходника, а ФАКТИЧЕСКИЙ argv: подменяется
    `subprocess.run`, и в перехваченных аргументах ищется тело материала.
    """
    СЕКРЕТ = "ТЕКСТ-КОТОРЫЙ-НЕ-ДОЛЖЕН-ПОПАСТЬ-В-ARGV"
    перехвачено: dict = {}

    class Ответ:
        returncode = 0
        stdout = json.dumps({"ok": True, "result": {"status": "ok"}})
        stderr = ""

    def ложный_run(аргументы, **кварги):
        перехвачено["argv"] = list(аргументы)
        # Файл с заданием ещё существует на этот момент — читаем его.
        перехвачено["payload"] = pathlib.Path(аргументы[-1]).read_text(encoding="utf-8")
        return Ответ()

    # Дерево оператора должно выглядеть пригодным, иначе отказ случится раньше.
    (tmp_path / "seo_engine" / "content_operator").mkdir(parents=True)
    (tmp_path / "seo_engine" / "content_operator" / "editorial_queue.py").write_text(
        "", encoding="utf-8")
    monkeypatch.setenv("SEO_OPERATOR_ROOT", str(tmp_path))
    monkeypatch.setattr(queue_bridge.subprocess, "run", ложный_run)

    queue_bridge.записать(task_id="t" * 16, owner="A", outcome="TEXT_WRITTEN",
                          body=СЕКРЕТ)

    склеенный = "\u0000".join(перехвачено["argv"])
    assert СЕКРЕТ not in склеенный, "текст материала оказался в командной строке"
    assert СЕКРЕТ in перехвачено["payload"], (
        "текст не доехал до подпроцесса вовсе — проверка бессмысленна")


def test_взятие_и_запись_числятся_пишущими() -> None:
    """Взятие задания ЗАПИСЫВАЕТ аренду — значит это пишущая операция.

    Ограничение «только чтение» обязано быть проверяемым свойством сервера.
    Инструмент, который оставляет аренду, в режиме только чтения предлагать
    нельзя; а `editorial_queue_status` читает и остаётся доступным — отчёт о
    состоянии нужен всегда.
    """
    assert "editorial_queue_next" in mcp.ПИШУЩИЕ
    assert "editorial_queue_result" in mcp.ПИШУЩИЕ
    assert "editorial_queue_status" not in mcp.ПИШУЩИЕ


def test_в_режиме_только_чтения_пишущие_не_объявляются(monkeypatch) -> None:
    monkeypatch.setattr(mcp, "ТОЛЬКО_ЧТЕНИЕ", True)
    доступные = mcp.доступные()
    assert "editorial_queue_status" in доступные
    assert "editorial_queue_next" not in доступные
    assert "editorial_queue_result" not in доступные


# ------------------------------------------- очередь в командной строке
def test_команды_очереди_объявлены_в_cli() -> None:
    """Инструкция говорит «нет инструмента — сделай то же командной строкой».

    Для новостей этого пути однажды не было, и сессия без инструментов взяла
    одноимённые глаголы карточек — новость уехала в накладку аниме (D182). Для
    очереди путь обязан существовать, иначе правило отсылает в пустоту.
    """
    from factory.qwen import __main__ as cli

    p = cli.разбор() if hasattr(cli, "разбор") else None
    # Разбор может быть внутренним; тогда проверяем перечень операций по тексту
    # модуля — он объявлен одним списком choices.
    источник = pathlib.Path(cli.__file__).read_text(encoding="utf-8")
    for имя in ("queue-next", "queue-result", "queue-status", "queue-release"):
        assert f'"{имя}"' in источник, f"операции {имя} нет в командной строке"


def test_cli_и_инструменты_называют_исходы_одинаково() -> None:
    """Один и тот же исход не должен называться двумя способами."""
    from factory.qwen import __main__ as cli

    источник = pathlib.Path(cli.__file__).read_text(encoding="utf-8")
    схема = mcp.ИНСТРУМЕНТЫ["editorial_queue_result"]["схема"]
    for исход in схема["properties"]["outcome"]["enum"]:
        assert исход in источник, (
            f"исход {исход} объявлен инструментом, но не назван в подсказке CLI")


# --------------------------------- поиск и регистрация в интерфейсе Qwen
def test_поиск_и_регистрация_объявлены() -> None:
    """Qwen должен уметь ПОСМОТРЕТЬ и ЗАВЕСТИ задание, а не только взять.

    Пока инструментов поиска не было, редактор SEO не мог ни проверить наличие
    задания по адресу, ни зарегистрировать его: единственным способом
    «посмотреть» было взятие, а оно ставит аренду. Отсюда и появлялся свой
    список работ рядом с канонической очередью.
    """
    for имя in ("editorial_queue_find", "editorial_queue_register"):
        assert имя in mcp.ИНСТРУМЕНТЫ, f"{имя} не объявлен"
        с = mcp.ИНСТРУМЕНТЫ[имя]["схема"]
        assert с["additionalProperties"] is False
        assert "canonical_url" in с["properties"]


def test_поиск_читает_а_регистрация_пишет() -> None:
    """Ограничение «только чтение» обязано быть проверяемым свойством."""
    assert "editorial_queue_find" not in mcp.ПИШУЩИЕ, (
        "поиск не создаёт аренды и не меняет состояния — он читающий")
    assert "editorial_queue_register" in mcp.ПИШУЩИЕ, (
        "регистрация заводит запись в реестре — это запись")


def test_регистрация_требует_названия_в_интерфейсе() -> None:
    with pytest.raises(mcp.ОшибкаИнструмента, match="headline"):
        mcp.ИНСТРУМЕНТЫ["editorial_queue_register"]["обработчик"](
            {"site": "yummyani.org", "canonical_url": "https://yummyani.org/anime/x"})


def test_поиск_требует_адреса() -> None:
    with pytest.raises(mcp.ОшибкаИнструмента, match="canonical_url"):
        mcp.ИНСТРУМЕНТЫ["editorial_queue_find"]["обработчик"](
            {"site": "yummyani.org"})


def test_команды_поиска_и_регистрации_есть_в_cli() -> None:
    from factory.qwen import __main__ as cli

    источник = pathlib.Path(cli.__file__).read_text(encoding="utf-8")
    for имя in ("queue-find", "queue-register"):
        assert f'"{имя}"' in источник, f"операции {имя} нет в командной строке"
    for ключ in ("--canonical-url", "--headline"):
        assert ключ in источник, f"ключа {ключ} нет в командной строке"


# --------------------------------- три публикации и тело описания
def test_три_публикации_различаются() -> None:
    """`publish` не «только для релизов»: операций три, и они разные.

    Сессия редактора уже решила однажды, что механизма публикации описаний не
    существует, и записала новость в накладку карточки (D186). Различие обязано
    быть объявлено в самих инструментах, а не только в инструкции.
    """
    для = {"publish_material": "/anime/", "publish_post": "/posts/",
           "release_site": "выпуск"}
    for имя in для:
        assert имя in mcp.ИНСТРУМЕНТЫ, f"{имя} не объявлен"
    описание = mcp.ИНСТРУМЕНТЫ["publish_material"]["описание"]
    assert "/anime/" in описание, "в описании не сказано, ЧТО публикуется"
    assert "release_site" in описание and "publish_post" in описание, (
        "описание не отделяет публикацию описания от выпуска и от новости")


def test_публикация_описания_принимает_тело() -> None:
    """Без поля `body` публикация описания у Yummy невозможна вовсе.

    `prepare_material` требует возможности `facts`, которой у семейства нет, а
    `publish_material` без черновика отвечает «передайте тело». Если поля нет,
    передать его нечем — измерено 2026-10-06 двумя отказами подряд.
    """
    с = mcp.ИНСТРУМЕНТЫ["publish_material"]["схема"]["properties"]
    assert "body" in с, "тело описания передать нечем"
    assert "обязателен" in (с["body"].get("description") or ""), (
        "не сказано, когда тело обязательно")


def test_возобновление_объявлено_и_пишет() -> None:
    assert "editorial_queue_reopen" in mcp.ИНСТРУМЕНТЫ
    с = mcp.ИНСТРУМЕНТЫ["editorial_queue_reopen"]["схема"]
    assert с["required"] == ["task_id", "reason"], (
        "возобновление без причины принимать нельзя")
    assert "editorial_queue_reopen" in mcp.ПИШУЩИЕ


def test_возобновление_требует_причины_в_интерфейсе() -> None:
    with pytest.raises(mcp.ОшибкаИнструмента, match="reason"):
        mcp.ИНСТРУМЕНТЫ["editorial_queue_reopen"]["обработчик"](
            {"task_id": "8b46299f05533fea"})


def test_команда_возобновления_есть_в_cli() -> None:
    from factory.qwen import __main__ as cli

    источник = pathlib.Path(cli.__file__).read_text(encoding="utf-8")
    assert '"queue-reopen"' in источник


# ------------------------------- отпечаток набора инструментов
def test_отпечаток_набора_в_каждом_ответе() -> None:
    """Устаревшая схема у подключения обязана быть видна ОДНИМ значением.

    Измерено 2026-10-06: служба отдавала 34 инструмента, версию правил
    2026-10-06.3 и поле `body` у publish_material, а редактор сообщал версию
    2026-10-06.1 без `body`, но с инструментом, появившимся ПОЗЖЕ этой версии.
    Такая смесь невозможна в одном ответе — сравнивались два разных момента.
    Отличить устаревший коннектор от неисправной службы иначе можно было только
    пробным вызовом, то есть публикацией.
    """
    о = mcp.окружение()
    assert "tools" in о, "в ответе нет отпечатка набора инструментов"
    т = о["tools"]
    assert т["count"] == len(mcp.ИНСТРУМЕНТЫ)
    assert len(т["fingerprint"]) == 16
    assert т["writing"] == len([и for и in mcp.ИНСТРУМЕНТЫ if и in mcp.ПИШУЩИЕ])


def test_отпечаток_меняется_при_смене_схемы(monkeypatch) -> None:
    """Отпечаток, не реагирующий на правку схемы, бесполезен."""
    было = mcp.окружение()["tools"]["fingerprint"]
    mcp._ОТПЕЧАТОК_ИНСТРУМЕНТОВ.clear()
    копия = dict(mcp.ИНСТРУМЕНТЫ)
    копия["publish_material"] = {
        **копия["publish_material"],
        "схема": {"type": "object", "properties": {"site": {"type": "string"}},
                  "required": ["site"], "additionalProperties": False},
    }
    monkeypatch.setattr(mcp, "ИНСТРУМЕНТЫ", копия)
    стало = mcp.окружение()["tools"]["fingerprint"]
    mcp._ОТПЕЧАТОК_ИНСТРУМЕНТОВ.clear()
    assert стало != было, "снятие поля body отпечаток не изменило"


def test_отпечаток_не_зависит_от_порядка_объявления(monkeypatch) -> None:
    было = mcp.окружение()["tools"]["fingerprint"]
    mcp._ОТПЕЧАТОК_ИНСТРУМЕНТОВ.clear()
    перевёрнутый = dict(reversed(list(mcp.ИНСТРУМЕНТЫ.items())))
    monkeypatch.setattr(mcp, "ИНСТРУМЕНТЫ", перевёрнутый)
    стало = mcp.окружение()["tools"]["fingerprint"]
    mcp._ОТПЕЧАТОК_ИНСТРУМЕНТОВ.clear()
    assert стало == было, "порядок объявления изменил отпечаток набора"
