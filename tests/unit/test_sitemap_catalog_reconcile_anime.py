"""Сверка карты с КАТАЛОГОМ ДОМЕНА по множествам, а не по итогам.

Задание владельца: «сверяй полные наборы адресов с каталогом самого домена;
совпадения итогов недостаточно». Отсюда и устройство прохода: множества
вычитаются в обе стороны, и у каждой разницы спрашивается ПРИЧИНА у живой
страницы.

Отрицательные контроли, названные заранее:

* **`noindex`-страница, отсутствующая в карте, дефектом НЕ является.** Карта
  описывает индексируемое; на animedia.icu таких записей 448 из 8 674 — это
  очередь тематического допуска, а не пробел. Проход, который объявил бы их
  пробелом, выдал бы 448 ложных находок;
* **`index`-страница, отсутствующей в карте, дефект.** Признак обязан уметь оба
  исхода, иначе он ничего не различает;
* **лишний адрес в карте — отдельный дефект**: карта обещает обходчику то,
  чего у витрины нет;
* **равенство ИТОГОВ ничего не доказывает**: проход обязан находить разницу и
  тогда, когда числа совпали. Это закреплено отдельной проверкой.
"""
from __future__ import annotations

import importlib.util
import json
import pathlib

КОРЕНЬ = pathlib.Path(__file__).resolve().parents[2]
_с = importlib.util.spec_from_file_location(
    "sitemap_catalog_reconcile_anime",
    КОРЕНЬ / "automation/local/sitemap-catalog-reconcile-anime.py")
ИНСТР = importlib.util.module_from_spec(_с)
_с.loader.exec_module(ИНСТР)

ДОМЕН = "animedia.icu"


def _подготовить(monkeypatch, tmp_path, *, каталог: list[str],
                 в_карте: list[str], robots: dict[str, str],
                 лишние: list[str] = ()):
    файл = tmp_path / "details.json"
    файл.write_text(json.dumps(
        {"details": {с: {"id": с} for с in каталог}}), encoding="utf-8")
    monkeypatch.setitem(ИНСТР.ВИТРИНЫ, ДОМЕН, str(файл))

    адреса = [f"https://{ДОМЕН}/"] + [f"https://{ДОМЕН}/title/{с}/"
                                      for с in list(в_карте) + list(лишние)]

    def добыть(url, таймаут=60):
        if url.endswith("/sitemap.xml"):
            тело = ("<sitemapindex><sitemap><loc>"
                    f"https://{ДОМЕН}/sitemap-1.xml</loc></sitemap>"
                    "</sitemapindex>")
            return тело, "200"
        if url.endswith("/sitemap-1.xml"):
            куски = "".join(f"<loc>{а}</loc>" for а in адреса)
            return f"<urlset>{куски}</urlset>", "200"
        слаг = url.rstrip("/").rsplit("/", 1)[-1]
        мета = robots.get(слаг, "index, follow")
        return f'<html><meta name="robots" content="{мета}"></html>', "200"

    monkeypatch.setattr(ИНСТР, "добыть", добыть)


def test_noindex_запись_вне_карты_дефектом_не_является(monkeypatch, tmp_path):
    """Живой случай: 448 записей очереди допуска на animedia.icu."""
    _подготовить(monkeypatch, tmp_path,
                 каталог=["a", "b", "c"], в_карте=["a", "b"],
                 robots={"c": "noindex, follow"})
    итог = ИНСТР.разобрать(ДОМЕН, предел=0, семя=1)
    assert итог["нет в карте"] == 1
    assert итог["из них noindex (отсутствие правильно)"] == 1
    assert итог["из них index (ПРОБЕЛ КАРТЫ)"] == []


def test_index_запись_вне_карты_это_пробел(monkeypatch, tmp_path):
    _подготовить(monkeypatch, tmp_path,
                 каталог=["a", "b", "c"], в_карте=["a", "b"], robots={})
    итог = ИНСТР.разобрать(ДОМЕН, предел=0, семя=1)
    assert итог["из них index (ПРОБЕЛ КАРТЫ)"] == ["c"]


