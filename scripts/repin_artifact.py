#!/usr/bin/env python3
"""Перепин артефакта шаблонов: отпечаток, таблица версий, запись об отличии.

Отпечаток артефакта считается по девятнадцати файлам и меняется от любой
правки рендерера, темы, плеера, разбиения или профилей. Пин обязан идти
следом: расхождение пина и дерева останавливает сверку происхождения и
предполётные проверки canary — намеренно, чтобы выложить нельзя было то, чего
никто не считал.

Раньше это делалось руками каждый цикл. Ручная операция, повторяемая
десятками, рано или поздно выполняется неверно: один раз пин уже остался на
предыдущей версии, и поймала это не внимательность, а сухой прогон.

Порядок обязателен и соблюдается здесь: сначала пин, затем коммит, и только
потом сборка манифеста происхождения — он собирается на чистом дереве, иначе
происхождение недостоверно и сверка отказывает.

Запуск:
    .venv/bin/python scripts/repin_artifact.py --note "что изменилось"
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from factory.templates import digest as digest_mod  # noqa: E402

APPLY = ROOT / "automation" / "host" / "lords-canary-apply.sh"
AUDIT = ROOT / "scripts" / "release_input_audit.py"


def _versions_block(text: str) -> str:
    """Тело таблицы версий и только оно.

    Разбор по всему файлу — ошибка, и она молчала: строки вида
    `{"version": 1,` из другого места принимались за записи таблицы, номер
    выходил вида 9113, вставка шла после несуществующей строки и не
    происходила вовсе. Отпечаток при этом в таблицу не попадал, а команда
    сообщала об успехе.
    """
    match = re.search(r"ARTIFACT_VERSIONS\s*=\s*\{(.*?)\n\}", text, re.S)
    return match.group(1) if match else ""


def current_version() -> int:
    block = _versions_block(AUDIT.read_text(encoding="utf-8"))
    versions = [int(m) for m in re.findall(r'"[0-9a-f]{64}":\s*(\d+),', block)]
    return max(versions) if versions else 0


def repin(note: str) -> tuple[str, int]:
    fingerprint = digest_mod.compute()["template_digest"]
    version = current_version() + 1

    apply_text = APPLY.read_text(encoding="utf-8")
    if f'EXPECT_DIGEST="{fingerprint}"' in apply_text:
        return fingerprint, version - 1  # дерево не менялось, пин уже верен

    apply_text = re.sub(r'readonly EXPECT_DIGEST="[0-9a-f]{64}"',
                        f'readonly EXPECT_DIGEST="{fingerprint}"', apply_text, count=1)
    previous = f"# Версия {version - 1}."
    entry = (f"# Версия {version}. Отличие от версии {version - 1}: {note}\n#\n{previous}")
    apply_text = apply_text.replace(previous, entry, 1)
    APPLY.write_text(apply_text, encoding="utf-8")

    audit_text = AUDIT.read_text(encoding="utf-8")
    block = _versions_block(audit_text)
    previous = re.search(r'("[0-9a-f]{64}":\s*' + str(version - 1) + r",)", block)
    if previous is None:
        raise SystemExit(
            f"в таблице версий нет записи {version - 1}: вставлять новую некуда")
    audit_text = audit_text.replace(
        previous.group(1), f'{previous.group(1)}\n    "{fingerprint}": {version},', 1)
    AUDIT.write_text(audit_text, encoding="utf-8")
    # Проверка на месте, а не на веру: молчаливая невставка уже случалась.
    if f'"{fingerprint}": {version},' not in AUDIT.read_text(encoding="utf-8"):
        raise SystemExit("запись версии не добавилась — таблица не изменилась")
    return fingerprint, version


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--note", required=True, help="чем версия отличается от предыдущей")
    parser.add_argument("--commit", action="store_true",
                        help="зафиксировать пин и пересобрать манифест происхождения")
    args = parser.parse_args()

    fingerprint, version = repin(args.note)
    print(f"артефакт версии {version}: {fingerprint}")

    if args.commit:
        def git(*argv):
            return subprocess.run(["git", "-C", str(ROOT), *argv],
                                  capture_output=True, text=True)

        if git("status", "--porcelain").stdout.strip():
            git("add", "-A")
            git("commit", "-q", "-m", f"canary: отпечаток артефакта версии {version}")
        # Манифест происхождения собирается только на чистом дереве.
        result = subprocess.run(
            [sys.executable, str(ROOT / "automation" / "host" / "lords-canary-provenance.py"),
             "--write"], capture_output=True, text=True)
        print(result.stdout.strip() or result.stderr.strip())
        if git("status", "--porcelain").stdout.strip():
            git("add", "-A")
            git("commit", "-q", "-m",
                f"canary: манифест происхождения пересобран под артефакт версии {version}")
        head = git("rev-parse", "HEAD").stdout.strip()
        print(f"HEAD: {head}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
