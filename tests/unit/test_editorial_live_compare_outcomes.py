"""Сверка текста со страницей: «статус не на той записи» ≠ «страница пуста».

Повод измеренный. 24 и 25.10 прогон дважды напечатал «РАСХОДИТСЯ 8» — то есть
восемь записей утверждают, что текст на странице, а его там нет. 25.10
выяснилось, что для пяти из восьми текст на странице ЕСТЬ: он принадлежит
СОСЕДНЕЙ записи того же адреса (`buffer-batch10-*-rev1`, `repair-*-rev1`), а
статус живого стоит на другой редакции. Разница не стилистическая: в первом
случае посетитель видит пустую карточку, во втором — видит текст, а неверна
разметка реестра.

Поэтому исходов пять, и здесь закреплены оба края: соседняя запись спасает от
ложного «расходится», но НЕ спасает, когда на странице нет ни одной записи
этого адреса.
"""
from __future__ import annotations

import importlib.util
from pathlib import Path

ПУТЬ = (Path(__file__).resolve().parents[2] / "automation" / "local"
        / "editorial-live-compare.py")


def _модуль():
    спец = importlib.util.spec_from_file_location("editorial_live_compare", ПУТЬ)
    м = importlib.util.module_from_spec(спец)
    спец.loader.exec_module(м)
    return м


МОД = _модуль()
ФРАЗА_А = ("Первая запись рассказывает о совершенно другом сюжете и своих"
           " героях, и она достаточно длинная для сравнения по фразам.")
ФРАЗА_Б = ("Вторая запись описывает именно то, что стоит на живой странице,"
           " и её текст тоже достаточно длинный для сверки по фразам.")


def _подмена(страница: str, monkeypatch):
    """Страница отдаётся как есть, а разбор нормализует её так же, как тело.

    Без нормализации сравнение шло бы «нижний регистр против исходного», и
    проверка падала бы на регистре, а не на существе.
    """
    monkeypatch.setattr(МОД, "загрузить", lambda url, т: (страница, ""))
    monkeypatch.setattr(МОД, "текст_страницы",
                        lambda код: (МОД.нормализовать(код), ""))


def test_совпадение_даёт_совпал(monkeypatch):
    _подмена(ФРАЗА_А, monkeypatch)
    и = МОД.сравнить_запись({"body": ФРАЗА_А, "canonical_url": "https://x/a",
                             "status": "ALREADY_LIVE", "content_id": "c1"}, 10)
    assert и["исход"] == "СОВПАЛ"


def test_текст_соседней_записи_на_странице_это_ошибка_разметки(monkeypatch):
    """Главный случай 25.10: страница в порядке, статус стоит не там."""
    _подмена(ФРАЗА_Б, monkeypatch)
    своя = {"body": ФРАЗА_А, "canonical_url": "https://x/a",
            "status": "ALREADY_LIVE", "content_id": "c1"}
    сосед = {"body": ФРАЗА_Б, "canonical_url": "https://x/a",
             "status": "READY_VERIFIED", "content_id": "c2"}
    и = МОД.сравнить_запись(своя, 10, [своя, сосед])
    assert и["исход"] == "СТАТУС НЕ НА ТОЙ ЗАПИСИ"
    assert и["живая_запись"] == "c2"
    assert "c2" in и["почему"] and "READY_VERIFIED" in и["почему"]


def test_без_соседей_остаётся_расходится(monkeypatch):
    """Обратный край: соседи не должны превращать пустую страницу в «в порядке»."""
    _подмена("на странице совсем другой текст про погоду и ничего больше",
             monkeypatch)
    своя = {"body": ФРАЗА_А, "canonical_url": "https://x/a",
            "status": "ALREADY_LIVE", "content_id": "c1"}
    сосед = {"body": ФРАЗА_Б, "canonical_url": "https://x/a",
             "status": "READY_VERIFIED", "content_id": "c2"}
    и = МОД.сравнить_запись(своя, 10, [своя, сосед])
    assert и["исход"] == "РАСХОДИТСЯ"


