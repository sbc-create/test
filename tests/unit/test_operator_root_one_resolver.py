"""Очередь и публикация берут корень оператора ОДНИМ способом.

ПОВОД ИЗМЕРЕННЫЙ, 24.10: редакционный цикл вставал на первом шаге.
`queue-next` отказывал словами «в дереве оператора
/home/claude/wt-seo-index-audit-20260930 нет модуля очереди
editorial_queue.py», а публикация в том же прогоне работала. Причина — не
права исполнителя (их проверяют отдельно) и не канал: в `editorial.py` корень
оператора стоял ЖЁСТКОЙ константой, а `queue_bridge` разрешал его резолвером
(переменная окружения → записанный выбор → умолчание). В дереве по умолчанию
есть `title_overlays.py` и НЕТ `editorial_queue.py`; в дереве ремонта есть оба.

Следствие жёсткого пути было двойным: цикл стоял, и запись о выборе корня
(`var/state/seo-operator-root`) действовала наполовину — очередь ей
подчинялась, публикация нет.

Проверяется поведение, а не форма: подставляются пути.
"""
from __future__ import annotations

import importlib
import pathlib
import sys

КОРЕНЬ = pathlib.Path(__file__).resolve().parents[2]
if str(КОРЕНЬ) not in sys.path:
    sys.path.insert(0, str(КОРЕНЬ))

from factory.qwen import editorial, queue_bridge  # noqa: E402


def test_жёсткого_пути_к_дереву_оператора_в_коде_нет():
    """Сторож на возврат константы: именно она ломала цикл."""
    текст = (КОРЕНЬ / "factory" / "qwen" / "editorial.py").read_text(
        encoding="utf-8")
    строки = [с for с in текст.splitlines()
              if "wt-seo-index-audit" in с and not с.lstrip().startswith("#")]
    assert строки == [], строки


def test_обе_половины_дают_один_корень_и_один_интерпретатор():
    assert editorial.ОПЕРАТОР_КОРЕНЬ() == queue_bridge.КОРЕНЬ_ОПЕРАТОРА()
    assert (editorial.ОПЕРАТОР_ИНТЕРПРЕТАТОР()
            == queue_bridge.ИНТЕРПРЕТАТОР())


def test_переменная_окружения_действует_на_публикацию_тоже(monkeypatch,
                                                           tmp_path):
    """Прежде переменную слушала только очередь."""
    monkeypatch.setenv("SEO_OPERATOR_ROOT", str(tmp_path))
    assert editorial.ОПЕРАТОР_КОРЕНЬ() == tmp_path
    assert queue_bridge.КОРЕНЬ_ОПЕРАТОРА() == tmp_path


def test_записанный_выбор_корня_действует_на_публикацию(monkeypatch, tmp_path):
    """Файл `var/state/seo-operator-root` — штатный способ назвать дерево."""
    monkeypatch.delenv("SEO_OPERATOR_ROOT", raising=False)
    дерево = tmp_path / "ремонт"
    дерево.mkdir()
    файл = tmp_path / "seo-operator-root"
    файл.write_text(str(дерево) + "\n", encoding="utf-8")
    monkeypatch.setattr(queue_bridge, "ФАЙЛ_КОРНЯ", файл)
    assert queue_bridge.КОРЕНЬ_ОПЕРАТОРА() == дерево
    assert editorial.ОПЕРАТОР_КОРЕНЬ() == дерево


def test_записанный_но_удалённый_путь_не_подсовывается(monkeypatch, tmp_path):
    """Запись об удалённом каталоге — след прошлого, а не выбор."""
    monkeypatch.delenv("SEO_OPERATOR_ROOT", raising=False)
    файл = tmp_path / "seo-operator-root"
    файл.write_text(str(tmp_path / "нет-такого") + "\n", encoding="utf-8")
    monkeypatch.setattr(queue_bridge, "ФАЙЛ_КОРНЯ", файл)
    выбран = queue_bridge.КОРЕНЬ_ОПЕРАТОРА()
    assert выбран != tmp_path / "нет-такого"
    assert editorial.ОПЕРАТОР_КОРЕНЬ() == выбран


