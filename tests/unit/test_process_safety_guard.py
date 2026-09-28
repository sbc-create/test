"""REQ-PROCESS-SAFETY: тестовые сценарии не убивают процессы по шаблону.

Инцидент 004: команда `pkill -f "site_engine.api.server"` из тестового
сценария совпала с боевым процессом и остановила `site-factory-control-api`
примерно на две минуты. Имя модуля у тестового и боевого процессов одно;
отличались рабочий каталог и порт, и ни то ни другое в шаблон не входило.

После инцидента появился безопасный запуск `with_test_server.sh`, но два
сценария остались со старым способом уборки. Правило, записанное в одном месте
и не проверяемое, держится ровно до следующего похожего сценария.

Проверка читает сами файлы. Запрещены `pkill`, `killall`, `kill` по результату
`pgrep`/`pidof` и остановка systemd-юнита ради уборки за тестом. Разрешено
одно: сигнал конкретному сохранённому PID собственного дочернего процесса.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
КАТАЛОГИ = ("tests", "scripts")

#: Третье поле — где правило применяется. Запрет широкого убийства действует
#: везде; запрет остановки systemd-юнита — только в тестовых сценариях: в
#: сценариях выкладки перезапуск службы и есть работа, а проверки, читающие
#: их текст, упоминают команду, а не выполняют её.
#: Команда узнаётся по месту, а не по слову. Начало строки, `;`, `&&`, `|`,
#: `$(`, `then`, `do`, `else` — места, где стоит команда; всё остальное — текст.
#: Без этого условия сторож ловил собственное описание инцидента: имя файла
#: `004-control-api-stopped-by-broad-pkill.md` содержит запрещённое слово и не
#: является командой. Сторож, ловящий разговор о правиле, заставляет обходить
#: себя переименованием — и перестаёт ловить нарушение.
НАЧАЛО = r"(?:^|[;&|(]|\$\(|\bthen\b|\bdo\b|\belse\b)\s*(?:sudo\s+(?:-n\s+)?)?"

ЗАПРЕЩЕНО: tuple[tuple[str, str], ...] = (
    (НАЧАЛО + r"pkill\b", "pkill убивает по шаблону имени и попадает в чужой процесс"),
    (НАЧАЛО + r"killall\b", "killall убивает по имени программы, а не по конкретному процессу"),
    (НАЧАЛО + r"kill\s+-9", "kill -9 не даёт процессу закрыть файлы и снять блокировки"),
    (
        НАЧАЛО + r"kill[^|\n]*\$\(\s*(pgrep|pidof)",
        "PID из pgrep/pidof — это чужой процесс так же часто, как свой",
    ),
)

ТОЛЬКО_ТЕСТОВЫЕ_СЦЕНАРИИ: tuple[tuple[str, str], ...] = (
    (
        r"systemctl\s+(stop|restart|kill)\b",
        "остановка юнита ради уборки за тестом задевает боевую службу",
    ),
)


def _файлы() -> list[Path]:
    файлы: list[Path] = []
    for каталог in КАТАЛОГИ:
        основа = ROOT / каталог
        if not основа.exists():
            continue
        for путь in основа.rglob("*"):
            if путь.is_file() and путь.suffix in {".sh", ".bash", ".py", ".js"}:
                файлы.append(путь)
    return файлы


def _значимые_строки(текст: str) -> list[tuple[int, str]]:
    """Комментарии не исполняются: объяснение запрета — не нарушение запрета."""
    строки = []
    for номер, строка in enumerate(текст.splitlines(), 1):
        без_отступа = строка.strip()
        if без_отступа.startswith("#") or без_отступа.startswith("//"):
            continue
        # Хвостовой комментарий отрезается только у shell-подобных строк.
        строки.append((номер, строка.split(" #", 1)[0]))
    return строки


def test_в_проверяемых_каталогах_есть_что_проверять():
    assert len(_файлы()) > 20


def _нарушения(шаблон: str, файлы) -> list[str]:
    правило = re.compile(шаблон)
    найдено = []
    for путь in файлы:
        if путь.name == "test_process_safety_guard.py":
            continue
        try:
            текст = путь.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        for номер, строка in _значимые_строки(текст):
            if правило.search(строка):
                найдено.append(f"{путь.relative_to(ROOT)}:{номер}: {строка.strip()}")
    return найдено


@pytest.mark.parametrize("шаблон,причина", ТОЛЬКО_ТЕСТОВЫЕ_СЦЕНАРИИ)
def test_тесты_не_трогают_systemd_юниты(шаблон: str, причина: str):
    сценарии = [п for п in _файлы() if п.suffix in {".sh", ".bash"} and "tests" in п.parts]
    нарушения = _нарушения(шаблон, сценарии)
    assert not нарушения, причина + "\n" + "\n".join(нарушения)


@pytest.mark.parametrize("шаблон,причина", ЗАПРЕЩЕНО)
def test_широких_убийств_нет(шаблон: str, причина: str):
    правило = re.compile(шаблон)
    нарушения = []
    for путь in _файлы():
        if путь.name == "test_process_safety_guard.py":
            continue
        try:
            текст = путь.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        for номер, строка in _значимые_строки(текст):
            if правило.search(строка):
                нарушения.append(f"{путь.relative_to(ROOT)}:{номер}: {строка.strip()}")
    assert not нарушения, причина + "\n" + "\n".join(нарушения)


def test_безопасный_запуск_на_месте():
    """Замена запрещённому способу должна существовать, а не подразумеваться."""
    сценарий = ROOT / "tests" / "tools" / "with_test_server.sh"
    assert сценарий.exists()
    текст = сценарий.read_text(encoding="utf-8")
    assert "trap cleanup" in текст, "уборка обязана срабатывать и при провале"
    assert "/proc/${SERVER_PID}/cmdline" in текст, "перед остановкой сверяется тот ли процесс"
    assert "kill -TERM" in текст


def test_сценарии_движков_пользуются_безопасным_запуском():
    """Каждый сценарий, поднимающий сервер, обязан делать это одним способом."""
    поднимают = []
    for путь in (ROOT / "tests" / "tools").glob("*.sh"):
        текст = путь.read_text(encoding="utf-8")
        if путь.name == "with_test_server.sh":
            continue
        if "factory.site_engine.api.server" in текст or "with_test_server" in текст:
            поднимают.append((путь, текст))
    assert поднимают, "сценарии движков должны существовать"
    for путь, текст in поднимают:
        assert "with_test_server.sh" in текст, f"{путь.name}: сервер поднимается в обход общего"


@pytest.mark.parametrize(
    "строка,ловится",
    [
        ('pkill -f "site_engine.api.server"', True),
        ('  pkill -f something', True),
        ('foo || pkill -f bar', True),
        ('$(pkill -f bar)', True),
        ('kill -9 12345', True),
        ('killall python', True),
        ('kill $(pgrep -f server)', True),
        ('"004-control-api-stopped-by-broad-pkill.md"', False),
        ('# запрещено: pkill, killall', False),
        ('assert "pkill" in заголовок', False),
        ('kill -TERM "$SERVER_PID"', False),
    ],
)
def test_сторож_различает_команду_и_упоминание(строка: str, ловится: bool):
    """Проверка самого сторожа: правило без этой проверки тихо слепнет.

    Ослабление шаблона ради собственного текста — самый естественный способ
    отключить сторож, не заметив этого.
    """
    попал = any(re.search(шаблон, строка) for шаблон, _ in ЗАПРЕЩЕНО)
    assert попал is ловится, строка

