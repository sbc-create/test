#!/usr/bin/env python3
"""Сторож завершения: блокирует не больше одного раза на неизменившееся состояние.

## Дефект, ради которого сторож написан

Наблюдался вживую: сторож девять раз подряд ответил «цель не достигнута» на
неизменившийся ответ агента, и работу пришлось обрывать принудительно. Ни одна
из девяти блокировок не могла ничего изменить — то, чего сторож требовал,
требовало внешнего разрешения, которого агент не мог себе выдать.

У такого поведения всегда одна из двух причин, и обе закрыты здесь:

1. **Не читается `stop_hook_active`.** Платформа сообщает этим полем, что
   предыдущая блокировка уже состоялась. Сторож, который его игнорирует,
   зацикливается по построению.
2. **Терминальные состояния не считаются завершением.** Доказанный внешний
   блокер — такой же законный итог, как успех: вся возможная работа сделана,
   и повторять её незачем.

## Контракт

| Код | Значение |
|---|---|
| `0` | завершение разрешено |
| `2` | завершение заблокировано, текст из stderr уходит агенту |

Любой отказ — нечитаемый вход, отсутствующее или повреждённое состояние,
неожиданное исключение — разрешает завершение. Сторож, падающий в блокировку
при собственной поломке, останавливает работу навсегда и незаметно; это хуже
любой пропущенной цели.

## Чего сторож не делает

Не блокирует `SubagentStop`. Подагент завершается внутри чужой задачи, и
держать его на паузе за цель родителя значит останавливать работу, которой он
не управляет.

## Установка

Путь намеренно вне `.claude/hooks/`: тот каталог защищён от записи, и это
правильная защита. Подключается ссылкой из настроек:

    "Stop": [{"hooks": [{"type": "command",
      "command": "python3 ${CLAUDE_PROJECT_DIR}/automation/hooks/stop_guard.py"}]}]
"""
from __future__ import annotations

import hashlib
import json
import os
import sys
from pathlib import Path

#: Итоги, после которых цель считается закрытой. Доказанный внешний блокер —
#: такой же законный итог, как успех: вся независимая работа выполнена, и
#: следующий шаг принадлежит не агенту.
TERMINAL_STATUSES = frozenset({
    "PASS",
    "DONE",
    "ROLLED_BACK",
    "CANARY_READY_FOR_OWNER_REVIEW",
    "BLOCKED_WITH_EVIDENCE",
    "BLOCKED_BEFORE_DEPLOY",
    "BLOCKED_ON_ONE_PRIVILEGED_ACTION",
    "STOP_HOOK_FIXED_CANARY_BLOCKED_WITH_EVIDENCE",
})

STATE_FILE = "goal.json"


def allow() -> None:
    raise SystemExit(0)


def block(message: str) -> None:
    print(message, file=sys.stderr)
    raise SystemExit(2)


def state_dir() -> Path:
    override = os.environ.get("FACTORY_GOAL_STATE_DIR", "").strip()
    if override:
        return Path(override)
    return Path(__file__).resolve().parents[2] / "var" / "goal"


def read_state(path: Path) -> dict:
    """Состояние цели. Повреждённое равнозначно отсутствующему.

    Ронять сессию из-за испорченного файла нельзя: он пишется сторонним кодом,
    а цена ошибки — остановка работы навсегда.
    """
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def write_state(directory: Path, path: Path, state: dict) -> bool:
    try:
        directory.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(state, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        return True
    except OSError:
        return False


def fingerprint(payload: dict) -> str:
    """Отпечаток попытки завершения.

    Считается по тому, что агент сказал последним. Совпадение означает, что
    состояние не изменилось, а значит новая блокировка потребовала бы того же,
    чего уже потребовала предыдущая, — и получила бы тот же ответ.
    """
    material = str(payload.get("last_message") or payload.get("transcript_path") or "")
    return hashlib.sha256(material.encode("utf-8")).hexdigest()[:16]


def main() -> None:
    try:
        raw = sys.stdin.read()
    except Exception:  # noqa: BLE001 — вход недоступен, это не повод блокировать
        allow()
    # Пустой вход неотличим от сломанного вызова: `stop_hook_active` в нём не
    # прочитать, а значит нельзя понять, была ли блокировка. Блокировать в
    # такой неизвестности — верный способ получить цикл.
    if not raw.strip():
        allow()
    try:
        payload = json.loads(raw)
    except ValueError:
        allow()
    if not isinstance(payload, dict):
        allow()

    if str(payload.get("hook_event_name") or "") == "SubagentStop":
        allow()

    # Платформа сообщила, что блокировка уже была. Второй раз — это цикл.
    if payload.get("stop_hook_active"):
        allow()

    directory = state_dir()
    path = directory / STATE_FILE
    state = read_state(path)
    if not state or not state.get("goal") or state.get("closed"):
        allow()

    status = str(state.get("status") or "").strip().upper()
    if status in TERMINAL_STATUSES:
        state["closed"] = True
        state["closed_by"] = status
        write_state(directory, path, state)
        allow()

    current = fingerprint(payload)
    if state.get("last_blocked_fingerprint") == current:
        # Тот же ответ во второй раз. Блокировать снова — значит требовать
        # изменений, которых сторож сам же не позволяет сделать.
        allow()

    state["last_blocked_fingerprint"] = current
    if not write_state(directory, path, state):
        # Записать не удалось — отличить повтор в следующий раз будет нечем,
        # и блокировка стала бы вечной. Цикл хуже пропущенной цели.
        allow()

    block(
        f"Цель не достигнута: {state['goal']}\n"
        "Продолжайте работу. Если дальнейшие шаги требуют внешнего разрешения, "
        "запишите терминальный статус в состояние цели — сторож пропустит завершение."
    )


if __name__ == "__main__":
    try:
        main()
    except SystemExit:
        raise
    except Exception:  # noqa: BLE001 — неожиданный отказ не должен держать сессию
        raise SystemExit(0)
