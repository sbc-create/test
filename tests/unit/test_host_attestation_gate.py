"""REQ-HOST-ATTESTATION: ворота релиза закрыты по умолчанию.

Открывает их только годное свидетельство host-контура — снятое на control host,
для того же candidate SHA, свежее, полное и без единой провалившейся или
недоступной обязательной проверки.

Проверяется ровно то, ради чего ворота существуют: пять способов, которыми
свидетельство перестаёт что-либо значить, и каждый из них обязан остановить
выкат. Все свидетельства здесь синтетические — host-контур не запускается, и
живого флота эти тесты не касаются.

Почему каждый случай отдельным тестом, а не одним «ворота работают». Все пять
отказов выглядят одинаково снаружи — выкат не состоялся, — и именно поэтому их
легко перепутать между собой при правке. Тест, различающий только «прошло/не
прошло», молча переживёт подмену протухшего свидетельства на чужое.
"""
from __future__ import annotations

import datetime as _dt
import json

import pytest

from factory.site_engine.attestation import contract as C
from factory.site_engine.attestation import gate as G

SHA = "a" * 40
ЧУЖОЙ_SHA = "b" * 40
МОМЕНТ = _dt.datetime(2026, 9, 16, 12, 0, tzinfo=_dt.timezone.utc)


def результат(check_id: str, status: str = "PASS") -> C.Результат:
    return C.Результат(check_id=check_id, status=status,
                       detail=f"синтетический результат {status}",
                       measured_at="2026-09-16T11:30:00Z")


def свидетельство(*, candidate_sha: str = SHA, control_host: bool = True,
                  measured_at: str = "2026-09-16T11:30:00Z",
                  пропустить: set[str] | None = None,
                  провалить: dict[str, str] | None = None) -> dict:
    пропустить = пропустить or set()
    провалить = провалить or {}
    результаты = [результат(cid, провалить.get(cid, "PASS"))
                  for cid in sorted(C.ОБЯЗАТЕЛЬНЫЕ) if cid not in пропустить]
    документ = C.собрать(candidate_sha=candidate_sha,
                         hostname="control-host.invalid",
                         control_host=control_host,
                         evidence_root="/srv/site-factory",
                         результаты=результаты, measured_at=measured_at)
    return документ


def test_полное_свидетельство_пропускает():
    итог = G.проверить(свидетельство(), candidate_sha=SHA, сейчас_utc=МОМЕНТ)
    assert итог["verdict"] == "PASS"
    assert {п["check_id"] for п in итог["checks"]} == C.ОБЯЗАТЕЛЬНЫЕ


def test_отсутствующее_свидетельство_блокирует():
    """Нет свидетельства — значит флот не измеряли. Это и есть главный случай."""
    with pytest.raises(G.РелизЗаблокирован) as ош:
        G.проверить(None, candidate_sha=SHA, сейчас_utc=МОМЕНТ)
    assert ош.value.код == "HOST_ATTESTATION_MISSING"


def test_протухшее_свидетельство_блокирует():
    документ = свидетельство(measured_at="2026-09-14T11:30:00Z")
    with pytest.raises(G.РелизЗаблокирован) as ош:
        G.проверить(документ, candidate_sha=SHA, сейчас_utc=МОМЕНТ)
    assert ош.value.код == "HOST_ATTESTATION_STALE"


def test_свидетельство_на_границе_срока_ещё_годно():
    """Граница проверяется с обеих сторон: иначе «сутки» могут значить что угодно."""
    почти = (МОМЕНТ - G.МАКСИМАЛЬНЫЙ_ВОЗРАСТ + _dt.timedelta(minutes=1))
    документ = свидетельство(
        measured_at=почти.isoformat().replace("+00:00", "Z"))
    assert G.проверить(документ, candidate_sha=SHA, сейчас_utc=МОМЕНТ)

    просрочено = (МОМЕНТ - G.МАКСИМАЛЬНЫЙ_ВОЗРАСТ - _dt.timedelta(minutes=1))
    with pytest.raises(G.РелизЗаблокирован) as ош:
        G.проверить(свидетельство(
            measured_at=просрочено.isoformat().replace("+00:00", "Z")),
            candidate_sha=SHA, сейчас_utc=МОМЕНТ)
    assert ош.value.код == "HOST_ATTESTATION_STALE"


def test_свидетельство_другого_дерева_блокирует():
    """Измеряли не то, что выкатывают."""
    with pytest.raises(G.РелизЗаблокирован) as ош:
        G.проверить(свидетельство(candidate_sha=ЧУЖОЙ_SHA),
                    candidate_sha=SHA, сейчас_utc=МОМЕНТ)
    assert ош.value.код == "HOST_ATTESTATION_SHA_MISMATCH"


@pytest.mark.parametrize("пропущенная", sorted(C.ОБЯЗАТЕЛЬНЫЕ))
def test_неполное_свидетельство_блокирует(пропущенная):
    """Каждая обязательная проверка обязана быть обязательной по отдельности.

    Параметризация по всему перечню, а не по одной проверке для примера:
    иначе проверку можно было бы тихо убрать из состава, и ворота этого не
    заметили бы ни для неё, ни для читателя теста.
    """
    документ = свидетельство(пропустить={пропущенная})
    with pytest.raises(G.РелизЗаблокирован) as ош:
        G.проверить(документ, candidate_sha=SHA, сейчас_utc=МОМЕНТ)
    assert ош.value.код == "HOST_ATTESTATION_INCOMPLETE"
    assert пропущенная in ош.value.detail


