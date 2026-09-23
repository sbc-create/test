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
NEW_ID = "20260923T104500Z-community-main-score-11"
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
                    subject, поля.get("name") or "", поля.get("text") or "", ключ,
                    ответ_на=str(поля.get("reply_to") or "").strip(), slug=slug)
            elif путь == "/community/comment/decide":
                if not модератор:
                    return self._перенаправить(назад + "?community=forbidden")
                хранилище.решить_комментарий(
                    subject, str(поля.get("id") or ""),
                    str(поля.get("decision") or ""), ключ, slug=slug)
            elif путь == "/community/comment/edit":
                хранилище.изменить_комментарий(
                    subject, str(поля.get("id") or ""), поля.get("text") or "", ключ,
                    модератор=модератор, slug=slug)
            elif путь == "/community/comment/delete":
                хранилище.удалить_комментарий(
                    subject, str(поля.get("id") or ""), ключ, модератор=модератор,
                    slug=slug)'''

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


# --- 6. f54a5f6: постоянный ключ вместо адреса и изоляция по витрине --------
# Оба дефекта были найдены на Zona до раскатки модуля. На Animedia записи под
# старым ключом уже есть, поэтому модуль их переносит, а не бросает.
STORE_ANCHOR = '''        _сообщество_хранилище = СООБЩЕСТВО.открыть(АНИМЕДИА_СООБЩЕСТВО_ПУТЬ)'''
STORE_PATCH = '''        # Витрина, а не семейство: animedia.icu и animedia.space — разные
        # публичные сайты на одном шаблоне, и общее хранилище показало бы
        # записи одного на другом.
        _сообщество_хранилище = СООБЩЕСТВО.открыть(
            АНИМЕДИА_СООБЩЕСТВО_ПУТЬ, витрина=САЙТ_ID)'''

SUBJECT_ANCHOR = '''        модератор = self._я_модератор()
        с = хранилище.состояние(slug, self._ключ_посетителя(), модератор=модератор)'''
SUBJECT_PATCH = '''        # Ключ обсуждения — постоянный идентификатор записи, а не адрес: адрес
        # меняется, и переименование тайтла осиротило бы все его сообщения.
        # Без идентификатора раздел не показывается вовсе: завести данные под
        # ключом, который потом придётся мигрировать, хуже, чем не завести.
        subject = str(деталь.get("id") or запись.get("id") or "").strip()
        if not subject:
            return ""
        модератор = self._я_модератор()
        с = хранилище.состояние(subject, self._ключ_посетителя(),
                                модератор=модератор, slug=slug)'''

SUBJECT_FIELD_ANCHOR = '''            f'{csrf_поле}\''''
SUBJECT_FIELD_PATCH = '''            f'{csrf_поле}'
            f'<input type="hidden" name="subject" value="{html.escape(subject)}">\''''

SECTION_ATTR_ANCHOR = '''            f'data-community-pending="{с.всего_на_модерации}" \''''
SECTION_ATTR_PATCH = '''            f'data-community-pending="{с.всего_на_модерации}" '
            f'data-comments-space="{html.escape(САЙТ_ID)}" '
            f'data-comments-subject="{html.escape(subject)}" '
            f'data-comments-subject-kind="content-id" '
            f'data-comments-slug="{html.escape(slug)}" \''''

HANDLER_KEY_ANCHOR = '''        slug = str(поля.get("slug") or "").strip()'''
HANDLER_KEY_PATCH = '''        slug = str(поля.get("slug") or "").strip()
        subject = str(поля.get("subject") or "").strip()'''

HANDLER_GUARD_ANCHOR = '''        if хранилище is None or not хранилище.доступно or not slug:
            return self._перенаправить(назад + "?community=unavailable")'''
HANDLER_GUARD_PATCH = '''        if хранилище is None or not хранилище.доступно or not subject:
            return self._перенаправить(назад + "?community=unavailable")'''


