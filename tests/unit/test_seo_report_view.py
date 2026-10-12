"""REQ-SEO-REGULAR: вкладка отчёта показывает отчёт дня в 10:00 МСК и не повторяет старые."""

from __future__ import annotations

import datetime as dt
import importlib.util
from pathlib import Path

_SPEC = importlib.util.spec_from_file_location(
    "seo_report_view",
    Path(__file__).resolve().parents[2] / "automation" / "local" / "seo-report-view.py",
)
view = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(view)

UTC = dt.timezone.utc


def at(text: str) -> dt.datetime:
    return dt.datetime.fromisoformat(text).replace(tzinfo=UTC)


def test_report_waits_until_ten_moscow():
    # отчёт 2026-10-09 готов в 05:54 UTC, показ — в 07:00 UTC (10:00 МСК)
    assert view.decide(["2026-10-09"], at("2026-10-09T06:30:00"), "2026-10-08") == {}
    assert view.decide(["2026-10-09"], at("2026-10-09T07:00:30"), "2026-10-08") == {
        "show": "2026-10-09"
    }


def test_shown_report_is_not_repeated():
    assert view.decide(["2026-10-08", "2026-10-09"], at("2026-10-09T12:00:00"), "2026-10-09") == {}


def test_backlog_is_not_dumped_only_the_latest_is_shown():
    got = view.decide(
        ["2026-10-07", "2026-10-08", "2026-10-09"], at("2026-10-09T07:01:00"), "2026-10-06"
    )
    assert got == {"show": "2026-10-09"}


def test_missing_report_is_named_after_ten_past_ten():
    assert view.decide(["2026-10-08"], at("2026-10-09T07:05:00"), "2026-10-08") == {}
    assert view.decide(["2026-10-08"], at("2026-10-09T07:11:00"), "2026-10-08") == {
        "late": "2026-10-09"
    }


def test_late_report_is_shown_when_it_appears():
    assert view.decide(["2026-10-09"], at("2026-10-09T09:30:00"), "2026-10-08") == {
        "show": "2026-10-09"
    }


# --- где искать отчёты ------------------------------------------------------
#
# Прежняя редакция брала каталог ТОЛЬКО от своего файла. Запущенная из другого
# worktree, вкладка печатала «жду суточный отчёт… Последний показанный: нет» —
# бесконечно, при четырёх готовых отчётах в дереве службы. Молчание, похожее
# на ожидание, хуже отказа: по нему нельзя понять, что искали не там.


def test_явный_каталог_побеждает(tmp_path, monkeypatch):
    свой = tmp_path / "свой" / "var" / "seo-regular" / "reports" / "daily"
    свой.mkdir(parents=True)
    чужой = tmp_path / "чужой" / "var" / "seo-regular" / "reports" / "daily"
    чужой.mkdir(parents=True)
    monkeypatch.setenv("SEO_OPERATOR_ROOT", str(tmp_path / "чужой"))
    найдено, проверено = view.где_отчёты(str(свой))
    assert найдено == свой
    assert проверено[0] == свой


def test_переменная_окружения_используется(tmp_path, monkeypatch):
    """Путь к корню оператора уже объявлен переменной — чужой путь не в коде."""
    каталог = tmp_path / "var" / "seo-regular" / "reports" / "daily"
    каталог.mkdir(parents=True)
    monkeypatch.setenv("SEO_OPERATOR_ROOT", str(tmp_path))
    найдено, _ = view.где_отчёты(None)
    assert найдено == каталог


def test_несуществующий_каталог_не_молчит(tmp_path, monkeypatch, capsys):
    """Отказ с перечислением проверенных путей вместо бесконечного ожидания."""
    monkeypatch.setenv("SEO_OPERATOR_ROOT", str(tmp_path / "нет"))
    код = view.main(["--reports", str(tmp_path / "тоже-нет")])
    assert код == 2, "ожидание на несуществующем каталоге запрещено"
    ошибки = capsys.readouterr().err
    assert "не найден" in ошибки
    # Названы ВСЕ проверенные пути: иначе непонятно, что искали не там.
    assert str(tmp_path / "тоже-нет") in ошибки
    assert str(tmp_path / "нет") in ошибки


def test_пустой_но_существующий_каталог_это_не_отказ(tmp_path, monkeypatch):
    """Каталог есть, отчётов пока нет — это штатное ожидание, а не ошибка пути."""
    каталог = tmp_path / "var" / "seo-regular" / "reports" / "daily"
    каталог.mkdir(parents=True)
    monkeypatch.setenv("SEO_OPERATOR_ROOT", str(tmp_path))
    найдено, _ = view.где_отчёты(None)
    assert найдено == каталог
    assert view._available.__name__ == "_available"


def test_порядок_поиска_не_зависит_от_своего_дерева(tmp_path, monkeypatch):
    """Своё дерево — ПОСЛЕДНЯЯ надежда, а не первая: служба пишет в своё."""
    monkeypatch.delenv("SEO_OPERATOR_ROOT", raising=False)
    _найдено, проверено = view.где_отчёты(None)
    assert проверено[-1].parts[-4:] == ("var", "seo-regular", "reports", "daily")
    assert len(проверено) == 1, "без явного пути и переменной остаётся один путь"
