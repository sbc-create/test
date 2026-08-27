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


#: Агрегаторы, допустимые как playback identifier. IMDb сюда не входит: PC-2
#: запрещает его в этой роли, и молчаливое расширение списка было бы нарушением.
ALLOWED_AGGREGATORS = ("kp", "mali", "mdl")

#: PC-3: значение фиксировано контрактом и не берётся из настроек сайта.
DISABLE_LICENSED = "false"

CONTRACT_REF = "knowledge/cdnvideohub/PLAYER_CONTRACT.yaml"


class PlayerContractError(RuntimeError):
    """Параметры плеера расходятся с контрактом."""

    status = "BLOCKED_PLAYER_CONTRACT"


def load_player_contract(path=None) -> dict:
    """Скрипт и элемент берутся из замороженного контракта, а не из кода."""
    from pathlib import Path

    import yaml

    from factory.paths import PATHS
    target = path or (PATHS.root / CONTRACT_REF)
    return yaml.safe_load(Path(target).read_text(encoding="utf-8")) or {}


def player_attributes(
    *,
    publisher_id: str,
    aggregator: str,
    title_id: str,
    ident: str,
    season: int,
    episode: int,
    only_voice: str | None = None,
    priority_voice: str | None = None,
    show_voice_only: bool = False,
    show_banner: bool = True,
) -> dict[str, str]:
    """Атрибуты `<video-player>` по контракту.

    Проверки здесь отказные, а не поправляющие: подставить «разумное» значение
    вместо неверного значило бы выдать собственную догадку за контракт.
    """
    if aggregator not in ALLOWED_AGGREGATORS:
        raise PlayerContractError(
            f"агрегатор {aggregator!r} вне допустимых {ALLOWED_AGGREGATORS} (PC-2)"
        )
    if not str(title_id).strip():
        raise PlayerContractError("пустой data-title-id")
    if not is_valid_publisher_id(publisher_id):
        raise PlayerContractError("publisher-id обязан быть положительным целым")
    for label, value in (("season", season), ("episode", episode)):
        if not isinstance(value, int) or isinstance(value, bool) or value < 1:
            raise PlayerContractError(f"{label} обязан быть положительным целым, получено {value!r}")

    attributes = {
        "ident": ident,
        "season": str(season),
        "episode": str(episode),
        "data-publisher-id": str(publisher_id).strip(),
        "data-title-id": str(title_id).strip(),
        "data-aggregator": aggregator,
        "is-show-voice-only": "true" if show_voice_only else "false",
        "is-show-banner": "true" if show_banner else "false",
        "disable-licensed": DISABLE_LICENSED,
    }

    # PC-1: непустой only-voice имеет приоритет, конфликтующая пара запрещена.
    only = (only_voice or "").strip()
    priority = (priority_voice or "").strip()
    if only and priority:
        raise PlayerContractError("only-voice и priority-voice одновременно запрещены (PC-1)")
    if only:
        attributes["only-voice"] = only
    elif priority:
        attributes["priority-voice"] = priority
    return attributes


def is_valid_publisher_id(value: str | int | None) -> bool:
    """Publisher ID — положительное целое.

    Плеер вызывает Number(publisherId); нечисловое значение превращается в NaN,
    и провайдер отвечает 400. Проверять это на сборке дешевле, чем ловить на
    публичной странице.
    """
    text = str(value or "").strip()
    if not text.isdigit() or text.startswith("0"):
        return False
    return int(text) >= 1


def render_live(
    *,
    publisher_id: str,
    aggregator: str,
    title_id: str,
    title_name: str,
    ident: str,
    season: int = 1,
    episode: int = 1,
    script_url: str | None = None,
    only_voice: str | None = None,
    priority_voice: str | None = None,
) -> str:
    """Разметка настоящего плеера: custom element, без iframe (PC-4).

    Publisher ID подставляется здесь, на сервере, в момент ответа. В общий
    JS-бандл он не попадает: отдельного скрипта с конфигурацией нет, значение
    живёт только атрибутом этого элемента.
    """
    from factory.lords.render import escape

    contract = load_player_contract()
    element = str(contract.get("element") or "video-player")
    url = script_url or str((contract.get("script") or {}).get("url", ""))
    if not url.startswith("https://"):
        raise PlayerContractError("в контракте нет https-адреса скрипта плеера")

    attributes = player_attributes(
        publisher_id=publisher_id, aggregator=aggregator, title_id=title_id,
        ident=ident, season=season, episode=episode,
        only_voice=only_voice, priority_voice=priority_voice,
    )
    rendered = " ".join(
        f'{escape(name)}="{escape(value)}"' for name, value in attributes.items()
    )
    return (
        '<section class="player" aria-labelledby="player-heading">'
        '<h2 id="player-heading">Просмотр</h2>'
        '<div class="player__frame" role="group" aria-label="Область плеера">'
        f"<{element} {rendered}></{element}>"
        '<noscript><p>Для просмотра нужен JavaScript: плеер подключается '
        "скриптом провайдера.</p></noscript>"
        '<p class="player__fallback" data-player-fallback hidden>'
        "Источник видео сейчас недоступен. Обновите страницу позже — "
        "каталог и описание доступны и без плеера.</p>"
        "</div>"
        f'<script src="{escape(url)}" async data-player-script></script>'
        "</section>"
    )


def render(player_state: PlayerState, *, title_name: str) -> str:
    """Разметка области плеера.

    Место, размеры и подпись одинаковы в обоих состояниях: включение настоящего
    плеера меняет содержимое кадра, а не раскладку страницы.
    """
    from factory.lords.render import escape  # локальный импорт: общий экранировщик

    if player_state.placeholder:
        # Текст читает посетитель, а не оператор сборки. Раньше здесь стоял
        # служебный код и инструкция про передачу учётных данных — она месяцами
        # висела на публичных страницах фильмов. Причина отказа принадлежит
        # отчёту сборки и журналу, а не странице.
        inner = (
            '<div class="player__frame" role="group" aria-label="Область плеера">'
            "<div><p>Видео для этого тайтла временно недоступно.</p>"
            "<p>Описание, каталог и похожие тайтлы работают как обычно.</p>"
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