@pytest.mark.parametrize("статус", ["FAIL", "BLOCKED"])
def test_провалившаяся_обязательная_проверка_блокирует(статус):
    """BLOCKED блокирует наравне с FAIL: «не смотрели» — не «всё хорошо»."""
    документ = свидетельство(провалить={"ledger.backup": статус})
    with pytest.raises(G.РелизЗаблокирован) as ош:
        G.проверить(документ, candidate_sha=SHA, сейчас_utc=МОМЕНТ)
    assert ош.value.код == "HOST_ATTESTATION_CHECK_FAILED"
    assert f"ledger.backup={статус}" in ош.value.detail


def test_свидетельство_не_с_control_host_блокирует():
    """Документ нужной формы можно выпустить где угодно. Ценность даёт место."""
    документ = свидетельство(control_host=False)
    # Вердикт при этом PASS: проверки-то прошли. Отказ приходит именно от места.
    assert документ["verdict"] == "PASS"
    with pytest.raises(G.РелизЗаблокирован) as ош:
        G.проверить(документ, candidate_sha=SHA, сейчас_utc=МОМЕНТ)
    assert ош.value.код == "HOST_ATTESTATION_NOT_CONTROL_HOST"


def test_подделанный_вердикт_не_открывает_ворота():
    """Ворота считают вердикт сами и сверяются с записанным."""
    документ = свидетельство(провалить={"fleet.census": "FAIL"})
    документ["verdict"] = "PASS"
    with pytest.raises(G.РелизЗаблокирован) as ош:
        G.проверить(документ, candidate_sha=SHA, сейчас_utc=МОМЕНТ)
    assert ош.value.код == "HOST_ATTESTATION_CHECK_FAILED"


def test_повторённая_проверка_блокирует():
    """Один check_id дважды: какой результат действителен, документ не говорит."""
    документ = свидетельство()
    документ["checks"].append(dict(документ["checks"][0], status="FAIL"))
    with pytest.raises(G.РелизЗаблокирован) as ош:
        G.проверить(документ, candidate_sha=SHA, сейчас_utc=МОМЕНТ)
    assert ош.value.код == "HOST_ATTESTATION_MALFORMED"


def test_измерение_из_будущего_блокирует():
    """Разъехавшиеся часы лишают срок годности смысла, а не удлиняют его."""
    будущее = (МОМЕНТ + _dt.timedelta(hours=3)).isoformat().replace("+00:00", "Z")
    with pytest.raises(G.РелизЗаблокирован) as ош:
        G.проверить(свидетельство(measured_at=будущее),
                    candidate_sha=SHA, сейчас_utc=МОМЕНТ)
    assert ош.value.код == "HOST_ATTESTATION_MALFORMED"


def test_время_без_зоны_блокирует():
    документ = свидетельство()
    документ["measured_at"] = "2026-09-16T11:30:00"
    with pytest.raises(G.РелизЗаблокирован) as ош:
        G.проверить(документ, candidate_sha=SHA, сейчас_utc=МОМЕНТ)
    assert ош.value.код == "HOST_ATTESTATION_MALFORMED"


def test_мусор_вместо_свидетельства_блокирует():
    with pytest.raises(G.РелизЗаблокирован) as ош:
        G.проверить({"schema_version": "host-attestation/1.0.0"},
                    candidate_sha=SHA, сейчас_utc=МОМЕНТ)
    assert ош.value.код == "HOST_ATTESTATION_MALFORMED"


def test_загрузка_с_диска_и_отсутствие_файла(tmp_path):
    """`допустить` читает каталог; отсутствие файла — это MISSING, а не сбой."""
    with pytest.raises(G.РелизЗаблокирован) as ош:
        G.допустить(candidate_sha=SHA, каталог=tmp_path, сейчас_utc=МОМЕНТ)
    assert ош.value.код == "HOST_ATTESTATION_MISSING"

    C.записать(свидетельство(), каталог=tmp_path)
    assert G.допустить(candidate_sha=SHA, каталог=tmp_path,
                       сейчас_utc=МОМЕНТ)["verdict"] == "PASS"


def test_каталог_берётся_из_настройки_развёртывания(tmp_path, monkeypatch):
    """Переменная задаёт МЕСТО, а не право обойти ворота: пустой каталог блокирует."""
    monkeypatch.setenv("HOST_ATTESTATION_DIR", str(tmp_path))
    with pytest.raises(G.РелизЗаблокирован) as ош:
        G.допустить(candidate_sha=SHA, сейчас_utc=МОМЕНТ)
    assert ош.value.код == "HOST_ATTESTATION_MISSING"

    C.записать(свидетельство())
    assert (tmp_path / f"{SHA}.json").is_file()
    assert G.допустить(candidate_sha=SHA, сейчас_utc=МОМЕНТ)["verdict"] == "PASS"


def test_записанное_свидетельство_соответствует_схеме(tmp_path):
    путь = C.записать(свидетельство(), каталог=tmp_path)
    C.проверить_схему(json.loads(путь.read_text(encoding="utf-8")))
