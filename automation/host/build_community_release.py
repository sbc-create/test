#!/usr/bin/env python3
"""Собрать релиз Animedia с публично работающими комментариями и оценками.

Оценки 1–10 на animedia.icu уже работают: посетитель голосует, меняет свой
голос, среднее и число голосов пересчитываются. Комментарии тоже принимаются,
но публикуются сразу и без премодерации, без ответов, без правки и удаления, а
формы не несут CSRF-токена. Здесь добавляется ровно это — и ничего больше.

Почему патч базового артефакта, а не копия файла в репозитории. Рантайм витрины
(`animedia-frontend.py`, 559 КБ) принадлежит ветке UX-rebuild и правится там.
Копия в этой ветке разошлась бы с оригиналом при первой же чужой правке, и
никто бы этого не заметил. Патч читается целиком, отказывается работать при
неуникальном якоре и записывает, от чего собран.

Модуль `factory/animedia/community.py` наоборот копируется целиком: премодерация
меняет его существенно, и ветка комментариев — законное место для этой правки.
"""
import hashlib
import json
import pathlib
import shutil
import subprocess
import sys

REPO = pathlib.Path(__file__).resolve().parents[2]
RELEASES = pathlib.Path("/srv/lords/.frontend/releases")
BASE_ID = "20260922T143111Z-efdef56-animedia-parity"
NEW_ID = "20260922T223000Z-community-public-01"
BASE, NEW = RELEASES / BASE_ID, RELEASES / NEW_ID


def die(m):
    print(f"REFUSED: {m}", file=sys.stderr)
    sys.exit(1)


def sha256(p):
    return hashlib.sha256(pathlib.Path(p).read_bytes()).hexdigest()


def replace_once(src: str, old: str, new: str, label: str) -> str:
    n = src.count(old)
    if n != 1:
        die(f"anchor '{label}' matched {n} times, expected 1")
    return src.replace(old, new, 1)


# --- 1. cookie on every response, not only on redirects ---------------------
# Без этого кука выдаётся только в ответ на POST: посетитель, который пришёл
# читать, её не получает, и «один голос от одного посетителя» держится на
# адресе. За NAT это один голос на весь дом.
COOKIE_ANCHOR = '''        self.send_response(код)
        self.send_header("Content-Type", тип)
        self.send_header("Content-Length", str(len(тело)))
        self.send_header("X-Robots-Tag", "noindex, nofollow")
'''
COOKIE_PATCH = COOKIE_ANCHOR + '''        if getattr(self, "_новая_кука", ""):
            self.send_header(
                "Set-Cookie",
                f"{self.COOKIE_ПОСЕТИТЕЛЯ}={self._новая_кука}; Path=/; "
                f"Max-Age=31536000; SameSite=Lax; HttpOnly")
'''

# --- 2. CSRF token and moderator flag on the handler ------------------------
HELPERS_ANCHOR = '''    def _перенаправить(self, куда: str) -> None:'''
HELPERS_PATCH = '''    #: Кука модератора. Значение сравнивается с ключом из окружения: пустой
    #: ключ означает, что модератора на этой витрине нет вовсе, а не что им
    #: является любой.
    COOKIE_МОДЕРАТОРА = "amd_mod"

    def _csrf(self) -> str:
        """Токен двойной отправки, выведенный из куки посетителя.

        Куку нельзя прочитать со стороннего сайта (HttpOnly), значит нельзя и
        вычислить токен. SameSite=Lax уже не пустит чужую форму с куками, но
        одна защита — это ноль защит, если она отключится.
        """
        кука = getattr(self, "_куки_посетителя", "") or ""
        if not кука:
            return ""
        return hashlib.sha256(
            ("animedia-community-csrf/1:" + кука).encode("utf-8")).hexdigest()[:32]

    def _csrf_совпал(self, присланный: str) -> bool:
        свой = self._csrf()
        if not свой or not присланный:
            return False
        return secrets.compare_digest(свой, str(присланный))

    def _модератор(self) -> bool:
        ключ = os.environ.get("ANIMEDIA_COMMUNITY_MODERATOR_KEY", "")
        if not ключ:
            return False
        сырое = self.headers.get("Cookie") or ""
        for кусок in сырое.split(";"):
            имя, _, значение = кусок.strip().partition("=")
            if имя == self.COOKIE_МОДЕРАТОРА and значение:
                return secrets.compare_digest(ключ, значение[:128])
        return False

    def _перенаправить(self, куда: str) -> None:'''

