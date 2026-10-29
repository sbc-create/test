"""Раздел «Приложение „Кинатека“»: ревизии главной по каналам (передача 135).

Сторожится то, что обещано владельцу и приложению:

* запись — своим выключателем и своей областью: право на подборки не даёт права
  на настройки витрин, выключенная запись не существует как маршрут;
* черновик правится со сверкой версии (409 вместо тихой перезаписи);
* публикация проверяет весь документ: состав по каталогу, причины, источники,
  даты и пригодность обложки для общей витрины: решает отметка редактора по
  картинке; жанр из списка риска требует отметки «подходит», а «гарем» и
  возрастная маркировка обложку не оценивают (наблюдение 27.10: «этти» в подборке);
* каналы раздельны: публикация в sandbox не трогает production;
* откат — перевод указателя на прежнюю ревизию своего канала, с записью в истории;
* перенос в production — копия в черновик, публикация отдельно;
* панель делает всё это через API и показывает предпросмотр из ответа API.
"""
import json
from pathlib import Path

import pytest

from factory import audit
from factory.paths import PATHS
from factory.site_engine.admin import ADMIN_COOKIE, CSRF_FIELD
from factory.site_engine.admin.app import AdminApp
from factory.site_engine.api import create_api
from factory.site_engine.api.control import ControlApi
from factory.site_engine.store import InMemoryStore

EDITOR = "editor-token"
SETTINGS = "settings-token"
READER = "reader-token"
A, B, ECCHI = "01aaaaaa-0000-7000-8000-000000000001", "01aaaaaa-0000-7000-8000-000000000002", \
    "01aaaaaa-0000-7000-8000-000000000003"
HAREM = "01aaaaaa-0000-7000-8000-000000000004"
NOW = "2026-10-28T10:00:00Z"


def env(data_dir, *, app_writes="1"):
    return {
        "SITE_ENGINE_CONTROL_WRITES": "",
        "SITE_ENGINE_APP_CONFIG_WRITES": app_writes,
        "SITE_ENGINE_APP_CATALOG_DIR_ANIMEDIA_01": str(data_dir),
        "SITE_ENGINE_CONTROL_TOKENS": f"{EDITOR}=read,app:write|{SETTINGS}=read,config:write|{READER}=read",
    }


@pytest.fixture
def root(tmp_path, monkeypatch):
    monkeypatch.setattr(PATHS, "root", tmp_path)
    for sub in ("var/locks", "var/audit", "var/state", "config/site-profiles"):
        (tmp_path / sub).mkdir(parents=True, exist_ok=True)
    data = tmp_path / "data"
    data.mkdir()
    (data / "animedia-01-details.json").write_text(json.dumps({"catalog_revision": "cat-1", "details": {
        "a": {"id": A, "name": "Первый", "type": "tv", "year": 2026, "genres": ["фэнтези"],
              "poster_url": "https://poster.example/a.webp"},
        "b": {"id": B, "name": "Второй фильм", "type": "movie", "year": 2025, "genres": ["драма"],
              "poster_url": "https://poster.example/b.webp"},
        "e": {"id": ECCHI, "name": "Откровенный", "type": "tv", "year": 2026, "genres": ["комедия", "этти"],
              "poster_url": "https://poster.example/e.webp"},
        "h": {"id": HAREM, "name": "Гаремный", "type": "tv", "year": 2026, "genres": ["гарем", "комедия"],
              "poster_url": "https://poster.example/h.webp"},
    }}, ensure_ascii=False), encoding="utf-8")
    return tmp_path


@pytest.fixture
def api(root):
    return ControlApi(root=root, env=env(root / "data"), now=lambda: 1_793_000_000.0)


def call(api, method, path, body=None, token=EDITOR):
    return api.handle(method, path, body=body or {}, headers={"Authorization": f"Bearer {token}"})


def item(cid, reason="Серия 5 в эфире 28 октября"):
    return {"contentId": cid, "reason": reason, "source": "anilist:1", "checkedAt": NOW}


def doc(items=(A, B), accent="#E3B26B"):
    return {
        "schema": "kinateka-config/1",
        "appearance": {"accent": accent, "heroStyle": "backdrop", "rowCardStyle": "poster", "focusScale": 1.08},
        "home": {"blocks": [
            {"id": "hero", "kind": "hero", "collectionId": "week", "visible": True},
            {"id": "continue", "kind": "continue", "visible": True},
            {"id": "week", "kind": "collection", "collectionId": "week", "title": "В эфире", "visible": True},
            {"id": "recent", "kind": "recent", "title": "Недавно добавлено", "visible": True},
        ]},
        "collections": [{"id": "week", "title": "В эфире на этой неделе", "source": "AniList",
                         "checkedAt": NOW, "items": [item(c) for c in items]}],
    }


