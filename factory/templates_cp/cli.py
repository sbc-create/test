"""Командный интерфейс подключения Templates к Control Plane.

Только чтение и наблюдение. Никаких изменений витрин здесь нет и быть не
может: изменяющие операции принадлежат ChangeSet Workflow, а его write-контур
пока не объявлен контрактом.
"""

from __future__ import annotations

import argparse
import json
import os
import sys

from factory.templates_cp.observer import Наблюдатель
from factory.templates_cp.projection import Проекция
from factory.templates_cp.registry_client import (RegistryClient,
                                                  RegistryUnavailable)

БАЗА = os.environ.get("TEMPLATES_CP_BASE", "http://127.0.0.1:8790")
СОСТОЯНИЕ = os.environ.get("TEMPLATES_CP_STATE", "var/templates-cp/projection.sqlite3")


def _проекция() -> Проекция:
    os.makedirs(os.path.dirname(СОСТОЯНИЕ), exist_ok=True)
    return Проекция(СОСТОЯНИЕ)


def команда_sync(_) -> int:
    """Полная сверка проекции со снимком Registry."""
    клиент, проекция = RegistryClient(БАЗА), _проекция()
    try:
        снимок = клиент.снимок()
    except RegistryUnavailable as ош:
        print(f"Registry недоступен: {ош}", file=sys.stderr)
        return 2
    проекция.применить_снимок(снимок)
    ответ = проекция.производственные(свежая=True, источник="snapshot")
    print(json.dumps({"registry_version": снимок.registry_version,
                      "checksum": снимок.checksum, "etag": снимок.etag,
                      "production_active": sorted(ответ.идентификаторы)},
                     ensure_ascii=False, indent=1))
    проекция.закрыть()
    return 0


def команда_observe(аргументы) -> int:
    """Живое наблюдение production-сайтов. Только чтение."""
    клиент, проекция = RegistryClient(БАЗА), _проекция()
    свежая, источник = True, "registry"
    try:
        снимок = клиент.производственные()
        if not аргументы.без_записи:
            проекция.применить_снимок(снимок)
        else:
            # Наблюдение по своей природе ничего не меняет. Раньше оно
            # попутно обновляло проекцию — и перестало работать, как только
            # состояние стало принадлежать служебной учётной записи. Право
            # на запись для чтения не нужно.
            свежая, источник = True, "registry (без записи проекции)"
    except RegistryUnavailable as ош:
        # Работаем от последнего известного состояния и говорим об этом.
        свежая, источник = False, f"projection (Registry недоступен: {ош})"
    ответ = проекция.производственные(свежая=свежая, источник=источник)
    наблюдения = Наблюдатель().наблюдать_все(ответ)
    строки = []
    for н in наблюдения:
        строки.append({
            "site_id": н.site_id, "canonical_domain": н.canonical_domain,
            "family": н.family, "registry_version": н.registry_version,
            "http_status": н.http_status,
            "observed": {k: н.observed.get(k) for k in
                         ("template_family", "design_version", "build_id",
                          "artifact_sha256", "source_commit")},
            "observed_fingerprint": н.observed_fingerprint,
            "source": н.источник, "freshness": н.свежесть, "error": н.ошибка,
        })
    успешных = sum(1 for н in наблюдения if н.успешно)
    вывод = {"observed": успешных, "total": len(наблюдения),
             "registry_version": ответ.registry_version,
             "freshness": "FRESH" if свежая else "STALE", "sites": строки}
    print(json.dumps(вывод, ensure_ascii=False, indent=1))
    if аргументы.out:
        with open(аргументы.out, "w", encoding="utf-8") as ф:
            json.dump(вывод, ф, ensure_ascii=False, indent=1)
    проекция.закрыть()
    return 0 if успешных == len(наблюдения) and наблюдения else 1


def команда_dlq(аргументы) -> int:
    """Показать отложенные события или разобрать их заново."""
    from factory.templates_cp.consumer import Потребитель
    клиент, проекция = RegistryClient(БАЗА), _проекция()
    очередь = проекция.очередь_разбора()
    if not аргументы.redrive:
        print(json.dumps({"depth": len(очередь), "items": [
            {k: з[k] for k in ("event_id", "seq", "reason", "attempts")}
            for з in очередь]}, ensure_ascii=False, indent=1))
        проекция.закрыть()
        return 0
    потребитель = Потребитель(клиент, проекция,
                              журнал=lambda в, д: print(
                                  f"[templates-cp] {в} {json.dumps(д, ensure_ascii=False)}"))
    свод = потребитель.разобрать_dlq()
    свод["depth_after"] = проекция.глубина_dlq
    print(json.dumps(свод, ensure_ascii=False, indent=1))
    проекция.закрыть()
    return 0 if свод["still_failing"] == 0 else 1


def команда_capabilities(_) -> int:
    """Что объявлено Control Plane. Источник решения о том, что можно делать."""
    клиент = RegistryClient(БАЗА)
    возможности = клиент.возможности()
    print(json.dumps({"contract_bundle": клиент.версия_контракта(),
                      "capabilities": возможности}, ensure_ascii=False, indent=1))
    return 0


def main(argv: list[str] | None = None) -> int:
    р = argparse.ArgumentParser(prog="templates-cp", description=__doc__)
    под = р.add_subparsers(dest="команда", required=True)
    под.add_parser("sync", help="сверить проекцию со снимком Registry")
    н = под.add_parser("observe", help="живое наблюдение production-сайтов")
    н.add_argument("--out", help="сохранить результат в файл")
    н.add_argument("--без-записи", "--read-only", dest="без_записи",
                   action="store_true",
                   help="не обновлять проекцию: только наблюдать")
    под.add_parser("capabilities", help="показать объявленные возможности")
    д = под.add_parser("dlq", help="отложенные события и их повторный разбор")
    д.add_argument("--redrive", action="store_true",
                   help="прогнать отложенные события заново текущим кодом")
    а = р.parse_args(argv)
    return {"sync": команда_sync, "observe": команда_observe,
            "capabilities": команда_capabilities,
            "dlq": команда_dlq}[а.команда](а)


if __name__ == "__main__":
    raise SystemExit(main())
