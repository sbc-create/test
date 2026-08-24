"""Точка подключения плеера. Серверная и единственная.

Пока `CDNVIDEOHUB_API_TOKEN` и `CDNVIDEOHUB_PUBLISHER_ID` не переданы, на месте
плеера стоит заглушка с диагностическим статусом. Это не «плеер работает» и не
попытка обойти отсутствие данных: заглушка сообщает, чего именно не хватает, и
никогда не засчитывается за пройденную проверку контракта плеера.

Устройство подобрано так, чтобы включение настоящего плеера не потребовало
переделки интерфейса: место в разметке, размеры, подпись и обрамление уже
занимает `render()`, меняется только его внутренность. Publisher ID при этом
остаётся на сервере — он подставляется в разметку в момент ответа и не попадает
ни в переменную окружения с префиксом `NEXT_PUBLIC_`, ни в JS-бандл, ни в
конфигурацию, которую отдаёт клиент.
"""

from __future__ import annotations

import os
from dataclasses import dataclass

#: Статус, с которым живёт заглушка. Совпадает с blueprint и с отчётом сборки.
BLOCKED_STATUS = "BLOCKED_INPUT_CDNVIDEOHUB_CREDENTIALS"

#: Имена секретов. Значения не читаются и не печатаются — проверяется наличие.
TOKEN_ENV = "CDNVIDEOHUB_API_TOKEN"
PUBLISHER_ENV = "CDNVIDEOHUB_PUBLISHER_ID"

#: Префикс, который выносит переменную в клиентский бандл. Здесь он запрещён:
#: Publisher ID — серверное значение, и публичного варианта у него не бывает.
FORBIDDEN_PUBLIC_PREFIX = "NEXT_PUBLIC_"
FORBIDDEN_PUBLIC_ENV = f"{FORBIDDEN_PUBLIC_PREFIX}{PUBLISHER_ENV}"


class PublicPublisherIdError(RuntimeError):
    """Publisher ID попытались вынести в клиентское окружение."""


@dataclass(frozen=True)
class PlayerState:
    available: bool
    status: str
    message: str

    @property
    def placeholder(self) -> bool:
        return not self.available


def assert_no_public_publisher_id(environ: dict | None = None) -> None:
    """Публичная переменная с Publisher ID — отказ сборки, а не предупреждение.

    Проверка сознательно жёсткая: переменная с префиксом `NEXT_PUBLIC_` попадает
    в бандл целиком, и обнаружить утечку после выката будет уже поздно.
    """
    env = os.environ if environ is None else environ
    leaked = sorted(
        name for name in env
        if name.startswith(FORBIDDEN_PUBLIC_PREFIX) and "CDNVIDEOHUB" in name.upper()
    )
    if leaked:
        raise PublicPublisherIdError(
            "Publisher ID CDNVideoHub не может быть публичной переменной: "
            + ", ".join(leaked)
        )


def state(environ: dict | None = None) -> PlayerState:
    """Состояние плеера. Наличие секретов проверяется, значения не читаются."""
    env = os.environ if environ is None else environ
    assert_no_public_publisher_id(env)
    missing = [name for name in (TOKEN_ENV, PUBLISHER_ENV) if not (env.get(name) or "").strip()]
    if missing:
        return PlayerState(
            available=False,
            status=BLOCKED_STATUS,
            message="не переданы: " + ", ".join(missing),
        )
    return PlayerState(available=True, status="READY", message="учётные данные переданы")


def contract_check(player_state: PlayerState) -> dict:
    """Результат проверки контракта плеера.

    Заглушка не может быть успешной проверкой: `passed` остаётся `False`, пока
    вместо плеера стоит текст. Иначе отчёт утверждал бы проверку, которая не
    выполнялась, — а это ошибка отчёта, а не формулировка.
    """
    if player_state.placeholder:
        return {
            "check": "player_contract",
            "passed": False,
            "status": player_state.status,
            "reason": "вместо плеера показана заглушка; контракт не проверялся",
        }
    return {
        "check": "player_contract",
        "passed": False,
        "status": "NOT_RUN",
        "reason": "учётные данные есть, но проверка контракта в этой сборке не запускалась",
    }


def render(player_state: PlayerState, *, title_name: str) -> str:
    """Разметка области плеера.

    Место, размеры и подпись одинаковы в обоих состояниях: включение настоящего
    плеера меняет содержимое кадра, а не раскладку страницы.
    """
    from factory.lords.render import escape  # локальный импорт: общий экранировщик

    if player_state.placeholder:
        inner = (
            '<div class="player__frame" role="group" aria-label="Область плеера">'
            "<div><p><strong>Плеер недоступен на стенде.</strong></p>"
            "<p>Подключение включится после передачи контракта и учётных данных "
            "CDNVideoHub. Стенд не подставляет ни чужой плеер, ни выдуманный "
            "Publisher&nbsp;ID.</p>"
            f'<code class="player__status">{escape(player_state.status)}</code>'
            "</div></div>"
        )
    else:  # pragma: no cover - путь включается вместе с реальными секретами
        inner = (
            '<div class="player__frame" data-player="cdnvideohub" '
            f'data-title="{escape(title_name)}">'
            "<p>Плеер подключается на сервере.</p></div>"
        )
    return (
        '<section class="player" aria-labelledby="player-heading">'
        '<h2 id="player-heading">Просмотр</h2>'
        f"{inner}</section>"
    )
