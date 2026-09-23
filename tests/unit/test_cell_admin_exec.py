"""Исполнитель принимает сайт и коммит — и отказывает всему остальному.

Смысл проверок: граница проходит по программе, а не по оболочке. Если бы
владелец разрешил «выполнять такой-то скрипт от root», границей стал бы путь на
диске — а писать по этому пути может кто угодно с доступом к рабочему каталогу.

Поэтому каждый отказ ниже проверяется запуском, а не чтением кода, и каждый
обязан наступить ДО сборки и ДО единой мутации.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

КОРЕНЬ = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(КОРЕНЬ))

from factory.cell import admin_exec  # noqa: E402

ЗАРЕГИСТРИРОВАННЫЙ = "zona-01"
КОММИТ_ВИДА = "0123456789abcdef0123456789abcdef01234567"


def _git(repo: Path, *args: str) -> str:
    return subprocess.run(["git", "-C", str(repo), *args], check=True,
                          capture_output=True, text=True).stdout.strip()


@pytest.fixture()
def репозиторий_сайта() -> Path:
    путь = КОРЕНЬ / "var" / "site-repos" / "zonafilm-space"
    if not (путь / ".git").is_dir():
        pytest.skip("репозитория выделенного сайта нет в этом рабочем каталоге")
    return путь


@pytest.mark.parametrize("значение", [
    "",                       # пусто
    "HEAD",                   # ссылка, а не хеш
    "main",                   # ветка
    "fc08252d22c0; rm -rf /",  # попытка дописать команду
    "../../etc/passwd",       # путь
    "z" * 40,                 # не шестнадцатеричное
    "abc",                    # слишком коротко
])
def test_коммит_только_по_форме(значение):
    """Форма проверяется до всего остального: спорить с оболочкой не нужно."""
    with pytest.raises(admin_exec.ExecutorRefused) as ош:
        admin_exec._проверить_коммит(значение)
    assert "git-хеш" in str(ош.value)


def test_коммит_нормальной_формы_принимается():
    assert admin_exec._проверить_коммит("  FC08252D22C0  ") == "fc08252d22c0"


def test_незарегистрированный_сайт_отклонён():
    with pytest.raises(admin_exec.ExecutorRefused) as ош:
        admin_exec.план("нет-такого-сайта", commit=КОММИТ_ВИДА)
    assert "реестре" in str(ош.value)


def test_чужой_коммит_отклонён(репозиторий_сайта):
    """Исполнитель не переключает ветки: он работает с тем, что уже выбрано."""
    with pytest.raises(admin_exec.ExecutorRefused) as ош:
        admin_exec.план(ЗАРЕГИСТРИРОВАННЫЙ, commit=КОММИТ_ВИДА)
    assert "нет" in str(ош.value) or "HEAD" in str(ош.value)


def test_план_на_настоящем_репозитории_ничего_не_меняет(репозиторий_сайта):
    до = _git(репозиторий_сайта, "status", "--porcelain")
    head = _git(репозиторий_сайта, "rev-parse", "HEAD")

    решение = admin_exec.план(ЗАРЕГИСТРИРОВАННЫЙ, commit=head)

    assert решение.commit == head
    assert решение.digest.startswith("sha256:")
    # build_id обязан называть именно этот коммит и именно этот сайт —
    # иначе публичный идентификатор не отвечает на вопрос «что сейчас работает».
    assert решение.build_id == f"{head[:12]}-{ЗАРЕГИСТРИРОВАННЫЙ}"
    assert решение.dry_run is True
    assert _git(репозиторий_сайта, "status", "--porcelain") == до
    assert _git(репозиторий_сайта, "rev-parse", "HEAD") == head


def test_несовпадение_digest_отменяет_активацию(репозиторий_сайта):
    """Выкладывается тот выпуск, который проверил CI, или никакой."""
    head = _git(репозиторий_сайта, "rev-parse", "HEAD")
    with pytest.raises(admin_exec.ExecutorRefused) as ош:
        admin_exec.активировать(ЗАРЕГИСТРИРОВАННЫЙ, commit=head, dry_run=False,
                                expect_digest="sha256:" + "0" * 64)
    assert "CI" in str(ош.value)


def test_по_умолчанию_сухой_прогон(репозиторий_сайта):
    """Команда, по умолчанию меняющая боевой сайт, однажды сработает случайно."""
    head = _git(репозиторий_сайта, "rev-parse", "HEAD")
    итог = admin_exec.активировать(ЗАРЕГИСТРИРОВАННЫЙ, commit=head)
    assert итог["status"] == "dry-run"


def test_cli_не_принимает_пути(репозиторий_сайта):
    """У команды нет параметра «какой скрипт запустить» — это и есть граница."""
    готово = subprocess.run(
        [sys.executable, "-m", "factory", "cell", "activate",
         "--site", ЗАРЕГИСТРИРОВАННЫЙ, "--commit", _git(репозиторий_сайта, "rev-parse", "HEAD"),
         "--artifact", "/tmp/чужое.tar.gz", "--dry-run"],
        cwd=str(КОРЕНЬ), capture_output=True, text=True)
    # --artifact у команды cell есть (его использует install), но activate его
    # игнорирует: артефакт собирается из коммита и больше ниоткуда.
    assert готово.returncode == 0, готово.stderr
    итог = json.loads(готово.stdout)
    assert итог["status"] == "dry-run"
    assert "чужое.tar.gz" not in json.dumps(итог, ensure_ascii=False)


def test_команда_без_подтверждения_не_активирует(репозиторий_сайта):
    """Забытый флаг не должен переключать боевую витрину.

    Первая версия команды делала сухой прогон только по `--dry-run`: модуль был
    безопасен по умолчанию, а команда — нет, и расхождение заметно ровно один
    раз.
    """
    head = _git(репозиторий_сайта, "rev-parse", "HEAD")
    готово = subprocess.run(
        [sys.executable, "-m", "factory", "cell", "activate",
         "--site", ЗАРЕГИСТРИРОВАННЫЙ, "--commit", head],
        cwd=str(КОРЕНЬ), capture_output=True, text=True)
    assert готово.returncode == 0, готово.stderr
    assert json.loads(готово.stdout)["status"] == "dry-run"
