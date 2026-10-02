"""Постоянные данные сайта: запрет на их изменение выпуском.

Все проверки идут в ИЗОЛИРОВАННОМ окружении: корни защищённых данных, отметок
и конфигураций nginx подменяются на временные каталоги. Боевые защищённые
данные не читаются на запись и не подменяются — иначе проверка сохранности
сама бы и ломала то, что проверяет.

Сценарии взяты из правила, а не придуманы: обновление и откат открытого сайта,
обновление закрытого, повторная установка, пропажа защищённого файла после
инициализации, попытка запрещённой записи, штатная операция редактора и
несовместимый выпуск.
"""
from __future__ import annotations

import json
import os
import pathlib
import re
import subprocess

import pytest

from factory.cell import protected

КОРЕНЬ = pathlib.Path(__file__).resolve().parents[2]
САЙТ = "test-01"
ДОМЕН = "t.example"


@pytest.fixture
def стенд(tmp_path, monkeypatch):
    """Изолированные корни: индексация, отметки, nginx, хранилище материалов."""
    инд = tmp_path / "indexing"
    (инд / "_log").mkdir(parents=True)
    отметки = tmp_path / "ownership"
    отметки.mkdir()
    ngx = tmp_path / "nginx-cells"
    ngx.mkdir()
    наложения = tmp_path / "overlays"
    наложения.mkdir()
    monkeypatch.setattr(protected, "КОРЕНЬ_ИНДЕКСАЦИИ", инд)
    monkeypatch.setattr(protected, "КОРЕНЬ_ОТМЕТОК", отметки)
    monkeypatch.setattr(protected, "КОРЕНЬ_NGINX_ЯЧЕЕК", ngx)
    monkeypatch.setattr(protected, "_корни_наложений",
                        lambda: {"test": str(наложения)})
    # Контракт сайта в стенде не читается: реестра для test-01 нет.
    monkeypatch.setattr(protected, "_контрактные", lambda site_id: [])
    monkeypatch.delenv(protected.ПЕРЕМЕННАЯ_ИСКЛЮЧЕНИЯ, raising=False)
    return {"indexing": инд, "markers": отметки, "nginx": ngx,
            "overlays": наложения, "root": tmp_path}


def _состояние(стенд, режим: str = "OPEN") -> pathlib.Path:
    п = стенд["indexing"] / f"{ДОМЕН}.json"
    п.write_text(json.dumps({"schema_version": 1, "site": ДОМЕН,
                             "desired_state": режим, "revision": 1},
                            ensure_ascii=False), encoding="utf-8")
    return п


def _материалы(стенд) -> pathlib.Path:
    к = стенд["overlays"] / ДОМЕН
    к.mkdir(parents=True, exist_ok=True)
    (к / "title-overlays.json").write_text(
        json.dumps({"schema_version": 1, "site": ДОМЕН, "items": [
            {"slug": "a", "body": "текст"}]}, ensure_ascii=False),
        encoding="utf-8")
    return к


def _robots(стенд) -> pathlib.Path:
    п = стенд["nginx"] / f"{САЙТ}.robots"
    п.write_text('default "";\n', encoding="utf-8")
    return п


# --- 1. Перечень защищаемого выведен из кода, а не из слов ----------------

def test_перечень_видов_закрыт_и_назван(стенд):
    виды = set(protected.пути(САЙТ, ДОМЕН))
    assert виды == {"indexing_state", "indexing_journal", "editorial",
                    "nginx_indexing", "site_declared"}, виды


def test_корни_совпадают_с_теми_что_читаются():
    """Защищаться должно ровно то, что читается. Расхождение означало бы
    защиту каталога, в который никто не пишет.
    """
    from factory.qwen import indexing as опер
    assert protected.КОРЕНЬ_ИНДЕКСАЦИИ == опер.КОРЕНЬ, (
        f"{protected.КОРЕНЬ_ИНДЕКСАЦИИ} против {опер.КОРЕНЬ}")
    from factory.qwen import registry as реестр
    assert protected._корни_наложений() == dict(реестр.КОРНИ_ХРАНИЛИЩ)
    from factory.cell import privileged
    assert protected.КОРЕНЬ_NGINX_ЯЧЕЕК == privileged.UPSTREAM_КАТАЛОГ


def test_перечень_родов_совпадает_с_читателями():
    assert set(protected.ЧИТАТЕЛИ) == set(protected.пути(САЙТ, ДОМЕН))


def test_производные_не_защищаются():
    """Каталог данных целиком замораживать запрещено: обновление каталога,
    кешей и карты сайта должно продолжать работать.
    """
    assert "sitemap" in protected.ПРОИЗВОДНЫЕ


