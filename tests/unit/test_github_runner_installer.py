"""Установщик self-hosted runner отказывает там, где отказ обязателен.

Зачем проверка. Сценарий ставит машину сборок, и запускать его будет владелец
на чужой для нас машине — своими руками и один раз. Значит доказывать надо не
то, что он «написан», а то, что он ОТКАЗЫВАЕТ: на production-хосте сети, без
названного репозитория, без метки и без файла токена. Все эти отказы проверяются
без машины и без сети.

Сам путь установки (загрузка пакета, `config.sh`, `svc.sh`) здесь НЕ
исполняется: он требует машины и доступа к github.com, и притворяться, что он
проверен, нельзя. Первый настоящий запуск — на машине владельца.

Имя машины подменяется подставным `hostname` в PATH — тем же приёмом, которым
проверка режима записи моста подменяет исполнителя модели. Иначе первая застава
закрывает остальные и проверить их нечем.
"""
from __future__ import annotations

import os
import subprocess
from pathlib import Path

import pytest

КОРЕНЬ = Path(__file__).resolve().parents[2]
СЦЕНАРИЙ = КОРЕНЬ / "automation" / "host" / "install-github-runner.sh"
ЗАПРЕЩЁННЫЙ_ХОСТ = "claude-control-01"


@pytest.fixture()
def окружение(tmp_path):
    """PATH с подставным `hostname`, который называет НЕ production-хост."""
    корзина = tmp_path / "bin"
    корзина.mkdir()
    (корзина / "hostname").write_text("#!/bin/sh\necho build-box-1\n", encoding="utf-8")
    (корзина / "hostname").chmod(0o755)
    return {**os.environ, "PATH": f"{корзина}:{os.environ['PATH']}"}


def запустить(окр, *аргументы) -> subprocess.CompletedProcess:
    return subprocess.run(["bash", str(СЦЕНАРИЙ), *аргументы], env=окр,
                          capture_output=True, text=True, timeout=120)


def test_сценарий_на_месте_и_синтаксически_цел():
    assert СЦЕНАРИЙ.is_file(), СЦЕНАРИЙ
    r = subprocess.run(["bash", "-n", str(СЦЕНАРИЙ)], capture_output=True, text=True)
    assert r.returncode == 0, r.stderr


def test_на_production_хосте_отказ_по_имени_машины():
    """Главная застава: этот хост под сборки не отдаётся решением владельца.

    Проверяется БЕЗ подмены PATH — на настоящем имени машины. Если проверка
    идёт не на `claude-control-01`, она пропускается с названной причиной:
    выдавать «не на том хосте» за доказательство нельзя.
    """
    текущий = subprocess.run(["hostname"], capture_output=True, text=True).stdout.strip()
    if текущий != ЗАПРЕЩЁННЫЙ_ХОСТ:
        pytest.skip(f"проверка идёт на {текущий!r}, а застава — про "
                    f"{ЗАПРЕЩЁННЫЙ_ХОСТ!r}")
    r = запустить(os.environ, "--repo", "o/n", "--labels", "L",
                  "--token-file", "/dev/null")
    assert r.returncode == 2
    assert ЗАПРЕЩЁННЫЙ_ХОСТ in (r.stdout + r.stderr)


@pytest.mark.parametrize(("имя", "аргументы", "ждём"), [
    ("без репозитория", ("--labels", "L", "--token-file", "/dev/null"), "нужен --repo"),
    ("без метки", ("--repo", "o/n", "--token-file", "/dev/null"), "нужен --labels"),
    ("без файла токена", ("--repo", "o/n", "--labels", "L"), "нужен --token-file"),
    ("репозиторий не owner/name",
     ("--repo", "badform", "--labels", "L", "--token-file", "/dev/null"), "owner/name"),
])
def test_входы_которые_нельзя_угадывать(окружение, имя, аргументы, ждём):
    r = запустить(окружение, *аргументы)
    вывод = r.stdout + r.stderr
    assert r.returncode == 2, вывод
    assert ждём in вывод, вывод


def test_широкие_права_файла_токена_отвергаются(окружение, tmp_path):
    """Токен регистрации подключает машину к репозиторию — права проверяются."""
    токен = tmp_path / "token"
    токен.write_text("не настоящий токен\n", encoding="utf-8")
    токен.chmod(0o644)
    r = запустить(окружение, "--repo", "o/n", "--labels", "L",
                  "--token-file", str(токен))
    вывод = r.stdout + r.stderr
    assert r.returncode == 2, вывод
    assert "шире, чем 600" in вывод, вывод