# --- 3. POST: CSRF gate, reply field, moderation routes ---------------------
POST_ANCHOR = '''        ключ = self._ключ_посетителя_запроса()
        try:
            if путь == "/community/vote":'''
POST_PATCH = '''        ключ = self._ключ_посетителя_запроса()
        # CSRF до любой записи. Токен выводится из куки, которой у чужой формы
        # нет; запрос без совпадения не меняет ничего и говорит об этом.
        if not self._csrf_совпал(поля.get("csrf") or ""):
            return self._перенаправить(назад + "?community=csrf")
        модератор = self._модератор()
        try:
            if путь == "/community/vote":'''

POST_ROUTES_ANCHOR = '''            elif путь == "/community/comment":
                хранилище.добавить_комментарий(
                    slug, поля.get("name") or "", поля.get("text") or "", ключ)'''
POST_ROUTES_PATCH = '''            elif путь == "/community/comment":
                хранилище.добавить_комментарий(
                    slug, поля.get("name") or "", поля.get("text") or "", ключ,
                    ответ_на=str(поля.get("reply_to") or "").strip())
            elif путь == "/community/comment/decide":
                if not модератор:
                    return self._перенаправить(назад + "?community=forbidden")
                хранилище.решить_комментарий(
                    slug, str(поля.get("id") or ""), str(поля.get("decision") or ""),
                    ключ)
            elif путь == "/community/comment/edit":
                хранилище.изменить_комментарий(
                    slug, str(поля.get("id") or ""), поля.get("text") or "", ключ,
                    модератор=модератор)
            elif путь == "/community/comment/delete":
                хранилище.удалить_комментарий(
                    slug, str(поля.get("id") or ""), ключ, модератор=модератор)'''

# --- 4. renderer: moderator state, CSRF field in every form -----------------
STATE_ANCHOR = '''        с = хранилище.состояние(slug, self._ключ_посетителя())'''
STATE_PATCH = '''        модератор = self._я_модератор()
        с = хранилище.состояние(slug, self._ключ_посетителя(), модератор=модератор)
        csrf_поле = (f'<input type="hidden" name="csrf" '
                     f'value="{html.escape(self._csrf_токен())}">')'''

CSRF_FIELD_ANCHOR = '''            f'<input type="hidden" name="back" value="{html.escape(путь)}">\''''
CSRF_FIELD_PATCH = ('''            f'<input type="hidden" name="back" value="{html.escape(путь)}">'\n'''
                    '''            f'{csrf_поле}\'''')

# Renderer-side accessors mirroring the handler's.
RENDER_HELPERS_ANCHOR = '''    def блок_сообщества(self, запись: dict, деталь: dict) -> str:'''
RENDER_HELPERS_PATCH = '''    def _csrf_токен(self) -> str:
        обработчик = getattr(self, "_обработчик", None)
        if обработчик is not None and hasattr(обработчик, "_csrf"):
            return обработчик._csrf()
        кука = getattr(self, "_куки_посетителя", "") or ""
        if not кука:
            return ""
        return hashlib.sha256(
            ("animedia-community-csrf/1:" + кука).encode("utf-8")).hexdigest()[:32]

    def _я_модератор(self) -> bool:
        обработчик = getattr(self, "_обработчик", None)
        if обработчик is not None and hasattr(обработчик, "_модератор"):
            return обработчик._модератор()
        return False

    def блок_сообщества(self, запись: dict, деталь: dict) -> str:'''

print("patch module loaded")