def test_сама_запись_не_считается_своим_соседом(monkeypatch):
    _подмена("ничего похожего", monkeypatch)
    своя = {"body": ФРАЗА_А, "canonical_url": "https://x/a",
            "status": "ALREADY_LIVE", "content_id": "c1"}
    и = МОД.сравнить_запись(своя, 10, [своя])
    assert и["исход"] == "РАСХОДИТСЯ"


def test_пустое_тело_это_нечего_сравнить():
    и = МОД.сравнить_запись({"body": "  ", "canonical_url": "https://x/a",
                             "status": "ALREADY_LIVE", "content_id": "c1"}, 10)
    assert и["исход"] == "НЕЧЕГО СРАВНИТЬ"


def test_страница_не_отдалась_это_не_измерено(monkeypatch):
    monkeypatch.setattr(МОД, "загрузить", lambda url, т: ("", "HTTP 503"))
    и = МОД.сравнить_запись({"body": ФРАЗА_А, "canonical_url": "https://x/a",
                             "status": "ALREADY_LIVE", "content_id": "c1"}, 10)
    assert и["исход"] == "НЕ ИЗМЕРЕНО" and "503" in и["почему"]


def test_описание_называет_пять_исходов():
    текст = ПУТЬ.read_text(encoding="utf-8")
    for исход in ("СОВПАЛ", "СТАТУС НЕ НА ТОЙ ЗАПИСИ", "РАСХОДИТСЯ",
                  "НЕЧЕГО СРАВНИТЬ", "НЕ ИЗМЕРЕНО"):
        assert исход in текст.split('"""')[1], исход


def test_запись_наложения_витрины_тоже_объясняет_страницу(tmp_path, monkeypatch):
    """Третий источник ответа «чей это текст» — хранилище РАЗМЕЩЕНИЯ.

    Измерено 25.10 на `24-y-okrug-tokio`: текста не было ни в одной записи
    реестра, и прогон объявил расхождение. На деле текст лежал в наложении
    витрины с происхождением `authorized_editorial_batch` — то есть страница
    в порядке, а неверна разметка реестра. Отдельная ловушка внутри той же
    ошибки: у наложения `items` это СПИСОК, и быстрая проверка по ключу слага
    записи не находила.
    """
    домен = "yummyani.test"
    корень = tmp_path / "srv"
    (корень / "stand" / "runtime" / "overlays" / домен).mkdir(parents=True)
    (корень / "stand" / "runtime" / "overlays" / домен / "title-overlays.json").write_text(
        МОД.json.dumps({"items": [
            {"slug": "a", "body": ФРАЗА_Б, "content_id": "batch10-15-a",
             "source_manifest": {"source_type": "authorized_editorial_batch"}},
        ]}, ensure_ascii=False), encoding="utf-8")
    monkeypatch.setattr(МОД, "НАЛОЖЕНИЯ", корень)
    _подмена(ФРАЗА_Б, monkeypatch)
    своя = {"body": ФРАЗА_А, "canonical_url": f"https://{домен}/anime/a",
            "status": "ALREADY_LIVE", "content_id": "c1", "target_site": домен}
    и = МОД.сравнить_запись(своя, 10, [своя])
    assert и["исход"] == "СТАТУС НЕ НА ТОЙ ЗАПИСИ"
    assert и["живая_запись"] == "batch10-15-a"
    assert "authorized_editorial_batch" in и["почему"]


def test_наложение_читается_и_когда_items_словарь(tmp_path, monkeypatch):
    """Обе формы хранилища настоящие, и обе должны читаться."""
    домен = "yummyani.test"
    корень = tmp_path / "srv"
    (корень / "stand" / "runtime" / "overlays" / домен).mkdir(parents=True)
    (корень / "stand" / "runtime" / "overlays" / домен / "title-overlays.json").write_text(
        МОД.json.dumps({"items": {"a": {"slug": "a", "body": ФРАЗА_Б,
                                        "content_id": "x"}}},
                       ensure_ascii=False), encoding="utf-8")
    monkeypatch.setattr(МОД, "НАЛОЖЕНИЯ", корень)
    записи = МОД.записи_наложения(домен)
    assert len(записи) == 1 and записи[0]["content_id"] == "x"
