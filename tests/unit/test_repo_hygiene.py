"""REQ-DLE-DIST, REQ-DLE-CORE, REQ-DLE-PERMS, REQ-INSTALLER, REQ-CDNVH."""
import os
import re
import subprocess

from factory.paths import PATHS


def _tracked_files() -> list[str]:
    out = subprocess.run(["git", "ls-files"], cwd=PATHS.root, capture_output=True, text=True, check=False)
    return out.stdout.splitlines()


def test_no_licensed_distribution_in_git():
    for path in _tracked_files():
        assert not path.startswith("blueprints/dle20/dist/"), f"лицензионный дистрибутив в git: {path}"
        assert not re.search(r"\.(zip|tar\.gz|tgz)$", path), f"архив в git: {path}"


def test_gitignore_protects_secrets_and_dist():
    text = (PATHS.root / ".gitignore").read_text(encoding="utf-8")
    for pattern in ("blueprints/dle20/dist/", ".env", "secrets/", "var/", "*.pem", "*.key"):
        assert pattern in text, f".gitignore не защищает {pattern}"


def test_no_secret_material_tracked():
    for path in _tracked_files():
        assert not re.search(r"(^|/)(\.env|id_rsa|id_ed25519)(\.|$)", path), path
        assert not path.endswith((".pem", ".key", ".p12", ".pfx")), path


def test_no_dle_core_patches():
    """Ядро DLE не модифицируется: в репозитории нет ни патчей, ни копий ядра."""
    for path in _tracked_files():
        assert "engine/" not in path or path.startswith(("docs/", "knowledge/", "blueprints/")), path
        assert not path.endswith(".patch"), path


def test_no_world_writable_files_tracked():
    for path in _tracked_files():
        full = PATHS.root / path
        if full.exists():
            mode = full.stat().st_mode & 0o777
            assert not (mode & 0o002), f"world-writable файл: {path} ({oct(mode)})"


def test_installer_removal_is_declared():
    tasks = (PATHS.automation / "ansible" / "roles" / "dle_release" / "tasks" / "main.yml").read_text(encoding="utf-8")
    assert "installer_entrypoints" in tasks and "state: absent" in tasks


def test_cdnvideohub_is_extension_point_only():
    plugin_dir = PATHS.plugins / "cdnvideohub"
    assert plugin_dir.exists(), "extension point для CDN Video Hub обязана существовать"
    readme = (plugin_dir / "README.md").read_text(encoding="utf-8").lower()
    assert "не интегрир" in readme or "no-op" in readme
    for path in _tracked_files():
        if path.startswith("plugins/cdnvideohub/"):
            assert path.endswith((".md", ".yaml", ".py", ".gitkeep")), f"неожиданный файл в extension point: {path}"


def test_hook_scripts_are_executable_and_lint_clean():
    for script in (PATHS.root / ".claude" / "hooks").glob("*.py"):
        result = subprocess.run(["python3", "-m", "py_compile", str(script)], capture_output=True, check=False)
        assert result.returncode == 0, f"{script}: {result.stderr.decode()[:200]}"


def test_php_sources_pass_lint():
    for php_file in list((PATHS.root / "automation").rglob("*.php")) + list((PATHS.themes).rglob("*.php")):
        result = subprocess.run(["php", "-l", str(php_file)], capture_output=True, text=True, check=False)
        assert result.returncode == 0, f"{php_file}: {result.stdout}"


def test_javascript_sources_parse():
    for js_file in [PATHS.root / "tools" / "browser-audit.js"] + list((PATHS.themes).rglob("*.js")):
        result = subprocess.run(["node", "--check", str(js_file)], capture_output=True, text=True, check=False)
        assert result.returncode == 0, f"{js_file}: {result.stderr[:200]}"


def test_ansible_yaml_parses():
    import yaml
    for path in (PATHS.automation / "ansible").rglob("*.yml"):
        yaml.safe_load(path.read_text(encoding="utf-8"))
