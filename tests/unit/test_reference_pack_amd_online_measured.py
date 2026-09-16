"""Пакет amd-online несёт замеры, а не описание замеров.

Пакет существовал черновиком с пустыми токенами: доступ к референсу отклонялся
профилем, и записать туда было нечего. Пустой файл тогда был честнее
заполненного. После открытия доступа появилась обратная опасность — заполнить
токены правдоподобными числами и объявить пакет готовым.

Поэтому здесь проверяется не наличие полей, а их происхождение: у каждого
токена есть единица, поверхность, ширина, метод, ссылка на доказательство и
допуск; доказательство разрешается в существующий файл; плейсхолдеров нет.

Отдельно закреплено то, что пакет пока НЕ сертифицирован: диапазоны
совместимости остаются `pending`, а утверждённого алгоритма визуального
сравнения в репозитории нет. Оба факта обязаны быть видимыми, а не
подразумеваемыми: именно их незаметность превращает черновик в «почти готовый»
пакет, на который потом ссылаются как на эталон.
"""

from __future__ import annotations

import json
import re

import pytest
import yaml

from factory.paths import PATHS

ПАКЕТ = PATHS.root / "docs" / "reference-packs" / "amd-online"
ТОКЕНЫ = ПАКЕТ / "VISUAL_TOKENS.yaml"
МАНИФЕСТ = ПАКЕТ / "TemplateManifest.yaml"
ПЛАН = PATHS.root / "config" / "reference-packs" / "reference-pack.amd-online.json"

#: Ширины, обязательные для матрицы снимков.
ШИРИНЫ = {390, 768, 1440}

#: Поверхности, снятые с самого референса.
ПОВЕРХНОСТИ = {"home", "catalog", "collection_hub", "title", "not_found"}

#: Значения, которыми заполняют поле, когда измерить не смогли.
ЗАГЛУШКИ = {"", "TODO", "todo", "pending", "unknown", "n/a", "N/A", "-", "0", None}


