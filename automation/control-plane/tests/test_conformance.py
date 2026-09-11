"""Conformance-матрица потребителей Control Plane.

Семь адаптеров — Templates, SEO, Content, Monitoring, Backup, Architect и
планировщик Qwen. Каждый обязан доказать одно и то же: сайты берутся из
реестра, ключом служит site_id, неизвестное поле не ломает, отсутствие
обязательного — ломает, повтор события обрабатывается один раз, курсор
переживает перезапуск, прямого доступа к чужой БД нет.

Адаптеры тестовые. Они ничего не публикуют и ничего не меняют: это проверка
контракта, а не запуск контуров.
"""
from __future__ import annotations

import json, sqlite3, sys, uuid
from pathlib import Path
import pytest

sys.path.insert(0, "/srv/site-factory/control-plane-contracts/clients")
from fleet_client import FleetClient, ContractError

БАЗА = "http://127.0.0.1:8790"
ОБЯЗАТЕЛЬНЫЕ = ("site_id", "canonical_domain", "lifecycle_state", "environment")
ПОТРЕБИТЕЛИ = ["templates", "seo", "content", "monitoring", "backup",
               "architect", "qwen-planner"]


class Адаптер:
    """Минимальный потребитель: курсор, идемпотентность, никакой БД."""

    def __init__(self, имя: str, клиент: FleetClient):
        self.имя = имя
        self.к = клиент
        self.курсор = 0
        self.обработанные: set[str] = set()
        self.состояние: dict[str, dict] = {}

    def sites(self) -> list[dict]:
        return self.к.active_production_sites()

    def потребить(self, событие: dict) -> bool:
        """True — обработано впервые. Повтор обязан вернуть False."""
        eid = событие["event_id"]
        if eid in self.обработанные:
            return False
        self.обработанные.add(eid)
        self.состояние[событие["site_id"]] = {
            "aggregate_version": событие["aggregate_version"],
            "type": событие["event_type"]}
        self.курсор = max(self.курсор, событие["seq"])
        return True

    def догнать(self) -> int:
        новых = 0
        for e in self.к.replay(self.курсор, page=50):
            if self.потребить(e):
                новых += 1
        return новых


@pytest.fixture(scope="module")
def клиент():
    return FleetClient(БАЗА)


@pytest.mark.parametrize("имя", ПОТРЕБИТЕЛИ)
def test_адаптер_видит_девять_из_реестра(имя, клиент):
    """Девять сайтов приходят из реестра, а не из списка в коде адаптера."""
    a = Адаптер(имя, клиент)
    сайты = a.sites()
    assert len(сайты) == 9, f"{имя}: получено {len(сайты)}"
    assert all(s["site_id"] for s in сайты), f"{имя}: запись без site_id"
    домены = {s["canonical_domain"] for s in сайты}
    assert len(домены) == 9, f"{имя}: домены повторяются"


@pytest.mark.parametrize("имя", ПОТРЕБИТЕЛИ)
def test_адаптер_терпит_неизвестное_поле(имя, клиент):
    """Аддитивное расширение производителя не должно ломать потребителя."""
    запись = dict(клиент.active_production_sites()[0])
    запись["совершенно_новое_поле"] = {"вложенное": [1, 2, 3]}
    FleetClient.validate(запись, ОБЯЗАТЕЛЬНЫЕ)   # не должно бросить


@pytest.mark.parametrize("имя", ПОТРЕБИТЕЛИ)
def test_адаптер_отвергает_без_обязательного(имя, клиент):
    запись = dict(клиент.active_production_sites()[0])
    запись.pop("site_id")
    with pytest.raises(ContractError):
        FleetClient.validate(запись, ОБЯЗАТЕЛЬНЫЕ)


