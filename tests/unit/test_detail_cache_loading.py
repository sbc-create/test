"""Чтение кэша detail-данных: один загрузчик, и битый файл не исчезает молча.

Один и тот же цикл — обойти `var/lords/detail-cache/*.json`, разобрать, битые
пропустить — скопирован дословно в три сценария. Копия расходится с копией
незаметно: ровно так очистка каталога выгрузки оказалась забыта в двух точках
вызова из четырёх.

Второе: битый файл пропускался через `except Exception: continue`, не оставляя
следа. Кэш обогащения — 12 010 файлов, и если часть из них перестала
разбираться, витрина беднеет ровно настолько же. Разница между «данных нет у
источника» и «файл кэша испорчен» существенна: первое неисправимо, второе
чинится перезаписью кэша. Молчание делает их неразличимыми.

Загрузчик обязан пропустить битое и назвать, сколько пропустил.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from factory.lords import detail_enrichment  # noqa: E402


def _cache(tmp_path: Path, files: dict[str, str]) -> Path:
    for имя, тело in files.items():
        (tmp_path / имя).write_text(тело, encoding="utf-8")
    return tmp_path


class TestЗагрузкаКэша:
    def test_целые_записи_читаются(self, tmp_path):
        _cache(tmp_path, {
            "a.json": json.dumps({"detail": {"id": "42", "name": "Пример"}}),
            "b.json": json.dumps({"detail": {"id": "43", "name": "Другое"}}),
        })
        details, битые = detail_enrichment.load_cached_details(tmp_path)
        assert sorted(details) == ["42", "43"]
        assert битые == []

    def test_битый_файл_пропускается_и_назван(self, tmp_path):
        _cache(tmp_path, {
            "ok.json": json.dumps({"detail": {"id": "1"}}),
            "плохой.json": "{не json",
        })
        details, битые = detail_enrichment.load_cached_details(tmp_path)
        assert list(details) == ["1"], "целые записи обязаны дойти"
        assert битые == ["плохой.json"], "битый файл обязан быть назван, а не исчезнуть"

    def test_запись_без_detail_не_попадает(self, tmp_path):
        _cache(tmp_path, {"пусто.json": json.dumps({"detail": None})})
        details, битые = detail_enrichment.load_cached_details(tmp_path)
        assert details == {}
        assert битые == [], "отсутствие поля — не порча файла"

    def test_ключом_служит_имя_файла_если_id_нет(self, tmp_path):
        _cache(tmp_path, {"777.json": json.dumps({"detail": {"name": "Без ид"}})})
        details, _ = detail_enrichment.load_cached_details(tmp_path)
        assert list(details) == ["777"]

    def test_отсутствующий_каталог_не_ошибка(self, tmp_path):
        details, битые = detail_enrichment.load_cached_details(tmp_path / "нет")
        assert details == {} and битые == []

    def test_нечитаемое_содержимое_не_роняет_разбор(self, tmp_path):
        """Обрезанный файл — обычное состояние кэша, прерванного на записи."""
        _cache(tmp_path, {"обрезан.json": '{"detail": {"id": "9"'})
        details, битые = detail_enrichment.load_cached_details(tmp_path)
        assert details == {} and битые == ["обрезан.json"]


class TestОдинЗагрузчикНаВсехПотребителей:
    def test_сценарии_не_держат_собственных_копий(self):
        """Три копии одного цикла расходятся молча — здесь их быть не должно."""
        свои = []
        for имя in ("scripts/build_live_search_stand.py",
                    "scripts/build_product_preview.py",
                    "scripts/lords_chain_audit.py"):
            текст = (ROOT / имя).read_text(encoding="utf-8")
            if "DETAIL_CACHE.glob" in текст:
                свои.append(имя)
        assert свои == [], f"собственная копия обхода кэша осталась в: {свои}"
