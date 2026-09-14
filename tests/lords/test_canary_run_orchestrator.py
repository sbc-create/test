"""Порядок canary: ворота, остановка и переход к следующей витрине.

Сценарий выполняет восемь шагов на двух витринах и решает, продолжать ли. Цена
ошибки в этом решении высокая: пропущенный провал оставит на публичном домене
непроверенного кандидата, а лишняя остановка — сорвёт выкладку на ровном месте.

Поэтому проверяется РЕШЕНИЕ, а не сеть: установщик, обходчик и снималка
отпечатков подменяются, а сценарий остаётся настоящим. Ни один тест не
обращается ни к домену, ни к systemd.
"""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest

КОРЕНЬ = Path(__file__).resolve().parents[2]
ИСХОДНИК = КОРЕНЬ / "automation" / "host" / "lords-zona-canary-run.py"


@pytest.fixture(scope="module")
def сц():
    спец = importlib.util.spec_from_file_location("canary_run", ИСХОДНИК)
    м = importlib.util.module_from_spec(спец)
    sys.modules["canary_run"] = м
    спец.loader.exec_module(м)
    return м


class TestПереченьВитрин:
    def test_только_две_разрешённые(self, сц):
        assert set(сц.ВИТРИНЫ) == {"lords-01", "zona-01"}

    def test_чужая_витрина_отвергается_до_действий(self, сц, tmp_path, capsys):
        код = сц.main(["--artifact", str(ИСХОДНИК), "--expect-sha256", "0" * 64,
                       "--commit", "0" * 40, "--build-id", "X",
                       "--out", str(tmp_path), "--sites", "yummy-site"])
        assert код == 2
        assert "вне перечня" in capsys.readouterr().err


class TestВорота:
    def test_пороги_нулевые(self, сц):
        """Одна карточка в никуда — дефект выкладки, а не допустимая доля."""
        assert set(сц.ВОРОТА.values()) == {0}
        for имя in ("ROUTE_FAILURES", "SOFT_404", "WRONG_ENTITY_200",
                    "BROKEN_INTERNAL_LINKS", "REDIRECT_LOOPS", "REDIRECT_CHAINS_GT1"):
            assert имя in сц.ВОРОТА


class TestОбъявленное:
    def test_пустой_снимок_это_неизвестность_а_не_совпадение(self, сц):
        """Нет данных — не «то же самое». Иначе недоступный домен выглядел бы
        как домен с прежним артефактом, и откат объявили бы удачным."""
        пусто = сц.объявленное({})
        assert пусто == {"versions": [], "artifacts": [], "statuses": []}
        assert пусто["artifacts"] != ["a" * 64]

    def test_разные_страницы_сводятся_в_множество(self, сц):
        снимок = {"pages": [
            {"status": 200, "declared": {"design_version": "1.1.0", "artifact_sha256": "aa"}},
            {"status": 200, "declared": {"design_version": "1.1.0", "artifact_sha256": "aa"}}]}
        assert сц.объявленное(снимок) == {"versions": ["1.1.0"], "artifacts": ["aa"],
                                          "statuses": [200]}

    def test_расхождение_между_страницами_видно(self, сц):
        """Две страницы с разными артефактами — это середина выкладки, и
        сводить их к одному значению нельзя."""
        снимок = {"pages": [
            {"status": 200, "declared": {"design_version": "1.0.2", "artifact_sha256": "aa"}},
            {"status": 200, "declared": {"design_version": "1.1.0", "artifact_sha256": "bb"}}]}
        свод = сц.объявленное(снимок)
        assert свод["artifacts"] == ["aa", "bb"] and len(свод["versions"]) == 2


