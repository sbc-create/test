#!/usr/bin/env python3
"""Аудит цепочки исполнения root-юнитов: что именно root запускает и кто это может переписать.

Проверяется не «ExecStart принадлежит root», а вся достижимая цепочка. Root-юнит
скомпрометирован целиком, если не-root может подменить хотя бы одно звено:

* сам исполняемый файл и любой его родительский каталог;
* цель символической ссылки — и её родители;
* интерпретатор из шебанга;
* интерпретатор, названный в ``Environment=`` (``FACTORY_PYTHON`` и подобные);
* каталог инструментов (``NOVA_TOOLS``) — из него скрипт запускает соседей;
* каждый элемент ``PYTHONPATH``: подменённый модуль исполняется так же, как скрипт;
* ``EnvironmentFile``: переменные из него влияют на то, что запустится;
* каждый каталог ``PATH``, потому что ``#!/usr/bin/env bash`` ищет bash по PATH.

Единица измерения — **эффективный** юнит: базовый файл плюс drop-in'ы, с
правилом сброса ``ExecStart=``. Без него закреплённый юнит выглядел бы
нарушителем, а подменённый через drop-in — чистым.

Модуль без побочных эффектов и ничего не исполняет: он только читает метаданные.
Значения секретов он не читает и прочитать не может — ни одно из проверяемых
полей их не содержит.
"""
from __future__ import annotations

import argparse
import json
import pwd
import re
import stat
from dataclasses import dataclass, field
from pathlib import Path

UNIT_DIR = Path("/etc/systemd/system")

EXECSTART_RE = re.compile(r"^ExecStart[^=]*=\s*[-+!@]*(.*)$")
USER_RE = re.compile(r"^User=\s*(\S+)\s*$")
ENV_RE = re.compile(r"^Environment=\s*(.*)$")
ENVFILE_RE = re.compile(r"^EnvironmentFile=\s*-?(\S+)\s*$")
WORKDIR_RE = re.compile(r"^WorkingDirectory=\s*(\S+)\s*$")

#: Переменные, значение которых — путь к коду, а не к данным. Разница
#: существенная: данные root читает и пишет по назначению, код он ИСПОЛНЯЕТ.
CODE_PATH_VARS = ("FACTORY_PYTHON", "NOVA_TOOLS", "PYTHONPATH", "PATH",
                  "FACTORY_TOOLS", "LORDS_TOOLS")

DEFAULT_PATH = "/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"


@dataclass
class Problem:
    unit: str
    path: str
    reason: str
    link: str = ""

    def as_dict(self) -> dict:
        out = {"unit": self.unit, "path": self.path, "reason": self.reason}
        if self.link:
            out["via"] = self.link
        return out


@dataclass
class UnitView:
    name: str
    runs_as_root: bool
    exec_starts: list[str] = field(default_factory=list)
    environment: dict[str, str] = field(default_factory=dict)
    env_files: list[str] = field(default_factory=list)
    working_directory: str = ""
    holds_credentials: bool = False


def _owner(path: Path) -> str | None:
    try:
        return pwd.getpwuid(path.lstat().st_uid).pw_name
    except (OSError, KeyError):
        return None


def _mode(path: Path) -> int | None:
    try:
        return stat.S_IMODE(path.lstat().st_mode)
    except OSError:
        return None


def _split_env(raw: str) -> dict[str, str]:
    """Разбор `Environment=` — допускает несколько пар и кавычки."""
    out: dict[str, str] = {}
    for token in _tokenize(raw):
        key, sep, value = token.partition("=")
        if sep:
            out[key.strip()] = value
    return out


def _tokenize(raw: str) -> list[str]:
    tokens, current, quote = [], "", ""
    for ch in raw.strip():
        if quote:
            if ch == quote:
                quote = ""
            else:
                current += ch
        elif ch in "'\"":
            quote = ch
        elif ch.isspace():
            if current:
                tokens.append(current)
                current = ""
        else:
            current += ch
    if current:
        tokens.append(current)
    return tokens


def read_unit(unit: Path) -> UnitView | None:
    """Эффективный вид юнита: базовый файл плюс drop-in'ы, по порядку."""
    texts: list[str] = []
    try:
        texts.append(unit.read_text(encoding="utf-8", errors="replace"))
    except OSError:
        return None
    dropin_dir = unit.with_name(unit.name + ".d")
    if dropin_dir.is_dir():
        try:
            for conf in sorted(dropin_dir.glob("*.conf")):
                texts.append(conf.read_text(encoding="utf-8", errors="replace"))
        except OSError:
            pass

    view = UnitView(name=unit.name, runs_as_root=True)
    user = None
    for text in texts:
        for line in text.splitlines():
            line = line.strip()
            match = USER_RE.match(line)
            if match:
                user = match.group(1)
                continue
            match = EXECSTART_RE.match(line)
            if match:
                value = match.group(1).strip()
                if not value:
                    # Пустое присваивание сбрасывает список — так drop-in
                    # ЗАМЕНЯЕТ команду, а не добавляет вторую.
                    view.exec_starts = []
                else:
                    view.exec_starts.append(value)
                continue
            match = ENV_RE.match(line)
            if match:
                view.environment.update(_split_env(match.group(1)))
                continue
            match = ENVFILE_RE.match(line)
            if match:
                view.env_files.append(match.group(1))
                continue
            match = WORKDIR_RE.match(line)
            if match:
                view.working_directory = match.group(1)
                continue
            if line.startswith("LoadCredential="):
                view.holds_credentials = True
    view.runs_as_root = (user == "root") if user is not None else True
    return view


