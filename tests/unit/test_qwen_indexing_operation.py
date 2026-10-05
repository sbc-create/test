"""Операция смены режима индексации: что в ней нельзя сломать.

Проверки сетью не пользуются: они держат СВОЙСТВА операции, а не состояние
живого сайта. Там, где свойство относится к живому ответу, проверяется логика
оценки сигналов на заранее заданных ответах.

Каждая отвечает на вопрос «что станет неправдой, если это место изменят».
Главный из них: сайт не должен открыться случайно — ни от пустого значения, ни
от нуля, ни от строки, похожей на правду, ни от отсутствия разрешения.
"""
from __future__ import annotations

import json
import pathlib
import re

import pytest

from factory.qwen import indexing

КОРЕНЬ = pathlib.Path(__file__).resolve().parents[2]


# --- 1. Четыре слоя, и ни один не открывает сайт сам ----------------------

def test_операция_меняет_только_состояние_а_не_разрешения():
    """Разрешения выдаёт владелец и несёт выпуск. Если операция начнёт менять
    их сама, она выдаст себе право: тот же признак станет и разрешением, и
    результатом его применения.
    """
    import ast
    исходник = (КОРЕНЬ / "factory" / "qwen" / "indexing.py").read_text("utf-8")
    дерево = ast.parse(исходник)
    функция = next(у for у in дерево.body
                   if isinstance(у, ast.FunctionDef) and у.name == "установить")
    # Записывать операция вправе только через три своих помощника: файл
    # состояния, снимок прежнего состояния и журнал. Любой иной вызов записи
    # означал бы, что она правит то, чего не её дело.
    разрешённые = {"_записать", "_снимок", "_дописать_журнал"}
    запрещённые = {"write_text", "write_bytes", "unlink", "replace", "mkdir"}
    найдено = set()
    for у in ast.walk(функция):
        if isinstance(у, ast.Call):
            имя = (у.func.attr if isinstance(у.func, ast.Attribute)
                   else getattr(у.func, "id", ""))
            if имя in запрещённые:
                найдено.add(имя)
    assert not найдено, (
        f"операция пишет напрямую через {sorted(найдено)}; записи идут только "
        f"через {sorted(разрешённые)}")
    # И ни один помощник записи не трогает разрешения.
    for помощник in ("_записать", "_снимок", "_дописать_журнал"):
        тело = исходник.split(f"def {помощник}", 1)[1].split("\ndef ", 1)[0]
        assert "site-cells" not in тело, помощник
        assert "/config/site.json" not in тело, помощник
        assert "/etc/nginx" not in тело, помощник


def test_разрешение_владельца_только_булево_true():
    """Пустое поле здесь не умолчание в пользу открытия."""
    т = (КОРЕНЬ / "factory" / "qwen" / "indexing.py").read_text("utf-8")
    # Имя с открывающей скобкой: рядом живёт `разрешение_владельца_ядра`
    # (авторитетный реестр владельца у Yummy), и разбор по префиксу
    # брал бы её тело вместо нужного.
    тело = т.split("def разрешение_владельца(", 1)[1].split("\ndef ", 1)[0]
    assert 'инд.get("open_authorized") is True' in тело, (
        "разрешением считается только булево true")
    assert "open_authorized" in тело and "desired_state" in тело, (
        "разрешение и объявленный режим — разные поля")


def test_корни_выпуска_называют_работающий_код():
    """`current` впереди `app`, рабочей копии в перечне нет.

    Проверяется ПОВЕДЕНИЕМ помощника, а не текстом функций: перечень корней
    выпуска — одно определение на модуль, и обе решающие функции обязаны
    пользоваться им, а не собирать путь заново.
    """
    from factory.qwen import indexing
    корни = indexing.корни_выпуска("образец-уч")
    assert корни == ("/srv/образец-уч/current", "/srv/образец-уч/app")
    for корень in корни:
        assert "site-repos" not in корень, (
            "рабочая копия репозитория доказательством не является")


def test_решения_о_режиме_берут_путь_из_одного_места():
    """Ни одна из решающих функций не собирает путь выпуска сама."""
    т = (КОРЕНЬ / "factory" / "qwen" / "indexing.py").read_text("utf-8")
    for имя in ("читатель_режима", "_разрешение_в_конфиге"):
        тело = т.split(f"def {имя}", 1)[1].split("\ndef ", 1)[0]
        assert "корни_выпуска(" in тело, (
            f"{имя} обязана брать корни выпуска из одного места")
        assert "/srv/" not in тело.replace("корни_выпуска(", ""), (
            f"{имя} собирает путь выпуска заново — два правила разойдутся")
        assert "site-repos" not in тело, (
            f"{имя} смотрит в рабочую копию")


def test_разрешение_выпуска_только_булево_true():
    т = (КОРЕНЬ / "factory" / "qwen" / "indexing.py").read_text("utf-8")
    тело = т.split("def _разрешение_в_конфиге", 1)[1].split("\ndef ", 1)[0]
    assert "значение is True" in тело, (
        "разрешением считается только булево true")


def test_разрешение_выпуска_семейное():
    """У Yummy разрешение живёт в переменной контейнера, а не в файле выпуска."""
    т = (КОРЕНЬ / "factory" / "qwen" / "indexing.py").read_text("utf-8")
    тело = т.split("def разрешение_выпуска", 1)[1].split("\ndef ", 1)[0]
    assert "контракт(adapter, аккаунт=аккаунт)" in тело, (
        "семейство обязано учитываться — и вместе с учётной записью: у Yummy "
        "одна точка входа работает в двух формах рантайма (контейнер и "
        "ячейка), и форму выбирает ВЫПУЩЕННЫЙ код, а не имя семейства")
    assert "container:" in тело, (
        "разрешение в переменной контейнера должно разбираться отдельно")


def test_корень_состояния_совпадает_с_читателем_витрины():
    """Расхождение означало бы запись в один файл и чтение другого."""
    читатель = (КОРЕНЬ / "var" / "site-repos" / "animedia-space"
                / "src" / "indexing_mode.py")
    if not читатель.is_file():
        pytest.skip("рабочая копия витрины недоступна")
    т = читатель.read_text(encoding="utf-8")
    м = re.search(r'КОРЕНЬ = os\.environ\.get\("[^"]+",\s*"([^"]+)"\)', т)
    assert м, "в читателе не найден корень по умолчанию"
    assert str(indexing.КОРЕНЬ) == м.group(1), (
        f"операция пишет в {indexing.КОРЕНЬ}, а витрина читает {м.group(1)}")


# --- 2. Оценка публичных сигналов -----------------------------------------

ОТКРЫТЫЕ_СИГНАЛЫ = {
    "x_robots_values": ["index, follow"],
    "x_robots_values_http80": ["index, follow"],
    "meta_robots_home": "index, follow",
    "robots_txt": "User-agent: *\nDisallow: /poster/\nAllow: /\n",
    "robots_txt_http": "200",
}


class _Стенд:
    """Крошечный сервер, который отвечает перенаправлением и страницей.

    Нужен настоящий сокет: проверяется именно поведение замера на 308, а
    подменённый `urlopen` проверял бы подмену.
    """

    def __init__(self, код: int, запрет_на_переходе: bool,
                 запрет_на_странице: bool):
        import http.server
        import threading
        стенд = self

        class Рука(http.server.BaseHTTPRequestHandler):
            def log_message(self, *_):
                pass

            def do_GET(self):
                if self.path == "/":
                    self.send_response(код)
                    self.send_header("Location", f"http://{стенд.адрес}/page")
                    if запрет_на_переходе:
                        self.send_header("X-Robots-Tag", "noindex, nofollow")
                    self.send_header("Content-Length", "0")
                    self.end_headers()
                    return
                тело = "<html><head></head><body>страница</body></html>".encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(тело)))
                if запрет_на_странице:
                    self.send_header("X-Robots-Tag", "noindex, nofollow")
                self.end_headers()
                self.wfile.write(тело)

        self.сервер = http.server.HTTPServer(("127.0.0.1", 0), Рука)
        self.адрес = f"127.0.0.1:{self.сервер.server_port}"
        self.поток = threading.Thread(target=self.сервер.serve_forever,
                                      daemon=True)

    def __enter__(self):
        self.поток.start()
        return self

    def __exit__(self, *_):
        self.сервер.shutdown()
        self.сервер.server_close()
        return False


@pytest.mark.parametrize("код", [301, 302, 307, 308])
def test_заголовок_перенаправления_не_приписывается_странице(код):
    """Запрет на 3xx — запрет перенаправления, а не страницы.

    Дефект, из-за которого проверка появилась: на `http://yummyani.site/`
    стоит 308 на https с `X-Robots-Tag: noindex, nofollow`, а страница по
    адресу перехода отдаёт `index, follow` и разрешающий robots.txt. Замер
    брал заголовки самого 308 (в Python 3.10 он приходит как `HTTPError`) и
    объявлял домен ЗАКРЫТЫМ — обратное действительности.
    """
    with _Стенд(код, запрет_на_переходе=True, запрет_на_странице=False) as с:
        итог, значения, тело, цепочка = indexing._ответ_с_цепочкой(
            f"http://{с.адрес}/", таймаут=10)
    assert итог == "200", f"переход {код} не пройден: {итог}"
    assert значения == [], f"заголовок перенаправления приписан странице: {значения}"
    assert "страница" in тело
    # Цепочку записывает только НАШ проход: 301/302/307 `urlopen` проходит
    # сам, и для них она пуста. Важно не это, а что заголовок перехода не
    # попал в сигналы страницы.
    if цепочка:
        assert str(код) in цепочка[0], цепочка