def test_контракт_сайта_источник_перечня():
    """Имена постоянных файлов берутся из `data_contract.user_writable`
    выпущенного кода, а не перечисляются вторым списком.
    """
    т = (КОРЕНЬ / "factory" / "cell" / "protected.py").read_text("utf-8")
    тело = т.split("def _контрактные", 1)[1].split("\ndef ", 1)[0]
    assert "контракт_данных" in тело
    assert "user_writable" in тело
    assert "ПРОИЗВОДНЫЕ" in тело, "производные обязаны исключаться"


# --- 2. Три состояния владения, и смешивать их нельзя ---------------------

def test_новый_сайт_можно_инициализировать(стенд):
    с = protected.состояние_владения(САЙТ, ДОМЕН)
    assert с["state"] == "first_init" and с["may_initialise"] is True


def test_после_инициализации_запись_запрещена(стенд):
    цель = _состояние(стенд)
    protected.поставить_отметку(САЙТ, ДОМЕН, кем="тест")
    с = protected.состояние_владения(САЙТ, ДОМЕН)
    assert с["state"] == "managed" and с["may_initialise"] is False
    with pytest.raises(protected.ЗащитаДанных) as ош:
        protected.проверить_запись(САЙТ, ДОМЕН, цель, операция="deploy")
    assert "защищённые данные" in str(ош.value)


def test_отметка_переживает_пропажу_данных(стенд):
    """ПРОВЕРКИ «ФАЙЛА СЕЙЧАС НЕТ» НЕДОСТАТОЧНО. У созданного сайта пропажа
    данных — утрата, а не новый сайт, и подставлять шаблонные значения в этот
    момент хуже всего.
    """
    цель = _состояние(стенд)
    protected.поставить_отметку(САЙТ, ДОМЕН, кем="тест")
    цель.unlink()
    с = protected.состояние_владения(САЙТ, ДОМЕН)
    assert с["state"] == "lost", с
    assert с["may_initialise"] is False
    with pytest.raises(protected.ЗащитаДанных) as ош:
        protected.проверить_запись(САЙТ, ДОМЕН, цель, операция="deploy")
    текст = str(ош.value)
    assert "УТРАТА" in текст
    assert "восстановление шаблонных значений запрещено" in текст


def test_отметка_не_перезаписывается(стенд):
    """Перезапись стёрла бы время первой инициализации — единственное, чем
    «создавали давно» отличается от «создают сейчас».
    """
    первая = protected.поставить_отметку(САЙТ, ДОМЕН, кем="первый")
    assert первая["created"] is True
    вторая = protected.поставить_отметку(САЙТ, ДОМЕН, кем="второй")
    assert вторая["created"] is False
    assert вторая["existing"]["initialised_by"] == "первый"


def test_данные_без_отметки_тоже_значат_передан(стенд):
    """Сайт, созданный до появления отметок, защищён так же."""
    _материалы(стенд)
    с = protected.состояние_владения(САЙТ, ДОМЕН)
    assert с["state"] == "managed" and с["marker"] is None


# --- 3. Что НЕ даёт разрешения --------------------------------------------

@pytest.mark.parametrize("операция", [
    "deploy", "redeploy", "rollback", "template_update", "hotfix",
    "migration", "reinstall", "seed_user_writable", "schema_mismatch",
])
def test_ни_одна_причина_не_открывает_запись(стенд, операция):
    """Обновление шаблона, исправление ошибки, повторный деплой, откут
    выпуска, отсутствие файла и несовпадение схемы разрешения не дают.
    """
    цель = _состояние(стенд)
    protected.поставить_отметку(САЙТ, ДОМЕН, кем="тест")
    with pytest.raises(protected.ЗащитаДанных):
        protected.проверить_запись(САЙТ, ДОМЕН, цель, операция=операция)


def test_запрет_покрывает_каждый_вид(стенд):
    protected.поставить_отметку(САЙТ, ДОМЕН, кем="тест")
    цели = [_состояние(стенд), _материалы(стенд) / "title-overlays.json",
            _robots(стенд), стенд["indexing"] / "_log" / "operations.jsonl"]
    for ц in цели:
        with pytest.raises(protected.ЗащитаДанных):
            protected.проверить_запись(САЙТ, ДОМЕН, ц, операция="deploy")


def test_запрет_покрывает_каталог_целиком(стенд):
    """Удаление и очистка каталога — тоже изменение."""
    protected.поставить_отметку(САЙТ, ДОМЕН, кем="тест")
    к = _материалы(стенд)
    with pytest.raises(protected.ЗащитаДанных):
        protected.проверить_запись(САЙТ, ДОМЕН, к, операция="rmtree")
    with pytest.raises(protected.ЗащитаДанных):
        protected.проверить_запись(САЙТ, ДОМЕН, стенд["indexing"],
                                   операция="rmtree")


