"""REQ-SEO-REPORT: сводный отчёт не умалчивает о том, чего в нём не показано.

Модуль уже отказывается выдавать частичный набор проверок за полный. Та же
честность нужна внутри одной проверки: таблица находок ограничена, и без явной
строки об остатке читатель принимает 200 показанных находок за все.
"""
from factory.seo.model import Finding, Report
from factory.seo.report import combine

TABLE_LIMIT = 200


def _report_with(count: int) -> Report:
    report = Report("seo-lint")
    for index in range(count):
        report.add(Finding("canonical", "minor", f"/page-{index}/", "тестовая находка"))
    return report


def test_full_table_carries_no_omission_note(tmp_path):
    combine("site-x", [_report_with(TABLE_LIMIT)], out_dir=tmp_path)
    assert "не показаны" not in (tmp_path / "seo-report.md").read_text(encoding="utf-8")


def test_truncated_table_says_how_many_are_hidden(tmp_path):
    combine("site-x", [_report_with(TABLE_LIMIT + 43)], out_dir=tmp_path)
    text = (tmp_path / "seo-report.md").read_text(encoding="utf-8")
    assert "не показаны" in text
    assert "43" in text


def test_json_keeps_every_finding_regardless_of_the_table(tmp_path):
    """Усечение — свойство читаемой таблицы, а не данных."""
    summary = combine("site-x", [_report_with(TABLE_LIMIT + 43)], out_dir=tmp_path)
    assert len(summary["reports"][0]["findings"]) == TABLE_LIMIT + 43
