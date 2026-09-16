"""Контракт свидетельства и host-команда: форма, вердикт, поведение без доступа.

Ни один тест здесь не измеряет живой флот и не обращается к `/srv`: проверяются
контракт и та часть команды, которая решает, можно ли вообще измерять.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from factory.site_engine.attestation import contract as C
from host_attestation import checks as X
from host_attestation import cli

КОРЕНЬ = Path(__file__).resolve().parents[2]
SHA = "c" * 40


def _результаты(статусы: dict[str, str]) -> list[C.Результат]:
    return [C.Результат(check_id=cid, status=статусы.get(cid, "PASS"),
                        detail="синтетический", measured_at=C.сейчас())
            for cid in sorted(C.ОБЯЗАТЕЛЬНЫЕ)]


def test_состав_контракта_и_исполнителя_совпадает():
    """Объявленная, но не выполняемая проверка сделала бы каждое свидетельство неполным.

    Расхождение этих двух списков — самый тихий способ сломать контур: состав
    берётся из контракта, а выполняет проверки другой модуль, и несовпадение
    проявилось бы только на боевом выкате.
    """
    выполняемые = {cid for cid, _ in X.ВСЕ}
    assert выполняемые == {п.check_id for п in C.ПРОВЕРКИ}
    assert выполняемые >= C.ОБЯЗАТЕЛЬНЫЕ


def test_у_каждой_проверки_есть_название_и_уникальный_идентификатор():
    идентификаторы = [п.check_id for п in C.ПРОВЕРКИ]
    assert len(идентификаторы) == len(set(идентификаторы))
    assert all(п.title.strip() for п in C.ПРОВЕРКИ)


def test_вердикт_pass_только_при_всех_pass():
    assert C.вердикт(_результаты({})) == "PASS"


def test_вердикт_fail_при_провале():
    assert C.вердикт(_результаты({"fleet.census": "FAIL"})) == "FAIL"


def test_недоступность_сильнее_провала():
    """BLOCKED перекрывает FAIL: о неизмеренном известно меньше, чем о сломанном."""
    статусы = {"fleet.census": "FAIL", "ledger.backup": "BLOCKED"}
    assert C.вердикт(_результаты(статусы)) == "BLOCKED"


def test_неполный_состав_не_бывает_pass():
    частично = _результаты({})[:-1]
    assert C.вердикт(частично) == "BLOCKED"


def test_необъявленная_проверка_отвергается():
    with pytest.raises(C.АттестацияНевалидна):
        C.Результат(check_id="fleet.невыдуманная", status="PASS",
                    detail="", measured_at=C.сейчас())


def test_необъявленный_статус_отвергается():
    with pytest.raises(C.АттестацияНевалидна):
        C.Результат(check_id="fleet.census", status="SKIPPED",
                    detail="", measured_at=C.сейчас())


def test_собранное_свидетельство_проходит_схему():
    документ = C.собрать(candidate_sha=SHA, hostname="h.invalid",
                         control_host=True, evidence_root="/srv/site-factory",
                         результаты=_результаты({}))
    C.проверить_схему(документ)
    assert документ["verdict"] == "PASS"
    assert документ["schema_version"] == C.ВЕРСИЯ_СХЕМЫ


def test_разбор_отвергает_не_json_и_не_объект():
    with pytest.raises(C.АттестацияНевалидна):
        C.разобрать("{не json")
    with pytest.raises(C.АттестацияНевалидна):
        C.разобрать("[1, 2]")


def test_версионированная_fixture_разбирается():
    сырое = (КОРЕНЬ / "tests/fixtures/host-attestation.valid.json").read_text("utf-8")
    assert C.разобрать(сырое)["verdict"] == "PASS"


def test_испорченная_fixture_отвергается():
    сырое = (КОРЕНЬ / "tests/fixtures/host-attestation.invalid.json").read_text("utf-8")
    with pytest.raises(C.АттестацияНевалидна):
        C.разобрать(сырое)


# --------------------------------------------------------------- host-команда


def test_команда_без_разрешённого_окружения_возвращает_blocked(tmp_path, capsys):
    """Главное свойство команды: без допуска она не притворяется успехом.

    Ни одна проверка не выполняется, но состав свидетельства остаётся полным —
    и каждая запись честно говорит, что измерения не было. Такое свидетельство
    ворота релиза не пропустят, и это правильный исход.
    """
    код = cli.main(["--candidate-sha", SHA, "--output-dir", str(tmp_path)])
    assert код == 2, "BLOCKED обязан отличаться от PASS и кодом возврата"

    документ = json.loads((tmp_path / f"{SHA}.json").read_text("utf-8"))
    C.проверить_схему(документ)
    assert документ["verdict"] == "BLOCKED"
    assert документ["host"]["control_host"] is False
    assert {п["check_id"] for п in документ["checks"]} == C.ОБЯЗАТЕЛЬНЫЕ
    assert all(п["status"] == "BLOCKED" for п in документ["checks"])
    assert all("измерение не выполнялось" in п["detail"] for п in документ["checks"])


def test_команда_без_доступного_корня_флота_возвращает_blocked(tmp_path, monkeypatch):
    """Хост объявлен control host, но корня флота нет — это тоже не PASS."""
    monkeypatch.setenv("HOST_ATTESTATION_CONTROL_HOST", "1")
    monkeypatch.setenv("FLEET_ROOT", str(tmp_path / "нет-такого-каталога"))
    код = cli.main(["--candidate-sha", SHA, "--output-dir", str(tmp_path)])
    assert код == 2
    документ = json.loads((tmp_path / f"{SHA}.json").read_text("utf-8"))
    assert документ["verdict"] == "BLOCKED"
    assert "корень флота" in документ["checks"][0]["detail"]


def test_команда_отвергает_негодный_candidate_sha(tmp_path, capsys):
    assert cli.main(["--candidate-sha", "не-sha", "--output-dir", str(tmp_path)]) == 3
    assert not list(tmp_path.glob("*.json")), "негодный вызов не выпускает свидетельств"


def test_корень_флота_задаётся_контрактом_а_не_зашит(monkeypatch, tmp_path):
    """Группа F: `/srv` — умолчание установки, а не единственное допустимое место."""
    assert X.корень_флота() == Path(X.БАЗОВАЯ_ЛИНИЯ["fleet_root"])
    monkeypatch.setenv("FLEET_ROOT", str(tmp_path))
    assert X.корень_флота() == tmp_path


def test_проверки_без_доступа_дают_blocked_а_не_pass(monkeypatch, tmp_path):
    """Каждая проверка, упирающаяся в данные флота, обязана сказать BLOCKED.

    Это тот же запрет на мягкую деградацию, что и в остальном контуре, но
    проверенный поимённо: проверка, которая на пустом каталоге отвечает PASS,
    ничего не измеряет и об этом молчит.
    """
    monkeypatch.setenv("FLEET_ROOT", str(tmp_path))
    зависящие_от_данных = (X.перепись_флота, X.версия_реестра,
                           X.синтетические_записи, X.резервная_копия,
                           X.секреты_не_раскрыты)
    for проверка in зависящие_от_данных:
        результат = проверка()
        assert результат.status == "BLOCKED", (
            f"{результат.check_id} без данных флота ответила {результат.status}")
        assert результат.detail.strip(), "отказ обязан называть причину"
