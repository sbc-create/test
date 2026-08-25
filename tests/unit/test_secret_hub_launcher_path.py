"""Единая точка запуска обязана существовать на хосте, а не иногда.

Боевой симптом: `bash /srv/site-factory/repo/var/install-secret-hub.sh` →
«No such file or directory», при том что владелец находился именно в корне
репозитория.

Причин две, и обе системные:

1. ``var/`` — рабочий каталог фабрики: locks, build, backups, artifacts. Его
   содержимое меняется на каждом прогоне. В git лончер попадал через
   исключение ``!var/...`` поверх ``var/*`` — конструкцию, которая работает
   ровно до первой неожиданности.
2. ``/srv/site-factory/repo`` — **общая** рабочая копия: ветки в ней
   переключают несколько параллельных сессий. На ветках, созданных до
   появления Secret Hub, лончера нет вовсе, и при переключении он исчезает из
   рабочего дерева.

Отсюда правило: единая точка запуска живёт в отслеживаемом каталоге, который
меняется только вместе с кодом, и находит репозиторий от своего собственного
расположения, а не от текущего каталога или переменной окружения.
"""
from __future__ import annotations

import os
import subprocess

import pytest

LAUNCHER = "bin/secret-hub-install"
#: Прежнее место лончера. Именно его отсутствие на хосте владелец и увидел.
OLD_PATH = "var/install-secret-hub.sh"
INSTALLER = "automation/secret-hub/install-secret-hub.sh"


@pytest.fixture
def tracked(repo_root):
    """Файлы, отслеживаемые git на текущем HEAD."""
    out = subprocess.run(["git", "-C", str(repo_root), "ls-files"],
                         capture_output=True, text=True, check=False).stdout
    return set(out.split())


class TestLauncherLivesInATrackedStablePath:
    def test_launcher_is_tracked(self, tracked):
        assert LAUNCHER in tracked, "единая точка запуска не отслеживается git"

    def test_installer_is_tracked(self, tracked):
        assert INSTALLER in tracked

    def test_nothing_runnable_lives_in_var(self, tracked):
        """`var/` — рабочий каталог; версионируемым скриптам там не место."""
        runnable = [p for p in tracked
                    if p.startswith("var/") and p.endswith((".sh", ".py"))]
        assert runnable == [], f"в var/ снова появились скрипты: {runnable}"

    def test_gitignore_has_no_exception_for_var_scripts(self, repo_root):
        text = (repo_root / ".gitignore").read_text(encoding="utf-8")
        exceptions = [line.strip() for line in text.splitlines()
                      if line.strip().startswith("!var/")
                      and line.strip() != "!var/.gitkeep"]
        assert exceptions == [], \
            f"исключение в .gitignore возвращает скрипт в рабочий каталог: {exceptions}"

    def test_launcher_exists_on_disk(self, repo_root):
        assert (repo_root / LAUNCHER).exists()
        assert (repo_root / INSTALLER).exists()

    def test_launcher_is_executable(self, repo_root):
        assert os.access(repo_root / LAUNCHER, os.X_OK), \
            "лончер не исполняем — придётся угадывать, звать его через bash или нет"


class TestLauncherFindsItsOwnRepository:
    def test_launcher_resolves_repo_from_its_location(self, repo_root):
        """Ни текущий каталог, ни переменные окружения не должны быть нужны."""
        text = (repo_root / LAUNCHER).read_text(encoding="utf-8")
        assert "BASH_SOURCE" in text
        assert "readlink -f" in text

    def test_installer_resolves_repo_from_its_location(self, repo_root):
        text = (repo_root / INSTALLER).read_text(encoding="utf-8")
        assert "BASH_SOURCE" in text
        assert "dirname" in text

    def test_launcher_works_from_an_unrelated_directory(self, repo_root, tmp_path):
        """Запуск из чужого каталога — обычный случай, а не исключение."""
        result = subprocess.run(
            ["bash", str(repo_root / LAUNCHER), "--preflight"],
            cwd=tmp_path, capture_output=True, text=True, timeout=120, check=False)
        assert result.returncode == 0, result.stdout + result.stderr
        assert "PREFLIGHT=pass" in result.stdout


