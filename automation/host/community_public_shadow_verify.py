#!/usr/bin/env python3
"""Пройти сценарии обычного посетителя и модератора по настоящему HTTP.

Витрина поднимается на отдельном порту, с собственным файлом хранилища во
временном каталоге: боевые данные animedia.icu не читаются и не изменяются.
Проверяется не разметка, а поведение — что посетитель может сделать и что он
после этого видит.
"""
from __future__ import annotations

import http.cookiejar
import json
import os
import pathlib
import re
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request

RELEASES = pathlib.Path("/srv/lords/.frontend/releases")
NEW = RELEASES / "20260923T104500Z-community-main-score-11"
BASE = RELEASES / "20260922T143111Z-efdef56-animedia-parity"
TITLE = "/title/master-lda-i-plameni-2/"
MOD_KEY = "shadow-moderator-key"
#: Постоянный ключ этого тайтла в боевых подробностях обеих витрин семейства.
CONTENT_ID = "01a0b507-3280-7b2a-8af4-674dd73cff72"

провалы: list[str] = []


def проверить(условие, описание, подробность=""):
    print(f"   {'ok  ' if условие else 'FAIL'} {описание}"
          + (f"  [{подробность}]" if подробность and not условие else ""))
    if not условие:
        провалы.append(описание)


class Посетитель:
    """Отдельный браузер: своя банка кук, свой ключ."""

    def __init__(self, порт: int, куки_модератора: str = ""):
        self.порт = порт
        self.jar = http.cookiejar.CookieJar()
        self.opener = urllib.request.build_opener(
            urllib.request.HTTPCookieProcessor(self.jar),
            _НеСледоватьЗаРедиректом())
        if куки_модератора:
            # Именно в банку. Ручной заголовок Cookie заставил бы urllib
            # пропустить свои куки, модератор остался бы без amd_v, а значит и
            # без CSRF-токена — и каждая его запись молча отвергалась бы.
            self.jar.set_cookie(http.cookiejar.Cookie(
                0, "amd_mod", куки_модератора, None, False,
                "127.0.0.1", False, False, "/", True,
                False, None, True, None, None, {}))

    def _заголовки(self):
        return {"Host": "animedia.icu"}

    def get(self, путь: str):
        req = urllib.request.Request(f"http://127.0.0.1:{self.порт}{путь}",
                                     headers=self._заголовки())
        with self.opener.open(req, timeout=10) as r:
            return r.status, r.read().decode("utf-8", "replace"), dict(r.headers)

    def post_ok(self, путь: str, поля: dict) -> str:
        """POST, который обязан быть принят. Возвращает Location."""
        код, куда = self.post(путь, поля)
        assert код == 303, f"{путь}: код {код}"
        assert "community=ok" in (куда or ""), f"{путь}: отказ — {куда}"
        return куда or ""

    def post(self, путь: str, поля: dict):
        данные = urllib.parse.urlencode(поля).encode("utf-8")
        req = urllib.request.Request(f"http://127.0.0.1:{self.порт}{путь}",
                                     data=данные, headers=self._заголовки())
        try:
            with self.opener.open(req, timeout=10) as r:
                return r.status, r.headers.get("Location", "")
        except urllib.error.HTTPError as e:
            return e.code, e.headers.get("Location", "")

    def csrf(self, страница: str) -> str:
        m = re.search(r'name="csrf" value="([0-9a-f]+)"', страница)
        return m.group(1) if m else ""


class _НеСледоватьЗаРедиректом(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *a, **k):
        return None


