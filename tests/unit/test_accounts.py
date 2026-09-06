"""REQ-ACCOUNTS: учётные записи зрителей.

Отдельный контур от операторского: другое хранилище, другие cookie, другие
права. Один общий список «пользователей» рано или поздно приводит к тому, что
зритель оказывается с правом оператора — не по злому умыслу, а потому что
где-то забыли проверить, из какого он списка.

Проверяются свойства, а не наличие функций: ответы не различают существующий
адрес и несуществующий, токены одноразовы и истекают, смена пароля гасит
сессии, витрины изолированы.
"""

from __future__ import annotations

import pytest

from factory.site_engine.accounts import (
    CONSENT_VERSION,
    CONTRACT_VERSION,
    RESEND_LIMIT,
    AccountDirectory,
    AccountError,
    AccountState,
)
from factory.site_engine.mail import CaptureMailer, MailError, Message, SmtpMailer

ПАРОЛЬ = "пароль-зрителя-1"
ДРУГОЙ = "другой-пароль-зрителя"


@pytest.fixture
def почта():
    return CaptureMailer()


@pytest.fixture
def каталог(tmp_path, почта):
    return AccountDirectory(tmp_path, mailer=почта)


def токен_из(почта, purpose="verify"):
    письмо = почта.last(purpose)
    assert письмо is not None, f"письма {purpose} не было"
    return письмо.body.split("token=")[1].split()[0]


def зарегистрировать(каталог, почта, *, site="s1", email="u@x.com"):
    каталог.register(site_id=site, email=email, password=ПАРОЛЬ, consent=True)
    return каталог.verify(site_id=site, token=токен_из(почта))


# --------------------------------------------------------------------------
# Доставка
# --------------------------------------------------------------------------
class TestДоставка:
    def test_складывающий_адаптер_не_годен_для_production(self):
        assert CaptureMailer().production_ready is False

    def test_smtp_без_реквизитов_отказывает_вслух(self):
        """Молчаливая потеря письма хуже отказа: человек ждёт того, чего нет."""
        with pytest.raises(MailError, match="не настроен"):
            SmtpMailer().send(Message(to="a@x", subject="s", body="b"))

    def test_выбор_адаптера_по_окружению(self):
        from factory.site_engine.mail import mailer_from_env

        assert mailer_from_env({}).production_ready is False
        настроенный = mailer_from_env(
            {
                "SITE_ENGINE_SMTP_HOST": "h",
                "SITE_ENGINE_SMTP_PORT": "25",
                "SITE_ENGINE_SMTP_SENDER": "s@x",
            }
        )
        assert настроенный.production_ready is True


