"""B15 — гейт локальной матрицы адаптива и доступности.

Паспорт: ANIMEDIA_BLOCK_SPEC_V1/B15. Матрицу снимает
`automation/host/animedia-b15-matrix.py`: он поднимает настоящий сервер шаблона
на настоящем снимке каталога и измеряет живой DOM в Chromium на шести ширинах.
Здесь проверяется результат измерения, а не наличие правил в CSS — строка в
стиле не доказывает раскладку.

Тест читает уже снятую матрицу и падает, если её нет: заново поднимать браузер
в unit-прогоне нельзя, это минуты и внешняя зависимость. Матрица лежит в
доказательствах блока и обновляется командой из его отчёта.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
EV = ROOT / "artifacts/evidence/animedia-blockwise-parity-03-2026-09-20"
МАТРИЦА = EV / "03-blocks" / "B15" / "RESPONSIVE_MATRIX.json"
CONTRACT_SHA = (EV / "00-contract" / "CONTRACT_SHA256.txt").read_text(
    encoding="utf-8").strip()

ШИРИНЫ = [320, 390, 768, 1024, 1440, 1920]
МАРШРУТЫ = ["home", "catalog", "search", "collections", "collection_detail",
            "title", "episode", "not_found"]

#: Контрактные сетки. Ключ — (маршрут, признак сетки).
#: Каталог — B11 (2/4/6). Хаб подборок — B13 (1/2/3). Полка подборок на
#: главной (`zhub--home`) живёт по своему контракту B06.4 и здесь не
#: проверяется; общая сетка `.zg` на прочих страницах контрактных чисел не
#: имеет и проверяется только на монотонность.
ОЖИДАЕМЫЕ_КОЛОНКИ = {
    ("catalog", "zg-catalog"): {320: 2, 390: 2, 768: 4, 1024: 4, 1440: 6, 1920: 6},
    ("collections", "zhub"): {320: 1, 390: 1, 768: 2, 1024: 3, 1440: 3, 1920: 3},
}


def _признак(сетка: dict) -> str | None:
    классы = (сетка.get("classes") or сетка.get("cls") or "").split()
    if "zhub" in классы and "zhub--home" not in классы:
        return "zhub"
    if "zg" in классы and сетка.get("scope") == "catalog":
        return "zg-catalog"
    if "zg" in классы:
        return "zg-generic"
    return None


@pytest.fixture(scope="module")
def матрица() -> dict:
    if not МАТРИЦА.is_file():
        pytest.fail(
            "матрица адаптива не снята: запустите "
            ".venv/bin/python automation/host/animedia-b15-matrix.py "
            f"--out {EV.relative_to(ROOT)}/03-blocks/B15 --shots")
    return json.loads(МАТРИЦА.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def ячейки(матрица: dict) -> dict:
    return {(c["route"], c["width"]): c for c in матрица["cells"]}


def test_contract_digest_unchanged() -> None:
    assert CONTRACT_SHA == (
        "5f2112e25ef974333c388bad405abfae3c3d460a713b028afa3c0e549b8eaeb3")


def test_matrix_covers_every_route_and_width(матрица, ячейки):
    assert матрица["viewports"] == ШИРИНЫ
    assert матрица["routes"] == МАРШРУТЫ
    assert len(матрица["cells"]) == len(ШИРИНЫ) * len(МАРШРУТЫ) == 48
    for маршрут in МАРШРУТЫ:
        for ширина in ШИРИНЫ:
            assert (маршрут, ширина) in ячейки, (маршрут, ширина)


def test_matrix_was_measured_in_a_browser_on_the_real_snapshot(матрица):
    assert матрица["browser"] == "chromium"
    # Снимок именно тот, что лежит на хосте, а не фикстура.
    assert матрица["snapshot"]["catalog"].endswith("animedia-01-catalog.json")
    assert матрица["snapshot"]["details"].endswith("animedia-01-details.json")
    assert len(матрица["source_commit"]) == 40


def test_matrix_was_measured_against_the_current_source(матрица):
    """Матрица обязана описывать те байты, что лежат в дереве сейчас.

    Одного `source_commit` для этого мало: правки могут быть ещё не
    зафиксированы, и тогда метка назвала бы коммит, который не измеряли.
    Поэтому стенд пишет цифру измеренного артефакта, а гейт её сверяет — иначе
    зелёная матрица могла бы относиться к прошлой вёрстке.
    """
    import hashlib

    цифра = матрица.get("measured_artifact_sha256")
    assert цифра, (
        "в матрице нет цифры измеренного артефакта — пересоздайте её стендом")
    файл = ROOT / "automation/host/lords-frontend.py"
    assert цифра == hashlib.sha256(файл.read_bytes()).hexdigest(), (
        "матрица снята с другой версии шаблона: пересоздайте её стендом")


def test_http_status_per_route(ячейки):
    for (маршрут, ширина), c in ячейки.items():
        ожидаем = 404 if маршрут == "not_found" else 200
        assert c["http"] == ожидаем, (маршрут, ширина, c["http"])


def test_no_horizontal_overflow_anywhere(ячейки):
    плохие = {k: (c["overflow_px"], c["overflow_offenders"][:2])
              for k, c in ячейки.items() if c["overflow_px"] > 1}
    assert плохие == {}, плохие


def test_no_required_text_is_clipped(ячейки):
    плохие = {k: c["clipped_required"] for k, c in ячейки.items()
              if c["clipped_required"]}
    assert плохие == {}, плохие


def test_no_card_title_is_cut_by_its_box(ячейки):
    """Заголовок карточки может переноситься, но не срезаться краем."""
    плохие = {k: c.get("card_title_overflow") for k, c in ячейки.items()
              if c.get("card_title_overflow")}
    assert плохие == {}, плохие


def test_no_timestamp_ellipsis(ячейки):
    плохие = {k: c["timestamp_ellipsis"] for k, c in ячейки.items()
              if c["timestamp_ellipsis"]}
    assert плохие == {}, плохие


def test_poster_frames_are_two_to_three(ячейки):
    нарушения = []
    всего = 0
    for k, c in ячейки.items():
        for p in c["posters"]:
            всего += 1
            if not 0.64 <= p["ratio"] <= 0.69:
                нарушения.append((k, p))
    assert всего > 0, "постеров не измерено — матрица пуста"
    assert нарушения == [], нарушения[:5]


def test_no_broken_images(ячейки):
    плохие = {k: c["broken_images"] for k, c in ячейки.items() if c["broken_images"]}
    assert плохие == {}, плохие


def test_no_empty_visible_blocks(ячейки):
    плохие = {k: c["empty_visible_blocks"] for k, c in ячейки.items()
              if c["empty_visible_blocks"]}
    assert плохие == {}, плохие


def test_no_unexplained_gap_over_96px(ячейки):
    плохие = {k: c["gaps_over_96"] for k, c in ячейки.items() if c["gaps_over_96"]}
    assert плохие == {}, плохие


def test_no_grid_overlaps(ячейки):
    плохие = {k: c["grid_overlaps"] for k, c in ячейки.items() if c["grid_overlaps"]}
    assert плохие == {}, плохие


def test_grid_columns_follow_the_block_contracts(ячейки):
    расхождения = []
    проверено = 0
    for (маршрут, ширина), c in ячейки.items():
        for сетка in c["grids"]:
            признак = _признак(сетка)
            ожидание = ОЖИДАЕМЫЕ_КОЛОНКИ.get((маршрут, признак), {}).get(ширина)
            if ожидание is None:
                continue
            # Сетка, в которой карточек меньше, чем колонок, о колонках
            # ничего не говорит.
            if сетка["count"] < ожидание:
                continue
            проверено += 1
            if сетка["cols"] != ожидание:
                расхождения.append((маршрут, ширина, признак,
                                    сетка["cols"], ожидание))
    assert проверено > 0, "ни одной контрактной сетки не проверено"
    assert расхождения == [], расхождения[:8]


def test_grid_columns_never_shrink_as_the_screen_grows(ячейки):
    """Общая сетка своих контрактных чисел не имеет, но шире экран — не меньше
    колонок. Обратное означало бы перекрывающиеся media-запросы."""
    по_маршруту: dict[tuple[str, str], dict[int, int]] = {}
    for (маршрут, ширина), c in ячейки.items():
        for сетка in c["grids"]:
            признак = _признак(сетка)
            if признак is None or сетка["count"] < 6:
                continue
            по_маршруту.setdefault((маршрут, признак), {})[ширина] = сетка["cols"]
    проверено = 0
    for ключ, по_ширине in по_маршруту.items():
        ширины = sorted(по_ширине)
        for a, b in zip(ширины, ширины[1:]):
            проверено += 1
            assert по_ширине[b] >= по_ширине[a], (ключ, a, по_ширине[a], b, по_ширине[b])
    assert проверено > 0


def test_exactly_one_player_and_sixteen_by_nine(ячейки):
    рамок = 0
    for (маршрут, ширина), c in ячейки.items():
        assert c["player_instances"] <= 1, (маршрут, ширина, c["player_instances"])
        for f in c["player_frames"]:
            рамок += 1
            ошибка = abs(f["ratio"] - 16 / 9) / (16 / 9) * 100
            assert ошибка <= 1, (маршрут, ширина, f, ошибка)
    assert рамок > 0, "рамка плеера не измерена ни на одной странице"


def test_autoplay_is_off_and_declared_off(ячейки):
    включён = {k: c["autoplay_attrs"] for k, c in ячейки.items() if c["autoplay_attrs"]}
    assert включён == {}, включён
    # Выключенность именно объявлена, а не просто отсутствует атрибут.
    assert sum(c.get("autoplay_declared_off", 0) for c in ячейки.values()) > 0


def test_one_h1_per_page(ячейки):
    плохие = {k: c["h1_count"] for k, c in ячейки.items() if c["h1_count"] != 1}
    assert плохие == {}, плохие


def test_header_and_footer_present_everywhere(ячейки):
    for k, c in ячейки.items():
        assert c["header_present"], k
        assert c["footer_present"], k


def test_header_height_within_b01_band(ячейки):
    плохие = {k: c["header_h"] for k, c in ячейки.items()
              if not 56 <= c["header_h"] <= 80}
    assert плохие == {}, плохие


def test_footer_height_within_b14_band_on_desktop(ячейки):
    """Полоса 220–300 применяется ко всем десктопным ширинам списка B15.

    Порог четырёх колонок специально опущен до 1024px, иначе 1024 получала
    планшетную раскладку и паспортная полоса высоты на ней не проверялась бы
    вовсе.
    """
    плохие = {k: c["footer_h"] for k, c in ячейки.items()
              if k[1] >= 1024 and not 220 <= c["footer_h"] <= 300}
    assert плохие == {}, плохие


def test_mobile_drawer_toggle_is_present(ячейки):
    for (маршрут, ширина), c in ячейки.items():
        if ширина <= 768:
            assert c["drawer_toggle_present"], (маршрут, ширина)


def test_indexability_is_closed_on_every_cell(ячейки):
    for k, c in ячейки.items():
        assert c["robots"] and "noindex" in c["robots"], (k, c["robots"])


def test_canonical_present_on_200_and_absent_on_404(ячейки):
    for (маршрут, ширина), c in ячейки.items():
        if маршрут == "not_found":
            assert not c["canonical"], (маршрут, ширина, c["canonical"])
        else:
            assert c["canonical"], (маршрут, ширина)
