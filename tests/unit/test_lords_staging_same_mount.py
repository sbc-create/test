"""Каталог сборки обязан лежать на том же монтировании, что и релизы.

Быстрый путь связывает базовый релиз жёсткими ссылками. Ядро отказывает в
ссылке между разными точками монтирования, даже когда файловая система под
ними одна. У службы включены PrivateTmp и ProtectSystem=strict, поэтому внутри
её пространства /tmp и /srv/lords — разные монтирования, и `mktemp -d` в /tmp
давал «Invalid cross-device link».

Снаружи пространства службы этого не видно: на хосте ни /tmp, ни /srv/lords
отдельными монтированиями не являются, и ручная проверка проходила успешно.
Поэтому инвариант охраняется тестом, а не памятью.
"""
from __future__ import annotations

import re
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[2] / "automation" / "host" / "lords-content-refresh.sh"


def _text() -> str:
    return SCRIPT.read_text(encoding="utf-8")


def test_staging_создаётся_рядом_с_релизами():
    строки = [l.strip() for l in _text().splitlines()
              if re.match(r'^\s*staging="\$\(mktemp', l)]
    assert строки, "не найдено создание каталога сборки"
    for строка in строки:
        assert "-p" in строка and "runtime" in строка, (
            f"каталог сборки создаётся вне монтирования релизов: {строка}"
        )


def test_staging_не_создаётся_в_tmp_по_умолчанию():
    assert 'staging="$(mktemp -d)"' not in _text(), (
        "mktemp -d без -p кладёт каталог сборки в /tmp, "
        "а он в пространстве службы — другое монтирование"
    )


def test_каталог_сборки_не_попадает_в_прополку_релизов():
    """Прополка перебирает только releases/*/, а .staging лежит рядом."""
    text = _text()
    assert 'releases/"*/' in text or 'releases/"*/ ' in text or '${runtime}/releases/"*/' in text, \
        "изменился шаблон прополки — инвариант нужно перепроверить"
    assert '.staging' in text
    assert '/releases/.staging' not in text, "каталог сборки оказался внутри releases/"