@pytest.mark.parametrize("код", [301, 308])
def test_запрет_самой_страницы_не_теряется_за_перенаправлением(код):
    """Обратная сторона: после перехода запрет страницы обязан остаться."""
    with _Стенд(код, запрет_на_переходе=False, запрет_на_странице=True) as с:
        итог, значения, _, цепочка = indexing._ответ_с_цепочкой(
            f"http://{с.адрес}/", таймаут=10)
    assert итог == "200"
    assert значения == ["noindex, nofollow"], значения


def test_перенаправление_на_чужой_хост_не_проходится():
    """Чужая страница о индексации ЭТОГО домена ничего не говорит."""
    import http.server
    import threading

    class Рука(http.server.BaseHTTPRequestHandler):
        def log_message(self, *_):
            pass

        def do_GET(self):
            self.send_response(308)
            self.send_header("Location", "http://example.invalid/next")
            self.send_header("X-Robots-Tag", "noindex, nofollow")
            self.send_header("Content-Length", "0")
            self.end_headers()

    сервер = http.server.HTTPServer(("127.0.0.1", 0), Рука)
    поток = threading.Thread(target=сервер.serve_forever, daemon=True)
    поток.start()
    try:
        код, значения, _, цепочка = indexing._ответ_с_цепочкой(
            f"http://127.0.0.1:{сервер.server_port}/", таймаут=10)
    finally:
        сервер.shutdown()
        сервер.server_close()
    assert код == "308"
    assert значения == ["noindex, nofollow"], значения and "чужой хост" in цепочка[0]


def test_открытым_считается_только_сайт_без_единого_запрета():
    режим, запрещают = indexing.оценить(dict(ОТКРЫТЫЕ_СИГНАЛЫ))
    assert режим == indexing.ОТКРЫТ, запрещают
    assert запрещают == []


@pytest.mark.parametrize("поле,значение", [
    ("x_robots_values", ["index, follow", "noindex, nofollow"]),
    ("x_robots_values_http80", ["noindex, nofollow"]),
    ("meta_robots_home", "noindex, nofollow"),
    ("meta_robots_home", "не объявлен"),
    ("robots_txt", "User-agent: *\nDisallow: /\n"),
    ("robots_txt_http", "404"),
])
def test_один_запрещающий_сигнал_закрывает_сайт(поле, значение):
    """«Частично открыт» — не состояние. Один запрет делает остальные три
    сигнала бессмысленными, поэтому здесь это список причин, а не оттенок.
    """
    сиг = dict(ОТКРЫТЫЕ_СИГНАЛЫ)
    сиг[поле] = значение
    режим, запрещают = indexing.оценить(сиг)
    assert режим == indexing.ЗАКРЫТ
    assert запрещают, f"{поле}={значение!r} должен попасть в перечень причин"


def test_два_заголовка_на_443_оба_попадают_в_перечень():
    """Исправленная ошибка измерения: `dict(ответ.headers)` оставлял только
    ПОСЛЕДНЕЕ вхождение одноимённого заголовка. На :443 X-Robots-Tag добавляют
    и nginx, и приложение, и такой замер показал бы один «index, follow» и
    объявил бы открытым сайт, которому nginx всё ещё запрещает обход.
    """
    т = (КОРЕНЬ / "factory" / "qwen" / "indexing.py").read_text("utf-8")
    тело = т.split("def _ответ", 1)[1].split("\ndef сигналы", 1)[0]
    assert "get_all" in тело, "значения заголовка берутся перечнем"
    assert "dict(о.headers)" not in тело

    сиг = dict(ОТКРЫТЫЕ_СИГНАЛЫ)
    сиг["x_robots_values"] = ["index, follow", "noindex, nofollow"]
    режим, запрещают = indexing.оценить(сиг)
    assert режим == indexing.ЗАКРЫТ
    assert len([з for з in запрещают if з.startswith("X-Robots-Tag")]) == 1


def test_disallow_не_путается_с_частным_запретом():
    """`Disallow: /poster/` — служебный запрет, а не закрытие сайта."""
    сиг = dict(ОТКРЫТЫЕ_СИГНАЛЫ)
    сиг["robots_txt"] = ("User-agent: *\nDisallow: /poster/\n"
                         "Disallow: /api/\nAllow: /\n")
    режим, запрещают = indexing.оценить(сиг)
    assert режим == indexing.ОТКРЫТ, запрещают


def test_закрытый_robots_узнаётся_с_пробелами_и_в_любом_регистре():
    for тело in ("User-agent: *\nDisallow: /\n",
                 "User-agent: *\ndisallow: /\n",
                 "User-agent: *\nDisallow:   /   \n"):
        сиг = dict(ОТКРЫТЫЕ_СИГНАЛЫ)
        сиг["robots_txt"] = тело
        режим, _ = indexing.оценить(сиг)
        assert режим == indexing.ЗАКРЫТ, repr(тело)


# --- 3. Остановка при несовпадении версии ---------------------------------

def test_версия_сверяется_по_каталогу_выпуска_а_не_по_манифесту():
    """У animedia.space манифест объявляет source_commit efdef56e…, а выложен
    e84b4be48d86: сборщик манифест не пересчитывает. Сверяться с ним значило
    бы сверяться с устаревшей записью.
    """
    т = (КОРЕНЬ / "factory" / "qwen" / "indexing.py").read_text("utf-8")
    тело = т.split("def проверить", 1)[1].split("\ndef ", 1)[0]
    assert "s.published_release" in тело, (
        "сверяется имя каталога выпуска")
    # Манифест не читается НИГДЕ в модуле: его сборщик не пересчитывает.
    assert "template-manifest" not in т.replace(
        "template-manifest", "", 0) or 'json.loads' not in т.split(
        "template-manifest", 1)[0][-200:], "манифест как источник версии"
    assert "template-manifest.json" not in т, (
        "манифест не источник версии: сборщик его не пересчитывает")


def test_несовпадение_версии_останавливает_до_записи():
    т = (КОРЕНЬ / "factory" / "qwen" / "indexing.py").read_text("utf-8")
    тело = т.split("def проверить", 1)[1].split("\ndef ", 1)[0]
    assert "raise Отказано" in тело
    assert "до единой записи" in тело
    # Проверка стоит ДО всех остальных: отказ после них стоил бы работы и
    # назвал бы не ту причину.
    место_версии = тело.index("expect_release")
    место_записи = тело.index("current_state_file")
    assert место_версии < место_записи


def test_установить_вызывает_предпроверку_первой():
    т = (КОРЕНЬ / "factory" / "qwen" / "indexing.py").read_text("utf-8")
    тело = т.split("def установить", 1)[1].split("\ndef ", 1)[0]
    первая = тело.index("проверить(site")
    запись = тело.index("_записать(")
    assert первая < запись, "запись не может идти раньше предпроверки"
    assert 'if not пред["ok"]' in тело


# --- 4. Снимок, запись, повтор --------------------------------------------

def test_прежнее_состояние_сохраняется_до_записи():
    т = (КОРЕНЬ / "factory" / "qwen" / "indexing.py").read_text("utf-8")
    тело = т.split("def установить", 1)[1].split("\ndef ", 1)[0]
    снимок = тело.index("_снимок(")
    запись = тело.index("_записать(")
    assert снимок < запись, "снимок делается ДО изменения"
    тело_снимка = т.split("def _снимок", 1)[1].split("\ndef ", 1)[0]
    assert "before.json" in тело_снимка
    assert '"public"' in тело_снимка and '"state_file"' in тело_снимка


def test_повтор_в_том_же_режиме_не_пишет():
    """Иначе в журнале появлялась бы операция, которая ничего не изменила, а
    время файла сдвигалось бы впустую — и витрина перечитывала бы его зря.
    """
    т = (КОРЕНЬ / "factory" / "qwen" / "indexing.py").read_text("utf-8")
    тело = т.split("def установить", 1)[1].split("\ndef ", 1)[0]
    assert 'прежнее.get("desired_state") == режим' in тело
    assert '"changed": False' in тело
    assert "запись не велась" in тело


def test_запись_атомарна_и_не_оставляет_битого():
    т = (КОРЕНЬ / "factory" / "qwen" / "indexing.py").read_text("utf-8")
    тело = т.split("def _записать", 1)[1].split("\ndef ", 1)[0]
    assert "os.replace" in тело and "fsync" in тело
    assert "json.loads" in тело, "битое не оставляем"


def test_файл_состояния_не_выходит_за_корень():
    with pytest.raises(indexing.Отказано):
        indexing._файл("../чужое")


def test_запись_одного_домена_не_касается_другого():
    """Имя файла — сам домен, поэтому физически задеть соседа нечем."""
    assert indexing._файл("a.example").name == "a.example.json"
    assert indexing._файл("b.example").name == "b.example.json"
    т = (КОРЕНЬ / "factory" / "qwen" / "indexing.py").read_text("utf-8")
    тело = т.split("def установить", 1)[1].split("\ndef ", 1)[0]
    assert "_файл(s.domain" in тело


def test_ревизия_растёт_и_отпечаток_считается():
    т = (КОРЕНЬ / "factory" / "qwen" / "indexing.py").read_text("utf-8")
    тело = т.split("def установить", 1)[1].split("\ndef ", 1)[0]
    assert 'int(прежнее.get("revision") or 0) + 1' in тело
    # Сама запись состояния собирается отдельной функцией: ветка выбора
    # прикладного слоя (наш файл или реестр семейства) не должна решать, из
    # каких полей состоит запись. Отпечаток обязан считаться там.
    запись = т.split("def _запись_состояния", 1)[1].split("\ndef ", 1)[0]
    assert "policy_digest" in запись
    assert "_отпечаток(запись)" in запись


