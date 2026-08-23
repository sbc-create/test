"""Идемпотентный провайдер Яндекс.Метрики и Яндекс.Вебмастера.

Все операции устроены одинаково: сначала прочитать фактическое состояние на
стороне Яндекса, потом сравнить с желаемым, и только при расхождении — записать.
Повторный запуск поэтому не создаёт второй счётчик, вторую цель и второй сайт в
Вебмастере.

Три свойства, которые провайдер обязан удержать:

* **никаких выдуманных данных.** Недоступный API — это ``BLOCKED_ANALYTICS_ACCESS``,
  а не пустой отчёт и не «счётчик, наверное, создался»;
* **неоднозначность не разрешается молча.** Два счётчика на один домен — это
  вопрос владельцу, а не повод выбрать первый попавшийся;
* **запись только по явному разрешению.** По умолчанию провайдер в режиме плана
  и в сеть с POST не ходит вовсе.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from urllib.parse import urlsplit

import yaml

from factory.analytics import events as events_mod
from factory.analytics.credentials import (
    OAuthToken,
    TokenFileStatus,
    inspect_token_file,
    load_token,
)
from factory.analytics.transport import YandexApiClient
from factory.errors import BlockedAnalyticsAccess, BlockedInput
from factory.paths import PATHS

CONTRACT_PATH = "knowledge/YANDEX_ANALYTICS_CONTRACT.yaml"

#: Состояния подтверждения прав из официальной документации Вебмастера.
VERIFICATION_STATES = ("NONE", "VERIFIED", "IN_PROGRESS", "VERIFICATION_FAILED", "INTERNAL_ERROR")

#: Собственные статусы фабрики поверх ответа Вебмастера. `DONE` среди них нет:
#: пока домен не отвечает по HTTPS, «подтверждено» — это неправда.
PLANNED = "PLANNED"
BLOCKED_DEPLOYMENT = "BLOCKED_DEPLOYMENT"

_WWW = re.compile(r"^www\.")


def load_contract() -> dict:
    """Замороженный контракт API. Без него провайдер не работает."""
    path = PATHS.root / CONTRACT_PATH
    if not path.exists():
        raise BlockedInput(
            f"Контракт {CONTRACT_PATH} не найден: адреса и поля API не переданы.",
            field="knowledge",
            required_input="Выжимка официальной документации Яндекса через /research-freeze",
            blocks_stage="VALIDATING",
        )
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def normalize_domain(value: str) -> str:
    """Домен в форме, в которой его хранит Метрика: без схемы, www и пути.

    Сравнение доменов «как есть» даёт ложное «не найдено» и второй счётчик на
    тот же сайт, поэтому нормализация — часть идемпотентности, а не косметика.
    """
    text = (value or "").strip().lower()
    if "//" in text:
        text = urlsplit(text).netloc or text
    text = text.split("/", 1)[0].split(":", 1)[0]
    return _WWW.sub("", text).rstrip(".")


def host_url(domain: str) -> str:
    """HTTPS-адрес сайта для Вебмастера. Схему выдумывать нельзя — только https."""
    return f"https://{normalize_domain(domain)}"


def webvisor_enabled(counter: dict) -> bool:
    """Включена ли запись сессий.

    Проверка намеренно шире документированных флагов: под-схема объекта
    ``webvisor`` в публичной документации раскрыта не целиком, поэтому любой
    ключ вида ``*enabled`` со значением «истина» считается включённым Вебвизором.
    Ошибиться в сторону «выключи» безопаснее, чем в сторону «наверное, выключен».
    """
    webvisor = counter.get("webvisor")
    if not isinstance(webvisor, dict):
        return False
    for key, value in webvisor.items():
        name = str(key).lower()
        looks_like_a_switch = name.endswith("enabled") or name in {"wv_forms", "arch_enabled"}
        if looks_like_a_switch and (value is True or str(value).lower() in {"true", "1", "yes"}):
            return True
    return False


@dataclass
class CounterState:
    """Публичное состояние счётчика. Ни токена, ни персональных данных здесь нет."""

    domain: str
    name: str
    counter_id: int | None = None
    created: bool = False
    reused: bool = False
    planned: bool = False
    status: str = "unknown"
    webvisor: bool = False
    goals_present: tuple[str, ...] = ()
    goals_created: tuple[str, ...] = ()
    goals_planned: tuple[str, ...] = ()
    problems: tuple[str, ...] = ()

    @property
    def goals_complete(self) -> bool:
        return set(events_mod.EVENT_IDS) <= set(self.goals_present) | set(self.goals_created)

    def as_dict(self) -> dict:
        return {
            "domain": self.domain,
            "name": self.name,
            "counter_id": self.counter_id,
            "created": self.created,
            "reused": self.reused,
            "planned": self.planned,
            "status": self.status,
            "webvisor": self.webvisor,
            "goals_present": list(self.goals_present),
            "goals_created": list(self.goals_created),
            "goals_planned": list(self.goals_planned),
            "goals_complete": self.goals_complete,
            "problems": list(self.problems),
        }


@dataclass
class WebmasterState:
    """Состояние сайта в Вебмастере. `DONE` появляется только после VERIFIED."""

    domain: str
    host_url: str
    host_id: str | None = None
    added: bool = False
    reused: bool = False
    planned: bool = False
    verification_state: str = PLANNED
    verification_uin: str | None = None
    applicable_verifiers: tuple[str, ...] = ()
    problems: tuple[str, ...] = ()

    def as_dict(self) -> dict:
        return {
            "domain": self.domain,
            "host_url": self.host_url,
            "host_id": self.host_id,
            "added": self.added,
            "reused": self.reused,
            "planned": self.planned,
            "verification_state": self.verification_state,
            # Маркер — публичное значение, оно попадает в HTML сайта. Секретом
            # он не является, но и без нужды в отчёт не выводится.
            "verification_uin_present": bool(self.verification_uin),
            "applicable_verifiers": list(self.applicable_verifiers),
            "problems": list(self.problems),
        }


@dataclass
class CredentialsReport:
    """Что удалось проверить о доступе. Ни токена, ни его части здесь нет."""

    token_file: dict
    metrika_status: int | None = None
    webmaster_status: int | None = None
    metrika_ok: bool = False
    webmaster_ok: bool = False
    #: Возможности, а не scopes: список scopes Яндекс в ответе API не возвращает,
    #: поэтому объявляется ровно то, что фактически проверено запросом.
    capabilities: tuple[str, ...] = ()
    problems: tuple[str, ...] = field(default_factory=tuple)

    @property
    def ok(self) -> bool:
        return self.metrika_ok and self.webmaster_ok

    def as_dict(self) -> dict:
        return {
            "token_file": self.token_file,
            "metrika_http_status": self.metrika_status,
            "webmaster_http_status": self.webmaster_status,
            "metrika_ok": self.metrika_ok,
            "webmaster_ok": self.webmaster_ok,
            "capabilities": list(self.capabilities),
            "problems": list(self.problems),
            "ok": self.ok,
        }


class YandexAnalyticsProvider:
    """Провайдер аналитики. Одна точка входа для фабрики и SEO-оператора."""

    name = "yandex"

    def __init__(
        self,
        token: OAuthToken | None = None,
        *,
        dry_run: bool = True,
        contract: dict | None = None,
        metrika_client: YandexApiClient | None = None,
        webmaster_client: YandexApiClient | None = None,
        job_id: str = "analytics",
        site_id: str = "-",
    ) -> None:
        self.contract = contract or load_contract()
        self.dry_run = dry_run
        self._token = token
        self._job_id = job_id
        self._site_id = site_id
        self._metrika = metrika_client
        self._webmaster = webmaster_client
        self._user_id: int | None = None

    # ------------------------------------------------------------- клиенты
    def _client(self, service: str) -> YandexApiClient:
        base = self.contract[service]["base_url"]
        if self._token is None:
            self._token = load_token()
        return YandexApiClient(
            base,
            self._token,
            service=service,
            dry_run=self.dry_run,
            job_id=self._job_id,
            site_id=self._site_id,
        )

    @property
    def metrika(self) -> YandexApiClient:
        if self._metrika is None:
            self._metrika = self._client("metrika")
        return self._metrika

    @property
    def webmaster(self) -> YandexApiClient:
        if self._webmaster is None:
            self._webmaster = self._client("webmaster")
        return self._webmaster

    # ------------------------------------------------------- 1. доступ
    def validate_credentials(self) -> CredentialsReport:
        """Безопасная проверка доступа: только HTTP-статус и подтверждённые возможности.

        Ни токен, ни его часть, ни персональные данные аккаунта в отчёт не
        попадают. Идентификатор пользователя Вебмастера нужен для работы, но
        наружу отдаётся только факт «получен».
        """
        status: TokenFileStatus = inspect_token_file()
        report = CredentialsReport(token_file=status.as_dict())
        problems: list[str] = list(status.problems)
        capabilities: list[str] = []

        try:
            response = self.metrika.get("/management/v1/counters", params={"per_page": 1})
            report.metrika_status = response.status
            report.metrika_ok = response.ok
            if response.ok:
                capabilities.append("metrika:counters:read")
        except BlockedAnalyticsAccess as exc:
            problems.append(f"Метрика: {exc.reason}")

        try:
            response = self.webmaster.get("/v4/user")
            report.webmaster_status = response.status
            report.webmaster_ok = response.ok
            if response.ok and isinstance(response.payload, dict):
                self._user_id = response.payload.get("user_id")
                capabilities.append("webmaster:user:read")
                if self._user_id:
                    capabilities.append("webmaster:hosts:read")
        except BlockedAnalyticsAccess as exc:
            problems.append(f"Вебмастер: {exc.reason}")

        report.capabilities = tuple(capabilities)
        report.problems = tuple(problems)
        return report

    def rotate_credentials_check(self) -> dict:
        """Пригоден ли текущий токен и не пора ли его менять.

        Отвечает на два вопроса и ни на один больше: «файл секрета лежит
        правильно» и «Яндекс токен ещё принимает». Отпечаток нужен, чтобы
        заметить смену токена между запусками, не показав ни одного символа.
        """
        status = inspect_token_file()
        result = {
            "token_file": status.as_dict(),
            "rotation_required": False,
            "reason": "",
            "fingerprint": None,
        }
        if not status.readable:
            result["reason"] = (
                "состояние токена не проверено: файл секрета недоступен этой учётной записи"
            )
            return result

        token = self._token or load_token()
        result["fingerprint"] = token.fingerprint()
        try:
            response = self.metrika.get("/management/v1/counters", params={"per_page": 1})
            result["http_status"] = response.status
            result["reason"] = "токен принят"
        except BlockedAnalyticsAccess as exc:
            result["rotation_required"] = True
            result["reason"] = exc.reason
        return result

    # --------------------------------------------------- 2. счётчики
    def list_counters(self) -> list[dict]:
        """Все активные счётчики аккаунта со списком целей.

        Пагинация обязательна: без неё «не найдено» на 1001-м счётчике означает
        второй счётчик на тот же домен.
        """
        counters: list[dict] = []
        offset, per_page = 1, 200
        while True:
            response = self.metrika.get(
                "/management/v1/counters",
                params={"per_page": per_page, "offset": offset, "field": "goals", "status": "Active"},
            )
            payload = response.payload or {}
            page = payload.get("counters") or []
            counters.extend(page)
            total = payload.get("rows")
            offset += len(page)
            if not page or (isinstance(total, int) and offset > total):
                break
            if len(page) < per_page:
                break
        return counters

    @staticmethod
    def match_counters(counters: list[dict], domain: str, name: str) -> list[dict]:
        """Счётчики этого домена. Совпадение по домену точное, имя — подсказка.

        Домен — единственный надёжный признак: имя владелец может переименовать
        в интерфейсе, и тогда поиск по имени создаст дубль.
        """
        target = normalize_domain(domain)
        return [
            counter
            for counter in counters
            if normalize_domain(str((counter.get("site2") or {}).get("site") or "")) == target
        ]

    def ensure_metrica_counter(self, domain: str, name: str) -> CounterState:
        """Находит счётчик домена или создаёт его. Повтор дубля не создаёт."""
        state = CounterState(domain=normalize_domain(domain), name=name)
        existing = self.match_counters(self.list_counters(), domain, name)

        if len(existing) > 1:
            ids = sorted(int(c["id"]) for c in existing if c.get("id"))
            state.problems = (
                f"на домен {state.domain} заведено несколько счётчиков: {ids}. "
                "Фабрика не выбирает между ними — нужное решение принимает владелец.",
            )
            state.status = "ambiguous"
            return state

        if existing:
            counter = existing[0]
            state.counter_id = int(counter["id"])
            state.reused = True
            state.status = str(counter.get("status") or "Active")
            state.webvisor = webvisor_enabled(counter)
            state.goals_present = tuple(
                self._goal_event_ids(counter.get("goals") or [])
            )
            if state.webvisor:
                state.problems = (
                    f"у счётчика {state.counter_id} включён Вебвизор — задание требует его выключить "
                    "в интерфейсе Метрики; фабрика запись сессий не настраивает.",
                )
            return state

        if self.dry_run:
            state.planned = True
            state.status = "planned"
            state.goals_planned = events_mod.EVENT_IDS
            return state

        # Тело создания — ровно то, что описано в контракте: имя и домен.
        # Ни webvisor, ни gdpr_agreement_accepted фабрика не отправляет.
        response = self.metrika.post(
            "/management/v1/counters",
            body={"counter": {"name": name, "site2": {"site": state.domain}}},
        )
        counter = (response.payload or {}).get("counter") or {}
        if not counter.get("id"):
            raise BlockedAnalyticsAccess(
                f"Метрика приняла запрос на счётчик {state.domain}, но не вернула id. "
                "Состояние неизвестно — повтор запрещён, чтобы не создать дубль.",
                field="analytics.counter_id",
                required_input="Проверить счётчики аккаунта вручную и запустить операцию заново",
                blocks_stage="BUILDING",
            )
        state.counter_id = int(counter["id"])
        state.created = True
        state.status = str(counter.get("status") or "Active")
        state.webvisor = webvisor_enabled(counter)
        return state

    @staticmethod
    def _goal_event_ids(goals: list[dict]) -> list[str]:
        """Идентификаторы событий, на которые уже заведены цели типа `action`."""
        found: list[str] = []
        for goal in goals:
            if str(goal.get("type")) != "action":
                continue
            for condition in goal.get("conditions") or []:
                url = str(condition.get("url") or "")
                if url in events_mod.BY_ID:
                    found.append(url)
        return sorted(set(found))

    def list_goal_ids(self, counter_id: int) -> dict[str, int]:
        """`{идентификатор события: числовой goal_id}` для существующих целей.

        Числовой идентификатор присваивает Метрика, и без него метрику
        достижения цели (`ym:s:goal<goal_id>reaches`) не адресовать. Реестр
        хранит идентификаторы событий, а не goal_id, поэтому связка живёт здесь.
        """
        response = self.metrika.get(
            f"/management/v1/counter/{counter_id}", params={"field": "goals"})
        counter = (response.payload or {}).get("counter") or {}
        mapping: dict[str, int] = {}
        for goal in counter.get("goals") or []:
            if str(goal.get("type")) != "action" or not goal.get("id"):
                continue
            for condition in goal.get("conditions") or []:
                event_id = str(condition.get("url") or "")
                if event_id in events_mod.BY_ID:
                    mapping[event_id] = int(goal["id"])
        return mapping

    def ensure_metrica_goals(self, counter_id: int, state: CounterState | None = None) -> CounterState:
        """Доводит набор целей до девяти. Существующие цели не трогает и не удаляет."""
        state = state or CounterState(domain="", name="", counter_id=counter_id)
        response = self.metrika.get(f"/management/v1/counter/{counter_id}", params={"field": "goals"})
        counter = (response.payload or {}).get("counter") or {}
        present = self._goal_event_ids(counter.get("goals") or [])
        state.goals_present = tuple(present)

        missing = [event for event in events_mod.EVENTS if event.id not in present]
        if not missing:
            return state

        if self.dry_run:
            state.goals_planned = tuple(event.id for event in missing)
            return state

        created: list[str] = []
        for event in missing:
            self.metrika.post(
                f"/management/v1/counter/{counter_id}/goals",
                body={"goal": event.as_goal()},
            )
            created.append(event.id)
        state.goals_created = tuple(created)
        return state

    # ------------------------------------------------- 3. Вебмастер
    def user_id(self) -> int:
        if self._user_id is not None:
            return self._user_id
        response = self.webmaster.get("/v4/user")
        payload = response.payload or {}
        user_id = payload.get("user_id")
        if not user_id:
            raise BlockedAnalyticsAccess(
                "Вебмастер не вернул user_id — остальные ресурсы API недоступны.",
                field="analytics.webmaster",
                required_input="Токен с доступом к Яндекс.Вебмастеру",
                blocks_stage="VALIDATING",
            )
        self._user_id = int(user_id)
        return self._user_id

    def list_hosts(self) -> list[dict]:
        response = self.webmaster.get(f"/v4/user/{self.user_id()}/hosts")
        payload = response.payload or {}
        return payload.get("hosts") or []

    def ensure_webmaster_host(self, domain: str, *, deployment_ready: bool = False) -> WebmasterState:
        """Регистрирует HTTPS-хост. Неразвёрнутый домен не регистрируется.

        ``deployment_ready`` приходит из ворот развёртывания, а не из желания
        вызывающего: пока домен не отвечает по HTTPS, добавление сайта в
        Вебмастер создаёт запись, которую невозможно подтвердить.
        """
        state = WebmasterState(domain=normalize_domain(domain), host_url=host_url(domain))

        if not deployment_ready:
            state.verification_state = BLOCKED_DEPLOYMENT
            state.problems = (
                f"домен {state.domain} ещё не отвечает по HTTPS — регистрация отложена. "
                "Это состояние BLOCKED_DEPLOYMENT, а не ошибка и не DONE.",
            )
            return state

        for host in self.list_hosts():
            if normalize_domain(str(host.get("ascii_host_url") or host.get("unicode_host_url") or "")) == state.domain:
                state.host_id = str(host.get("host_id") or "")
                state.reused = True
                return state

        if self.dry_run:
            state.planned = True
            state.verification_state = PLANNED
            return state

        response = self.webmaster.post(
            f"/v4/user/{self.user_id()}/hosts",
            body={"host_url": state.host_url},
            # 409 HOST_ALREADY_ADDED — это идемпотентность, а не сбой.
            allow_statuses=frozenset({409}),
        )
        if response.status == 409:
            state.reused = True
            for host in self.list_hosts():
                if normalize_domain(str(host.get("ascii_host_url") or "")) == state.domain:
                    state.host_id = str(host.get("host_id") or "")
            return state
        state.host_id = str((response.payload or {}).get("host_id") or "")
        state.added = True
        return state

    def get_verification_marker(self, host_id: str) -> dict:
        """Маркер подтверждения прав и текущее состояние проверки."""
        response = self.webmaster.get(f"/v4/user/{self.user_id()}/hosts/{host_id}/verification")
        payload = response.payload or {}
        uin = payload.get("verification_uin")
        return {
            "verification_state": str(payload.get("verification_state") or "NONE"),
            "verification_uin": uin,
            "verification_type": payload.get("verification_type"),
            "applicable_verifiers": list(payload.get("applicable_verifiers") or []),
            "meta_tag": f'<meta name="yandex-verification" content="{uin}" />' if uin else None,
            "html_file_name": f"yandex_{uin}.html" if uin else None,
        }

    def verify_webmaster_host(
        self, host_id: str, *, verification_type: str = "META_TAG", marker_reachable: bool = False
    ) -> dict:
        """Запускает подтверждение прав. Недоступный маркер — отказ до запроса.

        Запускать проверку, зная, что маркер не отдаётся по HTTP, значит
        получить ``VERIFICATION_FAILED`` и испортить историю проверок.
        """
        allowed = self.contract["webmaster"]["verification"]["start"]["query"]["verification_type"]
        if verification_type not in allowed:
            raise BlockedInput(
                f"Способ подтверждения «{verification_type}» не описан в контракте: {allowed}.",
                field="webmaster.verification_type",
                required_input=f"Один из {allowed}",
                blocks_stage="VALIDATING",
            )
        if not marker_reachable:
            return {
                "started": False,
                "verification_state": BLOCKED_DEPLOYMENT,
                "reason": "маркер подтверждения не отдаётся по HTTP — проверка не запускается",
            }
        if self.dry_run:
            return {"started": False, "verification_state": PLANNED, "reason": "режим плана"}

        response = self.webmaster.post(
            f"/v4/user/{self.user_id()}/hosts/{host_id}/verification",
            params={"verification_type": verification_type},
        )
        payload = response.payload or {}
        return {
            "started": True,
            "verification_state": str(payload.get("verification_state") or "IN_PROGRESS"),
            "reason": "проверка запущена",
        }

    # ---------------------------------------------------- 4. отчёты
    def get_metrica_report(self, counter_id: int, *, date1: str, date2: str,
                           metrics: list[str], dimensions: list[str] | None = None,
                           limit: int = 100) -> dict:
        """Табличный отчёт Метрики. Только чтение, только агрегаты."""
        params = {
            "ids": counter_id,
            "metrics": ",".join(metrics),
            "date1": date1,
            "date2": date2,
            "limit": limit,
        }
        if dimensions:
            params["dimensions"] = ",".join(dimensions)
        response = self.metrika.get("/stat/v1/data", params=params)
        payload = response.payload or {}
        return {
            "counter_id": counter_id,
            "date1": date1,
            "date2": date2,
            "metrics": metrics,
            "dimensions": dimensions or [],
            "totals": payload.get("totals"),
            "data": payload.get("data") or [],
            "total_rows": payload.get("total_rows"),
            # Выборка — часть честности числа: 40% сессий и 100% сессий это
            # разные утверждения, и отчёт обязан их различать.
            "sampled": payload.get("sampled"),
            "sample_share": payload.get("sample_share"),
        }

    def get_webmaster_report(self, host_id: str, resource: str, params: dict | None = None) -> dict:
        """Read-only ресурс Вебмастера из списка контракта."""
        catalog = self.contract["webmaster"]["reporting"]
        if resource not in catalog:
            raise BlockedInput(
                f"Ресурс Вебмастера «{resource}» не описан в контракте: {sorted(catalog)}.",
                field="webmaster.report",
                required_input=f"Один из {sorted(catalog)}",
                blocks_stage="VALIDATING",
            )
        template = str(catalog[resource]).split(" ", 1)[1]
        path = template.replace("{user-id}", str(self.user_id())).replace("{host-id}", host_id)
        response = self.webmaster.get(path, params=params)
        return {"resource": resource, "host_id": host_id, "payload": response.payload}

    # ----------------------------------------------------- 5. прочее
    def status(self, domains: list[str]) -> dict:
        """Фактическое состояние по каждому домену, без изменений на той стороне."""
        counters = self.list_counters()
        by_domain = {}
        for domain in domains:
            matched = self.match_counters(counters, domain, "")
            entry: dict = {"domain": normalize_domain(domain), "counter_id": None, "goals": []}
            if len(matched) > 1:
                entry["problem"] = "несколько счётчиков на один домен"
            elif matched:
                entry["counter_id"] = int(matched[0]["id"])
                entry["goals"] = self._goal_event_ids(matched[0].get("goals") or [])
                entry["webvisor"] = webvisor_enabled(matched[0])
            by_domain[normalize_domain(domain)] = entry
        return {"provider": self.name, "domains": by_domain}

    def disable(self, domain: str) -> dict:
        """Отключает аналитику для домена на стороне фабрики.

        Счётчик и его данные не удаляются: удаление необратимо и владельцу
        может понадобиться история. Выключается сбор — сайт перестаёт получать
        counter ID, и тег в страницу не попадает.
        """
        return {
            "domain": normalize_domain(domain),
            "action": "disable",
            "effect": "сайт перестаёт получать counter ID; тег Метрики в страницу не встраивается",
            "counter_deleted": False,
            "note": "Счётчик и накопленные данные сохраняются: удаление необратимо.",
        }