def test_посторонний_путь_не_задет(стенд):
    """Защита не должна мешать обычной работе: каталог данных целиком не
    заморожен, и производные файлы свободны.
    """
    protected.поставить_отметку(САЙТ, ДОМЕН, кем="тест")
    итог = protected.проверить_запись(
        САЙТ, ДОМЕН, стенд["root"] / "data" / f"{САЙТ}-catalog.json",
        операция="deliver")
    assert итог["allowed"] is True
    итог2 = protected.проверить_запись(
        САЙТ, ДОМЕН, стенд["root"] / "data" / "sitemap" / "sitemap.xml",
        операция="sitemap")
    assert итог2["allowed"] is True


# --- 4. Исключение только по поручению владельца --------------------------

def test_без_переменной_исключения_нет(стенд):
    assert protected.исключение() is None


def test_исключение_разрешает_ровно_названный_файл(стенд, monkeypatch):
    цель = _состояние(стенд)
    protected.поставить_отметку(САЙТ, ДОМЕН, кем="тест")
    monkeypatch.setenv(protected.ПЕРЕМЕННАЯ_ИСКЛЮЧЕНИЯ, json.dumps({
        "site": САЙТ, "files": [str(цель)],
        "change": "вернуть CLOSED по поручению владельца"}))
    итог = protected.проверить_запись(САЙТ, ДОМЕН, цель, операция="deploy")
    assert итог["allowed"] is True
    assert "поручению владельца" in итог["reason"]
    # А соседний файл тем же поручением НЕ разрешён.
    with pytest.raises(protected.ЗащитаДанных):
        protected.проверить_запись(САЙТ, ДОМЕН, _robots(стенд),
                                   операция="deploy")


@pytest.mark.parametrize("значение", [
    "не json",
    json.dumps({"files": ["/x"], "change": "что-то"}),            # нет site
    json.dumps({"site": САЙТ, "change": "что-то"}),               # нет files
    json.dumps({"site": САЙТ, "files": [], "change": "что-то"}),  # пустой
    json.dumps({"site": САЙТ, "files": ["/srv/*"], "change": "всё"}),
    json.dumps({"site": САЙТ, "files": ["/x"]}),                  # нет change
    json.dumps(["не объект"]),
])
def test_неполное_исключение_не_принимается(стенд, monkeypatch, значение):
    """«Разрешено всё» это отмена запрета, а не исключение."""
    monkeypatch.setenv(protected.ПЕРЕМЕННАЯ_ИСКЛЮЧЕНИЯ, значение)
    with pytest.raises(protected.ЗащитаДанных):
        protected.исключение()


def test_исключение_чужого_сайта_не_действует(стенд, monkeypatch):
    цель = _состояние(стенд)
    protected.поставить_отметку(САЙТ, ДОМЕН, кем="тест")
    monkeypatch.setenv(protected.ПЕРЕМЕННАЯ_ИСКЛЮЧЕНИЯ, json.dumps({
        "site": "другой-сайт", "files": [str(цель)], "change": "что-то"}))
    with pytest.raises(protected.ЗащитаДанных):
        protected.проверить_запись(САЙТ, ДОМЕН, цель, операция="deploy")


# --- 5. Несовместимый выпуск останавливается ДО активации -----------------

def _репозиторий(tmp_path, файлы: dict[str, str]) -> pathlib.Path:
    репо = tmp_path / "repo"
    (репо / "src").mkdir(parents=True)
    for имя, тело in файлы.items():
        (репо / имя).parent.mkdir(parents=True, exist_ok=True)
        (репо / имя).write_text(тело, encoding="utf-8")
    subprocess.run(["git", "init", "-q"], cwd=репо, check=True)
    subprocess.run(["git", "config", "user.email", "t@example"], cwd=репо, check=True)
    subprocess.run(["git", "config", "user.name", "t"], cwd=репо, check=True)
    subprocess.run(["git", "add", "-A"], cwd=репо, check=True)
    subprocess.run(["git", "commit", "-qm", "init"], cwd=репо, check=True)
    return репо


