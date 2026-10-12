"""Доставка между ветвями: отличить «их копия устарела» от «у них своя работа».

Эта разница — весь смысл инструмента. Если копию, в которой есть чужая работа,
объявить устаревшей, следующий шаг — скопировать файл целиком и затереть эту
работу молча. Именно так я чуть не удалил строку SEO-сессии из
`validate_registries.py`, и именно поэтому различение закреплено тестами, а не
осторожностью.

Git здесь настоящий: вопрос «совпадает ли их копия с каким-нибудь МОИМ
коммитом» без истории не ответить. Репозитории одноразовые, в tmp_path.
"""
from __future__ import annotations

import importlib.util
import io
import subprocess
from contextlib import redirect_stdout
from pathlib import Path

import pytest

КОРЕНЬ = Path(__file__).resolve().parents[2]
ИСТОЧНИК = КОРЕНЬ / "automation" / "local" / "delivery-drift.py"


def _модуль():
    спец = importlib.util.spec_from_file_location("drift", ИСТОЧНИК)
    м = importlib.util.module_from_spec(спец)
    спец.loader.exec_module(м)
    return м


@pytest.fixture(scope="module")
def м():
    return _модуль()


def git(репо: Path, *арг: str) -> None:
    subprocess.run(["git", "-C", str(репо), *арг], check=True,
                   capture_output=True, text=True, timeout=120)


def моя_ветвь(tmp_path: Path, версии: list[str]) -> Path:
    """Репозиторий с историей: каждая версия файла — отдельный коммит."""
    корень = tmp_path / "моё"
    (корень / "tests" / "unit").mkdir(parents=True)
    git(корень, "init", "-q", "-b", "main")
    git(корень, "config", "user.email", "s@example.invalid")
    git(корень, "config", "user.name", "стенд")
    for текст in версии:
        (корень / "tests" / "unit" / "проба.py").write_text(текст,
                                                            encoding="utf-8")
        git(корень, "add", "-A")
        git(корень, "commit", "-q", "-m", "версия")
    return корень


def их_ветвь(tmp_path: Path, текст: str) -> Path:
    корень = tmp_path / "их"
    (корень / "tests" / "unit").mkdir(parents=True)
    (корень / "tests" / "unit" / "проба.py").write_text(текст, encoding="utf-8")
    return корень


def прогон(м, моё: Path, их: Path):
    буфер = io.StringIO()
    with redirect_stdout(буфер):
        код = м.главное(["--mine", str(моё), "--theirs", str(их),
                         "--subdir", "tests/unit"])
    return код, буфер.getvalue()


def test_их_копия_это_мой_прежний_коммит(м, tmp_path):
    """Тогда доставлять можно целиком: своей работы у них нет."""
    моё = моя_ветвь(tmp_path, ["версия 1\n", "версия 2\n"])
    их = их_ветвь(tmp_path, "версия 1\n")
    код, вывод = прогон(м, моё, их)
    assert код == 1
    assert "их копия УСТАРЕЛА" in вывод
    # Легенда сменилась вместе с признаками набора: «доставить целиком» теперь
    # сказано как «про ФАЙЛ», потому что про набор говорят отдельные строки.
    assert "про ФАЙЛ" in вывод
    assert "СВОЯ работа" not in вывод
    набор = [с for с in вывод.splitlines()
             if с.strip().startswith(("ВМЕСТЕ С", "НЕ ДОСТАВЛЯТЬ"))]
    assert not набор, f"у одиночного файла нашлись признаки набора: {набор}"


def test_у_них_своя_работа_целиком_копировать_нельзя(м, tmp_path):
    """Главное различение: содержимое не из моей истории."""
    моё = моя_ветвь(tmp_path, ["версия 1\n", "версия 2\n"])
    их = их_ветвь(tmp_path, "версия 1\nих собственная строка\n")
    код, вывод = прогон(м, моё, их)
    assert код == 0, вывод
    assert "СВОЯ работа" in вывод
    assert "переносить построчно" in вывод
    assert "УСТАРЕЛА" not in вывод


