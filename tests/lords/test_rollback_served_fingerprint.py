"""Что именно доказывает публичный отпечаток после отката.

Разбор боевого случая. При учебном откате `zona-01` установщик вынес
`ROLLBACK_FAILED` с `disk_fingerprint_match=true` и `served_fingerprint_match=false`,
хотя откат полностью удался: снимки `zonafilm.space` до установки и после отката
совпали побайтно по телу, встроенным CSS и JS на всех трёх адресах.

Причина — сравнение двух РАЗНЫХ величин:

* `point.json.artifact_sha256` — sha256 ФИЗИЧЕСКОГО файла `lords-frontend.py`,
  сохранённого в точке отката;
* заголовок `X-Site-Factory-Artifact-Sha256` — поле `artifact_sha256` из
  МАНИФЕСТА, то есть объявленная личность релиза.

Исполняемый файл в парке ОДИН на все витрины, манифесты — раздельные. Поэтому
точка отката, снятая после того как соседняя витрина уже записала в общий файл
кандидата, честно сохраняет пару «файл кандидата + манифест прежнего релиза».
Откат восстанавливает ровно её, и домен объявляет отпечаток ПРЕЖНЕГО релиза —
не тот, что лежит в файле. Равенство этих величин было совпадением, а не
инвариантом.

Проверка не ослаблена, а разделена на два независимых утверждения, и оба
обязательны:

* `served_release_match` — объявленная доменом личность релиза совпадает с
  манифестом точки отката ЦЕЛИКОМ (семейство, версия, build_id, коммит,
  artifact_sha256), а не только по одному полю;
* `served_structure_match` — ИЗМЕРЕННЫЕ отпечатки тела, встроенных CSS и JS
  совпадают со снимком, снятым с домена до установки. Это не самоотчёт
  рантайма: подделать его манифестом нельзя.

Прежняя проверка не умела второго вовсе.
"""
from __future__ import annotations

import hashlib
import importlib.util
import json
import sys
from pathlib import Path

import pytest

КОРЕНЬ = Path(__file__).resolve().parents[2]
ИСХОДНИК = КОРЕНЬ / "automation" / "host" / "lords-nova-canary.py"

БАЙТЫ_БАЗЫ = b"# nova frontend 1.0.2 baseline\n"
БАЙТЫ_КАНДИДАТА = b"# nova frontend 1.1.0 candidate\n"

ОТПЕЧАТОК_БАЗЫ = "9229879ee5ab04eb68a59a98d9aeb1c6e3b745de7125c984756787790b0d6bbd"
ОТПЕЧАТОК_КАНДИДАТА = "a51dade469321e3078b8a7eee124e5ac936f286a33c28f327368bfbfabb85346"

РЕЛИЗ_БАЗЫ = {
    "schema_version": 1,
    "template_family": "zona",
    "design_version": "1.0.2",
    "source_commit": "a1691c568d5b53a6f5a09f3c79cc3b76c52821ee",
    "build_id": "20260910T124530Z-a1691c56-nova",
    "artifact_sha256": ОТПЕЧАТОК_БАЗЫ,
    "profile": "zona-general",
    "built_at": "2026-09-10T12:45:30Z",
}
РЕЛИЗ_КАНДИДАТА = {
    "schema_version": 1,
    "template_family": "zona",
    "design_version": "1.1.0",
    "source_commit": "7dc251d",
    "build_id": "20260913T2300Z-8ececc6c-nova",
    "artifact_sha256": ОТПЕЧАТОК_КАНДИДАТА,
    "profile": "zona-general",
    "built_at": "2026-09-14T07:43:00Z",
}

ДОМЕН = "zonafilm.space"


@pytest.fixture(scope="module")
def уст():
    спец = importlib.util.spec_from_file_location("nova_canary_fp", ИСХОДНИК)
    модуль = importlib.util.module_from_spec(спец)
    sys.modules["nova_canary_fp"] = модуль
    спец.loader.exec_module(модуль)
    return модуль


def _тело(версия: str, путь: str) -> bytes:
    """Правдоподобная страница: разметка, встроенный стиль, встроенный скрипт."""
    return (
        f"<!doctype html><html><head>"
        f"<style>.c{{color:#111}}/* {версия} */</style>"
        f"<script>window.v={версия!r}</script></head>"
        f"<body><main>{путь}</main>"
        f"<span class=\"vb\">Template: zona {версия}</span></body></html>"
    ).encode()


def _структура(тело: bytes, уст) -> dict:
    return уст._структура(тело)


