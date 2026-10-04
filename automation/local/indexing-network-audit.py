#!/usr/bin/env python3
"""Таблица готовности к индексации по ВСЕМ зарегистрированным сайтам.

Один проход по реестру штатными функциями фабрики, без сети и без мутаций:

    python3 automation/local/indexing-network-audit.py            # таблица
    python3 automation/local/indexing-network-audit.py --json     # машинный вид

Для каждого сайта: семейство, установленный выпуск, поддержка механизма
(читатель режима в ВЫЛОЖЕННОМ рантайме), разрешение выпуска, разрешение
владельца (объявление в реестре И подтверждение в каталоге root), слой nginx и
следующее действие. Разрешения владельца отсюда НЕ копируются и не выдаются:
инструмент только читает.
"""
from __future__ import annotations

import json
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2]))

from factory.cell import owner_consent  # noqa: E402
from factory.qwen import editorial, indexing  # noqa: E402


def строка_сайта(s) -> dict:
    к = indexing.контракт(s.adapter) or {}
    запись: dict = {
        "site_id": s.site_id,
        "domain": s.domain,
        "family": s.adapter or "не определено",
        "installed_release": s.published_release or None,
        "mode_owner": к.get("mode_owner") or "неизвестен",
        "contract_reader": к.get("reader") or None,
    }
    # 1. Механизм: читатель режима в ВЫЛОЖЕННОМ рантайме.
    if (к.get("reader") or "").startswith("container:"):
        св = indexing.читатель_контейнера(s.domain)
        запись["mechanism"] = "контейнер" if св.get("found") else "контейнер не опрошен"
        запись["reader_path"] = св.get("container") or None
    else:
        читатель = indexing.читатель_режима(s.account, s.adapter) if s.account else None
        запись["mechanism"] = "читатель в выпуске" if читатель else "читателя нет"
        запись["reader_path"] = str(читатель) if читатель else None
    # 2. Разрешение ВЫПУСКА.
    разрешено, откуда = indexing.разрешение_выпуска(s.account, s.adapter, s.domain)
    запись["release_permits_open"] = разрешено
    запись["release_permission_source"] = откуда
    # 3. Разрешение ВЛАДЕЛЬЦА: объявление и независимое подтверждение.
    разрешил, объявлен, пояснение = indexing.разрешение_владельца(s.site_id)
    согласие = owner_consent.сведения(s.domain) if s.domain else {"present": False}
    запись["owner_authorized_open"] = разрешил
    запись["owner_declared_state"] = объявлен or None
    запись["owner_consent_present"] = bool(согласие.get("present"))
    запись["owner_consent_id"] = согласие.get("id")
    запись["owner_note"] = (пояснение or "")[:160]
    # 4. Слой nginx.
    try:
        слой = indexing.слой_nginx(s.site_id, s.domain)
        запись["nginx_layer"] = слой.get("mode")
        запись["nginx_managed"] = слой.get("managed_by_this_operation")
    except Exception as ош:  # noqa: BLE001 — таблица не вправе падать из-за одного сайта
        запись["nginx_layer"] = f"не прочитан: {type(ош).__name__}"
        запись["nginx_managed"] = None
    # 5. Технические препятствия и следующее действие.
    блокеры = []
    if запись["mechanism"] not in ("читатель в выпуске", "контейнер"):
        блокеры.append("нет читателя режима в выложенном рантайме")
    if not разрешено:
        блокеры.append("выпуск не разрешает открытие (release_permits_open)")
    if запись["mode_owner"] == "compose":
        блокеры.append("режимом распоряжается переменная контейнера, не операция")
    if запись["family"] == "не определено":
        блокеры.append("семейство не определено: контракта режима нет")
    запись["technical_blockers"] = блокеры
    if блокеры:
        запись["next_action"] = "устранить техническое препятствие выпуском"
    elif not разрешил:
        запись["next_action"] = ("нужна команда владельца: authorize-indexing.sh "
                                 f"--domain {s.domain}")
    else:
        запись["next_action"] = ("открыть одной командой: set_indexing_mode "
                                 '{"site": "%s", "mode": "open"}' % s.domain)
    return запись


def главная(argv: list[str]) -> int:
    сайты = editorial._реестр(опрашивать_сеть=False)
    таблица = [строка_сайта(s) for s in sorted(сайты, key=lambda x: (x.adapter or "я", x.domain))]
    if "--json" in argv:
        print(json.dumps(таблица, ensure_ascii=False, indent=1))
        return 0
    шапка = (f"{'семейство':10} {'домен':24} {'выпуск':14} {'механизм':20} "
             f"{'выпуск разр':11} {'владелец':9} {'слой':8} препятствия")
    print(шапка)
    print("-" * len(шапка))
    for з in таблица:
        print(f"{з['family'][:10]:10} {з['domain'][:24]:24} "
              f"{str(з['installed_release'])[:14]:14} {з['mechanism'][:20]:20} "
              f"{str(з['release_permits_open']):11} "
              f"{str(з['owner_authorized_open']):9} {str(з['nginx_layer'])[:8]:8} "
              f"{'; '.join(з['technical_blockers'])[:60]}")
    print()
    готовы = [з for з in таблица if not з["technical_blockers"]]
    print(f"всего сайтов: {len(таблица)}")
    print(f"технически готовы (осталось только разрешение владельца): {len(готовы)}")
    for з in готовы:
        метка = "ОТКРЫТЬ одной командой" if з["owner_authorized_open"] else "ждёт команды владельца"
        print(f"   {з['domain']:24} {метка}")
    print()
    по_семействам: dict[str, list[str]] = {}
    for з in таблица:
        по_семействам.setdefault(з["family"], []).append(з["domain"])
    print("по семействам:")
    for семейство, домены in sorted(по_семействам.items()):
        готовых = len([д for д in домены
                       if not next(з for з in таблица if з["domain"] == д)["technical_blockers"]])
        print(f"   {семейство:12} сайтов {len(домены):2}, технически готовы {готовых}")
    return 0


if __name__ == "__main__":
    raise SystemExit(главная(sys.argv[1:]))
