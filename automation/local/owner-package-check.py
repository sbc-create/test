#!/usr/bin/env python3
"""Проверяемость пакета команд владельца: каждый путь, ключ и сайт — на месте.

Повод. 13.10 в пакете действий владельца оказались ссылки на сценарии, которых
в указанной копии репозитория нет вовсе: `install-site-nginx.sh`,
`install-site-tls.sh`, `launch-new-site.sh`, `apply-publisher-patch.py`,
`install-publisher-cell-paths.sh` лежат в рабочем дереве, а путь вёл в
`/srv/site-factory/repo`. Команда отказала бы сразу словами «No such file or
directory», и владелец узнал бы об этом уже в терминале.

Отдельная ловушка — КОНФИГУРАЦИЯ, которую сценарий ищет ОТНОСИТЕЛЬНО СЕБЯ:
`SRC_ROOT="$(dirname $0)/../.."`, дальше `$SRC_ROOT/config/site-cells.json` и
`$SRC_ROOT/automation/host/nginx-site/<site>.conf`. Проверять существование
самого сценария недостаточно: он может быть на месте, а реестра рядом с ним не
быть — ровно это и отличает рабочее дерево от живой копии.

Что проверяется по каждому блоку ```bash``` документа:

* путь сценария существует и исполняем (для `bash`/`sudo bash`) или читается
  (для `python3`);
* если сценарий читает `$SRC_ROOT/config/site-cells.json` или заготовку
  `nginx-site/<site>.conf` — эти файлы существуют РЯДОМ С НИМ;
* значение `--site` есть в реестре ячеек;
* ключи `--site` против позиционного аргумента: сценарий, объявивший `--site` в
  своём заголовке, позиционный не принимает.

Код возврата 1 — есть расхождения; 0 — пакет проверяем целиком.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

КОРЕНЬ = Path(__file__).resolve().parents[2]
РЕЕСТР = КОРЕНЬ / "config" / "site-cells.json"

#: Сценарии, которым нужен реестр рядом с собой (читают $SRC_ROOT/config/...).
НУЖЕН_РЕЕСТР = ("install-site-nginx.sh", "install-site-tls.sh",
                "launch-new-site.sh", "apply-publisher-patch.py",
                "install-publisher-cell-paths.sh", "install-cell-units.py")
#: Сценарии, которым нужна заготовка nginx рядом с собой.
НУЖНА_ЗАГОТОВКА = {"install-site-nginx.sh": "{site}.conf",
                   "install-site-tls.sh": "{site}-tls.conf"}


def site_id_ы() -> set[str]:
    try:
        д = json.loads(РЕЕСТР.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return set()
    return {str(c.get("site_id")) for c in (д.get("cells") or [])}


def блоки(текст: str) -> list[str]:
    """Строки команд из всех блоков ```bash ... ```."""
    итог: list[str] = []
    for кусок in re.findall(r"```bash\n(.*?)```", текст, re.S):
        строка = ""
        for с in кусок.splitlines():
            с = с.rstrip()
            if not с.strip() or с.strip().startswith("#"):
                continue
            строка += с[:-1] + " " if с.endswith("\\") else с
            if not с.endswith("\\"):
                итог.append(строка.strip())
                строка = ""
        if строка:
            итог.append(строка.strip())
    return итог


def путь_сценария(команда: str) -> tuple[Path | None, str]:
    """Путь исполняемого файла из команды и способ запуска."""
    части = команда.split()
    способ = ""
    for i, ч in enumerate(части):
        if ч in ("sudo", "-m", "0644", "0755"):
            continue
        if ч in ("bash", "python3", "/usr/bin/bash", "/usr/bin/python3"):
            способ = "bash" if "bash" in ч else "python3"
            continue
        if ч.startswith("/") and (ч.endswith(".sh") or ч.endswith(".py")):
            return Path(ч), способ or "прямой"
        if ч.startswith("-"):
            continue
        if ч.endswith(".sh") or ч.endswith(".py"):
            return Path(ч), способ or "прямой"
    return None, способ


def проверить(док: Path) -> list[str]:
    беды: list[str] = []
    известные = site_id_ы()
    for команда in блоки(док.read_text(encoding="utf-8")):
        путь, способ = путь_сценария(команда)
        коротко = команда[:88]
        if путь is None:
            continue
        if not путь.is_absolute():
            беды.append(f"относительный путь сценария: {коротко}")
            continue
        if not путь.is_file():
            беды.append(f"сценария НЕТ: {путь} ← {коротко}")
            continue
        if способ == "прямой" and not путь.stat().st_mode & 0o111:
            беды.append(f"сценарий не исполняем, а запускается напрямую: {путь}")
        # Конфигурация, которую сценарий ищет относительно себя.
        src_root = путь.parent.parent.parent
        if путь.name in НУЖЕН_РЕЕСТР and not (src_root / "config" / "site-cells.json").is_file():
            беды.append(f"{путь.name}: рядом нет {src_root}/config/site-cells.json "
                        f"— сценарий ищет реестр относительно себя ← {коротко}")
        сайты = re.findall(r"--site\s+([\w.-]+)", команда)
        for сайт in сайты:
            if известные and сайт not in известные:
                беды.append(f"--site {сайт} нет в реестре ← {коротко}")
            шаблон = НУЖНА_ЗАГОТОВКА.get(путь.name)
            if шаблон:
                заготовка = src_root / "automation" / "host" / "nginx-site" / шаблон.format(site=сайт)
                if not заготовка.is_file():
                    беды.append(f"{путь.name}: нет заготовки {заготовка} ← {коротко}")
        # Ключ --site против позиционного аргумента.
        if сайты:
            continue
        заголовок = "\n".join(путь.read_text(encoding="utf-8",
                                             errors="replace").splitlines()[:30])
        if "--site" in заголовок and путь.name in НУЖЕН_РЕЕСТР:
            позиционные = [ч for ч in команда.split()[1:]
                           if ч in известные]
            if позиционные:
                беды.append(f"{путь.name} принимает --site, а передан позиционный "
                            f"{позиционные[0]} ← {коротко}")
    return беды


def main() -> int:
    р = argparse.ArgumentParser(description=__doc__)
    р.add_argument("документ", nargs="?",
                   default=str(КОРЕНЬ / "docs" / "OWNER_ACTIONS_BATCH8_20261013.md"))
    а = р.parse_args()
    док = Path(а.документ)
    if not док.is_file():
        print(f"ОТКАЗ: нет {док}", file=sys.stderr)
        return 2
    команды = блоки(док.read_text(encoding="utf-8"))
    беды = проверить(док)
    print(f"документ: {док.name}; команд в блоках: {len(команды)}")
    if not беды:
        print("расхождений нет: каждый сценарий на месте, реестр и заготовки рядом с ним, "
              "все --site есть в реестре")
        return 0
    print(f"расхождений: {len(беды)}")
    for б in беды:
        print(f"   {б}")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