# --------------------------------------------------------------------------
# Регистрация и подтверждение
# --------------------------------------------------------------------------
class TestРегистрация:
    def test_путь_целиком(self, каталог, почта):
        итог = каталог.register(
            site_id="s1", email="U@X.com", password=ПАРОЛЬ, consent=True, display_name="Зритель"
        )
        assert итог["state"] == "PENDING_VERIFICATION"
        запись = каталог.verify(site_id="s1", token=токен_из(почта))
        assert запись.state is AccountState.ACTIVE and запись.verified_at
        assert запись.email == "u@x.com", "адрес приводится к одному виду"

    def test_без_согласия_нельзя(self, каталог):
        with pytest.raises(AccountError, match="согласие"):
            каталог.register(site_id="s1", email="u@x.com", password=ПАРОЛЬ, consent=False)

    def test_согласие_хранится_с_версией(self, каталог, почта):
        """«Согласился» без указания, с чем именно, ничего не значит."""
        запись = зарегистрировать(каталог, почта)
        assert запись.consent_version == CONSENT_VERSION and запись.consent_at

    def test_короткий_пароль_отклонён_до_записи(self, каталог):
        with pytest.raises(AccountError):
            каталог.register(site_id="s1", email="u@x.com", password="коротко", consent=True)
        assert каталог.list()["totalAll"] == 0

    def test_занятый_адрес_отвечает_так_же(self, каталог, почта):
        """Разный ответ превратил бы форму в перебор адресов."""
        первый = каталог.register(site_id="s1", email="u@x.com", password=ПАРОЛЬ, consent=True)
        второй = каталог.register(site_id="s1", email="u@x.com", password=ДРУГОЙ, consent=True)
        assert первый == второй

    def test_занятому_адресу_уходит_другое_письмо(self, каталог, почта):
        каталог.register(site_id="s1", email="u@x.com", password=ПАРОЛЬ, consent=True)
        каталог.register(site_id="s1", email="u@x.com", password=ДРУГОЙ, consent=True)
        assert почта.last("exists") is not None
        assert "token=" not in почта.last("exists").body

    def test_пароль_занятой_записи_не_подменяется(self, каталог, почта):
        """Иначе регистрация чужого адреса меняла бы чужой пароль."""
        запись = зарегистрировать(каталог, почта)
        каталог.register(site_id="s1", email="u@x.com", password=ДРУГОЙ, consent=True)
        assert каталог.authenticate(site_id="s1", email="u@x.com", password=ПАРОЛЬ)
        with pytest.raises(AccountError):
            каталог.authenticate(site_id="s1", email="u@x.com", password=ДРУГОЙ)
        assert каталог.get(запись.account_id).state is AccountState.ACTIVE

    def test_токен_подтверждения_одноразов(self, каталог, почта):
        каталог.register(site_id="s1", email="u@x.com", password=ПАРОЛЬ, consent=True)
        токен = токен_из(почта)
        каталог.verify(site_id="s1", token=токен)
        with pytest.raises(AccountError, match="не подходит"):
            каталог.verify(site_id="s1", token=токен)

    def test_токен_подтверждения_истекает(self, tmp_path, почта):
        часы = [1000.0]
        к = AccountDirectory(tmp_path, mailer=почта, now=lambda: часы[0])
        к.register(site_id="s1", email="u@x.com", password=ПАРОЛЬ, consent=True)
        часы[0] += 25 * 60 * 60
        with pytest.raises(AccountError, match="истёк"):
            к.verify(site_id="s1", token=токен_из(почта))

    def test_чужой_токен_не_подходит(self, каталог):
        with pytest.raises(AccountError, match="не подходит"):
            каталог.verify(site_id="s1", token="подобранный")

    def test_токен_другой_витрины_не_подходит(self, каталог, почта):
        каталог.register(site_id="s1", email="u@x.com", password=ПАРОЛЬ, consent=True)
        with pytest.raises(AccountError, match="не подходит"):
            каталог.verify(site_id="s2", token=токен_из(почта))

    def test_повторная_отправка_ограничена(self, каталог, почта):
        каталог.register(site_id="s1", email="u@x.com", password=ПАРОЛЬ, consent=True)
        for _ in range(RESEND_LIMIT + 3):
            каталог.resend_verification(site_id="s1", email="u@x.com")
        писем = sum(1 for m in почта.sent if m.purpose == "verify")
        assert писем <= RESEND_LIMIT + 1, f"писем {писем}: ограничение не работает"

    def test_повторная_отправка_несуществующему_отвечает_так_же(self, каталог):
        assert каталог.resend_verification(
            site_id="s1", email="нет@x.com"
        ) == каталог.resend_verification(site_id="s1", email="совсем-не-адрес")

    def test_токен_хранится_только_хэшем(self, каталог, почта, tmp_path):
        каталог.register(site_id="s1", email="u@x.com", password=ПАРОЛЬ, consent=True)
        токен = токен_из(почта)
        весь = "".join(
            ф.read_text(encoding="utf-8") for ф in (tmp_path / "var/state/accounts").rglob("*.json")
        )
        assert токен not in весь


# --------------------------------------------------------------------------
# Изоляция витрин
# --------------------------------------------------------------------------
class TestИзоляция:
    def test_один_адрес_на_двух_витринах_это_две_записи(self, каталог, почта):
        зарегистрировать(каталог, почта, site="s1")
        зарегистрировать(каталог, почта, site="s2")
        assert каталог.list()["totalAll"] == 2
        assert (
            каталог.by_email("s1", "u@x.com").account_id
            != каталог.by_email("s2", "u@x.com").account_id
        )

    def test_вход_на_чужую_витрину_отклонён(self, каталог, почта):
        зарегистрировать(каталог, почта, site="s1")
        with pytest.raises(AccountError):
            каталог.authenticate(site_id="s2", email="u@x.com", password=ПАРОЛЬ)

    def test_сессия_не_действует_на_чужой_витрине(self, каталог, почта):
        запись = зарегистрировать(каталог, почта, site="s1")
        каталог.register_session(sid="s", account_id=запись.account_id, site_id="s1")
        assert каталог.session_valid("s", site_id="s1") is not None
        assert каталог.session_valid("s", site_id="s2") is None