# Ключом записи должен стать постоянный идентификатор во ВСЕХ маршрутах, а не
# только в отрисовке. Пока запись шла под адресом, чтение спасал запасной
# поиск по slug — то есть дефект был не виден ни на одной странице.
ROUTE_KEY_ANCHOR = '''                if значение == 0:
                    хранилище.снять_голос(slug, ключ)
                else:
                    хранилище.добавить_голос(slug, значение, ключ)
            elif путь == "/community/reaction":
                хранилище.переключить_реакцию(slug, str(поля.get("reaction") or ""), ключ)'''
ROUTE_KEY_PATCH = '''                if значение == 0:
                    хранилище.снять_голос(subject, ключ, slug=slug)
                else:
                    хранилище.добавить_голос(subject, значение, ключ, slug=slug)
            elif путь == "/community/reaction":
                хранилище.переключить_реакцию(
                    subject, str(поля.get("reaction") or ""), ключ, slug=slug)'''

ROUTE_LIST_ANCHOR = '''                хранилище.выбрать_список(slug, выбор, ключ)'''
ROUTE_LIST_PATCH = '''                хранилище.выбрать_список(subject, выбор, ключ, slug=slug)'''


# --- 7. один посетитель — один голос: интерфейс ----------------------------
# Кнопки после сохранения не просто «выглядят нажатыми»: они disabled, а формы
# нет вовсе. Сервер всё равно отказал бы, но предлагать действие, которое
# заведомо будет отклонено, — это обещание, которого интерфейс не держит.
VOTE_UI_ANCHOR = '''        кнопки = "".join(
            f'<button class="acomm__vote{" is-on" if с.мой_голос == n else ""}" '
            f'type="submit" name="value" value="{n}" '
            f'aria-pressed="{"true" if с.мой_голос == n else "false"}">{n}</button>'
            for n in range(СООБЩЕСТВО.ОЦЕНКА_МИН, СООБЩЕСТВО.ОЦЕНКА_МАКС + 1))
        свод = (f'<b>{с.средняя:g}</b><span>из 10 · {с.голосов} '
                f'{"голос" if с.голосов == 1 else "голосов"}</span>'
                if с.средняя is not None else
                '<span class="acomm__none">Оценок посетителей пока нет</span>')
        снять = (f'<button class="acomm__clear" type="submit" name="value" value="0">'
                 f'Снять свою оценку</button>' if с.мой_голос else "")
        голосование = (
            f'<form class="acomm__votes" method="post" action="/community/vote">'
            f'<input type="hidden" name="slug" value="{html.escape(slug)}">'
            f'<input type="hidden" name="back" value="{html.escape(путь)}">'
            f'{csrf_поле}'
            f'<input type="hidden" name="subject" value="{html.escape(subject)}">'
            f'<div class="acomm__score" data-user-score="{с.средняя if с.средняя is not None else ""}"'
            f' data-user-votes="{с.голосов}">{свод}</div>'
            f'<div class="acomm__scale" role="group" aria-label="Поставить оценку">'
            f'{кнопки}</div>{снять}</form>')'''

