"""Ворота релиза и артефакт политики.

Ворота нужны затем, что изменение, которого никто не собирался делать,
отличается от задуманного только тем, что его никто не назвал. Здесь
проверяется, что ворота это различие показывают и что останавливают выкладку до
изменений, а не после.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from factory.indexing import CLOSED, OPEN, PolicyError, compile_policy
from factory.indexing.artifact import ARTIFACT_SCHEMA, build, load, write
from factory.indexing.gate import check, matrix_from_live, require

КОРЕНЬ = Path(__file__).resolve().parents[2]
ПРОФИЛИ = КОРЕНЬ / "config" / "site-profiles"
РЕЕСТР = КОРЕНЬ / "config" / "FLEET-REGISTRY.json"


def песочница(tmp_path: Path) -> Path:
    """Копия входа политики целиком: профили и реестр флота рядом с ними.

    Копировать только профили нельзя: реестр — такой же вход, и без него
    песочница проверяла бы не то, что собирается на самом деле.
    """
    корень = tmp_path / "config"
    каталог = корень / "site-profiles"
    каталог.mkdir(parents=True, exist_ok=True)
    for путь in ПРОФИЛИ.glob("*.json"):
        (каталог / путь.name).write_text(путь.read_text(encoding="utf-8"), encoding="utf-8")
    (корень / РЕЕСТР.name).write_text(РЕЕСТР.read_text(encoding="utf-8"), encoding="utf-8")
    return каталог

ОТКРЫТ = "yummyani.site"
ЗАКРЫТЫЕ = {
    "yummyani.org", "yummyani.biz", "lordfilm47.space", "lordserial33.biz",
    "1lordserials1.online", "zonafilm.space", "animedia.icu", "animedia.space",
}
ЖИВОЕ_ШТАТНОЕ = {ОТКРЫТ: OPEN, **{d: CLOSED for d in ЗАКРЫТЫЕ}}


def политика():
    return compile_policy(ПРОФИЛИ)


# --- артефакт -----------------------------------------------------------------

def test_артефакт_собирается_детерминированно() -> None:
    """Из одного дерева — один и тот же файл, иначе отпечаток ничего не значит."""
    первый = build(ПРОФИЛИ, source_commit="abc123")
    второй = build(ПРОФИЛИ, source_commit="abc123")
    assert первый == второй
    assert первый["manifest"]["policy_sha256"] == второй["manifest"]["policy_sha256"]


def test_манифест_несёт_отпечаток_каждого_входа() -> None:
    """Входов два: профили и реестр флота. Пропусти реестр — и появление
    нового обслуживаемого домена не изменило бы ни одного отпечатка."""
    артефакт = build(ПРОФИЛИ)
    профили = артефакт["manifest"]["profiles"]
    assert len(профили) == len(list(ПРОФИЛИ.glob("*.json"))) + 1
    assert РЕЕСТР.name in профили
    for имя, отпечаток in профили.items():
        assert len(отпечаток) == 64, f"{имя}: отпечаток не похож на sha256"


def test_правка_профиля_меняет_отпечаток_политики(tmp_path: Path) -> None:
    """Иначе манифест не поймал бы подмену решения."""
    каталог = песочница(tmp_path)
    до = build(каталог)["manifest"]["policy_sha256"]

    цель = каталог / "yummyani-org.json"
    данные = json.loads(цель.read_text(encoding="utf-8"))
    данные["seo_profile"]["indexing_enabled"] = True
    цель.write_text(json.dumps(данные, ensure_ascii=False), encoding="utf-8")

    после = build(каталог)["manifest"]["policy_sha256"]
    assert до != после


def test_появление_сайта_в_реестре_меняет_отпечаток(tmp_path: Path) -> None:
    """Реестр — вход политики, и его правка обязана быть видна в манифесте."""
    каталог = песочница(tmp_path)
    до = build(каталог)["manifest"]["policy_sha256"]

    реестр = каталог.parent / РЕЕСТР.name
    данные = json.loads(реестр.read_text(encoding="utf-8"))
    данные["fleet"].append({"site_id": "tenth-site", "domain": "tenth.example"})
    реестр.write_text(json.dumps(данные, ensure_ascii=False), encoding="utf-8")

    артефакт = build(каталог)
    assert артефакт["manifest"]["policy_sha256"] != до
    assert "tenth.example" in артефакт["matrix"]["closed"], "новый сайт обязан быть закрыт"


def test_артефакт_читается_обратно_в_политику(tmp_path: Path) -> None:
    путь = write(build(ПРОФИЛИ), tmp_path / "indexing-policy.json")
    восстановлено = load(путь)
    assert восстановлено.open_domains == (ОТКРЫТ,)
    assert set(восстановлено.closed_domains) == ЗАКРЫТЫЕ
    assert восстановлено.is_open("www.yummyani.site") is True
    assert восстановлено.is_open("example.invalid") is False


def test_пустой_артефакт_не_читается(tmp_path: Path) -> None:
    путь = tmp_path / "indexing-policy.json"
    путь.write_text("  ", encoding="utf-8")
    with pytest.raises(PolicyError, match="пуст"):
        load(путь)


def test_чужая_схема_артефакта_не_читается(tmp_path: Path) -> None:
    путь = tmp_path / "indexing-policy.json"
    путь.write_text(json.dumps({"schema": "иное/1.0"}), encoding="utf-8")
    with pytest.raises(PolicyError, match="чужая схема"):
        load(путь)


def test_схема_артефакта_названа_явно() -> None:
    assert build(ПРОФИЛИ)["schema"] == ARTIFACT_SCHEMA


# --- ворота: штатный случай ---------------------------------------------------

def test_штатная_матрица_проходит_ворота() -> None:
    результат = check(
        политика(), allowed_open={ОТКРЫТ}, allowed_closed=ЗАКРЫТЫЕ, live=ЖИВОЕ_ШТАТНОЕ
    )
    assert результат.allowed, результат.report()
    assert результат.changes == []
    assert "Изменений политики индексации нет" in результат.report()


def test_require_молчит_когда_ворота_пропускают() -> None:
    require(check(политика(), allowed_open={ОТКРЫТ}, allowed_closed=ЗАКРЫТЫЕ,
                  live=ЖИВОЕ_ШТАТНОЕ))


# --- ворота: запреты ----------------------------------------------------------

def test_неизвестное_живое_состояние_запрещает_выкладку() -> None:
    результат = check(политика(), allowed_open={ОТКРЫТ}, allowed_closed=ЗАКРЫТЫЕ, live=None)
    assert not результат.allowed
    assert any("сравнивать кандидата не с чем" in b for b in результат.blockers)


def test_неизмеренный_домен_запрещает_выкладку() -> None:
    живое = dict(ЖИВОЕ_ШТАТНОЕ)
    del живое["animedia.icu"]
    результат = check(политика(), allowed_open={ОТКРЫТ}, allowed_closed=ЗАКРЫТЫЕ, live=живое)
    assert not результат.allowed
    assert any("выкладка вслепую запрещена" in b for b in результат.blockers)


def test_незапланированное_изменение_запрещает_выкладку() -> None:
    """Живой домен закрыт, кандидат его открывает, и никто этого не заявлял."""
    живое = dict(ЖИВОЕ_ШТАТНОЕ, **{ОТКРЫТ: CLOSED})
    результат = check(политика(), allowed_open={ОТКРЫТ}, allowed_closed=ЗАКРЫТЫЕ, live=живое)
    assert not результат.allowed
    assert any("незапланированное изменение" in b for b in результат.blockers)
    assert len(результат.changes) == 1, "изменение обязано быть видно в diff"
    assert результат.changes[0].domain == ОТКРЫТ
    assert результат.changes[0].before == CLOSED
    assert результат.changes[0].after == OPEN


def test_заявленное_изменение_проходит_и_видно_в_diff() -> None:
    живое = dict(ЖИВОЕ_ШТАТНОЕ, **{ОТКРЫТ: CLOSED})
    результат = check(
        политика(), allowed_open={ОТКРЫТ}, allowed_closed=ЗАКРЫТЫЕ,
        live=живое, approved_changes={ОТКРЫТ},
    )
    assert результат.allowed, результат.report()
    assert len(результат.changes) == 1
    строка = str(результат.changes[0])
    assert ОТКРЫТ in строка and "closed → open" in строка
    assert "владельца" in строка, "в diff обязано быть основание"


def test_кандидат_открывающий_лишний_домен_не_проходит() -> None:
    результат = check(
        политика(), allowed_open={ОТКРЫТ, "yummyani.org"},
        allowed_closed=ЗАКРЫТЫЕ - {"yummyani.org"}, live=ЖИВОЕ_ШТАТНОЕ,
    )
    assert not результат.allowed
    assert any("не открывает" in b for b in результат.blockers)


def test_домен_вне_разрешённой_матрицы_не_проходит() -> None:
    результат = check(
        политика(), allowed_open={ОТКРЫТ}, allowed_closed=ЗАКРЫТЫЕ - {"animedia.icu"},
        live=ЖИВОЕ_ШТАТНОЕ,
    )
    assert not результат.allowed
    assert any("нет в разрешённой матрице" in b for b in результат.blockers)


def test_обслуживаемый_домен_без_профиля_не_проходит() -> None:
    живое = dict(ЖИВОЕ_ШТАТНОЕ, **{"новый.example": CLOSED})
    результат = check(политика(), allowed_open={ОТКРЫТ}, allowed_closed=ЗАКРЫТЫЕ, live=живое)
    assert not результат.allowed
    assert any("профиля в кандидате нет" in b for b in результат.blockers)


def test_require_поднимает_исключение_с_отчётом() -> None:
    результат = check(политика(), allowed_open={ОТКРЫТ}, allowed_closed=ЗАКРЫТЫЕ, live=None)
    with pytest.raises(PolicyError, match="ворота релиза"):
        require(результат)


# --- промежуточное состояние --------------------------------------------------

def test_промежуточное_живое_состояние_не_основание_для_выкладки() -> None:
    """MIXED — не open и не closed: выкладывать поверх спора слоёв нельзя."""
    with pytest.raises(PolicyError, match="Промежуточное состояние"):
        matrix_from_live({ОТКРЫТ: "mixed"})


def test_живое_состояние_приводится_к_нижнему_регистру() -> None:
    assert matrix_from_live({"YummyAni.Site": "OPEN"}) == {"yummyani.site": OPEN}
