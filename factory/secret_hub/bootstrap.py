"""Приёмочный сценарий: импорт, применение, при нехватке — форма, живая проверка.

Один вызов, выполняемый root'ом, доводит хаб от «установлен» до «направления
настроены и применены». Порядок продиктован заданием и здравым смыслом:

1. **сначала импорт.** Если credentials уже лежат на хосте файлами, спрашивать
   их у человека заново незачем — и вредно: человек ввёл бы их с ошибкой или из
   другого источника. Импорт идёт внутри этого же root-процесса, значения не
   печатаются и не покидают его.
2. **проверка живым запросом.** Импортированное проверяется у провайдера до
   того, как будет применено. Неподтверждённое не применяется.
3. **применение и проверка потребителей.** Только для направлений, у которых
   есть куда применять.
4. **форма — только для того, чего не хватило.** Если после импорта все
   направления настроены, форма не открывается вообще: публиковать endpoint
   «на всякий случай» — лишняя поверхность.
5. **живая проверка до показа адреса.** Оператору не показывают ни URL, ни код,
   пока на настоящем nginx не подтверждено, что endpoint отвечает 200 без
   пароля, отдаёт метку этой сессии, не сломал основной сайт, отдаёт
   сертификат домена и не пишет журнал.

Ничего из значений секретов этот модуль не печатает: в отчёт идут только
found/imported/verified, отпечаток и статусы.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field

from factory.errors import FactoryError

#: Статусы направления в отчёте приёмки.
NOT_CHECKED = "not_checked"
NOT_FOUND = "not_found"
IMPORTED = "imported"
VERIFIED = "verified"


@dataclass
class PortfolioOutcome:
    """Итог по одному направлению. Значений здесь нет по построению."""

    portfolio: str
    existing: str = NOT_CHECKED
    configured: bool = False
    verified: bool = False
    applied: bool = False
    fingerprint: str | None = None
    version: int | None = None
    status: str = "not_configured"
    detail: str = ""
    consumers: list[dict] = field(default_factory=list)

    def as_dict(self) -> dict:
        return {
            "portfolio": self.portfolio,
            "existing_credentials": self.existing,
            "configured": self.configured,
            "verified": self.verified,
            "applied": self.applied,
            "fingerprint": self.fingerprint,
            "version": self.version,
            "status": self.status,
            "detail": self.detail,
            "consumers": self.consumers,
        }


@dataclass
class BootstrapReport:
    outcomes: dict = field(default_factory=dict)
    form: dict | None = None
    live: dict | None = None
    problems: list = field(default_factory=list)

    def outcome(self, portfolio_id: str) -> PortfolioOutcome:
        return self.outcomes.setdefault(portfolio_id, PortfolioOutcome(portfolio_id))

    @property
    def missing(self) -> list:
        """Направления, которые ещё не настроены и куда есть что применять."""
        return [o.portfolio for o in self.outcomes.values() if not o.configured]

    def as_dict(self) -> dict:
        return {
            "portfolios": [o.as_dict() for o in self.outcomes.values()],
            "form": self.form,
            "live_verification": self.live,
            "problems": list(self.problems),
        }


def import_and_apply(hub, *, archive: bool = False, restart: bool = True) -> BootstrapReport:
    """Шаги 1–3: импорт существующего, проверка, применение.

    Форму не трогает вовсе. Отдельная функция, потому что этот кусок обязан
    работать и сам по себе: «просто подтяни то, что уже лежит на хосте» —
    осмысленная операция без всякого браузера.
    """
    from factory.secret_hub import migrate

    report = BootstrapReport()
    for portfolio in hub.config.portfolios:
        outcome = report.outcome(portfolio.id)
        state = hub.store.state(portfolio.id)

        if state.configured:
            # Уже настроено: повторно импортировать и перезаписывать версию
            # незачем. Существующее состояние — не повод его трогать.
            outcome.existing = VERIFIED if state.verified else IMPORTED
            outcome.configured = True
            outcome.verified = state.verified
            outcome.fingerprint = state.fingerprint
            outcome.version = state.active_version
            outcome.detail = "уже настроено в хранилище"
        elif portfolio.blocked_target is not None:
            outcome.existing = NOT_FOUND
            outcome.status = portfolio.blocked_target.status
            outcome.detail = portfolio.blocked_target.reason
            continue
        else:
            found = migrate.discover(hub.config, portfolio.id)
            usable = [f for f in found if f.usable]
            if not usable:
                outcome.existing = NOT_FOUND
                outcome.detail = "существующих файлов credentials не найдено"
            else:
                try:
                    result = migrate.import_existing(hub, portfolio.id, archive=False)
                except FactoryError as exc:
                    outcome.existing = NOT_FOUND
                    outcome.detail = f"[{exc.status}] {exc.reason}"
                    report.problems.append(f"{portfolio.id}: {exc.reason}")
                    continue
                if result.get("imported"):
                    outcome.existing = IMPORTED
                    outcome.configured = True
                    outcome.verified = True  # store_verified пишет только принятое
                    outcome.fingerprint = result.get("fingerprint")
                    outcome.version = result.get("version")
                    outcome.detail = "импортировано из существующих файлов"
                else:
                    outcome.existing = NOT_FOUND
                    outcome.detail = result.get("reason", "импорт не выполнен")
                    report.problems.append(f"{portfolio.id}: {outcome.detail}")

        if outcome.configured and portfolio.deployable:
            applied = hub.handle({"op": "apply", "portfolio": portfolio.id,
                                  "restart": restart})
            outcome.applied = bool(applied.get("ok"))
            outcome.consumers = applied.get("consumers", [])
            if outcome.applied:
                outcome.existing = VERIFIED
                outcome.verified = True
                outcome.status = "configured"
            else:
                outcome.status = applied.get("status", "apply_failed")
                outcome.detail = applied.get("reason") or outcome.detail
                report.problems.append(
                    f"{portfolio.id}: применение не удалось ({outcome.status})")
        elif outcome.configured:
            outcome.status = (portfolio.blocked_target.status
                              if portfolio.blocked_target else "configured")

        # Архивирование прежних файлов — только после подтверждённого
        # применения и только по явному запросу. До полной приёмки рабочие
        # credentials остаются там, где их сейчас читает работающий сайт.
        if archive and outcome.applied and outcome.existing == VERIFIED:
            try:
                migrate.import_existing(hub, portfolio.id, archive=True)
            except FactoryError as exc:
                report.problems.append(f"{portfolio.id}: архивирование не выполнено: {exc.reason}")

    return report


def run(hub, *, archive: bool = False, restart: bool = True,
        open_form: bool = True, ttl_seconds: int | None = None) -> BootstrapReport:
    """Полный сценарий приёмки, включая форму и живую проверку."""
    from factory.secret_hub import enroll, publish

    report = import_and_apply(hub, archive=archive, restart=restart)

    missing = [o.portfolio for o in report.outcomes.values() if not o.configured]
    if not missing:
        report.form = {"opened": False,
                       "reason": "все направления настроены: форма не открывалась"}
        return report
    if not open_form:
        report.form = {"opened": False, "reason": "форма отключена флагом",
                       "missing": missing}
        return report

    form = hub.config.public_form
    if form is None:
        report.form = {"opened": False,
                       "reason": "public_form не описан в config/secret-hub.json"}
        report.problems.append("публичная форма не настроена")
        return report

    if os.geteuid() != 0:
        report.form = {"opened": False, "reason": "публикация формы требует root"}
        report.problems.append("публикация формы требует root")
        return report

    # Форма поднимается на петле открытым текстом; TLS терминирует nginx
    # настоящим сертификатом домена.
    session_state: dict = {}

    def announce(session, url, port, fingerprint, ttl):
        session_state["session"] = session
        session_state["marker"] = session.marker
        session_state["url"] = form.url
        session_state["ttl"] = ttl

    started = enroll.start_session(
        hub, missing, ttl_seconds=ttl_seconds, host="127.0.0.1",
        port=form.loopback_port, base_path=form.path, tls=False,
        announce=announce, serve=False, public_url=form.url,
    )
    server = started["server"]
    session = started["session"]

    try:
        publish.activate(form.vhost, form.server_name, form.loopback_port, form.path)
    except publish.PublishError as exc:
        server.server_close()
        report.form = {"opened": False, "reason": str(exc)}
        report.problems.append(f"публикация формы не удалась: {exc}")
        return report

    # Живая проверка до показа адреса и кода. Сервер уже слушает, но обслуживать
    # запросы должен кто-то: проверка ходит снаружи, поэтому нужен поток.
    import threading

    serving = threading.Thread(target=server.serve_forever, kwargs={"poll_interval": 0.2},
                               daemon=True)
    serving.start()

    live = publish.verify_live(form.server_name, session.marker, path=form.path)
    report.live = live.as_dict()

    if not live.ok:
        # Не показываем ни адреса, ни кода: показать их, не убедившись, что
        # endpoint работает и никого не сломал, — значит отправить оператора
        # вводить секрет неизвестно куда.
        _shutdown(server, serving)
        try:
            publish.deactivate()
        except publish.PublishError as exc:
            report.problems.append(f"снятие формы после неудачной проверки: {exc}")
        report.form = {"opened": False, "reason": "живая проверка не пройдена",
                       "failures": live.failures()}
        report.problems.extend(live.failures())
        return report

    enroll._announce_to_root_console(session, form.url, form.loopback_port, "—",
                                     started["ttl_seconds"])
    report.form = {
        "opened": True,
        "url": form.url,
        "ttl_seconds": started["ttl_seconds"],
        "portfolios": missing,
        "attempts_allowed": enroll.MAX_ATTEMPTS,
    }

    # Ждём завершения сессии: успех, TTL или пять ошибок.
    timer = threading.Timer(started["ttl_seconds"], lambda: enroll._expire(session, server))
    timer.daemon = True
    timer.start()
    serving.join(started["ttl_seconds"] + 30)
    timer.cancel()
    _shutdown(server, serving)

    if not session.finished:
        session.close("expired", "TTL истёк")
    report.form["outcome"] = session.outcome
    report.form["attempts"] = session.attempts

    try:
        publish.deactivate()
        gone = publish.verify_gone(form.server_name, path=form.path)
        report.form["gone"] = gone.as_dict()
        if not gone.ok:
            report.problems.extend(gone.failures())
    except publish.PublishError as exc:
        report.problems.append(f"снятие формы: {exc}")

    if session.outcome == "stored" and session.portfolio:
        applied = import_and_apply(hub, archive=archive, restart=restart)
        for portfolio_id, outcome in applied.outcomes.items():
            report.outcomes[portfolio_id] = outcome
        report.problems.extend(applied.problems)

    return report


def _shutdown(server, thread) -> None:
    import threading

    threading.Thread(target=server.shutdown, daemon=True).start()
    thread.join(10)
    server.server_close()


def summarise(report: BootstrapReport, hub) -> dict:
    """Короткая сводка для печати. Значений не содержит."""
    rows = []
    for portfolio in hub.config.portfolios:
        outcome = report.outcomes.get(portfolio.id) or PortfolioOutcome(portfolio.id)
        state = hub.store.state(portfolio.id)
        rows.append({
            "portfolio": portfolio.id,
            "existing": outcome.existing,
            "configured": state.configured,
            "verified": state.verified,
            "applied": outcome.applied,
            "fingerprint": state.fingerprint,
            "status": outcome.status,
            "detail": outcome.detail,
        })
    return {"portfolios": rows, "form": report.form,
            "live_verification": report.live, "problems": report.problems}
