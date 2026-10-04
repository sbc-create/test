"""От root не исполняется ничего, пришедшего из репозитория сайта.

Дефект, который это закрывает: исполнитель запускал `deploy/activate.sh` и
`tools/build_release.py` из репозитория сайта. Репозиторий доступен на запись
обычной учётной записи, исполнитель работает от root — право писать в
репозиторий превращалось в право выполнить что угодно от root. Проверки
коммита, чистого дерева и CI этого не закрывают: CI описан тем же
репозиторием, и кто владеет репозиторием, тот владеет и проверкой.

Проверяется ЦЕПОЧКА целиком, а не один файл: заявка → исполнитель →
привилегированные операции → установщик и юнит. Тест обязан упасть, если
прежний путь вернётся хоть в одном звене.
"""
from __future__ import annotations

import ast
import re
import sys
from pathlib import Path

import pytest

КОРЕНЬ = Path(__file__).resolve().parents[2]
#: Каталоги, которым юнит ВПРАВЕ разрешить запись. Это другое направление, чем
#: вход: root пишет туда реестр и его копию, а не берёт оттуда код. Перечень
#: закрытый — грант не должен тихо расшириться на всё рабочее дерево.
РАЗРЕШЁННАЯ_ЗАПИСЬ = {
    "/home/claude/wt-portable-site-cell-01/config",
    "/usr/local/lib/site-factory-cell/config",
}


def _входные_пути(юнит: str) -> list[str]:
    """Пути, откуда юнит БЕРЁТ код, рабочий каталог и конфигурацию."""
    import re as _re

    return _re.findall(
        r"^(?:ExecStart|ExecStartPre|WorkingDirectory|Environment=PYTHONPATH|"
        r"Environment=SITE_CELLS_REGISTRY)=(\S+)", юнит, _re.M)


sys.path.insert(0, str(КОРЕНЬ))

#: Звенья цепочки, которые исполняются от root после установки.
ПРИВИЛЕГИРОВАННЫЕ = ("factory/cell/executor.py", "factory/cell/privileged.py",
                     "factory/cell/queue.py", "factory/cell/runtime.py")

#: Что репозиторий сайта может предложить к исполнению.
ФАЙЛЫ_РЕПОЗИТОРИЯ = ("activate.sh", "rollback.sh", "update.sh", "checks/run.sh")


def _вызовы(путь: Path) -> str:
    """Дамп всех вызовов запуска процессов. Документация сюда не попадает."""
    дерево = ast.parse(путь.read_text(encoding="utf-8"))
    интересные = []
    for узел in ast.walk(дерево):
        if isinstance(узел, ast.Call):
            имя = ""
            if isinstance(узел.func, ast.Attribute):
                имя = узел.func.attr
            elif isinstance(узел.func, ast.Name):
                имя = узел.func.id
            if имя in {"run", "Popen", "call", "check_call", "check_output",
                       "system", "execv", "execve", "spawnv"}:
                интересные.append(ast.dump(узел))
    return "\n".join(интересные)


@pytest.mark.parametrize("модуль", ПРИВИЛЕГИРОВАННЫЕ)
def test_привилегированное_звено_не_запускает_файлы_репозитория(модуль):
    путь = КОРЕНЬ / модуль
    # Отсутствие звена — не «нечего проверять». Под прежним skip удалить или
    # переименовать привилегированный модуль было дешевле, чем удержать его в
    # рамках: сторож зеленел ровно тогда, когда сторожить становилось нечего.
    assert путь.is_file(), (
        f"{модуль} отсутствует: привилегированная цепочка описана этим списком, "
        "и выпавшее из него звено никто не проверяет")
    вызовы = _вызовы(путь)
    for имя in ФАЙЛЫ_РЕПОЗИТОРИЯ:
        assert имя not in вызовы, f"{модуль} запускает {имя} из репозитория"
    assert "shell=True" not in путь.read_text(encoding="utf-8"), (
        f"{модуль}: shell=True превращает любую строку в команду")


def test_исполнитель_не_импортирует_admin_exec():
    """`admin_exec` — ручной инструмент владельца, он запускает сценарий репы.

    Импорт в исполнителе означал бы возврат прежнего пути даже без прямого
    вызова: достаточно одной строки, чтобы он снова оказался в цепочке.
    """
    текст = (КОРЕНЬ / "factory" / "cell" / "executor.py").read_text(encoding="utf-8")
    assert "admin_exec" not in текст