def save(api, channel, document):
    version = call(api, "GET", f"/api/v1/apps/kinateka/channels/{channel}").body["draftVersion"]
    r = call(api, "POST", f"/api/v1/apps/kinateka/channels/{channel}/draft",
             {"draft": document, "expectedVersion": version})
    assert r.status == 200, r.body
    return r.body["draftVersion"]


def publish(api, channel, document, expected=None):
    version = save(api, channel, document)
    r = call(api, "POST", f"/api/v1/apps/kinateka/channels/{channel}/publish",
             {"expectedVersion": version, "expectedRevision": expected, "comment": "проверка"})
    return r


# ---- Control API -------------------------------------------------------------

def test_выключенная_запись_не_существует(root):
    api = ControlApi(root=root, env=env(root / "data", app_writes=""))
    r = call(api, "POST", "/api/v1/apps/kinateka/channels/sandbox/draft", {"draft": doc(), "expectedVersion": "x"})
    assert r.status == 404
    assert call(api, "GET", "/api/v1/apps/kinateka").status == 200, "чтение остаётся"


def test_запись_приложения_не_включает_настройки_витрин(api):
    r = call(api, "PATCH", "/api/v1/sites/any/settings", {"changes": {"keep_releases": 3}}, token=EDITOR)
    assert r.status == 404


def test_право_настроек_не_даёт_права_на_подборки(api):
    r = call(api, "POST", "/api/v1/apps/kinateka/channels/sandbox/draft",
             {"draft": doc(), "expectedVersion": "x"}, token=SETTINGS)
    assert r.status == 403 and r.body["error"]["required_scope"] == "app:write"


def test_неизвестный_канал(api):
    assert call(api, "GET", "/api/v1/apps/kinateka/channels/staging").status == 404
    assert call(api, "GET", "/api/v1/apps/other").status == 404


def test_черновик_со_сверкой_версии(api):
    version = save(api, "sandbox", doc())
    r = call(api, "POST", "/api/v1/apps/kinateka/channels/sandbox/draft",
             {"draft": doc(accent="#FF0000"), "expectedVersion": "устаревшая"})
    assert r.status == 409 and r.body["error"]["current_version"] == version


def test_публикация_проверяет_весь_документ(api):
    плохой = doc(items=(A, ECCHI, "нет-такого"))
    плохой["collections"][0]["items"][0]["reason"] = ""
    плохой["appearance"]["focusScale"] = 1.3
    r = publish(api, "sandbox", плохой)
    assert r.status == 422
    текст = json.dumps(r.body["error"]["problems"], ensure_ascii=False)
    assert "обложка не проверена (жанр этти)" in текст
    assert "нет-такого нет в каталоге" in текст
    assert "нет причины" in текст
    assert "1.00 до 1.12" in текст
    assert call(api, "GET", "/api/v1/apps/kinateka").body["channels"]["sandbox"]["current"] is None


def test_публикация_в_песочницу_не_трогает_рабочий_канал(api, root):
    r = publish(api, "sandbox", doc())
    assert r.status == 200, r.body
    assert r.body["revision"] == 1
    обзор = call(api, "GET", "/api/v1/apps/kinateka").body
    assert обзор["channels"]["sandbox"]["current"] == 1
    assert обзор["channels"]["production"]["current"] is None
    store = root / "var" / "app-config" / "animedia-01"
    assert json.loads((store / "published-sandbox.json").read_text()) == {"revision": 1}
    assert not (store / "published-production.json").exists()
    ревизия = json.loads((store / "revisions" / "1.json").read_text(encoding="utf-8"))
    assert ревизия["channel"] == "sandbox" and ревизия["schema"] == "kinateka-config/1"
    assert ревизия["revisionId"].startswith("r1-")


def test_публикация_сверяет_действующую_ревизию(api):
    assert publish(api, "sandbox", doc()).status == 200
    r = publish(api, "sandbox", doc(items=(B, A)), expected=None)   # кто-то опубликовал раньше
    assert r.status == 409 and r.body["error"]["current_revision"] == 1


