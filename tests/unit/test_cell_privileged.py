"""Граница привилегий исполнителя: что он может и чего не может от root.

Исходный дефект: исполнитель запускал `deploy/activate.sh` из репозитория сайта.
Репозиторий доступен на запись обычной учётной записи, исполнитель работает от
root — право писать в репозиторий превращалось в право выполнить что угодно от
root. Проверки коммита, чистого дерева и CI этого не закрывают: CI описан тем же
репозиторием.

Здесь проверяется, что привилегированная сторона не исполняет ничего пришедшего
из репозитория и не принимает путей, и что распаковка артефакта не может
записать за пределы каталога назначения.
"""
from __future__ import annotations

import io
import sys
import tarfile
from pathlib import Path

import pytest

КОРЕНЬ = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(КОРЕНЬ))

from factory.cell import privileged  # noqa: E402


def _архив(путь: Path, члены: list[tarfile.TarInfo],
           содержимое: dict[str, bytes] | None = None) -> Path:
    содержимое = содержимое or {}
    with tarfile.open(путь, "w:gz") as tf:
        for ч in члены:
            данные = содержимое.get(ч.name, b"")
            ч.size = len(данные)
            tf.addfile(ч, io.BytesIO(данные))
    return путь


def test_набор_операций_закрыт():
    """«Выполнить команду» отсутствует как понятие, а не запрещено проверкой."""
    assert set(privileged.ОПЕРАЦИИ) == {
        "prepare", "install_release", "warm_up", "switch_route",
        "promote", "verify", "rollback"}
    описание = privileged.описать_границу()
    assert описание["runs_repository_scripts"] is False
    assert описание["accepts_paths_from_request"] is False


def test_модуль_не_запускает_ничего_из_репозитория():
    """Проверка по исходнику: ни одного вызова сценария сайта."""
    import ast
    дерево = ast.parse((КОРЕНЬ / "factory" / "cell" / "privileged.py")
                       .read_text(encoding="utf-8"))
    # Смотрим на КОД, а не на текст: в документации имя сценария упомянуто
    # намеренно — там объясняется, почему его больше не запускают.
    строки = [у.value for у in ast.walk(дерево)
              if isinstance(у, ast.Constant) and isinstance(у.value, str)
              and not isinstance(getattr(у, "parent", None), ast.Expr)]
    вызовы = [у for у in ast.walk(дерево)
              if isinstance(у, ast.Call) and isinstance(у.func, ast.Attribute)
              and у.func.attr in {"run", "Popen", "call", "check_output", "system"}]
    аргументы = " ".join(ast.dump(в) for в in вызовы)
    for запрещённое in ("activate.sh", "rollback.sh", "shell=True"):
        assert запрещённое not in аргументы, (
            f"привилегированный код вызывает {запрещённое!r}")


def test_выход_за_каталог_отвергается(tmp_path):
    """Один такой член превращает распаковку в запись куда угодно от root."""
    архив = _архив(tmp_path / "evil.tar.gz",
                   [tarfile.TarInfo("../../etc/passwd")],
                   {"../../etc/passwd": b"root:x:0:0"})
    with tarfile.open(архив) as tf, pytest.raises(privileged.PrivilegedRefused) as ош:
        list(privileged.безопасные_члены(tf, tmp_path / "dest"))
    assert "за пределами" in str(ош.value)


def test_абсолютный_путь_отвергается(tmp_path):
    архив = _архив(tmp_path / "abs.tar.gz", [tarfile.TarInfo("/etc/shadow")])
    with tarfile.open(архив) as tf, pytest.raises(privileged.PrivilegedRefused):
        list(privileged.безопасные_члены(tf, tmp_path / "dest"))


def test_ссылка_наружу_отвергается(tmp_path):
    ссылка = tarfile.TarInfo("config/player.json")
    ссылка.type = tarfile.SYMTYPE
    ссылка.linkname = "/etc/shadow"
    архив = _архив(tmp_path / "link.tar.gz", [ссылка])
    with tarfile.open(архив) as tf, pytest.raises(privileged.PrivilegedRefused) as ош:
        list(privileged.безопасные_члены(tf, tmp_path / "dest"))
    assert "наружу" in str(ош.value)


def test_устройство_в_архиве_отвергается(tmp_path):
    """В артефакте сайта нет и не может быть узлов устройств."""
    узел = tarfile.TarInfo("dev/sda")
    узел.type = tarfile.BLKTYPE
    архив = _архив(tmp_path / "dev.tar.gz", [узел])
    with tarfile.open(архив) as tf, pytest.raises(privileged.PrivilegedRefused) as ош:
        list(privileged.безопасные_члены(tf, tmp_path / "dest"))
    assert "недопустимый тип" in str(ош.value)


def test_обычный_артефакт_проходит(tmp_path):
    архив = _архив(tmp_path / "ok.tar.gz",
                   [tarfile.TarInfo("run.py"), tarfile.TarInfo("src/app.py")],
                   {"run.py": b"print(1)", "src/app.py": b"print(2)"})
    with tarfile.open(архив) as tf:
        имена = [ч.name for ч in privileged.безопасные_члены(tf, tmp_path / "dest")]
    assert имена == ["run.py", "src/app.py"]


def test_несовпадение_digest_отменяет_установку(tmp_path):
    """Ставится тот выпуск, который проверен, или никакой."""
    архив = _архив(tmp_path / "ok.tar.gz", [tarfile.TarInfo("run.py")],
                   {"run.py": b"print(1)"})
    with pytest.raises(privileged.PrivilegedRefused) as ош:
        privileged.install_release("zona-01", архив, "sha256:" + "0" * 64, dry_run=True)
    assert "digest" in str(ош.value)


def test_площадка_выводится_из_реестра_а_не_из_аргумента():
    """Принимать путь аргументом значило бы позволить назвать любой каталог."""
    п = privileged.Площадка.из_реестра("zona-01")
    assert п.root == Path("/srv/zonafilm-space")
    assert п.app == Path("/srv/zonafilm-space/app")
    assert str(п.root).startswith("/srv/")


def test_незарегистрированный_сайт_не_имеет_площадки():
    with pytest.raises(Exception):  # noqa: B017 — любой отказ годится
        privileged.Площадка.из_реестра("net-takogo")


def test_мутация_требует_root(tmp_path):
    """Без root привилегированная операция отказывает, а не делает половину."""
    архив = _архив(tmp_path / "ok.tar.gz", [tarfile.TarInfo("run.py")],
                   {"run.py": b"print(1)"})
    import hashlib
    digest = "sha256:" + hashlib.sha256(архив.read_bytes()).hexdigest()
    if __import__("os").geteuid() == 0:
        pytest.skip("запущено от root — отказ проверить нечем")
    with pytest.raises(privileged.PrivilegedRefused) as ош:
        privileged.install_release("zona-01", архив, digest, dry_run=False)
    assert "root" in str(ош.value)
