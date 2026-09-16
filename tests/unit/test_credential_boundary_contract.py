"""Граница учётных данных Templates: схема, разбор и правило — без живого юнита.

Что здесь проверяется и чего здесь нет.

ЕСТЬ: форма снимка, его разбор, и правило `проверить` — на годном снимке и на
каждом виде испорченного. Это воспроизводимо в любом клоне репозитория.

НЕТ: утверждений о том, в каком состоянии юнит `templates-cp-consumer` прямо
сейчас. Раньше они стояли в `tests/tplr2` и требовали файла
`artifacts/tpl-r2/credential-boundary.json`, который в репозитории не лежит и
лежать не может: его производит живой хост. На раннере файла не было, и
четырнадцать проверок падали на «нет снимка», не сообщив о границе ничего.
Теперь живой снимок снимает и проверяет host-контур
(`bin/host-attest`, проверка `templates.credential_boundary`) — тем же правилом,
что проверено здесь.

Правило и его проверка разделены намеренно: правило, проверяемое только на
живой машине, проверяется ровно там, где его труднее всего исполнить.
"""
from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from factory.site_engine.attestation import credential_boundary as CB
from factory.site_engine.changeset import model as M

КОРЕНЬ = Path(__file__).resolve().parents[2]
FIXTURE = КОРЕНЬ / "tests/fixtures/credential-boundary.valid.json"
ИСПОРЧЕННАЯ = КОРЕНЬ / "tests/fixtures/credential-boundary.invalid.json"


@pytest.fixture()
def снимок() -> dict:
    return CB.разобрать(FIXTURE.read_text(encoding="utf-8"))


def test_версионированная_fixture_разбирается(снимок):
    assert снимок["snapshot_version"] == CB.ВЕРСИЯ_СНИМКА
    assert снимок["unit"] == CB.ЮНИТ


def test_снимок_без_полного_перечня_запретов_отвергается():
    """Отсутствующий запрет не отличается от невыполненной проверки — значит, отказ."""
    with pytest.raises(CB.СнимокНевалиден):
        CB.разобрать(ИСПОРЧЕННАЯ.read_text(encoding="utf-8"))


def test_не_json_отвергается():
    with pytest.raises(CB.СнимокНевалиден):
        CB.разобрать("{не json")


def test_годный_снимок_нарушений_не_даёт(снимок):
    assert CB.проверить(снимок) == []


def test_чужая_учётная_запись(снимок):
    снимок["user"] = "control-api"
    assert any("собственной учётной записью" in н for н in CB.проверить(снимок))


def test_неактивный_юнит(снимок):
    снимок["active_state"] = "failed"
    assert any("состоянии" in н for н in CB.проверить(снимок))


def test_общий_env_читается(снимок):
    снимок["environment_files"] = [CB.ОБЩИЙ_ENV]
    снимок["shared_env_readers"] = 2
    нарушения = CB.проверить(снимок)
    assert any(CB.ОБЩИЙ_ENV in н for н in нарушения)
    assert any("посторонних юнитов" in н for н in нарушения)


def test_чужие_credential(снимок):
    снимок["foreign_credential_refs"] = ["approval-signing-key"]
    assert any("чужие credential" in н for н in CB.проверить(снимок))


def test_секреты_в_окружении(снимок):
    снимок["secrets_in_env"] = ["AUDIT_TOKEN_TEMPLATES"]
    assert any("секреты объявлены в окружении" in н for н in CB.проверить(снимок))


@pytest.mark.parametrize("опасное", ["--token=x", "KEY=y", "a-secret-here",
                                     "Authorization: Bearer zzz"])
def test_секрет_в_аргументах_процесса(снимок, опасное):
    """Аргументы процесса видны всем, кто может читать /proc."""
    снимок["process_args"] = f"/usr/bin/python -m consumer {опасное}"
    assert CB.проверить(снимок), f"{опасное!r} в аргументах не замечено"


def test_секрет_в_аргументах_потомка(снимок):
    снимок["child_process_args"] = ["/bin/sh -c 'curl -H \"Bearer abc\"'"]
    assert any("потомка" in н for н in CB.проверить(снимок))


@pytest.mark.parametrize("запрет", CB.ЗАПРЕТЫ)
def test_каждый_запрет_обязателен(снимок, запрет):
    """Поимённо: иначе отключённый запрет прошёл бы под видом «остальные же есть»."""
    снимок["denials"][запрет] = False
    assert f"запрет {запрет} не действует" in CB.проверить(снимок)


def test_лишняя_роль_у_templates(снимок):
    снимок["changeset_roles_templates"] = ["proposer", "approver"]
    assert any("предлагает и не более того" in н for н in CB.проверить(снимок))


def test_модели_не_запрещено_одобрять(снимок):
    снимок["model_forbidden_actions"] = ["apply", "rollback"]
    assert any("approve" in н for н in CB.проверить(снимок))


def test_правило_не_молчит_ни_на_одном_испорченном_снимке(снимок):
    """Страховка от правила, которое перестало смотреть на часть снимка.

    Каждое поле по очереди приводится в заведомо негодный вид. Поле, порча
    которого не даёт ни одного нарушения, правилом не проверяется — а значит,
    в снимке оно лежит зря.
    """
    порча = {
        "user": "posted-by-someone-else",
        "active_state": "inactive",
        "shared_env_readers": 3,
        "environment_files": [CB.ОБЩИЙ_ENV],
        "foreign_credential_refs": ["approval-signing-key"],
        "secrets_in_env": ["SOME_TOKEN"],
        "process_args": "consumer --token=abcdef",
        "child_process_args": ["sh -c 'echo secret'"],
        "changeset_roles_templates": ["proposer", "executor"],
        "model_forbidden_actions": [],
    }
    for поле, значение in порча.items():
        испорченный = copy.deepcopy(снимок)
        испорченный[поле] = значение
        assert CB.проверить(испорченный), f"порча поля {поле} осталась незамеченной"


def test_templates_не_подписывает():
    """Приватный ключ подписи принадлежит одной службе, и это не Templates.

    Утверждение о коде, а не о хосте: перенесено из `tests/tplr2` без изменений,
    потому что герметичным оно было всегда.
    """
    from factory.site_engine.approval import service as SIGNER
    assert "templates" not in SIGNER.ДОПУЩЕНЫ_К_ОДОБРЕНИЮ
    assert "templates" not in SIGNER.ДОПУЩЕНЫ_К_РАЗРЕШЕНИЮ


def test_роли_в_fixture_совпадают_с_моделью(снимок):
    """Снимок не вправе расходиться с объявленной моделью ролей.

    Иначе fixture начнёт жить своей жизнью: правило будет проверять её, модель
    изменится, и расхождение заметит только боевой выкат.
    """
    assert set(снимок["changeset_roles_templates"]) == set(M.роли_службы("templates"))
    assert M.APPROVER not in снимок["changeset_roles_templates"]
    assert M.EXECUTOR not in снимок["changeset_roles_templates"]


def test_fixture_валидна_по_схеме_из_репозитория():
    """Схема и fixture проверяются вместе: разойтись молча они не должны."""
    схема = json.loads(CB.СХЕМА.read_text(encoding="utf-8"))
    assert схема["properties"]["snapshot_version"]["const"] == CB.ВЕРСИЯ_СНИМКА
    обязательные = схема["properties"]["denials"]["required"]
    assert set(обязательные) == set(CB.ЗАПРЕТЫ)
