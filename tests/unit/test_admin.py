"""REQ-ADMIN: панель управления массивом витрин.

Проверяется главное свойство: панель не выполняет действий сама. Всё, что она
меняет, проходит через Control API и подчиняется его отказам — поэтому среди
проверок много отрицательных: отсутствие сессии, подделанная форма, нехватка
прав, отклонённая настройка, конфликт версии.
"""
import json
from pathlib import Path

import pytest

from factory import queue
from factory.paths import PATHS
from factory.site_engine.admin import ADMIN_COOKIE, CSRF_FIELD
from factory.site_engine.admin.app import AdminApp
from factory.site_engine.admin.session import SessionStore
from factory.site_engine.api import create_api
from factory.site_engine.api.control import ControlApi
from factory.site_engine.store import InMemoryStore

SITE = "admin-site-a"
FULL = "full-token"
READONLY = "ro-token"
ENV_CONTROL = {
    "SITE_ENGINE_CONTROL_WRITES": "1",
    "SITE_ENGINE_CONTROL_TOKENS": (
        f"{FULL}=read,jobs:write,config:write,cache:write,audit:read|{READONLY}=read"
    ),
}
ENV_READ = {"SITE_ENGINE_API_ENABLED": "1", "SITE_ENGINE_ENVIRONMENT": "test"}


REPO = Path(__file__).resolve().parents[2]


@pytest.fixture
def sandbox(tmp_path, monkeypatch):
    monkeypatch.setattr(PATHS, "root", tmp_path)
    profiles = tmp_path / "config" / "site-profiles"
    profiles.mkdir(parents=True)
    # За основу берётся настоящий профиль, а не выдуманный: набор обязательных
    # полей задаётся схемой и меняется, а придуманный образец молча отстанет.
    образец = json.loads(
        (REPO / "config" / "site-profiles" / "lords-01.json").read_text(encoding="utf-8"))
    образец.update({
        "site_id": SITE, "domains": ["example.test"], "canonical_host": "example.test",
        "keep_releases": 5, "indexing_enabled": True,
        "cache_policy": {"homepage_ttl": 60}, "feature_flags": {"beta": False},
    })
    (profiles / f"{SITE}.json").write_text(
        json.dumps(образец, ensure_ascii=False), encoding="utf-8")
    for sub in ("queue/inbox", "queue/processing", "queue/done", "queue/failed",
                "queue/quarantine", "var/locks", "var/audit", "var/state"):
        (tmp_path / sub).mkdir(parents=True, exist_ok=True)
    return tmp_path


@pytest.fixture
def app(sandbox):
    read = create_api([SITE], root=sandbox,
                      loader=lambda p: (InMemoryStore(p.site_id), "тестовый"), env=ENV_READ)
    return AdminApp(read, ControlApi(root=sandbox, env=ENV_CONTROL))


def войти(app, token=FULL):
    r = app.handle("POST", "/admin/login", form={"token": token})
    assert r.status == 303, r.status
    sid = r.headers["Set-Cookie"].split(";")[0].split("=", 1)[1]
    return {ADMIN_COOKIE: sid}, app.sessions.csrf_token(sid)


# ---- вход и сессия ----------------------------------------------------------

def test_без_сессии_страница_показывает_форму_входа(app):
    r = app.handle("GET", "/admin")
    assert r.status == 200 and "Вход по токену" in r.html


def test_без_сессии_запись_отвечает_отказом_а_не_формой(app):
    """200 с формой входа автоматика примет за успех."""
    r = app.handle("POST", "/admin/sites/x/jobs", form={"action": "reindex"})
    assert r.status == 403


def test_неверный_токен_отклонён(app):
    r = app.handle("POST", "/admin/login", form={"token": "нет-такого"})
    assert r.status == 401 and "не распознан" in r.html


def test_пустой_и_неверный_токен_неотличимы(app):
    """Разные тексты сообщали бы, существует ли токен."""
    a = app.handle("POST", "/admin/login", form={"token": ""})
    b = app.handle("POST", "/admin/login", form={"token": "чужой"})
    assert a.status == b.status == 401 and a.html == b.html


