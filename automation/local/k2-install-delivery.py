#!/usr/bin/env python3
"""Готовность постоянной рабочей копии к суточной доставке каталога K2.

Зачем. Таймер доставки подготовлен, но включать его в рабочую копию сессии
нельзя: она временная. Постоянная копия — `/srv/site-factory/repo` — к этому
не готова: в ней нет сценариев доставки (ветка не слита) и нет
`var/ansible/hosts.yml`, потому что `var/` не версионируется. «Просто включить
таймер» недостаточно, и эта проверка перечисляет ровно то, чего не хватает.

Что проверяется (каждая строка — отдельный факт, а не общий вывод):

  ветка        рабочая копия, её голова и наличие сценариев доставки;
  инвентарь    `inventory/ssh-hosts.yaml`, закреплённый ключ хоста и ПУТЬ к
               ssh-ключу — только существование и права, содержимое не
               читается и не печатается;
  издатель     живой `nova-catalog-publish.py` (абсолютный путь, от копии не
               зависит);
  снимок       снимок поставщика и его возраст;
  каталоги     куда доставка пишет комплект и отчёты.

`--apply` делает то, что можно сделать без root: создаёт каталоги и
генерирует `var/ansible/hosts.yml` штатным `render-ansible-inventory.py` в
указанной копии. Код ветки она не сливает — это решение владельца.

    python3 automation/local/k2-install-delivery.py                 # проверка
    python3 automation/local/k2-install-delivery.py --root /srv/site-factory/repo --apply
    python3 automation/local/k2-install-delivery.py --root … --check-ssh
"""
from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path

ЖИВОЙ_ИЗДАТЕЛЬ = Path("/srv/site-factory/repo/automation/host/"
                      "nova-catalog-publish.py")
СНИМОК = Path("/srv/site-factory/repo/var/lords/lords/catalog-cache/"
              "lords-01.json")
НУЖНЫЕ_СЦЕНАРИИ = (
    "automation/local/k2-deliver-catalog.sh",
    "automation/local/make-k2-publisher.py",
    "automation/local/run-k2-publisher.py",
    "automation/local/render-ansible-inventory.py",
)
НУЖНЫЕ_КАТАЛОГИ = ("var/k2-data", "var/k2-data/publish-reports")
ХОСТ = "k2-zomro-01"


def строка(ладно: bool, текст: str) -> str:
    return f"{'  ok  ' if ладно else ' НЕТ  '} {текст}"


def путь_ключа(корень: Path) -> str:
    """Путь к ssh-ключу из инвентаря. Содержимое не читается."""
    опись = корень / "inventory" / "ssh-hosts.yaml"
    if not опись.is_file():
        return ""
    try:
        import yaml
    except ImportError:
        return ""
    д = yaml.safe_load(опись.read_text(encoding="utf-8")) or {}
    for х in (д.get("hosts") or []):
        if (х or {}).get("ref") == ХОСТ:
            ссылка = str(х.get("ssh_key_secret_ref") or "")
            return ссылка.split("file:", 1)[1] if ссылка.startswith("file:") else ""
    return ""


#: Файлы, которые нужны доставке. Пути относительные: сценарии вычисляют
#: корень как `parents[2]` от себя, поэтому раскладка обязана совпадать.
НАБОР_УСТАНОВКИ = (
    "automation/local/k2-deliver-catalog.sh",
    "automation/local/make-k2-publisher.py",
    "automation/local/run-k2-publisher.py",
    "automation/local/render-ansible-inventory.py",
    "automation/local/k2-install-delivery.py",
    "config/site-cells.json",
    "inventory/ssh-hosts.yaml",
    "inventory/known_hosts.d/k2-zomro-01",
)
ОПИСЬ_УСТАНОВКИ = "INSTALL.json"


def _сумма(путь) -> str:
    import hashlib
    return hashlib.sha256(путь.read_bytes()).hexdigest()