# --- 5. Итог считается по ответу ------------------------------------------

def test_итог_считается_по_публичному_ответу():
    """Успешная запись файла режимом сайта не является."""
    т = (КОРЕНЬ / "factory" / "qwen" / "indexing.py").read_text("utf-8")
    тело = т.split("def установить", 1)[1].split("\ndef ", 1)[0]
    assert "подтвердить(site" in тело, (
        "операция обязана заканчиваться проверкой публичного ответа")
    подтв = т.split("def подтвердить", 1)[1].split("\ndef ", 1)[0]
    assert "сигналы(" in подтв and "оценить(" in подтв
    assert '"confirmed"' in подтв


def test_подтверждение_ждёт_а_не_стреляет_один_раз():
    т = (КОРЕНЬ / "factory" / "qwen" / "indexing.py").read_text("utf-8")
    подтв = т.split("def подтвердить", 1)[1].split("\ndef ", 1)[0]
    assert "ОЖИДАНИЕ_С" in подтв and "ШАГ_С" in подтв
    assert "attempts" in подтв


def test_незакрытый_nginx_называется_в_причине():
    """Пока nginx отдаёт noindex, открытым сайт называть нельзя — и причина
    обязана говорить, что именно и ЧЕМ это исправляется.

    Прежде проверялось упоминание root-скрипта `apply-indexing-nginx-root.sh`.
    Это требование устарело вместе со скриптом: слой переводит под управление
    та же штатная заявка, и подсказка «попросите владельца запустить скрипт»
    отправляла бы редактора к человеку за действием, которое механизм делает
    сам. Теперь требуется, чтобы причина называла ОПЕРАЦИЮ.
    """
    т = (КОРЕНЬ / "factory" / "qwen" / "indexing.py").read_text("utf-8")
    assert "--cell-operation indexing-nginx" in т, (
        "причина не называет штатную операцию перевода слоя")
    assert "apply-indexing-nginx-root.sh" not in т, (
        "в причине снова root-скрипт: операция существует, и просить о нём "
        "владельца больше не нужно")
    подтв = т.split("def подтвердить", 1)[1].split("\ndef ", 1)[0]
    assert "nginx" in подтв


def test_скрипт_слоя_nginx_существует_и_точечный():
    с = КОРЕНЬ / "automation" / "host" / "apply-indexing-nginx-root.sh"
    assert с.is_file(), с
    т = с.read_text(encoding="utf-8")
    assert "nginx -t" in т and "nginx -s reload" in т
    assert "cp -p" in т, "резервная копия обязательна"
    # Полная перегенерация потеряла бы живые настройки, которых нет в заготовке.
    assert 'COUNT' in т and 'exit 3' in т, (
        "скрипт обязан отказываться, если ожидаемая строка не одна")
    assert "yandex_" in т, "маркер Вебмастера остаётся закрытым"
    # Кириллица в именах ОБОЛОЧЕЧНЫХ переменных проходит `bash -n` и падает
    # в работе. Внутри heredoc'ов со вставками на Python она законна, поэтому
    # эти блоки из проверки исключаются — иначе проверка запрещала бы
    # осмысленные имена в Python-фрагментах.
    только_оболочка = []
    внутри = False
    for строка in т.split("\n"):
        if "<<'PY'" in строка:
            внутри = True
            continue
        if внутри:
            if строка.strip() == "PY":
                внутри = False
            continue
        только_оболочка.append(строка)
    assert len(только_оболочка) < len(т.split("\n")), (
        "в скрипте нет ни одного Python-фрагмента — проверьте разбор")
    присваивание = re.compile(r"^\s*[A-Za-z_]*[А-Яа-яЁё][\w]*\s*=")
    подстановка = re.compile(r"\$\{?[A-Za-z_]*[А-Яа-яЁё]")
    for строка in только_оболочка:
        assert not присваивание.match(строка), строка
        assert not подстановка.search(строка), строка


# --- 6. Откат адресный ----------------------------------------------------

def test_откат_читает_журнал_и_возвращает_прежнее():
    т = (КОРЕНЬ / "factory" / "qwen" / "indexing.py").read_text("utf-8")
    тело = т.split("def откатить", 1)[1].split("\ndef ", 1)[0]
    assert "operations.jsonl" in тело
    assert 'з.get("site") == s.domain' in тело, "откат адресный"
    assert '"(нет файла)"' in тело, (
        "возврат к состоянию «файла не было» — тоже откат")


def test_журнал_и_снимки_имеют_путь():
    assert str(indexing.ЖУРНАЛ)
    т = (КОРЕНЬ / "factory" / "qwen" / "indexing.py").read_text("utf-8")
    assert "operations.jsonl" in т


# --- 7. Реестр: разрешение владельца описано ------------------------------

def test_новые_поля_реестра_объявлены_новыми():
    с = json.loads((КОРЕНЬ / "schemas" / "site-cells.schema.json")
                   .read_text(encoding="utf-8"))
    текст = json.dumps(с, ensure_ascii=False)
    assert "open_authorized" in текст
    assert "open_authorization_note" in текст
    assert "НОВОЕ поле 2026-10-01" in текст, (
        "новые поля должны быть названы новыми, а не выданы за существующие")


def test_разрешение_владельца_записано_для_двух_сайтов():
    д = json.loads((КОРЕНЬ / "config" / "site-cells.json").read_text("utf-8"))
    сп = д.get("cells") or д.get("sites") or []
    сп = сп if isinstance(сп, list) else list(сп.values())
    по_ид = {я.get("site_id"): я for я in сп}
    for site_id in ("animedia-01", "animedia-02"):
        инд = (по_ид[site_id].get("indexing") or {})
        assert инд.get("open_authorized") is True, site_id
        assert инд.get("open_authorization_note"), (
            f"{site_id}: разрешение без пояснения не проверить")
        # Разрешение не равно открытию: объявленный режим пока закрыт.
        assert инд.get("desired_state") == "CLOSED", (
            f"{site_id}: объявленный режим должен отражать факт, а не разрешение")


#: Объявления разрешения, сделанные ДО появления корневого подтверждения.
#: Это не исключение из правила, а честная запись состояния: флаг в реестре у
#: них есть, подтверждения владельца в каталоге root — нет, и поэтому фабрика
#: считает их НЕразрешёнными (`owner_authorized_open: false`). Ничего не
#: закрывается и не открывается само; чтобы разрешение стало действующим,
#: владелец выполняет `authorize-indexing.sh --domain <домен>`.
НАСЛЕДУЕМЫЕ_ОБЪЯВЛЕНИЯ = {"animedia-01", "animedia-02"}


def test_остальные_сайты_разрешения_не_получили():
    """Операция не должна открыть сайт, которого владелец не называл.

    Перечень разрешённых больше не вписан руками. Прежде он был равен
    {animedia-01, animedia-02}, и тест упал 2026-10-04, когда владелец
    разрешил lordserials22.info явной командой с подтверждением
    7eb319e0-2a7d-4647-a432-9dfa6d47326a. Падение было ложным: разрешение
    законное, а устарел список.

    Проверяется то, что и должно: КАЖДОЕ объявление в реестре либо опирается на
    корневое подтверждение владельца, либо названо здесь наследуемым. Флаг,
    появившийся сам по себе, тест ловит — а именно это и есть опасность, ведь
    файл реестра доступен на запись той же учётной записи, под которой работают
    инструменты.
    """
    from factory.cell import owner_consent

    д = json.loads((КОРЕНЬ / "config" / "site-cells.json").read_text("utf-8"))
    сп = д.get("cells") or д.get("sites") or []
    сп = сп if isinstance(сп, list) else list(сп.values())
    объявлено = {я.get("site_id"): я.get("domain") for я in сп
                 if (я.get("indexing") or {}).get("open_authorized") is True}
    без_подтверждения = sorted(
        site_id for site_id, домен in объявлено.items()
        if not owner_consent.сведения(домен or "").get("present")
        and site_id not in НАСЛЕДУЕМЫЕ_ОБЪЯВЛЕНИЯ)
    assert not без_подтверждения, (
        "в реестре объявлено разрешение без корневого подтверждения владельца: "
        f"{без_подтверждения}. Флаг разрешением не считается")


# --- 8. Витрина: читатель и его строгость ---------------------------------

@pytest.mark.parametrize("репо", ["animedia-space", "animedia-icu"])
def test_читатель_витрины_fail_closed(репо):
    п = КОРЕНЬ / "var" / "site-repos" / репо / "src" / "indexing_mode.py"
    if not п.is_file():
        pytest.skip(f"{репо}: рабочая копия недоступна")
    т = п.read_text(encoding="utf-8")
    assert "разрешено_выпуском is not True" in т, (
        "разрешением считается только булево true")
    assert 'состояние == ОТКРЫТ' in т
    # Никакой ветки, которая открывала бы по умолчанию.
    тело = т.split("def решить", 1)[1].split("\ndef ", 1)[0]
    открытия = re.findall(r"return ОТКРЫТ", тело)
    assert len(открытия) == 1, (
        f"открытие должно возвращаться из одного места, найдено {len(открытия)}")