def test_откат_и_история(api):
    assert publish(api, "sandbox", doc()).status == 200
    assert publish(api, "sandbox", doc(items=(B, A)), expected=1).status == 200
    r = call(api, "POST", "/api/v1/apps/kinateka/channels/sandbox/rollback",
             {"toRevision": 1, "expectedRevision": 2, "comment": "вернуть порядок"})
    assert r.status == 200, r.body
    обзор = call(api, "GET", "/api/v1/apps/kinateka").body
    assert обзор["channels"]["sandbox"]["current"] == 1
    история = обзор["history"]
    assert [h["action"] for h in история] == ["rollback", "publish", "publish"]
    assert история[0]["rollbackOf"] == 2 and история[0]["comment"] == "вернуть порядок"
    действия = [e["action"] for e in audit.read_all()]
    assert "control.app.publish" in действия and "control.app.rollback" in действия


def test_откат_на_ревизию_другого_канала_запрещён(api):
    assert publish(api, "sandbox", doc()).status == 200
    r = call(api, "POST", "/api/v1/apps/kinateka/channels/production/rollback",
             {"toRevision": 1, "expectedRevision": None})
    assert r.status == 422 and r.body["error"]["code"] == "wrong_channel"


def test_перенос_в_рабочий_канал_отдельным_шагом(api):
    assert publish(api, "sandbox", doc()).status == 200
    version = call(api, "GET", "/api/v1/apps/kinateka/channels/production").body["draftVersion"]
    r = call(api, "POST", "/api/v1/apps/kinateka/channels/production/import",
             {"fromRevision": 1, "expectedVersion": version})
    assert r.status == 200, r.body
    канал = call(api, "GET", "/api/v1/apps/kinateka/channels/production").body
    assert канал["current"] is None, "копия в черновик ничего не публикует"
    assert канал["draft"]["collections"][0]["id"] == "week"
    r = call(api, "POST", "/api/v1/apps/kinateka/channels/production/publish",
             {"expectedVersion": канал["draftVersion"], "expectedRevision": None})
    assert r.status == 200 and r.body["revision"] == 2


def отметка(cid, verdict, url=None):
    return {"contentId": cid, "imageUrl": url or f"https://poster.example/{ {A: 'a', B: 'b', ECCHI: 'e', HAREM: 'h'}[cid] }.webp",
            "verdict": verdict, "reviewedAt": NOW}


def test_гарем_не_оценивает_обложку(api):
    r = publish(api, "sandbox", doc(items=(A, HAREM)))
    assert r.status == 200, r.body


def test_отметка_откровенной_обложки_убирает_тайтл_любого_жанра(api):
    d = doc(items=(A, B))
    d["artwork"] = {"reviews": [отметка(B, "explicit")]}
    r = publish(api, "sandbox", d)
    assert r.status == 422
    assert "«Второй фильм»: обложка отмечена редактором как откровенная" in json.dumps(
        r.body["error"]["problems"], ensure_ascii=False)


def test_жанр_риска_проходит_после_отметки_подходит(api):
    d = doc(items=(ECCHI, A))
    d["artwork"] = {"reviews": [отметка(ECCHI, "ok")]}
    save(api, "sandbox", d)
    канал = call(api, "GET", "/api/v1/apps/kinateka/channels/sandbox").body
    assert канал["publishable"] is True, канал["problems"]
    assert [i["contentId"] for i in канал["preview"]["collections"][0]["items"]] == [ECCHI, A]
    assert канал["artwork"]["queue"] == [] and канал["artwork"]["reviews"][0]["applies"] is True
    r = call(api, "POST", "/api/v1/apps/kinateka/channels/sandbox/publish",
             {"expectedVersion": канал["draftVersion"], "expectedRevision": None})
    assert r.status == 200
    # Отметка — часть ревизии: служба чтения применяет её так же.
    assert call(api, "GET", "/api/v1/apps/kinateka/revisions/1").body["artwork"]["reviews"][0]["verdict"] == "ok"


def test_отметка_относится_к_картинке_а_не_к_тайтлу(api):
    d = doc(items=(ECCHI, A))
    d["artwork"] = {"reviews": [отметка(ECCHI, "ok", url="https://poster.example/old.webp")]}
    save(api, "sandbox", d)
    канал = call(api, "GET", "/api/v1/apps/kinateka/channels/sandbox").body
    assert канал["publishable"] is False
    assert канал["artwork"]["reviews"][0]["applies"] is False
    assert [q["contentId"] for q in канал["artwork"]["queue"]] == [ECCHI]


