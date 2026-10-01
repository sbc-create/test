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


def test_разрешение_выпуска_читается_из_выпуска_а_не_рабочей_копии():
    т = (КОРЕНЬ / "factory" / "qwen" / "indexing.py").read_text("utf-8")
    тело = т.split("def разрешение_выпуска", 1)[1].split("\ndef ", 1)[0]
    assert "/current" in тело, "решение принимает код, который работает"
    assert "значение is True" in тело, (
        "разрешением считается только булево true")


def test_читатель_режима_ищется_в_выпуске():
    т = (КОРЕНЬ / "factory" / "qwen" / "indexing.py").read_text("utf-8")
    тело = т.split("def читатель_режима", 1)[1].split("\ndef ", 1)[0]
    assert "/current/src" in тело
    assert "repo" not in тело, "рабочая копия доказательством не является"


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