def установить(источник, цель) -> int:
    """Разложить набор доставки в постоянный каталог и описать установку.

    Копия, а не ссылка: каталог обязан пережить удаление рабочей копии
    сессии. Опись с суммами и коммитом источника делает установку проверяемой
    (`--verify`), то есть отличимой от «что-то когда-то скопировали».
    """
    import datetime as dt
    import json
    import shutil
    import subprocess

    не_нашлось = [и for и in НАБОР_УСТАНОВКИ if not (источник / и).is_file()]
    if не_нашлось:
        for и in не_нашлось:
            print(строка(False, f"в источнике нет {и}"))
        return 1
    коммит = subprocess.run(["git", "-C", str(источник), "rev-parse", "HEAD"],
                            capture_output=True, text=True).stdout.strip()
    грязно = subprocess.run(["git", "-C", str(источник), "status", "--porcelain"],
                            capture_output=True, text=True).stdout.strip()
    опись = {
        "источник": str(источник),
        "коммит": коммит,
        "незакоммиченных_в_источнике": len(грязно.splitlines()),
        "установлено": dt.datetime.now(dt.timezone.utc)
                         .strftime("%Y-%m-%dT%H:%M:%SZ"),
        "файлы": {},
    }
    for и in НАБОР_УСТАНОВКИ:
        куда = цель / и
        куда.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(источник / и, куда)
        опись["файлы"][и] = _сумма(куда)
        print(строка(True, f"{и}"))
    for и in НУЖНЫЕ_КАТАЛОГИ + ("var/ansible",):
        (цель / и).mkdir(parents=True, exist_ok=True)
    (цель / ОПИСЬ_УСТАНОВКИ).write_text(
        json.dumps(опись, ensure_ascii=False, indent=1) + "\n",
        encoding="utf-8")
    print(строка(True, f"опись {ОПИСЬ_УСТАНОВКИ}: коммит {коммит[:12]}, "
                       f"файлов {len(опись['файлы'])}"))
    ген = цель / "automation" / "local" / "render-ansible-inventory.py"
    п = subprocess.run([sys.executable, str(ген)], cwd=str(цель),
                       capture_output=True, text=True)
    ладно = п.returncode == 0 and (цель / "var" / "ansible" / "hosts.yml").is_file()
    print(строка(ладно, f"инвентарь сгенерирован (код {п.returncode})"))
    if п.stderr.strip():
        print("       " + п.stderr.strip()[:200])
    return 0 if ладно else 1


def сверить(цель) -> int:
    """Совпадает ли установленное с описью. Расхождение — повод переустановить."""
    import json
    оп = цель / ОПИСЬ_УСТАНОВКИ
    if not оп.is_file():
        print(строка(False, f"описи {ОПИСЬ_УСТАНОВКИ} нет: установка не "
                            f"подтверждается"))
        return 1
    опись = json.loads(оп.read_text(encoding="utf-8"))
    плохо = 0
    for и, сумма in (опись.get("файлы") or {}).items():
        п = цель / и
        ладно = п.is_file() and _сумма(п) == сумма
        плохо += not ладно
        print(строка(ладно, и))
    print(f"       установлено из коммита {опись.get('коммит', '')[:12]} "
          f"{опись.get('установлено', '')}")
    return 1 if плохо else 0