def test_неверная_отметка_не_публикуется(api):
    d = doc()
    d["artwork"] = {"reviews": [{"contentId": A, "imageUrl": "http://x", "verdict": "maybe"}]}
    r = publish(api, "sandbox", d)
    текст = json.dumps(r.body["error"]["problems"], ensure_ascii=False)
    assert r.status == 422 and "вердикт ok или explicit" in текст and "https://" in текст and "reviewedAt" in текст


def test_предпросмотр_из_каталога_и_запрет_жанров(api):
    save(api, "sandbox", doc(items=(ECCHI, A)))
    канал = call(api, "GET", "/api/v1/apps/kinateka/channels/sandbox").body
    п = канал["preview"]["collections"][0]
    assert [i["contentId"] for i in п["items"]] == [A]
    assert п["missing"] == [ECCHI]
    assert п["items"][0]["title"] == "Первый" and п["items"][0]["posterUrl"].endswith("a.webp")
    assert канал["publishable"] is False


def test_поиск_в_каталоге_помечает_жанры(api):
    r = call(api, "GET", "/api/v1/apps/kinateka/catalog", {"q": "откров"})
    assert r.status == 200
    assert r.body["items"][0]["coverRisk"] == ["этти"]


# ---- админка -----------------------------------------------------------------

@pytest.fixture
def admin(root, api):
    read = create_api([], root=root, loader=lambda p: (InMemoryStore(p.site_id), "тестовый"),
                      env={"SITE_ENGINE_API_ENABLED": "1", "SITE_ENGINE_ENVIRONMENT": "test"})
    return AdminApp(read, api)


def войти(admin, token=EDITOR):
    r = admin.handle("POST", "/admin/login", form={"token": token})
    sid = r.headers["Set-Cookie"].split(";")[0].split("=", 1)[1]
    return {ADMIN_COOKIE: sid}, admin.sessions.csrf_token(sid)


def страница(admin, cookies, path="/admin/apps/kinateka/sandbox"):
    r = admin.handle("GET", path, cookies=cookies)
    assert r.status == 200, r.html[:400]
    return r.html


def версия(html):
    return html.split('name="draftVersion" value="', 1)[1].split('"', 1)[0]


def test_раздел_в_шапке_и_обзор_каналов(admin):
    cookies, _ = войти(admin)
    html = страница(admin, cookies, "/admin/apps/kinateka")
    assert "Приложение «Кинатека»" in html
    assert "Канал sandbox" in html and "Канал production" in html


def test_полный_путь_через_панель(admin, api):
    cookies, csrf = войти(admin)
    save(api, "sandbox", doc())
    html = страница(admin, cookies)
    assert "черновик готов к публикации" in html and "Предпросмотр черновика" in html
    assert "poster.example/a.webp" in html
    # порядок блоков и скрытие
    v = версия(html)
    форма = {CSRF_FIELD: csrf, "draftVersion": v, "order_hero": "1", "order_continue": "4", "order_week": "2",
             "order_recent": "3", "visible_hero": "1", "visible_week": "1", "visible_continue": "1",
             "title_week": "В эфире сейчас", "title_recent": "Недавно добавлено", "cardStyle_week": "landscape",
             "cover_week": ""}
    r = admin.handle("POST", "/admin/apps/kinateka/sandbox/blocks", form=форма, cookies=cookies)
    assert r.status == 303
    черновик = call(api, "GET", "/api/v1/apps/kinateka/channels/sandbox").body["draft"]
    assert [b["id"] for b in черновик["home"]["blocks"]] == ["hero", "week", "recent", "continue"]
    assert черновик["home"]["blocks"][2]["visible"] is False
    assert черновик["home"]["blocks"][1]["title"] == "В эфире сейчас"
    assert черновик["home"]["blocks"][1]["cardStyle"] == "landscape"
    # порядок в подборке
    html = страница(admin, cookies, "/admin/apps/kinateka/sandbox/collections/week")
    форма = {CSRF_FIELD: csrf, "draftVersion": версия(html), "title": "В эфире на этой неделе",
             "source": "AniList", "checkedAt": NOW, f"order_{A}": "2", f"order_{B}": "1"}
    assert admin.handle("POST", "/admin/apps/kinateka/sandbox/collections/week", form=форма,
                        cookies=cookies).status == 303
    черновик = call(api, "GET", "/api/v1/apps/kinateka/channels/sandbox").body["draft"]
    assert [i["contentId"] for i in черновик["collections"][0]["items"]] == [B, A]
    # публикация
    html = страница(admin, cookies)
    r = admin.handle("POST", "/admin/apps/kinateka/sandbox/publish", cookies=cookies, form={
        CSRF_FIELD: csrf, "draftVersion": версия(html), "expectedRevision": "", "comment": "первая"})
    assert r.status == 303
    html = страница(admin, cookies)
    assert "Опубликовано в sandbox: ревизия 1" in html
    assert "Действует ревизия <b>1</b>" in html