def test_лишний_адрес_в_карте_называется(monkeypatch, tmp_path):
    _подготовить(monkeypatch, tmp_path, каталог=["a"], в_карте=["a"],
                 robots={}, лишние=["призрак"])
    итог = ИНСТР.разобрать(ДОМЕН, предел=0, семя=1)
    assert итог["лишних адресов в карте"] == [
        f"https://{ДОМЕН}/title/призрак/"]


def test_совпадение_итогов_разницу_не_скрывает(monkeypatch, tmp_path):
    """Числа равны, а наборы разные — ровно то, о чём предупреждал владелец."""
    _подготовить(monkeypatch, tmp_path, каталог=["a", "b"], в_карте=["a"],
                 robots={}, лишние=["призрак"])
    итог = ИНСТР.разобрать(ДОМЕН, предел=0, семя=1)
    assert итог["страниц произведений в карте"] == итог["записей в каталоге"]
    assert итог["из них index (ПРОБЕЛ КАРТЫ)"] == ["b"]
    assert len(итог["лишних адресов в карте"]) == 1


def test_отрицательный_контроль_смотрит_записи_ИЗ_карты(monkeypatch, tmp_path):
    _подготовить(monkeypatch, tmp_path,
                 каталог=["a", "b", "c"], в_карте=["a", "b"],
                 robots={"c": "noindex, follow"})
    итог = ИНСТР.разобрать(ДОМЕН, предел=0, семя=1)
    к = итог["отрицательный контроль"]
    assert к["проверено"] >= 1
    assert к["из них index"] == к["проверено"]


def test_контроль_ловит_неразличающий_признак(monkeypatch, tmp_path, capsys):
    """Если и в карте лежат noindex, вывод обязан предупредить."""
    _подготовить(monkeypatch, tmp_path,
                 каталог=["a", "b"], в_карте=["a"],
                 robots={"a": "noindex, follow", "b": "noindex, follow"})
    ИНСТР.главное(["--domain", ДОМЕН])
    assert "признак не различает" in capsys.readouterr().out


def test_предел_выборки_печатает_охват(monkeypatch, tmp_path, capsys):
    _подготовить(monkeypatch, tmp_path,
                 каталог=[f"s{н}" for н in range(20)],
                 в_карте=["s0"], robots={})
    ИНСТР.главное(["--domain", ДОМЕН, "--limit", "3"])
    вывод = capsys.readouterr().out
    assert "ОХВАТ: проверено 3 из 19" in вывод
    assert "НЕ ИЗМЕРЕНО" in вывод


def test_незнакомый_домен_отвергается(capsys):
    assert ИНСТР.главное(["--domain", "example.org"]) == 2
    assert "нет в перечне" in capsys.readouterr().out


def test_разделы_не_считаются_произведениями(monkeypatch, tmp_path):
    _подготовить(monkeypatch, tmp_path, каталог=["a"], в_карте=["a"],
                 robots={})
    итог = ИНСТР.разобрать(ДОМЕН, предел=0, семя=1)
    assert итог["прочих адресов в карте"] == [f"https://{ДОМЕН}/"]
    assert итог["страниц произведений в карте"] == 1


def test_код_один_при_пробеле_и_ноль_при_согласии(monkeypatch, tmp_path):
    _подготовить(monkeypatch, tmp_path, каталог=["a", "b"], в_карте=["a"],
                 robots={})
    assert ИНСТР.главное(["--domain", ДОМЕН]) == 1
    _подготовить(monkeypatch, tmp_path, каталог=["a", "b"], в_карте=["a"],
                 robots={"b": "noindex, follow"})
    assert ИНСТР.главное(["--domain", ДОМЕН]) == 0
