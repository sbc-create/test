"""Шаблоны проверок витрин обязаны УМЕТЬ упасть.

Эти файлы копируются в репозиторий каждой витрины и там решают, выпускать её
или нет. Проверка, которая не умеет упасть, доверия не несёт (D205), а шаг,
проходящий на неисправленном состоянии, вердикта не даёт (D203) — поэтому
шаблоны проверяются на подставных витринах, где «исправность» задаётся нарочно.

Шаблоны — сценарии: они выводят корень из `__file__` и завершаются
`sys.exit`. Поэтому запускаются через `exec` с подставленным `__file__`, а
исход читается из `SystemExit`.
"""
from __future__ import annotations

import io
import json
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

import pytest

КОРЕНЬ = Path(__file__).resolve().parents[2]
ШАБЛОНЫ = КОРЕНЬ / "factory" / "cell" / "site_checks"

#: Витрина, которая отказывает без каталога данных и соглашается с любым
#: переданным. Ровно то состояние, которое `fails_closed` обязан поймать:
#: «запуск отказывает» выполнено, «не подставляет чужое» — нет.
БЕРЁТ_ЛЮБОЙ_КАТАЛОГ = """\
import sys
if "--data-dir" not in sys.argv:
    print("нет каталога данных", file=sys.stderr)
    raise SystemExit(78)
raise SystemExit(0)
"""

#: Витрина, которая отказывает всегда: исправное поведение.
ОТКАЗЫВАЕТ_ВСЕГДА = """\
import sys
print("каталог данных не мой", file=sys.stderr)
raise SystemExit(78)
"""

#: Витрина, которая запускается вообще без каталога данных.
ЗАПУСКАЕТСЯ_БЕЗ_КАТАЛОГА = "raise SystemExit(0)\n"


def витрина(tmp_path: Path, пускатель: str, *, соседи=("lords-02",),
            site_id: str = "проба-01") -> Path:
    корень = tmp_path / "витрина"
    (корень / "checks").mkdir(parents=True, exist_ok=True)
    (корень / "config").mkdir(parents=True, exist_ok=True)
    (корень / "run.py").write_text(пускатель, encoding="utf-8")
    (корень / "config" / "site.json").write_text(json.dumps({
        "site_id": site_id, "neighbour_site_ids": list(соседи),
        "entrypoint": "frontend.py"}, ensure_ascii=False), encoding="utf-8")
    return корень


def прогнать(имя: str, корень: Path) -> tuple[int, str, str]:
    источник = (ШАБЛОНЫ / имя).read_text(encoding="utf-8")
    ошибки, вывод = io.StringIO(), io.StringIO()
    код = 0
    глоб = {"__name__": "__main__", "__file__": str(корень / "checks" / имя)}
    try:
        with redirect_stdout(вывод), redirect_stderr(ошибки):
            exec(compile(источник, имя, "exec"), глоб)
    except SystemExit as выход:
        код = выход.code or 0
    return код, вывод.getvalue(), ошибки.getvalue()


# --------------------------------------------------------------------------- #
#  fails_closed: изоляция данных между сайтами.
# --------------------------------------------------------------------------- #
def test_витрина_берущая_любой_каталог_не_проходит(tmp_path):
    """Главное свойство: шаг ловит витрину, согласную на чужие данные."""
    код, _вывод, ошибки = прогнать("fails_closed.py",
                                   витрина(tmp_path, БЕРЁТ_ЛЮБОЙ_КАТАЛОГ))
    assert код == 1, ошибки
    assert "не отказал" in ошибки


def test_исправная_витрина_проходит(tmp_path):
    код, вывод, ошибки = прогнать("fails_closed.py",
                                  витрина(tmp_path, ОТКАЗЫВАЕТ_ВСЕГДА))
    assert код == 0, ошибки
    assert "отказ подтверждён" in вывод


def test_запуск_без_каталога_обязан_отказать(tmp_path):
    код, _вывод, ошибки = прогнать("fails_closed.py",
                                   витрина(tmp_path, ЗАПУСКАЕТСЯ_БЕЗ_КАТАЛОГА))
    assert код == 1
    assert "без --data-dir не отказал" in ошибки


def test_без_поля_соседей_шаг_отказывает(tmp_path):
    корень = витрина(tmp_path, ОТКАЗЫВАЕТ_ВСЕГДА)
    (корень / "config" / "site.json").write_text(
        json.dumps({"site_id": "проба-01", "entrypoint": "frontend.py"}),
        encoding="utf-8")
    код, _вывод, ошибки = прогнать("fails_closed.py", корень)
    assert код == 1
    assert "neighbour_site_ids" in ошибки