def главная(аргв: list[str] | None = None) -> int:
    р = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    р.add_argument("--root", default="/srv/site-factory/repo")
    р.add_argument("--apply", action="store_true")
    р.add_argument("--check-ssh", action="store_true")
    р.add_argument("--provision", metavar="КАТАЛОГ",
                   help="разложить набор доставки в постоянный каталог")
    р.add_argument("--from", dest="источник", default=None,
                   help="откуда брать набор (по умолчанию эта рабочая копия)")
    р.add_argument("--verify", metavar="КАТАЛОГ",
                   help="сверить установленное с описью")
    а = р.parse_args(аргв)

    if а.provision:
        источник = Path(а.источник or Path(__file__).resolve().parents[2])
        цель = Path(а.provision)
        print(f"=== установка набора доставки: {источник} -> {цель}")
        код = установить(источник, цель)
        print(f"\nустановка {'выполнена' if код == 0 else 'НЕ выполнена'}")
        return код
    if а.verify:
        цель = Path(а.verify)
        print(f"=== сверка установки {цель}")
        код = сверить(цель)
        print(f"\nрасхождений: {код}")
        return код

    корень = Path(а.root)
    плохо = 0

    print(f"=== рабочая копия {корень}")
    есть = корень.is_dir()
    print(строка(есть, f"каталог существует"))
    плохо += not есть
    if есть and (корень / ".git").exists():
        голова = subprocess.run(["git", "-C", str(корень), "log", "--oneline", "-1"],
                                capture_output=True, text=True).stdout.strip()
        ветка = subprocess.run(["git", "-C", str(корень), "rev-parse",
                                "--abbrev-ref", "HEAD"],
                               capture_output=True, text=True).stdout.strip()
        print(f"       ветка {ветка or '—'}, голова {голова or '—'}")

    print("=== сценарии доставки (есть только после слияния ветки)")
    for имя in НУЖНЫЕ_СЦЕНАРИИ:
        ладно = (корень / имя).is_file()
        плохо += not ладно
        print(строка(ладно, имя))

    print("=== инвентарь и доступ")
    опись = корень / "inventory" / "ssh-hosts.yaml"
    ладно = опись.is_file()
    плохо += not ладно
    print(строка(ладно, "inventory/ssh-hosts.yaml"))
    закреплённый = корень / "inventory" / "known_hosts.d" / ХОСТ
    ладно = закреплённый.is_file()
    плохо += not ладно
    print(строка(ладно, f"inventory/known_hosts.d/{ХОСТ} (закрепление ключа хоста)"))
    ключ = путь_ключа(корень)
    if ключ:
        п = Path(ключ)
        ладно = п.is_file()
        плохо += not ладно
        права = oct(п.stat().st_mode & 0o777)[2:] if ладно else "—"
        print(строка(ладно, f"ssh-ключ по пути из инвентаря, права {права} "
                            f"(содержимое не читается)"))
    else:
        плохо += 1
        print(строка(False, "путь к ssh-ключу в инвентаре не найден"))
    инв = корень / "var" / "ansible" / "hosts.yml"
    print(строка(инв.is_file(), "var/ansible/hosts.yml (генерируется, в git его нет)"))

    print("=== данные и издатель")
    ладно = ЖИВОЙ_ИЗДАТЕЛЬ.is_file()
    плохо += not ладно
    print(строка(ладно, f"живой издатель {ЖИВОЙ_ИЗДАТЕЛЬ}"))
    ладно = СНИМОК.is_file()
    плохо += not ладно
    возраст = ""
    if ладно:
        import datetime as dt
        к = dt.datetime.fromtimestamp(СНИМОК.stat().st_mtime, dt.timezone.utc)
        часы = (dt.datetime.now(dt.timezone.utc) - к).total_seconds() / 3600
        возраст = f", обновлён {к:%Y-%m-%d %H:%M}Z ({часы:.1f} ч назад)"
    print(строка(ладно, f"снимок поставщика{возраст}"))

    print("=== каталоги записи")
    for имя in НУЖНЫЕ_КАТАЛОГИ:
        п = корень / имя
        ладно = п.is_dir() and os.access(п, os.W_OK)
        print(строка(ладно, имя))

    if а.apply:
        print("=== применение (без root)")
        for имя in НУЖНЫЕ_КАТАЛОГИ + ("var/ansible",):
            п = корень / имя
            try:
                п.mkdir(parents=True, exist_ok=True)
                print(строка(True, f"каталог {имя} готов"))
            except OSError as ош:
                плохо += 1
                print(строка(False, f"каталог {имя}: {ош}"))
        ген = корень / "automation" / "local" / "render-ansible-inventory.py"
        if ген.is_file():
            п = subprocess.run([sys.executable, str(ген)], cwd=str(корень),
                               capture_output=True, text=True)
            ладно = п.returncode == 0 and (корень / "var" / "ansible" /
                                           "hosts.yml").is_file()
            плохо += not ладно
            print(строка(ладно, f"инвентарь сгенерирован (код {п.returncode})"))
            if п.stderr.strip():
                print("       " + п.stderr.strip()[:200])
        else:
            плохо += 1
            print(строка(False, "render-ansible-inventory.py нет — ветка не слита"))

    if а.check_ssh:
        print("=== связь с узлом")
        инв = корень / "var" / "ansible" / "hosts.yml"
        if not инв.is_file():
            плохо += 1
            print(строка(False, "инвентаря нет, связь не проверяется"))
        else:
            п = subprocess.run(["ansible", "-i", str(инв), ХОСТ, "-m", "ping"],
                               capture_output=True, text=True, cwd=str(корень))
            ладно = "SUCCESS" in п.stdout
            плохо += not ладно
            print(строка(ладно, "ansible ping"))

    print(f"\nнехваток: {плохо}")
    if плохо:
        print("Пока есть нехватки, таймер доставки включать нельзя: он "
              "запустится и упадёт.")
    return 1 if плохо else 0


if __name__ == "__main__":
    sys.exit(главная())
