"""Имя поставщика постеров разрешается на каждом запросе, а не при загрузке.

Разбор боевого отказа на yummyani.biz. Посетитель видел в «Новых сериях»,
«Актуальном» и «Новом на сайте» чёрные карточки. Замер 7 сентября: из 77
постеров главной 74 отдавались настоящими файлами, а три —
`image/svg+xml`, 532 байта, `X-Poster-Cache: PLACEHOLDER`. Заглушка при этом
почти чёрная (`#1b1d24`) со значком сломанного снимка, то есть выглядит ровно
так, как описал владелец.

Ключ к причине — даты. У всех трёх постеров `Last-Modified` был 7 сентября,
у исправных — раньше. Сам поставщик отдавал все три по запросу, байт в байт
повторяющему запрос nginx (HTTP/1.0, только Host и User-Agent): 200,
`image/webp`. То есть источник был ни при чём.

Причина в `proxy_pass https://poster.cdnvideohub.com/` — имя БЕЗ переменной.
Такое имя nginx разрешает один раз, при загрузке конфигурации, и закрепляет
полученный адрес на всё время жизни рабочих процессов. У записи TTL 120
секунд, адрес меняется; конфигурация же была загружена 4 сентября в 07:15 и
держалась три с половиной суток. Закреплённый узел отвечал, но объектов,
загруженных поставщиком позже, на нём не было — на них приходил 404, а
`proxy_intercept_errors` подменял его заглушкой.

Отказ был молчаливым вдвойне. В `error.log` он не попадает: 404 — это не
ошибка соединения. А старые постеры продолжали отдаваться из дискового кэша,
поэтому ломались только САМЫЕ НОВЫЕ карточки — то есть именно те разделы,
которые показывают свежее. Чем дольше nginx работал без reload, тем больше
карточек чернело.

Проверка тем и подтверждена: `systemctl reload nginx` — без единой правки —
немедленно вернул все три постера. Значит, дело было в закреплённом адресе, а
не в данных.

Тесты ниже держат исправление на ФАКТИЧЕСКОЙ конфигурации, снятой с хоста.
"""

from __future__ import annotations

import re

import pytest

# Запись поставщика живёт 120 секунд. Окно повторного разрешения не должно
# быть длиннее: иначе адрес снова закрепляется, только на меньший срок.
PROVIDER_TTL_SECONDS = 120
PROVIDER_HOST = "poster.cdnvideohub.com"


@pytest.fixture
def snippet(repo_root):
    """Location постеров, снятый с боевого хоста."""
    path = repo_root / "tests" / "fixtures" / "nginx-poster-cache-snippet-production.conf"
    return path.read_text(encoding="utf-8")


@pytest.fixture
def confd(repo_root):
    """Часть в http-контексте: карты и описание кэша."""
    path = repo_root / "tests" / "fixtures" / "nginx-poster-cache-confd-production.conf"
    return path.read_text(encoding="utf-8")


def _proxy_pass(snippet: str) -> str:
    found = re.search(r"^\s*proxy_pass\s+([^;]+);", snippet, re.M)
    assert found, "в location постеров нет proxy_pass"
    return found.group(1).strip()


class TestOriginIsNotPinnedAtLoad:
    """Ровно тот дефект, который чернил карточки."""

    def test_proxy_pass_does_not_name_the_host_literally(self, snippet):
        """Литеральное имя в proxy_pass — это и есть закрепление адреса."""
        assert PROVIDER_HOST not in _proxy_pass(snippet), (
            "имя поставщика стоит в proxy_pass буквально: nginx разрешит его "
            "один раз при загрузке и закрепит адрес до следующего reload"
        )

    def test_proxy_pass_takes_the_host_from_a_variable(self, snippet):
        """Только переменная заставляет nginx разрешать имя на запросе."""
        assert re.match(r"https://\$[A-Za-z_][A-Za-z0-9_]*", _proxy_pass(snippet)), (
            "хост в proxy_pass должен задаваться переменной"
        )

    def test_the_variable_holds_the_provider_host(self, snippet):
        """Переменная должна указывать на поставщика, а не на что придётся."""
        assert re.search(
            r"set\s+\$poster_origin\s+\"%s\"\s*;" % re.escape(PROVIDER_HOST), snippet
        ), "переменная $poster_origin не задана именем поставщика"

    def test_a_resolver_is_defined(self, snippet):
        """С переменной в proxy_pass nginx без resolver вернёт 502."""
        assert re.search(r"^\s*resolver\s+", snippet, re.M), (
            "переменная в proxy_pass без resolver — постеры перестанут "
            "загружаться вовсе"
        )

    def test_resolution_window_is_not_longer_than_the_record(self, snippet):
        """valid= длиннее TTL вернул бы закрепление, только покороче."""
        found = re.search(r"^\s*resolver\b[^;]*\bvalid=(\d+)([sm]?)", snippet, re.M)
        assert found, "у resolver не задан valid= — nginx возьмёт TTL записи"
        seconds = int(found.group(1)) * (60 if found.group(2) == "m" else 1)
        assert seconds <= PROVIDER_TTL_SECONDS, (
            "окно повторного разрешения %ss длиннее TTL записи %ss"
            % (seconds, PROVIDER_TTL_SECONDS)
        )


class TestDestinationIsNotSteeredByTheRequest:
    """Переменная в адресе не должна открыть подстановку чужого пути."""

    @pytest.fixture
    def poster_file_regex(self, confd):
        # Тело карты нельзя вырезать по первой `}`: в самом правиле есть
        # `{8}`, `{4}` и `{12}`, и нежадный разбор оборвался бы на них.
        start = confd.find("map $uri $poster_file")
        assert start != -1, "карта $poster_file не найдена"
        rule = re.search(r"\"~([^\"]+)\"", confd[start:])
        assert rule, "в карте $poster_file нет правила с регулярным выражением"
        return re.compile(rule.group(1))

    @pytest.mark.parametrize(
        "uri",
        [
            "/poster/019efa54-4065-7233-97dc-5e982d0868e7.webp",
            "/poster/01a06d37-a9be-7afa-a9e9-09525c763b94.jpg",
        ],
    )
    def test_provider_names_pass(self, poster_file_regex, uri):
        assert poster_file_regex.match(uri), "нормальное имя постера отклонено"

    @pytest.mark.parametrize(
        "uri",
        [
            "/poster/../etc/passwd",
            "/poster/019efa54-4065-7233-97dc-5e982d0868e7.svg",
            "/poster/019efa54-4065-7233-97dc-5e982d0868e7.webp/../../x",
            "/poster/@evil.example.com/x.webp",
            "/poster/019EFA54-4065-7233-97DC-5E982D0868E7.webp",
            "/poster/x.webp",
            "/poster/",
        ],
    )
    def test_everything_else_is_refused(self, poster_file_regex, uri):
        assert not poster_file_regex.match(uri), (
            "карта приняла адрес, которого не отдаёт поставщик: %s" % uri
        )

    def test_empty_name_returns_404_before_the_proxy(self, snippet):
        """Пустое имя обязано отсекаться до proxy_pass, а не уходить наружу."""
        guard = re.search(r"if\s*\(\s*\$poster_file\s*=\s*\"\"\s*\)\s*\{\s*return\s+404;", snippet)
        assert guard, "нет проверки пустого $poster_file перед proxy_pass"
        assert guard.start() < snippet.index("proxy_pass"), (
            "проверка стоит после proxy_pass — она бы не сработала"
        )
