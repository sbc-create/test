"""Исполнитель Templates: разрешение, ограждение, ровно один эффект.

Три обязанности, и ни одна не выводится из другой
-------------------------------------------------

Первая — не исполнять без действующего разрешения. Вторая — не исполнять
дважды: повтор доставки, гонка двух вызовов и возобновление после обрыва
обязаны дать один эффект, а не три. Третья — уметь сказать, что эффект уже
есть, не полагаясь на собственную память о нём.

Почему притязание записывается ДО вызова цели
---------------------------------------------

Отметка после успеха отвечает на вопрос «мы закончили», но не на вопрос «мы
начинали». Процесс, умерший между эффектом и подтверждением, не оставил бы
следа, и возобновление повторило бы эффект — тем более уверенно, чем
аккуратнее написано. Поэтому притязание durable до вызова, а подтверждение —
после.

Почему победитель гонки определяется базой, а не проверкой
----------------------------------------------------------

«Посмотреть, нет ли записи, и записать» — две операции, между которыми
помещается второй поток. Победителя определяет уникальность ключа: проигравший
получает отказ вставки и читает результат победителя, а не исполняет своё.
"""
from __future__ import annotations

import datetime as _d
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from factory.site_engine.changeset import adapter as A
from factory.site_engine.approval import keyring as K
from factory.site_engine.provisioner import grant as G

DDL = """
PRAGMA journal_mode=WAL;
CREATE TABLE IF NOT EXISTS execution_claim (
  idempotency_key TEXT PRIMARY KEY,
  changeset_id    TEXT NOT NULL,
  site_id         TEXT NOT NULL,
  fencing_token   INTEGER NOT NULL,
  state           TEXT NOT NULL,        -- CLAIMED | SUCCEEDED | FAILED
  effect_ref      TEXT,
  detail          TEXT,
  claimed_at      TEXT NOT NULL,
  finished_at     TEXT
);
"""


def _сейчас() -> str:
    return _d.datetime.now(_d.timezone.utc).isoformat().replace("+00:00", "Z")


class ExecutorError(RuntimeError):
    def __init__(self, код: str, детали: str):
        super().__init__(детали)
        self.error_code, self.detail = код, детали


class Обрыв(RuntimeError):
    """Процесс прерван после durable-эффекта, но до подтверждения."""


@dataclass
class Исход:
    applied: bool
    replay: bool
    effects: int
    effect_ref: str | None
    fence_winner: bool
    claims: dict[str, Any] | None = None


