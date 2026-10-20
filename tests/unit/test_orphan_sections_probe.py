"""Разделы без входящих ссылок: переадресация — не смерть, ключ — не домен.

Повод измерен 20.10, и обе правки меняли ИТОГ, а не оформление.

1. Код раздела снимался без следования переадресации, и 308 считался смертью.
   На Yummy `/catalog/` переадресует на `/catalog`, поэтому проход объявлял
   живыми 3 раздела из десяти, а семь — «отвечает 308», и на сиротство их не
   проверял вовсе. Итог был «10 доменов из 25»; после правки — 25 из 25.
2. Ключи `--all` и `--help` принимались за имена доменов: проход печатал
   «НЕ ИЗМЕРЕНО: главная не ответила» и итог «0 из 1», то есть опечатка в ключе
   читалась как здоровая сеть.

Отрицательные контроли, названные заранее:

* раздел, которого у витрины НЕТ (404), сиротой не считается — иначе проход
  требовал бы ссылок на несуществующее;
* раздел, на который главная ссылается, в список не попадает;
* адрес с завершающей косой чертой и без неё — один и тот же вход;
* ноль найденных ссылок на живой главной означает «разметка устроена иначе», а
  не сиротство всех разделов.

Сеть не используется: `код` и загрузка главной подменяются.
"""
from __future__ import annotations

import importlib.util
import pathlib
import subprocess

КОРЕНЬ = pathlib.Path(__file__).resolve().parents[2]
ПУТЬ = КОРЕНЬ / "automation/local/orphan-sections-probe.py"
_с = importlib.util.spec_from_file_location("orphan_sections_probe", ПУТЬ)
ИНСТР = importlib.util.module_from_spec(_с)
_с.loader.exec_module(ИНСТР)


def _главная(ссылки: list[str]) -> str:
    тело = "".join(f'<a href="{с}">x</a>' for с in ссылки)
    return f"<html><body>{тело}</body></html>"


def _подменить(monkeypatch, главная: str, коды: dict[str, str]):
    class _Итог:
        def __init__(self, текст):
            self.stdout = текст

    def run(части, **к):
        url = части[-1]
        if url.endswith("/") and url.count("/") == 3:
            return _Итог(главная)
        for путь, код in коды.items():
            if url.endswith(путь.rstrip("/")) or url.endswith(путь):
                return _Итог(код if "-w" in части else главная)
        return _Итог("404" if "-w" in части else "")

    monkeypatch.setattr(subprocess, "run", run)


# --- следование переадресации --------------------------------------------------

def test_код_снимается_со_следованием_переадресации():
    """Главный признак: без -L раздел с 308 считался мёртвым."""
    текст = ПУТЬ.read_text(encoding="utf-8")
    строка = next(с for с in текст.splitlines() if '"curl"' in с)
    assert "-sSL" in строка, строка


def test_основание_правки_названо_в_коде():
    """«308 это не смерть» — утверждение, и у него должно быть измерение.

    Проверяется по словам, а не по фразе целиком: фраза переносится по строкам,
    и дословное сравнение сломалось бы от переформатирования, ничего не говоря
    о поведении.
    """
    текст = " ".join(ПУТЬ.read_text(encoding="utf-8").split())
    assert "308" in текст
    assert "Переадресация — не смерть раздела" in текст
    assert "3 раздела из десяти" in текст


# --- ключи не домены ----------------------------------------------------------

def test_ключ_отвергается_а_не_считается_доменом(capsys):
    assert ИНСТР.главная(["--all"]) == 2
    вывод = capsys.readouterr().out
    assert "ключей этот инструмент не принимает" in вывод
    assert "--all" in вывод
    assert "НЕ ИЗМЕРЕНО" not in вывод


def test_несколько_ключей_перечислены(capsys):
    ИНСТР.главная(["--all", "--json"])
    вывод = capsys.readouterr().out
    assert "--all" in вывод and "--json" in вывод


def test_домен_ключом_не_считается(monkeypatch, capsys):
    """Отрицательный контроль: обычный домен по-прежнему проверяется."""
    _подменить(monkeypatch, _главная(["/catalog/"]), {"/catalog/": "200"})
    код = ИНСТР.главная(["x.site"])
    assert код in (0, 1)
    assert "ключей этот инструмент не принимает" not in capsys.readouterr().out


# --- сиротство ----------------------------------------------------------------

def test_живой_раздел_без_ссылки_это_сирота(monkeypatch):
    monkeypatch.setattr(ИНСТР, "код",
                        lambda url: "200" if "/schedule" in url else "404")
    monkeypatch.setattr(
        subprocess, "run",
        lambda ч, **к: type("И", (), {"stdout": _главная(["/catalog/"])})())
    итог = ИНСТР.по_домену("x.site")
    assert "/schedule/" in итог["осиротевшие"], итог


def test_раздел_со_ссылкой_сиротой_не_считается(monkeypatch):
    """Положительный контроль: так ведут себя /new/ и /collections/ у Zona."""
    monkeypatch.setattr(ИНСТР, "код",
                        lambda url: "200" if "/new" in url else "404")
    monkeypatch.setattr(
        subprocess, "run",
        lambda ч, **к: type("И", (), {"stdout": _главная(["/new/"])})())
    итог = ИНСТР.по_домену("x.site")
    assert итог["осиротевшие"] == [], итог


def test_косая_черта_не_создаёт_сироту(monkeypatch):
    """Главная ссылается без черты, кандидат с чертой — это один вход."""
    monkeypatch.setattr(ИНСТР, "код",
                        lambda url: "200" if "/new" in url else "404")
    monkeypatch.setattr(
        subprocess, "run",
        lambda ч, **к: type("И", (), {"stdout": _главная(["/new"])})())
    assert ИНСТР.по_домену("x.site")["осиротевшие"] == []


def test_отсутствующий_раздел_сиротой_не_считается(monkeypatch):
    """Отрицательный контроль: на Yummy /movies и /series отдают 404."""
    monkeypatch.setattr(ИНСТР, "код", lambda url: "404")
    monkeypatch.setattr(
        subprocess, "run",
        lambda ч, **к: type("И", (), {"stdout": _главная(["/catalog/"])})())
    итог = ИНСТР.по_домену("x.site")
    assert итог["осиротевшие"] == [] and итог["живые"] == []


def test_ноль_ссылок_на_главной_это_не_сиротство(monkeypatch):
    """Разметка устроена иначе — не повод объявить сиротами все разделы."""
    monkeypatch.setattr(ИНСТР, "код", lambda url: "200")
    monkeypatch.setattr(
        subprocess, "run",
        lambda ч, **к: type("И", (), {"stdout": "<html><body>нет ссылок</body></html>"})())
    итог = ИНСТР.по_домену("x.site")
    assert итог["осиротевшие"] == []
    assert итог.get("неизмеримо") is True