@pytest.mark.parametrize("репо", ["animedia-space", "animedia-icu"])
def test_в_рантайме_не_осталось_буквального_запрета_страниц(репо):
    """КАЖДЫЙ `<meta name="robots">` и заголовок обычной отдачи обязаны быть
    ВЫЧИСЛЯЕМЫМИ. Исключение одно: `/poster/` — картинки витрины, их запрет
    намеренный и от режима не зависит.

    Проверяется ИНВАРИАНТ, а не написание вызова. Прежняя версия требовала
    ровно два вхождения строки `content="{мета_роботов()}"` — то есть
    закрепляла не «значение вычисляется», а «вызов без аргументов». Измерено
    2026-10-05: соседняя сессия добавила второму месту аргумент
    (`мета_роботов(getattr(self, "вне_подборок", False))` — записи вне
    подборок получают свой режим с названной причиной), значение осталось
    вычисляемым, а проверка упала. Такой отказ ничего не защищает: он ловит
    правку формы вместо подмены значения на буквальный запрет.

    Поэтому: буквального `noindex` в мете нет НИ ОДНОГО, вычисляемых мет не
    меньше двух, и каждая мета робота — вычисляемая. Третья зашитая мета
    теперь тоже ловится, чего прежняя проверка не умела.
    """
    import re as _re

    п = (КОРЕНЬ / "var" / "site-repos" / репо / "src" / "animedia-frontend.py")
    if not п.is_file():
        pytest.skip(f"{репо}: рабочая копия недоступна")
    т = п.read_text(encoding="utf-8")
    assert '<meta name="robots" content="noindex, nofollow">' not in т
    меты = _re.findall(r'<meta name="robots" content="([^"]*)"', т)
    assert len(меты) >= 2, f"мет робота найдено {len(меты)}: {меты}"
    зашитые = [м for м in меты if "мета_роботов(" not in м]
    assert not зашитые, (
        f"{репо}: значение меты робота не вычисляется: {зашитые}. Режим "
        "индексации такой страницы не переключается ничем")
    # Заголовок обычной отдачи — тоже по ИНВАРИАНТУ: значение вычисляется.
    # Аргументы вызова проверке не принадлежат: страница вне тематического
    # допуска получает свой режим, и это решение витрины, а не режима домена.
    заголовки = _re.findall(r'send_header\("X-Robots-Tag", ([^\n]*?)\)\n', т)
    вычисляемые = [з for з in заголовки if "мета_роботов(" in з]
    assert вычисляемые, (
        f"{репо}: ни одна отдача X-Robots-Tag не вычисляется: {заголовки}")
    # Остаться должен ровно один буквальный — у постеров.
    остаток = т.count('self.send_header("X-Robots-Tag", "noindex, nofollow")')
    assert остаток == 1, f"буквальных запретов осталось {остаток}"
    место = т.index('self.send_header("X-Robots-Tag", "noindex, nofollow")')
    assert "/poster/" in т[место - 800:место], (
        "единственный буквальный запрет должен относиться к постерам")


@pytest.mark.parametrize("репо", ["animedia-space", "animedia-icu"])
def test_проверки_режима_подключены_в_прогон(репо):
    п = КОРЕНЬ / "var" / "site-repos" / репо / "checks" / "run.sh"
    if not п.is_file():
        pytest.skip(f"{репо}: рабочая копия недоступна")
    т = п.read_text(encoding="utf-8")
    assert "indexing_mode_rules.py" in т
    assert "indexing_live_switch.py" in т


@pytest.mark.parametrize("репо", ["animedia-space", "animedia-icu"])
def test_выпуск_разрешает_открытие_этих_двух_сайтов(репо):
    п = КОРЕНЬ / "var" / "site-repos" / репо / "config" / "site.json"
    if not п.is_file():
        pytest.skip(f"{репо}: рабочая копия недоступна")
    д = json.loads(п.read_text(encoding="utf-8"))
    assert (д.get("indexing") or {}).get("release_permits_open") is True
    assert "indexing_enabled" not in д, (
        "старое поле никто не читал; два поля об одном разошлись бы")


# --- 9. Операции есть в CLI -----------------------------------------------

def test_операции_режима_есть_в_cli():
    т = (КОРЕНЬ / "factory" / "qwen" / "__main__.py").read_text("utf-8")
    фрагмент = т.split('"операция", choices=[', 1)[1].split("])", 1)[0]
    команды = set(re.findall(r'"([a-z-]+)"', фрагмент))
    for оп in ("indexing-state", "indexing-set", "indexing-confirm",
               "indexing-rollback"):
        assert оп in команды, оп
    assert "--mode" in т and "--expect-release" in т


def test_код_возврата_различает_подтверждённое_и_записанное():
    т = (КОРЕНЬ / "factory" / "qwen" / "__main__.py").read_text("utf-8")
    тело = т.split('if args.операция == "indexing-set"', 1)[1][:600]
    assert 'итог.get("confirmed")' in тело
    assert "return 0 if" in тело and "else 3" in тело


# --- 10. Слой nginx определяется по конфигурации, а не по числу заголовков --

ФИКС = 'add_header X-Robots-Tag "noindex, nofollow" always;'
ПЕРЕМ = "add_header X-Robots-Tag $cell_robots_test_01 always;"


def _конфиг(tmp_path, строки: str, *, include: str | None = None) -> pathlib.Path:
    корень = tmp_path / "nginx"
    (корень / "lords").mkdir(parents=True)
    (корень / "cells").mkdir(parents=True)
    вкл = корень / "cells" / "test-01.robots"
    if include is not None:
        вкл.write_text(include, encoding="utf-8")
    конф = корень / "lords" / "test-01.conf"
    конф.write_text(строки.replace("@@INCLUDE@@", str(вкл)), encoding="utf-8")
    return корень


@pytest.fixture
def nginx_корень(monkeypatch):
    """Подменить корень конфигураций nginx.

    Подменяется ИСТОЧНИК — модуль `factory.cell.nginx_indexing`, где разбор и
    живёт. Подмена имени, повторно экспортированного инструментом, ничего не
    меняла бы: функции читают глобальную величину своего модуля.
    """
    from factory.cell import nginx_indexing

    def поставить(корень: pathlib.Path):
        monkeypatch.setattr(nginx_indexing, "КОРЕНЬ_NGINX", корень)
        monkeypatch.setattr(indexing, "КОРЕНЬ_NGINX", корень, raising=False)
    return поставить


def test_слой_nginx_закрыт_при_фиксированной_строке(tmp_path, nginx_корень):
    корень = _конфиг(tmp_path, f"server {{\n    {ФИКС}\n}}\n")
    nginx_корень(корень)
    сл = indexing.слой_nginx("test-01", "t.example")
    assert сл["mode"] == "closed" and сл["denying"] is True
    assert "noindex" in сл["evidence"]


def test_слой_nginx_открыт_при_пустом_default(tmp_path, nginx_корень):
    """Именно этот случай операция и показывала неверно: nginx уже открыт,
    а `denying` оставался true, потому что считался по любому заголовку.
    """
    корень = _конфиг(
        tmp_path,
        "map $uri $cell_robots_test_01 {\n    include @@INCLUDE@@;\n}\n"
        f"server {{\n    {ПЕРЕМ}\n}}\n",
        include='default "";\n"~^/healthz$" "noindex, nofollow";\n')
    nginx_корень(корень)
    сл = indexing.слой_nginx("test-01", "t.example")
    assert сл["mode"] == "open" and сл["denying"] is False
    assert "default пуст" in сл["evidence"]


def test_слой_nginx_закрыт_при_noindex_в_default(tmp_path, nginx_корень):
    корень = _конфиг(
        tmp_path,
        "map $uri $cell_robots_test_01 {\n    include @@INCLUDE@@;\n}\n"
        f"server {{\n    {ПЕРЕМ}\n}}\n",
        include='default "noindex, nofollow";\n')
    nginx_корень(корень)
    сл = indexing.слой_nginx("test-01", "t.example")
    assert сл["mode"] == "closed" and сл["denying"] is True
    assert "noindex" in сл["evidence"]


def test_слой_nginx_открыт_без_add_header(tmp_path, nginx_корень):
    корень = _конфиг(tmp_path, "server {\n    listen 80;\n}\n")
    nginx_корень(корень)
    сл = indexing.слой_nginx("test-01", "t.example")
    assert сл["mode"] == "open" and сл["denying"] is False
    assert "add_header X-Robots-Tag нет" in сл["evidence"]


def test_слой_nginx_неизвестен_без_конфигурации(tmp_path, nginx_корень):
    """Неизвестно — это не «открыто». Отсутствие конфигурации не разрешает."""
    nginx_корень(tmp_path / "пусто")
    сл = indexing.слой_nginx("test-01", "t.example")
    assert сл["mode"] == "unknown" and сл["denying"] is None
    assert "не найдено" in сл["evidence"]


def test_слой_nginx_неизвестен_при_нечитаемом_include(tmp_path, nginx_корень):
    корень = _конфиг(
        tmp_path,
        "map $uri $cell_robots_test_01 {\n    include /нет/такого/файла.robots;\n}\n"
        f"server {{\n    {ПЕРЕМ}\n}}\n")
    nginx_корень(корень)
    сл = indexing.слой_nginx("test-01", "t.example")
    assert сл["denying"] is None, сл
    assert сл["mode"] == "unknown"


