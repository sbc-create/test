"""Граница шаблона: presentation layer и ничего кроме.

Непереговариваемое правило контракта: шаблону запрещены прямые обращения к БД,
источнику, очередям и инфраструктуре, а также raw HTTP к CMS. Данные приходят
только через versioned SDK/DataProvider и нормализованные ViewModel.

Правило держится не уговорами. Один `import pg` в шаблоне выглядит безобидно и
работает — до дня, когда шаблон нужно собрать без базы, откатить отдельно от
платформы или отдать другой ленте. Тогда выясняется, что «слой представления»
им не является, и цена перехода уже уплачена.

Проверка текстовая и намеренно грубая: она читает исходники, а не исполняет их.
Исполнять чужой шаблон, чтобы узнать, что он импортирует, значит запускать в
своей проверке ровно тот код, безопасность которого проверяешь.

Ложные срабатывания дешевле пропусков, поэтому спорное попадает в отчёт, но
каждый запрет объясняет себя: сообщение говорит, чем заменить, а не только что
нельзя. Запрет без замены разработчик обходит, а не выполняет.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

SOURCE_SUFFIXES = {".ts", ".tsx", ".js", ".jsx", ".mjs", ".cjs", ".vue", ".svelte"}

# Каталоги, которые не являются исходниками шаблона.
SKIP_DIRS = {"node_modules", ".next", "dist", "build", ".git", "coverage", "__pycache__"}


@dataclass(frozen=True)
class Violation:
    path: str
    line: int
    rule: str
    snippet: str
    remedy: str

    def __str__(self) -> str:  # pragma: no cover - формат вывода
        return f"{self.path}:{self.line}: {self.rule} — {self.remedy}\n    {self.snippet}"


# (имя правила, регулярное выражение, чем заменить)
RULES: tuple[tuple[str, re.Pattern[str], str], ...] = (
    (
        "прямой драйвер БД",
        re.compile(r"""\b(?:from|require)\s*\(?\s*['"](?:pg|postgres|mysql2?|sqlite3|mongodb|prisma|drizzle-orm)['"]"""),
        "данные берутся из SDK/DataProvider, а не из базы напрямую",
    ),
    (
        "клиент кэша или очереди",
        re.compile(r"""\b(?:from|require)\s*\(?\s*['"](?:ioredis|redis|amqplib|bullmq|kafkajs|nats)['"]"""),
        "кэш и очереди принадлежат платформе; шаблон получает уже готовую ViewModel",
    ),
    (
        "инфраструктурный модуль",
        re.compile(r"""\b(?:from|require)\s*\(?\s*['"]node:(?:fs|child_process|net|dgram|cluster)['"]"""),
        "шаблон не читает диск и не порождает процессы; нужное кладётся в артефакт сборки",
    ),
    (
        "секрет в шаблоне",
        re.compile(r"""process\.env\.[A-Z_]*(?:DATABASE|DB|REDIS|SECRET|TOKEN|PASSWORD|API_KEY)[A-Z_]*"""),
        "серверные секреты шаблону не выдаются; публичные значения объявляются в манифесте",
    ),
    (
        "raw HTTP к CMS или источнику",
        # Именно к CMS/источнику: обычный fetch к своему же API не запрещён.
        re.compile(r"""(?:fetch|axios|got)\s*\(\s*[`'"][^`'"]*(?:cms|payload|admin/api|public-api\.)"""),
        "обращения к CMS идут через SDK: адрес и версия контракта не должны жить в вёрстке",
    ),
)


def check_source(text: str, path: str = "<текст>") -> list[Violation]:
    """Нарушения в одном файле. Комментарии пропускаются: упоминание запрета в
    пояснении — не его нарушение, и наказывать за документацию нельзя."""
    out: list[Violation] = []
    for number, raw in enumerate(text.splitlines(), start=1):
        line = raw.strip()
        if line.startswith(("//", "*", "/*", "#")):
            continue
        for rule, pattern, remedy in RULES:
            if pattern.search(line):
                out.append(
                    Violation(path=path, line=number, rule=rule, snippet=line[:120], remedy=remedy)
                )
    return out


def check_tree(root: str | Path) -> list[Violation]:
    """Нарушения по всему дереву шаблона, в устойчивом порядке."""
    root = Path(root)
    out: list[Violation] = []
    for file in sorted(root.rglob("*")):
        if not file.is_file() or file.suffix not in SOURCE_SUFFIXES:
            continue
        if any(part in SKIP_DIRS for part in file.parts):
            continue
        try:
            text = file.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        out.extend(check_source(text, str(file.relative_to(root))))
    return out


def main(argv: list[str] | None = None) -> int:
    """Код возврата — число нарушений, чтобы проверка падала видимо."""
    import argparse
    import sys

    parser = argparse.ArgumentParser(description="Проверить границу шаблона")
    parser.add_argument("root", help="каталог шаблона")
    args = parser.parse_args(argv)

    violations = check_tree(args.root)
    for violation in violations:
        print(violation)
    if violations:
        print(f"\nнарушений границы шаблона: {len(violations)}", file=sys.stderr)
        return len(violations)
    print("граница шаблона не нарушена")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