def test_cookie_защищена(app):
    r = app.handle("POST", "/admin/login", form={"token": FULL})
    cookie = r.headers["Set-Cookie"]
    assert "HttpOnly" in cookie and "SameSite=Strict" in cookie and "Path=/admin" in cookie


def test_выход_разрушает_сессию(app):
    cookies, csrf = войти(app)
    assert app.sessions.count() == 1
    r = app.handle("POST", "/admin/logout", form={CSRF_FIELD: csrf}, cookies=cookies)
    assert r.status == 303 and app.sessions.count() == 0
    assert "Max-Age=0" in r.headers["Set-Cookie"]
    assert app.handle("GET", "/admin", cookies=cookies).html.count("Вход по токену") == 1


def test_сессия_истекает_по_бездействию(sandbox, monkeypatch):
    from factory.site_engine.admin import SESSION_IDLE_SECONDS
    часы = {"t": 1000.0}
    store = SessionStore(now=lambda: часы["t"])
    s = store.create("tok")
    assert store.get(s.sid) is not None
    часы["t"] += SESSION_IDLE_SECONDS + 1
    assert store.get(s.sid) is None


def test_сессия_истекает_по_общему_сроку(sandbox):
    from factory.site_engine.admin import SESSION_IDLE_SECONDS, SESSION_TTL_SECONDS
    часы = {"t": 1000.0}
    store = SessionStore(now=lambda: часы["t"])
    s = store.create("tok")
    прошло = 0
    # Активность каждые полчаса не должна продлевать сессию вечно.
    while прошло < SESSION_TTL_SECONDS:
        часы["t"] += SESSION_IDLE_SECONDS // 2
        прошло += SESSION_IDLE_SECONDS // 2
        store.get(s.sid)
    часы["t"] += SESSION_IDLE_SECONDS // 2
    assert store.get(s.sid) is None


# ---- подделка формы ---------------------------------------------------------

def test_форма_без_csrf_отклонена(app):
    cookies, _ = войти(app)
    r = app.handle("POST", f"/admin/sites/{SITE}/jobs",
                   form={"action": "reindex"}, cookies=cookies)
    assert r.status == 403
    assert queue.counts()["inbox"] == 0


def test_csrf_не_из_ascii_даёт_отказ_а_не_сбой(app):
    """compare_digest со строками бросает TypeError на не-ASCII.

    Найдено сквозной проверкой: подделка кириллицей возвращала 500 вместо 403.
    """
    cookies, _ = войти(app)
    r = app.handle("POST", f"/admin/sites/{SITE}/jobs",
                   form={"action": "reindex", CSRF_FIELD: "подделка"}, cookies=cookies)
    assert r.status == 403
    assert queue.counts()["inbox"] == 0


def test_csrf_с_суррогатом_не_роняет_сравнение(app):
    """Суррогат приходит из формы, разобранной с errors=replace."""
    cookies, _ = войти(app)
    r = app.handle("POST", f"/admin/sites/{SITE}/jobs",
                   form={"action": "reindex", CSRF_FIELD: "\ud800x"},
                   cookies=cookies)
    assert r.status == 403


def test_форма_с_чужим_csrf_отклонена(app):
    cookies, _ = войти(app)
    r = app.handle("POST", f"/admin/sites/{SITE}/jobs",
                   form={"action": "reindex", CSRF_FIELD: "a" * 64}, cookies=cookies)
    assert r.status == 403
    assert queue.counts()["inbox"] == 0


# ---- витрины ----------------------------------------------------------------

def test_список_витрин_показан(app):
    cookies, _ = войти(app)
    r = app.handle("GET", "/admin", cookies=cookies)
    assert r.status == 200 and SITE in r.html


def test_карточка_витрины_показана(app):
    cookies, _ = войти(app)
    r = app.handle("GET", f"/admin/sites/{SITE}", cookies=cookies)
    assert r.status == 200 and "Полнота каталога" in r.html or SITE in r.html