def _проверка(уст, путь: str, релиз: dict, *, версия_тела: str | None = None,
              статус: int = 200, тело: bytes | None = None,
              конечный: str | None = None, переходов: int = 0,
              объявленное: dict | None = None) -> dict:
    версия_тела = версия_тела or релиз["design_version"]
    тело = тело if тело is not None else _тело(версия_тела, путь)
    объявленное = объявленное if объявленное is not None else {
        к: str(релиз[к]) for к in уст.ЗАГОЛОВКИ_РЕЛИЗА
    }
    хорошо = статус == 200 and (путь == "/healthz" or len(тело) >= уст.МИНИМУМ_ТЕЛА)
    return {
        "path": путь,
        "status": статус,
        "bytes": len(тело),
        "version": объявленное.get("design_version", ""),
        "artifact": объявленное.get("artifact_sha256", ""),
        "declared": объявленное,
        "final_url": конечный or f"https://{ДОМЕН}{путь}",
        "redirects": переходов,
        "structure": уст._структура(тело),
        "ok": хорошо,
    }


def _проба(уст, релиз: dict, **правки) -> dict:
    """Ответ домена целиком: /healthz, / и /catalog/."""
    страницы = []
    for путь in уст.ПРОБЫ:
        своё = правки.get(путь, {})
        if путь == "/healthz":
            страницы.append(_проверка(уст, путь, релиз, тело=b"ok\n", **своё))
        else:
            крупное = b"<!-- " + b"x" * уст.МИНИМУМ_ТЕЛА + b" -->"
            тело = своё.pop("тело", None)
            если_нет = _тело(своё.get("версия_тела") or релиз["design_version"], путь) + крупное
            страницы.append(_проверка(уст, путь, релиз,
                                      тело=тело if тело is not None else если_нет, **своё))
    итог = {"domain": ДОМЕН, "checks": страницы, "ok": all(с["ok"] for с in страницы)}
    return итог


@pytest.fixture
def стенд(уст, tmp_path, monkeypatch):
    """Точка отката боевого случая Zona: файл кандидата, манифест прежнего релиза."""
    фронт = tmp_path / "frontend"
    фронт.mkdir()
    артефакт = фронт / "lords-frontend.py"
    артефакт.write_bytes(БАЙТЫ_КАНДИДАТА)
    манифест = фронт / "template-manifest-zona-01.json"
    манифест.write_text(json.dumps(РЕЛИЗ_КАНДИДАТА, ensure_ascii=False, indent=2) + "\n",
                        encoding="utf-8")

    точка = фронт / ".rollback" / "20260914T074300Z-zona-01"
    точка.mkdir(parents=True)
    (точка / "lords-frontend.py").write_bytes(БАЙТЫ_КАНДИДАТА)
    снимок = _проба(уст, РЕЛИЗ_БАЗЫ)
    (точка / "point.json").write_text(json.dumps({
        "saved_at_utc": "20260914T074300Z",
        "artifact_sha256": hashlib.sha256(БАЙТЫ_КАНДИДАТА).hexdigest(),
        "manifest": манифест.name,
        "manifest_content": РЕЛИЗ_БАЗЫ,
        "served_snapshot": уст._снимок_отданного(снимок),
    }, ensure_ascii=False, indent=1), encoding="utf-8")

    monkeypatch.setattr(уст, "ФРОНТ", фронт)
    monkeypatch.setattr(уст, "АРТЕФАКТ", артефакт)
    monkeypatch.setattr(уст, "ОТКАТЫ", фронт / ".rollback")
    monkeypatch.setattr(уст, "ПАУЗА_ПОСЛЕ_ПЕРЕЗАПУСКА", 0)
    monkeypatch.setattr(уст, "СХОЖДЕНИЕ_ИНТЕРВАЛ", 0)
    monkeypatch.setattr(уст, "СХОЖДЕНИЕ_ПОПЫТОК", 2)
    monkeypatch.setattr(уст, "_юнит", lambda действие, юнит: (True, ""))
    # Диагностика кэша ходит в сеть и в вердикт не входит: в стенде её нет.
    monkeypatch.setattr(уст, "_кэш_диагностика",
                        lambda домен: {"url": f"https://{домен}/", "skipped_in_test": True})
    return {"front": фронт, "artifact": артефакт, "manifest": манифест, "point": точка}


def запустить(уст, стенд, monkeypatch, проба):
    """Откат с подставленным ответом домена. Привилегий не требуется."""
    monkeypatch.setattr(уст, "_проба", lambda домен: проба)

    class Арг:
        site = "zona-01"
        point = str(стенд["point"])
        record = None

    код = уст.откатить(Арг())
    return код, уст.ПОСЛЕДНЯЯ_ЗАПИСЬ


