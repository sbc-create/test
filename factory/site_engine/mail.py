"""Отправка писем: интерфейс и две реализации.

Публичная регистрация без доставки писем — это регистрация без подтверждения
адреса и без восстановления пароля, то есть учётная запись, которую нельзя ни
подтвердить, ни вернуть. Поэтому доставка вынесена в сменный адаптер, а не
вшита: интерфейс существует и проверяется тестами даже тогда, когда внешнего
поставщика нет.

Два адаптера намеренно:

* `CaptureMailer` — складывает письма в память или в файл. Только для тестов и
  локальной разработки. Он **не** является поставщиком: с ним публичная
  регистрация в production не включается;
* `SmtpMailer` — настоящая доставка. Требует настроенных реквизитов, которых
  сейчас нет; при их отсутствии он отказывается работать вслух, а не молча
  теряет письма.

Молчаливая потеря письма хуже отказа: пользователь ждёт подтверждения,
которого не будет, и решает, что сломана регистрация.
"""

from __future__ import annotations

import dataclasses
import datetime as dt
import json
import os
from pathlib import Path
from typing import Any, Protocol

CONTRACT_VERSION = "mail-adapter/1.0.0"


class MailError(RuntimeError):
    """Письмо не отправлено. Молчать об этом нельзя."""


@dataclasses.dataclass(frozen=True)
class Message:
    to: str
    subject: str
    body: str
    #: Назначение письма. Нужно для ограничения частоты и для отчётов:
    #: «сколько подтверждений не дошло» и «сколько восстановлений» — разные
    #: вопросы, и по одному счётчику на оба не ответить.
    purpose: str = "generic"

    def as_dict(self) -> dict[str, Any]:
        return {
            "to": self.to,
            "subject": self.subject,
            "purpose": self.purpose,
            "bodyLength": len(self.body),
        }


class Mailer(Protocol):
    """Контракт доставки. Реализация обязана либо отправить, либо отказать."""

    name: str
    production_ready: bool

    def send(self, message: Message) -> dict[str, Any]: ...


class CaptureMailer:
    """Складывает письма вместо отправки. Только тесты и локальная разработка.

    `production_ready = False` — это не свойство настройки, а свойство самого
    адаптера. Признак читается перед включением публичной регистрации, и
    подменить его настройкой нельзя.
    """

    name = "capture"
    production_ready = False

    def __init__(self, sink: Path | str | None = None) -> None:
        self.sent: list[Message] = []
        self.sink = Path(sink) if sink else None
        if self.sink:
            self.sink.mkdir(parents=True, exist_ok=True)

    def send(self, message: Message) -> dict[str, Any]:
        self.sent.append(message)
        if self.sink:
            имя = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%S%f")
            путь = self.sink / f"{имя}-{message.purpose}.json"
            врем = путь.with_name(f".{путь.name}.tmp")
            врем.write_text(
                json.dumps(
                    {**message.as_dict(), "body": message.body}, ensure_ascii=False, indent=1
                ),
                encoding="utf-8",
            )
            os.replace(врем, путь)
        return {
            "delivered": True,
            "adapter": self.name,
            "productionReady": False,
            "contractVersion": CONTRACT_VERSION,
        }

    def last(self, purpose: str = "") -> Message | None:
        for сообщение in reversed(self.sent):
            if not purpose or сообщение.purpose == purpose:
                return сообщение
        return None


class SmtpMailer:
    """Настоящая доставка. Без реквизитов отказывается работать вслух."""

    name = "smtp"
    production_ready = True

    def __init__(
        self,
        *,
        host: str = "",
        port: int = 0,
        username: str = "",
        password: str = "",
        sender: str = "",
        starttls: bool = True,
        timeout: float = 10.0,
    ) -> None:
        self.host, self.port = host, port
        self.username, self.password = username, password
        self.sender, self.starttls, self.timeout = sender, starttls, timeout

    @property
    def configured(self) -> bool:
        return bool(self.host and self.port and self.sender)

    @classmethod
    def from_env(cls, env: dict[str, str] | None = None) -> SmtpMailer:
        env = env if env is not None else os.environ
        return cls(
            host=env.get("SITE_ENGINE_SMTP_HOST", ""),
            port=int(env.get("SITE_ENGINE_SMTP_PORT", "0") or 0),
            username=env.get("SITE_ENGINE_SMTP_USER", ""),
            password=env.get("SITE_ENGINE_SMTP_PASSWORD", ""),
            sender=env.get("SITE_ENGINE_SMTP_SENDER", ""),
            starttls=str(env.get("SITE_ENGINE_SMTP_STARTTLS", "1")).lower()
            not in {"0", "false", "no"},
        )

    def send(self, message: Message) -> dict[str, Any]:
        if not self.configured:
            raise MailError(
                "поставщик доставки не настроен: нужны SITE_ENGINE_SMTP_HOST, "
                "SITE_ENGINE_SMTP_PORT и SITE_ENGINE_SMTP_SENDER. Письмо НЕ "
                "отправлено — молчаливая потеря хуже отказа"
            )
        import smtplib
        from email.message import EmailMessage

        письмо = EmailMessage()
        письмо["From"] = self.sender
        письмо["To"] = message.to
        письмо["Subject"] = message.subject
        письмо.set_content(message.body)
        try:
            with smtplib.SMTP(self.host, self.port, timeout=self.timeout) as соединение:
                if self.starttls:
                    соединение.starttls()
                if self.username:
                    соединение.login(self.username, self.password)
                соединение.send_message(письмо)
        except Exception as ошибка:  # noqa: BLE001
            # Наружу уходит факт и класс ошибки. Реквизиты и содержимое письма
            # в текст не попадают: журнал читают шире, чем почтовый ящик.
            raise MailError(f"доставка не удалась: {type(ошибка).__name__}") from ошибка
        return {
            "delivered": True,
            "adapter": self.name,
            "productionReady": True,
            "contractVersion": CONTRACT_VERSION,
        }


def mailer_from_env(
    env: dict[str, str] | None = None, *, capture_sink: Path | None = None
) -> Mailer:
    """Настоящий адаптер, если он настроен; иначе — складывающий.

    Подмена молчаливой быть не может: у складывающего `production_ready`
    равен False, и включение публичной регистрации это проверяет.
    """
    env = env if env is not None else os.environ
    smtp = SmtpMailer.from_env(env)
    if smtp.configured:
        return smtp
    # Каталог для складывания задаётся отдельно и только ради проверок:
    # письма на диске — это ссылки подтверждения на диске, и в production
    # такого каталога быть не должно.
    сток = capture_sink or env.get("SITE_ENGINE_MAIL_CAPTURE_DIR") or None
    return CaptureMailer(сток)
