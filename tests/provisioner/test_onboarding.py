"""Обязательные проверки Integration Provisioner (пункт 11 задания).

Доказываются следствия, а не вызовы: сколько объектов создано у провайдера,
что осталось после обрыва, что уцелело при компенсации и чего Qwen не может
сделать в принципе.
"""
from __future__ import annotations

import pytest

from factory.site_engine.changeset import model as M
from factory.site_engine.changeset import store as S
from factory.site_engine.provisioner import orchestrator as O
from factory.site_engine.provisioner import readiness as R
from factory.site_engine.provisioner.providers import base as B
from factory.site_engine.provisioner.providers import fake as F
from factory.site_engine.provisioner.qwen import QwenDenied, QwenКонтракт

from .conftest import намерение, одобрить


def _provisioner(о, одобряющий=одобрить):
    return O.Provisioner(соед_наборов=о["соед"], связи=о["связи"],
                         реестр=о["реестр"], провайдеры=о["провайдеры"],
                         одобряющий=одобряющий, сон=lambda _: None)


def _провести(о, site_id="s-1", домен="shop.test", ключ="k-1"):
    о["реестр"].добавить(site_id, domain=домен)
    п = _provisioner(о)
    return п, п.провести(намерение(домен, ключ), site_id)


# --- 1. динамический рост ----------------------------------------------------

def test_01_n_плюс_один_даёт_одну_проекцию(обвязка):
    for i in range(1, 4):
        _провести(обвязка, f"s-{i}", f"shop{i}.test", f"k-{i}")
    _, свод = _провести(обвязка, "s-4", "shop4.test", "k-4")
    assert свод["site_id"] == "s-4"
    # На новый сайт — ровно один комплект связей, без дублей.
    ключи = [(с["provider_type"], с["resource_kind"]) for с in свод["links"]]
    assert len(ключи) == len(set(ключи))
    assert len(обвязка["реестр"].сайты()) == 4


# --- 2. повтор события -------------------------------------------------------

def test_02_повтор_не_создаёт_второй_объект(обвязка):
    п, первый = _провести(обвязка)
    второй = п.провести(намерение("shop.test", "k-1"), "s-1")
    мир = обвязка["мир"]
    assert мир.эффектов("create") == 5, "по одному объекту на провайдера"
    assert len(первый["links"]) == len(второй["links"]) == 5


# --- 3. два одинаковых вызова ------------------------------------------------

def test_03_два_вызова_один_эффект(обвязка):
    мир = обвязка["мир"]
    м = обвязка["провайдеры"]["analytics"]
    и = намерение()
    н = м.observe(site_id="s-1", intent=и)
    план = м.plan(site_id="s-1", intent=и, observed=н)
    r1 = м.apply(site_id="s-1", plan=план, idempotency_key="a")
    r2 = м.apply(site_id="s-1", plan=план, idempotency_key="b")
    assert (мир.эффектов("create"), r1["external_id"] == r2["external_id"]) == (1, True)
    assert мир.вызовов >= 2


# --- 4. обрыв после эффекта --------------------------------------------------

def test_04_обрыв_после_эффекта_даёт_тот_же_идентификатор(обвязка):
    мир, м = обвязка["мир"], обвязка["провайдеры"]["analytics"]
    и = намерение()
    н = м.observe(site_id="s-1", intent=и)
    план = м.plan(site_id="s-1", intent=и, observed=н)
    мир.сломать(F.ПАДЕНИЕ_ПОСЛЕ_ЭФФЕКТА)
    with pytest.raises(F.Обрыв):
        м.apply(site_id="s-1", plan=план, idempotency_key="a")
    мир.починить()
    повтор = м.apply(site_id="s-1", plan=план, idempotency_key="a")
    assert мир.эффектов("create") == 1, "обрыв не должен рождать второй объект"
    assert повтор["created"] is False
    assert повтор["public_counter_id"] == 90000001


# --- 5. потерянный ответ -----------------------------------------------------

