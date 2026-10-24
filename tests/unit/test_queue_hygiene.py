"""Живые дубли на одном адресе и форма адреса в очереди (MOD-08, MOD-09).

ПОВОД И УРОК МЕТОДА. Первый мой счёт дал 0 дублей — потому что «живыми» я
взяла только рабочие статусы. Это было неверно: очередь ПЕРЕНАЗНАЧАЕТ и
заблокированные задания (`BLOCKED_INSUFFICIENT_FACTS` через 24 ч,
`NO_TARGET_PAGE` через 6 ч — MOD-168). С определением, взятым из ПОВЕДЕНИЯ
кода, дубль нашёлся: 1 адрес из 1 121 живых.

Поэтому проверки ниже закрепляют именно определение: заблокированное задание
считается живым, а «повторно не предлагается» и размещённое — нет.
"""
from __future__ import annotations

import importlib.util
import json
import pathlib

КОРЕНЬ = pathlib.Path(__file__).resolve().parents[2]
ПУТЬ = КОРЕНЬ / "automation" / "local" / "queue-hygiene.py"
_с = importlib.util.spec_from_file_location("queue_hygiene", ПУТЬ)
МОДУЛЬ = importlib.util.module_from_spec(_с)
assert _с.loader is not None
_с.loader.exec_module(МОДУЛЬ)


def _з(cid: str, url: str, статус: str = "READY_VERIFIED",
       домен: str = "d.site") -> dict:
    return {"content_id": cid, "canonical_url": url, "status": статус,
            "target_site": домен}


def test_абсолютная_и_относительная_формы_дают_один_ключ():
    """Именно расхождение форм и породило дубль в MOD-08."""
    а = МОДУЛЬ.нормализовать("https://d.site/anime/x/", "d.site")
    б = МОДУЛЬ.нормализовать("/anime/x", "d.site")
    assert а == б == ("d.site", "/anime/x")


def test_запрос_и_якорь_на_ключ_не_влияют():
    assert (МОДУЛЬ.нормализовать("https://d.site/anime/x?a=1#b", "d.site")
            == МОДУЛЬ.нормализовать("/anime/x", "d.site"))


def test_разные_домены_не_склеиваются():
    assert (МОДУЛЬ.нормализовать("/anime/x", "a.site")
            != МОДУЛЬ.нормализовать("/anime/x", "b.site"))


def test_заблокированное_задание_считается_живым():
    """Очередь его переназначает — значит оно занимает адрес."""
    записи = [_з("a", "/anime/x", "BLOCKED_INSUFFICIENT_FACTS"),
              _з("b", "/anime/y", "NO_TARGET_PAGE")]
    assert len(МОДУЛЬ.живые(записи)) == 2


def test_терминальные_статусы_живыми_не_считаются():
    записи = [_з("a", "/anime/x", "PUBLISHED"),
              _з("b", "/anime/y", "ALREADY_LIVE"),
              _з("c", "/anime/z", "DUPLICATE"),
              _з("d", "/anime/w", "BLOCKED_WRONG_MAPPING")]
    assert МОДУЛЬ.живые(записи) == []


def test_дубль_находится_при_разных_формах_адреса():
    """Ровно случай MOD-08: одно задание абсолютным адресом, другое — нет."""
    записи = [_з("a", "https://d.site/anime/x", "BLOCKED_INSUFFICIENT_FACTS"),
              _з("b", "/anime/x", "READY_VERIFIED")]
    д = МОДУЛЬ.дубли(записи)
    assert len(д) == 1
    assert sorted(з["content_id"] for з in list(д.values())[0]) == ["a", "b"]


def test_одно_задание_дублем_не_считается():
    """Отрицательный контроль: иначе проверка ругалась бы на норму."""
    assert МОДУЛЬ.дубли([_з("a", "/anime/x")]) == {}


def test_терминальное_рядом_с_живым_дублем_не_создаёт():
    записи = [_з("a", "/anime/x", "PUBLISHED"), _з("b", "/anime/x")]
    assert МОДУЛЬ.дубли(записи) == {}


def test_формы_считаются_раздельно():
    записи = [_з("a", "https://d.site/anime/x"), _з("b", "/anime/y"),
              _з("c", "anime/z")]
    ф = МОДУЛЬ.формы(записи)
    assert ф["абсолютная"] == 1 and ф["относительная"] == 1 and ф["иная"] == 1


def test_дубль_отражается_кодом_выхода(tmp_path, capsys):
    ф = tmp_path / "registry.json"
    ф.write_text(json.dumps({"items": [
        _з("a", "https://d.site/anime/x", "BLOCKED_INSUFFICIENT_FACTS"),
        _з("b", "/anime/x", "READY_VERIFIED")]}), encoding="utf-8")
    код = МОДУЛЬ.главное(["--registry", str(ф)])
    из = capsys.readouterr().out
    assert код == 1, из
    assert "MOD-08" in из


def test_чистая_очередь_даёт_ноль(tmp_path, capsys):
    """Отрицательный контроль кода выхода."""
    ф = tmp_path / "registry.json"
    ф.write_text(json.dumps({"items": [_з("a", "https://d.site/anime/x")]}),
                 encoding="utf-8")
    assert МОДУЛЬ.главное(["--registry", str(ф)]) == 0
    assert "живых дублей нет" in capsys.readouterr().out


def test_нет_реестра_это_не_измерено(tmp_path, capsys):
    assert МОДУЛЬ.главное(["--registry", str(tmp_path / "нет.json")]) == 2
    assert "НЕ ИЗМЕРЕНО" in capsys.readouterr().out