def test_обложки_отмечаются_в_панели(admin, api):
    cookies, csrf = войти(admin)
    save(api, "sandbox", doc(items=(ECCHI, A)))
    html = страница(admin, cookies)
    assert "Ждут просмотра" in html and "poster.example/e.webp" in html
    r = admin.handle("POST", "/admin/apps/kinateka/sandbox/artwork/mark", cookies=cookies, form={
        CSRF_FIELD: csrf, "draftVersion": версия(html), "contentId": ECCHI,
        "imageUrl": "https://poster.example/e.webp", "verdict": "ok"})
    assert r.status == 303
    html = страница(admin, cookies)
    assert "Ждут просмотра" not in html and "черновик готов к публикации" in html
    # по contentId — берётся нынешний постер из каталога
    r = admin.handle("POST", "/admin/apps/kinateka/sandbox/artwork/mark", cookies=cookies, form={
        CSRF_FIELD: csrf, "draftVersion": версия(html), "contentId": A, "verdict": "explicit",
        "note": "кадр с обнажением"})
    assert r.status == 303
    черновик = call(api, "GET", "/api/v1/apps/kinateka/channels/sandbox").body["draft"]
    assert черновик["artwork"]["reviews"][1] == {**черновик["artwork"]["reviews"][1], "contentId": A,
                                                 "imageUrl": "https://poster.example/a.webp",
                                                 "verdict": "explicit", "note": "кадр с обнажением"}
    html = страница(admin, cookies)
    assert "обложка отмечена редактором как откровенная" in html
    r = admin.handle("POST", "/admin/apps/kinateka/sandbox/artwork/remove", cookies=cookies, form={
        CSRF_FIELD: csrf, "draftVersion": версия(html), "contentId": A,
        "imageUrl": "https://poster.example/a.webp"})
    assert r.status == 303
    assert len(call(api, "GET", "/api/v1/apps/kinateka/channels/sandbox").body["draft"]["artwork"]["reviews"]) == 1


def test_испорченное_поле_обложек_даёт_сообщение_а_не_сбой(admin, api):
    cookies, csrf = войти(admin)
    d = doc()
    d["artwork"] = []
    save(api, "sandbox", d)
    html = страница(admin, cookies)
    r = admin.handle("POST", "/admin/apps/kinateka/sandbox/artwork/mark", cookies=cookies, form={
        CSRF_FIELD: csrf, "draftVersion": версия(html), "contentId": A,
        "imageUrl": "https://poster.example/a.webp", "verdict": "ok"})
    assert r.status == 303
    assert "artwork черновика не по форме" in страница(admin, cookies)


def test_устаревшая_форма_даёт_конфликт_а_не_перезапись(admin, api):
    cookies, csrf = войти(admin)
    save(api, "sandbox", doc())
    старая = версия(страница(admin, cookies))
    save(api, "sandbox", doc(accent="#112233"))              # чужая правка
    admin.handle("POST", "/admin/apps/kinateka/sandbox/appearance", cookies=cookies, form={
        CSRF_FIELD: csrf, "draftVersion": старая, "accent": "#ff0000", "heroStyle": "poster",
        "rowCardStyle": "poster", "focusScale": "1.1"})
    html = страница(admin, cookies)
    assert "409 version_conflict" in html
    assert call(api, "GET", "/api/v1/apps/kinateka/channels/sandbox").body["draft"]["appearance"]["accent"] == "#112233"


def test_откат_кнопкой_истории(admin, api):
    cookies, csrf = войти(admin)
    assert publish(api, "sandbox", doc()).status == 200
    assert publish(api, "sandbox", doc(items=(B, A)), expected=1).status == 200
    html = страница(admin, cookies)
    assert "Вернуть ревизию 1" in html
    r = admin.handle("POST", "/admin/apps/kinateka/sandbox/rollback", cookies=cookies, form={
        CSRF_FIELD: csrf, "toRevision": "1", "expectedRevision": "2"})
    assert r.status == 303
    assert call(api, "GET", "/api/v1/apps/kinateka").body["channels"]["sandbox"]["current"] == 1