def test_совпадающие_файлы_молчат(м, tmp_path):
    моё = моя_ветвь(tmp_path, ["версия 1\n"])
    их = их_ветвь(tmp_path, "версия 1\n")
    код, вывод = прогон(м, моё, их)
    assert код == 0
    assert "файлов совпало 1" in вывод
    assert "УСТАРЕЛА" not in вывод and "СВОЯ работа" not in вывод


def test_разный_состав_ветвей_расхождением_не_считается(м, tmp_path):
    моё = моя_ветвь(tmp_path, ["версия 1\n"])
    их = их_ветвь(tmp_path, "версия 1\n")
    (моё / "tests" / "unit" / "только_моё.py").write_text("x\n", encoding="utf-8")
    (их / "tests" / "unit" / "только_их.py").write_text("y\n", encoding="utf-8")
    код, вывод = прогон(м, моё, их)
    assert код == 0
    assert "только в моей ветви: 1; только у них: 1" in вывод
    assert "не расхождение" in вывод


def test_предел_глубины_ограничивает_поиск(м, tmp_path):
    """Ожидание ограничено ЧИСЛОМ коммитов, а не «пока не найдётся» (D205).

    За пределом совпадение не находится, и тогда файл честно попадает в «своя
    работа» — вывод осторожнее, чем ложное «устарела».
    """
    моё = моя_ветвь(tmp_path, [f"версия {i}\n" for i in range(1, 6)])
    их = их_ветвь(tmp_path, "версия 1\n")
    буфер = io.StringIO()
    with redirect_stdout(буфер):
        м.главное(["--mine", str(моё), "--theirs", str(их),
                   "--subdir", "tests/unit", "--depth", "2"])
    assert "СВОЯ работа" in буфер.getvalue()


def test_парный_файл_назван_вместе_с_этим(м, tmp_path):
    """Поправка по измерению SEO-сессии: доставка — про НАБОР, не про файл.

    Новый `build_release.py` без парного перечня в `extract.py` валит проверку,
    которая читает ОБА файла, а менялись они РАЗНЫМИ коммитами — «тот же
    коммит» такую пару не находит. Находит её тест, упоминающий оба.
    """
    моё = моя_ветвь(tmp_path, ["версия 1\n", "версия 2\n"])
    # Второй расходящийся файл и проверка, читающая оба.
    (моё / "factory" / "cell").mkdir(parents=True)
    (моё / "factory" / "cell" / "парный.py").write_text("ПЕРЕЧЕНЬ = (1, 2)\n",
                                                        encoding="utf-8")
    (моё / "tests" / "unit" / "test_пара.py").write_text(
        "# читает проба.py и парный.py\n", encoding="utf-8")
    git(моё, "add", "-A")
    git(моё, "commit", "-q", "-m", "пара")
    (моё / "factory" / "cell" / "парный.py").write_text("ПЕРЕЧЕНЬ = (1, 2, 3)\n",
                                                        encoding="utf-8")
    git(моё, "add", "-A")
    git(моё, "commit", "-q", "-m", "перечень вырос")

    их = их_ветвь(tmp_path, "версия 1\n")
    (их / "factory" / "cell").mkdir(parents=True)
    (их / "factory" / "cell" / "парный.py").write_text("ПЕРЕЧЕНЬ = (1, 2)\n",
                                                       encoding="utf-8")
    буфер = io.StringIO()
    with redirect_stdout(буфер):
        м.главное(["--mine", str(моё), "--theirs", str(их),
                   "--subdir", "tests/unit", "--subdir", "factory/cell"])
    вывод = буфер.getvalue()
    assert "ВМЕСТЕ С" in вывод, вывод
    assert "по одному нельзя" in вывод
    assert "читающая оба файла" in вывод, "связь названа неверно"