def test_05_потерянный_ответ_чинится_сверкой(обвязка):
    мир, м = обвязка["мир"], обвязка["провайдеры"]["analytics"]
    связи = обвязка["связи"]
    # Сайт обязан быть в реестре: сверка ищет объект по домену из реестра,
    # а не по домену, придуманному на месте.
    обвязка["реестр"].добавить("s-1", domain="shop.test")
    и = намерение()
    н = м.observe(site_id="s-1", intent=и)
    план = м.plan(site_id="s-1", intent=и, observed=н)
    ключ = "s-1:analytics:counter:потеря"
    связи.начать_действие(ключ, site_id="s-1", provider_type="analytics",
                          resource_kind="counter", operation="apply")
    мир.сломать(F.ПОТЕРЯ_ОТВЕТА)
    with pytest.raises(B.ProviderError) as ош:
        м.apply(site_id="s-1", plan=план, idempotency_key=ключ)
    assert ош.value.retryable is True
    мир.починить()

    п = _provisioner(обвязка)
    свод = п.сверить_незавершённые()
    assert свод["found_effect"] == 1, "эффект случился и обязан быть найден"
    assert мир.эффектов("create") == 1, "сверка не создаёт второй объект"


# --- 6. смена домена ---------------------------------------------------------

def test_06_смена_домена_сохраняет_site_id(обвязка):
    п, свод = _провести(обвязка, "s-1", "old.test", "k-1")
    обвязка["реестр"].сменить_домен("s-1", "new.test")
    связи_после = обвязка["связи"].по_сайту("s-1")
    assert {с.site_id for с in связи_после} == {"s-1"}
    assert свод["site_id"] == "s-1"
    # Ключ связи не содержит домена — иначе переезд рвал бы связь.
    assert all(с.site_id == "s-1" for с in связи_после)


# --- 7. adoption требует доказательства владения -----------------------------

def test_07_принятие_требует_доказательства(обвязка):
    dns = обвязка["провайдеры"]["dns"]
    мир = обвязка["мир"]
    # Чужая зона: метки владения нет.
    мир.поместить("dns", "dns:record_set:s-1",
                  {"owner": "кто-то-другой", "zone": "shop.test", "records": {}})
    н = dns.observe(site_id="s-1", intent=намерение())
    assert н.существует is True
    assert н.владение_подтверждено is False, "чужое нельзя принимать молча"

    мир.объекты["dns:record_set:s-1"]["records"]["_site-verify.shop.test"] = "s-1"
    н2 = dns.observe(site_id="s-1", intent=намерение())
    assert н2.владение_подтверждено is True


# --- 8. компенсация не трогает чужое -----------------------------------------

def test_08_компенсация_не_удаляет_существовавшее(обвязка):
    мир, м = обвязка["мир"], обвязка["провайдеры"]["analytics"]
    мир.поместить("analytics", "counter-777",
                  {"owner": None, "site": "shop.test",
                   "public_counter_id": 777, "data_state": "WAITING_DATA"})
    п, свод = _провести(обвязка)
    связь = обвязка["связи"].найти("s-1", "analytics", "counter")
    assert связь.external_id == "counter-777"
    assert связь.origin == "ADOPTED", "существовавшее принято, а не создано"

    with pytest.raises(B.ProviderError) as ош:
        м.удалить(external_id="counter-777", создан_набором=None,
                  changeset_id="какой-то-набор")
    assert ош.value.error_code == "COMPENSATION_REFUSED"
    assert "counter-777" in мир.объекты


# --- 9. вывод сайта ----------------------------------------------------------

def test_09_вывод_сайта_не_удаляет_объекты(обвязка):
    п, свод = _провести(обвязка)
    было = dict(обвязка["мир"].объекты)
    итог = п.вывести("s-1")
    assert итог["deleted"] == 0
    assert set(обвязка["мир"].объекты) == set(было), "объекты провайдера остались"
    assert all(с.lifecycle == "RETIRED" for с in обвязка["связи"].по_сайту("s-1"))
    assert обвязка["мир"].эффектов("delete") == 0


# --- 10. Templates получает только публичный идентификатор -------------------

def test_10_templates_получает_только_публичный_id(обвязка):
    п, свод = _провести(обвязка)
    шаг = next(ш for ш in свод["steps"] if ш["имя"] == "analytics")
    публичное = шаг["public"] or {}
    assert set(публичное) <= {"public_counter_id", "project_id"}
    сырое = str(свод)
    assert "credential" not in сырое or "credential_ref" in сырое
    assert "OAuth" not in сырое and "Bearer" not in сырое


# --- 11. установка тега идёт через контур ------------------------------------