def test_только_чтение_видит_но_не_меняет(admin, api):
    cookies, csrf = войти(admin, READER)
    save(api, "sandbox", doc())
    html = страница(admin, cookies)
    assert "disabled" in html
    admin.handle("POST", "/admin/apps/kinateka/sandbox/publish", cookies=cookies, form={
        CSRF_FIELD: csrf, "draftVersion": версия(html), "expectedRevision": ""})
    assert "403" in страница(admin, cookies)
    assert call(api, "GET", "/api/v1/apps/kinateka").body["channels"]["sandbox"]["current"] is None


def test_значения_экранируются(admin, api):
    cookies, _ = войти(admin)
    d = doc()
    d["collections"][0]["title"] = "<script>alert(1)</script>"
    save(api, "sandbox", d)
    html = страница(admin, cookies)
    assert "<script>alert" not in html and "&lt;script&gt;" in html


def test_поиск_тайтла_на_странице_подборки(admin, api):
    cookies, _ = войти(admin)
    save(api, "sandbox", doc())
    r = admin.handle("GET", "/admin/apps/kinateka/sandbox/collections/week", form={"q": "откров"},
                     cookies=cookies)
    assert ECCHI in r.html and "обложку нужно посмотреть: жанр этти" in r.html


def test_после_отката_черновик_помечен_и_берётся_из_ревизии(admin, api):
    cookies, csrf = войти(admin)
    assert publish(api, "sandbox", doc()).status == 200
    assert publish(api, "sandbox", doc(items=(B, A)), expected=1).status == 200
    call(api, "POST", "/api/v1/apps/kinateka/channels/sandbox/rollback", {"toRevision": 1, "expectedRevision": 2})
    html = страница(admin, cookies)
    assert "Черновик отличается от действующей ревизии 1" in html
    admin.handle("POST", "/admin/apps/kinateka/sandbox/import", cookies=cookies, form={
        CSRF_FIELD: csrf, "draftVersion": версия(html), "fromRevision": "1"})
    html = страница(admin, cookies)
    assert "Черновик отличается" not in html
    черновик = call(api, "GET", "/api/v1/apps/kinateka/channels/sandbox").body["draft"]
    assert [i["contentId"] for i in черновик["collections"][0]["items"]] == [A, B]


def test_через_http_слой_фабрики(root):
    """Проверки выше зовут ControlApi напрямую и не видели, что HTTP-слой отвечает
    405 на любой PUT (установка 28.10: черновик не сохранился, а публикация прошла
    с черновиком по умолчанию). Здесь — тот же путь через настоящий сервер."""
    import threading
    import urllib.request

    from factory.site_engine.api.server import ServerConfig, build_server
    control = ControlApi(root=root, env=env(root / "data"))
    read = create_api([], root=root, env={"SITE_ENGINE_API_ENABLED": "1", "SITE_ENGINE_ENVIRONMENT": "test"})
    srv = build_server(ServerConfig(host="127.0.0.1", port=0), read, control, None)
    поток = threading.Thread(target=srv.serve_forever, kwargs={"poll_interval": 0.05}, daemon=True)
    поток.start()
    база = f"http://127.0.0.1:{srv.server_address[1]}/api/v1/apps/kinateka/channels/sandbox"

    def http(метод, путь="", тело=None):
        req = urllib.request.Request(база + путь, method=метод,
                                     data=json.dumps(тело).encode() if тело is not None else None,
                                     headers={"Authorization": f"Bearer {EDITOR}", "Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=10) as о:
                return о.status, json.loads(о.read())
        except urllib.error.HTTPError as e:
            return e.code, json.loads(e.read())
    try:
        _, канал = http("GET")
        код, ответ = http("POST", "/draft", {"draft": doc(), "expectedVersion": канал["draftVersion"]})
        assert код == 200, ответ
        код, ответ = http("POST", "/publish", {"expectedVersion": ответ["draftVersion"], "expectedRevision": None})
        assert код == 200, ответ
        _, канал = http("GET")
        assert канал["currentRevision"]["collections"][0]["id"] == "week", "опубликован сохранённый черновик"
    finally:
        srv.shutdown()
        поток.join(timeout=5)
        srv.server_close()
