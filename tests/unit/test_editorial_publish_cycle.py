"""Сквозной круг публикации описаний: ручные поля переживают ПОВТОРЫ.

Повод — живая потеря 2026-10-11. Прогон редактора опубликовал описания на
zonafilm.space, файл правок был заменён целиком, и внесённое решением D200
название исчезло: страница вернулась к оригиналу. Правка «состав собирается из
ЖИВОГО файла плюс свои описания» написана, но в службу MCP не установлена.

Прежние проверки (`test_editorial_name_field_zona01.py`) сторожат ОДНУ
публикацию: они перехватывают подачу и смотрят состав. Этого мало. Потеря
случилась не на первой публикации, а на очередной — файл к тому моменту уже
содержал и чужое поле, и чужие описания. Поэтому здесь круг замыкается:

    состав → содержимое файла (тем же `editorial_store.собрать`, которым
    пишет исполнитель) → запись в живой файл → СЛЕДУЮЩАЯ публикация

и проверяется, что ручное значение переживает второй и третий заход, в том
числе когда описание пишется В ТУ ЖЕ запись.

Авторство оговорено отдельно и намеренно: запись, к которой редактор добавил
описание, переходит в его авторство целиком — «название внесла ЗОНА, описание
внёс редактор» одной строкой журнала не выразить. Значение при этом не
теряется, и это главное.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

КОРЕНЬ = Path(__file__).resolve().parents[2]
if str(КОРЕНЬ) not in sys.path:
    sys.path.insert(0, str(КОРЕНЬ))

from factory.cell import editorial_store  # noqa: E402
from factory.qwen import editorial, registry  # noqa: E402

ИД = "01a1252c-9a84-7175-bcf2-ec7cea1cf1b0"
СЛАГ = "silsila-badalte-rishton-ka"
НАЗВАНИЕ = "История наших отношений"
ОРИГИНАЛ = "Silsila Badalte Rishton Ka"


class Сайт:
    site_id = "zona-01"
    domain = "zonafilm.space"
    adapter = "lords"
    account = "zonafilm-space"


class Круг:
    """Живой файл правок и публикации поверх него, как у исполнителя."""

    def __init__(self, живой: Path, monkeypatch):
        self.живой = живой
        self.monkeypatch = monkeypatch
        self.подач = 0

    def записать(self, правки: dict) -> None:
        """Так пишет исполнитель: содержимое — из `editorial_store.собрать`."""
        содержимое = editorial_store.собрать(
            "zona-01", правки, actor="executor/проба", reason="проба круга")
        self.живой.write_text(json.dumps(содержимое, ensure_ascii=False),
                              encoding="utf-8")

    def опубликовать(self, записи: list[dict], *, author: str) -> dict:
        """Публикация описаний через ту же функцию, что и в службе."""
        поданное: dict = {}

        def подача(s, правки, *, author, reason):
            поданное["правки"] = правки
            # Исполнитель пишет состав в живой файл — повторяем это, иначе
            # следующая публикация читала бы несуществующее состояние.
            self.записать(правки)
            self.подач += 1
            return {"request_id": f"zona-01-edit-проба-{self.подач}"}

        self.monkeypatch.setattr(editorial, "_подать_правки", подача)
        editorial._доставить(Сайт(), записи, записи,
                             поколение=f"g-{self.подач + 1}",
                             author=author, reason="описание")
        return поданное["правки"]

    def состояние(self) -> dict:
        return (json.loads(self.живой.read_text(encoding="utf-8"))
                .get("overrides") or {})


@pytest.fixture()
def круг(tmp_path, monkeypatch):
    живой = tmp_path / "editorial-overrides.json"
    # Исходное состояние: ручное название от другой сессии плюс чужое описание.
    живой.write_text(json.dumps({
        "schema_version": 1,
        "site_id": "zona-01",
        "overrides": {
            СЛАГ: {"fields": {"name": НАЗВАНИЕ, "original_name": ОРИГИНАЛ},
                   "actor": "zona-01/posters-titles/run-7",
                   "reason": "подтверждено по ru-статье и Wikidata (D200)"},
            "dorohedoro-2-2": {"fields": {"description": "Прежнее описание."},
                               "actor": "editor/claude-auto/run-1",
                               "reason": "описание"},
        },
    }, ensure_ascii=False), encoding="utf-8")
    monkeypatch.setattr(registry, "путь_доставки", lambda s: str(живой))
    monkeypatch.setattr(registry, "механизм", lambda s: "editorial-queue")
    monkeypatch.setattr(editorial, "_записать_атомарно", lambda *а, **к: None)
    monkeypatch.setattr(editorial, "_каталог", lambda s: живой.parent)
    monkeypatch.setattr(editorial, "_чужая_правка", lambda s: "")
    return Круг(живой, monkeypatch)


def test_название_переживает_три_публикации_подряд(круг):
    """Главное: потеря случилась на очередной публикации, не на первой."""
    for номер in range(1, 4):
        круг.опубликовать(
            [{"title_id": "dorohedoro-2-2", "body": f"Описание номер {номер}."}],
            author=f"editor/claude-auto/run-{номер}")
        записи = круг.состояние()
        assert СЛАГ in записи, f"название исчезло на публикации {номер}"
        assert записи[СЛАГ]["fields"]["name"] == НАЗВАНИЕ, номер
        assert записи[СЛАГ]["fields"]["original_name"] == ОРИГИНАЛ, номер
        assert записи["dorohedoro-2-2"]["fields"]["description"] == \
            f"Описание номер {номер}."
    assert круг.подач == 3


def test_описание_в_ту_же_запись_не_стирает_название(круг):
    круг.опубликовать([{"title_id": СЛАГ, "body": "Описание сериала."}],
                      author="editor/claude-auto/run-9")
    поля = круг.состояние()[СЛАГ]["fields"]
    assert поля["name"] == НАЗВАНИЕ
    assert поля["original_name"] == ОРИГИНАЛ
    assert поля["description"] == "Описание сериала."


def test_авторство_чужой_записи_сохраняется_пока_её_не_трогают(круг):
    круг.опубликовать([{"title_id": "dorohedoro-2-2", "body": "Новое."}],
                      author="editor/claude-auto/run-9")
    запись = круг.состояние()[СЛАГ]
    assert запись["actor"] == "zona-01/posters-titles/run-7"
    assert "Wikidata" in запись["reason"]


def test_авторство_переходит_к_редактору_когда_он_пишет_в_запись(круг):
    """Оговорённое поведение, а не случайность: значение важнее подписи.

    Одной строкой журнала не выразить «название внесла ЗОНА, описание внёс
    редактор». Поэтому запись, к которой редактор добавил описание, переходит
    в его авторство — но ЗНАЧЕНИЕ названия остаётся.
    """
    круг.опубликовать([{"title_id": СЛАГ, "body": "Описание сериала."}],
                      author="editor/claude-auto/run-9")
    запись = круг.состояние()[СЛАГ]
    assert запись["fields"]["name"] == НАЗВАНИЕ
    assert запись.get("actor") != "zona-01/posters-titles/run-7"


def test_пустое_описание_не_создаёт_запись_и_не_трёт_чужую(круг):
    круг.опубликовать([{"title_id": СЛАГ, "body": "   "},
                       {"title_id": "dorohedoro-2-2", "body": "Есть текст."}],
                      author="editor/claude-auto/run-9")
    записи = круг.состояние()
    assert записи[СЛАГ]["fields"]["name"] == НАЗВАНИЕ
    assert "description" not in записи[СЛАГ]["fields"]
    assert записи["dorohedoro-2-2"]["fields"]["description"] == "Есть текст."


def test_прежний_код_терял_бы_название(круг):
    """Сторожит саму причину: сбор состава ИЗ ОДНИХ описаний теряет поле.

    Проверка намеренно воспроизводит прежнее поведение — иначе нечем показать,
    что исправление исправляет, и правка со временем может «усохнуть» обратно.
    """
    прежний_состав = {
        "dorohedoro-2-2": {"fields": {"description": "Новое описание."}},
    }
    круг.записать(прежний_состав)
    записи = круг.состояние()
    assert СЛАГ not in записи, (
        "состав из одних описаний обязан терять название — иначе эта проверка "
        "ничего не сторожит")


def test_после_потери_значение_восстанавливается_той_же_операцией(круг):
    """Восстановление — обычная правка поля, а не особый путь."""
    круг.записать({"dorohedoro-2-2": {"fields": {"description": "Новое."}}})
    assert СЛАГ not in круг.состояние()
    # Восстановление: тот же состав плюс ручное поле.
    круг.записать({
        "dorohedoro-2-2": {"fields": {"description": "Новое."}},
        СЛАГ: {"fields": {"name": НАЗВАНИЕ},
               "actor": "architect/claude-restore/run-1",
               "reason": "восстановление решения D200"},
    })
    запись = круг.состояние()[СЛАГ]
    assert запись["fields"]["name"] == НАЗВАНИЕ
    assert запись["actor"].startswith("architect/")
    # И следующая публикация описаний его уже не теряет.
    круг.опубликовать([{"title_id": "dorohedoro-2-2", "body": "Ещё одно."}],
                      author="editor/claude-auto/run-10")
    assert круг.состояние()[СЛАГ]["fields"]["name"] == НАЗВАНИЕ