# --- 5. the comment feed: status, replies, own controls, moderator queue ----
FEED_ANCHOR = '''        лента = "".join(
            f'<li class="acomm__item"><span class="acomm__name">'
            f'{html.escape(str(к.get("name") or "Гость"))}</span>'
            f'<time datetime="{html.escape(str(к.get("created_at") or ""))}">'
            f'{html.escape(_аниме_формат_времени_анонса(str(к.get("created_at") or ""), "datetime"))}'
            f'</time><p>{html.escape(str(к.get("text") or ""))}</p></li>'
            for к in с.комментарии[:20])
        пусто = ('<p class="acomm__none">Обсуждения пока нет. Первое сообщение '
                 'появится здесь сразу после отправки.</p>')
        список_сообщений = (f'<ul class="acomm__list">{лента}</ul>'
                            if лента else пусто)'''

FEED_PATCH = '''        def _действия(к: dict) -> str:
            """Кнопки под своим сообщением. Чужое не предлагается трогать."""
            if not к.get("моё") and not модератор:
                return ""
            ид = html.escape(str(к.get("id") or ""))
            общее = (f'<input type="hidden" name="slug" value="{html.escape(slug)}">'
                     f'<input type="hidden" name="back" value="{html.escape(путь)}">'
                     f'{csrf_поле}<input type="hidden" name="id" value="{ид}">')
            правка = (
                f'<form class="acomm__edit" method="post" '
                f'action="/community/comment/edit">{общее}'
                f'<textarea name="text" rows="2" required '
                f'maxlength="{СООБЩЕСТВО.ДЛИНА_КОММЕНТАРИЯ}">'
                f'{html.escape(str(к.get("text") or ""))}</textarea>'
                f'<button type="submit">Сохранить</button></form>')
            удалить = (
                f'<form class="acomm__del" method="post" '
                f'action="/community/comment/delete">{общее}'
                f'<button type="submit">Удалить</button></form>')
            return f'<div class="acomm__own">{правка}{удалить}</div>'

        def _ответить(к: dict) -> str:
            """Ответить можно только на опубликованное и только на верхний уровень."""
            if str(к.get("parent_id") or "") or к.get("status") != СООБЩЕСТВО.СТАТУС_ОДОБРЕН:
                return ""
            ид = html.escape(str(к.get("id") or ""))
            return (
                f'<details class="acomm__reply"><summary>Ответить</summary>'
                f'<form method="post" action="/community/comment">'
                f'<input type="hidden" name="slug" value="{html.escape(slug)}">'
                f'<input type="hidden" name="back" value="{html.escape(путь)}">'
                f'{csrf_поле}<input type="hidden" name="reply_to" value="{ид}">'
                f'<input name="name" maxlength="40" placeholder="Гость">'
                f'<textarea name="text" rows="2" required '
                f'maxlength="{СООБЩЕСТВО.ДЛИНА_КОММЕНТАРИЯ}" '
                f'placeholder="Ваш ответ"></textarea>'
                f'<button type="submit">Отправить</button></form></details>')

        def _метка(к: dict) -> str:
            """Честный статус вместо молчания: отправленное не пропадает."""
            if к.get("status") != СООБЩЕСТВО.СТАТУС_ОЖИДАЕТ:
                return ""
            return ('<span class="acomm__pending" data-comment-status="pending">'
                    'На проверке — видно только вам, появится в ленте после '
                    'одобрения модератором</span>')

        def _сообщение(к: dict) -> str:
            статус = html.escape(str(к.get("status") or ""))
            правлено = (' · изменено' if к.get("edited_at") else '')
            своё_атрибут = ' data-comment-mine="1"' if к.get("моё") else ''
            return (
                f'<li class="acomm__item" data-comment-id="{html.escape(str(к.get("id") or ""))}" '
                f'data-comment-status="{статус}"{своё_атрибут}>'
                f'<span class="acomm__name">'
                f'{html.escape(str(к.get("name") or "Гость"))}</span>'
                f'<time datetime="{html.escape(str(к.get("created_at") or ""))}">'
                f'{html.escape(_аниме_формат_времени_анонса(str(к.get("created_at") or ""), "datetime"))}'
                f'{правлено}</time>{_метка(к)}'
                f'<p>{html.escape(str(к.get("text") or ""))}</p>'
                f'{_ответить(к)}{_действия(к)}{_ветка(к)}</li>')

        видимые = list(с.комментарии[:20])
        по_родителю: dict = {}
        for к in видимые:
            род = str(к.get("parent_id") or "")
            if род:
                по_родителю.setdefault(род, []).append(к)

        def _ветка(к: dict) -> str:
            дети = по_родителю.get(str(к.get("id") or "")) or []
            if not дети:
                return ""
            return ('<ul class="acomm__list acomm__list--replies">'
                    + "".join(_сообщение(д) for д in дети) + '</ul>')

        лента = "".join(_сообщение(к) for к in видимые
                        if not str(к.get("parent_id") or ""))
        пусто = ('<p class="acomm__none">Обсуждения пока нет. Первое сообщение '
                 'появится здесь сразу после одобрения модератором.</p>')
        список_сообщений = (f'<ul class="acomm__list">{лента}</ul>'
                            if лента else пусто)

        # Очередь модератора. Показывается только модератору и только если в
        # ней что-то есть: пустая панель на странице произведения — шум.
        очередь = ""
        if модератор and с.на_модерации:
            строки = []
            for к in с.на_модерации[:50]:
                ид = html.escape(str(к.get("id") or ""))
                общее = (f'<input type="hidden" name="slug" value="{html.escape(slug)}">'
                         f'<input type="hidden" name="back" value="{html.escape(путь)}">'
                         f'{csrf_поле}<input type="hidden" name="id" value="{ид}">')
                строки.append(
                    f'<li data-moderation-id="{ид}" '
                    f'data-comment-status="{html.escape(str(к.get("status") or ""))}">'
                    f'<span class="acomm__name">'
                    f'{html.escape(str(к.get("name") or "Гость"))}</span>'
                    f'<p>{html.escape(str(к.get("text") or ""))}</p>'
                    f'<form method="post" action="/community/comment/decide">{общее}'
                    f'<button name="decision" value="{СООБЩЕСТВО.СТАТУС_ОДОБРЕН}">'
                    f'Одобрить</button>'
                    f'<button name="decision" value="{СООБЩЕСТВО.СТАТУС_ОТКЛОНЁН}">'
                    f'Отклонить</button></form></li>')
            очередь = (
                f'<div class="acomm__queue" data-moderation-queue="1" '
                f'data-moderation-count="{с.всего_на_модерации}">'
                f'<h3 class="zh zh--sm">На проверке: {с.всего_на_модерации}</h3>'
                f'<ul>{"".join(строки)}</ul></div>')'''

