"""Работает ли поиск — по содержимому выдачи, с обязательным отрицательным контролём.

Повод и цена ошибки измерены 20.10. Первый прогон объявил «ПРОВАЛ: своё название
не находит» у yummyani.site и .biz, и оба раза это было свойством ЗОНДА, а не
витрины: сперва «названием» бралась строка `08:49` (время из разметки), потом
опрашивался адрес `/search/` с косой чертой, который отдаёт 308 без `Location`.
Настоящий дефект (MOD-113) нашёлся только при разборе, ПОЧЕМУ зонд получает ноль.

Отсюда устройство проверки, и каждая часть здесь проверяется:

* запрос берётся из `h1` страницы произведения ТОЙ ЖЕ витрины — там, где слово
  заведомо название, а не время и не рейтинг;
* отрицательный контроль обязателен: по заведомой небылице должно найтись НОЛЬ.
  Поиск, отдающий одно и то же на любой запрос, исправным не является;
* четыре исхода различаются, а не сводятся к «ок/не ок»: нашёл своё и не нашёл
  небылицу; нашёл оба; не нашёл ничего; нашёл только небылицу.
"""
from __future__ import annotations

import importlib.util
import pathlib

КОРЕНЬ = pathlib.Path(__file__).resolve().parents[2]
_с = importlib.util.spec_from_file_location(
    "search_works_check", КОРЕНЬ / "automation/local/search-works-check.py")
ИНСТР = importlib.util.module_from_spec(_с)
_с.loader.exec_module(ИНСТР)


def _страница_произведения(имя: str) -> str:
    return f"<html><body><h1 class='x'>{имя}</h1></body></html>"


def _карточки(n: int) -> str:
    return "".join(f'<a href="/title/t{и}/">x</a>' for и in range(n))


def test_слово_берётся_из_h1_страницы_произведения(monkeypatch):
    """Главный признак: прежде зонд брал «08:49» — время, а не название."""
    главная = ('<html><body><span>08:49</span>'
               '<a href="/title/kiberpank/">к</a></body></html>')

    def достать(url):
        return (_страница_произведения("Киберпанк: бегущие по краю")
                if "/title/kiberpank/" in url else главная)

    monkeypatch.setattr(ИНСТР, "достать", достать)
    слово, путь = ИНСТР.первое_название(главная, "x.site")
    assert слово == "Киберпанк", (слово, путь)
    assert путь == "/title/kiberpank/"


def test_короткие_слова_и_числа_запросом_не_берутся(monkeypatch):
    """«08», «49», «2026» названием не являются."""
    главная = '<a href="/title/a/">a</a>'
    monkeypatch.setattr(
        ИНСТР, "достать",
        lambda url: _страница_произведения("2026 ТВ 5 Некромант")
        if "/title/a/" in url else главная)
    слово, _ = ИНСТР.первое_название(главная, "x.site")
    assert слово == "Некромант", слово


def test_без_h1_название_не_выдумывается(monkeypatch):
    главная = '<a href="/title/a/">a</a>'
    monkeypatch.setattr(ИНСТР, "достать",
                        lambda url: "<html><body>нет h1</body></html>"
                        if "/title/a/" in url else главная)
    assert ИНСТР.первое_название(главная, "x.site") == ("", "")


def test_карточек_считает_уникальные_адреса():
    assert ИНСТР.карточек(_карточки(5)) == 5
    assert ИНСТР.карточек(_карточки(1) + _карточки(1)) == 1


def test_карточек_на_пустой_выдаче_ноль():
    assert ИНСТР.карточек("<html><body>ничего не найдено</body></html>") == 0


def test_небылица_объявлена_строкой():
    """Запрос-небылица должен быть заведомо отсутствующим, а не случайным."""
    assert len(ИНСТР.НЕБЫЛИЦА) >= 8
    assert ИНСТР.НЕБЫЛИЦА.isalpha()


def test_четыре_исхода_различаются():
    """«Нашёл оба» и «не нашёл ничего» — разные беды, и сводить их нельзя."""
    assert ИНСТР.исход(1, 0) == "исправно"
    assert "по небылице тоже находит" in ИНСТР.исход(1, 1)
    assert "своё название не находит" in ИНСТР.исход(0, 0)
    assert "находит только небылицу" in ИНСТР.исход(0, 1)


def test_опрашивается_адрес_без_косой_черты(monkeypatch, capsys):
    """Главный признак: на `/search/` стоит 308 без Location (MOD-113).

    Первый прогон получил на нём ноль по любому запросу и объявил поиск
    сломанным. Зонд не должен налетать на отдельный дефект адреса.
    """
    запрошено = []

    def достать(url):
        запрошено.append(url)
        if "/search?q=" in url:
            return _карточки(0 if "небыл" in url or "щщ" in url else 3)
        if "/title/" in url:
            return _страница_произведения("Некромант идёт")
        return '<a href="/title/a/">a</a>'

    monkeypatch.setattr(ИНСТР, "достать", достать)
    assert ИНСТР.главное(["x.site"]) == 0
    assert not any("/search/?q=" in у for у in запрошено), запрошено
    assert any("/search?q=" in у for у in запрошено)
    assert "исправно" in capsys.readouterr().out


def test_провал_даёт_код_один(monkeypatch):
    def достать(url):
        if "/search?q=" in url:
            return _карточки(3)  # находит и по небылице тоже
        if "/title/" in url:
            return _страница_произведения("Некромант идёт")
        return '<a href="/title/a/">a</a>'

    monkeypatch.setattr(ИНСТР, "достать", достать)
    assert ИНСТР.главное(["x.site"]) == 1


def test_модуль_при_импорте_в_сеть_не_ходит():
    """Инструмент без защиты `__main__` исполнял проход при импорте.

    Измерено: проверки шли 21 с и делали настоящие запросы. Такой инструмент
    нельзя проверить, и правило «тесты не выходят в сеть» он нарушал сам.
    """
    текст = (КОРЕНЬ / "automation/local/search-works-check.py").read_text(
        encoding="utf-8")
    assert 'if __name__ == "__main__":' in текст
    до = текст.split('if __name__ == "__main__":')[0]
    строки = [с for с in до.splitlines()
              if с and not с.startswith((" ", "\t", "#", '"', "'"))]
    вызовы = [с for с in строки if с.startswith(("print(", "for ", "главное("))]
    assert вызовы == [], вызовы


def test_перечень_домéнов_покрывает_все_семейства():
    д = ИНСТР.ДОМЕНЫ
    assert any("yummyani" in х for х in д)
    assert any("lordserials22" in х or "lordfilm47" in х for х in д)
    assert any("zonafilm" in х for х in д)
    assert any("animedia" in х or "animeg0" in х for х in д)
    assert any(х in ("lordserial.su", "lordfilm.group") for х in д)