class TemplatesExecutor:
    """Единственная точка, через которую Templates меняет цель."""

    #: Род ресурса, который исполняет этот исполнитель.
    РЕСУРС = "template.release"

    def __init__(self, журнал: str | Path, адаптер, набор_ключей: K.НаборКлючей,
                 *, наблюдатель: Callable[[str], str | None] | None = None) -> None:
        self.путь = str(журнал)
        Path(self.путь).parent.mkdir(parents=True, exist_ok=True)
        self.соед = sqlite3.connect(self.путь, timeout=30, isolation_level=None)
        self.соед.row_factory = sqlite3.Row
        self.соед.executescript(DDL)
        self.адаптер = адаптер
        self.набор = набор_ключей
        #: Как узнать у ЦЕЛИ, случился ли эффект. Нужен для возобновления:
        #: собственная память после обрыва ничего не доказывает.
        self.наблюдатель = наблюдатель

    def закрыть(self) -> None:
        self.соед.close()

    # --- притязание --------------------------------------------------------
    def _занять(self, ключ: str, *, changeset_id: str, site_id: str,
                fencing_token: int) -> tuple[bool, dict | None]:
        """Вернуть (победитель, прежняя запись)."""
        try:
            with self.соед:
                self.соед.execute(
                    "INSERT INTO execution_claim(idempotency_key, changeset_id, "
                    "site_id, fencing_token, state, claimed_at) "
                    "VALUES(?,?,?,?,?,?)",
                    (ключ, changeset_id, site_id, int(fencing_token),
                     "CLAIMED", _сейчас()))
            return True, None
        except sqlite3.IntegrityError:
            с = self.соед.execute(
                "SELECT * FROM execution_claim WHERE idempotency_key=?",
                (ключ,)).fetchone()
            return False, dict(с) if с else None

    def _завершить(self, ключ: str, *, состояние: str,
                   effect_ref: str | None = None,
                   detail: str | None = None) -> None:
        with self.соед:
            self.соед.execute(
                "UPDATE execution_claim SET state=?, effect_ref=?, detail=?, "
                "finished_at=? WHERE idempotency_key=?",
                (состояние, effect_ref, (detail or "")[:300], _сейчас(), ключ))

    def притязание(self, ключ: str) -> dict | None:
        с = self.соед.execute(
            "SELECT * FROM execution_claim WHERE idempotency_key=?",
            (ключ,)).fetchone()
        return dict(с) if с else None

    def незавершённые(self) -> list[dict]:
        return [dict(с) for с in self.соед.execute(
            "SELECT * FROM execution_claim WHERE state='CLAIMED' "
            "ORDER BY claimed_at")]

    # --- исполнение ---------------------------------------------------------
    def выполнить(self, *, подпись: str, полезное: dict[str, Any],
                  ожидания: G.Ожидания, план: dict[str, Any],
                  idempotency_key: str) -> Исход:
        """Проверить разрешение и применить план ровно один раз."""
        # Разрешение проверяется ДО любого эффекта и до занятия притязания:
        # отклонённый вызов не должен оставлять следов, которые потом примут
        # за начатую работу.
        притязания = G.проверить(подпись, полезное, ожидания, self.набор)

        победитель, прежнее = self._занять(
            idempotency_key, changeset_id=ожидания.changeset_id,
            site_id=ожидания.site_id, fencing_token=ожидания.fencing_token)
        if not победитель:
            if прежнее and прежнее["state"] == "SUCCEEDED":
                return Исход(applied=True, replay=True, effects=0,
                             effect_ref=прежнее["effect_ref"],
                             fence_winner=False, claims=притязания)
            # Победитель ещё в работе. Второй не исполняет и не ждёт молча.
            return Исход(applied=False, replay=True, effects=0,
                         effect_ref=(прежнее or {}).get("effect_ref"),
                         fence_winner=False, claims=притязания)

        try:
            r = self.адаптер.apply(site_id=ожидания.site_id, plan=план,
                                   fencing_token=ожидания.fencing_token)
        except A.AdapterError as ош:
            # Адаптер отказал ОСОЗНАННО и до эффекта: это единственный случай,
            # когда исполнитель вправе утверждать, что эффекта не было.
            self._завершить(idempotency_key, состояние="FAILED",
                            detail=f"{ош.error_code}: {ош.detail}")
            raise
        except Exception:
            # Всё прочее — обрыв, таймаут, потерянный ответ. Эффект МОГ
            # случиться, и исполнитель этого не знает. Пометить FAILED значило
            # бы утверждать обратное; притязание остаётся CLAIMED, и ответ
            # получают у цели при возобновлении.
            raise
        ссылка = r.get("external_id")
        self._завершить(idempotency_key, состояние="SUCCEEDED",
                        effect_ref=ссылка)
        # Адаптер сообщает число эффектов полем `effects`; поля `created` у
        # него нет. Читать несуществующий ключ — значит всегда считать нулём
        # и объявить идемпотентность там, где её не измеряли.
        return Исход(applied=True, replay=False,
                     effects=int(r.get("effects", 0)), effect_ref=ссылка,
                     fence_winner=True, claims=притязания)

    # --- возобновление -------------------------------------------------------
    def возобновить(self) -> dict[str, Any]:
        """Довести до определённости то, что начинали и не подтвердили.

        Сначала спрашивают ЦЕЛЬ, а не себя: после обрыва собственная память
        не содержит ответа, ради которого возобновление и затевается.
        """
        итог = {"checked": 0, "confirmed_existing": 0, "reapplied": 0,
                "unresolved": 0}
        for п in self.незавершённые():
            итог["checked"] += 1
            ссылка = self.наблюдатель(п["site_id"]) if self.наблюдатель else None
            if ссылка:
                итог["confirmed_existing"] += 1
                self._завершить(п["idempotency_key"], состояние="SUCCEEDED",
                                effect_ref=ссылка,
                                detail="эффект подтверждён наблюдением цели")
            else:
                итог["unresolved"] += 1
        return итог
