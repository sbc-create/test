"""REQ-SECRETS: значение секрета не покидает процесс."""
import json

from factory.redaction import PLACEHOLDER, redact, redact_obj


def test_command_line_password_is_redacted():
    assert "Sup3rSecretValue" not in redact("mysql --password=Sup3rSecretValue -h db")


def test_url_credentials_are_redacted():
    out = redact("https://user:hunter2pass@host/path")
    assert "hunter2pass" not in out and "user" in out


def test_private_key_block_is_redacted():
    text = "-----BEGIN PRIVATE KEY-----\nMIIabc\n-----END PRIVATE KEY-----"
    assert "MIIabc" not in redact(text)


def test_known_token_shapes():
    for token in ("AKIAIOSFODNN7EXAMPLE", "ghp_" + "a" * 30, "vk1.a." + "b" * 30):
        assert token not in redact(f"value: {token}")


def test_secret_ref_is_preserved():
    """Ссылка — это не секрет: прятать её вредно, она нужна оператору."""
    for ref in ("env:FACTORY_DLE_LICENSE", "file:/run/secrets/db", "vault:kv/site/db"):
        assert ref in redact(f"password_secret_ref: {ref}")


def test_env_secret_values_are_stripped(monkeypatch):
    monkeypatch.setenv("FACTORY_DEMO_TOKEN", "abcdef0123456789")
    assert "abcdef0123456789" not in redact("лог содержит abcdef0123456789 в тексте")


def test_boolean_fields_are_not_mangled():
    """Регрессия: «passed» содержит «pass», но булево значение обязано выжить."""
    data = {"passed": True, "passed_checks": 3, "compass": "ok", "password": "s3cret-value"}
    result = redact_obj(data)
    assert result["passed"] is True
    assert result["passed_checks"] == 3
    assert result["compass"] == "ok"
    assert result["password"] == PLACEHOLDER


def test_nested_structures():
    data = {"checks": [{"id": "x", "passed": False, "api_key": "k" * 20}], "secret_ref": "env:X"}
    result = redact_obj(data)
    assert result["checks"][0]["passed"] is False
    assert result["checks"][0]["api_key"] == PLACEHOLDER
    assert json.dumps(result)  # результат остаётся сериализуемым