# ---- действия идут через Control API ----------------------------------------

def test_проверка_задания_ничего_не_ставит(app):
    cookies, csrf = войти(app)
    app.handle("POST", f"/admin/sites/{SITE}/jobs",
               form={"action": "reindex", "dryRun": "1", CSRF_FIELD: csrf}, cookies=cookies)
    assert queue.counts()["inbox"] == 0
    r = app.handle("GET", f"/admin/sites/{SITE}", cookies=cookies)
    assert "ничего не изменено" in r.html


def test_боевая_постановка_создаёт_задание(app):
    cookies, csrf = войти(app)
    app.handle("POST", f"/admin/sites/{SITE}/jobs",
               form={"action": "reindex", "dryRun": "", CSRF_FIELD: csrf}, cookies=cookies)
    assert queue.counts()["inbox"] == 1


def test_недопустимое_действие_отклоняется_апи(app):
    cookies, csrf = войти(app)
    app.handle("POST", f"/admin/sites/{SITE}/jobs",
               form={"action": "rm -rf /", "dryRun": "", CSRF_FIELD: csrf}, cookies=cookies)
    r = app.handle("GET", f"/admin/sites/{SITE}", cookies=cookies)
    assert "invalid_action" in r.html
    assert queue.counts()["inbox"] == 0


def test_опасная_настройка_отклонена_с_причиной(app):
    cookies, csrf = войти(app)
    app.handle("POST", f"/admin/sites/{SITE}/settings",
               form={"key": "indexing_enabled", "value": "false", "dryRun": "",
                     CSRF_FIELD: csrf}, cookies=cookies)
    r = app.handle("GET", f"/admin/sites/{SITE}", cookies=cookies)
    assert "отклонено намеренно" in r.html
    путь = PATHS.root / "config" / "site-profiles" / f"{SITE}.json"
    assert json.loads(путь.read_text(encoding="utf-8"))["indexing_enabled"] is True


def test_настройка_применяется_со_сверкой_версии(app):
    cookies, csrf = войти(app)
    app.handle("POST", f"/admin/sites/{SITE}/settings",
               form={"key": "keep_releases", "value": "9", "dryRun": "",
                     CSRF_FIELD: csrf}, cookies=cookies)
    путь = PATHS.root / "config" / "site-profiles" / f"{SITE}.json"
    assert json.loads(путь.read_text(encoding="utf-8"))["keep_releases"] == 9


def test_негодный_json_не_доходит_до_апи(app):
    cookies, csrf = войти(app)
    app.handle("POST", f"/admin/sites/{SITE}/settings",
               form={"key": "keep_releases", "value": "{не json", "dryRun": "",
                     CSRF_FIELD: csrf}, cookies=cookies)
    r = app.handle("GET", f"/admin/sites/{SITE}", cookies=cookies)
    assert "не разобрано как JSON" in r.html
    путь = PATHS.root / "config" / "site-profiles" / f"{SITE}.json"
    assert json.loads(путь.read_text(encoding="utf-8"))["keep_releases"] == 5


def test_инвалидация_области_title_требует_ключей(app):
    cookies, csrf = войти(app)
    app.handle("POST", f"/admin/sites/{SITE}/cache",
               form={"scope": "title", "keys": "", "dryRun": "", CSRF_FIELD: csrf},
               cookies=cookies)
    r = app.handle("GET", f"/admin/sites/{SITE}", cookies=cookies)
    assert "keys_required" in r.html


# ---- права ------------------------------------------------------------------

def test_панель_не_показывает_недоступных_действий(app):
    cookies, _ = войти(app, READONLY)
    r = app.handle("GET", f"/admin/sites/{SITE}", cookies=cookies)
    assert "Задание" not in r.html and "Настройки" not in r.html