# --------------------------------------------------------------------------
# Вход, восстановление, сессии
# --------------------------------------------------------------------------
class TestВходИВосстановление:
    def test_неподтверждённый_не_входит(self, каталог):
        каталог.register(site_id="s1", email="u@x.com", password=ПАРОЛЬ, consent=True)
        with pytest.raises(AccountError):
            каталог.authenticate(site_id="s1", email="u@x.com", password=ПАРОЛЬ)

    def test_отказ_не_различает_причину(self, каталог, почта):
        зарегистрировать(каталог, почта)
        сообщения = set()
        for адрес, пароль in (("u@x.com", "неверный"), ("нет@x.com", ПАРОЛЬ), ("не-адрес", ПАРОЛЬ)):
            with pytest.raises(AccountError) as e:
                каталог.authenticate(site_id="s1", email=адрес, password=пароль)
            сообщения.add(str(e.value))
        assert len(сообщения) == 1

    def test_блокировка_после_неудач(self, каталог, почта):
        зарегистрировать(каталог, почта)
        for _ in range(5):
            with pytest.raises(AccountError):
                каталог.authenticate(site_id="s1", email="u@x.com", password="нет")
        with pytest.raises(AccountError):
            каталог.authenticate(site_id="s1", email="u@x.com", password=ПАРОЛЬ)

    def test_восстановление_меняет_пароль_и_гасит_сессии(self, каталог, почта):
        запись = зарегистрировать(каталог, почта)
        каталог.register_session(sid="s", account_id=запись.account_id, site_id="s1")
        каталог.request_reset(site_id="s1", email="u@x.com")
        каталог.reset_password(site_id="s1", token=токен_из(почта, "reset"), password=ДРУГОЙ)
        assert каталог.session_valid("s", site_id="s1") is None
        assert каталог.authenticate(site_id="s1", email="u@x.com", password=ДРУГОЙ)

    def test_токен_восстановления_одноразов(self, каталог, почта):
        зарегистрировать(каталог, почта)
        каталог.request_reset(site_id="s1", email="u@x.com")
        токен = токен_из(почта, "reset")
        каталог.reset_password(site_id="s1", token=токен, password=ДРУГОЙ)
        with pytest.raises(AccountError, match="не подходит"):
            каталог.reset_password(site_id="s1", token=токен, password="третий-пароль-1")

    def test_запрос_восстановления_несуществующему_отвечает_так_же(self, каталог, почта):
        зарегистрировать(каталог, почта)
        assert каталог.request_reset(site_id="s1", email="u@x.com") == каталог.request_reset(
            site_id="s1", email="нет@x.com"
        )

    def test_смена_пароля_требует_текущего(self, каталог, почта):
        запись = зарегистрировать(каталог, почта)
        with pytest.raises(AccountError, match="текущий пароль"):
            каталог.change_password(запись.account_id, current="нет", new=ДРУГОЙ)

    def test_смена_пароля_гасит_сессии(self, каталог, почта):
        запись = зарегистрировать(каталог, почта)
        каталог.register_session(sid="s", account_id=запись.account_id, site_id="s1")
        каталог.change_password(запись.account_id, current=ПАРОЛЬ, new=ДРУГОЙ)
        assert каталог.session_valid("s", site_id="s1") is None

    def test_чужую_сессию_отозвать_нельзя(self, каталог, почта):
        первый = зарегистрировать(каталог, почта, email="a@x.com")
        второй = зарегистрировать(каталог, почта, email="b@x.com")
        каталог.register_session(sid="sa", account_id=первый.account_id, site_id="s1")
        чужая = каталог.list_sessions(account_id=первый.account_id)[0]["sessionId"]
        assert каталог.revoke_session(чужая, account_id=второй.account_id) is False
        assert каталог.session_valid("sa", site_id="s1") is not None

    def test_свою_сессию_отозвать_можно(self, каталог, почта):
        запись = зарегистрировать(каталог, почта)
        каталог.register_session(sid="sa", account_id=запись.account_id, site_id="s1")
        своя = каталог.list_sessions(account_id=запись.account_id)[0]["sessionId"]
        assert каталог.revoke_session(своя, account_id=запись.account_id)
        assert каталог.session_valid("sa", site_id="s1") is None