VOTE_UI_PATCH = '''        проголосовал = с.мой_голос is not None
        кнопки = "".join(
            f'<button class="acomm__vote{" is-on" if с.мой_голос == n else ""}" '
            f'type="submit" name="value" value="{n}" '
            f'{"disabled " if проголосовал else ""}'
            f'aria-pressed="{"true" if с.мой_голос == n else "false"}">{n}</button>'
            for n in range(СООБЩЕСТВО.ОЦЕНКА_МИН, СООБЩЕСТВО.ОЦЕНКА_МАКС + 1))
        свод = (f'<b>{с.средняя:g}</b><span>из 10 · {с.голосов} '
                f'{"голос" if с.голосов == 1 else "голосов"}</span>'
                if с.средняя is not None else
                '<span class="acomm__none">Оценок посетителей пока нет</span>')
        # Своя оценка названа словами и восстанавливается при каждом открытии
        # страницы: она хранится на сервере, а не в этой вкладке.
        моя = (f'<p class="acomm__mine" data-my-score="{с.мой_голос}">'
               f'Ваша оценка: <b>{с.мой_голос}</b>'
               f'<span class="acomm__final"> — оценка ставится один раз '
               f'и не меняется</span></p>' if проголосовал else "")
        # Ошибка сохранения не должна запирать посетителя: пока голос не
        # сохранён, форма остаётся рабочей и попытку можно повторить.
        сбой = ""
        if не_сохранилось and not проголосовал:
            сбой = (f'<p class="acomm__retry" data-vote-error="1">'
                    f'{html.escape(не_сохранилось)} Попробуйте ещё раз.</p>')
        счёт = (f'<div class="acomm__score" '
                f'data-user-score="{с.средняя if с.средняя is not None else ""}"'
                f' data-user-votes="{с.голосов}">{свод}</div>')
        if проголосовал:
            # Формы нет: голос окончателен, отправлять нечего.
            голосование = (
                f'<div class="acomm__votes is-final" data-vote-locked="1">'
                f'{счёт}{моя}'
                f'<div class="acomm__scale" role="group" '
                f'aria-label="Ваша оценка" aria-disabled="true">{кнопки}</div></div>')
        else:
            голосование = (
                f'<form class="acomm__votes" method="post" action="/community/vote">'
                f'<input type="hidden" name="slug" value="{html.escape(slug)}">'
                f'<input type="hidden" name="back" value="{html.escape(путь)}">'
                f'{csrf_поле}'
                f'<input type="hidden" name="subject" value="{html.escape(subject)}">'
                f'{счёт}{сбой}'
                f'<div class="acomm__scale" role="group" aria-label="Поставить оценку">'
                f'{кнопки}</div></form>')'''

# Причина отказа приходит в адресе (?community=error&why=...) — её надо показать
# там, где посетитель нажимал, а не потерять.
VOTE_ERR_ANCHOR = '''        модератор = self._я_модератор()'''
VOTE_ERR_PATCH = '''        не_сохранилось = self._причина_отказа()
        модератор = self._я_модератор()'''

RENDER_ERR_ANCHOR = '''    def _csrf_токен(self) -> str:'''
RENDER_ERR_PATCH = '''    def _причина_отказа(self) -> str:
        """Текст ошибки последнего действия сообщества, если он пришёл в адресе."""
        # Адрес запроса: отрисовка и обработчик — один объект, но запасной
        # путь через _обработчик оставлен, чтобы правка не зависела от этого.
        запрос = getattr(self, "path", "") or ""
        if not запрос:
            обработчик = getattr(self, "_обработчик", None)
            запрос = getattr(обработчик, "path", "") or ""
        if "community=error" not in запрос:
            return ""
        for кусок in запрос.replace("?", "&").split("&"):
            if кусок.startswith("why="):
                return unquote(кусок[4:])[:160]
        return "Не удалось сохранить."

    def _csrf_токен(self) -> str:'''


# --- 8. колонка рейтингов ищет голоса по постоянному ключу ------------------
# `_рейтинги_колонка_b07` уже показывает среднюю посетителей и число голосов
# отдельной строкой и явно не пускает их в сводную — это ровно то поведение,
# которого требует задача. Но искала она их по адресу, а записи переехали под
# постоянный идентификатор: колонка показывала «ещё не голосовали» при живых
# голосах. Ключ тот же, что у раздела обсуждения; адрес остаётся подсказкой
# для переноса.
RAIL_KEY_ANCHOR = '''        свои_голоса = 0
        свои_средняя = None
        хранилище = сообщество()
        if slug and хранилище is not None and getattr(хранилище, "доступно", False):
            с = хранилище.состояние(slug)
            свои_голоса = int(с.голосов or 0)
            свои_средняя = с.средняя'''
RAIL_KEY_PATCH = '''        свои_голоса = 0
        свои_средняя = None
        хранилище = сообщество()
        ключ_темы = str(деталь.get("id") or "").strip()
        if ключ_темы and хранилище is not None and getattr(хранилище, "доступно", False):
            с = хранилище.состояние(ключ_темы, slug=slug)
            свои_голоса = int(с.голосов or 0)
            свои_средняя = с.средняя'''