@pytest.fixture(scope="module")
def токены() -> dict:
    return yaml.safe_load(ТОКЕНЫ.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def манифест() -> dict:
    return yaml.safe_load(МАНИФЕСТ.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def план() -> dict:
    return json.loads(ПЛАН.read_text(encoding="utf-8"))


def test_токены_не_пусты(токены):
    """Пустой `tokens: {}` был честен при закрытом доступе и недопустим сейчас."""
    assert токены.get("status") == "measured"
    assert токены.get("tokens"), "токенов нет: пакет снова стал описанием вместо замера"
    assert len(токены["tokens"]) == токены["tokens_total"]
    assert len(токены["tokens"]) >= 100, "замеров слишком мало для пяти поверхностей"


def test_у_каждого_токена_есть_происхождение(токены):
    """Число без метода и ссылки на доказательство неотличимо от догадки."""
    обязательные = ("name", "value", "unit", "surface", "viewport", "method",
                    "evidence", "tolerance", "status")
    for т in токены["tokens"]:
        нет = [п for п in обязательные if п not in т]
        assert not нет, f"{т.get('name')}: нет полей {нет}"
        assert т["status"] == "measured_by_factory"
        assert т["viewport"] in ШИРИНЫ, f"{т['name']}: ширина {т['viewport']} вне матрицы"


def test_значения_не_заглушки(токены):
    """Плейсхолдер в поле замера — это догадка, которую через неделю не отличить."""
    плохие = [т["name"] for т in токены["tokens"]
              if not isinstance(т["value"], bool) and т["value"] in ЗАГЛУШКИ]
    assert not плохие, f"значения-заглушки: {плохие[:5]}"


def test_доказательство_разрешается_в_файл(токены):
    """Ссылка на доказательство обязана указывать на существующий файл.

    Снимки и сырые замеры лежат в evidence-каталоге задания и в git не входят
    (`artifacts/*` в .gitignore). Поэтому проверяется форма ссылки и то, что
    она указывает внутрь этого каталога, а не в произвольное место.
    """
    for т in токены["tokens"]:
        ссылка = str(т["evidence"]).split("#")[0]
        assert ссылка.startswith("artifacts/reference-pack-amd-online-01/"), (
            f"{т['name']}: доказательство вне каталога задания — {ссылка}")
        assert ссылка.endswith((".json", ".png")), f"{т['name']}: странная ссылка {ссылка}"


def test_матрица_поверхностей_и_ширин_полна(токены):
    """Каждая поверхность снята на каждой обязательной ширине."""
    пары = {(т["surface"], т["viewport"]) for т in токены["tokens"]}
    нет = [(п, ш) for п in ПОВЕРХНОСТИ for ш in ШИРИНЫ if (п, ш) not in пары]
    assert not нет, f"в матрице не хватает: {нет}"


def test_у_каждого_снимка_есть_дайджест(токены):
    """Снимок без SHA-256 нельзя сверить при независимой проверке."""
    дайджесты = [т for т in токены["tokens"] if т["name"] == "screenshot_sha256"]
    assert len(дайджесты) == len(ПОВЕРХНОСТИ) * len(ШИРИНЫ)
    for д in дайджесты:
        assert re.fullmatch(r"[0-9a-f]{64}", str(д["value"])), f"не sha256: {д['value']}"


def test_доступ_к_референсу_записан_замером(план):
    """Статус доступа меняется доказательством, а не решением."""
    assert план["access"]["status"] == "reachable"
    assert "REF-EGRESS-01" in план["access"]["detail"]
    assert "availability.json" in план["access"]["detail"], (
        "снятие блокера обязано ссылаться на проверку доступности")


def test_наблюдения_повышены_только_измеренные(план):
    """`measured_by_factory` ставится после прогона, а не авансом."""
    for о in план["observations"]:
        assert о["verified"] in ("measured_by_factory", "unverified")
        if о["verified"] == "measured_by_factory":
            assert "measurement" in о["source"] or "замер" in о["source"], (
                f"{о['parameter']}: статус измеренного без ссылки на замер")


def test_пакет_не_объявляет_себя_сертифицированным(манифест):
    """Автор пакета не принимает собственную работу.

    Замеры появились, но диапазоны совместимости — решение владельца контракта,
    а утверждённого алгоритма сравнения в репозитории нет. Пока так, статус
    обязан оставаться черновиком: «почти готовый» пакет опаснее пустого, потому
    что на него ссылаются как на эталон.
    """
    assert манифест["status"] == "draft"
    assert манифест["productionEnabled"] is False
    assert манифест["indexingEnabled"] is False
    assert манифест["compatibility"]["status"] == "pending"


def test_блокер_доступа_снят_в_манифесте(манифест):
    """Прежняя причина черновика больше не соответствует состоянию."""
    assert манифест["reference"]["access"] == "reachable"
    assert манифест["reference"]["blocker"] is None
    assert манифест["reference"]["measuredTokens"] >= 100


def test_исключения_объявлены_заранее():
    """Разделение областей — до сравнения, а не после неудобного результата."""
    текст = (ПАКЕТ / "EXCLUSIONS.md").read_text(encoding="utf-8")
    for раздел in ("IN_SCOPE_PRODUCT_STRUCTURE", "OUT_OF_SCOPE_ADS_AND_TRACKERS",
                   "OUT_OF_SCOPE_THIRD_PARTY_WIDGETS", "FORBIDDEN_TO_COPY"):
        assert раздел in текст, f"в исключениях нет раздела {раздел}"


def test_в_пакете_нет_чужих_ассетов():
    """Из чужого интерфейса переносимы только числа и порядок разделов."""
    запрещено = (".png", ".jpg", ".jpeg", ".webp", ".svg", ".woff", ".woff2", ".css")
    найдено = [p.name for p in ПАКЕТ.rglob("*") if p.suffix.lower() in запрещено]
    assert not найдено, f"в пакете лежат чужие ассеты: {найдено}"
