"""Живая проверка credentials: три исхода и ни одной утечки.

Сеть не участвует: подставляется opener. Проверяется, что «отвергнут» и «не
проверено» — разные исходы, что записывать разрешено только явно принятое, и
что ни значение, ни тело ответа не попадают в результат.
"""
from __future__ import annotations

import urllib.error

import pytest

from factory.errors import BlockedAccess
from factory.secret_hub import provider
from factory.secret_hub.crypto import Secret
from factory.secret_hub.registry import VerifyContract

TOKEN = "живой-токен-cdnvideohub"
PUBLISHER = "publisher-42"

CONTRACT = VerifyContract(
    base_url="https://public-api.cdnvideohub.com/api/v1/",
    path="countries", method="GET", auth_header="Authorization", auth_scheme="Bearer",
    timeout_ms=15000, provenance="из рабочего клиента на хосте",
)


class FakeResponse:
    def __init__(self, status: int, body: bytes = b'{"items":[]}') -> None:
        self.status = status
        self._body = body
        self.read_calls = 0

    def getcode(self) -> int:
        return self.status

    def read(self, *args) -> bytes:
        self.read_calls += 1
        return self._body

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


def opener_returning(status: int):
    captured: dict = {}

    def opener(request, timeout=None):
        captured["headers"] = dict(request.header_items())
        captured["method"] = request.get_method()
        captured["url"] = request.full_url
        captured["timeout"] = timeout
        return FakeResponse(status)

    opener.captured = captured
    return opener


def opener_raising(status: int):
    def opener(request, timeout=None):
        raise urllib.error.HTTPError(request.full_url, status, "отказ", {}, None)

    return opener


class TestOutcomes:
    def test_2xx_is_accepted(self):
        result = provider.verify(CONTRACT, Secret(TOKEN, "t"), Secret(PUBLISHER, "p"),
                                 opener=opener_returning(200))
        assert result.outcome is provider.Outcome.ACCEPTED
        assert result.ok is True
        assert result.may_store is True

    @pytest.mark.parametrize("status", sorted(provider.REJECTED_STATUSES))
    def test_provider_refusal_is_rejected(self, status):
        result = provider.verify(CONTRACT, Secret(TOKEN, "t"), Secret(PUBLISHER, "p"),
                                 opener=opener_raising(status))
        assert result.outcome is provider.Outcome.REJECTED
        assert result.may_store is False

    @pytest.mark.parametrize("status", [500, 502, 503, 429, 404])
    def test_other_statuses_are_unmeasured(self, status):
        """«Сервис сломался» — не «токен неверен»."""
        result = provider.verify(CONTRACT, Secret(TOKEN, "t"), Secret(PUBLISHER, "p"),
                                 opener=opener_raising(status))
        assert result.outcome is provider.Outcome.UNMEASURED
        assert result.may_store is False

    def test_network_failure_is_unmeasured_not_rejected(self):
        def opener(request, timeout=None):
            raise urllib.error.URLError("нет маршрута")

        result = provider.verify(CONTRACT, Secret(TOKEN, "t"), Secret(PUBLISHER, "p"),
                                 opener=opener)
        assert result.outcome is provider.Outcome.UNMEASURED
        assert result.http_status is None
        assert result.may_store is False, "непроверенное не записывается"

    def test_timeout_is_unmeasured(self):
        def opener(request, timeout=None):
            raise TimeoutError()

        result = provider.verify(CONTRACT, Secret(TOKEN, "t"), Secret(PUBLISHER, "p"),
                                 opener=opener)
        assert result.outcome is provider.Outcome.UNMEASURED


class TestRequestShape:
    def test_request_is_read_only_get(self):
        opener = opener_returning(200)
        provider.verify(CONTRACT, Secret(TOKEN, "t"), Secret(PUBLISHER, "p"), opener=opener)
        assert opener.captured["method"] == "GET"

    def test_token_goes_only_into_the_authorization_header(self):
        opener = opener_returning(200)
        provider.verify(CONTRACT, Secret(TOKEN, "t"), Secret(PUBLISHER, "p"), opener=opener)
        assert TOKEN not in opener.captured["url"], "токен в URL — это токен в логах прокси"
        headers = opener.captured["headers"]
        auth = next(v for k, v in headers.items() if k.lower() == "authorization")
        assert auth == f"Bearer {TOKEN}"

    def test_publisher_id_is_never_sent(self):
        """Publisher ID — не credential Content API; посылать его туда незачем."""
        opener = opener_returning(200)
        provider.verify(CONTRACT, Secret(TOKEN, "t"), Secret(PUBLISHER, "p"), opener=opener)
        assert PUBLISHER not in str(opener.captured)

    def test_timeout_is_applied(self):
        opener = opener_returning(200)
        provider.verify(CONTRACT, Secret(TOKEN, "t"), Secret(PUBLISHER, "p"), opener=opener)
        assert opener.captured["timeout"] == 15.0


