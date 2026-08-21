"""REQ-CLAUDE-CONFIG: конфигурация Claude Code проверяема, а не декларативна."""
import json
import re

import yaml

from factory.paths import PATHS

CLAUDE = PATHS.root / ".claude"


def test_claude_md_is_short_enough():
    lines = (PATHS.root / "CLAUDE.md").read_text(encoding="utf-8").splitlines()
    assert 0 < len(lines) <= 200, f"CLAUDE.md {len(lines)} строк — документация рекомендует держаться под 200"


def test_claude_md_names_sources_pipeline_and_dod():
    text = (PATHS.root / "CLAUDE.md").read_text(encoding="utf-8")
    for anchor in ("Источники истины", "Definition of Done", "BLOCKED_LICENSE", "factory deploy"):
        assert anchor in text, f"в CLAUDE.md нет раздела/якоря: {anchor}"


def test_settings_json_is_valid_and_safe():
    settings = json.loads((CLAUDE / "settings.json").read_text(encoding="utf-8"))
    permissions = settings["permissions"]
    assert permissions["defaultMode"] != "bypassPermissions"
    assert settings.get("disableBypassPermissionsMode") == "disable"
    deny = " ".join(permissions["deny"])
    for pattern in ("ssh", "rm -rf", "sudo", "git push --force", "mkfs", "Read(**/.env)"):
        assert pattern in deny, f"нет deny-правила для: {pattern}"


def test_file_rules_use_read_and_edit_not_write():
    """Путевые правила для Write/Glob документация не проверяет — они бесполезны."""
    settings = json.loads((CLAUDE / "settings.json").read_text(encoding="utf-8"))
    for group in ("allow", "ask", "deny"):
        for rule in settings["permissions"].get(group, []):
            assert not re.match(r"^(Write|Glob|NotebookEdit|MultiEdit)\(", rule), \
                f"правило {rule} никогда не будет применено; используй Edit()/Read()"


def test_hooks_are_registered_and_executable():
    settings = json.loads((CLAUDE / "settings.json").read_text(encoding="utf-8"))
    hooks = settings["hooks"]["PreToolUse"]
    matchers = {group["matcher"] for group in hooks}
    assert "Bash" in matchers
    assert any("Edit" in matcher for matcher in matchers)
    for group in hooks + settings["hooks"].get("PostToolUse", []):
        for hook in group["hooks"]:
            script = hook["command"].split()[-1].replace("${CLAUDE_PROJECT_DIR}", str(PATHS.root))
            assert (PATHS.root / script).exists() or PATHS.root.joinpath(script).exists(), script
            assert hook.get("timeout"), "у хука обязан быть timeout"


def test_unattended_settings_enable_sandbox():
    settings = json.loads((CLAUDE / "settings.unattended.json").read_text(encoding="utf-8"))
    sandbox = settings["sandbox"]
    assert sandbox["enabled"] is True
    assert sandbox["failIfUnavailable"] is True
    assert sandbox["allowUnsandboxedCommands"] is False
    assert sandbox["network"]["allowedDomains"] == [], "сеть в закрытом мире по умолчанию пуста"
    assert any(entry["path"].endswith(".ssh") for entry in sandbox["credentials"]["files"])


def test_rules_are_scoped_and_present():
    rules = sorted(p.name for p in (CLAUDE / "rules").glob("*.md"))
    expected = {"dle-php.md", "frontend.md", "content.md", "security.md", "tests.md",
                "infrastructure.md", "deployment.md", "seo.md"}
    assert expected <= set(rules), f"нет правил: {sorted(expected - set(rules))}"
    for path in (CLAUDE / "rules").glob("*.md"):
        text = path.read_text(encoding="utf-8")
        assert text.startswith("---"), f"{path.name}: нет frontmatter"
        front = yaml.safe_load(text.split("---")[1])
        assert front.get("paths"), f"{path.name}: правило обязано быть scoped по путям"


def test_skills_exist_with_valid_frontmatter():
    expected = {"research-freeze", "site-intake", "site-build", "site-qa", "site-deploy",
                "site-rollback", "site-update", "incident-report"}
    found = {p.parent.name for p in (CLAUDE / "skills").glob("*/SKILL.md")}
    assert expected <= found, f"нет скиллов: {sorted(expected - found)}"
    allowed_keys = {"name", "description", "when_to_use", "allowed-tools", "disallowed-tools",
                    "disable-model-invocation", "user-invocable", "model", "effort", "context",
                    "agent", "background", "paths", "metadata", "license", "compatibility",
                    "argument-hint", "arguments", "hooks", "shell"}
    for path in (CLAUDE / "skills").glob("*/SKILL.md"):
        front = yaml.safe_load(path.read_text(encoding="utf-8").split("---")[1])
        assert front.get("description"), f"{path}: без description скилл не будет найден"
        assert set(front) <= allowed_keys, f"{path}: неизвестные поля {set(front) - allowed_keys}"


def test_reviewer_agents_exist():
    expected = {"architecture-reviewer", "dle-reviewer", "security-reviewer",
                "qa-visual-reviewer", "deployment-reviewer"}
    found = set()
    for path in (CLAUDE / "agents").glob("*.md"):
        front = yaml.safe_load(path.read_text(encoding="utf-8").split("---")[1])
        assert front.get("name") and front.get("description")
        found.add(front["name"])
    assert expected <= found, f"нет ревьюеров: {sorted(expected - found)}"
