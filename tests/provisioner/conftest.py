"""Эфемерная обвязка Integration Provisioner.

Всё изменяющее идёт только здесь: канонические Registry, Ledger и ChangeSet
Store в этих испытаниях не участвуют вовсе. Проверять идемпотентность на
рабочем контуре значило бы доказывать её ценой мусора в истории системы.

Обещание изоляции держалось не до конца, и дыра была ровно одна. Служба
подписи спрашивает версию реестра через `RegistryClient`, а тотберёт адрес из
`CONTROL_API_BASE` и по умолчанию — `http://127.0.0.1:8790`, то есть
**канонический** control API машины. На хосте, где он поднят, эфемерное
испытание сверялось с живым флотом: реестр теста объявлял версию 2, живой
отвечал 32, и двенадцать проверок падали с `REGISTRY_VERSION_STALE` — не
потому, что provisioner неисправен, а потому, что тест дотянулся туда, куда не
должен. На чистой машине те же тесты проходили, и расхождение выглядело
«нестабильностью окружения».

Поэтому адрес здесь задаётся, а не наследуется. Реестр теста живёт в процессе
и HTTP-лица не имеет, спрашивать его службе подписи неоткуда — и
`_общие_проверки` этот случай предусматривает сам: недоступный реестр даёт
`None`, и проверка версии не выполняется. Это штатная ветка кода, а не
ослабленное утверждение: выбор здесь между «сверяться не с чем» и «сверяться с
чужим флотом», и первое честнее.
"""
from __future__ import annotations

import datetime as _d

import pytest

from factory.site_engine.approval import testing as ПОДПИСЬ_ТЕСТ
from factory.site_engine.changeset import store as S
from factory.site_engine.provisioner.intent import OnboardingIntent
from factory.site_engine.provisioner.mapping import Связи
from factory.site_engine.provisioner.providers import fake as F


class ЭфемерныйРеестр:
    """Реестр на время теста. Растёт по ходу, как настоящий."""

    def __init__(self) -> None:
        self._сайты: dict[str, dict] = {}
        self._версия = 1

    def добавить(self, site_id: str, *, environment: str = "test",
                 lifecycle: str = "DRAFT", domain: str | None = None) -> dict:
        self._версия += 1
        запись = {"site_id": site_id, "environment": environment,
                  "lifecycle_state": lifecycle,
                  "canonical_domain": domain or f"{site_id}.test",
                  "registry_version": self._версия}
        self._сайты[site_id] = запись
        return запись

    def сменить_домен(self, site_id: str, новый: str) -> None:
        self._версия += 1
        self._сайты[site_id]["canonical_domain"] = новый

    def версия(self) -> int:
        return self._версия

    def сайт(self, site_id: str) -> dict | None:
        return self._сайты.get(site_id)

    def сайты(self) -> list[dict]:
        return list(self._сайты.values())


def через_час() -> str:
    return (_d.datetime.now(_d.timezone.utc)
            + _d.timedelta(hours=1)).isoformat().replace("+00:00", "Z")


def одобрить(движок, cid: str) -> None:
    """Одобряет человек. Provisioner только предлагает."""
    движок.одобрить(cid, approver_id="human:owner", служба="human_owner",
                    actor_type="HUMAN", expires_at=через_час(),
                    reason="эфемерное испытание")


#: Адрес, по которому control API не бывает: порт 1 зарезервирован и службой
#: флота не занимается никогда. Нужен именно недостижимый адрес, а не пустая
#: строка: пустую `RegistryClient` заменит своим умолчанием — каноническим
#: экземпляром, от которого мы и уходим.
НЕДОСТИЖИМЫЙ_CONTROL_API = "http://127.0.0.1:1"


@pytest.fixture()
def обвязка(tmp_path, monkeypatch):
    monkeypatch.setenv("CHANGESET_DB", str(tmp_path / "cs.sqlite3"))
    monkeypatch.setenv("CONTROL_API_BASE", НЕДОСТИЖИМЫЙ_CONTROL_API)
    with ПОДПИСЬ_ТЕСТ.эфемерный_signer(tmp_path / "credentials", monkeypatch):
        соед = S.открыть(tmp_path / "cs.sqlite3")
        связи = Связи(str(tmp_path / "links.sqlite3"))
        реестр = ЭфемерныйРеестр()
        мир = F.Мир()
        провайдеры = {"dns": F.ФейковыйDNS(мир), "tls": F.ФейковыйTLS(мир),
                      "analytics": F.ФейковаяМетрика(мир),
                      "template": F.ФейковаяВитрина(мир),
                      "seo_rank": F.ФейковыйTopvisor(мир)}
        yield {"соед": соед, "связи": связи, "реестр": реестр, "мир": мир,
               "провайдеры": провайдеры, "tmp": tmp_path}
        связи.закрыть()
        соед.close()


def намерение(домен="shop.test", ключ="k-1", **прочее) -> OnboardingIntent:
    основа = {"requested_by": "service:qwen", "canonical_domain": домен,
              "template_family": "yummy", "template_profile": "catalog-search",
              "language": "ru", "region": "RU",
              "correlation_id": "corr-1", "idempotency_key": ключ}
    основа.update(прочее)
    return OnboardingIntent.разобрать(основа)
