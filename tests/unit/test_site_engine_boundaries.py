"""Гейт границ обязан падать на намеренно неправильных фикстурах.

Гейт, который проходит всегда, ничего не проверяет. Здесь он сначала ломается
о заведомо неверный код, и только потом объявляется рабочим на настоящем.
"""
import json
import shutil
from pathlib import Path

import pytest

from factory.site_engine import boundaries

ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture
def песочница(tmp_path: Path) -> Path:
    """Копия реального устройства модулей, которую можно портить."""
    engine = tmp_path / "factory" / "site_engine"
    engine.mkdir(parents=True)
    for path in (ROOT / "factory" / "site_engine").rglob("*.py"):
        if "__pycache__" in path.parts:
            continue
        target = engine / path.relative_to(ROOT / "factory" / "site_engine")
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy(path, target)
    registry = tmp_path / "config" / "site-engine"
    registry.mkdir(parents=True)
    shutil.copy(ROOT / "config/site-engine/module-registry.json",
                registry / "module-registry.json")
    return tmp_path


class TestНастоящийКод:
    def test_границы_соблюдены(self):
        result = boundaries.check(ROOT)
        assert result.passed, "\n".join(result.problems)

    def test_проверено_не_ноль_файлов(self):
        """Гейт, ничего не открывший, тоже «проходит»."""
        result = boundaries.check(ROOT)
        assert result.checked_files >= 10
        assert result.checked_modules == 19


class TestНамеренноСломанное:
    def test_ядро_с_зависимостью_отклоняется(self, песочница: Path):
        """core-contracts обязан быть свободным от всех."""
        core = песочница / "factory/site_engine/contracts.py"
        core.write_text(
            "from factory.site_engine.providers import get\n" + core.read_text(encoding="utf-8"),
            encoding="utf-8",
        )
        result = boundaries.check(песочница)
        assert not result.passed
        assert any("core-contracts" in p for p in result.problems)

    def test_запрещённая_зависимость_отклоняется(self, песочница: Path):
        """Загрузчик, потянувший рендерер, — это ingestion, меняющий вёрстку."""
        path = песочница / "factory/site_engine/ingestion.py"
        path.write_text(
            "from factory.site_engine.renderers import get\n" + path.read_text(encoding="utf-8"),
            encoding="utf-8",
        )
        result = boundaries.check(песочница)
        assert not result.passed
        assert any("content-ingestion" in p and "renderer-adapters" in p
                   for p in result.problems)

    def test_хранилище_с_адаптером_поставщика_отклоняется(self, песочница: Path):
        """Хранилище, потянувшее адаптер, перестаёт быть владельцем данных."""
        path = песочница / "factory/site_engine/store.py"
        path.write_text(
            "from factory.site_engine.adapters.yummy import YummyWatcherAdapter\n"
            + path.read_text(encoding="utf-8"),
            encoding="utf-8",
        )
        result = boundaries.check(песочница)
        assert not result.passed
        assert any("normalized-content" in p and "provider-adapters" in p
                   for p in result.problems)

    def test_обход_публичного_интерфейса_пакета_отклоняется(self, песочница: Path):
        """`api.app` вместо `api` — связь с устройством, а не с интерфейсом."""
        path = песочница / "factory/site_engine/store.py"
        path.write_text(
            "from factory.site_engine.api.app import ApiResponse\n"
            + path.read_text(encoding="utf-8"),
            encoding="utf-8",
        )
        result = boundaries.check(песочница)
        assert not result.passed
        assert any("внутренности пакета" in p for p in result.problems)

    def test_внутри_своего_пакета_обращение_законно(self, песочница: Path):
        """`api/__init__` обязан импортировать `api/app` — иначе интерфейса нет."""
        assert boundaries.check(песочница).passed

    def test_имя_сайта_в_универсальном_модуле_отклоняется(self, песочница: Path):
        """Литерал имени сайта в ядре — настоящее нарушение, не оборот речи."""
        path = песочница / "factory/site_engine/store.py"
        path.write_text(
            path.read_text(encoding="utf-8") + '\nLORDS_SPECIAL_CASE = "lords-01"\n',
            encoding="utf-8",
        )
        result = boundaries.check(песочница)
        assert not result.passed
        assert any("lords" in p for p in result.problems)

    def test_имя_сайта_в_объяснении_нарушением_не_считается(self, песочница: Path):
        """Комментарий с причиной — не поведение. Причины ценнее чистоты текста."""
        path = песочница / "factory/site_engine/store.py"
        path.write_text(
            path.read_text(encoding="utf-8")
            + "\n# Так было сделано, потому что каталог Lords обрывался на 4800 записях.\n",
            encoding="utf-8",
        )
        assert boundaries.check(песочница).passed

    def test_несуществующая_реализация_отклоняется(self, песочница: Path):
        path = песочница / "config/site-engine/module-registry.json"
        data = json.loads(path.read_text(encoding="utf-8"))
        for module in data["modules"]:
            if module["id"] == "audit":
                module["implementation"] = "factory/site_engine/несуществующий.py"
        path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
        result = boundaries.check(песочница)
        assert not result.passed
        assert any("а файла нет" in p for p in result.problems)

    def test_contract_only_с_реализацией_отклоняется(self, песочница: Path):
        """Модуль либо описан контрактом, либо реализован. Третьего не заявляем."""
        path = песочница / "config/site-engine/module-registry.json"
        data = json.loads(path.read_text(encoding="utf-8"))
        for module in data["modules"]:
            if module["id"] == "catalog":
                module["implementation"] = "factory/site_engine/store.py"
        path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
        result = boundaries.check(песочница)
        assert not result.passed
        assert any("CONTRACT_ONLY" in p for p in result.problems)


