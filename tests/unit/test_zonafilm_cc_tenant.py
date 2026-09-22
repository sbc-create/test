"""Границы контура zonafilm.cc проверяются, а не декларируются.

`TENANT.yaml` объявляет, куда этому контуру можно писать и чего он не трогает.
Объявление без проверки — это обещание. Здесь оно превращается в утверждение о
фактическом состоянии стенда.

Проверяется четыре вещи:

1. маркер контура существует, разбирается и называет те же значения, что выдал
   аллокатор (иначе отчёт и стенд расходятся);
2. витрина zona-02 нигде не наследует идентичность соседей — ни домена, ни
   счётчика, ни имени службы, ни порта, ни сборки;
3. правка общего реестра диспетчера ограничена одним ключом: записи соседей
   совпадают с их резервной копией побайтно;
4. ни один файл контура zona-02 не лежит внутри чужого.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
import yaml

КОРЕНЬ = Path(__file__).resolve().parents[2]
TENANT = КОРЕНЬ / "TENANT.yaml"
ФРОНТ = Path("/srv/lords/.frontend")
РЕЕСТР = ФРОНТ / "lords-runtime-registry.json"

СОСЕДИ = ("zona-01", "animedia-01", "animedia-02", "lords-01", "lords-02", "lords-03")


@pytest.fixture(scope="module")
def маркер() -> dict:
    assert TENANT.is_file(), "TENANT.yaml отсутствует: границы контура не объявлены"
    return yaml.safe_load(TENANT.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def выдача() -> dict:
    путь = (КОРЕНЬ / "artifacts" / "evidence" / "release-zonafilm-cc-full-cycle-01"
            / "04-site-creation" / "allocation.json")
    assert путь.is_file(), "нет доказательства выдачи идентификаторов"
    return json.loads(путь.read_text(encoding="utf-8"))


# ---------------------------------------------------------------------------
# 1. Маркер и выдача говорят одно и то же
# ---------------------------------------------------------------------------
def test_маркер_совпадает_с_выдачей_аллокатора(маркер, выдача):
    a = маркер["allocation"]
    assert выдача["status"] == "ALLOCATED"
    assert a["site_id"] == выдача["site_id"] == маркер["tenant"]
    assert a["service_name"] == выдача["service_name"]
    assert a["port"] == выдача["port"]
    assert маркер["domain"] == выдача["domain"] == "zonafilm.cc"


def test_маркер_запрещает_то_что_обязан_запрещать(маркер):
    з = маркер["forbidden"]
    for ключ in ("cross_tenant_writes", "other_site_mutations",
                 "other_domain_dns_mutations", "restart_of_other_units",
                 "touching_zona_template_branch", "force_push",
                 "opening_indexing_without_owner_command"):
        assert з.get(ключ) is True, f"{ключ} не объявлен запрещённым"


# ---------------------------------------------------------------------------
# 2. Ничего чужого не унаследовано
# ---------------------------------------------------------------------------
pytestmark_runtime = pytest.mark.skipif(
    not (ФРОНТ / "template-manifest-zona-02.json").is_file(),
    reason="витрина zona-02 не развёрнута на этом хосте",
)


@pytestmark_runtime
def test_манифест_не_несёт_чужой_идентичности(маркер):
    мой = json.loads((ФРОНТ / "template-manifest-zona-02.json").read_text(encoding="utf-8"))
    текст = json.dumps(мой, ensure_ascii=False)
    for домен in маркер["neighbours_readonly"]["domains"]:
        assert домен not in текст, f"в манифесте zona-02 присутствует чужой домен {домен}"
    for юнит in маркер["neighbours_readonly"]["units"]:
        assert юнит not in текст, f"в манифесте zona-02 присутствует чужой юнит {юнит}"
    assert мой["domain"] == "zonafilm.cc"
    assert мой["service_name"] == "nova-zona-02.service"
    assert мой["port"] == 9123
    assert мой["expected_indexability"] == "noindex,nofollow"
    # Сборка своя: совпадение build_id с соседом означало бы, что витрина
    # объявляет чужой релиз своим.
    for сосед in СОСЕДИ:
        чужой = ФРОНТ / f"template-manifest-{сосед}.json"
        if not чужой.is_file():
            continue
        данные = json.loads(чужой.read_text(encoding="utf-8"))
        assert мой["build_id"] != данные.get("build_id"), f"build_id совпал с {сосед}"


@pytestmark_runtime
def test_счётчик_аналитики_не_подставлен_чужой():
    """Пустое поле лучше чужого счётчика: чужой пишет события не туда."""
    мой = json.loads((ФРОНТ / "template-manifest-zona-02.json").read_text(encoding="utf-8"))
    assert "counter_id" not in мой, "в манифесте zona-02 появился счётчик Метрики"
    assert "analytics" not in json.dumps(мой).lower() or "counter" not in json.dumps(мой).lower()


# ---------------------------------------------------------------------------
# 3. Общий реестр: добавлен один ключ, соседи не тронуты
# ---------------------------------------------------------------------------
@pytestmark_runtime
def test_в_реестре_диспетчера_добавлен_ровно_один_ключ():
    резервы = sorted(ФРОНТ.glob("lords-runtime-registry.json.before-zona-02.*"))
    assert резервы, "нет резервной копии реестра: сравнивать не с чем"
    было = json.loads(резервы[0].read_text(encoding="utf-8"))
    стало = json.loads(РЕЕСТР.read_text(encoding="utf-8"))

    новые = set(стало.get("sites") or {}) - set(было.get("sites") or {})
    assert новые == {"zona-02"}, f"в реестре появились посторонние витрины: {новые}"

    for site_id, запись in (было.get("sites") or {}).items():
        assert стало["sites"][site_id] == запись, (
            f"запись соседа {site_id} изменилась: правка вышла за пределы контура"
        )


@pytestmark_runtime
def test_запись_zona_02_в_реестре_указывает_на_свой_релиз():
    стало = json.loads(РЕЕСТР.read_text(encoding="utf-8"))
    запись = стало["sites"]["zona-02"]
    assert запись["port"] == 9123
    assert запись["unit"] == "nova-zona-02.service"
    assert запись["exact_domain"] == "zonafilm.cc"
    assert запись["indexing_enabled"] is False
    цель = Path(запись["release_link"])
    assert цель.is_symlink(), "ссылка current не создана"
    assert "zona-02" in str(цель.resolve()), "ссылка ведёт в чужой релиз"


# ---------------------------------------------------------------------------
# 4. Файлы контура лежат только в своих путях
# ---------------------------------------------------------------------------
@pytestmark_runtime
def test_файлы_контура_не_лежат_внутри_чужих(маркер):
    разрешённые = tuple(p.rstrip("*").rstrip("/") for p in маркер["allowed_writes"]["runtime"])
    мои = [
        ФРОНТ / "template-manifest-zona-02.json",
        ФРОНТ / "zona-02-catalog.json",
        ФРОНТ / "zona-02-details.json",
        ФРОНТ / "sites" / "zona-02",
    ]
    for путь in мои:
        assert путь.exists(), f"нет {путь}"
        assert any(str(путь).startswith(p) for p in разрешённые), (
            f"{путь} вне объявленных границ контура")

    релиз = (ФРОНТ / "sites" / "zona-02" / "current").resolve()
    # Проверяется принадлежность релиза каталогу витрины, а не его имя.
    #
    # Раньше здесь стояло `релиз.name.startswith("zona-02-")`, и это был
    # разумный признак, пока релизы всех витрин лежали в общем
    # `.frontend/releases/`: имя было единственным, что отделяло свой релиз от
    # соседского. После выделения сайта в собственную ячейку релизы витрины
    # лежат в её же корне (`sites/zona-02/releases/<коммит>`), и именем служит
    # коммит проекта сайта — искать в нём `zona-02-` значило бы требовать,
    # чтобы коммит начинался с имени витрины.
    #
    # Замена не ослабление: принадлежность каталогу — более сильное
    # утверждение, чем совпадение префикса имени. Релиз с «правильным» именем
    # в чужом каталоге прежнюю проверку проходил, эту — нет.
    свой_корень = (ФРОНТ / "sites" / "zona-02").resolve()
    assert релиз.is_relative_to(свой_корень), (
        f"релиз {релиз} лежит вне каталога витрины {свой_корень}")
    for сосед in СОСЕДИ:
        ссылка = ФРОНТ / "sites" / сосед / "current"
        if ссылка.is_symlink():
            assert ссылка.resolve() != релиз, f"витрина {сосед} делит релиз с zona-02"
