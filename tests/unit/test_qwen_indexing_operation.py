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
    тело = т.split("def разрешение_владельца", 1)[1].split("\ndef ", 1)[0]
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
    assert "контракт(adapter)" in тело, "семейство обязано учитываться"
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
    assert "policy_digest" in тело


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
    обязана говорить, что именно и кому делать.
    """
    т = (КОРЕНЬ / "factory" / "qwen" / "indexing.py").read_text("utf-8")
    assert "apply-indexing-nginx-root.sh" in т
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


def test_остальные_сайты_разрешения_не_получили():
    """Операция не должна открыть сайт, которого владелец не называл."""
    д = json.loads((КОРЕНЬ / "config" / "site-cells.json").read_text("utf-8"))
    сп = д.get("cells") or д.get("sites") or []
    сп = сп if isinstance(сп, list) else list(сп.values())
    разрешённые = {я.get("site_id") for я in сп
                   if (я.get("indexing") or {}).get("open_authorized") is True}
    assert разрешённые == {"animedia-01", "animedia-02"}, разрешённые


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
    """Два `<meta name="robots">` и заголовок обычной отдачи обязаны быть
    вычисляемыми. Исключение одно: `/poster/` — картинки витрины, их запрет
    намеренный и от режима не зависит.
    """
    п = (КОРЕНЬ / "var" / "site-repos" / репо / "src" / "animedia-frontend.py")
    if not п.is_file():
        pytest.skip(f"{репо}: рабочая копия недоступна")
    т = п.read_text(encoding="utf-8")
    assert '<meta name="robots" content="noindex, nofollow">' not in т
    assert т.count('<meta name="robots" content="{мета_роботов()}">') == 2
    assert 'self.send_header("X-Robots-Tag", мета_роботов())' in т
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
    def поставить(корень: pathlib.Path):
        monkeypatch.setattr(indexing, "КОРЕНЬ_NGINX", корень)
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


def test_прежнее_правило_не_вернулось():
    """Слой nginx не определяется перебором публичных заголовков."""
    т = (КОРЕНЬ / "factory" / "qwen" / "indexing.py").read_text("utf-8")
    assert 'з.startswith("X-Robots-Tag") for з in запрещают' not in т, (
        "возврат к определению слоя по перечню запрещающих сигналов")
    тело = т.split("def слой_nginx", 1)[1].split("\ndef ", 1)[0]
    assert "_конфиг_сайта" in тело, "источник — конфигурация сайта"
    assert "запрещают" not in тело, (
        "перечень публичных запретов не должен участвовать в определении слоя")


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
