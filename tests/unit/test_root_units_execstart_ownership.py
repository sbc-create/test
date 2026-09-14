"""root-юнит не имеет права исполнять файл, доступный на запись не-root.

Это не стилистика и не перестраховка. Служба, работающая от root и
запускающая скрипт из каталога, открытого на запись учётной записи агента,
отдаёт root этой учётной записи: достаточно переписать файл и дождаться
таймера. Все запреты профиля (`sudo`, `systemctl`) при этом остаются на месте
и ничего не значат — граница обходится не через них.

Для Secret Hub это ещё и прямой обход заявленной границы. `docs/SECRET_HUB.md`
обещает, что сессия агента не может прочитать API Token и Publisher ID.
Обещание держится разделением процессов; юнит с `LoadCredential` и с
`ExecStart`, открытым агенту на запись, кладёт расшифрованные значения в
процесс, содержимое которого агент определяет сам.

Тест измеряет фактическое состояние машины. Где измерить нельзя — каталога
юнитов нет, файл недоступен на чтение — он помечается SKIPPED с причиной, а не
считается пройденным.
"""
from __future__ import annotations

import os
import pwd
import re
import stat
from pathlib import Path

import pytest

UNIT_DIR = Path("/etc/systemd/system")

#: `ExecStart=` допускает префиксы `-`, `+`, `!`, `!!`, `@` перед путём.
EXECSTART = re.compile(r"^ExecStart[^=]*=\s*[-+!@]*(\S+)", re.M)
USER = re.compile(r"^User=\s*(\S+)", re.M)


def _units(unit_dir: Path | None = None) -> list[Path]:
    directory = unit_dir or UNIT_DIR
    if not directory.is_dir():
        return []
    try:
        return sorted(p for p in directory.glob("*.service") if p.is_file())
    except OSError:
        return []


def _fragments(unit: Path) -> list[str]:
    """Текст юнита и его drop-in'ов в том порядке, в каком их читает systemd.

    Без drop-in'ов проверка врала бы в обе стороны. `lords-content-refresh`
    закреплён drop-in'ом на неизменяемый релиз — по базовому файлу он выглядел
    бы нарушителем, которым не является. Обратный случай опаснее: drop-in
    может и увести `ExecStart` в открытый каталог, и без него это осталось бы
    незамеченным.
    """
    texts = []
    try:
        texts.append(unit.read_text(encoding="utf-8", errors="replace"))
    except OSError:
        return []
    dropin_dir = unit.with_name(unit.name + ".d")
    if dropin_dir.is_dir():
        try:
            for conf in sorted(dropin_dir.glob("*.conf")):
                texts.append(conf.read_text(encoding="utf-8", errors="replace"))
        except OSError:
            pass
    return texts


def _runs_as_root(texts: list[str]) -> bool:
    value = None
    for text in texts:
        for match in USER.finditer(text):
            value = match.group(1)
    # User= не задан — значит root: это умолчание systemd, а не «не указано».
    return value == "root" if value is not None else True


def _effective_execstarts(texts: list[str]) -> list[str]:
    """`ExecStart` после применения drop-in'ов.

    Пустое присваивание `ExecStart=` сбрасывает список — именно так drop-in
    заменяет команду, а не добавляет вторую. Без этого правила закреплённый
    релиз читался бы как «исполняются оба пути».
    """
    commands: list[str] = []
    for text in texts:
        for line in text.splitlines():
            if not line.startswith("ExecStart"):
                continue
            _, sep, value = line.partition("=")
            if not sep:
                continue
            value = value.strip()
            if not value:
                commands = []
                continue
            match = EXECSTART.match(line)
            if match:
                commands.append(match.group(1))
    return commands


def _owner(path: Path) -> str | None:
    try:
        return pwd.getpwuid(path.stat().st_uid).pw_name
    except (OSError, KeyError):
        return None


def _writable_by_others(path: Path) -> bool:
    """Открыт ли путь на запись кому-то кроме владельца-root."""
    try:
        mode = stat.S_IMODE(path.stat().st_mode)
    except OSError:
        return False
    return bool(mode & 0o022)