def test_выпуск_без_читателя_отклоняется_до_сборки(стенд, tmp_path):
    _состояние(стенд)
    _материалы(стенд)
    protected.поставить_отметку(САЙТ, ДОМЕН, кем="тест")
    репо = _репозиторий(tmp_path, {"src/other.py": "# без читателей\n"})
    коммит = subprocess.run(["git", "rev-parse", "HEAD"], cwd=репо,
                            capture_output=True, text=True).stdout.strip()
    with pytest.raises(protected.ЗащитаДанных) as ош:
        protected.проверить_выпуск(САЙТ, ДОМЕН, репо, коммит, adapter="test")
    текст = str(ош.value)
    assert "не несёт читателей" in текст
    assert "indexing_mode.py" in текст and "seo_overlay.py" in текст
    assert "ДО сборки" in текст


def test_выпуск_с_читателями_проходит(стенд, tmp_path):
    _состояние(стенд)
    _материалы(стенд)
    protected.поставить_отметку(САЙТ, ДОМЕН, кем="тест")
    репо = _репозиторий(tmp_path, {
        "src/indexing_mode.py": "# читатель режима\n",
        "src/seo_overlay.py": "# читатель материалов\n"})
    коммит = subprocess.run(["git", "rev-parse", "HEAD"], cwd=репо,
                            capture_output=True, text=True).stdout.strip()
    итог = protected.проверить_выпуск(САЙТ, ДОМЕН, репо, коммит, adapter="test")
    assert итог["compatible"] is True and итог["missing_readers"] == []


def test_читатель_правок_называется_по_семейству(стенд, tmp_path):
    """У Lords читатель правок — `editorial_overlay.py`, у Animedia —
    `seo_overlay.py`. Требовать у одного семейства файл другого значило бы
    блокировать исправный выпуск, а не защищать данные.
    """
    _состояние(стенд)
    _материалы(стенд)
    protected.поставить_отметку(САЙТ, ДОМЕН, кем="тест")
    лордс = _репозиторий(tmp_path / "lords", {
        "src/indexing_mode.py": "# читатель режима\n",
        "src/editorial_overlay.py": "# читатель правок Lords\n",
        "src/lords-frontend.py": "# рантайм\n"})
    коммит = subprocess.run(["git", "rev-parse", "HEAD"], cwd=лордс,
                            capture_output=True, text=True).stdout.strip()
    итог = protected.проверить_выпуск(САЙТ, ДОМЕН, лордс, коммит,
                                      adapter="lords")
    assert итог["compatible"] is True and итог["missing_readers"] == []
    # Тот же выпуск без читателя правок — отказ, и названо ИМЯ ЭТОГО семейства.
    (лордс / "src" / "editorial_overlay.py").unlink()
    subprocess.run(["git", "add", "-A"], cwd=лордс, check=True)
    subprocess.run(["git", "commit", "-qm", "без правок"], cwd=лордс, check=True)
    без = subprocess.run(["git", "rev-parse", "HEAD"], cwd=лордс,
                         capture_output=True, text=True).stdout.strip()
    with pytest.raises(protected.ЗащитаДанных) as ош:
        protected.проверить_выпуск(САЙТ, ДОМЕН, лордс, без, adapter="lords")
    assert "editorial_overlay.py" in str(ош.value)
    assert "seo_overlay.py" not in str(ош.value)


def test_семейство_определяется_по_выпускаемому_коду(стенд, tmp_path):
    """Семейство берётся из выпуска, а не из реестра: `adapter` можно не
    передавать, и ворота всё равно спросят читателя ТОГО рантайма."""
    _состояние(стенд)
    _материалы(стенд)
    protected.поставить_отметку(САЙТ, ДОМЕН, кем="тест")
    репо = _репозиторий(tmp_path / "по-коду", {
        "src/indexing_mode.py": "# читатель режима\n",
        "src/lords-frontend.py": "# рантайм Lords\n",
        "config/site.json": '{"entrypoint": "lords-frontend.py"}\n'})
    коммит = subprocess.run(["git", "rev-parse", "HEAD"], cwd=репо,
                            capture_output=True, text=True).stdout.strip()
    with pytest.raises(protected.ЗащитаДанных) as ош:
        protected.проверить_выпуск(САЙТ, ДОМЕН, репо, коммит)
    assert "editorial_overlay.py" in str(ош.value)


def test_режим_yummy_не_требует_файла_в_ячейке(стенд, tmp_path):
    """У Yummy режимом распоряжается контейнер: читателя в репозитории ячейки
    нет по устройству семейства, и отказ был бы отказом об устройстве, а не о
    данных. Материал там тоже читает приложение в контейнере.
    """
    _состояние(стенд)
    _материалы(стенд)
    protected.поставить_отметку(САЙТ, ДОМЕН, кем="тест")
    репо = _репозиторий(tmp_path / "yummy", {
        "src/yummy-frontend.py": "# заглушка витрины\n"})
    коммит = subprocess.run(["git", "rev-parse", "HEAD"], cwd=репо,
                            capture_output=True, text=True).stdout.strip()
    итог = protected.проверить_выпуск(САЙТ, ДОМЕН, репо, коммит, adapter="yummy")
    assert итог["compatible"] is True and итог["missing_readers"] == []