def test_предмет_проверки_отсутствует_в_цели(м, tmp_path):
    """«Их копия — мой прежний коммит» необходимо, но НЕ достаточно."""
    моё = моя_ветвь(tmp_path, ["версия 1\n"])
    (моё / "factory" / "cell").mkdir(parents=True)
    (моё / "factory" / "cell" / "модуль.py").write_text(
        "def новая_функция():\n    return 1\n", encoding="utf-8")
    (моё / "tests" / "unit" / "test_предмет.py").write_text(
        "from factory.cell import модуль as м\n"
        "def test_зовёт():\n    assert м.новая_функция() == 1\n",
        encoding="utf-8")
    git(моё, "add", "-A")
    git(моё, "commit", "-q", "-m", "предмет и тест")
    (моё / "tests" / "unit" / "test_предмет.py").write_text(
        "from factory.cell import модуль as м\n"
        "def test_зовёт():\n    assert м.новая_функция() == 1  # правка\n",
        encoding="utf-8")
    git(моё, "add", "-A")
    git(моё, "commit", "-q", "-m", "правка теста")

    их = их_ветвь(tmp_path, "версия 1\n")
    (их / "factory" / "cell").mkdir(parents=True)
    (их / "factory" / "cell" / "модуль.py").write_text(
        "def старая_функция():\n    return 0\n", encoding="utf-8")
    (их / "tests" / "unit" / "test_предмет.py").write_text(
        "from factory.cell import модуль as м\n"
        "def test_зовёт():\n    assert м.новая_функция() == 1\n",
        encoding="utf-8")
    буфер = io.StringIO()
    with redirect_stdout(буфер):
        м.главное(["--mine", str(моё), "--theirs", str(их),
                   "--subdir", "tests/unit", "--subdir", "factory/cell"])
    вывод = буфер.getvalue()
    находки = [с for с in вывод.splitlines()
               if с.strip().startswith("чего нет в цели")]
    assert находки, вывод
    assert "нет новая_функция" in вывод
    # Спутник назван, значит сказано, что недостающее принесёт он.
    assert "принесёт спутник" in вывод or "доставлять нельзя" in вывод


def test_поведенческую_разницу_инструмент_не_видит(м, tmp_path):
    """Граница названа честно, а не обойдена молчанием.

    Тест может падать в цели не из-за пропавшего символа, а из-за ИНОГО
    поведения того же символа (у SEO-сессии так падала передача черновика:
    имя проверяющего). Такого инструмент не видит и видеть не может, поэтому
    полный прогон остаётся обязательным — и он молчит, а не утверждает
    «доставлять безопасно».
    """
    моё = моя_ветвь(tmp_path, ["версия 1\n"])
    (моё / "factory" / "cell").mkdir(parents=True)
    (моё / "factory" / "cell" / "модуль.py").write_text(
        'def имя():\n    return "новое"\n', encoding="utf-8")
    (моё / "tests" / "unit" / "test_поведение.py").write_text(
        "from factory.cell import модуль as м\n"
        'def test_имя():\n    assert м.имя() == "новое"\n', encoding="utf-8")
    git(моё, "add", "-A")
    git(моё, "commit", "-q", "-m", "поведение")
    (моё / "tests" / "unit" / "test_поведение.py").write_text(
        "from factory.cell import модуль as м\n"
        'def test_имя():\n    assert м.имя() == "новое"  # правка\n',
        encoding="utf-8")
    git(моё, "add", "-A")
    git(моё, "commit", "-q", "-m", "правка")

    их = их_ветвь(tmp_path, "версия 1\n")
    (их / "factory" / "cell").mkdir(parents=True)
    # Символ ЕСТЬ, но ведёт себя иначе.
    (их / "factory" / "cell" / "модуль.py").write_text(
        'def имя():\n    return "прежнее"\n', encoding="utf-8")
    (их / "tests" / "unit" / "test_поведение.py").write_text(
        "from factory.cell import модуль as м\n"
        'def test_имя():\n    assert м.имя() == "новое"\n', encoding="utf-8")
    буфер = io.StringIO()
    with redirect_stdout(буфер):
        м.главное(["--mine", str(моё), "--theirs", str(их),
                   "--subdir", "tests/unit", "--subdir", "factory/cell"])
    вывод = буфер.getvalue()
    # Утверждение про НАХОДКУ, а не про строку легенды: легенда упоминает
    # «НЕ ДОСТАВЛЯТЬ» всегда, и первая редакция теста ловила именно её.
    находки = [с for с in вывод.splitlines()
               if с.strip().startswith("чего нет в цели")]
    assert not находки, (
        f"инструмент заявил о том, чего не умеет измерить: {находки}")


