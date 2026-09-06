"""Сессии оператора.

Сессия хранит токен Control API, выданный при входе, и ничего больше. Своих
прав у панели нет: что позволено токену — то позволено оператору.

Токен живёт только в памяти процесса. Он не пишется в журнал, не попадает в
разметку и не кладётся в cookie: в cookie уходит лишь идентификатор сессии.
Утёкшая cookie даёт доступ до истечения срока, утёкший токен — до его отзыва,
и это разные величины ущерба.
"""
from __future__ import annotations

import hmac
import secrets
import time
from dataclasses import dataclass
from hashlib import sha256

from factory.site_engine.admin import SESSION_IDLE_SECONDS, SESSION_TTL_SECONDS


@dataclass
class Session:
    sid: str
    token: str
    created_at: float
    last_seen: float
    label: str = ""
    #: Оператор, которому выдана сессия. Пусто у сессий времени начальной
    #: настройки, когда каталог операторов ещё пуст.
    operator_id: str = ""
    email: str = ""
    roles: tuple = ()
    #: Витрина, к которой привязан вошедший. Пустая строка — супер-администратор
    #: или сессия времени начальной настройки. Значение берётся из каталога при
    #: входе и не меняется ничем, что приходит снаружи: поле формы или параметр
    #: адреса, задающий тенанта, — это и есть смена тенанта снаружи.
    site_id: str = ""
    is_super_admin: bool = False
    #: На какую витрину смотрит супер-администратор сейчас. Переключение —
    #: отдельное действие под запись, а не побочный эффект открытия страницы.
    viewing_site_id: str = ""
    # Сообщение о результате последнего действия: панель перенаправляет
    # после записи, поэтому результат нужно пронести через перенаправление.
    flash: dict | None = None

    def token_fingerprint(self) -> str:
        """Отпечаток для журнала. Сам токен наружу не отдаётся никогда."""
        return sha256(self.token.encode("utf-8")).hexdigest()[:12]


class SessionStore:
    """Хранилище сессий в памяти процесса.

    В памяти, а не на диске: перезапуск службы обязан разлогинивать. Сессия,
    пережившая перезапуск, переживает и смену настроек безопасности, о которой
    оператор не узнает.
    """

    def __init__(self, *, now=time.time) -> None:
        self._now = now
        self._sessions: dict[str, Session] = {}
        # Секрет для CSRF рождается вместе с процессом: он не должен переживать
        # перезапуск, иначе старые формы остаются действительными.
        self._csrf_secret = secrets.token_bytes(32)

    def create(self, token: str, *, label: str = "", operator_id: str = "",
               email: str = "", roles=(), site_id: str = "",
               is_super_admin: bool = False) -> Session:
        """Новый идентификатор на каждый вход.

        Идентификатор не переиспользуется никогда: сессия, начатая до входа и
        сохранённая после него, — это фиксация сессии, и чужая ссылка с таким
        идентификатором даёт чужие права.
        """
        now = float(self._now())
        sid = secrets.token_urlsafe(32)
        session = Session(sid=sid, token=token, created_at=now, last_seen=now,
                          label=label, operator_id=operator_id, email=email,
                          roles=tuple(roles), site_id=site_id,
                          is_super_admin=is_super_admin,
                          viewing_site_id=site_id)
        self._sessions[sid] = session
        return session

    def attach_directory(self, directory) -> None:
        """Каталог операторов, по которому сессия проверяется на КАЖДОМ запросе.

        Проверка только при входе оставила бы отозванную сессию живой до
        истечения срока, а это и есть та дыра, ради закрытия которой отзыв
        существует.
        """
        self._directory = directory

    def get(self, sid: str | None) -> Session | None:
        if not sid:
            return None
        session = self._sessions.get(sid)
        if session is None:
            return None
        now = float(self._now())
        # Два срока, а не один: общий и по бездействию. Только общий позволяет
        # открытой вкладке жить восемь часов без единого действия оператора.
        if now - session.created_at > SESSION_TTL_SECONDS:
            self._sessions.pop(sid, None)
            return None
        if now - session.last_seen > SESSION_IDLE_SECONDS:
            self._sessions.pop(sid, None)
            return None
        каталог = getattr(self, "_directory", None)
        if каталог is not None and session.operator_id:
            оператор = каталог.session_valid(sid)
            if оператор is None:
                # Отозвана, заблокирована, разжалована или устарела по политике.
                self._sessions.pop(sid, None)
                return None
            # Роли могли измениться: сессия обязана нести текущие, а не те,
            # что были при входе.
            session.roles = tuple(оператор.roles)
        session.last_seen = now
        return session

    def destroy(self, sid: str | None) -> None:
        if sid:
            self._sessions.pop(sid, None)

    def count(self) -> int:
        return len(self._sessions)

    # ---- CSRF ----------------------------------------------------------

    def csrf_token(self, sid: str) -> str:
        return hmac.new(self._csrf_secret, sid.encode("utf-8"), sha256).hexdigest()

    def csrf_valid(self, sid: str, candidate: str | None) -> bool:
        """Сравнение постоянного времени.

        Обычное сравнение строк выходит на первом различающемся символе, и по
        времени ответа значение подбирается посимвольно.
        """
        if not candidate:
            return False
        # Сравниваются байты, а не строки: compare_digest со строками отказывает
        # на не-ASCII и бросает TypeError. Подделанное значение с кириллицей
        # превращало бы честный отказ 403 во внутреннюю ошибку 500.
        return hmac.compare_digest(
            self.csrf_token(sid).encode("utf-8"),
            candidate.encode("utf-8", errors="surrogatepass"),
        )
