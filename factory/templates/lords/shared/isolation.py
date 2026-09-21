#!/usr/bin/env python3
"""Жёсткая изоляция фабрики шаблонов Lords.

## Что изолируется и от чего

Фабрика авторская: она сочиняет и проверяет шаблонные пакеты. Живого рантайма
она не касается вовсе. Но «не касается» — это намерение, а намерение не
проверяется. Здесь оно превращено в проверяемое свойство.

Три границы:

* **Рантайм.** Ни один путь фабрики не ведёт в `/srv/lords/.frontend`,
  `/srv/lords/<витрина>`, `/etc/systemd` и прочие живые каталоги. Сегодня в том
  же `/srv/lords/.frontend` посторонняя сессия уже создавала релизы Animedia —
  и именно поэтому граница нужна физическая, а не устная.

* **Семейство.** В пакете Lords не должно быть ни animedia, ни zona, ни yummy:
  ни в идентификаторах, ни в путях, ни в текстах. Шаблон, знающий про чужое
  семейство, рано или поздно окажется на чужом домене.

* **Домены.** Пакет не называет конкретных доменов. Домен приходит из
  назначения и живёт в реестре, а не в шаблоне: вписанный в шаблон домен — это
  привязка, которую нельзя ни переназначить, ни проверить.

Исключение ровно одно и оно объявлено: `preview_domain` вида
`lords-tNNN.example`. Он существует, чтобы канонический адрес превью не был
пустым, и намеренно взят из зарезервированного домена `example`, который не
может принадлежать никому.

Запуск: `isolation.py --root factory/templates/lords` — код 2 при нарушении.
"""

from __future__ import annotations

import argparse
import json
import pathlib
import re
import sys

#: Живые каталоги, упоминание которых в пакете или в его сборке запрещено.
ЖИВЫЕ_ПУТИ = (
    "/srv/lords/.frontend",
    "/srv/lords/lords-",
    "/etc/systemd",
    "/etc/nginx",
    "/var/lib/lords-deploy",
)

#: Чужие семейства. Lords не должен знать о них ничего.
ЧУЖИЕ_СЕМЕЙСТВА = ("animedia", "zona", "yummy", "yummyani")

#: Домен допускается только в виде превью на зарезервированном example.
ПРЕВЬЮ_ДОМЕН = re.compile(r"^lords-t\d{3}\.example$")

#: Что считается настоящим доменом в тексте пакета.
ДОМЕН_В_ТЕКСТЕ = re.compile(
    r"\b[a-z0-9][a-z0-9-]*\.(?:ru|com|net|org|biz|space|online|icu|site|info|tv)\b"
)

OK, НАРУШЕНИЕ = 0, 2


def файлы_пакета(пакет: pathlib.Path):
    for путь in sorted(пакет.rglob("*")):
        if путь.is_file() and путь.suffix in (".json", ".css", ".md", ".yaml", ".yml"):
            yield путь


def проверить_пакет(пакет: pathlib.Path) -> list[str]:
    нарушения: list[str] = []
    манифест_путь = пакет / "template.json"
    манифест = json.loads(манифест_путь.read_text(encoding="utf-8")) if манифест_путь.is_file() else {}

    превью = манифест.get("preview_domain", "")
    if превью and not ПРЕВЬЮ_ДОМЕН.match(превью):
        нарушения.append(
            f"{пакет.name}: preview_domain «{превью}» не вида lords-tNNN.example — "
            f"пакет не имеет права называть настоящий домен"
        )

    for путь in файлы_пакета(пакет):
        текст = путь.read_text(encoding="utf-8", errors="replace")
        низ = текст.lower()

        for живой in ЖИВЫЕ_ПУТИ:
            if живой in текст:
                нарушения.append(f"{пакет.name}/{путь.name}: путь живого контура «{живой}»")

        for чужое in ЧУЖИЕ_СЕМЕЙСТВА:
            if чужое in низ:
                нарушения.append(f"{пакет.name}/{путь.name}: упоминание чужого семейства «{чужое}»")

        for домен in set(ДОМЕН_В_ТЕКСТЕ.findall(низ)):
            if домен == превью.lower():
                continue
            нарушения.append(f"{пакет.name}/{путь.name}: настоящий домен «{домен}» внутри пакета")

    return нарушения


def проверить_ядро(ядро: pathlib.Path) -> list[str]:
    """Ядро вправе знать про пути фикстуры, но не про живой рантайм.

    Исключение — сборщик фикстуры: он ЧИТАЕТ живой каталог, чтобы взять
    настоящие данные, и этот единственный случай назван явно.
    """
    нарушения = []
    # Два файла обязаны называть живые пути, и оба названы поимённо:
    # сборщик фикстуры их ЧИТАЕТ, чтобы взять настоящие данные, а эта проверка
    # их ЗАПРЕЩАЕТ — запрет невозможно записать, не назвав запрещаемое.
    разрешено_читать = {"build_fixture.py", "isolation.py"}
    for путь in sorted(ядро.glob("*.py")):
        if путь.name in разрешено_читать:
            continue
        текст = путь.read_text(encoding="utf-8", errors="replace")
        for живой in ЖИВЫЕ_ПУТИ:
            if живой in текст:
                нарушения.append(f"ядро/{путь.name}: путь живого контура «{живой}»")
    return нарушения


def главное() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default="factory/templates/lords")
    parser.add_argument("--record")
    args = parser.parse_args()

    корень = pathlib.Path(args.root)
    пакеты = sorted(p for p in корень.iterdir()
                    if p.is_dir() and re.match(r"^T\d{3}-", p.name))

    все: list[str] = проверить_ядро(корень / "shared")
    for пакет in пакеты:
        все.extend(проверить_пакет(пакет))

    отчёт = {
        "packages_checked": len(пакеты),
        "violations": все,
        "ISOLATION_VIOLATIONS": len(все),
        "PASS": not все,
        "boundaries": {
            "runtime_paths_forbidden": list(ЖИВЫЕ_ПУТИ),
            "foreign_families_forbidden": list(ЧУЖИЕ_СЕМЕЙСТВА),
            "real_domains_forbidden": True,
            "preview_domain_allowed": "lords-tNNN.example",
        },
    }
    if args.record:
        pathlib.Path(args.record).parent.mkdir(parents=True, exist_ok=True)
        pathlib.Path(args.record).write_text(
            json.dumps(отчёт, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({k: v for k, v in отчёт.items() if k != "boundaries"},
                     ensure_ascii=False, indent=2))
    if все:
        for н in все[:20]:
            print("НАРУШЕНИЕ:", н, file=sys.stderr)
    return OK if not все else НАРУШЕНИЕ


if __name__ == "__main__":
    raise SystemExit(главное())