class TestПорядокШагов:
    """Сценарий обязан останавливаться там, где написано, и не идти дальше."""

    def _подменить(self, сц, monkeypatch, *, установка, отдаёт, ворота_ок, откат=None):
        monkeypatch.setattr(сц, "ФИНАЛЬНЫЙ_ИНТЕРВАЛ", 0)
        monkeypatch.setattr(сц, "установить", lambda сайт, арг, запись: (
            установка.get("code", True), установка))
        monkeypatch.setattr(сц, "откатить", lambda сайт, точка, запись: (
            True, откат or {"verdict": "ROLLED_BACK_VERIFIED",
                            "disk_fingerprint_match": True, "served_fingerprint_match": True}))
        последовательность = list(отдаёт)
        monkeypatch.setattr(сц, "отпечатки", lambda домен, метка, куда:
                            последовательность.pop(0) if последовательность else {})
        monkeypatch.setattr(сц, "проверить_публично", lambda *а, **к: {
            "ok": ворота_ок, "gates": {"routes.ROUTE_FAILURES":
                                       {"value": 0 if ворота_ок else 3, "limit": 0, "ok": ворота_ок}}})

    def _снимок(self, версия, арт):
        return {"pages": [{"status": 200,
                           "declared": {"design_version": версия, "artifact_sha256": арт}}]}

    class Арг:
        artifact = "x"; expect_sha256 = "b" * 64; commit = "0" * 40
        build_id = "B"; design_version = "1.1.0"; профили = {}

    def test_без_базового_отпечатка_не_устанавливаем(self, сц, monkeypatch, tmp_path):
        """Домен не ответил — значит неизвестно, что откатывать. Не трогаем."""
        self._подменить(сц, monkeypatch, установка={}, отдаёт=[{}], ворота_ок=True)
        итог = сц.провести("lords-01", self.Арг(), tmp_path)
        assert итог["verdict"] == "ABORT_NO_BASELINE"
        assert [ш["step"] for ш in итог["steps"]] == ["baseline"]

    def test_неудачная_установка_останавливает_порядок(self, сц, monkeypatch, tmp_path):
        self._подменить(сц, monkeypatch,
                        установка={"code": False, "verdict": "ROLLED_BACK_NO_CHANGE"},
                        отдаёт=[self._снимок("1.0.2", "a" * 64)], ворота_ок=True)
        итог = сц.провести("lords-01", self.Арг(), tmp_path)
        assert итог["verdict"] == "INSTALL_FAILED_NO_CHANGE"

    def test_домен_отдающий_прежний_артефакт_откатывается(self, сц, monkeypatch, tmp_path):
        """Установщик доложил успех, а домен отдаёт прежнее — это не выкладка."""
        self._подменить(сц, monkeypatch,
                        установка={"verdict": "DEPLOYED_AND_VERIFIED",
                                   "rollback_point": "/tmp/точка"},
                        отдаёт=[self._снимок("1.0.2", "a" * 64),
                                self._снимок("1.0.2", "a" * 64)], ворота_ок=True)
        итог = сц.провести("lords-01", self.Арг(), tmp_path)
        assert итог["verdict"] == "ROLLED_BACK_GATES_FAILED"
        assert any(ш["step"] == "forced_rollback" for ш in итог["steps"])

    def test_провал_ворот_откатывает_и_останавливает(self, сц, monkeypatch, tmp_path):
        self._подменить(сц, monkeypatch,
                        установка={"verdict": "DEPLOYED_AND_VERIFIED",
                                   "rollback_point": "/tmp/точка"},
                        отдаёт=[self._снимок("1.0.2", "a" * 64),
                                self._снимок("1.1.0", "b" * 64)], ворота_ок=False)
        итог = сц.провести("lords-01", self.Арг(), tmp_path)
        assert итог["verdict"] == "ROLLED_BACK_GATES_FAILED"

    def test_несовпавший_возврат_останавливает(self, сц, monkeypatch, tmp_path):
        """После отката домен обязан отдавать ТОТ ЖЕ базовый отпечаток."""
        self._подменить(сц, monkeypatch,
                        установка={"verdict": "DEPLOYED_AND_VERIFIED",
                                   "rollback_point": "/tmp/точка"},
                        отдаёт=[self._снимок("1.0.2", "a" * 64),
                                self._снимок("1.1.0", "b" * 64),
                                self._снимок("1.0.2", "c" * 64)], ворота_ок=True)
        итог = сц.провести("lords-01", self.Арг(), tmp_path)
        assert итог["verdict"] == "ROLLBACK_DRILL_FAILED"

    def test_полный_проход_объявляет_канарейку_живой(self, сц, monkeypatch, tmp_path):
        self._подменить(сц, monkeypatch,
                        установка={"verdict": "DEPLOYED_AND_VERIFIED",
                                   "rollback_point": "/tmp/точка"},
                        отдаёт=[self._снимок("1.0.2", "a" * 64),
                                self._снимок("1.1.0", "b" * 64),
                                self._снимок("1.0.2", "a" * 64),
                                self._снимок("1.1.0", "b" * 64),
                                self._снимок("1.1.0", "b" * 64),
                                self._снимок("1.1.0", "b" * 64)], ворота_ок=True)
        итог = сц.провести("lords-01", self.Арг(), tmp_path)
        assert итог["verdict"] == "CANARY_ACTIVE_VERIFIED"
        финал = [ш for ш in итог["steps"] if ш["step"] == "final_check"][0]
        assert len(финал["checks"]) == сц.ФИНАЛЬНЫХ_ПРОВЕРОК
        assert all(п["ok"] for п in финал["checks"])
        шаги = [ш["step"] for ш in итог["steps"]]
        assert шаги == ["baseline", "install", "served_changed", "public_gates",
                        "rollback_drill", "baseline_restored", "restore_forward",
                        "final_check"]
        assert итог["public_urls"] == ["https://lordfilm47.space/",
                                       "https://lordfilm47.space/catalog/"]


    def test_сползание_между_запросами_ловится_и_откатывается(self, сц, monkeypatch, tmp_path):
        """Один запрос увидел кандидата, следующий — прежний релиз.

        Одиночная финальная проверка объявила бы это успехом. Витрину нельзя
        оставлять на неподтверждённом кандидате: порядок обязан вернуть её.
        """
        self._подменить(сц, monkeypatch,
                        установка={"verdict": "DEPLOYED_AND_VERIFIED",
                                   "rollback_point": "/tmp/точка"},
                        отдаёт=[self._снимок("1.0.2", "a" * 64),
                                self._снимок("1.1.0", "b" * 64),
                                self._снимок("1.0.2", "a" * 64),
                                self._снимок("1.1.0", "b" * 64),
                                self._снимок("1.0.2", "a" * 64),
                                self._снимок("1.1.0", "b" * 64)], ворота_ок=True)
        итог = сц.провести("lords-01", self.Арг(), tmp_path)
        assert итог["verdict"] == "FINAL_CHECK_FAILED"
        шаги = [ш["step"] for ш in итог["steps"]]
        assert "rollback_after_final" in шаги, шаги
        assert "public_urls" not in итог, "неподтверждённую витрину не объявляют доступной"

    def test_финальная_проверка_не_одиночная(self, сц):
        assert сц.ФИНАЛЬНЫХ_ПРОВЕРОК >= 3