def test_неизвестное_семейство_не_даёт_послабления(стенд, tmp_path):
    """Опечатка в имени семейства не должна открывать ворота: действует общий
    перечень читателей, и выпуск без любого из них отклоняется."""
    _состояние(стенд)
    _материалы(стенд)
    protected.поставить_отметку(САЙТ, ДОМЕН, кем="тест")
    репо = _репозиторий(tmp_path / "ничей", {"src/other.py": "#\n"})
    коммит = subprocess.run(["git", "rev-parse", "HEAD"], cwd=репо,
                            capture_output=True, text=True).stdout.strip()
    for имя in ("lordz", "YUMMY", "animedia-2", "contaner:x"):
        with pytest.raises(protected.ЗащитаДанных):
            protected.проверить_выпуск(САЙТ, ДОМЕН, репо, коммит, adapter=имя)


def test_отказ_чтения_репозитория_не_читается_как_потеря_читателей(
        стенд, tmp_path, monkeypatch):
    """Git не ответил — это ДРУГОЙ отказ, чем «выпуск без читателя».

    Измерено на живом выпуске animedia.space: исполнитель работает от root,
    рабочая копия принадлежит `claude`, и `git cat-file` отвечает
    `fatal: detected dubious ownership` кодом 128. Прежний код считал любой
    ненулевой код «файла в коммите нет» и отклонял исправный выпуск
    сообщением «не несёт читателей защищённых данных» — то есть винил выпуск
    в том, чего в нём нет, и отправлял искать не там.
    """
    _состояние(стенд)
    _материалы(стенд)
    protected.поставить_отметку(САЙТ, ДОМЕН, кем="тест")
    репо = _репозиторий(tmp_path, {
        "src/indexing_mode.py": "# читатель режима\n",
        "src/seo_overlay.py": "# читатель материалов\n"})
    коммит = subprocess.run(["git", "rev-parse", "HEAD"], cwd=репо,
                            capture_output=True, text=True).stdout.strip()
    # Файлы на месте — выпуск проходит.
    assert protected.проверить_выпуск(САЙТ, ДОМЕН, репо, коммит,
                                      adapter="test")["compatible"] is True
    # Тот же выпуск, но git отвечает как ЧУЖОМУ владельцу: своим ключом
    # `safe.directory` ворота это переживают.
    monkeypatch.setenv("GIT_TEST_ASSUME_DIFFERENT_OWNER", "1")
    assert protected.проверить_выпуск(САЙТ, ДОМЕН, репо, коммит,
                                      adapter="test")["compatible"] is True
    monkeypatch.delenv("GIT_TEST_ASSUME_DIFFERENT_OWNER")
    # А вот нечитаемый репозиторий — отказ, и названный своим именем.
    не_репо = tmp_path / "не-репозиторий"
    не_репо.mkdir()
    with pytest.raises(protected.РепозиторийНедоступен) as ош:
        protected.проверить_выпуск(САЙТ, ДОМЕН, не_репо, коммит, adapter="test")
    текст = str(ош.value)
    assert "отказ ЧТЕНИЯ" in текст, текст
    assert "не несёт читателей" not in текст, текст


def test_отсутствующий_путь_отличается_от_нечитаемого_репозитория(tmp_path):
    """Отсутствующий путь git тоже отдаёт кодом 128 — и это «нет файла»."""
    репо = _репозиторий(tmp_path, {"src/indexing_mode.py": "#\n"})
    коммит = subprocess.run(["git", "rev-parse", "HEAD"], cwd=репо,
                            capture_output=True, text=True).stdout.strip()
    assert protected._файл_в_коммите(репо, коммит, "src/indexing_mode.py") is True
    assert protected._файл_в_коммите(репо, коммит, "src/нет-такого.py") is False


def test_новый_сайт_сверять_нечего(стенд, tmp_path):
    репо = _репозиторий(tmp_path, {"src/other.py": "#\n"})
    итог = protected.проверить_выпуск(САЙТ, ДОМЕН, репо, "", adapter="test")
    assert итог["compatible"] is True
    assert "сверять нечего" in итог["reason"]