class TestБоевойСлучай:
    """Ровно тот вход, что дал ложный ROLLBACK_FAILED у zona-01."""

    def test_откат_признаётся_состоявшимся(self, уст, стенд, monkeypatch):
        код, запись = запустить(уст, стенд, monkeypatch, _проба(уст, РЕЛИЗ_БАЗЫ))
        assert запись["verdict"] == "ROLLED_BACK_VERIFIED", запись
        assert запись["served_fingerprint_match"] is True
        assert код == 0

    def test_диск_и_отданное_остались_раздельными_утверждениями(self, уст, стенд, monkeypatch):
        _, запись = запустить(уст, стенд, monkeypatch, _проба(уст, РЕЛИЗ_БАЗЫ))
        assert запись["disk_fingerprint_match"] is True
        assert запись["served_release_match"] is True
        assert запись["served_structure_match"] is True

    def test_объявленный_отпечаток_НЕ_сверяется_с_файлом(self, уст, стенд, monkeypatch):
        """Суть исправления: это разные величины, и они разошлись штатно."""
        _, запись = запустить(уст, стенд, monkeypatch, _проба(уст, РЕЛИЗ_БАЗЫ))
        assert запись["expected_artifact"] == hashlib.sha256(БАЙТЫ_КАНДИДАТА).hexdigest()
        assert запись["served_artifact_after_rollback"] == [ОТПЕЧАТОК_БАЗЫ]
        assert запись["expected_artifact"] != запись["served_artifact_after_rollback"][0]
        assert запись["verdict"] == "ROLLED_BACK_VERIFIED"