def test_но_запрет_держится_апи_а_не_разметкой(app):
    """Скрытая кнопка — удобство. Отправленная форма всё равно отклоняется."""
    cookies, csrf = войти(app, READONLY)
    app.handle("POST", f"/admin/sites/{SITE}/jobs",
               form={"action": "reindex", "dryRun": "", CSRF_FIELD: csrf}, cookies=cookies)
    assert queue.counts()["inbox"] == 0
    r = app.handle("GET", f"/admin/sites/{SITE}", cookies=cookies)
    assert "forbidden" in r.html and "jobs:write" in r.html


# ---- утечки и разметка ------------------------------------------------------

def test_токен_не_попадает_в_разметку(app):
    cookies, csrf = войти(app)
    страницы = [
        app.handle("GET", "/admin", cookies=cookies).html,
        app.handle("GET", f"/admin/sites/{SITE}", cookies=cookies).html,
        app.handle("GET", "/admin/audit", cookies=cookies).html,
    ]
    for html in страницы:
        assert FULL not in html


def test_значения_экранируются(app, sandbox):
    """Значения приходят из профилей, куда пишет не только эта панель."""
    путь = sandbox / "config" / "site-profiles" / f"{SITE}.json"
    данные = json.loads(путь.read_text(encoding="utf-8"))
    данные["domains"] = ["<script>alert(1)</script>"]
    путь.write_text(json.dumps(данные, ensure_ascii=False), encoding="utf-8")
    read = create_api([SITE], root=sandbox,
                      loader=lambda p: (InMemoryStore(p.site_id), "т"), env=ENV_READ)
    свой = AdminApp(read, ControlApi(root=sandbox, env=ENV_CONTROL))
    cookies, _ = войти(свой)
    html = свой.handle("GET", "/admin", cookies=cookies).html
    assert "<script>alert(1)</script>" not in html
    assert "&lt;script&gt;" in html


def test_журнал_показывает_и_отказы(app):
    cookies, csrf = войти(app)
    app.handle("POST", f"/admin/sites/{SITE}/settings",
               form={"key": "indexing_enabled", "value": "false", "dryRun": "",
                     CSRF_FIELD: csrf}, cookies=cookies)
    r = app.handle("GET", "/admin/audit", cookies=cookies)
    assert r.status == 200 and "control.denied" in r.html


def test_неизвестная_страница_админки_даёт_404(app):
    cookies, _ = войти(app)
    assert app.handle("GET", "/admin/нет-такой", cookies=cookies).status == 404


# ---- контракт CMS -----------------------------------------------------------

def test_панель_показывает_состояние_контракта(app):
    cookies, _ = войти(app)
    r = app.handle("GET", f"/admin/sites/{SITE}", cookies=cookies)
    assert "Контракт CMS" in r.html
    assert "контракт не объявлен" in r.html


def test_несовместимая_витрина_видна_в_списке(app, sandbox):
    путь = sandbox / "config" / "site-profiles" / f"{SITE}.json"
    данные = json.loads(путь.read_text(encoding="utf-8"))
    данные["cms_contract"] = "99.0.0"
    путь.write_text(json.dumps(данные, ensure_ascii=False), encoding="utf-8")
    cookies, _ = войти(app)
    r = app.handle("GET", "/admin", cookies=cookies)
    assert "управление запрещено" in r.html


def test_действие_над_несовместимой_витриной_отклоняется(app, sandbox):
    """Панель показывает кнопки, но ворота стоят в API."""
    путь = sandbox / "config" / "site-profiles" / f"{SITE}.json"
    данные = json.loads(путь.read_text(encoding="utf-8"))
    данные["cms_contract"] = "99.0.0"
    путь.write_text(json.dumps(данные, ensure_ascii=False), encoding="utf-8")
    cookies, csrf = войти(app)
    app.handle("POST", f"/admin/sites/{SITE}/jobs",
               form={"action": "reindex", "dryRun": "", CSRF_FIELD: csrf}, cookies=cookies)
    assert queue.counts()["inbox"] == 0
    r = app.handle("GET", f"/admin/sites/{SITE}", cookies=cookies)
    assert "incompatible_contract" in r.html