# --- 9. единый главный рейтинг ---------------------------------------------
# Одна функция на главную карточку, обсуждение и карточки каталога. Три
# независимых вычисления одного и того же неизбежно разойдутся, и посетитель
# увидит на соседних экранах разные числа про одно кино.
EXT_HELPER_ANCHOR = '''def сводная_оценка(деталь: dict) -> dict | None:'''
EXT_HELPER_PATCH = '''def внешние_для_базы(деталь: dict) -> dict:
    """Внешние оценки как {ключ: {"value", "scale"}} для выбора базы.

    Оценка самой витрины сюда не попадает: база обязана быть ВНЕШНЕЙ, иначе
    мнение наших же зрителей вошло бы в формулу дважды — и базой, и голосами.
    Исходные значения источников не изменяются, только читаются.
    """
    итог = {}
    for о in оценки_по_источникам(деталь):
        if о.get("пользовательская"):
            continue
        итог[о["ключ"]] = {"value": о["значение"], "scale": о["шкала"]}
    return итог


def главный_рейтинг_тайтла(деталь: dict) -> dict | None:
    """Единый результат расчёта для этой записи, или None если считать нечем."""
    ключ = str(деталь.get("id") or "").strip()
    if not ключ:
        return None
    try:
        хранилище = сообщество()
        if хранилище is None or not getattr(хранилище, "доступно", False):
            return None
        return хранилище.главный_рейтинг(ключ, внешние_для_базы(деталь))
    except Exception:
        return None


def сводная_оценка(деталь: dict) -> dict | None:'''

# Главная карточка: крупное число — главный рейтинг, личная оценка отдельно.
RAIL_MAIN_ANCHOR = '''        сводная = сводная_оценка(деталь)
        if сводная:'''
RAIL_MAIN_PATCH = '''        главный = главный_рейтинг_тайтла(деталь)
        сводная = сводная_оценка(деталь)
        if главный and главный.get("значение") is not None:
            число = (f'<span class="ztitle__score-val">'
                     f'{главный["значение"]:g}</span>')
            состав = {
                "base+votes": f'внешняя база и {главный["голосов"]} '
                              f'{"голос" if главный["голосов"] == 1 else "голосов"} зрителей',
                "base-only": "внешняя база, зрители ещё не голосовали",
                "votes-only": f'{главный["голосов"]} '
                              f'{"голос" if главный["голосов"] == 1 else "голосов"} зрителей',
            }.get(главный["состояние"], "")
            строка = f'{АНИМЕДИА_СВОДНАЯ_ПОДПИСЬ} · {состав}'
            основа = главный.get("база") or {}
            атрибуты = (
                ' data-main-score="1"'
                f' data-main-value="{главный["значение"]:g}"'
                f' data-main-state="{html.escape(главный["состояние"])}"'
                f' data-main-formula="{html.escape(главный["формула"])}"'
                f' data-main-weight="{главный["вес"]}"'
                f' data-native-count="{главный["голосов"]}"'
                + (f' data-base-value="{основа.get("value")}"'
                   f' data-base-source="{html.escape(str(основа.get("source") or ""))}"'
                   if основа else "")
                + (' data-base-drifted="1"' if главный.get("база_разошлась") else "")
                + (' data-base-provisional="1"' if главный.get("база_предварительная") else ""))
        elif сводная:'''

# Расхождение закреплённой базы с текущей внешней — отдельной строкой.
RAIL_DRIFT_ANCHOR = '''        return (
            f'<aside class="ztitle__rail" data-b07="ratings">\''''
RAIL_DRIFT_PATCH = '''        дрейф = ""
        if главный and главный.get("база_разошлась"):
            сейчас = главный.get("внешняя_сейчас") or {}
            была = главный.get("база") or {}
            дрейф = (
                f'<p class="ztitle__basedrift" data-base-drift="1">'
                f'База рейтинга закреплена при первом голосе: '
                f'{html.escape(str(была.get("source") or ""))} '
                f'{была.get("value")}. Сейчас источник даёт '
                f'{сейчас.get("value")} — это показано отдельно и '
                f'закреплённую базу не меняет.</p>')
        return (
            f'<aside class="ztitle__rail" data-b07="ratings">\''''

RAIL_DRIFT_INSERT_ANCHOR = '''            f'{своя_строка}\''''
RAIL_DRIFT_INSERT_PATCH = '''            f'{своя_строка}{дрейф}\''''