class TestНастоящиеНесовпаденияОстаютсяКрасными:
    """Каждый случай — реальный дефект. Ни один не имеет права стать зелёным."""

    def _провал(self, уст, стенд, monkeypatch, проба):
        код, запись = запустить(уст, стенд, monkeypatch, проба)
        assert запись["verdict"] == "ROLLBACK_FAILED", запись
        assert код == 1
        return запись

    def test_публично_остался_кандидат(self, уст, стенд, monkeypatch):
        запись = self._провал(уст, стенд, monkeypatch, _проба(уст, РЕЛИЗ_КАНДИДАТА))
        assert запись["served_release_match"] is False

    def test_чужой_релиз_отвергается_немедленно(self, уст, стенд, monkeypatch):
        чужой = dict(РЕЛИЗ_БАЗЫ, design_version="0.9.9",
                     artifact_sha256="f" * 64, build_id="чужая-сборка")
        запись = self._провал(уст, стенд, monkeypatch, _проба(уст, чужой))
        assert запись["convergence"]["log"][-1]["outcome"] == "wrong_release"
        assert len(запись["convergence"]["log"]) == 1, "чужой релиз ждать нельзя"

    def test_неверный_build_id(self, уст, стенд, monkeypatch):
        запись = self._провал(уст, стенд, monkeypatch,
                              _проба(уст, dict(РЕЛИЗ_БАЗЫ, build_id="20260101T000000Z-подмена")))
        assert запись["served_release_match"] is False

    def test_неверный_коммит(self, уст, стенд, monkeypatch):
        запись = self._провал(уст, стенд, monkeypatch,
                              _проба(уст, dict(РЕЛИЗ_БАЗЫ, source_commit="0" * 40)))
        assert запись["served_release_match"] is False

    def test_неверное_семейство(self, уст, стенд, monkeypatch):
        запись = self._провал(уст, стенд, monkeypatch,
                              _проба(уст, dict(РЕЛИЗ_БАЗЫ, template_family="lords")))
        assert запись["served_release_match"] is False

    def test_заголовки_верны_а_разметка_подменена(self, уст, стенд, monkeypatch):
        """Манифест объявляет что угодно; измеренная страница уличает его."""
        проба = _проба(уст, РЕЛИЗ_БАЗЫ, **{"/": {"версия_тела": "1.1.0"}})
        запись = self._провал(уст, стенд, monkeypatch, проба)
        assert запись["served_release_match"] is True
        assert запись["served_structure_match"] is False
        assert запись["structure_diff"], "различие обязано быть названо"

    def test_подменён_только_встроенный_css(self, уст, стенд, monkeypatch):
        тело = _тело("1.0.2", "/").replace(b"color:#111", b"color:#fff")
        тело += b"<!-- " + b"x" * уст.МИНИМУМ_ТЕЛА + b" -->"
        проба = _проба(уст, РЕЛИЗ_БАЗЫ, **{"/": {"тело": тело}})
        запись = self._провал(уст, стенд, monkeypatch, проба)
        assert запись["served_structure_match"] is False

    def test_неполный_ответ(self, уст, стенд, monkeypatch):
        проба = _проба(уст, РЕЛИЗ_БАЗЫ, **{"/": {"тело": b"<html>truncated"}})
        self._провал(уст, стенд, monkeypatch, проба)

    def test_ошибочный_переход(self, уст, стенд, monkeypatch):
        проба = _проба(уст, РЕЛИЗ_БАЗЫ,
                       **{"/": {"конечный": f"https://{ДОМЕН}/catalog/", "переходов": 1}})
        запись = self._провал(уст, стенд, monkeypatch, проба)
        assert запись["served_structure_match"] is False

    def test_пятисотый(self, уст, стенд, monkeypatch):
        проба = _проба(уст, РЕЛИЗ_БАЗЫ, **{"/": {"статус": 500}})
        self._провал(уст, стенд, monkeypatch, проба)

    def test_домен_молчит(self, уст, стенд, monkeypatch):
        пусто = {"domain": ДОМЕН, "checks": [], "ok": False}
        запись = self._провал(уст, стенд, monkeypatch, пусто)
        assert запись["served_release_match"] is False
        assert запись["served_structure_match"] is False

    def test_диск_не_восстановлен(self, уст, стенд, monkeypatch):
        """Файл подменяют после отката: совпавшее отданное не спасает."""
        родной = уст._атомарно

        def подмена(цель, данные):
            родной(цель, данные)
            if цель == стенд["artifact"]:
                цель.write_bytes(b"# alien file\n")

        monkeypatch.setattr(уст, "_атомарно", подмена)
        запись = self._провал(уст, стенд, monkeypatch, _проба(уст, РЕЛИЗ_БАЗЫ))
        assert запись["disk_fingerprint_match"] is False

    def test_перезапуск_не_удался(self, уст, стенд, monkeypatch):
        monkeypatch.setattr(уст, "_юнит", lambda действие, юнит: (False, "отказ"))
        self._провал(уст, стенд, monkeypatch, _проба(уст, РЕЛИЗ_БАЗЫ))

    def test_точка_без_манифеста_не_подтверждается_молчанием(self, уст, стенд, monkeypatch):
        """Пустой ожидаемый релиз не имеет права совпасть с пустым отданным."""
        файл = стенд["point"] / "point.json"
        данные = json.loads(файл.read_text(encoding="utf-8"))
        данные["manifest_content"] = None
        файл.write_text(json.dumps(данные, ensure_ascii=False, indent=1), encoding="utf-8")
        пусто = {"domain": ДОМЕН, "ok": True, "checks": [
            dict(с, declared={к: "" for к in уст.ЗАГОЛОВКИ_РЕЛИЗА},
                 version="", artifact="")
            for с in _проба(уст, РЕЛИЗ_БАЗЫ)["checks"]]}
        запись = self._провал(уст, стенд, monkeypatch, пусто)
        assert запись["served_release_match"] is False

    def test_точка_без_снимка_отданного_не_подтверждается(self, уст, стенд, monkeypatch):
        """Старая точка не умеет доказать структуру — значит не доказывает."""
        файл = стенд["point"] / "point.json"
        данные = json.loads(файл.read_text(encoding="utf-8"))
        данные.pop("served_snapshot")
        файл.write_text(json.dumps(данные, ensure_ascii=False, indent=1), encoding="utf-8")
        запись = self._провал(уст, стенд, monkeypatch, _проба(уст, РЕЛИЗ_БАЗЫ))
        assert запись["served_structure_reason"] == "POINT_WITHOUT_SERVED_SNAPSHOT"


