"""Новый сайт фабрики и жизненный цикл выкладки политики.

Исправление обязано работать не только для девяти нынешних доменов. Десятый
сайт, заведённый завтра, должен быть закрыт, пока владелец не откроет его
отдельным изменением его профиля, — и его появление не должно ничего изменить у
остальных девяти.

Вторая половина файла — жизненный цикл: сборка, повторная сборка, откат и
повторное применение. Политика обязана переживать всё это без дрейфа, иначе
«работает сейчас» ничего не говорит о том, что будет после ближайшего рестарта.
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest

from factory.indexing import CLOSED, OPEN, PolicyError, compile_policy
from factory.indexing.artifact import build, load, write
from factory.indexing.gate import check, require

КОРЕНЬ = Path(__file__).resolve().parents[2]
ПРОФИЛИ = КОРЕНЬ / "config" / "site-profiles"

ОТКРЫТ = "yummyani.site"
ДЕВЯТЬ = {
    ОТКРЫТ, "yummyani.org", "yummyani.biz", "lordfilm47.space", "lordserial33.biz",
    "1lordserials1.online", "zonafilm.space", "animedia.icu", "animedia.space",
}
ЗАКРЫТЫЕ = ДЕВЯТЬ - {ОТКРЫТ}


@pytest.fixture
def песочница(tmp_path: Path) -> Path:
    """Копия реальных профилей, которую можно менять."""
    d = tmp_path / "site-profiles"
    d.mkdir()
    for путь in ПРОФИЛИ.glob("*.json"):
        shutil.copy2(путь, d / путь.name)
    return d


def завести_домен(каталог: Path, site_id: str, домен: str, *, expected: str = CLOSED) -> Path:
    """То, что делает генератор нового сайта фабрики."""
    профиль = {
        "schema_version": "1.0",
        "site_id": site_id,
        "domains": [домен],
        "canonical_domain": домен,
        "environment": "production",
        "profile_family": "новое-семейство",
        "profile_version": "1.0",
        "seo_profile": {
            "indexing_expected": expected,
            "indexing_reason": "новый сайт фабрики: решения об открытии нет",
        },
    }
    путь = каталог / f"{site_id}.json"
    путь.write_text(json.dumps(профиль, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return путь


# --- десятый домен ------------------------------------------------------------

def test_новый_домен_закрыт_до_явного_разрешения(песочница: Path) -> None:
    завести_домен(песочница, "tenth-site", "tenth.example")
    политика = compile_policy(песочница)
    assert политика.is_open("tenth.example") is False
    assert политика.decide("tenth.example").expected == CLOSED


def test_появление_нового_домена_не_меняет_остальные_девять(песочница: Path) -> None:
    до = compile_policy(песочница).matrix()
    завести_домен(песочница, "tenth-site", "tenth.example")
    после = compile_policy(песочница)
    assert после.open_domains == (ОТКРЫТ,), "десятый домен не должен ничего открывать"
    assert set(после.closed_domains) == ЗАКРЫТЫЕ | {"tenth.example"}
    assert до["open"] == после.matrix()["open"]


def test_открыть_новый_домен_можно_только_его_профилем(песочница: Path) -> None:
    путь = завести_домен(песочница, "tenth-site", "tenth.example")
    assert compile_policy(песочница).is_open("tenth.example") is False

    данные = json.loads(путь.read_text(encoding="utf-8"))
    данные["seo_profile"]["indexing_expected"] = OPEN
    данные["seo_profile"]["indexing_reason"] = "решение владельца от такого-то числа"
    путь.write_text(json.dumps(данные, ensure_ascii=False), encoding="utf-8")

    политика = compile_policy(песочница)
    assert политика.is_open("tenth.example") is True
    assert set(политика.open_domains) == {ОТКРЫТ, "tenth.example"}


def test_удаление_профиля_известного_домена_блокирует_выкладку(песочница: Path) -> None:
    """Домен обслуживается, профиля нет — deploy обязан остановиться."""
    завести_домен(песочница, "tenth-site", "tenth.example")
    (песочница / "tenth-site.json").unlink()
    with pytest.raises(PolicyError, match="без профиля"):
        compile_policy(песочница, expected_domains=ДЕВЯТЬ | {"tenth.example"})


def test_новый_домен_виден_в_diff_ворот(песочница: Path) -> None:
    """Появление домена в матрице обязано быть видимым изменением."""
    завести_домен(песочница, "tenth-site", "tenth.example")
    живое = {d: (OPEN if d == ОТКРЫТ else CLOSED) for d in ДЕВЯТЬ}
    результат = check(
        compile_policy(песочница), allowed_open={ОТКРЫТ},
        allowed_closed=ЗАКРЫТЫЕ, live=живое,
    )
    assert not результат.allowed
    assert any("tenth.example" in b for b in результат.blockers)


# --- жизненный цикл -----------------------------------------------------------

def test_повторная_сборка_даёт_тот_же_артефакт(песочница: Path, tmp_path: Path) -> None:
    первый = write(build(песочница), tmp_path / "a.json")
    второй = write(build(песочница), tmp_path / "b.json")
    assert первый.read_bytes() == второй.read_bytes()


def test_повторное_применение_идемпотентно(песочница: Path, tmp_path: Path) -> None:
    """Выложить тот же артефакт дважды — не то же самое, что выложить другой."""
    путь = tmp_path / "indexing-policy.json"
    write(build(песочница), путь)
    первое = load(путь).matrix()
    write(build(песочница), путь)
    второе = load(путь).matrix()
    assert первое == второе


def test_откат_возвращает_ровно_исходную_матрицу(песочница: Path, tmp_path: Path) -> None:
    """Полный круг: базовая линия → кандидат → проверка → откат → та же линия."""
    цель = tmp_path / "indexing-policy.json"
    база = write(build(песочница), цель).read_bytes()
    база_матрица = load(цель).matrix()

    # кандидат: открыли соседний домен
    профиль = песочница / "yummyani-org.json"
    прежнее = профиль.read_text(encoding="utf-8")
    данные = json.loads(прежнее)
    данные["seo_profile"]["indexing_expected"] = OPEN
    профиль.write_text(json.dumps(данные, ensure_ascii=False), encoding="utf-8")
    write(build(песочница), цель)
    assert load(цель).matrix()["open_count"] == 2, "кандидат обязан отличаться"

    # откат
    профиль.write_text(прежнее, encoding="utf-8")
    откат = write(build(песочница), цель).read_bytes()

    assert откат == база, "откат обязан вернуть артефакт байт в байт"
    assert load(цель).matrix() == база_матрица


def test_повторное_применение_кандидата_после_отката(песочница: Path, tmp_path: Path) -> None:
    цель = tmp_path / "indexing-policy.json"
    write(build(песочница), цель)
    первый_отпечаток = build(песочница)["manifest"]["policy_sha256"]

    профиль = песочница / "yummyani-org.json"
    прежнее = профиль.read_text(encoding="utf-8")
    данные = json.loads(прежнее)
    данные["seo_profile"]["indexing_expected"] = OPEN
    кандидат_текст = json.dumps(данные, ensure_ascii=False)

    профиль.write_text(кандидат_текст, encoding="utf-8")
    кандидат_отпечаток = build(песочница)["manifest"]["policy_sha256"]
    профиль.write_text(прежнее, encoding="utf-8")
    assert build(песочница)["manifest"]["policy_sha256"] == первый_отпечаток
    профиль.write_text(кандидат_текст, encoding="utf-8")
    assert build(песочница)["manifest"]["policy_sha256"] == кандидат_отпечаток


def test_полный_цикл_проходит_ворота(песочница: Path, tmp_path: Path) -> None:
    """Сборка → ворота → артефакт → чтение обратно → та же матрица."""
    живое = {d: (OPEN if d == ОТКРЫТ else CLOSED) for d in ДЕВЯТЬ}
    политика = compile_policy(песочница, expected_domains=ДЕВЯТЬ)
    require(check(политика, allowed_open={ОТКРЫТ}, allowed_closed=ЗАКРЫТЫЕ, live=живое))
    путь = write(build(песочница, expected_domains=ДЕВЯТЬ), tmp_path / "p.json")
    восстановлено = load(путь)
    assert восстановлено.matrix() == политика.matrix()