def test_11_тег_ставится_через_changeset(обвязка):
    п, свод = _провести(обвязка)
    аналитика = next(ш for ш in свод["steps"] if ш["имя"] == "analytics")
    assert аналитика["changeset_id"], "изменение без набора недопустимо"
    набор = S.получить(обвязка["соед"], аналитика["changeset_id"])
    assert набор["status"] == M.SUCCEEDED
    assert набор["resource_type"] == "analytics.counter"
    # Одобрение выдано человеком, а не Provisioner'ом.
    assert набор["approval"]["approver_type"] == "HUMAN"

    # Установка тега — ОТДЕЛЬНЫЙ набор изменений. Успешное создание счётчика
    # ничего не говорит о том, что витрина его отдаёт.
    витрина_шаг = next(ш for ш in свод["steps"] if ш["имя"] == "template")
    набор_тега = S.получить(обвязка["соед"], витрина_шаг["changeset_id"])
    assert набор_тега["status"] == M.SUCCEEDED
    assert набор_тега["resource_type"] == "template.build"
    assert набор_тега["changeset_id"] != набор["changeset_id"]

    номер = обвязка["провайдеры"]["analytics"].мир.объекты[
        обвязка["связи"].найти("s-1", "analytics", "counter").external_id
    ]["public_counter_id"]
    assert обвязка["провайдеры"]["template"].тег_установлен(номер), (
        "счётчик создан, но витрина тег не отдаёт")


def test_11b_витрина_получает_только_публичный_номер(обвязка):
    п, свод = _провести(обвязка)
    витрина = обвязка["провайдеры"]["template"]
    ключ = f"template:counter_tag:s-1"
    объект = обвязка["мир"].объекты[ключ]
    assert set(объект) <= {"owner", "counter_id", "placement", "_provider"}
    assert isinstance(объект["counter_id"], int)


def test_11c_без_счётчика_тег_не_ставится(обвязка):
    """Пустой тег выглядел бы установленным — это хуже отсутствия."""
    витрина = обвязка["провайдеры"]["template"]
    витрина.установить_счётчик(None)
    with pytest.raises(B.ProviderError) as ош:
        витрина.plan(site_id="s-1", intent=намерение(), observed=None)
    assert ош.value.error_code == "COUNTER_ID_REQUIRED"


# --- 12–13. роль Qwen --------------------------------------------------------

def test_12_qwen_создаёт_намерение_и_черновик():
    к = QwenКонтракт(версия_модели="2.5", версия_профиля="seo-v3")
    и = к.создать_намерение({
        "canonical_domain": "shop.test", "template_family": "yummy",
        "template_profile": "catalog-search", "language": "ru", "region": "RU",
        "correlation_id": "c-1", "idempotency_key": "k-1"})
    assert и.requested_by == "service:qwen"
    ч = к.черновик(site_id="s-1", resource_id="page:home", locale="ru",
                   correlation_id="c-1", created_at="2026-09-12T00:00:00Z",
                   title="Заголовок", description="Описание", h1="H1",
                   body="Текст страницы")
    д = ч.в_словарь()
    for поле in ("site_id", "page_resource_id", "locale", "model",
                 "model_version", "prompt_profile_version", "content_hash",
                 "created_at", "correlation_id", "status"):
        assert д.get(поле), f"в черновике нет {поле}"
    assert д["status"] == "DRAFT"
    assert д["content_hash"].startswith("sha256:")


@pytest.mark.parametrize("метод,код", [
    ("approve", "MODEL_ACTION_DENIED"), ("apply", "MODEL_ACTION_DENIED"),
    ("rollback", "MODEL_ACTION_DENIED"), ("read_secret", "SECRET_ACCESS_DENIED"),
    ("call_provider", "PROVIDER_ACCESS_DENIED"),
    ("change_policy", "POLICY_CHANGE_DENIED"), ("run", "EXECUTION_DENIED")])
def test_13_qwen_получает_отказ(метод, код):
    к = QwenКонтракт()
    with pytest.raises(QwenDenied) as ош:
        getattr(к, метод)()
    assert ош.value.error_code == код


def test_13b_qwen_не_вправе_выбрать_неутверждённый_профиль():
    к = QwenКонтракт()
    with pytest.raises(QwenDenied) as ош:
        к.создать_намерение({
            "canonical_domain": "shop.test", "template_family": "yummy",
            "template_profile": "придуманный", "language": "ru", "region": "RU",
            "correlation_id": "c", "idempotency_key": "k"})
    assert ош.value.error_code == "TEMPLATE_PROFILE_NOT_APPROVED"