class TestZonaТолькоПослеLords:
    def test_провал_lords_не_пускает_к_zona(self, сц, monkeypatch, tmp_path):
        посещённые = []

        def подделка(сайт, арг, выход):
            посещённые.append(сайт)
            return {"site": сайт, "verdict": "ROLLED_BACK_GATES_FAILED", "steps": []}

        monkeypatch.setattr(сц, "провести", подделка)
        код = сц.main(["--artifact", str(ИСХОДНИК), "--expect-sha256", "0" * 64,
                       "--commit", "0" * 40, "--build-id", "X", "--out", str(tmp_path)])
        assert код == 1
        assert посещённые == ["lords-01"], "к Zona перешли после провала Lords"

    def test_успех_lords_пускает_к_zona(self, сц, monkeypatch, tmp_path):
        посещённые = []

        def подделка(сайт, арг, выход):
            посещённые.append(сайт)
            return {"site": сайт, "verdict": "CANARY_ACTIVE_VERIFIED", "steps": [],
                    "public_urls": []}

        monkeypatch.setattr(сц, "провести", подделка)
        код = сц.main(["--artifact", str(ИСХОДНИК), "--expect-sha256", "0" * 64,
                       "--commit", "0" * 40, "--build-id", "X", "--out", str(tmp_path)])
        assert код == 0
        assert посещённые == ["lords-01", "zona-01"]
        свод = json.loads((tmp_path / "canary-run.json").read_text(encoding="utf-8"))
        assert свод["verdict"] == "ALL_CANARIES_ACTIVE"


class TestНичегоЛишнего:
    ЗАПРЕЩЁННОЕ = ("nsupdate", "certbot", "/etc/nginx", "daemon-reload", "iptables")

    def test_сценарий_не_трогает_инфраструктуру(self):
        код = "\n".join(с for с in ИСХОДНИК.read_text(encoding="utf-8").splitlines()
                        if not с.lstrip().startswith("#"))
        найдено = [з for з in self.ЗАПРЕЩЁННОЕ if з in код]
        assert not найдено, f"сценарий касается запрещённого: {найдено}"

    def test_привилегированное_только_через_установщик(self):
        текст = ИСХОДНИК.read_text(encoding="utf-8")
        assert "systemctl" not in текст, (
            "сценарий вызывает systemctl напрямую вместо установщика")
        assert "shell=True" not in текст


class TestПутиРазрешаются:
    """Ошибка на единицу в `parents[...]` ломает сценарий на первом же шаге.

    Она уже случалась в установщике и повторилась здесь: файл лежит в
    `automation/host/`, и один уровень вверх даёт `automation/`, отчего пути
    складывались в `automation/automation/host/`. Проверяется существование
    файлов по тем путям, которые вычисляет сам сценарий.
    """

    def test_все_вызываемые_инструменты_существуют(self, сц):
        для_проверки = {
            "установщик": сц.УСТАНОВЩИК, "отпечатки": сц.ОТПЕЧАТКИ,
            "обход": сц.ОБХОД, "сущности": сц.СУЩНОСТИ, "архетипы": сц.АРХЕТИПЫ,
        }
        нет = {и: str(п) for и, п in для_проверки.items() if not p_is_file(п)}
        assert not нет, f"инструменты не найдены по вычисленным путям: {нет}"

    def test_корень_не_удваивает_automation(self, сц):
        assert "automation/automation" not in str(сц.УСТАНОВЩИК)


def p_is_file(p):
    return p.is_file()