def поднять(release: pathlib.Path, порт: int, store: pathlib.Path,
            витрина: str = "animedia-01"):
    env = dict(os.environ)
    env["ANIMEDIA_COMMUNITY_STORE"] = str(store)
    env["ANIMEDIA_COMMUNITY_MODERATOR_KEY"] = MOD_KEY
    # Вторая витрина того же семейства — настоящая, со своим снимком каталога,
    # а не тот же процесс с другим файлом: идентификатор витрины выводится из
    # имени снимка, и подменять надо именно его.
    env["ANIMEDIA_CATALOG"] = f"/srv/lords/.frontend/{витрина}-catalog.json"
    env["ANIMEDIA_DETAILS"] = f"/srv/lords/.frontend/{витрина}-details.json"
    п = subprocess.Popen([sys.executable, "animedia-frontend.py", "--port", str(порт)],
                         cwd=str(release), env=env,
                         stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    for _ in range(60):
        try:
            req = urllib.request.Request(f"http://127.0.0.1:{порт}/",
                                         headers={"Host": "animedia.icu"})
            urllib.request.urlopen(req, timeout=3).read()
            return п
        except Exception:
            if п.poll() is not None:
                print(п.stdout.read() if п.stdout else "")
                raise SystemExit(f"витрина на {порт} не поднялась")
            time.sleep(0.5)
    raise SystemExit(f"витрина на {порт} не ответила")


def main() -> int:
    tmp = pathlib.Path(tempfile.mkdtemp(prefix="community-shadow-"))
    store = tmp / "community.json"
    сервер = поднять(NEW, 9191, store)
    try:
        гость = Посетитель(9191)
        второй = Посетитель(9191)
        модератор = Посетитель(9191, куки_модератора=MOD_KEY)

        print("\n== страница и текущий UX")
        код, стр, заг = гость.get(TITLE)
        проверить(код == 200, "страница произведения отвечает 200", str(код))
        проверить("noindex" in (заг.get("X-Robots-Tag") or ""),
                  "noindex/nofollow сохранён", заг.get("X-Robots-Tag", ""))
        проверить('data-b07-player="1"' in стр, "плеер на месте")
        проверить('data-community="on"' in стр, "раздел сообщества включён")
        проверить("amd_v=" in (заг.get("Set-Cookie") or ""),
                  "кука посетителя выдана на обычном GET",
                  заг.get("Set-Cookie", "нет"))
        # /lists/ здесь не для галочки: именно эта страница падала с NameError
        # в 2.0 — `списки_посетителя` звала account_id, которого у неё не было.
        for путь in ("/", "/catalog/", "/lists/"):
            к, _, _ = гость.get(путь)
            проверить(к == 200, f"{путь} отвечает 200", str(к))

        токен = гость.csrf(стр)
        проверить(bool(токен), "CSRF-токен в форме есть")

        print("\n== оценка 1–10: первый голос")
        код, куда = гость.post("/community/vote", {
            "slug": "master-lda-i-plameni-2", "subject": CONTENT_ID, "back": TITLE,
            "value": "8", "csrf": токен})
        проверить("community=ok" in (куда or ""), "первый голос принят", куда or str(код))
        _, стр, _ = гость.get(TITLE)
        проверить('data-user-votes="1"' in стр, "голос посчитан")
        проверить('data-user-score="8.0"' in стр, "среднее 8.0")

        print("\n== интерфейс после сохранения")
        проверить("Ваша оценка:" in стр, "показано «Ваша оценка: N»")
        проверить('data-my-score="8"' in стр, "названа именно своя оценка")
        проверить('data-vote-locked="1"' in стр, "повторный выбор заблокирован")
        проверить('action="/community/vote"' not in стр,
                  "формы голосования больше нет — отправлять нечего")
        проверить(стр.count("acomm__vote") >= 10 and "disabled" in стр,
                  "кнопки показаны, но неактивны")

        print("\n== повтор той же оценки")
        код, куда = гость.post("/community/vote", {
            "slug": "master-lda-i-plameni-2", "subject": CONTENT_ID, "back": TITLE,
            "value": "8", "csrf": токен})
        проверить("community=ok" in (куда or ""),
                  "повтор той же оценки принят без ошибки", куда or str(код))
        _, стр, _ = гость.get(TITLE)
        проверить('data-user-votes="1"' in стр, "второго голоса не появилось")
        проверить('data-user-score="8.0"' in стр, "среднее не изменилось")

        print("\n== попытка изменить оценку (старый клиент не должен обойти правило)")
        код, куда = гость.post("/community/vote", {
            "slug": "master-lda-i-plameni-2", "subject": CONTENT_ID, "back": TITLE,
            "value": "2", "csrf": токен})
        проверить("community=error" in (куда or ""),
                  "другая оценка отклонена сервером", куда or str(код))
        _, стр, _ = гость.get(TITLE)
        проверить('data-my-score="8"' in стр, "первоначальный голос сохранён")
        проверить('data-user-votes="1"' in стр, "счётчик не изменился")
        проверить('data-user-score="8.0"' in стр, "среднее не изменилось")

        print("\n== снятие голоса больше не предлагается и не работает")
        # Искать надо кнопку, а не имя класса: правило .acomm__clear остаётся
        # в таблице стилей и само по себе ничего не предлагает нажать.
        проверить('class="acomm__clear"' not in стр, "кнопки «снять оценку» нет")
        код, куда = гость.post("/community/vote", {
            "slug": "master-lda-i-plameni-2", "subject": CONTENT_ID, "back": TITLE,
            "value": "0", "csrf": токен})
        проверить("community=error" in (куда or ""), "снятие отклонено", куда or str(код))
        _, стр, _ = гость.get(TITLE)
        проверить('data-user-votes="1"' in стр, "голос на месте после попытки снять")

        print("\n== состояние восстанавливается в новой вкладке")
        новая = Посетитель(9191)
        новая.jar = гость.jar          # та же кука — тот же посетитель
        новая.opener = гость.opener
        _, вкладка, _ = новая.get(TITLE)
        проверить('data-my-score="8"' in вкладка, "своя оценка видна при новом открытии")
        проверить('data-vote-locked="1"' in вкладка, "и по-прежнему заблокирована")

        print("\n== единый главный рейтинг")
        _, каталог, _ = гость.get("/catalog/")
        проверить('data-main-score="1"' in стр, "главный рейтинг на карточке тайтла")
        проверить('data-main-formula="main-score/1.0"' in стр, "названа версия расчёта")
        проверить('data-main-weight="5"' in стр, "вес объявлен настройкой")
        проверить('data-native-count="1"' in стр,
                  "счётчик считает только живые голоса, не вес")
        проверить('data-main-score="1"' in каталог,
                  "тот же рейтинг в карточках каталога")
        # Сравнивать надо ЭТОТ тайтл, а не всё подряд: на странице ещё полки
        # похожего и рекомендаций, и там карточки других произведений со
        # своими главными рейтингами — совпадать они не обязаны.
        в_колонке = re.search(
            r'class="ztitle__score"[^>]*data-main-value="([0-9.]+)"', стр)
        в_обсуждении = re.search(r'<b data-main-value="([0-9.]+)"', стр)
        проверить(bool(в_колонке), "главный рейтинг назван в колонке карточки")
        проверить(bool(в_обсуждении), "и в обсуждении")
        if в_колонке and в_обсуждении:
            проверить(в_колонке.group(1) == в_обсуждении.group(1),
                      "карточка и обсуждение показывают одно число",
                      f"{в_колонке.group(1)} и {в_обсуждении.group(1)}")
        проверить("Главный рейтинг считается по формуле" in стр,
                  "методика описана в согласии с формулой")
        проверить("Оценки посетителей витрины в неё не входят" not in стр,
                  "старое описание методики убрано")

        print("\n== главный блок рейтинга")
        проверить('data-our-votes="1"' in стр,
                  "голоса посетителей показаны в колонке рейтинга")
        проверить('data-our-average="8.0"' in стр, "с настоящим средним")
        проверить("Посетители ещё не голосовали" not in стр,
                  "при живых голосах колонка не утверждает обратного")
        # Голоса зрителей теперь ВХОДЯТ в главное число — по формуле, и это
        # сказано прямо. Отдельной остаётся строка «Посетители: …», чтобы
        # личный вклад был виден рядом, а не растворялся в общем.
        проверить('data-our-votes=' in стр,
                  "средняя зрителей показана отдельной строкой")
        проверить('data-rating-source="shikimori"' in стр,
                  "внешние источники перечислены отдельным списком")
        проверить('data-rating-details="1"' in стр,
                  "состав вынесен в раскрытие, а не смешан с главным числом")

        print("\n== второй посетитель считается отдельно")
        _, стр2, _ = второй.get(TITLE)
        т2 = второй.csrf(стр2)
        второй.post_ok("/community/vote", {
            "slug": "master-lda-i-plameni-2", "subject": CONTENT_ID, "back": TITLE,
            "value": "9", "csrf": т2})
        _, стр, _ = гость.get(TITLE)
        проверить('data-user-votes="2"' in стр, "второй голос посчитан")
        проверить('data-user-score="8.5"' in стр, "среднее по двоим 8.5")
        проверить('data-my-score="8"' in стр, "чужой голос не изменил свой")

        print("\n== CSRF")
        код, куда = гость.post("/community/comment", {
            "slug": "master-lda-i-plameni-2", "subject": CONTENT_ID, "back": TITLE,
            "name": "Без токена", "text": "это не должно пройти"})
        проверить("community=csrf" in (куда or ""),
                  "запись без CSRF-токена отклонена", куда or "")

        print("\n== комментарий и премодерация")
        код, куда = гость.post("/community/comment", {
            "slug": "master-lda-i-plameni-2", "subject": CONTENT_ID, "back": TITLE,
            "name": "Гость", "text": "Первое сообщение посетителя.", "csrf": токен})
        проверить("community=ok" in (куда or ""), "сообщение принято", куда or str(код))
        _, своя, _ = гость.get(TITLE)
        проверить("Первое сообщение посетителя." in своя, "автор видит своё сообщение")
        проверить('data-comment-status="pending"' in своя, "статус «на проверке» показан")
        проверить("появится в ленте после" in своя, "статус объяснён словами")
        _, чужая, _ = второй.get(TITLE)
        проверить("Первое сообщение посетителя." not in чужая,
                  "постороннему неодобренное не видно")

        print("\n== модератор")
        _, мод_стр, _ = модератор.get(TITLE)
        проверить('data-moderation-queue="1"' in мод_стр, "очередь модерации видна")
        m = re.search(r'data-moderation-id="([0-9a-f]+)"', мод_стр)
        проверить(bool(m), "сообщение в очереди адресуемо")
        ид = m.group(1) if m else ""
        т_мод = модератор.csrf(мод_стр)
        код, куда = модератор.post("/community/comment/decide", {
            "slug": "master-lda-i-plameni-2", "subject": CONTENT_ID, "back": TITLE, "id": ид,
            "decision": "approved", "csrf": т_мод})
        проверить("community=ok" in (куда or ""), "решение принято", куда or str(код))
        _, чужая, _ = второй.get(TITLE)
        проверить("Первое сообщение посетителя." in чужая,
                  "одобренное сообщение опубликовано для всех")

        print("\n== посторонний не модератор")
        _, стр2, _ = второй.get(TITLE)
        проверить('data-moderation-queue="1"' not in стр2,
                  "обычный посетитель очереди не видит")
        код, куда = второй.post("/community/comment/decide", {
            "slug": "master-lda-i-plameni-2", "subject": CONTENT_ID, "back": TITLE, "id": ид,
            "decision": "approved", "csrf": второй.csrf(стр2)})
        проверить("community=forbidden" in (куда or ""),
                  "чужое решение модератора отклонено", куда or "")

        print("\n== ответ")
        _, стр2, _ = второй.get(TITLE)
        код, куда = второй.post("/community/comment", {
            "slug": "master-lda-i-plameni-2", "subject": CONTENT_ID, "back": TITLE, "name": "Второй",
            "text": "Ответ на первое.", "reply_to": ид,
            "csrf": второй.csrf(стр2)})
        проверить("community=ok" in (куда or ""), "ответ принят", куда or str(код))
        _, свой2, _ = второй.get(TITLE)
        проверить("acomm__list--replies" in свой2, "ответ показан веткой")

        print("\n== защита от заливки")
        _, своя, _ = гость.get(TITLE)
        т = гость.csrf(своя)
        код, куда = гость.post("/community/comment", {
            "slug": "master-lda-i-plameni-2", "subject": CONTENT_ID, "back": TITLE, "name": "Гость",
            "text": "Первое сообщение посетителя.", "csrf": т})
        проверить("community=error" in (куда or ""), "повтор слово в слово отклонён",
                  куда or "")
        код, куда = гость.post("/community/comment", {
            "slug": "master-lda-i-plameni-2", "subject": CONTENT_ID, "back": TITLE, "name": "Гость",
            "text": "Совсем другое сообщение.", "csrf": т})
        проверить("community=error" in (куда or ""), "слишком частая отправка отклонена",
                  куда or "")

        print("\n== правка и удаление своего")
        код, куда = гость.post("/community/comment/edit", {
            "slug": "master-lda-i-plameni-2", "subject": CONTENT_ID, "back": TITLE, "id": ид,
            "text": "Поправленное сообщение.", "csrf": т})
        проверить("community=ok" in (куда or ""), "правка принята", куда or str(код))
        _, чужая, _ = второй.get(TITLE)
        проверить("Поправленное сообщение." not in чужая,
                  "правка вернула сообщение на проверку")
        код, куда = второй.post("/community/comment/delete", {
            "slug": "master-lda-i-plameni-2", "subject": CONTENT_ID, "back": TITLE, "id": ид,
            "csrf": второй.csrf(чужая)})
        проверить("community=error" in (куда or ""), "чужое сообщение удалить нельзя",
                  куда or "")
        код, куда = гость.post("/community/comment/delete", {
            "slug": "master-lda-i-plameni-2", "subject": CONTENT_ID, "back": TITLE, "id": ид, "csrf": т})
        проверить("community=ok" in (куда or ""), "своё сообщение удалено",
                  куда or str(код))

        print("\n== XSS")
        _, своя, _ = гость.get(TITLE)
        т = гость.csrf(своя)
        time.sleep(1)
        гость.post("/community/comment", {
            "slug": "master-lda-i-plameni-2", "subject": CONTENT_ID, "back": TITLE,
            "name": "<img src=x onerror=alert(1)>",
            "text": "<script>alert('xss')</script>", "csrf": т})
        _, своя, _ = гость.get(TITLE)
        проверить("<script>alert('xss')</script>" not in своя,
                  "разметка из сообщения не попала на страницу сырой")
        проверить("&lt;script&gt;" in своя, "она экранирована")

        print("\n== контракт точки подключения (f54a5f6)")
        _, стр, _ = гость.get(TITLE)
        проверить(f'data-comments-subject="{CONTENT_ID}"' in стр,
                  "ключ обсуждения — постоянный идентификатор, не адрес")
        проверить('data-comments-subject-kind="content-id"' in стр,
                  "род ключа объявлен, а не угадывается")
        проверить('data-comments-space="animedia-01"' in стр,
                  "пространство — конкретная витрина")
        проверить('data-comments-space="animedia"' not in стр.replace(
                      'data-comments-space="animedia-01"', ''),
                  "пространство не объявлено семейством")
        проверить('data-comments-slug="master-lda-i-plameni-2"' in стр,
                  "адрес сохранён справочным полем")
        проверить('name="subject"' in стр, "формы несут постоянный ключ")

        print("\n== изоляция двух витрин одного семейства")
        store2 = tmp / "community-02.json"
        второй_сайт = поднять(NEW, 9192, store2, витрина="animedia-02")
        try:
            соседка = Посетитель(9192)
            _, стр02, _ = соседка.get(TITLE)
            проверить('data-comments-space="animedia-02"' in стр02,
                      "вторая витрина объявляет себя")
            проверить("Первое сообщение посетителя." not in стр02,
                      "сообщение с animedia-01 не видно на animedia-02")
            проверить('data-user-votes="0"' in стр02,
                      "голоса с animedia-01 не посчитаны на animedia-02")
            т02 = соседка.csrf(стр02)
            соседка.post_ok("/community/vote", {
                "slug": "master-lda-i-plameni-2", "subject": CONTENT_ID,
                "back": TITLE, "value": "3", "csrf": т02})
            _, стр02, _ = соседка.get(TITLE)
            проверить('data-user-score="3.0"' in стр02, "своя оценка на animedia-02")
            _, стр01, _ = гость.get(TITLE)
            проверить('data-user-score="3.0"' not in стр01,
                      "оценка с animedia-02 не протекла на animedia-01")
            д1 = json.loads(store.read_text("utf-8"))
            д2 = json.loads(store2.read_text("utf-8"))
            проверить(д1.get("site_id") == "animedia-01"
                      and д2.get("site_id") == "animedia-02",
                      "каждое хранилище помнит свою витрину",
                      f"{д1.get('site_id')} / {д2.get('site_id')}")
            проверить(CONTENT_ID in (д1.get("titles") or {}),
                      "запись лежит под постоянным ключом")
        finally:
            второй_сайт.terminate()
            try:
                второй_сайт.wait(timeout=10)
            except subprocess.TimeoutExpired:
                второй_сайт.kill()

        print("\n== изоляция домена")
        проверить(json.loads(store.read_text("utf-8")).get("titles") is not None,
                  "запись легла в собственный файл витрины")
        боевой = pathlib.Path("/srv/lords/animedia-01/data/animedia-community.json")
        проверить(store != боевой, "боевой файл animedia.icu не использовался")

    finally:
        сервер.terminate()
        try:
            сервер.wait(timeout=10)
        except subprocess.TimeoutExpired:
            сервер.kill()

    print(f"\nSHADOW_PUBLIC_VERDICT={'PASS' if not провалы else 'FAIL'}")
    for п in провалы:
        print(f"  - {п}")
    return 0 if not провалы else 1


if __name__ == "__main__":
    raise SystemExit(main())
