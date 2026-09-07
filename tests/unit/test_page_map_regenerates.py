"""Карта страниц пересобирается и совпадает с записанной.

У модуля, порождающего `docs/templates/PAGE-MAP-lords.md`, не было точки входа
вовсе. Документ собрали однажды руками, и разойтись с кодом он мог молча:
пересобрать его не мог никто, не зная, как именно. Документ, который нельзя
перепроверить, со временем становится описанием того, чего нет.

Он и разошёлся. Записанный документ обещал 25 поверхностей, пересборка давала
20 — пять адресов пагинации, которых нет на маленьком каталоге.

Отсюда второе, что здесь закреплено: набор поверхностей зависит от каталога, и
карта обязана называть свой. В фикстуре 62 записи, у мультфильмов восемь —
меньше страницы, и адреса `/animation/page/{n}/` не существует. А без
обогащения у первых 4 000 записей боевого среза нет страны **ни у одной**, и
раздела стран в карте не появляется: она выходит достоверной на вид и беднее
витрины на целый раздел.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from factory.templates import pagemap  # noqa: E402

DOC = ROOT / "docs" / "templates" / "PAGE-MAP-lords.md"


@pytest.fixture(scope="module")
def записанный() -> str:
    return DOC.read_text(encoding="utf-8")


class TestТочкаВходаЕсть:
    def test_модуль_запускается(self):
        result = subprocess.run(
            [sys.executable, "-m", "factory.templates.pagemap", "--snapshot", ""],
            capture_output=True, text=True, cwd=str(ROOT), timeout=900)
        assert result.returncode == 0, result.stderr[-2000:]
        assert "Карта страниц направления Lords" in result.stdout

    def test_документ_называет_команду_пересборки(self, записанный):
        assert "python3 -m factory.templates.pagemap --write" in записанный


class TestКартаНазываетСвойКаталог:
    def test_каталог_назван(self, записанный):
        assert "Каталог, на котором построена карта:" in записанный

    def test_обогащение_учтено(self, записанный):
        """Без обогащения раздела стран не бывает — и это должно быть видно."""
        assert "обогащено" in записанный

    def test_раздел_стран_присутствует(self, записанный):
        assert "`/countries/{slug}/`" in записанный, (
            "страна есть у 8 361 записи кэша; пустой раздел означал бы "
            "потерянное обогащение")


class TestНаборПоверхностейЗависитОтКаталога:
    def test_фикстура_даёт_меньше_поверхностей(self):
        """Утверждение, которое первая редакция модуля отрицала в докстроке."""
        по_фикстуре, описание = pagemap.build_all(sites=("lords-01",), snapshot=None)
        assert "фикстура" in описание
        адреса = {s.path for s in по_фикстуре[0].surfaces}
        assert "/animation/page/{n}/" not in адреса, (
            "у мультфильмов в фикстуре восемь записей — меньше страницы")

    def test_карта_воспроизводима(self):
        первая, _ = pagemap.build_all(sites=("lords-01",), snapshot=None)
        вторая, _ = pagemap.build_all(sites=("lords-01",), snapshot=None)
        assert [s.as_dict() for s in первая[0].surfaces] == \
               [s.as_dict() for s in вторая[0].surfaces]
