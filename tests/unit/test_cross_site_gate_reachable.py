"""Ворота cross-site: падение и недостижимость вместо отказа.

Повод — два измерения 12.10, оба про то, что DoD-ворота «нет утечки между
сайтами» не выполнялись на живой сети вовсе.

1. **Недостижимость.** `cmd_seo_cross_site` разрешал цель ДО того, как читал
   `--base`, и для ячеек с адаптером `operator_applied` (агент к серверу не
   подключается — применяет оператор на хосте) отвечал
   `[BLOCKED_ACCESS] Неизвестный adapter цели` даже с прямо указанным
   адресом. Цель нужна ровно за базовым адресом; когда адрес дан, строить её
   незачем.
2. **Падение.** Участник группы без объявленного домена уезжал в заголовок
   `Host` значением `None`, и ворота падали с
   `TypeError: expected string or bytes-like object`. Измерено на группе
   `lords-quartet`, где у `lords-04` домен не объявлен. Падение хуже отказа:
   по traceback не видно, что сравнение не состоялось, а проверка, которая не
   сравнила, уникальностью не является.

Сеть не используется: запрос подменяется.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from factory import verify as verify_mod


class _ПутиСтенда:
    """Подмена PATHS: `sites` там свойство, присвоить его нельзя.

    Нужен ровно один атрибут — каталог пакетов; остальное ворота не трогают.
    """

    def __init__(self, каталог: Path) -> None:
        self.sites = каталог


СТРАНИЦА = (
    '<html><head><title>Каталог — Один</title>'
    '<meta name="robots" content="index, follow">'
    '<link rel="canonical" href="https://один.example/catalog/">'
    '<meta name="description" content="Описание каталога сайта Один">'
    '</head><body><a class="site-header__brand" href="/">Один</a>'
    '<h1>Каталог</h1><main>' + ("Собственный текст сайта Один. " * 30)
    + '</main></body></html>')


@pytest.fixture()
def группа(tmp_path, monkeypatch):
    """Три пакета в одной группе: два с доменом, один без.

    Третий и есть предмет: раньше он ронял прогон.
    """
    сайты = tmp_path / "sites"
    сайты.mkdir()
    пакеты = {
        "с-одним": {"domain": "один.example", "cross_site_group": "тройка"},
        "с-другим": {"domain": "другой.example", "cross_site_group": "тройка"},
        "без-домена": {"domain": None, "cross_site_group": "тройка"},
        "чужой": {"domain": "чужой.example", "cross_site_group": "другая"},
    }
    for имя in пакеты:
        (сайты / имя).mkdir()
        (сайты / имя / "package.yaml").write_text("", encoding="utf-8")

    monkeypatch.setattr(verify_mod, "PATHS", _ПутиСтенда(сайты))

    from factory import validation
    monkeypatch.setattr(validation, "load_package",
                        lambda имя: dict(пакеты[имя], site_id=имя))
    # Поверхность и ответы страниц подменяются: предмет теста — состав
    # сравниваемых сайтов, а не разбор HTML.
    monkeypatch.setattr(verify_mod, "_surface",
                        lambda base, host: [("/catalog/", True)])
    запрошено: list[tuple[str, str]] = []

    def поддельный(base_url, path, host, *, follow=True):
        assert isinstance(host, str), (
            f"Host обязан быть строкой, пришло {type(host).__name__} — "
            "именно так ворота и падали")
        запрошено.append((host, path))
        return 200, {}, СТРАНИЦА.replace("Один", host.split(".")[0])
    monkeypatch.setattr(verify_mod, "_get_host", поддельный)
    return пакеты, запрошено


def test_участник_без_домена_не_роняет_прогон(группа, tmp_path):
    _пакеты, запрошено = группа
    отчёт = verify_mod.cross_site_uniqueness(
        "https://один.example", {"cross_site_group": "тройка"}, tmp_path)
    хосты = sorted({х for х, _п in запрошено})
    assert хосты == ["другой.example", "один.example"], хосты
    assert отчёт.counts["sites"] == 2


def test_пропущенный_участник_назван_в_отчёте(группа, tmp_path):
    """По отчёту должно быть видно, С КЕМ сравнение не проводилось."""
    verify_mod.cross_site_uniqueness(
        "https://один.example", {"cross_site_group": "тройка"}, tmp_path)
    артефакт = json.loads(
        (tmp_path / "cross-site-uniqueness.json").read_text(encoding="utf-8"))
    assert артефакт["counts"]["group_members_without_domain"] == 1
    assert артефакт["counts"]["skipped_members"] == "без-домена"


def test_чужая_группа_не_участвует(группа, tmp_path):
    _пакеты, запрошено = группа
    verify_mod.cross_site_uniqueness(
        "https://один.example", {"cross_site_group": "тройка"}, tmp_path)
    assert "чужой.example" not in {х for х, _п in запрошено}


def test_без_группы_сравнивать_не_с_чем(группа, tmp_path):
    """Пакет без группы не тянет за собой чужие сайты."""
    _пакеты, запрошено = группа
    отчёт = verify_mod.cross_site_uniqueness(
        "https://один.example", {}, tmp_path)
    assert запрошено == []
    assert отчёт.counts.get("sites", 0) == 0


def test_все_участники_без_домена_дают_ноль_сайтов(tmp_path, monkeypatch):
    """Крайний случай: сравнивать не с чем, и это не «уникально».

    Проверяется, что прогон доходит до конца и честно показывает ноль
    сайтов, а не падает и не объявляет успех.
    """
    сайты = tmp_path / "sites"
    сайты.mkdir()
    (сайты / "пусто").mkdir()
    (сайты / "пусто" / "package.yaml").write_text("", encoding="utf-8")
    monkeypatch.setattr(verify_mod, "PATHS", _ПутиСтенда(сайты))
    from factory import validation
    monkeypatch.setattr(validation, "load_package",
                        lambda имя: {"domain": None,
                                     "cross_site_group": "тройка"})
    monkeypatch.setattr(verify_mod, "_surface",
                        lambda base, host: [("/catalog/", True)])
    monkeypatch.setattr(
        verify_mod, "_get_host",
        lambda *a, **k: pytest.fail("запроса быть не должно: хостов нет"))
    отчёт = verify_mod.cross_site_uniqueness(
        "https://один.example", {"cross_site_group": "тройка"}, tmp_path)
    assert отчёт.counts["group_members_without_domain"] == 1
    assert отчёт.counts.get("sites", 0) == 0


def test_нечитаемый_чужой_пакет_не_роняет_проверку(tmp_path, monkeypatch):
    """Так было и раньше, и это свойство стоит удержать."""
    сайты = tmp_path / "sites"
    сайты.mkdir()
    for имя in ("хороший", "битый"):
        (сайты / имя).mkdir()
        (сайты / имя / "package.yaml").write_text("", encoding="utf-8")
    monkeypatch.setattr(verify_mod, "PATHS", _ПутиСтенда(сайты))
    from factory import validation

    def загрузить(имя):
        if имя == "битый":
            raise ValueError("пакет не разбирается")
        return {"domain": "хороший.example", "cross_site_group": "тройка"}
    monkeypatch.setattr(validation, "load_package", загрузить)
    monkeypatch.setattr(verify_mod, "_surface",
                        lambda base, host: [("/catalog/", True)])
    monkeypatch.setattr(verify_mod, "_get_host",
                        lambda *a, **k: (200, {}, СТРАНИЦА))
    отчёт = verify_mod.cross_site_uniqueness(
        "https://хороший.example", {"cross_site_group": "тройка"}, tmp_path)
    assert отчёт.counts["sites"] == 1