def _check_path(unit: str, raw: str, *, kind: str, follow: bool = True,
                seen: set | None = None) -> list[Problem]:
    """Путь и все его родители: владелец root и закрыт на запись остальным."""
    problems: list[Problem] = []
    seen = seen if seen is not None else set()
    path = Path(raw)
    if not path.is_absolute() or raw in seen:
        return problems
    seen.add(raw)
    if not path.exists() and not path.is_symlink():
        return problems

    for node in [path, *path.parents]:
        owner = _owner(node)
        mode = _mode(node)
        if owner is None or mode is None:
            continue
        if node.is_symlink():
            # У символической ссылки биты режима на Linux всегда 0777 и ни на
            # что не влияют: право подменить ссылку даёт КАТАЛОГ, в котором она
            # лежит, а он проверяется отдельно — как родитель. Поэтому у ссылки
            # смотрится только владелец. Иначе проверка объявляла бы дефектом
            # /bin и /sbin на каждой системе, где они ссылки в /usr.
            if owner != "root":
                problems.append(Problem(unit, str(node),
                                        f"{kind}: символическая ссылка принадлежит {owner}"))
            continue
        if owner != "root":
            problems.append(Problem(unit, str(node), f"{kind}: принадлежит {owner}"))
        if mode & 0o022:
            problems.append(Problem(unit, str(node),
                                    f"{kind}: открыт на запись не владельцу ({mode:04o})"))

    if follow and path.is_symlink():
        try:
            target = path.resolve()
        except OSError:
            return problems
        problems.extend(_check_path(unit, str(target), kind=f"{kind} → цель ссылки",
                                    follow=False, seen=seen))
    return problems


def _shebang_interpreter(path: Path) -> str | None:
    try:
        with path.open("rb") as handle:
            first = handle.readline(256)
    except OSError:
        return None
    if not first.startswith(b"#!"):
        return None
    parts = first[2:].decode("utf-8", "replace").strip().split()
    if not parts:
        return None
    # `#!/usr/bin/env bash` — интерпретатор ищется по PATH; сам env root-owned,
    # а найденный им bash проверяется отдельно, через элементы PATH.
    return parts[0]


def audit_unit(view: UnitView) -> list[Problem]:
    problems: list[Problem] = []
    if not view.runs_as_root:
        return problems

    for command in view.exec_starts:
        tokens = _tokenize(command)
        if not tokens:
            continue
        executable = tokens[0]
        problems.extend(_check_path(view.name, executable, kind="ExecStart"))

        exe_path = Path(executable)
        if exe_path.is_file():
            interpreter = _shebang_interpreter(exe_path)
            if interpreter:
                problems.extend(_check_path(view.name, interpreter, kind="шебанг"))
        # Аргумент-скрипт: `python foo.py` исполняет foo.py так же, как сам python.
        for argument in tokens[1:]:
            if argument.startswith("/") and Path(argument).is_file():
                problems.extend(_check_path(view.name, argument, kind="аргумент-скрипт"))

    for name in CODE_PATH_VARS:
        value = view.environment.get(name)
        if not value:
            continue
        separator = ":" if name in ("PYTHONPATH", "PATH") else None
        candidates = value.split(separator) if separator else [value]
        for candidate in candidates:
            if candidate:
                problems.extend(_check_path(view.name, candidate, kind=f"{name}"))

    if "PATH" not in view.environment:
        for entry in DEFAULT_PATH.split(":"):
            problems.extend(_check_path(view.name, entry, kind="PATH по умолчанию"))

    for env_file in view.env_files:
        problems.extend(_check_path(view.name, env_file, kind="EnvironmentFile"))

    if view.working_directory:
        problems.extend(_check_path(view.name, view.working_directory,
                                    kind="WorkingDirectory"))
    return problems


def audit(unit_dir: Path | None = None, only: list[str] | None = None) -> dict:
    directory = unit_dir or UNIT_DIR
    units = []
    if directory.is_dir():
        units = sorted(p for p in directory.glob("*.service") if p.is_file())
    if only:
        wanted = set(only)
        units = [u for u in units if u.name in wanted]

    problems: list[Problem] = []
    audited: list[str] = []
    credential_units: list[str] = []
    for unit in units:
        view = read_unit(unit)
        if view is None or not view.runs_as_root:
            continue
        audited.append(view.name)
        found = audit_unit(view)
        if view.holds_credentials and found:
            credential_units.append(view.name)
        problems.extend(found)

    by_unit: dict[str, list[dict]] = {}
    for problem in problems:
        by_unit.setdefault(problem.unit, []).append(problem.as_dict())

    return {
        "unit_dir": str(directory),
        "root_units_audited": len(audited),
        "units_with_problems": sorted(by_unit),
        "credential_units_with_problems": sorted(credential_units),
        "problem_count": len(problems),
        "problems": [p.as_dict() for p in problems],
        "clean": not problems,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="audit_root_units",
        description="Аудит цепочки исполнения root-юнитов. Ничего не меняет.")
    parser.add_argument("--unit-dir", default=str(UNIT_DIR))
    parser.add_argument("--only", action="append",
                        help="проверить только названный unit (можно повторять)")
    parser.add_argument("--json", action="store_true", help="машинный вывод")
    args = parser.parse_args(argv)

    report = audit(Path(args.unit_dir), args.only)
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(f"root-юнитов проверено: {report['root_units_audited']}")
        if report["clean"]:
            print("нарушений нет: root исполняет только root-owned код")
        else:
            print(f"НАРУШЕНИЙ: {report['problem_count']}")
            for problem in report["problems"]:
                print(f"  {problem['unit']}: {problem['path']} — {problem['reason']}")
            if report["credential_units_with_problems"]:
                print("\nИЗ НИХ ПОЛУЧАЮТ РАСШИФРОВАННЫЕ CREDENTIALS: "
                      + ", ".join(report["credential_units_with_problems"]))
    return 0 if report["clean"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