RETURN_ANCHOR = '''            f'<div class="acomm__list-wrap">{список_сообщений}</div>'
            f'{форма}</section>')'''
RETURN_PATCH = '''            f'<div class="acomm__list-wrap">{список_сообщений}</div>'
            f'{очередь}{форма}</section>')'''

QUEUE_ATTR_ANCHOR = '''            f'data-community-comments="{len(с.комментарии)}" \''''
QUEUE_ATTR_PATCH = '''            f'data-community-comments="{len(с.комментарии)}" '
            f'data-community-pending="{с.всего_на_модерации}" \''''


def main() -> int:
    if not BASE.is_dir():
        die(f"base release missing: {BASE}")
    if NEW.exists() and (NEW / "RELEASE.json").exists():
        die(f"refusing to overwrite a finished release: {NEW}")
    if NEW.exists():
        shutil.rmtree(NEW)

    base_manifest = json.loads((BASE / "RELEASE.json").read_text(encoding="utf-8"))
    if base_manifest["artifact_sha256"] != sha256(BASE / "animedia-frontend.py"):
        die("base artifact does not match its own manifest")
    print(f"base {BASE_ID} verified")

    src = (BASE / "animedia-frontend.py").read_text(encoding="utf-8")
    if "_csrf_совпал" in src:
        die("base already carries these changes")

    src = replace_once(src, COOKIE_ANCHOR, COOKIE_PATCH, "cookie on every response")
    src = replace_once(src, HELPERS_ANCHOR, HELPERS_PATCH, "handler helpers")
    src = replace_once(src, POST_ANCHOR, POST_PATCH, "csrf gate")
    src = replace_once(src, POST_ROUTES_ANCHOR, POST_ROUTES_PATCH, "moderation routes")
    src = replace_once(src, RENDER_HELPERS_ANCHOR, RENDER_HELPERS_PATCH, "render helpers")
    src = replace_once(src, STATE_ANCHOR, STATE_PATCH, "moderator state")

    # Раньше правки ленты: та добавляет собственные формы, и они уже несут
    # токен. Иначе счётчик исходных форм перестанет сходиться.
    n = src.count(CSRF_FIELD_ANCHOR)
    if n != 4:
        die(f"expected 4 community forms to gain a csrf field, found {n}")
    src = src.replace(CSRF_FIELD_ANCHOR, CSRF_FIELD_PATCH)

    src = replace_once(src, FEED_ANCHOR, FEED_PATCH, "comment feed")
    src = replace_once(src, RETURN_ANCHOR, RETURN_PATCH, "section return")
    src = replace_once(src, QUEUE_ATTR_ANCHOR, QUEUE_ATTR_PATCH, "pending attribute")

    try:
        compile(src, "animedia-frontend.py", "exec")
    except SyntaxError as e:
        die(f"patched artifact does not compile: {e}")
    print("patched artifact compiles")

    NEW.mkdir(parents=True)
    for item in sorted(BASE.iterdir()):
        if item.name in ("RELEASE.json", "animedia-frontend.py", "community.py"):
            continue
        shutil.copy2(item, NEW / item.name)
    (NEW / "animedia-frontend.py").write_text(src, encoding="utf-8")
    shutil.copymode(BASE / "animedia-frontend.py", NEW / "animedia-frontend.py")
    shutil.copy2(REPO / "factory" / "animedia" / "community.py", NEW / "community.py")

    diff = subprocess.run(["diff", "-u", str(BASE / "animedia-frontend.py"),
                           str(NEW / "animedia-frontend.py")],
                          capture_output=True, text=True).stdout
    added = sum(1 for l in diff.splitlines() if l.startswith("+") and not l.startswith("+++"))
    removed = sum(1 for l in diff.splitlines() if l.startswith("-") and not l.startswith("---"))
    print(f"frontend diff vs base: +{added} / -{removed}")

    manifest = {
        "schema_version": 1, "tenant": "animedia", "site_id": "animedia-01",
        "domain": "animedia.icu", "build_id": NEW_ID,
        "stage": "ANIMEDIA-COMMUNITY-PUBLIC-01",
        "branch": "claude/community-comments-platform-01",
        "built_at": "2026-09-22T22:30:00Z",
        "release_dir": str(NEW), "artifact": "animedia-frontend.py",
        "artifact_sha256": sha256(NEW / "animedia-frontend.py"),
        "rebased_onto": {"build_id": BASE_ID,
                         "artifact_sha256": base_manifest["artifact_sha256"]},
        "adds": ["premoderation with a visible status", "one-level replies",
                 "author and moderator edit/delete", "CSRF double-submit token",
                 "rate limit and duplicate guard",
                 "visitor cookie issued on every response, not only redirects"],
        "keeps": ["player", "URLs", "noindex/nofollow", "external ratings shown "
                  "separately from visitor votes", "existing votes and comments"],
        "frontend_diff": {"added": added, "removed": removed},
        "files": {},
    }
    for item in sorted(NEW.iterdir()):
        if item.name != "RELEASE.json" and item.is_file():
            manifest["files"][item.name] = {"sha256": sha256(item),
                                            "bytes": item.stat().st_size}
    (NEW / "RELEASE.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(f"\nBUILT {NEW_ID}\n  sha256 {manifest['artifact_sha256']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