# --- 16. недействительный credential ----------------------------------------

def test_16_недействительный_credential_не_ретраится(обвязка):
    обвязка["мир"].сломать(F.НЕДЕЙСТВИТЕЛЬНЫЙ_CREDENTIAL)
    обвязка["реестр"].добавить("s-1", domain="shop.test")
    п = _provisioner(обвязка)
    свод = п.провести(намерение(), "s-1")
    dns = next(ш for ш in свод["steps"] if ш["имя"] == "dns")
    assert dns["отказ"] == "CREDENTIAL_INVALID"
    assert обвязка["мир"].эффектов("create") == 0
    assert свод["readiness"]["stage"] in ("REQUESTED", "INFRA_PLANNED", "FAILED")


# --- 17. таймаут, квота и отложенная согласованность -------------------------

def test_17_таймаут_не_создаёт_дублей(обвязка):
    мир, м = обвязка["мир"], обвязка["провайдеры"]["analytics"]
    и = намерение()
    н = м.observe(site_id="s-1", intent=и)
    план = м.plan(site_id="s-1", intent=и, observed=н)
    мир.сломать(F.ТАЙМАУТ)
    for _ in range(3):
        with pytest.raises(B.ProviderError):
            м.apply(site_id="s-1", plan=план, idempotency_key="a")
    мир.починить()
    м.apply(site_id="s-1", plan=план, idempotency_key="a")
    м.apply(site_id="s-1", plan=план, idempotency_key="a")
    assert мир.эффектов("create") == 1


def test_17b_квота_размыкает_выключатель(обвязка):
    мир = обвязка["мир"]
    мир.предел_стоимости = 50           # меньше стоимости одного создания
    tv = обвязка["провайдеры"]["seo_rank"]
    и = намерение()
    н = tv.observe(site_id="s-1", intent=и)
    план = tv.plan(site_id="s-1", intent=и, observed=н)
    with pytest.raises(B.ProviderError) as ош:
        tv.apply(site_id="s-1", plan=план, idempotency_key="a")
    assert ош.value.error_code == "QUOTA_EXCEEDED"
    assert ош.value.retryable is False, "исчерпанную квоту не ретраят"
    assert мир.эффектов("create") == 0


def test_17c_данные_метрики_ждут_а_не_крутят_onboarding(обвязка):
    п, свод = _провести(обвязка)
    assert "analytics.data:WAITING_DATA" in свод["readiness"]["waiting"]
    assert свод["readiness"]["stage"] != "FAILED"


# --- 18. небезопасные входы --------------------------------------------------

@pytest.mark.parametrize("тип,имя,значение,код", [
    ("NS", "@", "ns1.example", "RECORD_TYPE_PROTECTED"),
    ("MX", "@", "mail.example", "RECORD_TYPE_PROTECTED"),
    ("TXT", "_dmarc", "v=DMARC1", "TXT_PROTECTED"),
    ("A", "@", "1.2.3.4`id`", "VALUE_REJECTED"),
    ("SRV", "@", "x", "RECORD_TYPE_UNSUPPORTED"),
])
def test_18_защищённые_записи(тип, имя, значение, код):
    with pytest.raises(B.ProviderError) as ош:
        B.проверить_запись(тип, имя, значение)
    assert ош.value.error_code == код


@pytest.mark.parametrize("адрес,код", [
    ("http://api-metrika.yandex.net/x", "URL_INSECURE"),
    ("https://evil.test/x", "EGRESS_DENIED"),
    ("file:///etc/passwd", "URL_REJECTED"),
    ("https://localhost/x", "EGRESS_DENIED"),
])
def test_18b_небезопасные_адреса(адрес, код):
    with pytest.raises(B.ProviderError) as ош:
        B.проверить_адрес(адрес, frozenset({"api-metrika.yandex.net"}))
    assert ош.value.error_code == код


def test_18c_внутренний_адрес_блокируется_после_разрешения():
    """Имя в allowlist, но резолвится внутрь — запрос не выполняется."""
    with pytest.raises(B.ProviderError) as ош:
        B.проверить_адрес("https://localhost/x", frozenset({"localhost"}))
    assert ош.value.error_code == "SSRF_BLOCKED"


