"""Наблюдение фактического состояния витрин. Только чтение.

Наблюдение — это не «сайт ответил 200». Код ответа говорит лишь о том, что
что-то живо; он не отличает нужный релиз от прошлогоднего. Поэтому здесь
снимается отпечаток: семейство, версия шаблона, build_id и SHA-256
артефакта — то, что объявляет сам сайт, — и из них считается
`observed_fingerprint`.

Ожидаемое значение берётся не отсюда. Наблюдатель отвечает на вопрос «что
работает», сравнение с «что должно работать» делает вызывающий: смешивать
их в одном месте значит позволить наблюдателю подтвердить самого себя.

Список сайтов приходит из проекции Registry по `site_id`. Домен —
изменяемый атрибут, и адрес наблюдения берётся из `canonical_domain`
текущей записи, а не из зашитой таблицы.
"""

from __future__ import annotations

import hashlib
import json
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from typing import Any

#: Маршрут самоописания витрины. Он уже существует на всех девяти сайтах и
#: отдаёт манифест релиза целиком.
МАРШРУТ_ВЕРСИИ = "/__template_version"
ЗАГОЛОВКИ = {"User-Agent": "site-factory-templates-observer/1.0 (read-only)"}


@dataclass(frozen=True)
class Наблюдение:
    site_id: str
    canonical_domain: str | None
    family: str | None
    registry_version: int | None
    http_status: Any
    observed: dict[str, Any] = field(default_factory=dict)
    observed_fingerprint: str | None = None
    источник: str = МАРШРУТ_ВЕРСИИ
    свежесть: str = "FRESH"
    ошибка: str | None = None

    @property
    def успешно(self) -> bool:
        return self.http_status == 200 and self.observed_fingerprint is not None


def _отпечаток(манифест: dict[str, Any]) -> str:
    """Устойчивый отпечаток наблюдаемого состояния.

    Берутся только поля, которые описывают, ЧТО работает. Время сборки
    исключено намеренно: оно меняется при каждой пересборке того же
    исходника и превращало бы сравнение отпечатков в вечное расхождение.
    """
    ядро = {k: манифест.get(k) for k in
            ("template_family", "design_version", "build_id",
             "artifact_sha256", "source_commit", "profile")}
    сырое = json.dumps(ядро, ensure_ascii=False, sort_keys=True)
    return "sha256:" + hashlib.sha256(сырое.encode("utf-8")).hexdigest()


class Наблюдатель:
    def __init__(self, таймаут: float = 25.0, открывашка=None) -> None:
        self.таймаут = таймаут
        self._открыть = открывашка or urllib.request.urlopen

    def наблюдать(self, site_id: str, домен: str | None, family: str | None,
                  registry_version: int | None, свежесть: str = "FRESH") -> Наблюдение:
        if not домен:
            return Наблюдение(site_id, домен, family, registry_version, None,
                              свежесть=свежесть, ошибка="в записи Registry нет домена")
        адрес = f"https://{домен}{МАРШРУТ_ВЕРСИИ}"
        зпр = urllib.request.Request(адрес, headers=ЗАГОЛОВКИ)
        try:
            with self._открыть(зпр, timeout=self.таймаут) as о:
                манифест = json.loads(о.read().decode("utf-8"))
                код = о.status
        except urllib.error.HTTPError as ош:
            return Наблюдение(site_id, домен, family, registry_version, ош.code,
                              свежесть=свежесть, ошибка=f"HTTP {ош.code}")
        except Exception as ош:
            return Наблюдение(site_id, домен, family, registry_version, None,
                              свежесть=свежесть, ошибка=f"{type(ош).__name__}")
        return Наблюдение(site_id=site_id, canonical_domain=домен, family=family,
                          registry_version=registry_version, http_status=код,
                          observed=манифест, observed_fingerprint=_отпечаток(манифест),
                          свежесть=свежесть)

    def наблюдать_все(self, ответ) -> list[Наблюдение]:
        """Наблюдение по списку из проекции. Порядок — по site_id."""
        свежесть = "FRESH" if ответ.свежая else "STALE"
        итог = []
        for с in sorted(ответ.сайты, key=lambda x: x.site_id):
            итог.append(self.наблюдать(с.site_id, с.canonical_domain, с.family,
                                       ответ.registry_version, свежесть))
            time.sleep(0.05)              # вежливая частота, не нагрузка
        return итог