def test_берётся_настоящий_чужой_каталог_а_не_путь_из_site_id(tmp_path):
    """Поправка по измерению SEO-сессии 12.10.

    Прежняя редакция брала `/srv/<site_id>/data`, а каталоги в `/srv` названы
    по РЕПОЗИТОРИЮ: такого пути нет ни у одной ячейки. Шаг доказывал лишь
    «каталога нет → отказ» и регрессию «витрина берёт любой `*-catalog.json`»
    не поймал бы. Теперь чужой каталог ищется на машине по имени снимка.
    """
    код, вывод, ошибки = прогнать("fails_closed.py",
                                  витрина(tmp_path, ОТКАЗЫВАЕТ_ВСЕГДА))
    assert код == 0, ошибки
    если_нашёлся = "ЗАМЕЧАНИЕ" not in ошибки
    if если_нашёлся:
        # На этой машине чужие каталоги есть — значит проверен настоящий путь.
        assert "/srv/" in вывод and "chuzhoy-sayt" not in вывод, вывод
    else:
        # Иначе слабость названа вслух, а не проглочена.
        assert "она слабее" in ошибки, ошибки


def test_отсутствие_чужого_каталога_называется_вслух(tmp_path, monkeypatch):
    """Молчаливого «прошло» быть не должно: без чужого каталога шаг слабее."""
    источник = (ШАБЛОНЫ / "fails_closed.py").read_text(encoding="utf-8")
    подменённый = источник.replace('Path("/srv")', f'Path("{tmp_path / "нет"}")')
    assert подменённый != источник, "строка с корнем данных не нашлась"
    корень = витрина(tmp_path, ОТКАЗЫВАЕТ_ВСЕГДА)
    ошибки, вывод = io.StringIO(), io.StringIO()
    код = 0
    глоб = {"__name__": "__main__",
            "__file__": str(корень / "checks" / "fails_closed.py")}
    try:
        with redirect_stdout(вывод), redirect_stderr(ошибки):
            exec(compile(подменённый, "fails_closed.py", "exec"), глоб)
    except SystemExit as выход:
        код = выход.code or 0
    assert код == 0
    assert "ЗАМЕЧАНИЕ" in ошибки.getvalue()
    assert "она слабее" in ошибки.getvalue()


# --------------------------------------------------------------------------- #
#  no_secrets: секрет и в имени файла, и внутри него.
# --------------------------------------------------------------------------- #
def репозиторий_с_файлом(tmp_path: Path, имя: str, содержимое: str) -> Path:
    """Подставной репозиторий с настоящим git: шаблон спрашивает индекс."""
    import subprocess
    корень = tmp_path / "репо"
    (корень / "checks").mkdir(parents=True, exist_ok=True)
    (корень / имя).parent.mkdir(parents=True, exist_ok=True)
    (корень / имя).write_text(содержимое, encoding="utf-8")
    for арг in (("init", "-q"), ("config", "user.email", "s@example.invalid"),
                ("config", "user.name", "стенд"), ("add", "-A"),
                ("commit", "-q", "-m", "стенд")):
        subprocess.run(["git", "-C", str(корень), *арг], check=True,
                       capture_output=True)
    return корень


def test_секрет_внутри_файла_с_безобидным_именем_находится(tmp_path):
    """Список имён такого не ловит: имя файла здесь ни при чём."""
    корень = репозиторий_с_файлом(
        tmp_path, "checks/harness.py", 'ДАННЫЕ = {"publisher_id": "48217"}\n')
    код, _вывод, ошибки = прогнать("no_secrets.py", корень)
    assert код == 1, ошибки
    assert "publisher_id" in ошибки
    assert "48217" not in ошибки, "значение секрета попало в отчёт"


def test_очевидная_подстановка_проходит(tmp_path):
    """Подстановка обязана быть ВИДНА подстановкой — тогда она разрешена."""
    корень = репозиторий_с_файлом(
        tmp_path, "checks/harness.py", 'ДАННЫЕ = {"publisher_id": "00000"}\n')
    код, _вывод, ошибки = прогнать("no_secrets.py", корень)
    assert код == 0, ошибки


def test_приватный_ключ_в_индексе_находится(tmp_path):
    # Заголовок ключа собирается из частей нарочно: вписанный литералом, он
    # сам попадает под сторож секретов фабрики — и сторож прав, этот тест на
    # нём и споткнулся. Образец для проверки не обязан быть настоящим
    # заголовком в исходнике, ему достаточно стать им в подставном файле.
    заголовок = "-----BEGIN " + "RSA PRIVATE" + " KEY-----"
    корень = репозиторий_с_файлом(tmp_path, "docs/notes.md",
                                  f"{заголовок}\nAAAA\n")
    код, _вывод, ошибки = прогнать("no_secrets.py", корень)
    assert код == 1
    assert "приватный ключ" in ошибки


def test_запрещённое_имя_файла_находится(tmp_path):
    корень = репозиторий_с_файлом(tmp_path, "config/player.json", "{}\n")
    код, _вывод, ошибки = прогнать("no_secrets.py", корень)
    assert код == 1
    assert "не должны быть в Git" in ошибки


