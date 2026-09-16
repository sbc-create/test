"""REQ-CORE-STOPHOOK-01: сторож завершения не зацикливается.

Дефект, ради которого написан этот файл, наблюдался вживую: сторож девять раз
подряд ответил «цель не достигнута» на неизменившееся состояние, и работу
пришлось обрывать принудительно. Причина у такого поведения всегда одна из
двух — сторож не смотрит на `stop_hook_active` либо не считает терминальные
состояния终 завершением.

Оба случая проверяются здесь, и оба проверяются с обратной стороны: тест,
который проходит и на сломанном сторожe, ничего не сторожит.

Контракт сторожа:

* `exit 0` — завершение разрешено;
* `exit 2` со stderr — завершение заблокировано, текст уходит агенту;
* любой отказ разбора, отсутствие состояния, повреждённый файл — разрешение.
  Сторож, падающий в блокировку при собственной поломке, останавливает работу
  навсегда и незаметно.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

HOOK = Path(__file__).resolve().parents[2] / "automation" / "hooks" / "stop_guard.py"


def run(payload: dict, *, state_dir: Path) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(HOOK)],
        input=json.dumps(payload), text=True, capture_output=True,
        env={"PATH": "/usr/bin:/bin", "FACTORY_GOAL_STATE_DIR": str(state_dir)},
    )


def set_goal(state_dir: Path, text: str, *, status: str | None = None,
             fingerprint: str | None = None) -> None:
    state_dir.mkdir(parents=True, exist_ok=True)
    payload = {"goal": text}
    if status:
        payload["status"] = status
    if fingerprint:
        payload["last_blocked_fingerprint"] = fingerprint
    (state_dir / "goal.json").write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")


class TestStopHookActive:
    def test_повторный_вызов_завершается_успехом(self, tmp_path):
        # Главный случай дефекта. Второй заход сторожа обязан разрешить
        # завершение независимо от того, достигнута цель или нет: платформа уже
        # сообщила, что предыдущая блокировка состоялась.
        set_goal(tmp_path, "выложить что-нибудь")
        result = run({"stop_hook_active": True, "transcript_path": ""}, state_dir=tmp_path)
        assert result.returncode == 0, result.stderr
        assert "не достигнута" not in result.stderr

    def test_первый_вызов_с_недостигнутой_целью_блокирует_один_раз(self, tmp_path):
        set_goal(tmp_path, "выложить что-нибудь")
        first = run({"stop_hook_active": False}, state_dir=tmp_path)
        assert first.returncode == 2, first.stdout
        assert first.stderr.strip()


class TestTerminalStatuses:
    @pytest.mark.parametrize("status", [
        "PASS",
        "CANARY_READY_FOR_OWNER_REVIEW",
        "BLOCKED_WITH_EVIDENCE",
        "BLOCKED_ON_ONE_PRIVILEGED_ACTION",
        "ROLLED_BACK",
    ])
    def test_терминальный_статус_разрешает_завершение_сразу(self, tmp_path, status):
        set_goal(tmp_path, "выложить что-нибудь", status=status)
        result = run({"stop_hook_active": False}, state_dir=tmp_path)
        assert result.returncode == 0, f"{status}: {result.stderr}"

    def test_терминальный_статус_закрывает_цель(self, tmp_path):
        set_goal(tmp_path, "выложить", status="ROLLED_BACK")
        run({"stop_hook_active": False}, state_dir=tmp_path)
        state = json.loads((tmp_path / "goal.json").read_text(encoding="utf-8"))
        assert state.get("closed") is True, "цель осталась открытой после терминального статуса"

    def test_нетерминальный_статус_не_разрешает(self, tmp_path):
        set_goal(tmp_path, "выложить", status="IN_PROGRESS")
        result = run({"stop_hook_active": False}, state_dir=tmp_path)
        assert result.returncode == 2


class TestUnchangedState:
    def test_то_же_состояние_второй_раз_не_блокирует(self, tmp_path):
        # Агент повторил ту же позицию. Новая блокировка означала бы, что
        # сторож требует изменений, которых сам же не позволяет сделать.
        set_goal(tmp_path, "выложить что-нибудь")
        first = run({"stop_hook_active": False, "last_message": "позиция окончательная"},
                    state_dir=tmp_path)
        assert first.returncode == 2
        second = run({"stop_hook_active": False, "last_message": "позиция окончательная"},
                     state_dir=tmp_path)
        assert second.returncode == 0, "тот же ответ заблокирован дважды — это и есть цикл"

    def test_изменившееся_состояние_блокирует_снова(self, tmp_path):
        set_goal(tmp_path, "выложить что-нибудь")
        assert run({"stop_hook_active": False, "last_message": "шаг один"},
                   state_dir=tmp_path).returncode == 2
        assert run({"stop_hook_active": False, "last_message": "шаг два"},
                   state_dir=tmp_path).returncode == 2


class TestSafeFallback:
    def test_нет_состояния_цели_разрешает(self, tmp_path):
        result = run({"stop_hook_active": False}, state_dir=tmp_path)
        assert result.returncode == 0

    def test_повреждённое_состояние_разрешает(self, tmp_path):
        tmp_path.mkdir(parents=True, exist_ok=True)
        (tmp_path / "goal.json").write_text("{это не json", encoding="utf-8")
        result = run({"stop_hook_active": False}, state_dir=tmp_path)
        assert result.returncode == 0, "повреждённое состояние заблокировало завершение"

    def test_мусор_на_входе_разрешает(self, tmp_path):
        set_goal(tmp_path, "выложить")
        result = subprocess.run(
            [sys.executable, str(HOOK)], input="не json вовсе", text=True, capture_output=True,
            env={"PATH": "/usr/bin:/bin", "FACTORY_GOAL_STATE_DIR": str(tmp_path)})
        assert result.returncode == 0

    def test_пустой_вход_разрешает(self, tmp_path):
        set_goal(tmp_path, "выложить")
        result = subprocess.run(
            [sys.executable, str(HOOK)], input="", text=True, capture_output=True,
            env={"PATH": "/usr/bin:/bin", "FACTORY_GOAL_STATE_DIR": str(tmp_path)})
        assert result.returncode == 0


class TestGoalLifecycle:
    def test_закрытая_цель_не_блокирует(self, tmp_path):
        set_goal(tmp_path, "выложить", status="PASS")
        run({"stop_hook_active": False}, state_dir=tmp_path)
        again = run({"stop_hook_active": False}, state_dir=tmp_path)
        assert again.returncode == 0

    def test_новая_цель_не_наследует_старое_состояние(self, tmp_path):
        # Отпечаток прошлой блокировки не должен разрешать завершение новой
        # цели: иначе первый же Stop после смены цели пройдёт молча.
        set_goal(tmp_path, "старая цель", fingerprint="старый-отпечаток")
        set_goal(tmp_path, "новая цель")
        result = run({"stop_hook_active": False, "last_message": "старый-отпечаток"},
                     state_dir=tmp_path)
        assert result.returncode == 2, "новая цель унаследовала состояние старой"


class TestSubagentStop:
    def test_subagent_stop_подчиняется_тому_же_правилу(self, tmp_path):
        set_goal(tmp_path, "выложить")
        assert run({"stop_hook_active": True, "hook_event_name": "SubagentStop"},
                   state_dir=tmp_path).returncode == 0

    def test_subagent_stop_не_блокирует_вовсе(self, tmp_path):
        # Подагент завершается внутри чужой задачи: блокировать его завершение
        # значит держать родителя на паузе за чужую цель.
        set_goal(tmp_path, "выложить")
        result = run({"stop_hook_active": False, "hook_event_name": "SubagentStop"},
                     state_dir=tmp_path)
        assert result.returncode == 0
