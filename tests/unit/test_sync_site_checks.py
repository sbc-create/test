"""Доставка проверок исполнителя не вправе затирать работу сайта.

Случай измерен 2026-10-04 по всей сети: канонический
`factory/cell/site_checks/activate_scenarios.py` не совпал ни с одним из 11
репозиториев сайтов. Соблазн очевидный — скопировать канон всем. Он неверен:
копия `zonafilm-space` БОГАЧЕ канона (отложенный HTTP-сервер и заглушка systemd
с памятью состояния — то, чем ловится активация, не успевшая за 40 секунд), и
копирование удалило бы эту проверку.

Поэтому критерий замены измеряемый: заменять можно только копию, чей отпечаток
есть в ИСТОРИИ канонического файла. Тогда это отставшая ревизия того же файла.
Нет отпечатка в истории — копия своя, и инструмент её не трогает.

Второе закреплённое свойство — риск D138 называется, даже когда замена
невозможна: витрина без `publisher_id_expected` со старой копией подтверждает
активацию ЧУЖИМ номером издателя.
"""
from __future__ import annotations

import importlib.util
import json
import pathlib

import pytest

КОРЕНЬ = pathlib.Path(__file__).resolve().parents[2]
ПУТЬ = КОРЕНЬ / "automation" / "local" / "sync-site-checks.py"


def _модуль():
    спец = importlib.util.spec_from_file_location("sync_site_checks", ПУТЬ)
    м = importlib.util.module_from_spec(спец)
    спец.loader.exec_module(м)
    return м


@pytest.fixture()
def среда(tmp_path, monkeypatch):
    """Канон, история канона и три репозитория: отставший, свой, без копии."""
    м = _модуль()
    канон = tmp_path / "canon"
    канон.mkdir()
    (канон / "activate_scenarios.py").write_text("КАНОН v2\n", encoding="utf-8")
    репозитории = tmp_path / "repos"

    def сайт(имя: str, копия: str | None, издатель: str | None):
        к = репозитории / имя
        (к / "checks").mkdir(parents=True)
        cfg: dict = {"site_id": имя}
        if издатель:
            cfg["publisher_id_expected"] = издатель
        (к / "config").mkdir()
        (к / "config" / "site.json").write_text(json.dumps(cfg), encoding="utf-8")
        if копия is not None:
            (к / "checks" / "activate_scenarios.py").write_text(копия,
                                                                encoding="utf-8")

    сайт("отставший", "КАНОН v1\n", "10238")
    сайт("свой", "КАНОН v2 + своя проверка\n", "10261")
    сайт("без-копии", None, "10252")
    сайт("без-издателя", "КАНОН v1\n", None)

    monkeypatch.setattr(м, "КАНОН", канон)
    monkeypatch.setattr(м, "РЕПОЗИТОРИИ", репозитории)
    # История канона: v1 была его прошлой ревизией, «своя проверка» — нет.
    monkeypatch.setattr(м, "история_канона",
                        lambda имя: {м.отпечаток(b"\xd0\x9a\xd0\x90\xd0\x9d"
                                                 b"\xd0\x9e\xd0\x9d v1\n"):
                                     "aaaaaaaaaaaa"})
    return м, репозитории


def _состояния(м, *аргументы):
    import io
    import contextlib
    поток = io.StringIO()
    with contextlib.redirect_stdout(поток):
        код = м.главная(list(аргументы) + ["--json"])
    assert код == 0
    return json.loads(поток.getvalue())


def test_отставшая_ревизия_заменяется(среда):
    м, репозитории = среда
    итог = _состояния(м, "--sync")
    assert any("отставший" in с for с in итог["synced"]), итог["synced"]
    assert (репозитории / "отставший" / "checks"
            / "activate_scenarios.py").read_text(encoding="utf-8") == "КАНОН v2\n"


def test_своя_копия_не_трогается(среда):
    """Главное свойство: версии вне истории канона — работа сайта."""
    м, репозитории = среда
    _состояния(м, "--sync")
    assert (репозитории / "свой" / "checks" / "activate_scenarios.py").read_text(
        encoding="utf-8") == "КАНОН v2 + своя проверка\n", (
        "инструмент затёр копию, которой нет в истории канона")


def test_вердикт_объясняет_отказ(среда):
    м, _ = среда
    итог = _состояния(м)
    по_имени = {с["repo"]: с["files"]["activate_scenarios.py"] for с in итог["repos"]}
    assert "в истории канона такой версии нет" in по_имени["свой"]["verdict"]
    assert по_имени["свой"]["sync"] is False
    assert по_имени["отставший"]["sync"] is True
    assert по_имени["отставший"]["ancestor_commit"] == "aaaaaaaaaaaa"


def test_отсутствие_копии_не_создаёт_её(среда):
    """Репозиторий, не несущий договор, не получает его молча."""
    м, репозитории = среда
    _состояния(м, "--sync")
    assert not (репозитории / "без-копии" / "checks"
                / "activate_scenarios.py").exists()


def test_риск_d138_называется(среда):
    """Нет объявленного издателя — это сказано, а не подставлено."""
    м, репозитории = среда
    итог = _состояния(м, "--sync")
    запись = next(с["files"]["activate_scenarios.py"] for с in итог["repos"]
                  if с["repo"] == "без-издателя")
    assert запись["missing_fields"] == ["publisher_id_expected"]
    assert "РИСК D138" in запись["verdict"]
    # Доставить канон туда нельзя: он потребует поля, которого нет.
    assert not any("без-издателя" in с for с in итог["synced"])
    assert (репозитории / "без-издателя" / "checks"
            / "activate_scenarios.py").read_text(encoding="utf-8") == "КАНОН v1\n"


def test_сухой_прогон_ничего_не_пишет(среда):
    м, репозитории = среда
    итог = _состояния(м, "--sync", "--dry-run")
    assert итог["synced"], "сухой прогон обязан сообщить, что бы изменилось"
    assert (репозитории / "отставший" / "checks"
            / "activate_scenarios.py").read_text(encoding="utf-8") == "КАНОН v1\n"


def test_канон_в_фабрике_не_имеет_умолчания_издателя():
    """D138 в самом каноне: чужой номер не подставляется (без песочницы)."""
    текст = (КОРЕНЬ / "factory" / "cell" / "site_checks"
             / "activate_scenarios.py").read_text(encoding="utf-8")
    # Только исполняемые строки: в пояснении `or '10238'` упомянут намеренно —
    # там сказано, почему умолчания больше нет.
    код = [с for с in текст.splitlines()
           if с.strip() and not с.lstrip().startswith("#")]
    виновные = [с for с in код if "or '10238'" in с]
    assert not виновные, (
        "канон вернул умолчание издателя: витрина без своего номера будет "
        f"подтверждать активацию чужим — {виновные}")
    assert "publisher_id_expected" in текст