# Обсуждение: то же число, что на карточке.
DISCUSS_ANCHOR = '''        проголосовал = с.мой_голос is not None'''
DISCUSS_PATCH = '''        главный_в_обсуждении = главный_рейтинг_тайтла(деталь)
        проголосовал = с.мой_голос is not None'''

DISCUSS_SHOW_ANCHOR = '''        свод = (f'<b>{с.средняя:g}</b><span>из 10 · {с.голосов} '
                f'{"голос" if с.голосов == 1 else "голосов"}</span>'
                if с.средняя is not None else
                '<span class="acomm__none">Оценок посетителей пока нет</span>')'''
DISCUSS_SHOW_PATCH = '''        # Главный рейтинг сайта — тот же, что на карточке и в каталоге.
        # Рядом, но отдельно, среднее самих посетителей: это разные величины,
        # и показывать одну вместо другой значит путать их между собой.
        if главный_в_обсуждении and главный_в_обсуждении.get("значение") is not None:
            г = главный_в_обсуждении
            своё = (f' · зрители {с.средняя:g} по {с.голосов}'
                    if с.средняя is not None else "")
            свод = (f'<b data-main-value="{г["значение"]:g}">{г["значение"]:g}</b>'
                    f'<span data-main-state="{html.escape(г["состояние"])}">'
                    f'рейтинг сайта{своё}</span>')
        else:
            свод = (f'<b>{с.средняя:g}</b><span>из 10 · {с.голосов} '
                    f'{"голос" if с.голосов == 1 else "голосов"}</span>'
                    if с.средняя is not None else
                    '<span class="acomm__none">Оценок посетителей пока нет</span>')'''

# Карточка каталога: то же число.
CARD_ANCHOR = '''    свод = сводная_оценка(деталь)
    класс = "zt__score" + (" zt__score--row" if строкой else "")'''
CARD_PATCH = '''    # Тот же главный рейтинг, что на странице произведения. Иначе посетитель
    # видит в каталоге одно число, а внутри другое — про одно и то же кино.
    главный_к = главный_рейтинг_тайтла(деталь)
    свод = сводная_оценка(деталь)
    класс = "zt__score" + (" zt__score--row" if строкой else "")
    if главный_к and главный_к.get("значение") is not None:
        состав = {
            "base+votes": f\'внешняя база и {главный_к["голосов"]} зрит.\',
            "base-only": "внешняя база",
            "votes-only": f\'{главный_к["голосов"]} зрит.\',
        }.get(главный_к["состояние"], "")
        подсказка_г = (f\'Рейтинг Animedia {главный_к["значение"]:g} из 10 · \'
                       f\'{состав}\')
        return (f\'<span class="{класс}" data-score-state="value" \'
                f\'data-main-score="1" \'
                f\'data-score="{главный_к["значение"]:g}" \'
                f\'data-main-value="{главный_к["значение"]:g}" \'
                f\'data-main-state="{html.escape(главный_к["состояние"])}" \'
                f\'data-native-count="{главный_к["голосов"]}" \'
                f\'data-score-method="{html.escape(главный_к["формула"])}" \'
                f\'title="{html.escape(подсказка_г)}">\'
                f\'<b aria-hidden="true">{главный_к["значение"]:g}</b>\'
                f\'<span class="vh">{html.escape(подсказка_г)}</span></span>\')'''

# Голос фиксирует базу: обработчику нужны внешние оценки этой записи.
VOTE_EXT_ANCHOR = '''                if значение == 0:
                    хранилище.снять_голос(subject, ключ, slug=slug)
                else:
                    хранилище.добавить_голос(subject, значение, ключ, slug=slug)'''
VOTE_EXT_PATCH = '''                if значение == 0:
                    хранилище.снять_голос(subject, ключ, slug=slug)
                else:
                    # Внешние оценки передаются в момент голоса: база
                    # закрепляется первым голосом и потом не меняется.
                    хранилище.добавить_голос(
                        subject, значение, ключ, slug=slug,
                        внешние=внешние_для_базы(self.вид().деталь(slug) or {}))'''