class TestPreflightIsSafeAndInformative:
    def _run(self, repo_root):
        return subprocess.run(["bash", str(repo_root / LAUNCHER), "--preflight"],
                              capture_output=True, text=True, timeout=120, check=False)

    def test_preflight_passes_without_root(self, repo_root):
        result = self._run(repo_root)
        assert result.returncode == 0, result.stdout + result.stderr
        assert "PREFLIGHT=pass" in result.stdout

    def test_preflight_changes_nothing(self, repo_root):
        """Проверка обязана быть безопасной: рабочее дерево не меняется."""
        before = subprocess.run(["git", "-C", str(repo_root), "status", "--porcelain"],
                                capture_output=True, text=True, check=False).stdout
        self._run(repo_root)
        after = subprocess.run(["git", "-C", str(repo_root), "status", "--porcelain"],
                               capture_output=True, text=True, check=False).stdout
        assert before == after, "предполётная проверка изменила рабочее дерево"

    def test_preflight_lists_the_steps_it_would_take(self, repo_root):
        result = self._run(repo_root)
        for step in ("перезапуск хаба", "перезапуск панели",
                     "применение сохранённого", "проверка результата"):
            assert step in result.stdout, f"шаг «{step}» не заявлен"

    def test_preflight_checks_every_required_file(self, repo_root):
        result = self._run(repo_root)
        for required in ("install.sh", "bootstrap-venv.sh",
                         "site-factory-secret-hub.service",
                         "site-factory-secret-panel.service",
                         "config/secret-hub.json", "reconcile.py"):
            assert required in result.stdout, f"{required} не проверяется"

    def test_preflight_reports_missing_files(self, repo_root, tmp_path):
        """Отсутствие обязательного файла обязано быть замечено, а не пропущено."""
        import shutil

        copy = tmp_path / "repo"
        shutil.copytree(repo_root / "automation", copy / "automation")
        shutil.copytree(repo_root / "bin", copy / "bin")
        (copy / "config").mkdir()
        # config/secret-hub.json намеренно не копируется
        result = subprocess.run(["bash", str(copy / LAUNCHER), "--preflight"],
                                capture_output=True, text=True, timeout=120, check=False)
        assert result.returncode != 0
        assert "ОТСУТСТВУЕТ" in result.stdout + result.stderr


class TestTheCommandDoesWhatItPromises:
    def test_installer_restarts_both_services(self, repo_root):
        launcher = (repo_root / INSTALLER).read_text(encoding="utf-8")
        installer = (repo_root / "automation" / "secret-hub"
                     / "install.sh").read_text(encoding="utf-8")
        assert 'systemctl restart "$PANEL_UNIT"' in launcher
        assert 'systemctl restart "$UNIT"' in installer

    def test_installer_runs_reconcile(self, repo_root):
        text = (repo_root / INSTALLER).read_text(encoding="utf-8")
        assert "rootcmd reconcile" in text

    def test_reconcile_includes_audit(self, repo_root):
        text = (repo_root / "factory" / "secret_hub"
                / "rootcmd.py").read_text(encoding="utf-8")
        assert "reconcile.audit" in text
        assert "format_audit" in text

    def test_installer_does_not_touch_the_master_key(self, repo_root):
        text = (repo_root / "automation" / "secret-hub"
                / "install.sh").read_text(encoding="utf-8")
        assert 'if [ -e "$KEY_FILE" ]' in text

    def test_no_reference_to_the_old_var_path_remains(self, repo_root):
        """Старый путь не должен всплывать ни в скриптах, ни в документации."""
        offenders = []
        for relative in ("automation/secret-hub/install.sh",
                         "automation/secret-hub/install-secret-hub.sh",
                         "bin/secret-hub-install",
                         "docs/SECRET_HUB.md"):
            path = repo_root / relative
            if not path.exists():
                continue
            text = path.read_text(encoding="utf-8")
            for line in text.splitlines():
                if OLD_PATH in line and not line.strip().startswith("#"):
                    offenders.append(f"{relative}: {line.strip()}")
        assert offenders == [], f"остались ссылки на прежний путь: {offenders}"
