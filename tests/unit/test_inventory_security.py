"""REQ-SSH: least privilege, host key pinning, узкие права."""
import pytest

from factory import inventory
from factory.errors import BlockedAccess
from factory.paths import PATHS

#: Формы, в которых слово «секрет» допустимо в реестре: ссылка на секрет и имя
#: области секретов. Обе называют, где лежит значение, но самого значения не
#: содержат. Список именно такой, а не «файл целиком разрешён»: исключение для
#: файла сняло бы проверку с его содержимого навсегда.
SECRET_MENTION_FORMS = ("_secret_ref", "secret_scope", "secret://")


def test_inventory_contains_no_secret_values():
    forbidden = ("BEGIN PRIVATE KEY", "password:", "api_token:", "secret:")
    for path in PATHS.inventory.glob("*.yaml"):
        text = path.read_text(encoding="utf-8")
        for marker in forbidden:
            assert marker not in text, f"{path.name}: похоже на секрет в открытом виде ({marker})"
        mentions_secret = "secret" in text.lower()
        in_allowed_form = any(form in text for form in SECRET_MENTION_FORMS)
        assert in_allowed_form or not mentions_secret or path.name in (
            "targets.yaml", "public-suffixes.yaml", "README.md"
        ), f"{path.name}: слово «секрет» вне разрешённых форм {SECRET_MENTION_FORMS}"


def test_unknown_refs_are_blocked():
    for resolver in (inventory.target, inventory.ssh_host, inventory.dns_zone, inventory.license_entry):
        with pytest.raises(BlockedAccess):
            resolver("does-not-exist")


def test_root_deploy_user_is_rejected(monkeypatch):
    monkeypatch.setattr(inventory, "load", lambda name: {"hosts": [
        {"ref": "bad", "hostname": "h", "deploy_user": "root", "known_hosts_entry_ref": "x"}]}
        if name == "ssh-hosts.yaml" else {})
    with pytest.raises(BlockedAccess) as exc:
        inventory.ssh_host("bad")
    assert "root" in exc.value.reason


def test_missing_host_key_pin_is_rejected(monkeypatch):
    monkeypatch.setattr(inventory, "load", lambda name: {"hosts": [
        {"ref": "bad", "hostname": "h", "deploy_user": "deploy"}]}
        if name == "ssh-hosts.yaml" else {})
    with pytest.raises(BlockedAccess) as exc:
        inventory.ssh_host("bad")
    assert "known_hosts_entry_ref" in exc.value.reason


def test_local_target_cannot_be_used_for_production():
    target = inventory.target("local-disposable")
    assert target["production_capable"] is False
    assert "production" not in target["environments"]


def test_ssh_template_documents_sudo_allowlist_and_pinning():
    text = (PATHS.inventory / "ssh-hosts.yaml").read_text(encoding="utf-8")
    for anchor in ("sudo_allowlist", "known_hosts_entry_ref", "strict_host_key_checking", "deploy_user"):
        assert anchor in text


def test_dns_zone_scope_is_documented():
    text = (PATHS.inventory / "dns-zones.yaml").read_text(encoding="utf-8")
    assert "zone_records_only" in text and "api_token_secret_ref" in text


def test_ansible_never_disables_host_key_checking():
    for path in (PATHS.automation / "ansible").rglob("*.yml"):
        text = path.read_text(encoding="utf-8")
        assert "StrictHostKeyChecking=no" not in text
        assert "host_key_checking = False" not in text
    target = (PATHS.root / "factory" / "targets" / "ssh_ansible.py").read_text(encoding="utf-8")
    assert 'ANSIBLE_HOST_KEY_CHECKING"] = "True"' in target
    assert "StrictHostKeyChecking=yes" in target