def test_сборка_идёт_под_учётной_записью_сайта():
    """Сборщик — код репозитория; от root он не запускается."""
    from factory.cell import privileged

    исходник = (КОРЕНЬ / "factory" / "cell" / "privileged.py").read_text(encoding="utf-8")
    # Привилегии сбрасываются: setuid/setgid обязаны присутствовать рядом с
    # запуском сборщика, иначе «под учётной записью» — только на словах.
    assert "os.setuid" in исходник and "os.setgid" in исходник
    assert "preexec_fn" in исходник
    assert hasattr(privileged, "собрать_без_прав")


def test_юнит_собирается_из_шаблона_исполнителя_а_не_из_репозитория():
    """Юнит из строк репозитория задавал бы ExecStart и User от root."""
    from factory.cell import privileged

    шаблон = privileged.ЮНИТ_ШАБЛОН
    assert "ExecStart=/usr/bin/python3 {link}/run.py" in шаблон
    assert "User={account}" in шаблон
    # В шаблоне нет ни одного места, куда репозиторий мог бы подставить строку:
    # все поля заполняются из реестра.
    поля = set(re.findall(r"\{(\w+)\}", шаблон))
    assert поля <= {"domain", "site_id", "account", "link", "data", "port"}


def test_установщик_кладёт_корневую_копию_а_не_ссылается_на_рабочий_каталог():
    """Юнит, исполняющий код из каталога с правом записи у обычной учётной
    записи, означает, что писать туда — то же, что выполнять команды от root."""
    юнит = (КОРЕНЬ / "automation" / "host" / "site-cell-executor.service"
            ).read_text(encoding="utf-8")
    assert "WorkingDirectory=/usr/local/lib/site-factory-cell" in юнит
    assert "PYTHONPATH=/usr/local/lib/site-factory-cell" in юнит
    # Запрещён ВХОД из рабочего каталога, а не всякое его упоминание.
    #
    # Разница существенная и измерена 2026-10-04: доставка разрешения
    # владельца требует, чтобы служба МОГЛА ПИСАТЬ в `config/` рабочего дерева
    # (`ReadWritePaths`), иначе команда владельца отказывает словами
    # «Read-only file system». Это обратное направление: root пишет туда
    # реестр, а не берёт оттуда код. Сторож проверяет именно вход и отдельно —
    # что грант на запись не расширился дальше двух названных каталогов.
    вход = _входные_пути(юнит)
    assert вход, "в юните не нашлось ни одного входного пути"
    for п in вход:
        assert not п.startswith("/home/"), (
            f"юнит берёт вход {п} из домашнего каталога")
    import re as _re
    запись = set(_re.findall(r"^ReadWritePaths=(\S+)", юнит, _re.M))
    лишнее = запись - РАЗРЕШЁННАЯ_ЗАПИСЬ
    assert not лишнее, f"юнит разрешил запись лишним каталогам: {sorted(лишнее)}"

    установщик = (КОРЕНЬ / "automation" / "host" / "install-cell-executor.sh"
                  ).read_text(encoding="utf-8")
    assert "chown -R root:root" in установщик
    assert "chmod -R go-w" in установщик


def test_обновление_исполнителя_требует_переустановки():
    """Правка рабочего каталога не должна менять то, что исполняется от root.

    Иначе корневая копия была бы украшением: достаточно записать в рабочий
    каталог, и следующий прогон исполнителя подхватит чужой код.
    """
    юнит = (КОРЕНЬ / "automation" / "host" / "site-cell-executor.service"
            ).read_text(encoding="utf-8")
    пути = re.findall(r"^(?:ExecStart|WorkingDirectory|Environment=PYTHONPATH)=(\S+)",
                      юнит, re.M)
    assert пути, "в юните не нашлось ни одного пути"
    for п in пути:
        assert not п.startswith("/home/"), f"юнит берёт {п} из домашнего каталога"
        assert not п.startswith("/srv/site-factory/repo"), (
            f"юнит берёт {п} из рабочего каталога фабрики")