def test_нет_каталога_у_одной_стороны_это_не_измерено(м, tmp_path):
    моё = моя_ветвь(tmp_path, ["версия 1\n"])
    их = tmp_path / "пусто"
    их.mkdir()
    код, вывод = прогон(м, моё, их)
    assert код == 0
    assert "нет в одной из ветвей" in вывод


def test_тест_и_код_под_ним_называются_парой(м, tmp_path):
    """Пара «тест ↔ код, который он проверяет» обязана ехать вместе.

    Прежний признак искал ТЕСТЫ, упоминающие имя файла, и для файла теста не
    находил ничего: тест своего имени в тексте не содержит. Поэтому пара
    молчала — проверено 12.10 на `test_comment_draft_handoff` ↔
    `factory/qwen/comments.py`, которые остались у SEO-сессии на ОДНОМ прежнем
    коммите. Доставить тест без кода — получить красное; код без теста —
    потерять проверку.
    """
    моё = моя_ветвь(tmp_path, ["версия 1\n"])
    (моё / "factory" / "qwen").mkdir(parents=True)
    (моё / "factory" / "qwen" / "модуль.py").write_text(
        "def имя():\n    return 1\n", encoding="utf-8")
    (моё / "tests" / "unit" / "test_пара_кода.py").write_text(
        "from factory.qwen import модуль\n"
        "def test_зовёт():\n    assert модуль.имя() == 1\n", encoding="utf-8")
    git(моё, "add", "-A")
    git(моё, "commit", "-q", "-m", "пара теста и кода")
    # Обе стороны расходятся: правим и код, и тест.
    (моё / "factory" / "qwen" / "модуль.py").write_text(
        "def имя():\n    return 2\n", encoding="utf-8")
    (моё / "tests" / "unit" / "test_пара_кода.py").write_text(
        "from factory.qwen import модуль\n"
        "def test_зовёт():\n    assert модуль.имя() == 2\n", encoding="utf-8")
    git(моё, "add", "-A")
    git(моё, "commit", "-q", "-m", "обе стороны")

    их = их_ветвь(tmp_path, "версия 1\n")
    (их / "factory" / "qwen").mkdir(parents=True)
    (их / "factory" / "qwen" / "модуль.py").write_text(
        "def имя():\n    return 1\n", encoding="utf-8")
    (их / "tests" / "unit" / "test_пара_кода.py").write_text(
        "from factory.qwen import модуль\n"
        "def test_зовёт():\n    assert модуль.имя() == 1\n", encoding="utf-8")

    буфер = io.StringIO()
    with redirect_stdout(буфер):
        м.главное(["--mine", str(моё), "--theirs", str(их),
                   "--subdir", "tests/unit", "--subdir", "factory/qwen"])
    вывод = буфер.getvalue()
    строки = [с for с in вывод.splitlines() if "ВМЕСТЕ С" in с]
    assert строки, вывод
    assert "factory/qwen/модуль.py" in строки[0], строки
    assert "этот тест проверяет их код" in строки[0], строки