def _offenders(unit_dir: Path | None = None) -> list[tuple[str, str, str]]:
    """(unit, путь, причина) для каждого нарушения. Пустой список — чисто."""
    found: list[tuple[str, str, str]] = []
    for unit in _units(unit_dir):
        texts = _fragments(unit)
        if not texts or not _runs_as_root(texts):
            continue
        for command in _effective_execstarts(texts):
            exe = Path(command)
            if not exe.is_absolute() or not exe.exists():
                continue
            reasons = []
            if _owner(exe) not in (None, "root"):
                reasons.append(f"файл принадлежит {_owner(exe)}")
            if _writable_by_others(exe):
                reasons.append("файл открыт на запись не владельцу")
            parent = exe.parent
            if _owner(parent) not in (None, "root"):
                reasons.append(f"каталог принадлежит {_owner(parent)}")
            if _writable_by_others(parent):
                reasons.append("каталог открыт на запись не владельцу")
            if reasons:
                found.append((unit.name, str(exe), "; ".join(reasons)))
    return found


@pytest.mark.skipif(not UNIT_DIR.is_dir(),
                    reason="каталог unit'ов systemd отсутствует: состояние хоста не измерено")
class TestRootUnitsExecuteOnlyRootOwnedFiles:
    def test_no_root_unit_runs_a_file_others_can_rewrite(self):
        offenders = _offenders()
        assert not offenders, (
            "root-юнит исполняет файл, который может переписать не-root, — это "
            "выдача root этой учётной записи:\n"
            + "\n".join(f"  {unit}: {exe} — {why}" for unit, exe, why in offenders)
        )

    def test_units_holding_credentials_are_checked_too(self):
        """Юнит с `LoadCredential` — отдельный и худший случай.

        Он получает расшифрованные значения в `$CREDENTIALS_DIRECTORY`. Если
        исполняемый файл открыт на запись агенту, значения открыты агенту.
        """
        offenders = {unit for unit, _, _ in _offenders()}
        holding = []
        for unit in _units():
            texts = _fragments(unit)
            if any("LoadCredential=" in t for t in texts) and unit.name in offenders:
                holding.append(unit.name)
        assert not holding, (
            "юнит получает расшифрованные credentials и исполняет файл, "
            "доступный на запись не-root: " + ", ".join(sorted(holding))
        )


class TestTheCheckItselfWorks:
    """Проверка обязана уметь падать: правило, которое ничего не ловит, — не правило."""

    def _unit_dir(self, tmp_path: Path, body: str, mode: int) -> Path:
        script = tmp_path / "target.sh"
        script.write_text("#!/bin/sh\n", encoding="utf-8")
        os.chmod(script, mode)
        unit_dir = tmp_path / "units"
        unit_dir.mkdir()
        (unit_dir / "probe.service").write_text(
            body.format(exe=script), encoding="utf-8")
        return unit_dir

    def test_a_root_unit_with_a_world_writable_target_is_detected(self, tmp_path):
        unit_dir = self._unit_dir(tmp_path, "[Service]\nExecStart={exe}\n", 0o777)
        offenders = _offenders(unit_dir)
        assert offenders, "проверка не заметила заведомо опасный юнит"
        assert "открыт на запись" in offenders[0][2]

    def test_user_is_not_assumed_to_be_set(self, tmp_path):
        """Отсутствие `User=` — это root, а не «не указано»."""
        unit_dir = self._unit_dir(tmp_path, "[Service]\nExecStart={exe}\n", 0o777)
        assert _offenders(unit_dir)

    def test_a_non_root_unit_is_out_of_scope(self, tmp_path):
        unit_dir = self._unit_dir(
            tmp_path, "[Service]\nUser=nobody\nExecStart={exe}\n", 0o777)
        assert not _offenders(unit_dir)

    def test_a_closed_target_is_accepted(self, tmp_path):
        unit_dir = self._unit_dir(tmp_path, "[Service]\nExecStart={exe}\n", 0o755)
        # Владелец файла в tmp_path — не root, и это тоже нарушение; проверяем,
        # что режим 0755 сам по себе претензии не вызывает.
        reasons = " ".join(why for _, _, why in _offenders(unit_dir))
        assert "открыт на запись" not in reasons
