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

Третья ловушка — команда, которую проверка МОЛЧА ПРОПУСКАЛА. Форма
`python3 -m <модуль>` не содержит ни пути сценария, ни расширения `.py`, и
разбор возвращал «исполняемого файла нет» → строка не проверялась вовсе. 13.10
в пакет едва не попал вызов анализатора журналов без обязательного `--format`:
инструмент отказал бы на первой же строке, а проверка пакета оставалась
зелёной. Проверка, которая не может отказать, доверия не несёт (D203/D205).

Что проверяется по каждому блоку ```bash``` документа:

* путь сценария существует и исполняем (для `bash`/`sudo bash`) или читается
  (для `python3`); относительный путь разрешается от объявленного `cd`, а без
  него остаётся расхождением — проверять нечего;
* если сценарий читает `$SRC_ROOT/config/site-cells.json` или заготовку
  `nginx-site/<site>.conf` — эти файлы существуют РЯДОМ С НИМ;
* значение `--site` есть в реестре ячеек;
* ключи `--site` против позиционного аргумента: сценарий, объявивший `--site` в
  своём заголовке, позиционный не принимает;
* `python3 -m <модуль>` разрешается в файл относительно ОБЪЯВЛЕННОГО каталога
  запуска (`cd … && python3 -m …`); без объявленного каталога такая команда —
  расхождение, а не пропуск;
* обязательные ключи инструмента (argparse `required=True`, читается через
  `ast`) присутствуют в команде.

