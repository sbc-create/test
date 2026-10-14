"""Устойчивое хранение ежедневных отчётов и учёт их доставки.

Отчёт до сих пор либо печатался в поток, либо писался в файл по ``--out`` —
одно и то же имя, перезапись поверх вчерашнего. Поэтому цикл, отработавший без
читателя, не оставлял следа: узнать, что отчёт за 9 сентября был и что в нём
стояло, неоткуда.

Модуль решает две задачи, и обе — про честность, а не про удобство.

**След остаётся.** Каждый прогон ложится в каталог своего дня и не затирает
чужой: повторный прогон того же дня пишется рядом со своим ``run_id``, а не
поверх. ``latest`` — отдельная ссылка на последний, а не единственное место
хранения.

**Недоставленное видно.** Адресат отчёта (Quin) не задан ни в одном файле
репозитория, и это внешний блокер. Но блокер доставки не является поводом
терять отчёт: он складывается в spool со статусом ``PENDING_NO_DESTINATION`` и
точным именем недостающего поля. Цикл продолжается, а невыполненная доставка
остаётся видимой, вместо того чтобы выглядеть выполненной.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

#: Единственное, чего не хватает для доставки. Называется одним именем, чтобы
#: владельцу не пришлось выяснять, что именно от него требуется.
DESTINATION_FIELD = "reporting.quin_destination"

PENDING = "PENDING_NO_DESTINATION"
DELIVERED = "DELIVERED"
FAILED = "DELIVERY_FAILED"

#: Что разрешено в имени файла. Юникод оставлен намеренно: run_id приходят
#: по-русски, а вырезав кириллицу, два разных прогона одного дня превращаются
#: в одно имя и затирают друг друга — ровно это и произошло на первом прогоне
#: проверок. Точки схлопываются, чтобы `..` не попадало в имя даже безвредно.
_UNSAFE = re.compile(r"[^\w.-]+", re.UNICODE)
_DOTS = re.compile(r"\.{2,}")


@dataclass
class SpoolEntry:
    run_id: str
    day: str
    markdown_path: Path
    json_path: Path
    delivery_status: str
    detail: str = ""
    owner_action: str | None = None


@dataclass
class Spool:
    root: Path
    entries: list[SpoolEntry] = field(default_factory=list)

    def day_dir(self, day: date | str) -> Path:
        return self.root / (day if isinstance(day, str) else day.isoformat())

    @property
    def latest_markdown(self) -> Path:
        return self.root / "latest.md"

    @property
    def latest_json(self) -> Path:
        return self.root / "latest.json"


def _safe(value: str) -> str:
    """Имя файла из run_id — различающее, а не только безопасное.

    Санитизация, которая склеивает разные значения в одно имя, опаснее грязного
    имени: второй прогон дня молча затрёт первый. Поэтому если очистка что-то
    изменила, к имени добавляется короткий отпечаток исходного значения.
    """
    cleaned = _DOTS.sub(".", _UNSAFE.sub("-", value)).strip("-.")
    if cleaned == value:
        return cleaned or "run"
    digest = hashlib.blake2s(value.encode("utf-8"), digest_size=4).hexdigest()
    return f"{cleaned or 'run'}-{digest}"


def store(
    root: Path,
    *,
    run_id: str,
    day: date,
    markdown: str,
    payload: dict,
    destination: str | None = None,
) -> SpoolEntry:
    """Положить отчёт в spool и зафиксировать состояние доставки.

    ``destination`` пуст — отчёт всё равно сохраняется. Потеря отчёта из-за
    ненастроенной доставки была бы худшим исходом, чем сама ненастроенная
    доставка: во втором случае данные есть и ждут, в первом их нет.
    """
    day_dir = root / day.isoformat()
    day_dir.mkdir(parents=True, exist_ok=True)

    stem = f"SEO-DAILY-REPORT.{_safe(run_id)}"
    md_path = day_dir / f"{stem}.md"
    json_path = day_dir / f"{stem}.json"

    if destination:
        status, detail, owner_action = DELIVERED, f"адресат: {destination}", None
    else:
        status = PENDING
        detail = f"адресат не задан: {DESTINATION_FIELD}"
        owner_action = (
            f"задать {DESTINATION_FIELD} — единственное, чего не хватает для доставки; "
            f"накопленные отчёты лежат в {root}"
        )

    record = dict(payload)
    record["delivery"] = {"status": status, "detail": detail, "run_id": run_id}

    md_path.write_text(markdown, encoding="utf-8")
    json_path.write_text(
        json.dumps(record, ensure_ascii=False, indent=2, default=str), encoding="utf-8"
    )

    (root / "latest.md").write_text(markdown, encoding="utf-8")
    (root / "latest.json").write_text(
        json.dumps(record, ensure_ascii=False, indent=2, default=str), encoding="utf-8"
    )

    return SpoolEntry(
        run_id=run_id,
        day=day.isoformat(),
        markdown_path=md_path,
        json_path=json_path,
        delivery_status=status,
        detail=detail,
        owner_action=owner_action,
    )


def pending(root: Path) -> list[Path]:
    """Отчёты, которые сохранены, но не доставлены. Порядок — от старых к новым."""
    if not root.exists():
        return []
    out = []
    for path in sorted(root.glob("*/SEO-DAILY-REPORT.*.json")):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except ValueError:
            continue
        if data.get("delivery", {}).get("status") != DELIVERED:
            out.append(path)
    return out


def owner_action(root: Path) -> str | None:
    """Единственное требуемое действие владельца, если есть недоставленное."""
    waiting = pending(root)
    if not waiting:
        return None
    return (
        f"задать {DESTINATION_FIELD}: {len(waiting)} отчётов сохранены и ждут доставки, "
        f"самый ранний — {waiting[0].parent.name}"
    )