# Описание методики в раскрытии осталось от прежней сводной и теперь неверно:
# главное число включает голоса зрителей, а текст утверждает обратное. Текст,
# расходящийся с формулой, хуже отсутствующего — на него ссылаются.
METHOD_TEXT_ANCHOR = '''            f\'<p class="ztitle__method">Сводная считается по подтверждённым \'
            f\'источникам с весом по числу голосов. Оценки посетителей витрины \'
            f\'в неё не входят.</p>\''''
METHOD_TEXT_PATCH = '''            f\'<p class="ztitle__method">Главный рейтинг считается по формуле \'
            f\'(вес×база + сумма оценок зрителей) / (вес + число зрителей). \'
            f\'База — внешняя оценка, выбранная по подтверждённому приоритету \'
            f\'источников и закреплённая при первом голосе зрителя; позже она \'
            f\'не меняется, а обновления источников показываются отдельно. \'
            f\'Вес базы — {СООБЩЕСТВО.ВЕС_БАЗЫ}, и это настройка формулы, \'
            f\'а не голоса: отдельно посчитанных зрителей столько, сколько их \'
            f\'есть на самом деле. Список источников ниже — исходные значения, \'
            f\'они не изменяются.</p>\''''


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
    src = replace_once(src, STORE_ANCHOR, STORE_PATCH, "store per site")
    src = replace_once(src, SUBJECT_ANCHOR, SUBJECT_PATCH, "content-id subject")
    src = replace_once(src, SECTION_ATTR_ANCHOR, SECTION_ATTR_PATCH, "mount contract")
    src = replace_once(src, HANDLER_KEY_ANCHOR, HANDLER_KEY_PATCH, "handler subject")
    src = replace_once(src, HANDLER_GUARD_ANCHOR, HANDLER_GUARD_PATCH, "handler guard")
    src = replace_once(src, ROUTE_KEY_ANCHOR, ROUTE_KEY_PATCH, "vote/reaction key")
    src = replace_once(src, ROUTE_LIST_ANCHOR, ROUTE_LIST_PATCH, "list key")
    n = src.count(SUBJECT_FIELD_ANCHOR)
    if n < 4:
        die(f"expected every community form to carry the subject, found {n}")
    src = src.replace(SUBJECT_FIELD_ANCHOR, SUBJECT_FIELD_PATCH)

    # Правка формы голосования — последней: её якорь описывает форму уже с
    # токеном и постоянным ключом, то есть после всех предыдущих вставок.
    src = replace_once(src, RENDER_ERR_ANCHOR, RENDER_ERR_PATCH, "vote error reason")
    src = replace_once(src, VOTE_ERR_ANCHOR, VOTE_ERR_PATCH, "vote error state")
    src = replace_once(src, VOTE_UI_ANCHOR, VOTE_UI_PATCH, "one vote UI")

    # Единый главный рейтинг на карточке, в обсуждении и в каталоге.
    src = replace_once(src, EXT_HELPER_ANCHOR, EXT_HELPER_PATCH, "main score helpers")
    src = replace_once(src, RAIL_MAIN_ANCHOR, RAIL_MAIN_PATCH, "main card score")
    src = replace_once(src, RAIL_DRIFT_ANCHOR, RAIL_DRIFT_PATCH, "base drift notice")
    src = replace_once(src, RAIL_DRIFT_INSERT_ANCHOR, RAIL_DRIFT_INSERT_PATCH, "drift slot")
    src = replace_once(src, DISCUSS_ANCHOR, DISCUSS_PATCH, "discussion main score")
    src = replace_once(src, DISCUSS_SHOW_ANCHOR, DISCUSS_SHOW_PATCH, "discussion summary")
    src = replace_once(src, CARD_ANCHOR, CARD_PATCH, "catalog card score")
    src = replace_once(src, VOTE_EXT_ANCHOR, VOTE_EXT_PATCH, "vote fixes base")
    src = replace_once(src, METHOD_TEXT_ANCHOR, METHOD_TEXT_PATCH, "method text")

    # Колонка рейтингов витрины уже отделяет голоса посетителей от импорта и
    # не пускает их в сводную. Сломан был только ключ: она искала их по адресу.
    src = replace_once(src, RAIL_KEY_ANCHOR, RAIL_KEY_PATCH, "rail votes key")

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