def test_сценарий_не_обходит_обязательный_CI():
    """Он ставит машину, а не подменяет проверки происхождения выпуска.

    Сторожится отсутствием: сценарий не должен ни трогать проверки исполнителя,
    ни писать статусы прогонов, ни отключать workflow.
    """
    текст = СЦЕНАРИЙ.read_text(encoding="utf-8")
    for запрещено in ("gh api", "check-run", "statuses", "workflow disable",
                      "ci_run", "--force"):
        assert запрещено not in текст, (
            f"сценарий трогает {запрещено!r}: его дело — машина, а не статусы")


def test_метки_не_меняются_этим_сценарием():
    """Переключение `runs-on` — отдельный шаг ПОСЛЕ зелёного пробного задания.

    Если сценарий начнёт править workflow сам, метка сменится раньше рабочего
    runner'а, и задания встанут в очередь, которую никто не обслуживает: выпуск
    замрёт молча. Поэтому правок workflow в нём нет, а порядок записан в
    подсказке.
    """
    текст = СЦЕНАРИЙ.read_text(encoding="utf-8")
    assert "runs-on: ubuntu-latest" in текст, "порядок переключения не назван"
    assert "release.yml" in текст
    for запрещено in ("sed -i", "yq ", "git commit", "git push"):
        assert запрещено not in текст, f"сценарий сам правит файлы: {запрещено!r}"


# --- ограниченный режим -----------------------------------------------------
#
# Отдельной машины владелец не дал, а выпуск без зелёного CI не принимается.
# Поэтому есть один осознанный способ поставить runner на тот же хост, что
# витрины: в своём cgroup с пределами. Здесь сторожится, что это именно
# ограничение, а не обход заставы: без флага отказ остаётся, предел ставится до
# первого запуска, память витринам резервируется, а своп заданию недоступен.


@pytest.fixture()
def хост_сети(tmp_path):
    """PATH с подставным `hostname`, называющим production-хост сети."""
    корзина = tmp_path / "bin-prod"
    корзина.mkdir()
    (корзина / "hostname").write_text(
        f"#!/bin/sh\necho {ЗАПРЕЩЁННЫЙ_ХОСТ}\n", encoding="utf-8")
    (корзина / "hostname").chmod(0o755)
    return {**os.environ, "PATH": f"{корзина}:{os.environ['PATH']}"}


def test_без_флага_отказ_остаётся_и_называет_способ(хост_сети):
    r = запустить(хост_сети, "--repo", "o/n", "--labels", "L",
                  "--token-file", "/dev/null")
    вывод = r.stdout + r.stderr
    assert r.returncode == 2, вывод
    assert "--confined" in вывод, "отказ обязан называть разрешённый способ"


def test_флаг_снимает_только_заставу_имени_машины(хост_сети):
    """Дальше идут обычные проверки входов — флаг их не отменяет."""
    r = запустить(хост_сети, "--repo", "o/n", "--labels", "L",
                  "--token-file", "/nonexistent", "--confined")
    вывод = r.stdout + r.stderr
    assert r.returncode == 2, вывод
    assert "ограниченный режим" in вывод
    assert "файла токена нет" in вывод, "проверки входов остались на месте"


def test_резерв_памяти_витрин_требуется_явно():
    текст = СЦЕНАРИЙ.read_text(encoding="utf-8")
    assert "RESERVE_MIB=2048" in текст, (
        "резерв равен порогу редактора: прогон не имеет права его занять")
    assert "NEED_MIB=$((RESERVE_MIB + 1200))" in текст


def test_предел_ставится_до_первого_запуска():
    """Иначе первое же задание пойдёт без предела — и заберёт память витрин."""
    текст = СЦЕНАРИЙ.read_text(encoding="utf-8")
    пределы = текст.index("10-confined.conf")
    запуск = текст.index("./svc.sh start")
    assert пределы < запуск, "drop-in обязан быть записан раньше svc.sh start"


@pytest.mark.parametrize("строка", [
    "MemoryMax=$CONFINED_MEM_MAX",
    "MemorySwapMax=0",
    "CPUQuota=$CONFINED_CPU",
    "Nice=19",
    "ProtectSystem=strict",
])
def test_состав_предела(строка):
    текст = СЦЕНАРИЙ.read_text(encoding="utf-8")
    assert строка in текст, f"в пределе нет {строка!r}"


def test_предел_проверяется_а_не_предполагается():
    """Сценарий обязан сказать, чем проверить поставленный предел."""
    текст = СЦЕНАРИЙ.read_text(encoding="utf-8")
    assert "systemctl show" in текст and "MemoryMax" in текст
    assert "ожидается MemoryMax" in текст


def test_ограниченный_режим_описан_в_документе():
    текст = (КОРЕНЬ / "docs" / "SELF_HOSTED_RUNNER.md").read_text(encoding="utf-8")
    assert "--confined" in текст, "вариант без документа владельцу бесполезен"
    assert "MemoryMax" in текст