def test_один_заголовок_не_приписывается_nginx(tmp_path, nginx_корень):
    """ПРИЧИНА расхождения, из-за которого передача Qwen была заблокирована.

    Владелец снял запрет в nginx: заголовков в публичном ответе стало один
    вместо двух, exit 0. А `indexing-state` продолжал показывать
    `nginx_header.denying: true`, потому что прежнее правило считало слой
    nginx закрытым при ЛЮБОМ запрещающем `X-Robots-Tag` — и видело заголовок
    ПРИЛОЖЕНИЯ, закрытого штатно (файла состояния нет, fail-closed).
    """
    корень = _конфиг(
        tmp_path,
        "map $uri $cell_robots_test_01 {\n    include @@INCLUDE@@;\n}\n"
        f"server {{\n    {ПЕРЕМ}\n}}\n",
        include='default "";\n')
    nginx_корень(корень)
    сиг = {
        "x_robots_values": ["noindex, nofollow"],          # один, от приложения
        "x_robots_count": 1,
        "x_robots_values_http80": ["noindex, nofollow"],
        "x_robots_count_service": 2,                        # nginx добавляет служебным
        "meta_robots_home": "noindex, nofollow",
        "robots_txt": "User-agent: *\nDisallow: /\n",
        "robots_txt_http": "200",
        "sitemap_http": "404",
    }
    сл = indexing.слой_nginx("test-01", "t.example", сиг)
    assert сл["denying"] is False, "слой nginx открыт — запрет не его"
    assert сл["cross_check"]["agrees_with_config"] is True

    пр = indexing.слой_приложения(сиг)
    assert пр["denying"] is True, "запреты приложения обязаны остаться видны"

    # И публичный итог остаётся закрытым: приложение запрещает.
    режим, запрещают = indexing.оценить(сиг)
    assert режим == indexing.ЗАКРЫТ
    assert len(запрещают) >= 3, запрещают


def test_перекрёстная_сверка_ловит_расхождение(tmp_path, nginx_корень):
    """Конфигурация говорит «открыт», а ответ не отличает служебный путь —
    такое расхождение не прячется.
    """
    корень = _конфиг(
        tmp_path,
        "map $uri $cell_robots_test_01 {\n    include @@INCLUDE@@;\n}\n"
        f"server {{\n    {ПЕРЕМ}\n}}\n",
        include='default "";\n')
    nginx_корень(корень)
    сиг = {"x_robots_count": 1, "x_robots_count_service": 1,
           "x_robots_values_http80": [], "meta_robots_home": "index, follow",
           "robots_txt": "User-agent: *\nAllow: /\n", "robots_txt_http": "200"}
    сл = indexing.слой_nginx("test-01", "t.example", сиг)
    assert сл["mode"] == "open"
    assert сл["cross_check"]["agrees_with_config"] is False


def test_запрет_в_блоке_перенаправления_не_закрывает_домен(tmp_path, nginx_корень):
    """Дефект yummyani.site: `add_header noindex` стоит в блоках :80 и `www`,
    оба только перенаправляют, а канонический блок :443 заголовка не несёт.
    Операция искала строку по всему файлу и называла домен ЗАКРЫТЫМ, тогда как
    публичный ответ открыт.
    """
    корень = tmp_path / "nginx"
    # Стенд ставится в ЗАГРУЖАЕМЫЙ каталог: `sites-available` nginx не
    # включает, и с 2026-10-05 операция его «живым» не считает (D170). Смысл
    # этой проверки — блоки перенаправления против канонического, а не
    # каталог, поэтому меняется только место файла.
    (корень / "sites-enabled").mkdir(parents=True)
    (корень / "sites-enabled" / "t.example.conf").write_text(
        'server {\n'
        '    listen 80;\n'
        '    server_name t.example www.t.example;\n'
        '    add_header X-Robots-Tag "noindex, nofollow" always;\n'
        '    location ^~ /.well-known/acme-challenge/ { root /var/www/certbot; }\n'
        '    location / { return 308 https://t.example$request_uri; }\n'
        '}\n'
        'server {\n'
        '    listen 443 ssl;\n'
        '    server_name www.t.example;\n'
        '    add_header X-Robots-Tag "noindex, nofollow" always;\n'
        '    location / { return 308 https://t.example$request_uri; }\n'
        '}\n'
        'server {\n'
        '    listen 443 ssl;\n'
        '    server_name t.example;\n'
        '    location / { proxy_pass http://127.0.0.1:9999; }\n'
        '}\n', encoding="utf-8")
    nginx_корень(корень)
    сл = indexing.слой_nginx("test-01", "t.example")
    assert сл["mode"] == "open", сл
    assert сл["denying"] is False
    assert сл["add_header_lines"] == [], сл["add_header_lines"]
    # Строки не замолчаны: сказано, что они в блоках-перенаправлениях.
    assert сл["add_header_in_redirect_blocks"] == 2, сл
    assert "перехода" in сл["evidence"]


def test_блок_443_в_отдельном_файле_учитывается(tmp_path, nginx_корень):
    """У lords-05 блок :80 лежит в `lords-05.conf`, а блок :443 — отдельным
    файлом `lords-05-tls.conf`. Судить о слое по одному файлу значит судить по
    тому, чего краулер не видит.
    """
    корень = tmp_path / "nginx"
    (корень / "lords").mkdir(parents=True)
    (корень / "lords" / "test-01.conf").write_text(
        'server {\n    listen 80;\n    server_name t.example;\n'
        '    location / { proxy_pass http://127.0.0.1:9999; }\n}\n',
        encoding="utf-8")
    (корень / "lords" / "test-01-tls.conf").write_text(
        'server {\n    listen 443 ssl;\n    server_name t.example;\n'
        '    add_header X-Robots-Tag "noindex, nofollow" always;\n'
        '    location / { proxy_pass http://127.0.0.1:9999; }\n}\n',
        encoding="utf-8")
    nginx_корень(корень)
    сл = indexing.слой_nginx("test-01", "t.example")
    assert сл["mode"] == "closed" and сл["denying"] is True, сл
    assert any("test-01-tls.conf" in ф for ф in сл["configs"]), сл["configs"]


def test_нечитаемая_конфигурация_не_объявляет_слой_открытым(tmp_path, nginx_корень):
    """Нечитаемый файл — не «запрета нет». Открытым слой называется только при
    согласии измерения: надбавки nginx к заголовкам приложения нет.
    """
    import os
    корень = tmp_path / "nginx"
    (корень / "lords").mkdir(parents=True)
    (корень / "lords" / "test-01.conf").write_text(
        'server {\n    listen 443 ssl;\n    server_name t.example;\n'
        '    location / { proxy_pass http://127.0.0.1:9999; }\n}\n',
        encoding="utf-8")
    закрытый = корень / "lords" / "test-01-extra.conf"
    закрытый.write_text("server { server_name t.example; }\n", encoding="utf-8")
    os.chmod(закрытый, 0o000)
    nginx_корень(корень)
    try:
        # Без измерения — не «открыт».
        сл = indexing.слой_nginx("test-01", "t.example")
        assert сл["mode"] == "unknown" and сл["denying"] is None, сл
        assert "не читается" in сл["evidence"]
        # С измерением, где надбавки нет — открыт, и это сказано.
        сл = indexing.слой_nginx("test-01", "t.example", {
            "x_robots_count": 1, "x_robots_count_service": 2,
            "x_robots_values_app": ["index, follow"],
            "meta_robots_home": "index, follow"})
        assert сл["mode"] == "open" and сл["denying"] is False, сл
        assert сл["cross_check"]["nginx_extra_headers"] == 0
        # С измерением, где надбавка есть — не «открыт».
        сл = indexing.слой_nginx("test-01", "t.example", {
            "x_robots_count": 2, "x_robots_count_service": 2,
            "x_robots_values_app": ["noindex, nofollow"],
            "meta_robots_home": "noindex, nofollow"})
        assert сл["mode"] == "unknown" and сл["denying"] is None, сл
    finally:
        os.chmod(закрытый, 0o644)


def test_объявление_map_в_другом_файле_домена_разрешается(tmp_path, nginx_корень):
    """Объявление `map` живёт в ОДНОМ файле домена, заголовок — в обоих.

    После того как объявление стали ставить ровно в один файл (иначе
    `nginx: [emerg] duplicate variable`), поиск «в своём файле» объявлял
    второй файл неразрешимым, и слой целиком становился `unknown` — то есть
    исправно открытый слой нельзя было бы подтвердить.
    """
    корень = tmp_path / "nginx"
    (корень / "lords").mkdir(parents=True)
    (корень / "cells").mkdir(parents=True)
    включаемый = корень / "cells" / "test-01.robots"
    включаемый.write_text('default "";\n', encoding="utf-8")
    # Файл с объявлением map И заголовком.
    (корень / "lords" / "test-01-tls.conf").write_text(
        f"map $uri $cell_robots_test_01 {{\n    include {включаемый};\n}}\n"
        "server {\n    listen 443 ssl;\n    server_name t.example;\n"
        "    add_header X-Robots-Tag $cell_robots_test_01 always;\n"
        "    location / { proxy_pass http://127.0.0.1:9999; }\n}\n",
        encoding="utf-8")
    # Файл ТОЛЬКО с заголовком: объявления здесь нет и быть не должно.
    (корень / "lords" / "test-01.conf").write_text(
        "server {\n    listen 80;\n    server_name t.example;\n"
        "    add_header X-Robots-Tag $cell_robots_test_01 always;\n"
        "    location / { proxy_pass http://127.0.0.1:9999; }\n}\n",
        encoding="utf-8")
    nginx_корень(корень)
    сл = indexing.слой_nginx("test-01", "t.example")
    assert сл["mode"] == "open", сл
    assert сл["denying"] is False, сл
    assert сл["managed_by_this_operation"] is True
    assert "объявления map" not in сл["evidence"], сл["evidence"]


