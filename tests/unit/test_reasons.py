"""REQ-REASONS: классификация причин пригодна для машины и для человека.

Проверяется не наличие списка, а то, ради чего он заведён: по коду можно
понять звено, решить, повторять ли, что показать зрителю и что система вправе
сделать сама. Классификация без этих свойств — просто строки.
"""
import pytest

from factory.site_engine.api import reasons

ОБЯЗАТЕЛЬНЫЕ = [
    "MISSING_PROVIDER_ID", "UNSUPPORTED_AGGREGATOR", "IDENTITY_MAPPING_MISS",
    "IDENTITY_AMBIGUOUS", "PROVIDER_NOT_PLAYABLE", "RESOLVER_TIMEOUT",
    "RESOLVER_ERROR", "DOMAIN_NOT_ELIGIBLE", "CONTENT_NOT_PLAYABLE_BY_POLICY",
    "PROJECTION_STALE", "DESCRIPTOR_INVALID", "CLIENT_COMPONENT_FAILED",
    "IFRAME_FAILED", "MEDIA_REQUEST_FAILED", "FIRST_FRAME_TIMEOUT",
    "IDENTIFIER_FORBIDDEN_BY_CONTRACT",
    "IDENTIFIER_DISABLED_BY_POLICY", "IDENTIFIER_OUT_OF_SCOPE", "UNKNOWN",
]


@pytest.mark.parametrize("code", ОБЯЗАТЕЛЬНЫЕ)
def test_код_объявлен(code):
    assert code in reasons.REASONS


@pytest.mark.parametrize("code", ОБЯЗАТЕЛЬНЫЕ)
def test_у_кода_есть_всё_нужное(code):
    r = reasons.REASONS[code]
    assert r.stage in reasons.STAGES, f"{code}: звено вне цепочки"
    assert r.public and len(r.public) > 10, f"{code}: нет безопасного сообщения зрителю"
    assert r.operator and len(r.operator) > 20, f"{code}: нет детализации оператору"
    assert r.metric, f"{code}: нет метрики"
    assert r.remediation and len(r.remediation) > 15, f"{code}: не сказано, что делать"


@pytest.mark.parametrize("code", ОБЯЗАТЕЛЬНЫЕ)
def test_публичное_сообщение_не_раскрывает_устройство(code):
    """Зрителю не нужны имена агрегаторов, кодов ответа и наших модулей."""
    p = reasons.REASONS[code].public.lower()
    for запрет in ("aggregator", "kinopoisk", "imdb", "resolver", "descriptor",
                   "http", "204", "503", "kp:", "provider"):
        assert запрет not in p, f"{code}: публичное сообщение раскрывает {запрет!r}"


def test_окончательные_и_повторяемые_не_пересекаются():
    assert not (reasons.TERMINAL & reasons.RETRYABLE)
    assert set(reasons.REASONS) == reasons.TERMINAL | reasons.RETRYABLE


def test_повторяемые_имеют_остывание():
    """Повтор без паузы превращается в самообстрел поставщика."""
    for code in reasons.RETRYABLE:
        r = reasons.REASONS[code]
        if r.automatic:
            assert r.cooldown_seconds > 0, f"{code}: автодействие без остывания"


def test_опасное_не_делается_автоматически():
    """Неоднозначное тождество выбирать автоматически нельзя."""
    assert reasons.REASONS["IDENTITY_AMBIGUOUS"].automatic is None
    assert reasons.REASONS["IDENTITY_AMBIGUOUS"].terminal is True


def test_политика_и_отсутствие_идентификатора_окончательны():
    """Повторять то, что не изменится от повтора, — жечь квоту впустую."""
    for code in ("MISSING_PROVIDER_ID", "DOMAIN_NOT_ELIGIBLE",
                 "CONTENT_NOT_PLAYABLE_BY_POLICY", "PROVIDER_NOT_PLAYABLE"):
        assert reasons.REASONS[code].terminal, f"{code} должен быть окончательным"


def test_unknown_имеет_порог_эскалации():
    """Массовый UNKNOWN означает, что классификация отстала."""
    assert reasons.REASONS["UNKNOWN"].escalate_after > 0


def test_неизвестный_код_не_роняет():
    assert reasons.get("НЕТ ТАКОГО").code == "UNKNOWN"
    assert reasons.get("").code == "UNKNOWN"
    assert reasons.get(None).code == "UNKNOWN"


def test_справочник_машиночитаем():
    c = reasons.catalogue()
    assert c["version"] == reasons.VERSION
    assert len(c["codes"]) == len(ОБЯЗАТЕЛЬНЫЕ)
    for _code, d in c["codes"].items():
        assert d["retryable"] == (not d["terminal"])
        assert d["stage"] in c["stages"]


# ---- классификация состояния записи -----------------------------------------

def test_нет_идентификаторов():
    assert reasons.classify_descriptor({}, None) == "MISSING_PROVIDER_ID"


def test_запрещённый_контрактом_идентификатор_отличается_от_неизвестного():
    """Ровно класс двух названных владельцем адресов.

    IMDb запрещён правилом PC-2, а не отсутствует в перечне. Смешивать нельзя:
    первое чинится решением владельца, второе — кодом.
    """
    assert reasons.classify_descriptor({"imdb": "43670638"}, None) == \
        "IDENTIFIER_FORBIDDEN_BY_CONTRACT"
    assert reasons.classify_descriptor({"tvdb": "1"}, None) == "UNSUPPORTED_AGGREGATOR"


def test_запрет_контракта_окончателен_и_без_автодействия():
    """Снятие запрета — решение владельца контракта, не системы."""
    r = reasons.REASONS["IDENTIFIER_FORBIDDEN_BY_CONTRACT"]
    assert r.terminal is True
    assert r.automatic is None
    assert "требует-решения-владельца" in r.tags


def test_неполный_дескриптор():
    assert reasons.classify_descriptor({"kinopoisk": "1"},
                                       {"aggregator": "kp"}) == "DESCRIPTOR_INVALID"


@pytest.mark.parametrize("проба,ожидание", [
    ("EMPTY", "PROVIDER_NOT_PLAYABLE"),
    ("ERROR_TimeoutError", "RESOLVER_TIMEOUT"),
    ("HTTP_502", "RESOLVER_ERROR"),
    ("ERROR_URLError", "RESOLVER_ERROR"),
    (None, "OK"),
])
def test_ответ_поставщика_переводится_в_код(проба, ожидание):
    assert reasons.classify_descriptor(
        {"kinopoisk": "1"}, {"aggregator": "kp", "title_id": "1"},
        probe=проба) == ожидание