# --------------------------------------------------------------------------
# Профиль, выгрузка, удаление
# --------------------------------------------------------------------------
class TestЖизненныйЦикл:
    def test_профиль_обновляется(self, каталог, почта):
        запись = зарегистрировать(каталог, почта)
        assert (
            каталог.update_profile(запись.account_id, display_name="Новое имя").display_name
            == "Новое имя"
        )

    def test_выгрузка_не_содержит_хэша_и_токенов(self, каталог, почта):
        запись = зарегистрировать(каталог, почта)
        выгрузка = каталог.export(запись.account_id)
        текст = str(выгрузка)
        assert "scrypt" not in текст and "verifyHash" not in текст

    def test_удаление_освобождает_адрес_и_гасит_сессии(self, каталог, почта):
        запись = зарегистрировать(каталог, почта)
        каталог.register_session(sid="s", account_id=запись.account_id, site_id="s1")
        каталог.delete(запись.account_id)
        мёртвая = каталог.get(запись.account_id)
        assert мёртвая.state is AccountState.DELETED
        assert мёртвая.password is None and "@invalid" in мёртвая.email
        assert каталог.session_valid("s", site_id="s1") is None

    def test_после_удаления_адрес_можно_зарегистрировать_снова(self, каталог, почта):
        запись = зарегистрировать(каталог, почта)
        каталог.delete(запись.account_id)
        каталог.register(site_id="s1", email="u@x.com", password=ДРУГОЙ, consent=True)
        новая = каталог.verify(site_id="s1", token=токен_из(почта))
        assert новая.state is AccountState.ACTIVE

    def test_заблокированный_не_входит_и_теряет_сессии(self, каталог, почта):
        запись = зарегистрировать(каталог, почта)
        каталог.register_session(sid="s", account_id=запись.account_id, site_id="s1")
        каталог.block(запись.account_id, reason="нарушение")
        assert каталог.session_valid("s", site_id="s1") is None
        with pytest.raises(AccountError):
            каталог.authenticate(site_id="s1", email="u@x.com", password=ПАРОЛЬ)

    def test_список_не_отдаёт_хэш_пароля(self, каталог, почта):
        зарегистрировать(каталог, почта)
        текст = str(каталог.list())
        assert "scrypt" not in текст and "salt" not in текст
        assert каталог.list()["contractVersion"] == CONTRACT_VERSION

    def test_негодный_идентификатор_не_выходит_за_каталог(self, каталог):
        with pytest.raises(AccountError, match="негодный идентификатор"):
            каталог.get("../../etc/passwd")


class TestКонтурыНеСмешаны:
    """Операторы и зрители не должны пересекаться нигде.

    Общий список «пользователей» рано или поздно приводит к тому, что зритель
    оказывается с правом оператора — не по злому умыслу, а потому что где-то
    забыли проверить, из какого он списка.
    """

    def test_хранилища_разные(self, tmp_path, почта):
        from factory.site_engine.operators import OperatorDirectory

        AccountDirectory(tmp_path, mailer=почта)
        OperatorDirectory(tmp_path)
        assert (tmp_path / "var/state/accounts").exists()
        assert (tmp_path / "var/state/operators").exists()
        assert (tmp_path / "var/state/accounts") != (tmp_path / "var/state/operators")

    def test_оператор_не_виден_как_зритель(self, tmp_path, почта):
        from factory.site_engine.operators import OperatorDirectory

        операторы = OperatorDirectory(tmp_path)
        _, секрет = операторы.invite(
            email="op@x.com", roles=["admin"], created_by="boot", super_admin=True
        )
        операторы.accept_invite(secret=секрет, password="пароль-оператора-1")
        зрители = AccountDirectory(tmp_path, mailer=почта)
        assert зрители.by_email("s1", "op@x.com") is None
        assert зрители.list()["totalAll"] == 0

    def test_зритель_не_виден_как_оператор(self, tmp_path, почта):
        from factory.site_engine.operators import OperatorDirectory

        зрители = AccountDirectory(tmp_path, mailer=почта)
        зарегистрировать(зрители, почта, email="v@x.com")
        assert OperatorDirectory(tmp_path).by_email("v@x.com") is None

    def test_у_зрителя_нет_областей_доступа(self, каталог, почта):
        """Права оператора выражаются областями; у зрителя их нет вовсе."""
        запись = зарегистрировать(каталог, почта)
        assert "scopes" not in запись.as_dict()
        assert "roles" not in запись.as_dict()

    def test_ошибка_операторского_контура_не_всплывает_в_публичном(self, каталог):
        """Иначе обработчик обязан знать про чужой контур."""
        from factory.site_engine.operators import OperatorError

        with pytest.raises(AccountError):
            каталог.register(site_id="s1", email="u@x.com", password="мало", consent=True)
        try:
            каталог.register(site_id="s1", email="u@x.com", password="мало", consent=True)
        except AccountError as ошибка:
            assert not isinstance(ошибка, OperatorError)

    def test_сессии_разных_контуров_не_пересекаются(self, tmp_path, почта):
        from factory.site_engine.operators import OperatorDirectory

        операторы = OperatorDirectory(tmp_path)
        _, секрет = операторы.invite(
            email="op@x.com", roles=["admin"], created_by="boot", super_admin=True
        )
        оператор = операторы.accept_invite(secret=секрет, password="пароль-оператора-1")
        операторы.register_session(sid="общий", operator_id=оператор.operator_id)

        зрители = AccountDirectory(tmp_path, mailer=почта)
        запись = зарегистрировать(зрители, почта)
        # Один и тот же идентификатор cookie не должен давать доступ в обоих.
        assert зрители.session_valid("общий", site_id="s1") is None
        зрители.register_session(sid="зритель", account_id=запись.account_id, site_id="s1")
        assert операторы.session_valid("зритель") is None