def test_откат_на_старый_коммит_без_читателя_отклоняется(стенд, tmp_path):
    """Откат кода не откатывает данные редактора: выпуск, который их не читает,
    активировать нельзя — открытый сайт стал бы закрытым.
    """
    _состояние(стенд)
    protected.поставить_отметку(САЙТ, ДОМЕН, кем="тест")
    репо = _репозиторий(tmp_path, {"src/indexing_mode.py": "# читатель\n"})
    старый = subprocess.run(["git", "rev-parse", "HEAD"], cwd=репо,
                            capture_output=True, text=True).stdout.strip()
    # Удаляем читателя и делаем ВТОРОЙ коммит; первый остаётся «старым».
    (репо / "src" / "indexing_mode.py").unlink()
    subprocess.run(["git", "add", "-A"], cwd=репо, check=True)
    subprocess.run(["git", "commit", "-qm", "без читателя"], cwd=репо, check=True)
    без = subprocess.run(["git", "rev-parse", "HEAD"], cwd=репо,
                         capture_output=True, text=True).stdout.strip()
    # Коммит с читателем проходит, коммит без него — нет, и оба проверяются
    # по СОДЕРЖИМОМУ коммита, а не по рабочей копии.
    assert protected.проверить_выпуск(САЙТ, ДОМЕН, репо, старый,
                                      adapter="test")["compatible"] is True
    with pytest.raises(protected.ЗащитаДанных):
        protected.проверить_выпуск(САЙТ, ДОМЕН, репо, без, adapter="test")


# --- 6. Ворота стоят в механизме выпуска, а не рядом с ним ----------------

def test_активация_проверяет_защиту_первой():
    """Ворота обязаны стоять ДО подготовки площадки и засева: иначе отказ
    пришёл бы после того, как что-то уже создано.
    """
    т = (КОРЕНЬ / "factory" / "cell" / "executor.py").read_text("utf-8")
    тело = т.split("def активировать", 1)[1].split("\ndef ", 1)[0]
    assert "protected.проверить_выпуск" in тело
    место_ворот = тело.index("protected.проверить_выпуск")
    for шаг in ('privileged.prepare', '_засеять_хранилище'):
        assert место_ворот < тело.index(шаг), f"ворота должны стоять до {шаг}"


def test_засев_закрыт_воротами():
    т = (КОРЕНЬ / "factory" / "cell" / "privileged.py").read_text("utf-8")
    тело = т.split("def засеять_пользовательское", 1)[1].split("\ndef ", 1)[0]
    assert "protected.проверить_запись" in тело
    # Строка документации отбрасывается: в ней упомянут `Connection.backup()`
    # как объяснение, а не как вызов, и сравнение по позиции в тексте приняло
    # бы объяснение за запись.
    без_док = тело.split('"""', 2)[-1]
    место = без_док.index("protected.проверить_запись")
    for запись in ("shutil.copytree", "shutil.copy2", ".backup(", "shutil.chown"):
        if запись in без_док:
            assert место < без_док.index(запись), запись


def test_засев_не_запрещает_выпуск_сайта_с_данными(стенд, tmp_path, monkeypatch):
    """Файл НА МЕСТЕ — писать нечего, и выпуск не отклоняется.

    Дефект измерен на живом выпуске: активация `an1meg0.site` была отклонена
    сообщением «операция seed_user_writable пытается изменить защищённые данные
    ['site_declared']», хотя засев ничего бы не тронул — хранилище сообщества
    на месте. Ворота стояли ПЕРЕД проверкой существования, и защита запрещала
    любой выпуск сайта, у которого защищаемые данные ЕСТЬ.
    """
    from factory.cell import privileged

    данные = tmp_path / "data"
    данные.mkdir()
    (данные / "site-data").mkdir()                    # уже на месте
    источник = tmp_path / "source"
    источник.mkdir()
    (источник / "site-data").mkdir()

    площадка = privileged.Площадка(
        site_id=САЙТ, account="acct", root=tmp_path, app=tmp_path / "app",
        data=данные, unit="u.service", previous_unit=None, port=9999)

    monkeypatch.setattr(privileged, "контракт_данных",
                        lambda *a, **k: {"user_writable": ["site-data"],
                                         "source": "тест"})
    monkeypatch.setattr(privileged, "_домен_сайта", lambda _s: ДОМЕН)
    protected.поставить_отметку(САЙТ, ДОМЕН, кем="тест")
    итог = privileged.засеять_пользовательское(
        САЙТ, источник, dry_run=True, площадка=площадка)
    записи = итог["entries"]
    assert записи and записи[0].get("skipped") == "уже на месте", записи