class TestNoLeaks:
    def test_result_contains_neither_value(self):
        result = provider.verify(CONTRACT, Secret(TOKEN, "t"), Secret(PUBLISHER, "p"),
                                 opener=opener_returning(200))
        serialized = str(result.as_dict())
        assert TOKEN not in serialized
        assert PUBLISHER not in serialized

    def test_response_body_is_not_read(self):
        """Тело ответа не читается: прочитанное имеет свойство попадать в логи."""
        response = FakeResponse(200)

        def opener(request, timeout=None):
            return response

        provider.verify(CONTRACT, Secret(TOKEN, "t"), Secret(PUBLISHER, "p"), opener=opener)
        assert response.read_calls == 0

    def test_refusal_message_contains_no_value(self):
        result = provider.verify(CONTRACT, Secret(TOKEN, "t"), Secret(PUBLISHER, "p"),
                                 opener=opener_raising(401))
        with pytest.raises(BlockedAccess) as excinfo:
            provider.require_verified(result, "yami")
        assert TOKEN not in excinfo.value.reason
        assert TOKEN not in str(excinfo.value.as_blocker())


class TestPublisherIdFormat:
    @pytest.mark.parametrize("value", ["publisher-1", "PUB_42", "a.b:c", "x1"])
    def test_reasonable_values_pass(self, value):
        assert provider.check_publisher_id(Secret(value, "p")) is True

    @pytest.mark.parametrize("value", ["", " ", "с пробелом", "a", "-начинается-с-дефиса",
                                       "перевод\nстроки"])
    def test_broken_values_fail(self, value):
        assert provider.check_publisher_id(Secret(value, "p")) is False

    def test_bad_publisher_id_blocks_storing_even_if_token_is_good(self):
        result = provider.verify(CONTRACT, Secret(TOKEN, "t"), Secret("с пробелом", "p"),
                                 opener=opener_returning(200))
        assert result.publisher_id_format_ok is False
        assert result.may_store is False


class TestRequireVerified:
    def test_accepted_passes(self):
        result = provider.verify(CONTRACT, Secret(TOKEN, "t"), Secret(PUBLISHER, "p"),
                                 opener=opener_returning(200))
        provider.require_verified(result, "yami")  # не выбрасывает

    def test_rejected_raises_blocked_access(self):
        result = provider.verify(CONTRACT, Secret(TOKEN, "t"), Secret(PUBLISHER, "p"),
                                 opener=opener_raising(403))
        with pytest.raises(BlockedAccess) as excinfo:
            provider.require_verified(result, "lords")
        assert excinfo.value.status == "BLOCKED_ACCESS"
        assert "Значения не сохранены" in excinfo.value.reason

    def test_unmeasured_raises_with_network_hint(self):
        def opener(request, timeout=None):
            raise urllib.error.URLError("нет сети")

        result = provider.verify(CONTRACT, Secret(TOKEN, "t"), Secret(PUBLISHER, "p"),
                                 opener=opener)
        with pytest.raises(BlockedAccess) as excinfo:
            provider.require_verified(result, "yami")
        assert "public-api.cdnvideohub.com" in excinfo.value.required_input


class TestContractComesFromConfiguration:
    def test_verify_url_is_built_from_registry(self, repo_root):
        from factory.secret_hub.registry import load

        config = load(repo_root / "config" / "secret-hub.json")
        assert config.verify.url == "https://public-api.cdnvideohub.com/api/v1/countries"
        assert config.verify.method == "GET"

    def test_provenance_is_recorded(self, repo_root):
        from factory.secret_hub.registry import load

        config = load(repo_root / "config" / "secret-hub.json")
        assert "constants.ts" in config.verify.provenance, \
            "адрес обязан ссылаться на существующий артефакт, а не быть подобранным"