def test_прежнее_правило_не_вернулось():
    """Слой nginx не определяется перебором публичных заголовков."""
    т = (КОРЕНЬ / "factory" / "qwen" / "indexing.py").read_text("utf-8")
    assert 'з.startswith("X-Robots-Tag") for з in запрещают' not in т, (
        "возврат к определению слоя по перечню запрещающих сигналов")
    тело = т.split("def слой_nginx", 1)[1].split("\ndef ", 1)[0]
    assert "конфиги_сайта" in тело, "источник — конфигурации сайта"
    assert "запрещают" not in тело, (
        "перечень публичных запретов не должен участвовать в определении слоя")
    # И второе прежнее правило: строка искалась по ВСЕМУ файлу, из-за чего
    # закрытыми объявлялись домены, у которых она стоит только в
    # блоке-перенаправлении.
    assert "серверные_блоки" in тело or "отдающие" in тело, (
        "строки заголовка обязаны браться из блоков, отдающих страницы")


def test_вклад_приложения_измеряется_на_80(tmp_path):
    """На :80 серверный блок сайта заголовка не добавляет — там виден ровно
    вклад приложения. Больше одного заголовка там означает, что приписывать
    его приложению нельзя.
    """
    пр = indexing.слой_приложения({"x_robots_values_http80": ["index, follow"],
                                   "meta_robots_home": "index, follow",
                                   "robots_txt": "User-agent: *\nAllow: /\n"})
    assert пр["denying"] is False and "note" not in пр
    пр2 = indexing.слой_приложения({
        "x_robots_values_http80": ["index, follow", "noindex, nofollow"],
        "meta_robots_home": "index, follow",
        "robots_txt": "User-agent: *\nAllow: /\n"})
    assert пр2["denying"] is True
    assert "note" in пр2 and "кто-то ещё" in пр2["note"]


def test_состояние_разделяет_слои():
    """В ответе `indexing-state` слои стоят отдельными полями: иначе «почему
    закрыт» пришлось бы угадывать.
    """
    т = (КОРЕНЬ / "factory" / "qwen" / "indexing.py").read_text("utf-8")
    тело = т.split("def состояние", 1)[1]
    assert '"nginx_header": слой_nginx(' in тело
    assert '"app": слой_приложения(' in тело


def test_причина_отказа_называет_слой():
    т = (КОРЕНЬ / "factory" / "qwen" / "indexing.py").read_text("utf-8")
    тело = т.split("def подтвердить", 1)[1].split("\ndef ", 1)[0]
    assert "слой nginx открыт" in тело, (
        "когда nginx открыт, причина обязана говорить это, а не предлагать "
        "снимать уже снятый запрет")
    assert "запрет добавляет nginx" in тело
    assert "fail-closed" in тело


# --- 11. Карта сайта подключена к обработчику обновления ------------------

def test_sitemap_404_не_считается_запретом():
    """404 на карте — не запрет индексации. Карта и режим — разные вещи, и
    смешивать их значило бы объявлять сайт закрытым из-за отсутствия карты.
    """
    сиг = dict(ОТКРЫТЫЕ_СИГНАЛЫ)
    сиг["sitemap_http"] = "404"
    режим, запрещают = indexing.оценить(сиг)
    assert режим == indexing.ОТКРЫТ, запрещают


@pytest.mark.parametrize("репо", ["animedia-space", "animedia-icu"])
def test_карта_собирается_штатным_обработчиком(репо):
    """РАНЬШЕ здесь закреплялось обратное: «сборка карты нигде не вызывается».
    Это была честная запись факта — генератор `seo_layer.построить_sitemap`
    существовал и не вызывался ниоткуда, а `LORDS_SITEMAP_DIR` не задавался,
    поэтому `/sitemap.xml` отвечал 404 в обоих режимах.

    Теперь карта собирается шагом `sitemap` обработчика обновления данных —
    того самого, который ходит по таймеру каждые десять минут и переносит
    снимок каталога. Ожидание перевёрнуто осознанно, а не подогнано: если
    вызов снова исчезнет, этот тест упадёт.
    """
    репо_путь = КОРЕНЬ / "var" / "site-repos" / репо
    if not репо_путь.is_dir():
        pytest.skip(f"{репо}: рабочая копия недоступна")
    обработчики = sorted((репо_путь / "automation").glob("*update*.py"))
    assert обработчики, f"{репо}: обработчика обновления нет"
    тексты = {п.name: п.read_text(encoding="utf-8") for п in обработчики}
    с_шагом = [имя for имя, т in тексты.items() if "def шаг_карты" in т]
    assert с_шагом, f"{репо}: шага карты нет ни в одном обработчике: {list(тексты)}"
    т = тексты[с_шагом[0]]
    assert "построить_sitemap(" in т, "генератор должен вызываться"
    assert '"sitemap"' in т, "шаг обязан быть в перечне шагов прогона"
    # Шаг идёт ПОСЛЕ доставки: карта по промежуточному состоянию описывала бы
    # страницы, которых витрина ещё не отдаёт.
    место_карты = т.index('("sitemap", lambda')
    место_каталога = т.index('"catalog" in шаги')
    assert место_каталога < место_карты


@pytest.mark.parametrize("репо", ["animedia-space", "animedia-icu"])
def test_каталог_карты_один_у_обеих_сторон(репо):
    """Обработчик пишет карту туда же, откуда витрина её отдаёт.

    Два правила вывода пути разошлись бы, и карта писалась бы в одно место, а
    искалась в другом. Путь внутри каталога ДАННЫХ, а не выпуска: юнит
    обновления объявляет `ReadWritePaths=/srv/<аккаунт>/data`, и карта обязана
    переживать смену выпуска.
    """
    репо_путь = КОРЕНЬ / "var" / "site-repos" / репо
    if not репо_путь.is_dir():
        pytest.skip(f"{репо}: рабочая копия недоступна")
    запуск = (репо_путь / "run.py").read_text(encoding="utf-8")
    assert 'LORDS_SITEMAP_DIR' in запуск, (
        "переменная каталога карты не задаётся — ровно из-за этого карта и "
        "отвечала 404")
    assert '"sitemap"' in запуск
    обработчик = next(п for п in sorted((репо_путь / "automation").glob("*update*.py"))
                      if "def шаг_карты" in п.read_text(encoding="utf-8"))
    т = обработчик.read_text(encoding="utf-8")
    assert 'ПОДКАТАЛОГ_КАРТЫ = "sitemap"' in т
    assert "данные / ПОДКАТАЛОГ_КАРТЫ" in т


@pytest.mark.parametrize("репо", ["animedia-space", "animedia-icu"])
def test_в_карту_не_попадают_чужие_и_служебные_адреса(репо):
    """Адрес собирается из ДОМЕНА этого сайта, а не берётся из данных —
    чужой домен невозможен по построению. Служебные пути, страницы серий и
    фасеты исключены осознанно, и причина у каждого записана.
    """
    репо_путь = КОРЕНЬ / "var" / "site-repos" / репо
    if not репо_путь.is_dir():
        pytest.skip(f"{репо}: рабочая копия недоступна")
    слой = (репо_путь / "src" / "seo_layer.py").read_text(encoding="utf-8")
    тело = слой.split("def построить_sitemap", 1)[1].split("\ndef ", 1)[0]
    assert 'f"https://{хост}' in тело, "адрес собирается из переданного хоста"
    assert "видели" in тело, "дубли убираются"
    обработчик = next(п for п in sorted((репо_путь / "automation").glob("*update*.py"))
                      if "def шаг_карты" in п.read_text(encoding="utf-8"))
    т = обработчик.read_text(encoding="utf-8")
    assert "РАЗДЕЛЫ_КАРТЫ" in т
    for причина in ("страницы серий", "фасеты", "служебные", "SLUG_ALIASES"):
        assert причина in т, f"не записана причина исключения: {причина}"
    # Исторические слаги читаются из рантайма, а не дублируются списком.
    assert "_исторические_слаги" in т
    assert "SLUG_ALIASES" in т


@pytest.mark.parametrize("репо", ["animedia-space", "animedia-icu"])
def test_lastmod_только_по_достоверному_времени(репо):
    """Источник один и он назван: `first_seen_at` события о серии с объявленной
    семантикой `appeared_on_site`. Подставленное «сегодня» сообщало бы
    поисковику, что весь каталог обновился сегодня, и обесценивало бы поле у
    всех страниц сразу.
    """
    репо_путь = КОРЕНЬ / "var" / "site-repos" / репо
    if not репо_путь.is_dir():
        pytest.skip(f"{репо}: рабочая копия недоступна")
    обработчик = next(п for п in sorted((репо_путь / "automation").glob("*update*.py"))
                      if "def шаг_карты" in п.read_text(encoding="utf-8"))
    т = обработчик.read_text(encoding="utf-8")
    тело = т.split("def _время_изменения", 1)[1].split("\ndef ", 1)[0]
    assert "first_seen_at" in тело
    assert "appeared_on_site" in тело, "семантика отметки проверяется"
    слой = (репо_путь / "src" / "seo_layer.py").read_text(encoding="utf-8")
    assert "if lastmod:" in слой, "пустой lastmod в XML не пишется"


@pytest.mark.parametrize("репо", ["animedia-space", "animedia-icu"])
def test_карта_не_отдаётся_в_закрытом_режиме(репо):
    """Карта — приглашение обойти страницы. У закрытой витрины в `robots.txt`
    стоит `Disallow: /`, и отдавать рядом перечень адресов значило бы
    противоречить самому себе. Оба сигнала переключаются вместе.
    """
    п = КОРЕНЬ / "var" / "site-repos" / репо / "src" / "animedia-frontend.py"
    if not п.is_file():
        pytest.skip(f"{репо}: рабочая копия недоступна")
    т = п.read_text(encoding="utf-8")
    маршрут = т.split('if путь == "/sitemap.xml"', 1)[1][:900]
    assert 'режим_индексации()[0] != "OPEN"' in маршрут, (
        "карта обязана отдаваться только в открытом режиме")
    # А строка Sitemap в robots.txt — только при существующем файле.
    робots = т.split("def _тело_robots", 1)[1].split("\ndef ", 1)[0]
    assert "SITEMAP_DIR" in робots and "is_file()" in робots