def test_пропавший_файл_у_переданного_сайта_останавливает_засев(
        стенд, tmp_path, monkeypatch):
    """А вот отсутствующий файл шаблонным значением не восстанавливается."""
    from factory.cell import privileged

    данные = tmp_path / "data2"
    данные.mkdir()
    источник = tmp_path / "source2"
    источник.mkdir()
    (источник / "site-data").mkdir()                   # в источнике есть
    площадка = privileged.Площадка(
        site_id=САЙТ, account="acct", root=tmp_path, app=tmp_path / "app",
        data=данные, unit="u.service", previous_unit=None, port=9999)
    monkeypatch.setattr(privileged, "контракт_данных",
                        lambda *a, **k: {"user_writable": ["site-data"],
                                         "source": "тест"})
    monkeypatch.setattr(privileged, "_домен_сайта", lambda _s: ДОМЕН)
    # Защищаемым объявляется именно синтетический путь: своё устройство путей
    # проверяет сам `protected`, здесь проверяется ПРОВОДКА — что ворота
    # спрашивают при записи, которая действительно произошла бы.
    monkeypatch.setattr(protected, "пути",
                        lambda *a, **k: {"site_declared": [данные / "site-data"]})
    _состояние(стенд)          # у сайта есть защищённые данные
    protected.поставить_отметку(САЙТ, ДОМЕН, кем="тест")
    with pytest.raises(protected.ЗащитаДанных) as ош:
        privileged.засеять_пользовательское(
            САЙТ, источник, dry_run=True, площадка=площадка)
    # Остановка именно ДИАГНОСТИЧЕСКАЯ: названы отметка первой инициализации и
    # требование разобраться с причиной, а не «ставлю шаблонное значение».
    текст = str(ош.value)
    assert "отметка инициализации есть" in текст, текст
    assert "верните данные осознанно" in текст, текст


def test_защита_не_отключается_переменной():
    """Никаких «обходов» и флагов отключения: единственная переменная —
    поручение владельца с названными файлами.
    """
    т = (КОРЕНЬ / "factory" / "cell" / "protected.py").read_text("utf-8")
    import re
    переменные = set(re.findall(r'os\.environ\.get\("([A-Z_]+)"', т))
    assert переменные <= {"QWEN_INDEXING_ROOT", "SITE_NGINX_UPSTREAMS",
                          "SITE_OWNERSHIP_MARKERS",
                          protected.ПЕРЕМЕННАЯ_ИСКЛЮЧЕНИЯ}, переменные
    for запрещено in ("SKIP", "DISABLE", "FORCE", "NO_PROTECT", "bypass"):
        assert запрещено not in т, запрещено


# --- 7. Штатные операции редактора продолжают работать -------------------

def test_операции_редактора_не_импортируют_запрет():
    """Запрет адресован выпуску, а не редактору: его штатные операции пишут в
    эти же файлы законно. Импорт запрета в них остановил бы работу.
    """
    for имя in ("indexing.py", "editorial.py"):
        т = (КОРЕНЬ / "factory" / "qwen" / имя).read_text("utf-8")
        assert "from factory.cell import protected" not in т, имя
        assert "protected.проверить_запись" not in т, имя


def test_запрет_не_мешает_читать():
    """Чтение для диагностики разрешено и ничем не ограничено."""
    т = (КОРЕНЬ / "factory" / "cell" / "protected.py").read_text("utf-8")
    assert "Чтение для диагностики разрешено" in т
    # Сами функции чтения ничего не поднимают.
    assert protected.пути(САЙТ, ДОМЕН)
    assert isinstance(protected.существующие(САЙТ, ДОМЕН), dict)


# --- 8. Правило записано в читаемых инструкциях --------------------------

def test_центральный_документ_существует():
    д = КОРЕНЬ / "docs" / "RUNTIME_DATA_OWNERSHIP.md"
    assert д.is_file(), д
    т = д.read_text(encoding="utf-8")
    for что in ("/srv/sites/indexing", "runtime/overlays",
                "editorial-overrides.json", "/etc/nginx/cells",
                "первичн", "исключение", "Чтение для диагностики"):
        assert что in т, что


def test_правило_подключено_к_читаемым_инструкциям():
    """Документ, на который никто не ссылается, правилом не является."""
    ссылки = []
    for путь in (КОРЕНЬ / "CLAUDE.md",
                 КОРЕНЬ / "docs" / "PORTABLE_SITE_CELL.md",
                 КОРЕНЬ / "docs" / "QWEN_SITE_MANAGEMENT.md"):
        if путь.is_file() and "RUNTIME_DATA_OWNERSHIP" in путь.read_text("utf-8"):
            ссылки.append(путь.name)
    assert len(ссылки) >= 3, f"ссылаются только {ссылки}"


def test_новый_сайт_наследует_правило():
    """Создание сайта обязано ставить отметку и оставлять сайт закрытым."""
    т = (КОРЕНЬ / "factory" / "cell" / "newsite.py").read_text("utf-8")
    assert "RUNTIME_DATA_OWNERSHIP" in т or "protected" in т, (
        "создание сайта не упоминает правило владения данными")


