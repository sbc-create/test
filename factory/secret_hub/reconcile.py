"""Приведение направлений к заявленному состоянию: применить то, что сохранено.

Сохранённые и проверенные credentials должны оказаться у потребителей. Если
между «сохранено» и «применено» что-то помешало — недоступная цель, упавшая
запись, перезапуск сервера, — это расхождение, и устранять его должна машина, а
не человек кликом в панели.

Что делает и чего не делает:

* **не создаёт версий.** Работает с уже активной версией; ``store.put`` здесь не
  вызывается. Повторный ввод credentials не требуется и не запрашивается;
* **не трогает мастер-ключ и хранилище.** Только применение к потребителям;
* **идемпотентно.** Направление, применённое ко всем потребителям, пропускается:
  лишний перезапуск сайтов — не безобидная операция;
* **ничего не печатает из значений.** В отчёт идут имена, статусы и причины.

Отдельно от ``bootstrap``: тот отвечал за импорт и первичную настройку, а здесь
задача узкая — довести уже сохранённое до потребителей.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from factory.errors import FactoryError


@dataclass
class PortfolioResult:
    portfolio: str
    action: str                      # applied | already | skipped | failed
    version: int | None = None
    applied: int = 0
    total: int = 0
    reason: str = ""
    consumers: list = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return self.action in ("applied", "already")

    def as_dict(self) -> dict:
        return {
            "portfolio": self.portfolio,
            "action": self.action,
            "version": self.version,
            "applied": self.applied,
            "total": self.total,
            "reason": self.reason,
            "consumers": self.consumers,
        }


@dataclass
class Report:
    results: list = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return all(r.ok for r in self.results)

    def as_dict(self) -> dict:
        return {"ok": self.ok, "portfolios": [r.as_dict() for r in self.results]}


def _applied_count(hub, portfolio_id: str) -> int:
    state = hub.store.state(portfolio_id)
    return sum(1 for d in state.deployments if d.status == "applied")


def run(hub, *, only: str | None = None, restart: bool = True,
        force: bool = False) -> Report:
    """Применяет сохранённое там, где оно ещё не применено.

    ``force`` пересматривает и уже применённые направления — нужен, когда
    состояние на диске могло разойтись с записью о выкате.
    """
    report = Report()
    targets = ([hub.config.portfolio(only)] if only
               else list(hub.config.portfolios))

    for portfolio in targets:
        state = hub.store.state(portfolio.id)
        total = len(portfolio.consumers)

        if portfolio.blocked_target is not None:
            report.results.append(PortfolioResult(
                portfolio.id, "skipped", state.active_version, 0, total,
                portfolio.blocked_target.reason))
            continue
        if not state.configured:
            report.results.append(PortfolioResult(
                portfolio.id, "skipped", None, 0, total,
                "credentials не сохранены — вводить их здесь нечем и не нужно"))
            continue
        if not portfolio.deployable:
            report.results.append(PortfolioResult(
                portfolio.id, "skipped", state.active_version, 0, total,
                "у направления нет потребителей"))
            continue

        already = _applied_count(hub, portfolio.id)
        if already >= total and not force:
            report.results.append(PortfolioResult(
                portfolio.id, "already", state.active_version, already, total,
                "уже применено ко всем потребителям"))
            continue

        try:
            applied = hub.handle({"op": "apply", "portfolio": portfolio.id,
                                  "restart": restart})
        except FactoryError as exc:
            report.results.append(PortfolioResult(
                portfolio.id, "failed", state.active_version, already, total,
                f"[{exc.status}] {exc.reason}"))
            continue

        consumers = applied.get("consumers") or []
        ok_now = sum(1 for c in consumers if c.get("status") == "applied")
        if applied.get("ok"):
            report.results.append(PortfolioResult(
                portfolio.id, "applied", state.active_version, ok_now, total,
                "", consumers))
        else:
            reason = (applied.get("reason") or applied.get("status")
                      or applied.get("error") or "")
            if not reason and consumers:
                reason = "; ".join(
                    f"{c.get('consumer')}: {c.get('detail') or c.get('status')}"
                    for c in consumers if c.get("status") != "applied")
            report.results.append(PortfolioResult(
                portfolio.id, "failed", state.active_version, ok_now, total,
                reason or "хаб не сообщил причину отказа", consumers))

    return report


def format_report(report: Report) -> str:
    """Печатная сводка. Значений секретов в ней нет по построению."""
    lines = ["", "=" * 72, "  ПРИМЕНЕНИЕ СОХРАНЁННЫХ CREDENTIALS", "=" * 72]
    header = f"  {'НАПРАВЛЕНИЕ':<12} {'ВЕРСИЯ':<8} {'ПРИМЕНЕНО':<12} ИТОГ"
    lines.append(header)
    words = {
        "applied": "применено сейчас",
        "already": "было применено",
        "skipped": "пропущено",
        "failed": "ОТКАЗ",
    }
    for result in report.results:
        lines.append(
            f"  {result.portfolio:<12} {str(result.version or '—'):<8} "
            f"{f'{result.applied}/{result.total}':<12} {words.get(result.action, result.action)}")
        if result.reason:
            lines.append(f"      {result.reason}")
        for consumer in result.consumers:
            if consumer.get("status") != "applied":
                detail = consumer.get("detail") or ""
                lines.append(f"      ! {consumer.get('consumer')}: "
                             f"{consumer.get('status')}"
                             + (f" — {detail}" if detail else ""))
    lines.append("=" * 72)
    lines.append("")
    return "\n".join(lines)


# --- проверка результата на хосте -----------------------------------------
def audit(hub) -> dict:
    """Фактическое состояние целей после применения.

    Смотрит на диск и на systemd, а не на отчёт: отчёт говорит, что было
    сделано, а проверка — что получилось. Значений не читает и не печатает:
    у файлов проверяются владелец, режим и непустота, у drop-in — что в нём
    только `LoadCredential`, а не значение.
    """
    import stat as stat_mod
    import subprocess

    from factory.secret_hub import SECRET_FIELDS

    rows = []
    for portfolio in hub.config.portfolios:
        if portfolio.blocked_target is not None or not portfolio.consumers:
            continue
        for consumer in portfolio.consumers:
            entry = {"portfolio": portfolio.id, "consumer": consumer.id,
                     "unit": consumer.unit, "problems": []}

            directory = consumer.directory
            try:
                info = directory.stat()
                mode = stat_mod.S_IMODE(info.st_mode)
                entry["directory_mode"] = format(mode, "04o")
                entry["directory_owner_root"] = info.st_uid == 0 and info.st_gid == 0
                if mode & 0o077:
                    entry["problems"].append(
                        f"каталог {directory} доступен группе или миру ({mode:04o})")
                if info.st_uid != 0:
                    entry["problems"].append(f"каталог {directory} не принадлежит root")
            except FileNotFoundError:
                entry["problems"].append(f"каталог {directory} не создан")
            except OSError as exc:
                entry["problems"].append(
                    f"каталог {directory} не проверен ({exc.__class__.__name__})")

            files = []
            for field_name in SECRET_FIELDS:
                path = consumer.path_for(field_name)
                item = {"field": field_name, "path": str(path)}
                try:
                    info = path.stat()
                    mode = stat_mod.S_IMODE(info.st_mode)
                    item.update(mode=format(mode, "04o"),
                                owner_root=info.st_uid == 0 and info.st_gid == 0,
                                empty=info.st_size == 0)
                    if mode != 0o400:
                        entry["problems"].append(f"{path}: режим {mode:04o}, ожидается 0400")
                    if info.st_uid != 0 or info.st_gid != 0:
                        entry["problems"].append(f"{path}: владелец не root:root")
                    if info.st_size == 0:
                        entry["problems"].append(f"{path}: файл пуст")
                except FileNotFoundError:
                    entry["problems"].append(f"{path}: не создан")
                except OSError as exc:
                    entry["problems"].append(f"{path}: не проверен ({exc.__class__.__name__})")
                files.append(item)
            entry["files"] = files

            if consumer.dropin:
                try:
                    text = consumer.dropin.read_text(encoding="utf-8")
                    entry["dropin_has_loadcredential"] = "LoadCredential=" in text
                    # В drop-in не должно быть ничего, кроме путей и имён.
                    suspicious = [ln for ln in text.splitlines()
                                  if ln.strip().startswith("Environment=")
                                  and "_FILE=" not in ln and "_CREDENTIAL=" not in ln]
                    entry["dropin_only_paths"] = not suspicious
                    if not entry["dropin_has_loadcredential"]:
                        entry["problems"].append(f"{consumer.dropin}: нет LoadCredential")
                    if suspicious:
                        entry["problems"].append(
                            f"{consumer.dropin}: подозрительные Environment-строки")
                except FileNotFoundError:
                    entry["problems"].append(f"{consumer.dropin}: не создан")
                except OSError as exc:
                    entry["problems"].append(
                        f"{consumer.dropin}: не прочитан ({exc.__class__.__name__})")

            if consumer.unit:
                try:
                    proc = subprocess.run(["systemctl", "is-active", consumer.unit],
                                          capture_output=True, text=True, timeout=15,
                                          check=False)
                    state = proc.stdout.strip() or "unknown"
                except (OSError, subprocess.SubprocessError) as exc:
                    state = f"не измерено ({exc.__class__.__name__})"
                entry["unit_state"] = state
                if state == "activating":
                    entry["problems"].append(
                        f"{consumer.unit}: цикл перезапуска (activating)")
                elif state not in ("active", "unknown"):
                    entry["problems"].append(f"{consumer.unit}: состояние {state}")
            rows.append(entry)
    return {"ok": all(not r["problems"] for r in rows), "consumers": rows}


def format_audit(result: dict) -> str:
    lines = ["", "=" * 72, "  ПРОВЕРКА РЕЗУЛЬТАТА НА ХОСТЕ", "=" * 72]
    header = (f"  {'ПОТРЕБИТЕЛЬ':<14} {'КАТАЛОГ':<9} {'ФАЙЛЫ':<9} "
              f"{'DROP-IN':<9} UNIT")
    lines.append(header)
    for row in result["consumers"]:
        files_ok = all(f.get("mode") == "0400" and f.get("owner_root")
                       and not f.get("empty") for f in row.get("files", []))
        lines.append(
            f"  {row['consumer']:<14} "
            f"{row.get('directory_mode', '—'):<9} "
            f"{('0400 root' if files_ok else 'ОТКАЗ'):<9} "
            f"{('только пути' if row.get('dropin_only_paths') else 'ОТКАЗ'):<9} "
            f"{row.get('unit_state', '—')}")
        for problem in row["problems"]:
            lines.append(f"      ! {problem}")
    lines.append("=" * 72)
    lines.append("")
    return "\n".join(lines)
