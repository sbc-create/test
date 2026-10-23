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


def test_pinned_host_key_files_are_present_and_tracked():
    """Закрепление ключа хоста должно РАЗРЕШАТЬСЯ в файл, и файл — лежать в git.

    Прежние проверки требовали только наличия ПОЛЯ `known_hosts_entry_ref` в
    реестре. Поля достаточно, чтобы они прошли, и недостаточно, чтобы доставка
    заработала: измерено 23.10, `inventory/ssh-hosts.yaml` ссылается на
    `inventory/known_hosts.d/k2-zomro-01`, файл есть в рабочей копии сессии и
    НЕ отслеживается git — поэтому в постоянной копии `/srv/site-factory/repo`
    его нет, и готовность доставки каталога K2 показывает нехватку
    «закрепление ключа хоста». Висячая ссылка не отличима от исправной, пока
    её не разрешают, а при `strict_host_key_checking: yes` отсутствие файла
    останавливает доставку целиком.

    Проверяется три факта, а не один: файл существует, он не пуст и разбирается
    как строка known_hosts (хост, тип ключа, ключ в base64), и он ОТСЛЕЖИВАЕТСЯ
    git — без третьего условия проверка зеленеет на копии, где файл оставили
    неотслеживаемым, то есть ровно в сегодняшнем состоянии.

    Чего проверка НЕ делает: не судит, ПОДЛИННЫЙ ли ключ. Отпечаток
    подтверждается владельцем вне сети, и эта проверка такого подтверждения не
    заменяет — она гарантирует лишь, что ключ зафиксирован и не меняется молча.
    """
    import base64
    import subprocess

    hosts = inventory.load("ssh-hosts.yaml").get("hosts") or []
    assert hosts, "ssh-hosts.yaml: ни одного хоста — проверять нечего"
    tracked = subprocess.run(
        ["git", "-C", str(PATHS.root), "ls-files", "-z", "inventory"],
        capture_output=True, text=True, check=True).stdout.split("\0")
    for host in hosts:
        ref = host.get("known_hosts_entry_ref")
        assert ref, f"{host.get('ref')}: нет known_hosts_entry_ref"
        path = PATHS.root / ref
        assert path.is_file(), f"{host['ref']}: закрепление {ref} не существует"
        line = path.read_text(encoding="utf-8").strip()
        assert line, f"{host['ref']}: закрепление {ref} пусто"
        fields = line.split()
        assert len(fields) >= 3, f"{host['ref']}: {ref} не похож на known_hosts"
        assert fields[1].startswith(("ssh-", "ecdsa-")), (
            f"{host['ref']}: {ref} — неизвестный тип ключа {fields[1]}")
        base64.b64decode(fields[2], validate=True)
        assert ref in tracked, (
            f"{host['ref']}: {ref} НЕ отслеживается git — в свежей копии"
            " репозитория закрепления не будет, и доставка остановится")