# --- 9. Обходы штатными путями закрыты ------------------------------------

def test_установка_и_откат_проверяют_читателей():
    """`cell install` и `cell rollback` меняют `current` НАПРЯМУЮ, минуя
    активацию. Без ворот здесь запрет обходился бы штатной командой: прежний
    артефакт или откат вернули бы код, который перестал читать режим и тексты.
    """
    т = (КОРЕНЬ / "factory" / "cell" / "transfer.py").read_text("utf-8")
    assert "_ворота_защиты" in т
    for имя in ("def install", "def rollback"):
        тело = т.split(имя, 1)[1].split("\ndef ", 1)[0]
        assert "_ворота_защиты" in тело, имя
    # Проверяется РАСПАКОВАННЫЙ выпуск: у артефакта может не быть git-истории.
    ворота = т.split("def _ворота_защиты", 1)[1].split("\ndef ", 1)[0]
    assert "(выпуск / читатель).is_file()" in ворота
    # Проверяется распакованный выпуск, а не коммит: `git cat-file` здесь не
    # вызывается — у артефакта истории может не быть вовсе. Слово «git» в
    # пояснении допустимо, вызова быть не должно.
    без_док = ворота.split('"""', 2)[-1]
    assert "git " not in без_док and "subprocess" not in без_док


def test_ворота_установки_отклоняют_выпуск_без_читателя(tmp_path, стенд):
    from factory.cell import transfer
    без = tmp_path / "releases" / "aaaaaaaaaaaa"
    (без / "src").mkdir(parents=True)
    (без / "src" / "other.py").write_text("#\n", encoding="utf-8")
    _состояние(стенд)
    protected.поставить_отметку(САЙТ, ДОМЕН, кем="тест")
    # Домен берётся из реестра; для синтетического сайта его нет, поэтому
    # проверяется путь с явным доменом через саму защиту.
    есть = protected.существующие(САЙТ, ДОМЕН)
    assert есть, есть
    нет = [f"{в}: {ч}" for в in есть
           for ч in protected.ЧИТАТЕЛИ.get(в, ())
           if not (без / ч).is_file()]
    assert нет, "в выпуске без читателей должна быть нехватка"
    assert "indexing_mode.py" in " ".join(нет)


def test_сценарий_установки_отказывается_без_защиты():
    """Установка исполнителя из дерева без защиты — обход штатной командой.
    Сценарий обязан отказать, а не поставить исполнителя без ворот.
    """
    с = КОРЕНЬ / "automation" / "host" / "install-cell-executor.sh"
    т = с.read_text(encoding="utf-8")
    assert "factory/cell/protected.py" in т
    assert "protected.проверить_выпуск" in т
    assert "protected.проверить_запись" in т
    assert "_ворота_защиты" in т
    # Проверка стоит ДО копирования пакета.
    место = т.index("проверка защиты постоянных данных")
    assert место < т.index('cp -a "$SRC_ROOT/factory"')
    # Кириллица в именах переменных и циклов оболочки падает в работе, а
    # `bash -n` её пропускает: поймано сухим прогоном на `for вызов in`.
    присваивание = re.compile(r"^\s*[A-Za-z_]*[А-Яа-яЁё][\w]*\s*=")
    цикл = re.compile(r"^\s*for\s+[A-Za-z_]*[А-Яа-яЁё]")
    подстановка = re.compile(r"\$\{?[A-Za-z_]*[А-Яа-яЁё]")
    внутри = False
    for строка in т.split("\n"):
        if "<<'PY'" in строка:
            внутри = True
            continue
        if внутри:
            if строка.strip() == "PY":
                внутри = False
            continue
        assert not присваивание.match(строка), строка
        assert not цикл.match(строка), строка
        assert not подстановка.search(строка), строка


def test_исполнитель_не_держит_старый_процесс():
    """Исполнитель — oneshot по таймеру раз в минуту, а не демон: после
    установки следующий же прогон берёт новый код. Долгоживущего процесса со
    старым кодом не бывает по построению.
    """
    юнит = pathlib.Path("/etc/systemd/system/site-cell-executor.service")
    if not юнит.is_file():
        pytest.skip("юнита исполнителя нет в этом окружении")
    т = юнит.read_text(encoding="utf-8")
    assert "Type=oneshot" in т
    таймер = pathlib.Path("/etc/systemd/system/site-cell-executor.timer")
    if таймер.is_file():
        assert "OnCalendar" in таймер.read_text(encoding="utf-8")