@pytest.mark.parametrize("репо", ["animedia-space", "animedia-icu"])
def test_проверка_карты_подключена_в_прогон(репо):
    """Исправление обязано сохраняться при последующих выпусках: проверка
    стоит в прогоне перед выпуском, а не рядом с ним.
    """
    п = КОРЕНЬ / "var" / "site-repos" / репо / "checks" / "run.sh"
    if not п.is_file():
        pytest.skip(f"{репо}: рабочая копия недоступна")
    assert "sitemap_live.py" in п.read_text(encoding="utf-8")
    проверка = КОРЕНЬ / "var" / "site-repos" / репо / "checks" / "sitemap_live.py"
    assert проверка.is_file(), проверка
    т = проверка.read_text(encoding="utf-8")
    # Проверка обязана мерить ОТДАЧУ, а не наличие файлов.
    for что in ("/sitemap.xml", "canonical", "robots.txt", "Sitemap:",
                "publisher-id", "обновлено"):
        assert что in т, f"проверка не измеряет {что}"


def test_карта_пишется_правами_для_чтения_витриной():
    """`mkstemp` создаёт 0600. Карту ПИШЕТ обработчик, а ОТДАЁТ витрина, и
    одной службы под другой учётной записью достаточно, чтобы карта стала
    нечитаемой — а выглядело бы это как отсутствующая карта.
    """
    for репо in ("animedia-space", "animedia-icu"):
        п = КОРЕНЬ / "var" / "site-repos" / репо / "src" / "seo_layer.py"
        if not п.is_file():
            continue
        тело = п.read_text(encoding="utf-8").split(
            "def записать_атомарно", 1)[1].split("\ndef ", 1)[0]
        assert "os.chmod(врем, 0o644)" in тело, репо

# --------------------------------------------- вердикт готовности (7 статусов)

def test_статусы_готовности_закрытый_словарь():
    """Статус — из перечня, и у каждого есть следующее допустимое действие."""
    assert indexing.СТАТУСЫ == (
        "ENV_UNAVAILABLE", "DOMAIN_UNKNOWN", "MECHANISM_UNSUPPORTED",
        "MECHANISM_UNPROVEN", "AWAITING_OWNER", "CHECKS_FAILED",
        "OPEN_CONFIRMED")
    assert set(indexing.ДАЛЬШЕ) == set(indexing.СТАТУСЫ), (
        "у каждого статуса обязано быть названо следующее действие")
    for статус, действие in indexing.ДАЛЬШЕ.items():
        assert действие and len(действие) > 20, статус


def test_нечитаемый_реестр_не_отвечает_пустым_успехом(monkeypatch, tmp_path):
    """Беда окружения — ENV_UNAVAILABLE, а не «домена нет» и не пустой успех.

    Прежде нечитаемый сетевой список молча давал пустой перечень, и отказ
    доступа читался как вывод о сайте.
    """
    from factory.qwen import registry as реестр

    monkeypatch.setattr(реестр, "РЕЕСТР_ЯЧЕЕК", tmp_path / "нет.json")
    итог = indexing.готовность("lordserials22.info", доказать=False)
    assert итог["status"] == "ENV_UNAVAILABLE", итог["status"]
    assert итог["ok"] is False
    assert "не читается" in итог["reason"]
    # Источник назван: путь и ошибка, а не «пусто».
    assert итог["registry"]["site_cells"]["ok"] is False
    assert итог["registry"]["site_cells"]["error"]
    assert str(tmp_path / "нет.json") == итог["registry"]["site_cells"]["path"]


def test_пустой_реестр_это_тоже_беда_окружения(monkeypatch, tmp_path):
    """Реестр без ячеек — состояние окружения, а не «ни одного сайта»."""
    from factory.qwen import registry as реестр

    пустой = tmp_path / "пусто.json"
    пустой.write_text('{"cells": []}', encoding="utf-8")
    monkeypatch.setattr(реестр, "РЕЕСТР_ЯЧЕЕК", пустой)
    итог = indexing.готовность("любой.example", доказать=False)
    assert итог["status"] == "ENV_UNAVAILABLE", итог
    assert "ни одной ячейки" in итог["reason"]


def test_домена_нет_в_реестре_не_вывод_о_механизме():
    итог = indexing.готовность("нет-такого-домена.example", доказать=False)
    assert итог["status"] == "DOMAIN_UNKNOWN"
    assert "не вывод о механизме" in итог["reason"]
    # Источник назван всегда: по вердикту видно, какой файл читался.
    assert итог["registry"]["site_cells"]["path"].endswith("site-cells.json")


def test_вердикт_всегда_называет_версию_инструкции_и_выпуск():
    итог = indexing.готовность("lordserials22.info", доказать=False)
    from factory.qwen import __main__ as точка
    assert итог["instruction_version"] == точка.ВЕРСИЯ_ИНСТРУКЦИИ
    assert итог["instruction"] == точка.ИНСТРУКЦИЯ
    assert итог["published_release"], "выпуск обязан быть назван"
    assert итог["statuses_known"] == list(indexing.СТАТУСЫ)


def test_пустой_читатель_не_означает_отсутствия_механизма():
    """У zona-serve рантайм — закреплённый артефакт, читателя подключает
    отдельная правка витрины. Пустое поле `runtime_reader` в этом семействе
    означало бы неверный вывод, и подключение ищется по ФАКТУ.
    """
    итог = indexing.готовность("zonafilm.cc", доказать=False)
    # Утверждение — про ЧИТАТЕЛЯ, а не про статус: статус может быть
    # `MECHANISM_UNSUPPORTED` по другому пробелу выпуска (разрешение), и это
    # не вывод об отсутствии читателя.
    assert итог.get("release_gap") != "reader_missing", итог.get("reason")
    assert итог["runtime_reader"], "читатель найден и назван путём"
    подключение = итог["evidence"]["wiring"]
    assert подключение["imports"], подключение
    assert подключение["substitution"] == "indexing.py", подключение


def test_семейство_под_compose_не_обещает_открытия_операцией():
    """Форма КОНТЕЙНЕРА: режимом распоряжается compose, и операция это говорит.

    Утверждение проверяется на самом контракте, а не на домене. Причина
    измерена 2026-10-04: контейнерной формой считалось всё семейство Yummy, а
    публичные домены обслуживают ЯЧЕЙКИ — и `yummyani.biz` оказался ячейкой,
    чей режим операция менять как раз вправе. Привязка к домену проверяла бы
    не правило, а устаревший факт о конкретном сайте.
    """
    к = indexing.КОНТРАКТ_РЕЖИМА["yummy"]
    assert к["mode_owner"] == "compose"
    assert к["reader"].startswith("container:")
    assert к["state"] == "container"
    # Контракт выбирается по ВЫПУЩЕННОМУ коду: без учётной записи форма
    # остаётся контейнерной, иначе имя семейства решало бы за измерение.
    assert indexing.контракт("yummy")["mode_owner"] == "compose"


def test_форма_ячейки_семейства_принадлежит_операции():
    """У ячейки Yummy режим в реестре ядра, и распоряжается им операция.

    Измерено 2026-10-04: все пять витрин семейства — ячейки
    (`/srv/<учётная запись>/current`), режим читает
    `src/nova_core_indexability.py`, и `yummyani.site` с `yummyani.org`
    открыты записями `desired_state: OPEN` ОДНОГО файла, который объявлен
    каждым выпуском в `environment.INDEXING_CORE_REGISTRY`.
    """
    итог = indexing.готовность("yummyani.biz", доказать=False)
    assert итог["mode_owner"] == "operation", итог.get("reason")
    assert итог["mode_state_layer"] == indexing.СЛОЙ_РЕЕСТРА
    assert итог["runtime_reader"].endswith("src/nova_core_indexability.py")
    assert итог["owner_registry"].endswith("indexing-core-registry.json")
    # Наличия файла НЕ достаточно: подключение проверяется по вызову в точке
    # входа, и ответ обязан это называть.
    подкл = итог["evidence"]["core_reader"]
    assert подкл["connected"] is True, подкл
    assert подкл["calls"] is True, подкл


def test_открытый_домен_терминален():
    итог = indexing.готовность("animedia.space", доказать=False)
    assert итог["status"] == "OPEN_CONFIRMED"
    assert итог["ok"] is True
    assert итог["denying_signals"] == []
    assert итог["operation_can_open"] is True


def test_вердикт_надмножество_прежнего_ответа():
    """Прежний `indexing` отдавал четыре сигнала и canonical — всё осталось."""
    итог = indexing.готовность("lordserials22.info", доказать=False)
    публично = итог["evidence"]["public"]
    for поле in ("home_https", "robots_txt_http", "robots_txt_head",
                 "sitemap_http", "meta_robots_home", "canonical_home"):
        assert поле in публично, поле

