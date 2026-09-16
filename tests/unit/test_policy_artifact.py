"""Артефакт политики: то, что переносит решение Core до витрины.

Витрина обязана знать, открыта ли она для поиска, на каждый отрисованный
ответ. Ходить за этим в Core на каждый пользовательский запрос нельзя: сеть
отказывает, а отказ сети решением закрыть сайт не является. Поэтому Core
читает управляющий слой, а витрина — готовый файл.

Здесь проверяется, что файл переносит решение и не принимает его: понижение
ревизии отклоняется, чужое решение не подменяет своё, публикация атомарна, а
смешение ревизий между поверхностями видно.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from factory.indexing import core_client as клиент
from factory.indexing import policy_artifact as арт

САЙТ = "yummyani-site"


def конверт(состояние: str, revision: int, *, digest: str = "d1",
            event: str = "e1", site_id: str = САЙТ) -> клиент.Envelope:
    return клиент.Envelope(
        contract_version=клиент.ПОДДЕРЖИВАЕМЫЙ_КОНТРАКТ,
        schema_version=клиент.ПОДДЕРЖИВАЕМАЯ_СХЕМА,
        provider_health=клиент.ЗДОРОВ, snapshot_digest="snap",
        taken_at="2026-09-16T00:00:00Z",
        sites={site_id: {
            "site_id": site_id, "desired_state": состояние, "revision": revision,
            "snapshot_digest": digest, "source_event_id": event,
            "schema_version": клиент.ПОДДЕРЖИВАЕМАЯ_СХЕМА,
        }},
    )


# --- сборка --------------------------------------------------------------------

def test_артефакт_собирается_из_ответа_core() -> None:
    а = арт.собрать(конверт(клиент.OPEN, 3), САЙТ)
    assert а.desired_state == клиент.OPEN
    assert а.indexing_revision == 3
    assert а.event_id == "e1"
    assert а.state_digest == "d1"
    assert а.schema_version == клиент.ПОДДЕРЖИВАЕМАЯ_СХЕМА


def test_сайта_нет_в_ответе_значит_артефакта_нет() -> None:
    """Подставить CLOSED было бы решением, которого никто не принимал."""
    with pytest.raises(арт.ArtifactError, match="такого сайта нет"):
        арт.собрать(конверт(клиент.OPEN, 1, site_id="другой"), САЙТ)


def test_запись_детерминирована(tmp_path: Path) -> None:
    а = арт.собрать(конверт(клиент.OPEN, 3), САЙТ)
    assert а.to_json() == а.to_json()


# --- публикация ----------------------------------------------------------------

def test_публикация_и_чтение(tmp_path: Path) -> None:
    цель = tmp_path / "indexing-policy.json"
    арт.опубликовать(арт.собрать(конверт(клиент.OPEN, 3), САЙТ), цель)
    прочитано = арт.прочитать(цель)
    assert прочитано.desired_state == клиент.OPEN
    assert прочитано.indexing_revision == 3


def test_понижение_ревизии_отклоняется(tmp_path: Path) -> None:
    """Старый релиз, кеш или копия не возвращают прежнее решение владельца."""
    цель = tmp_path / "p.json"
    арт.опубликовать(арт.собрать(конверт(клиент.CLOSED, 5, digest="d5"), САЙТ), цель)
    with pytest.raises(клиент.RevisionRegression, match="не откатывает"):
        арт.опубликовать(арт.собрать(конверт(клиент.OPEN, 3, digest="d3"), САЙТ), цель)
    assert арт.прочитать(цель).indexing_revision == 5
    assert арт.прочитать(цель).desired_state == клиент.CLOSED


def test_та_же_ревизия_с_тем_же_отпечатком_это_повтор(tmp_path: Path) -> None:
    цель = tmp_path / "p.json"
    а = арт.собрать(конверт(клиент.OPEN, 4, digest="x"), САЙТ)
    арт.опубликовать(а, цель)
    арт.опубликовать(а, цель)
    assert арт.прочитать(цель).indexing_revision == 4


def test_та_же_ревизия_с_другим_отпечатком_это_конфликт(tmp_path: Path) -> None:
    цель = tmp_path / "p.json"
    арт.опубликовать(арт.собрать(конверт(клиент.OPEN, 4, digest="x"), САЙТ), цель)
    with pytest.raises(арт.ArtifactError, match="другим отпечатком"):
        арт.опубликовать(арт.собрать(конверт(клиент.OPEN, 4, digest="y"), САЙТ), цель)


def test_большая_ревизия_применяется(tmp_path: Path) -> None:
    цель = tmp_path / "p.json"
    арт.опубликовать(арт.собрать(конверт(клиент.OPEN, 4, digest="x"), САЙТ), цель)
    арт.опубликовать(арт.собрать(конверт(клиент.CLOSED, 5, digest="y"), САЙТ), цель)
    assert арт.прочитать(цель).desired_state == клиент.CLOSED
    assert арт.прочитать(цель).indexing_revision == 5


def test_ABA_различается_по_ревизии(tmp_path: Path) -> None:
    """OPEN r10 → CLOSED r11 → OPEN r12: значение то же, ревизия другая."""
    цель = tmp_path / "p.json"
    арт.опубликовать(арт.собрать(конверт(клиент.OPEN, 10, digest="a"), САЙТ), цель)
    арт.опубликовать(арт.собрать(конверт(клиент.CLOSED, 11, digest="b"), САЙТ), цель)
    арт.опубликовать(арт.собрать(конверт(клиент.OPEN, 12, digest="c"), САЙТ), цель)
    assert арт.прочитать(цель).indexing_revision == 12
    with pytest.raises(клиент.RevisionRegression):
        арт.опубликовать(арт.собрать(конверт(клиент.OPEN, 10, digest="a"), САЙТ), цель)


def test_чужое_решение_не_подменяет_своё(tmp_path: Path) -> None:
    цель = tmp_path / "p.json"
    арт.опубликовать(арт.собрать(конверт(клиент.OPEN, 1), САЙТ), цель)
    чужой = арт.собрать(конверт(клиент.CLOSED, 9, site_id="lords-01"), "lords-01")
    with pytest.raises(арт.ArtifactError, match="чужое решение"):
        арт.опубликовать(чужой, цель)


def test_публикация_атомарна(tmp_path: Path) -> None:
    """Витрина не должна увидеть файл наполовину записанным."""
    цель = tmp_path / "p.json"
    арт.опубликовать(арт.собрать(конверт(клиент.OPEN, 1), САЙТ), цель)
    временные = [p for p in tmp_path.iterdir() if p.name != цель.name]
    assert not временные, f"остались временные файлы: {[p.name for p in временные]}"
    assert json.loads(цель.read_text(encoding="utf-8"))["desired_state"] == клиент.OPEN


def test_повторная_публикация_не_плодит_временных(tmp_path: Path) -> None:
    цель = tmp_path / "p.json"
    for n in range(1, 6):
        арт.опубликовать(арт.собрать(конверт(клиент.OPEN, n, digest=f"d{n}"), САЙТ), цель)
    assert list(tmp_path.iterdir()) == [цель]


# --- негодный артефакт ----------------------------------------------------------

def test_пустой_не_читается(tmp_path: Path) -> None:
    п = tmp_path / "p.json"
    п.write_text("  ", encoding="utf-8")
    with pytest.raises(арт.ArtifactError, match="пуст"):
        арт.прочитать(п)


def test_нечитаемый_не_применяется(tmp_path: Path) -> None:
    п = tmp_path / "p.json"
    п.write_text("{не json", encoding="utf-8")
    with pytest.raises(арт.ArtifactError, match="не разбирается"):
        арт.прочитать(п)


def test_частичный_не_является_артефактом(tmp_path: Path) -> None:
    цель = tmp_path / "p.json"
    арт.опубликовать(арт.собрать(конверт(клиент.OPEN, 1), САЙТ), цель)
    данные = json.loads(цель.read_text(encoding="utf-8"))
    del данные["indexing_revision"]
    цель.write_text(json.dumps(данные), encoding="utf-8")
    with pytest.raises(арт.ArtifactError, match="нет полей"):
        арт.прочитать(цель)


@pytest.mark.parametrize("поле, значение", [
    ("schema_version", "иное/9.9"),
    ("contract_version", "иное/9.9"),
])
def test_чужая_версия_не_применяется(tmp_path: Path, поле: str, значение: str) -> None:
    цель = tmp_path / "p.json"
    арт.опубликовать(арт.собрать(конверт(клиент.OPEN, 1), САЙТ), цель)
    данные = json.loads(цель.read_text(encoding="utf-8"))
    данные[поле] = значение
    цель.write_text(json.dumps(данные), encoding="utf-8")
    with pytest.raises(клиент.ContractDrift):
        арт.прочитать(цель)


def test_неизвестное_состояние_не_применяется(tmp_path: Path) -> None:
    цель = tmp_path / "p.json"
    арт.опубликовать(арт.собрать(конверт(клиент.OPEN, 1), САЙТ), цель)
    данные = json.loads(цель.read_text(encoding="utf-8"))
    данные["desired_state"] = "MAYBE"
    цель.write_text(json.dumps(данные), encoding="utf-8")
    with pytest.raises(арт.ArtifactError, match="не объявлено"):
        арт.прочитать(цель)


# --- согласованность поверхностей -----------------------------------------------

def test_одна_ревизия_на_все_поверхности() -> None:
    один = арт.собрать(конверт(клиент.OPEN, 5), САЙТ)
    арт.сверить([один, один, один])


def test_смешение_ревизий_видно() -> None:
    """Часть страниц по прежнему решению, часть по новому — и отличить это от
    нормальной работы потом невозможно."""
    with pytest.raises(арт.ArtifactError, match="разных ревизий"):
        арт.сверить([арт.собрать(конверт(клиент.OPEN, 5), САЙТ),
                     арт.собрать(конверт(клиент.OPEN, 6), САЙТ)])


def test_одна_ревизия_с_разными_отпечатками_видна() -> None:
    with pytest.raises(арт.ArtifactError, match="разными отпечатками"):
        арт.сверить([арт.собрать(конверт(клиент.OPEN, 5, digest="x"), САЙТ),
                     арт.собрать(конверт(клиент.OPEN, 5, digest="y"), САЙТ)])


# --- границы ответственности ----------------------------------------------------

def test_публикатор_не_принимает_решений() -> None:
    """Состояние берётся из ответа Core; своего у публикатора нет."""
    import factory.indexing.policy_artifact as модуль

    запретные = [имя for имя in dir(модуль)
                 if any(k in имя.lower() for k in
                        ("open_index", "close_index", "set_state", "решить"))]
    assert not запретные, f"в публикаторе появился писатель: {запретные}"
