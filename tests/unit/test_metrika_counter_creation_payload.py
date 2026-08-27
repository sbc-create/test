"""REQ-METRIKA-CREATE-PAYLOAD: счётчик создаётся, а не отклоняется на лету.

История отказа. Ветка создания счётчика ни разу не исполнялась успешно: три
счётчика Yummy были найдены готовыми (`reused`), и `created` не случался никогда.
Ошибка в теле запроса пролежала незамеченной до первого настоящего создания —
трёх доменов Lords, — и все три отказа выглядели одинаково:

    metrika ответил HTTP 400 — Could not read JSON, error in line 1,
    column 115, path: counter.code_options.visor

`code_options` Метрика принимает только на изменении счётчика. На создании этого
поля быть не должно. Инвариант «запись сессий выключена» при этом сохраняется:
сразу после создания `apply` вызывает `ensure_webvisor_disabled`, который ходит
PUT-ом — тем самым путём, которым Метрика полем и управляет.

Проверяется поведение, а не текст: подставной транспорт ловит настоящее тело
запроса, которое ушло бы в Метрику.
"""

from __future__ import annotations

from factory.analytics import yandex


class _Response:
    def __init__(self, payload: dict):
        self.payload = payload
        self.status = 200


class _Recorder:
    """Транспорт, который запоминает тело и притворяется Метрикой."""

    def __init__(self):
        self.posts: list[tuple[str, dict]] = []
        self.puts: list[tuple[str, dict]] = []

    def get(self, path, **kwargs):
        # Счётчиков нет — значит ветка создания и исполнится.
        return _Response({"counters": []})

    def post(self, path, body=None, **kwargs):
        self.posts.append((path, body or {}))
        return _Response({"counter": {"id": 999001, "status": "Active"}})

    def put(self, path, body=None, **kwargs):
        self.puts.append((path, body or {}))
        return _Response({"counter": {"id": 999001, "code_options": {"visor": False}}})


def _provider(recorder: _Recorder):
    """Настоящий провайдер с подставным транспортом — конструктор его принимает."""
    return yandex.YandexAnalyticsProvider(
        dry_run=False,
        metrika_client=recorder,
        webmaster_client=recorder,
    )


class TestCounterCreationBody:
    def test_creation_does_not_send_code_options(self):
        recorder = _Recorder()
        provider = _provider(recorder)
        state = provider.ensure_metrica_counter("lordfilm47.space", "Lords — lordfilm47.space")

        assert state.created is True, "ветка создания не исполнилась — тест ничего не проверяет"
        assert recorder.posts, "запрос на создание счётчика не ушёл"
        _, body = recorder.posts[0]
        counter = body.get("counter") or {}
        assert "code_options" not in counter, (
            "тело создания снова содержит code_options: Метрика отвечает на это "
            "HTTP 400 и счётчик не создаётся"
        )

    def test_creation_still_names_the_domain_and_the_counter(self):
        recorder = _Recorder()
        provider = _provider(recorder)
        provider.ensure_metrica_counter("lordserial33.biz", "Lords — lordserial33.biz")
        _, body = recorder.posts[0]
        counter = body["counter"]
        assert counter["name"] == "Lords — lordserial33.biz"
        assert counter["site2"]["site"] == "lordserial33.biz"

    def test_gdpr_agreement_is_never_sent(self):
        """Юридическое действие владельца аккаунта, а не фабрики (D55)."""
        recorder = _Recorder()
        provider = _provider(recorder)
        provider.ensure_metrica_counter("1lordserials1.online", "Lords — 1lordserials1.online")
        _, body = recorder.posts[0]
        assert "gdpr_agreement_accepted" not in body["counter"]