class TestРеестр:
    def test_каждый_модуль_описан_полностью(self):
        registry = json.loads(
            (ROOT / "config/site-engine/module-registry.json").read_text(encoding="utf-8")
        )
        обязательные = (
            "id", "status", "purpose", "owns", "public_interface", "inputs", "outputs",
            "events", "depends_on", "forbidden", "errors", "metrics", "cache_tags",
        )
        for module in registry["modules"]:
            for field in обязательные:
                assert field in module, f"{module['id']}: нет поля {field}"
            assert module["purpose"].strip(), f"{module['id']}: назначение пустое"

    def test_зависимость_и_запрет_не_пересекаются(self):
        registry = json.loads(
            (ROOT / "config/site-engine/module-registry.json").read_text(encoding="utf-8")
        )
        for module in registry["modules"]:
            общее = set(module["depends_on"]) & set(module["forbidden"])
            assert not общее, f"{module['id']}: {общее} одновременно разрешено и запрещено"

    def test_статусы_из_закрытого_списка(self):
        registry = json.loads(
            (ROOT / "config/site-engine/module-registry.json").read_text(encoding="utf-8")
        )
        for module in registry["modules"]:
            assert module["status"] in ("IMPLEMENTED", "ADAPTED", "CONTRACT_ONLY")


class TestГраницыAPI:
    """API — тоже модуль, и его зависимости проверяются наравне с прочими.

    Пока файлы пакета `api` не были отнесены ни к какому модулю реестра, правило
    о запрещённых зависимостях к ним просто не применялось: гейт проходил, ничего
    об этом пакете не проверив.
    """

    def test_api_не_ходит_к_поставщику(self, песочница: Path):
        path = песочница / "factory/site_engine/api/app.py"
        path.write_text(
            "from factory.site_engine.providers import get\n"
            + path.read_text(encoding="utf-8"),
            encoding="utf-8",
        )
        result = boundaries.check(песочница)
        assert not result.passed
        assert any("site-engine-api" in p and "provider-adapters" in p
                   for p in result.problems)

    def test_api_не_запускает_обход(self, песочница: Path):
        path = песочница / "factory/site_engine/api/app.py"
        path.write_text(
            "from factory.site_engine.ingestion import IngestionService\n"
            + path.read_text(encoding="utf-8"),
            encoding="utf-8",
        )
        result = boundaries.check(песочница)
        assert not result.passed
        assert any("content-ingestion" in p for p in result.problems)

    def test_api_ничего_не_рендерит(self, песочница: Path):
        path = песочница / "factory/site_engine/api/app.py"
        path.write_text(
            "from factory.site_engine.renderers import get\n"
            + path.read_text(encoding="utf-8"),
            encoding="utf-8",
        )
        result = boundaries.check(песочница)
        assert not result.passed
        assert any("renderer-adapters" in p for p in result.problems)


class TestОбратнаяСовместимость:
    """Форма ответов — обязательство, а не подробность реализации."""

    def test_версия_схемы_модели_не_менялась_молча(self):
        from factory.site_engine.contracts import SCHEMA_VERSION

        assert SCHEMA_VERSION == "1.0", (
            "смена версии схемы — событие: потребители обязаны узнать о ней "
            "из версии, а не из отладки"
        )

    def test_обязательные_поля_события_на_месте(self):
        import json

        схема = json.loads(
            (ROOT / "schemas/site-engine/content-event.schema.json").read_text(encoding="utf-8")
        )
        assert set(схема["required"]) >= {
            "schema_version", "event_id", "event_type", "provider", "provider_id",
            "canonical_title_id", "observed_at", "idempotency_key", "payload",
        }

    def test_разделение_времён_сохранено(self):
        import json

        схема = json.loads(
            (ROOT / "schemas/site-engine/content-event.schema.json").read_text(encoding="utf-8")
        )
        assert "provider_timestamp" in схема["properties"]
        assert "observed_at" in схема["required"]
        assert "provider_timestamp" not in схема["required"], (
            "время поставщика обязательным быть не может: он сообщает его не всегда"
        )