def test_ожидание_владельца_невозможно_без_разрешения_выпуска():
    """Инвариант: `AWAITING_OWNER` не выдаётся, пока выпуск запрещает открытие.

    Дефект, из-за которого проверка появилась: вердикт обоих контрольных
    доменов был `AWAITING_OWNER` с `next_action: ждать команды владельца` при
    `release_permits_open: false`. Читалось это как «осталось только
    разрешение владельца», а на самом деле нужен ЕЩЁ И новый выпуск:
    разрешение владельца живёт в реестре и выпуск не заменяет.
    """
    for домен in ("lordserials22.info", "zonafilm.cc"):
        итог = indexing.готовность(домен, доказать=False)
        if итог["status"] == "AWAITING_OWNER":
            assert итог["release_permits_open"] is True, (
                f"{домен}: AWAITING_OWNER при release_permits_open="
                f"{итог['release_permits_open']!r} — отчёт утверждал бы, что "
                "осталось только разрешение владельца")
        if итог["release_permits_open"] is not True and итог["operation_can_open"]:
            assert итог["status"] == "MECHANISM_UNSUPPORTED", итог["status"]
            assert итог["release_gap"] == "permission_false", итог
            assert итог["owner_permission_is_not_enough"] is True
            assert "НОВЫЙ выпуск" in итог["reason"], итог["reason"]
            assert "release_permits_open: true" in итог["required_release"]


def test_пробел_выпуска_назван_и_различим():
    """Два разных пробела выпуска не сливаются в один ответ."""
    assert set(indexing.ПРОБЕЛ_ВЫПУСКА) == {"reader_missing", "permission_false"}
    assert set(indexing.ТРЕБУЕТ_ВЫПУСКА) == set(indexing.ПРОБЕЛ_ВЫПУСКА)
    # У домена без читателя — свой пробел, и он не про разрешение. Предмет
    # ВЫЧИСЛЯЕТСЯ, а не вписан: прежде здесь стоял an1meg0.site, и тест упал,
    # когда этому домену штатно доставили читателя (2026-10-04). Падение было
    # ложным — поведение правильное, устарел пример. Домены приходят и уходят,
    # а свойство «пробелы различимы» от конкретного домена не зависит.
    from factory.qwen import editorial as _ред

    без_читателя = None
    for s in _ред._реестр(опрашивать_сеть=False):
        if not s.domain:
            continue
        проба = indexing.готовность(s.domain, доказать=False)
        if проба.get("release_gap") == "reader_missing":
            без_читателя = проба
            break
    if без_читателя is None:
        # Все домены несут читателя — тоже законное состояние сети. Выдумывать
        # домен ради проверки нельзя, а структурная часть выше уже проверена.
        return
    assert без_читателя["status"] == "MECHANISM_UNSUPPORTED", без_читателя["status"]
    assert "readernot" not in без_читателя["required_release"]
    assert без_читателя.get("owner_permission_is_not_enough") is None, (
        "у пробела «нет читателя» разговор о разрешении владельца неуместен")


# --- реестр владельца у семейства с внешним механизмом --------------------

def test_разрешение_владельца_yummy_читается_из_его_реестра(tmp_path, monkeypatch):
    """У семейства с авторитетным реестром владельца спрашивается ЕГО реестр.

    В нашем `config/site-cells.json` у `yummy-*` раздела `indexing` нет вовсе, и
    прежде вердикт отвечал «разрешение владельца не объявлено» — то есть
    называл неразрешённым открытие, которое владелец разрешил и которое
    фактически действует на двух доменах семейства. Схема реестра ячеек прямо
    предписывает обратное: где есть авторитетный реестр владельца, значение
    обязано совпадать с ним.
    """
    from factory.qwen import indexing as и

    реестр = tmp_path / "indexing-core-registry.json"
    реестр.write_text(json.dumps({"schema": "indexing-core-registry/1.0",
        "domains": {"t.example": {
            "exact_domain": "t.example", "tenant_id": "t",
            "compose_service": "web-t", "desired_state": "OPEN",
            "policy_revision": 3,
            "owner_authorization_id": "OWNER-DECISION-1",
            "reason": "разрешено владельцем"}}}, ensure_ascii=False),
        encoding="utf-8")
    monkeypatch.setattr(и, "РЕЕСТР_ЯДРА_YUMMY", реестр)

    св = и.реестр_ядра("t.example")
    assert св["found"] and св["readable"], св
    assert св["desired_state"] == "OPEN"
    assert св["owner_authorization_id"] == "OWNER-DECISION-1"
    разрешил, объявлен, пояснение = и.разрешение_владельца_ядра("t.example")
    assert разрешил is True and объявлен == "OPEN"
    assert "OWNER-DECISION-1" in пояснение and str(реестр) in пояснение

    # Домена в реестре нет — это ОТСУТСТВИЕ РЕШЕНИЯ, а не беда файла.
    нет = и.реестр_ядра("чужой.example")
    assert нет["readable"] is True and нет["found"] is False
    assert "решения владельца" in нет["error"]
    assert и.разрешение_владельца_ядра("чужой.example")[0] is False


def test_нечитаемый_реестр_владельца_не_выдаётся_за_запрет(tmp_path, monkeypatch):
    """Беда окружения и «владелец не разрешал» — разные ответы.

    Слить их значило бы объявлять домен неразрешённым всякий раз, когда файл
    недоступен, — то есть судить о решении владельца по правам на каталог.
    """
    from factory.qwen import indexing as и

    monkeypatch.setattr(и, "РЕЕСТР_ЯДРА_YUMMY", tmp_path / "нет-такого.json")
    св = и.реестр_ядра("t.example")
    assert св["readable"] is False and св["found"] is False
    assert "не читается" in св["error"], св
    битый = tmp_path / "битый.json"
    битый.write_text("{не json", encoding="utf-8")
    monkeypatch.setattr(и, "РЕЕСТР_ЯДРА_YUMMY", битый)
    assert и.реестр_ядра("t.example")["error"].startswith("JSONDecodeError")


def test_предпроверка_и_вердикт_спрашивают_одно_разрешение():
    """Два ответа об одном домене расходиться не вправе.

    Предпроверка операции (`проверить`) читала разрешение владельца из НАШЕГО
    реестра ячеек, а вердикт (`готовность`) — из авторитетного реестра
    площадки. У `yummy-*` раздела `indexing` в нашем реестре нет вовсе, и
    получалось: вердикт называет объявленный режим и идентификатор разрешения
    владельца, а предпроверка на том же домене отвечает «разрешение владельца
    не объявлено». Источник обязан быть один.
    """
    из_предпроверки = indexing.проверить("yummyani.biz", mode="OPEN")
    вердикт = indexing.готовность("yummyani.biz", доказать=False)
    assert из_предпроверки["owner_declared_state"] == вердикт["owner_declared_state"]
    assert из_предпроверки["owner_authorized_open"] is вердикт["owner_authorized_open"]
    assert из_предпроверки.get("owner_registry") == вердикт.get("owner_registry")
    # ИСТОЧНИК назван в обоих ответах И СОВПАДАЕТ. Это и есть проверяемое
    # свойство: пока источников два, согласованность текстов ничего не
    # гарантирует, а один источник гарантирует её по построению.
    источник = из_предпроверки.get("owner_permission_source")
    assert источник in ("cell-registry", "core-registry", "owner-consent-anchor"), (
        источник)
    assert источник == (вердикт.get("evidence") or {}).get(
        "owner_permission_source"), (
        f"предпроверка читает {источник}, вердикт — "
        f"{(вердикт.get('evidence') or {}).get('owner_permission_source')}")

    # Прежде здесь проверялся ТЕКСТ блокера предпроверки. Утверждение
    # опиралось на то, что разрешения у домена НЕТ, и перестало работать в тот
    # же час, когда владелец его зарегистрировал: блокеров не стало, и
    # проверка упала на пустой строке, ничего при этом не защищая. Условная
    # ветка «если у кого-то из семейства разрешения нет» была бы не лучше:
    # сейчас оно есть у всех пяти, и ветка стала бы мёртвым кодом в одежде
    # проверки.
    #
    # Поэтому отказ проверяется ТАМ, ГДЕ ОН РОЖДАЕТСЯ, и на домене, которого в
    # реестре заведомо нет: ответ обязан назвать реестр ВЛАДЕЛЬЦА и не
    # ссылаться на наш реестр ячеек.
    разрешил, объявлен, пояснение = indexing.разрешение_владельца_ядра(
        "нет-такого-домена.invalid")
    assert разрешил is False
    assert объявлен == ""
    assert "indexing-core-registry.json" in пояснение, пояснение
    assert "site-cells.json" not in пояснение, (
        "разрешение владельца этой формы судится по нашему реестру")
    assert "решения владельца" in пояснение, пояснение


def test_ранний_возврат_требует_обоих_слоёв():
    """Полуприменённое состояние не должно быть устойчивым.

    Измерено 2026-10-05 на yummyani7.info: прикладной слой был уже открыт
    (операция применилась, а вызывающий прочитал устаревший файл результата и
    счёл её неудачной), слой nginx остался закрытым. По прежнему условию
    повтор отвечал «уже в этом режиме», не переключал ничего — и домен
    оставался закрытым запретом nginx при открытом приложении.
    """
    т = (КОРЕНЬ / "factory" / "qwen" / "indexing.py").read_text("utf-8")
    тело = т.split("def установить", 1)[1].split("\ndef ", 1)[0]
    строки = тело.splitlines()
    ранний = [н for н, с in enumerate(строки) if "desired_state" in с and "== режим" in с]
    assert ранний, "раннего возврата в операции не найдено"
    окно = "\n".join(строки[ранний[0]:ранний[0] + 3])
    assert "слой_в_нужном_режиме" in окно, (
        f"ранний возврат снова судит только по прикладному слою:\n{окно}")
    # И ветка записи не пишет повторно то, что уже в режиме.
    assert "уже_в_режиме" in тело
    assert "прикладной слой уже в этом режиме" in тело