def test_интерпретатор_берётся_у_умолчания_когда_в_дереве_его_нет(monkeypatch,
                                                                  tmp_path):
    """У ветки ремонта своего .venv нет: код оттуда, интерпретатор — общий.

    Без этого запасного пути запись корня на дерево ремонта обменяла бы один
    отказ на другой: очередь нашлась бы, а запускать стало бы нечем.
    """
    monkeypatch.setenv("SEO_OPERATOR_ROOT", str(tmp_path))
    выбран = queue_bridge.ИНТЕРПРЕТАТОР()
    assert str(tmp_path) not in str(выбран), выбран
    assert editorial.ОПЕРАТОР_ИНТЕРПРЕТАТОР() == выбран


def test_записанный_корень_проекта_содержит_оба_модуля():
    """Фактическая проверка установленного выбора, а не только логики.

    Выбор корня осмысленен лишь тогда, когда в дереве есть И очередь, И
    хранилище накладок: цикл использует обе половины.
    """
    корень = queue_bridge.КОРЕНЬ_ОПЕРАТОРА()
    сод = корень / "seo_engine" / "content_operator"
    assert (сод / "editorial_queue.py").is_file(), f"нет очереди в {корень}"
    assert (сод / "title_overlays.py").is_file(), f"нет накладок в {корень}"
    assert queue_bridge.ИНТЕРПРЕТАТОР().is_file()


# --- умолчание пригодно само ------------------------------------------------

def _половинки(корень: pathlib.Path, *имена: str) -> None:
    сод = корень / "seo_engine" / "content_operator"
    сод.mkdir(parents=True, exist_ok=True)
    for имя in имена:
        (сод / имя).write_text("# заглушка\n", encoding="utf-8")


def test_умолчание_выбирает_дерево_с_обеими_половинами(monkeypatch, tmp_path):
    """Лечение записью в var/ не доживает до свежей копии: var/* в .gitignore.

    Поэтому умолчание обязано быть пригодным само, иначе следующая рабочая
    копия встанет на `queue-next` там же, где встала эта.
    """
    только_накладки = tmp_path / "audit"
    оба = tmp_path / "repair"
    _половинки(только_накладки, "title_overlays.py")
    _половинки(оба, "title_overlays.py", "editorial_queue.py")
    monkeypatch.delenv("SEO_OPERATOR_ROOT", raising=False)
    monkeypatch.setattr(queue_bridge, "ФАЙЛ_КОРНЯ", tmp_path / "нет-записи")
    monkeypatch.setattr(queue_bridge, "_КАНДИДАТЫ_УМОЛЧАНИЯ",
                        (str(только_накладки), str(оба)))
    assert queue_bridge.КОРЕНЬ_ОПЕРАТОРА() == оба
    assert editorial.ОПЕРАТОР_КОРЕНЬ() == оба


def test_умолчание_не_перебивает_явный_выбор(monkeypatch, tmp_path):
    """Проверка касается ТОЛЬКО умолчания и не выбирает за оператора."""
    оба = tmp_path / "repair"
    пустое = tmp_path / "явно-указанное"
    _половинки(оба, "title_overlays.py", "editorial_queue.py")
    пустое.mkdir()
    monkeypatch.setattr(queue_bridge, "_КАНДИДАТЫ_УМОЛЧАНИЯ", (str(оба),))
    monkeypatch.setenv("SEO_OPERATOR_ROOT", str(пустое))
    assert queue_bridge.КОРЕНЬ_ОПЕРАТОРА() == пустое, (
        "явно названное дерево должно побеждать даже без половин: иначе"
        " инструмент молча работает не там, куда его послали")


def test_полный_промах_возвращает_прежнее_умолчание(monkeypatch, tmp_path):
    """Прежнее поведение и прежний текст отказа сохраняются.

    По этому отказу уже написаны разборы; подменять его молча нельзя.
    """
    monkeypatch.delenv("SEO_OPERATOR_ROOT", raising=False)
    monkeypatch.setattr(queue_bridge, "ФАЙЛ_КОРНЯ", tmp_path / "нет-записи")
    monkeypatch.setattr(queue_bridge, "_КАНДИДАТЫ_УМОЛЧАНИЯ",
                        (str(tmp_path / "нет-1"), str(tmp_path / "нет-2")))
    assert queue_bridge.КОРЕНЬ_ОПЕРАТОРА() == pathlib.Path(
        queue_bridge._ПО_УМОЛЧАНИЮ)


def test_половины_названы_обе():
    """Проверять одну половину бессмысленно: цикл использует обе."""
    assert set(queue_bridge._ПОЛОВИНЫ) == {"editorial_queue.py",
                                           "title_overlays.py"}