class TestДопустимыеТранспортныеРазличия:
    """То, что меняет байты в канале, но не меняет релиз."""

    def test_порядок_и_регистр_заголовков(self, уст, стенд, monkeypatch):
        объявленное = {к: str(РЕЛИЗ_БАЗЫ[к]) for к in reversed(list(уст.ЗАГОЛОВКИ_РЕЛИЗА))}
        проба = _проба(уст, РЕЛИЗ_БАЗЫ)
        for с in проба["checks"]:
            с["declared"] = dict(объявленное)
        _, запись = запустить(уст, стенд, monkeypatch, проба)
        assert запись["verdict"] == "ROLLED_BACK_VERIFIED"

    def test_перевод_строки_crlf(self, уст, стенд, monkeypatch):
        """Тело то же; переносы строк переписаны по пути к клиенту."""
        def телa(путь):
            основа = (_тело("1.0.2", путь) + b"\n"
                      + b"<!-- " + b"x" * уст.МИНИМУМ_ТЕЛА + b" -->\n")
            return основа, основа.replace(b"\n", b"\r\n")

        опорная = json.loads((стенд["point"] / "point.json").read_text(encoding="utf-8"))
        проба = _проба(уст, РЕЛИЗ_БАЗЫ)
        for с in проба["checks"]:
            if с["path"] == "/healthz":
                continue
            lf, crlf = телa(с["path"])
            assert lf != crlf, "стенд обязан различать байты до нормализации"
            опорная["served_snapshot"][с["path"]]["structure"] = уст._структура(lf)
            с["structure"] = уст._структура(crlf)
        (стенд["point"] / "point.json").write_text(
            json.dumps(опорная, ensure_ascii=False, indent=1), encoding="utf-8")

        _, запись = запустить(уст, стенд, monkeypatch, проба)
        assert запись["served_structure_match"] is True
        assert запись["verdict"] == "ROLLED_BACK_VERIFIED"

    def test_нормализация_переносов_не_прячет_подмену(self, уст, стенд, monkeypatch):
        """Та же нормализация не должна скрывать настоящее изменение содержимого."""
        опорная = json.loads((стенд["point"] / "point.json").read_text(encoding="utf-8"))
        проба = _проба(уст, РЕЛИЗ_БАЗЫ)
        for с in проба["checks"]:
            if с["path"] == "/healthz":
                continue
            основа = (_тело("1.0.2", с["path"]) + b"\n"
                      + b"<!-- " + b"x" * уст.МИНИМУМ_ТЕЛА + b" -->\n")
            опорная["served_snapshot"][с["path"]]["structure"] = уст._структура(основа)
            подменённое = основа.replace(b"<main>", b"<main data-\xd0\xbf=1>")
            с["structure"] = уст._структура(подменённое.replace(b"\n", b"\r\n"))
        (стенд["point"] / "point.json").write_text(
            json.dumps(опорная, ensure_ascii=False, indent=1), encoding="utf-8")

        _, запись = запустить(уст, стенд, monkeypatch, проба)
        assert запись["served_structure_match"] is False
        assert запись["verdict"] == "ROLLBACK_FAILED"


class TestОжиданиеОграничено:
    def test_ожидание_имеет_предел_и_журнал(self, уст, стенд, monkeypatch):
        _, запись = запустить(уст, стенд, monkeypatch, _проба(уст, РЕЛИЗ_КАНДИДАТА))
        журнал = запись["convergence"]["log"]
        assert len(журнал) == уст.СХОЖДЕНИЕ_ПОПЫТОК
        assert all("elapsed_s" in ш and "declared" in ш for ш in журнал)
        assert журнал[-1]["outcome"] == "not_converged"

    def test_схождение_с_первой_попытки_не_ждёт(self, уст, стенд, monkeypatch):
        _, запись = запустить(уст, стенд, monkeypatch, _проба(уст, РЕЛИЗ_БАЗЫ))
        assert len(запись["convergence"]["log"]) == 1
        assert запись["convergence"]["log"][0]["outcome"] == "converged"


class TestПроверкаНеОслаблена:
    def test_нет_дизъюнкции_диска_и_отданного(self):
        текст = ИСХОДНИК.read_text(encoding="utf-8")
        вердикт = текст[текст.index('запись["verdict"] = ('):]
        голова = вердикт[:600]
        assert "disk_fingerprint_match" in голова
        assert "served_fingerprint_match" in голова
        assert " or " not in голова.split("ROLLED_BACK_VERIFIED")[1][:300], (
            "вердикт не имеет права быть дизъюнкцией")

    def test_отданное_складывается_из_двух_обязательных_частей(self):
        текст = ИСХОДНИК.read_text(encoding="utf-8")
        assert 'запись["served_fingerprint_match"] = (' in текст
        место = текст.index('запись["served_fingerprint_match"] = (')
        кусок = текст[место:место + 200]
        assert "served_release_match" in кусок and "served_structure_match" in кусок

    def test_кэшелом_не_участвует_в_вердикте(self):
        текст = ИСХОДНИК.read_text(encoding="utf-8")
        assert "cache_diagnostic" in текст, "диагностика кэша должна быть записана"
        вердикт = текст[текст.index('запись["verdict"] = ('):]
        assert "cache_diagnostic" not in вердикт[:600]

    def test_проверка_идёт_на_настоящий_домен_по_https(self):
        текст = ИСХОДНИК.read_text(encoding="utf-8")
        assert 'f"https://{домен}{путь}"' in текст
        assert "127.0.0.1" not in текст and "localhost" not in текст
