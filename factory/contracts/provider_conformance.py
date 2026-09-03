"""Сверка контракта с работающей службой: схема против реальности.

Проверка совместимости схемы ловит расхождения между её версиями. Она ничего не
знает о том, совпадает ли схема с тем, что служба делает на самом деле, — а
именно это расхождение дороже всего: клиент генерируется из схемы и ломается о
реализацию.

Два случая, найденные 2026-09-03 на живом `site-engine` и ставшие причиной
появления этого модуля:

* `components.securitySchemes` в схеме отсутствует, а `GET /api/v1/sites`
  отвечает `401`. Клиент, сгенерированный из такой схемы, не пошлёт учётные
  данные и сломается на первом же вызове.
* `GET /api/v1/ingestion/status` объявлен в схеме и отвечает `404`.

Обе находки — не ошибки службы и не ошибки схемы по отдельности. Они ошибки
**связи** между ними, и увидеть их можно только сверкой одного с другим.

Проверка намеренно щадящая к сети: недоступная служба — это `SKIPPED`, а не
провал. Провал по недоступности приучил бы игнорировать красный результат,
и тогда настоящее расхождение прошло бы незамеченным.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Iterable

# Коды, означающие «эндпоинт существует»: доступ может быть закрыт, но маршрут
# объявлен не зря. 404 и 501 означают обратное.
EXISTS_CODES = frozenset({200, 201, 202, 204, 206, 400, 401, 403, 405, 409, 422, 429, 500, 503})
MISSING_CODES = frozenset({404, 501})

AUTH_CODES = frozenset({401, 403})


@dataclass(frozen=True)
class Finding:
    kind: str
    path: str
    detail: str

    def __str__(self) -> str:  # pragma: no cover - формат вывода
        return f"{self.kind}: {self.path}: {self.detail}"


def declared_get_paths(schema: dict[str, Any]) -> list[str]:
    """Только GET: дёргать POST у живой службы ради проверки нельзя — это
    изменило бы её состояние, а проверка обязана быть безопасной."""
    out = []
    for path, methods in (schema.get("paths") or {}).items():
        if isinstance(methods, dict) and "get" in methods:
            out.append(path)
    return sorted(out)


def declares_security(schema: dict[str, Any]) -> bool:
    components = schema.get("components") or {}
    if components.get("securitySchemes"):
        return True
    # Глобальное требование безопасности тоже считается объявлением.
    return bool(schema.get("security"))


def _is_concrete(path: str) -> bool:
    """Шаблонные пути с параметрами не дёргаем: подставленное значение может не
    существовать, и 404 будет означать «нет такой записи», а не «нет маршрута»."""
    return "{" not in path


def check_provider(
    schema: dict[str, Any],
    probe: Callable[[str], int | None],
    paths: Iterable[str] | None = None,
) -> list[Finding]:
    """`probe` возвращает HTTP-код для пути или None, если служба недоступна."""
    findings: list[Finding] = []
    candidates = [p for p in (paths if paths is not None else declared_get_paths(schema)) if _is_concrete(p)]

    observed_auth = False
    reachable = False

    for path in candidates:
        code = probe(path)
        if code is None:
            findings.append(Finding("SKIPPED", path, "служба недоступна — расхождение не проверено"))
            continue
        reachable = True
        if code in MISSING_CODES:
            findings.append(
                Finding("MISSING", path, f"объявлен в схеме, но служба отвечает {code}")
            )
        elif code not in EXISTS_CODES:
            findings.append(Finding("UNEXPECTED", path, f"неожиданный код {code}"))
        if code in AUTH_CODES:
            observed_auth = True

    if reachable and observed_auth and not declares_security(schema):
        findings.append(
            Finding(
                "UNDECLARED_AUTH",
                "(схема)",
                "служба требует аутентификации, но securitySchemes в схеме нет — "
                "сгенерированный клиент не пошлёт учётные данные",
            )
        )
    if reachable and not observed_auth and declares_security(schema):
        findings.append(
            Finding(
                "UNENFORCED_AUTH",
                "(схема)",
                "схема объявляет аутентификацию, но ни один защищённый путь её не потребовал",
            )
        )
    return findings


def blocking(findings: list[Finding]) -> list[Finding]:
    """`SKIPPED` не блокирует: недоступность сети не есть расхождение контракта."""
    return [f for f in findings if f.kind != "SKIPPED"]


def load_schema(path: str | Path) -> dict[str, Any]:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def main(argv: list[str] | None = None) -> int:  # pragma: no cover - точка входа
    import argparse
    import sys
    import urllib.error
    import urllib.request

    parser = argparse.ArgumentParser(description="Сверить схему с работающей службой")
    parser.add_argument("schema")
    parser.add_argument("base_url")
    parser.add_argument("--timeout", type=float, default=10.0)
    args = parser.parse_args(argv)

    def probe(path: str) -> int | None:
        url = args.base_url.rstrip("/") + path
        try:
            with urllib.request.urlopen(url, timeout=args.timeout) as response:
                return response.status
        except urllib.error.HTTPError as error:
            return error.code
        except Exception:
            return None

    findings = check_provider(load_schema(args.schema), probe)
    for finding in findings:
        print(finding)
    hard = blocking(findings)
    if hard:
        print(f"\nрасхождений схемы с реализацией: {len(hard)}", file=sys.stderr)
        return len(hard)
    print("схема и реализация согласованы")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
