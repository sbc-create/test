#!/usr/bin/env python3
"""Показывает, какой именно allowlist видит guard и что в нём про zonafilm.space.

Запись `zona-public` есть в allowlist этой ветки, а guard всё равно закрывал
домен. Значит, guard читает другой файл — и прежде чем что-то править, надо
узнать какой. Править не тот файл означало бы «снять gate» и обнаружить, что
он на месте.
"""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from seo_operator import unattended  # noqa: E402

print("repo_root, от которого считает unattended:", unattended._repo_root())
хосты = unattended.network_hosts()
print("хостов в allowlist:", len(хосты))
print("zonafilm.space разрешён:", "zonafilm.space" in хосты)
print("отсортированный список:")
for h in sorted(хосты):
    print("   ", h)

разрешено, причина = unattended.decide("curl -s https://zonafilm.space/")
print("\nрешение по curl к домену:", разрешено, "—", причина)