def test_18d_домен_намерения_разбирается_как_данные():
    from factory.site_engine.provisioner.intent import IntentError, OnboardingIntent
    for плохой in ("../../etc", "a b.test", "http://x.test", "x.test/../y"):
        with pytest.raises(IntentError):
            OnboardingIntent.разобрать({
                "requested_by": "q", "canonical_domain": плохой,
                "template_family": "y", "template_profile": "c",
                "language": "ru", "region": "RU", "correlation_id": "c",
                "idempotency_key": "k"})


# --- 19. две чистые серии ----------------------------------------------------

def test_19_две_серии_дают_одинаковый_итог(обвязка):
    п, первый = _провести(обвязка)
    эффектов_после_первой = обвязка["мир"].эффектов("create")
    второй = п.провести(намерение("shop.test", "k-1"), "s-1")
    assert обвязка["мир"].эффектов("create") == эффектов_после_первой
    assert первый["readiness"]["stage"] == второй["readiness"]["stage"]
    assert первый["intent_fingerprint"] == второй["intent_fingerprint"]


# --- готовность --------------------------------------------------------------

def test_20_готовность_вычисляется_а_не_хранится(обвязка):
    п, свод = _провести(обвязка)
    г = свод["readiness"]
    assert г["stage"] in R.ПОРЯДОК
    assert "DNS_READY" in г["reached"] and "TLS_READY" in г["reached"]
    # Жизненный цикл реестра не переопределяется.
    assert г["details"]["lifecycle_state"] == "DRAFT"


# --- 10. наблюдаемость -------------------------------------------------------

def test_21_показатели_собираются_из_состояния(обвязка):
    from factory.site_engine.provisioner import health as H
    п, свод = _провести(обвязка)
    м = H.собрать(связи=обвязка["связи"], соед_наборов=обвязка["соед"])
    assert м.ready is True
    assert м.links_total == 5 and м.onboarding_sites == 1
    assert м.duplicate_effects == 0, "дубль внешнего объекта — отказ, а не метрика"
    assert м.dlq_depth == 0
    assert м.changesets_failed == 0 and м.stuck_changesets == []
    assert м.provider_error_rate == 0.0
    assert м.stage_durations_sec, "длительность стадий обязана считаться"


def test_22_дубль_эффекта_поднимает_тревогу(обвязка):
    from factory.site_engine.provisioner import health as H
    связи = обвязка["связи"]
    for ключ in ("a", "b"):
        связи.начать_действие(ключ, site_id="s-1", provider_type="analytics",
                              resource_kind="counter", operation="apply")
        связи.завершить_действие(ключ, состояние="SUCCEEDED",
                                 external_id="counter-1")
    м = H.собрать(связи=связи, соед_наборов=обвязка["соед"])
    assert м.duplicate_effects == 1
    assert any(а["code"] == "DUPLICATE_PROVIDER_EFFECT" and а["severity"] == "P0"
               for а in м.alerts)
    assert м.ready is False


def test_23_застрявший_набор_обнаружен(обвязка):
    """Набор, которого никто не одобрил, действительно висит.

    Подменить статус напрямую нельзя: хранилище не даёт менять его мимо
    машины переходов — и правильно делает. Поэтому застревание создаётся
    по-настоящему: предложение без одобряющего остаётся ждать вечно.
    """
    import datetime as d
    from factory.site_engine.provisioner import health as H
    обвязка["реестр"].добавить("s-1", domain="shop.test")
    п = _provisioner(обвязка, одобряющий=None)
    свод = п.провести(намерение(), "s-1")
    assert свод["steps"][0]["отказ"] == "APPROVAL_REQUIRED"

    сейчас = H.собрать(связи=обвязка["связи"], соед_наборов=обвязка["соед"])
    assert сейчас.stuck_changesets == [], "только что созданный не застрял"

    поздно = d.datetime.now(d.timezone.utc) + d.timedelta(hours=2)
    м = H.собрать(связи=обвязка["связи"], соед_наборов=обвязка["соед"],
                  сейчас=поздно)
    assert м.stuck_changesets, "набор без движения обязан быть замечен"
    assert any(а["code"] == "CHANGESET_STUCK" for а in м.alerts)
    assert м.ready is False