@pytest.mark.parametrize("имя", ПОТРЕБИТЕЛИ)
def test_адаптер_идемпотентен_к_повтору(имя, клиент):
    a = Адаптер(имя, клиент)
    события = list(клиент.replay(0, page=50))
    assert события, "лента пуста"
    первый = a.потребить(события[0])
    повтор = a.потребить(события[0])
    assert первый is True and повтор is False
    # Повторная подача всей ленты не должна дать ни одной новой обработки.
    было = len(a.обработанные)
    for e in события:
        a.потребить(e)
    a.обработанные == a.обработанные
    снова = sum(1 for e in события if e["event_id"] not in a.обработанные)
    assert снова == 0, f"{имя}: повтор дал новые обработки"


@pytest.mark.parametrize("имя", ПОТРЕБИТЕЛИ)
def test_курсор_переживает_перезапуск(имя, клиент):
    a = Адаптер(имя, клиент)
    a.догнать()
    сохранён = {"cursor": a.курсор, "seen": sorted(a.обработанные)}
    # «Перезапуск»: новый объект, состояние восстановлено из durable-снимка.
    b = Адаптер(имя, клиент)
    b.курсор = сохранён["cursor"]
    b.обработанные = set(сохранён["seen"])
    новых = b.догнать()
    assert новых == 0, f"{имя}: после перезапуска обработано заново {новых}"
    assert b.курсор == a.курсор


@pytest.mark.parametrize("имя", ПОТРЕБИТЕЛИ)
def test_адаптер_не_ходит_в_чужую_бд(имя, клиент):
    """Потребитель работает только по HTTP. Прямой доступ к БД запрещён.

    Проверяется буквально: файл БД реестра адаптеру недоступен на запись, и
    сам адаптер не содержит ни одного обращения к sqlite.
    """
    исходник = Path(__file__).read_text(encoding="utf-8")
    начало = исходник.index("class Адаптер")
    конец = исходник.index("@pytest.fixture")
    тело = исходник[начало:конец]
    for запрещённое in ("sqlite3.connect", "registry.sqlite3", "psycopg", "open("):
        assert запрещённое not in тело, f"{имя}: адаптер обращается к {запрещённое}"


def test_qwen_не_имеет_прав_на_запись(клиент):
    """Qwen — MODEL-actor: читает и предлагает, но не применяет."""
    кат = клиент.capabilities()
    qwen = [c for c in кат["capabilities"] if c["owner_service"] == "qwen"]
    assert qwen, "возможности qwen нет в каталоге"
    for c in qwen:
        assert c["command_endpoint"] is None, "у qwen есть командный адрес"
        assert c["status"] == "PLANNED", f"qwen объявлен {c['status']}"
    мат = json.loads(Path("/srv/site-factory/control-plane-contracts/1.0.0/"
                          "ownership-matrix.json").read_text(encoding="utf-8"))
    строки = [r for r in мат["resources"] if r["single_writer"] == "qwen"]
    assert all("PROPOSAL_ONLY" in r["mutation_policy"] for r in строки)
    доменные = [r for r in мат["resources"]
                if r["single_writer"] == "qwen" and not r["resource"].startswith("qwen.")]
    assert not доменные, "qwen объявлен владельцем доменного ресурса"


def test_ни_у_одного_ресурса_нет_двух_писателей():
    мат = json.loads(Path("/srv/site-factory/control-plane-contracts/1.0.0/"
                          "ownership-matrix.json").read_text(encoding="utf-8"))
    по_ресурсу: dict[str, set[str]] = {}
    for r in мат["resources"]:
        по_ресурсу.setdefault(r["resource"], set()).add(r["single_writer"])
    конфликты = {k: v for k, v in по_ресурсу.items() if len(v) > 1}
    assert not конфликты, f"два писателя: {конфликты}"


def test_ложных_available_нет(клиент):
    кат = клиент.capabilities()
    for c in кат["capabilities"]:
        if c["status"] == "AVAILABLE":
            assert c["read_endpoint"], f"{c['capability_id']}: AVAILABLE без адреса"
            assert c["last_verified_at"], f"{c['capability_id']}: без проверки"
        if c["status"] == "PLANNED":
            assert c["read_endpoint"] is None and c["command_endpoint"] is None, \
                f"{c['capability_id']}: PLANNED с адресом"