def test_чистый_репозиторий_проходит(tmp_path):
    корень = репозиторий_с_файлом(tmp_path, "src/frontend.py", "print(1)\n")
    код, _вывод, ошибки = прогнать("no_secrets.py", корень)
    assert код == 0, ошибки


def test_git_не_про_этот_проект_это_отказ(tmp_path):
    """Иначе распакованное дерево опросило бы объемлющий репозиторий."""
    корень = tmp_path / "без-гита"
    (корень / "checks").mkdir(parents=True)
    код, _вывод, ошибки = прогнать("no_secrets.py", корень)
    assert код == 1
    assert "не про этот проект" in ошибки


# --------------------------------------------------------------------------- #
#  entrypoint_present: зеркало не врёт.
# --------------------------------------------------------------------------- #
def ячейка_с_точкой(tmp_path: Path, *, объявлено: str, запускает: str | None,
                    в_пинах: bool = False) -> Path:
    """Витрина, у которой имя точки входа объявлено одним способом, а
    `run.py` запускает (или не запускает) названный файл."""
    корень = tmp_path / "ячейка"
    (корень / "checks").mkdir(parents=True, exist_ok=True)
    (корень / "config").mkdir(parents=True, exist_ok=True)
    (корень / "src").mkdir(parents=True, exist_ok=True)
    (корень / "src" / объявлено).write_text("print(1)\n", encoding="utf-8")
    конфиг = {"site_id": "проба-01"}
    if в_пинах:
        (корень / "pins.lock.json").write_text(
            json.dumps({"pins": {"entrypoint": объявлено}}), encoding="utf-8")
    else:
        конфиг["entrypoint"] = объявлено
    (корень / "config" / "site.json").write_text(
        json.dumps(конфиг, ensure_ascii=False), encoding="utf-8")
    пускатель = ('КОРЕНЬ = "."\n'
                 f'путь = КОРЕНЬ / "src" / "{запускает}"\n'
                 if запускает else "имя = конфиг['entrypoint']\n")
    (корень / "run.py").write_text(пускатель, encoding="utf-8")
    return корень


def test_зеркало_разошлось_это_отказ(tmp_path):
    """Пин никто не исполняет, поэтому разойтись он может только молча."""
    корень = ячейка_с_точкой(tmp_path, объявлено="frontend.py",
                             запускает="другой.py")
    код, _вывод, ошибки = прогнать("entrypoint_present.py", корень)
    assert код == 1, ошибки
    assert "зеркало разошлось" in ошибки


def test_зеркало_совпадает_это_проход(tmp_path):
    корень = ячейка_с_точкой(tmp_path, объявлено="frontend.py",
                             запускает="frontend.py")
    код, вывод, ошибки = прогнать("entrypoint_present.py", корень)
    assert код == 0, ошибки
    assert "зеркало совпадает" in вывод


def test_имя_из_конфигурации_пускателя_не_сверяется_вслух(tmp_path):
    """«Не проверялось» и «проверено» — разные утверждения."""
    корень = ячейка_с_точкой(tmp_path, объявлено="frontend.py", запускает=None)
    код, вывод, ошибки = прогнать("entrypoint_present.py", корень)
    assert код == 0, ошибки
    assert "зеркало не сверялось" in вывод


def test_имя_из_пинов_тоже_находится(tmp_path):
    """У animedia-space имя живёт в pins.lock.json, и ячейка исправна."""
    корень = ячейка_с_точкой(tmp_path, объявлено="frontend.py",
                             запускает="frontend.py", в_пинах=True)
    код, вывод, ошибки = прогнать("entrypoint_present.py", корень)
    assert код == 0, ошибки
    assert "pins.lock.json" in вывод


def test_пропавший_файл_точки_входа_это_отказ(tmp_path):
    корень = ячейка_с_точкой(tmp_path, объявлено="frontend.py",
                             запускает="frontend.py")
    (корень / "src" / "frontend.py").unlink()
    код, _вывод, ошибки = прогнать("entrypoint_present.py", корень)
    assert код == 1
    assert "нет точки входа" in ошибки


def test_имя_не_задано_нигде_это_отказ(tmp_path):
    корень = ячейка_с_точкой(tmp_path, объявлено="frontend.py",
                             запускает="frontend.py")
    (корень / "config" / "site.json").write_text(
        json.dumps({"site_id": "проба-01"}), encoding="utf-8")
    код, _вывод, ошибки = прогнать("entrypoint_present.py", корень)
    assert код == 1
    assert "не задают имя точки входа" in ошибки


@pytest.mark.parametrize("имя", ["fails_closed.py", "no_secrets.py",
                                 "entrypoint_present.py"])
def test_шаблон_существует_и_компилируется(имя):
    источник = (ШАБЛОНЫ / имя).read_text(encoding="utf-8")
    compile(источник, имя, "exec")