Код возврата 1 — есть расхождения; 0 — пакет проверяем целиком.
"""
from __future__ import annotations

import argparse
import ast
import importlib.util
import json
import re
import sys

import yaml
from pathlib import Path
from typing import NamedTuple

КОРЕНЬ = Path(__file__).resolve().parents[2]


class БлокКоманд(NamedTuple):
    """Команды одного блока и узел, на котором они исполняются.

    `узел is None` — блок для ЭТОЙ машины: пути проверяются здесь. Иначе
    локальные пути не проверяются вовсе, и это сказано в сводке: проверка,
    которая молча ничего не смотрит, доверия не несёт.
    """

    узел: str | None
    команды: list[tuple[Path | None, str]]
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


def каталоги_и_команды(текст: str) -> list[tuple[Path | None, str]]:
    """Команды блоков вместе с ОБЪЯВЛЕННЫМ каталогом запуска.

    Каталог берётся из `cd <путь>` — в той же строке через `&&` или в
    предыдущей строке того же блока. Он нужен формам, у которых пути в самой
    команде нет: `python3 -m <модуль>`.
    """
    итог: list[tuple[Path | None, str]] = []
    for блок in _строки_блоков(текст):
        итог += блок.команды
    return итог


#: Метка блока, исполняемого на другой машине: `# host: <ref из inventory>`.
МЕТКА_ХОСТА = re.compile(r"^\s*#\s*host:\s*([\w.-]+)\s*$", re.M)


def _строки_блоков(текст: str) -> list[БлокКоманд]:
    блоки_: list[БлокКоманд] = []
    for кусок in re.findall(r"```bash\n(.*?)```", текст, re.S):
        найдено = МЕТКА_ХОСТА.search(кусок)
        узел = найдено.group(1) if найдено else None
        текущий: Path | None = None
        собранные: list[tuple[Path | None, str]] = []
        for команда in _склеить(кусок):
            части = [ч.strip() for ч in команда.split("&&")]
            for ч in части:
                сл = ч.split()
                if сл and сл[0] == "cd" and len(сл) > 1:
                    текущий = Path(сл[1])
                    continue
                if сл:
                    собранные.append((текущий, ч))
        блоки_.append(БлокКоманд(узел, собранные))
    return блоки_


def _склеить(кусок: str) -> list[str]:
    """Логические строки блока: продолжения `\\` склеены, комментарии убраны."""
    итог: list[str] = []
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


def блоки(текст: str) -> list[str]:
    """Строки команд из всех блоков ```bash ... ``` (без каталогов запуска)."""
    return [к for _, к in каталоги_и_команды(текст)]


def путь_сценария(команда: str) -> tuple[Path | None, str]:
    """Путь исполняемого файла из команды и способ запуска.

    `install src dst` исполняемого файла не содержит: это копирование, и
    `.py`-источник там — данные. Такие строки проверяет `файлы_установки`,
    иначе источник требует исполнимости и обязательных ключей ни за что.
    """
    части = команда.split()
    if "install" in части and not any(ч in ПИТОНЫ for ч in части):
        return None, ""
    # Цель перенаправления — не исполняемый файл: `… > /tmp/откат.py` ничего
    # не запускает, а создаёт. Разбор идёт только по части ДО `>`.
    for i, ч in enumerate(части):
        if ч.startswith(">"):
            части = части[:i]
            break
    способ = ""
    for i, ч in enumerate(части):
        if ч in ("sudo", "-m", "0644", "0755"):
            continue
        if ч in ("bash", "python3", "/usr/bin/bash", "/usr/bin/python3") \
                or ч.endswith(("/python", "/python3", "/bash")):
            способ = "bash" if "bash" in ч else "python3"
            continue
        if ":" in ч:
            # `<ревизия>:<путь>` и `host:путь` — не файл на диске, а адрес
            # внутри истории или на другой машине; путём его считать нельзя.
            continue
        if ч.startswith("/") and (ч.endswith(".sh") or ч.endswith(".py")):
            return Path(ч), способ or "прямой"
        if ч.startswith("-"):
            continue
        if ч.endswith(".sh") or ч.endswith(".py"):
            return Path(ч), способ or "прямой"
    return None, способ


def файлы_установки(команда: str) -> list[Path]:
    """Источники команды `install`: всё, кроме каталога назначения и ключей.

    Нужно отдельно: у `install` нет исполняемого сценария, и первая версия
    проверки такие строки пропускала молча — а это ровно те файлы, которых
    может не быть («install -m 0644 … unit /etc/systemd/system/»).
    """
    части = команда.split()
    if "install" not in части:
        return []
    кандидаты = [Path(ч) for ч in части
                 if ч.startswith("/") and not ч.startswith("/etc/")]
    return [п for п in кандидаты if п.suffix]


ПИТОНЫ = ("python3", "/usr/bin/python3", "python")


def модуль_в_команде(команда: str) -> str | None:
    """Имя модуля из формы `python3 -m <модуль>`.

    `-m` принадлежит питону, а не любой команде: у `install -m 0644` это режим
    доступа, и первая версия проверки принимала его за модуль.
    """
    части = команда.split()
    питон = next((i for i, ч in enumerate(части) if ч in ПИТОНЫ), None)
    if питон is None:
        return None
    for i in range(питон + 1, len(части) - 1):
        if части[i] == "-m" and not части[i + 1].startswith("-"):
            return части[i + 1]
    return None


def путь_модуля(модуль: str, каталог: Path) -> Path | None:
    """Файл модуля относительно каталога запуска: `a.b` → `a/b.py` или пакет."""
    основа = каталог.joinpath(*модуль.split("."))
    for кандидат in (основа.with_suffix(".py"), основа / "__main__.py"):
        if кандидат.is_file():
            return кандидат
    return None


def установленный(модуль: str) -> bool:
    """Модуль есть в окружении (`pytest`, `json.tool`), а не в дереве проекта."""
    try:
        return importlib.util.find_spec(модуль.split(".")[0]) is not None
    except (ImportError, ValueError):
        return False


def обязательные_ключи(путь: Path) -> list[str]:
    """Ключи argparse с `required=True` — читаются разбором кода, не строкой.

    Повод: вызов анализатора журналов без `--format` выглядит как рабочая
    команда и отказывает только в терминале владельца.
    """
    if путь.suffix != ".py":
        return []
    try:
        текст = путь.read_text(encoding="utf-8", errors="replace")
        дерево = ast.parse(текст)
    except (OSError, SyntaxError):
        return []
    if "add_subparsers" in текст:
        # У подкоманд обязательные ключи СВОИ: `--run-id` нужен одной из них, а
        # не всем. Какой именно — из команды не видно, и требовать его от всех
        # значит выдумывать требование. Такой файл не проверяется по ключам.
        return []
    итог: list[str] = []
    for узел in ast.walk(дерево):
        if not (isinstance(узел, ast.Call)
                and isinstance(узел.func, ast.Attribute)
                and узел.func.attr == "add_argument"):
            continue
        обязателен = any(к.arg == "required"
                         and isinstance(к.value, ast.Constant)
                         and к.value.value is True for к in узел.keywords)
        if not обязателен:
            continue
        for арг in узел.args:
            if isinstance(арг, ast.Constant) and str(арг.value).startswith("--"):
                итог.append(str(арг.value))
    return итог


def созданные_пути(команда: str) -> list[Path]:
    """Файлы, которые команда САМА создаёт: перенаправление вывода.

    Нужно для порядка внутри блока: строка вида `… > /tmp/откат.py` создаёт
    источник следующей строки, и требовать его существования ЗАРАНЕЕ — ошибка
    проверки, а не документа.
    """
    итог: list[Path] = []
    части = команда.split()
    for i, ч in enumerate(части[:-1]):
        if ч in (">", ">>") and части[i + 1].startswith("/"):
            итог.append(Path(части[i + 1]))
        elif ч.startswith(">") and len(ч) > 1 and ч.lstrip(">").startswith("/"):
            итог.append(Path(ч.lstrip(">")))
    хвост = части[-1]
    if хвост.startswith(">") and хвост.lstrip(">").startswith("/"):
        итог.append(Path(хвост.lstrip(">")))
    return итог


def проверить(док: Path, *, строгий_каталог: bool = True,
              корень: Path = КОРЕНЬ) -> list[str]:
    """Расхождения документа.

    `строгий_каталог` — планка пакета владельца: он вставляет строки в терминал,
    где рабочий каталог ничем не задан, поэтому блок обязан объявить `cd`.
    Обычная документация живёт по соглашению «команды от корня репозитория»:
    для неё планка снимается, а каталогом по умолчанию служит `корень`.
    """
    беды: list[str] = []
    известные = site_id_ы()
    каталоги_проверены: set[Path] = set()
    узлы = inventory_хосты()
    for блок in _строки_блоков(док.read_text(encoding="utf-8")):
        if блок.узел is not None:
            # Метка действует только для утверждённого хоста. Иначе она была
            # бы способом отключить проверку одной строкой комментария.
            if блок.узел not in узлы:
                беды.append(f"метка «# host: {блок.узел}» указывает на хост вне "
                            f"inventory/ssh-hosts.yaml — блок не проверяется и "
                            f"не может быть помечен")
            continue
        беды += _проверить_блок(блок.команды, известные, каталоги_проверены,
                                строгий_каталог, корень)
    return беды


def inventory_хосты() -> set[str]:
    """Имена и адреса хостов из реестра — для метки блока."""
    try:
        д = yaml.safe_load((КОРЕНЬ / "inventory" / "ssh-hosts.yaml")
                           .read_text(encoding="utf-8")) or {}
    except (OSError, ValueError):
        return set()
    итог: set[str] = set()
    for з in д.get("hosts") or []:
        for ключ in ("ref", "hostname"):
            if з.get(ключ):
                итог.add(str(з[ключ]))
    return итог


def это_заготовка(значение: str | Path) -> bool:
    """`<проект>`, `<repo>`, `path/to/…` — место для подстановки.

    Спрашивать такой путь на диске бессмысленно: документ и не утверждает, что
    он существует. Молчать о нём — не поблажка, а отказ от ложной тревоги.
    """
    с = str(значение)
    return "<" in с or ">" in с or с.startswith("path/to") or "/path/to" in с


def _проверить_блок(блок: list[tuple[Path | None, str]], известные: set[str],
                    каталоги_проверены: set[Path], строгий_каталог: bool,
                    корень: Path) -> list[str]:
    беды: list[str] = []
    создано: set[Path] = set()
    for каталог, команда in блок:
        if каталог is not None and это_заготовка(каталог):
            continue
        if каталог is None and not строгий_каталог:
            каталог = корень
        коротко = команда[:88]
        создано.update(созданные_пути(команда))
        if каталог is not None and каталог not in каталоги_проверены:
            каталоги_проверены.add(каталог)
            if not каталог.is_dir():
                беды.append(f"каталога запуска НЕТ: {каталог} ← {коротко}")
        модуль = модуль_в_команде(команда)
        if модуль and not модуль.endswith((".sh", ".py")):
            if каталог is None:
                беды.append(f"python3 -m {модуль}: каталог запуска не объявлен в "
                            f"блоке, модуль не проверяем ← {коротко}")
            else:
                файл = путь_модуля(модуль, каталог)
                if файл is None and установленный(модуль):
                    файл = None   # есть в окружении: проверять нечего
                elif файл is None:
                    беды.append(f"модуля НЕТ: {модуль} в {каталог} ← {коротко}")
                else:
                    for ключ in обязательные_ключи(файл):
                        if ключ not in команда.split():
                            беды.append(f"{модуль}: нет обязательного ключа "
                                        f"{ключ} ← {коротко}")
        for источник in файлы_установки(команда):
            if источник in создано:
                continue
            if not источник.is_file():
                беды.append(f"install: источника НЕТ: {источник} ← {команда[:80]}")
        путь, способ = путь_сценария(команда)
        if путь is None:
            continue
        if not путь.is_absolute():
            if каталог is None:
                беды.append(f"относительный путь сценария, каталог запуска не "
                            f"объявлен в блоке: {коротко}")
                continue
            путь = каталог / путь
        if это_заготовка(путь):
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
        for ключ in обязательные_ключи(путь):
            if ключ not in команда.split():
                беды.append(f"{путь.name}: нет обязательного ключа {ключ} ← {коротко}")
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
    р.add_argument("--relaxed-cwd", action="store_true",
                   help="обычная документация: команды от корня репозитория, "
                        "объявлять `cd` в блоке не требуется")
    а = р.parse_args()
    док = Path(а.документ)
    if not док.is_file():
        print(f"ОТКАЗ: нет {док}", file=sys.stderr)
        return 2
    команды = блоки(док.read_text(encoding="utf-8"))
    удалённые = [б for б in _строки_блоков(док.read_text(encoding="utf-8"))
                 if б.узел is not None]
    беды = проверить(док, строгий_каталог=not а.relaxed_cwd)
    print(f"документ: {док.name}; команд в блоках: {len(команды)}")
    if удалённые:
        всего = sum(len(б.команды) for б in удалённые)
        узлы = ", ".join(sorted({str(б.узел) for б in удалённые}))
        print(f"блоков для другой машины: {len(удалённые)} ({всего} команд, "
              f"узлы: {узлы}) — их пути проверяются ТАМ, не здесь")
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
