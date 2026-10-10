"""Установщик читающего API ставит службу, которая переживёт эту сессию.

Повод. Юнит собирался из пути, откуда запущен установщик, то есть из рабочего
дерева сессии (`/home/claude/wt-…`). Дерево — временное: `git worktree remove`
его снимает, и служба осталась бы с `ExecStart` в несуществующий файл, а в
`ReadOnlyPaths` — с несуществующим каталогом. Поймано при подготовке команды
владельцу: ставить службу, живущую в моём дереве, нельзя.

Поэтому код службы и её контракт копируются в `/usr/local/lib/site-factory` —
туда же, где на хосте уже лежат другие хостовые сценарии фабрики, — и юнит
указывает на копию. Откат эту копию убирает.

Сам путь установки здесь НЕ исполняется: он требует root, nginx и systemd.
Проверяются сухой прогон и состав юнита; «проверено» о непройденном не
говорится.
"""
from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

КОРЕНЬ = Path(__file__).resolve().parents[2]
СЦЕНАРИЙ = КОРЕНЬ / "automation" / "host" / "install-app-read-api.sh"
СТАБИЛЬНЫЙ = "/usr/local/lib/site-factory"


@pytest.fixture(scope="module")
def сухой() -> str:
    р = subprocess.run(["bash", str(СЦЕНАРИЙ), "--dry-run"],
                       capture_output=True, text=True, timeout=300)
    assert р.returncode == 0, р.stdout + р.stderr
    return р.stdout + р.stderr


def test_синтаксис():
    р = subprocess.run(["bash", "-n", str(СЦЕНАРИЙ)], capture_output=True, text=True)
    assert р.returncode == 0, р.stderr


def test_код_службы_копируется_в_стабильное_место(сухой):
    assert f"{СТАБИЛЬНЫЙ}/app-read-api-animedia-01.py" in сухой


@pytest.mark.parametrize("строка", [
    f"ExecStart=/usr/bin/python3 {СТАБИЛЬНЫЙ}/app-read-api-animedia-01.py",
    f"WorkingDirectory={СТАБИЛЬНЫЙ}",
    f"ReadOnlyPaths=/srv/animedia-icu/data {СТАБИЛЬНЫЙ}",
])
def test_юнит_не_смотрит_в_рабочее_дерево(сухой, строка):
    assert строка in сухой, строка


def test_в_юните_нет_пути_сессии(сухой):
    """Главное утверждение: ни одной ссылки на дерево сессии внутри юнита."""
    юнит = сухой.split("записать /etc/systemd/system/", 1)[1]
    юнит = юнит.split("systemctl daemon-reload", 1)[0]
    assert "/home/claude/wt-" not in юнит, (
        "юнит зависит от рабочего дерева сессии: оно будет снято")


def test_служба_ничего_не_пишет(сухой):
    assert "ProtectSystem=strict" in сухой
    assert "ReadWritePaths=" not in сухой, "запись разрешать нечему: API читающее"


def test_предел_памяти_назван(сухой):
    assert "MemoryMax=512M" in сухой, (
        "без предела утечка в службе добирала бы память у витрин и редактора")


def test_маршрут_только_на_чтение(сухой):
    assert "limit_except GET HEAD { deny all; }" in сухой
    assert 'add_header X-Robots-Tag "noindex, nofollow" always;' in сухой


def test_копия_конфигурации_сайта_снимается_до_правки(сухой):
    assert ".before-app-read-api-animedia-01." in сухой
    assert "nginx -t" in сухой


def test_откат_убирает_и_копию_кода():
    текст = СЦЕНАРИЙ.read_text(encoding="utf-8")
    откат = текст.split('if [ "$rollback" = 1 ]', 1)[1].split("exit 0", 1)[0]
    assert "$INSTALLED_SCRIPT" in откат, "копия кода осталась бы после откат�"
    assert "$UNIT_PATH" in откат and "$SNIPPET" in откат


def test_ключ_показывается_один_раз_и_только_при_создании():
    """Ключ владелец обязан получить — но ровно один раз и только в терминале.

    Значение печатается ТОЛЬКО в ветке создания файла: повторный запуск
    установщика его не покажет, а в подсказках и примерах стоит
    местозаполнитель. В отчёты, журналы и передачи ключ не попадает — там он
    назван словом «ключ», а не значением.
    """
    текст = СЦЕНАРИЙ.read_text(encoding="utf-8")
    показ = текст.index('ЗНАЧЕНИЕ КЛЮЧА')
    создание = текст.index("secrets.token_urlsafe")
    конец_ветки = текст.index("if [ \"$dry_run\" = 0 ]", создание)
    assert создание < показ < конец_ветки, (
        "значение печатается вне ветки создания ключа: повторный запуск "
        "показал бы его снова")
    assert "показывается один раз" in текст
    assert "<значение>" in текст, "в подсказке местозаполнитель, а не ключ"
    assert "logger" not in текст and "tee" not in текст, "ключ не идёт в журнал"


def test_сухой_прогон_ключ_не_печатает(сухой):
    assert "ЗНАЧЕНИЕ КЛЮЧА" not in сухой
