"""Отмена зависшего прогона: адресная, доказанная и идемпотентная.

Прогон обновления упёрся в предел памяти и три часа не производил ничего: за
пять минут ноль прироста файлов и байт при 191 срабатывании предела, память
2047 МиБ из 2048, `current` не переключался, все манифесты на прежней ревизии.
Гасить такое нужно — но гашение чужой работы это операция, которую нельзя
делать по впечатлению.

Отсюда три свойства, закреплённые здесь. Адресность: юнит из закрытого списка и
точная InvocationID, иначе отмена промахнётся по уже сменившемуся прогону.
Доказанность: признаки застоя измеряются заново перед остановкой. Идемпотентность:
если прогон уже сменился, операция ничего не делает и говорит об этом.

Гашение — типизованная операция systemd, а не сигнал по угаданному PID: `kill`
мимо цели убивает чужую работу, и восстановить её будет нечем.
"""

from __future__ import annotations

import argparse
import ast
import importlib.machinery
import importlib.util
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture(scope="module")
def помощник():
    путь = ROOT / "automation" / "deploy" / "lords-deployctl"
    спец = importlib.util.spec_from_loader(
        "ctl_cancel", importlib.machinery.SourceFileLoader("ctl_cancel", str(путь)))
    м = importlib.util.module_from_spec(спец)
    спец.loader.exec_module(м)
    return м


class TestАдресность:
    def test_список_отменяемых_юнитов_закрыт(self, помощник):
        assert помощник.ОТМЕНЯЕМЫЕ == (помощник.ОБНОВЛЕНИЕ_СЛУЖБА,)

    def test_чужой_юнит_отвергается(self, помощник):
        args = argparse.Namespace(unit="nginx.service", invocation="a" * 32,
                                  observe=1, stop_timeout=1, force_proven=False)
        with pytest.raises(помощник.Отказ):
            помощник.глагол_cancel_stuck(args)

    def test_глагол_объявлен_в_разборе_аргументов(self, помощник):
        assert "cancel-stuck" in помощник.ГЛАГОЛЫ


class TestБезПроизвольногоИсполнения:
    def test_ни_kill_ни_pkill_ни_оболочки(self, помощник):
        """Разбор дерева, а не поиск подстроки.

        Поиск по тексту срабатывает на упоминании запрета в документации —
        проверка, не отличающая запрет от нарушения, не проверяет ничего.
        """
        дерево = ast.parse(Path(помощник.__file__).read_text(encoding="utf-8"))
        оболочка = [у.lineno for у in ast.walk(дерево) if isinstance(у, ast.Call)
                    for к in у.keywords
                    if к.arg == "shell" and getattr(к.value, "value", False) is True]
        assert оболочка == [], f"оболочка вызвана в строках {оболочка}"
        имена = {ast.unparse(у.func) for у in ast.walk(дерево) if isinstance(у, ast.Call)}
        for запретное in ("os.kill", "signal.raise_signal"):
            assert запретное not in имена, f"в помощнике вызывается {запретное}"
        строки = {s.value for у in ast.walk(дерево)
                  if isinstance(у, ast.Constant) and isinstance(у.value, str)
                  for s in [у]}
        for запретное in ("pkill", "killall"):
            assert not any(запретное in с for с in строки), (
                f"в помощнике есть строковый литерал {запретное}")

    def test_остановка_идёт_через_systemctl(self, помощник):
        дерево = ast.parse(Path(помощник.__file__).read_text(encoding="utf-8"))
        функция = next(у for у in ast.walk(дерево)
                       if isinstance(у, ast.FunctionDef) and у.name == "глагол_cancel_stuck")
        тело = ast.unparse(функция)
        assert "'systemctl', 'stop', unit" in тело


class TestСвидетельстваИКарантин:
    def test_частичная_сборка_переносится_а_не_удаляется(self, помощник):
        дерево = ast.parse(Path(помощник.__file__).read_text(encoding="utf-8"))
        функция = next(у for у in ast.walk(дерево)
                       if isinstance(у, ast.FunctionDef) and у.name == "глагол_cancel_stuck")
        тело = ast.unparse(функция)
        assert "shutil.move" in тело, "частичная сборка удаляется вместо карантина"
        assert "rmtree" not in тело

    def test_снимается_только_свой_dropin(self, помощник):
        дерево = ast.parse(Path(помощник.__file__).read_text(encoding="utf-8"))
        функция = next(у for у in ast.walk(дерево)
                       if isinstance(у, ast.FunctionDef) and у.name == "глагол_cancel_stuck")
        тело = ast.unparse(функция)
        assert "ДРОПИН" in тело and "LORDS_CANARY_SITE" in тело, (
            "drop-in снимается без проверки, что он наш"
        )
        assert "glob" not in тело, "drop-in ищется маской, а не по точному имени"

    def test_вердикт_различает_отмену_и_откат(self, помощник):
        текст = Path(помощник.__file__).read_text(encoding="utf-8")
        assert "STALE_RENDER_CANCELLED_NO_CHANGE" in текст
        assert "RELEASES_CHANGED" in текст, (
            "смена релиза во время отмены обязана называться иначе")

    def test_доказательство_застоя_измеряет_пять_признаков(self, помощник):
        дерево = ast.parse(Path(помощник.__file__).read_text(encoding="utf-8"))
        функция = next(у for у in ast.walk(дерево)
                       if isinstance(у, ast.FunctionDef) and у.name == "_доказать_застой")
        тело = ast.unparse(функция)
        for признак in ("files_growth", "bytes_growth", "limit_events_growth",
                        "memory_ratio", "renderer_revisions"):
            assert признак in тело, f"признак {признак} не измеряется"


class TestЗанятостьЮнита:
    """Дефект LORDS-DEPLOYCTL-ACTIVATING-42.

    `systemctl is-active` для работающего oneshot отвечает `activating`, а не
    `active`. Проверка простоя сравнивала только с `active`, поэтому занятый
    юнит дважды был объявлен свободным: заявка подавалась в чужой прогон и
    присоединялась к нему вместо запуска своей. Оба раза это стоило часов.
    """

    def test_все_рабочие_состояния_считаются_занятыми(self, помощник):
        assert set(помощник.ЗАНЯТЫЕ_СОСТОЯНИЯ) == {
            "active", "activating", "deactivating", "reloading"}

    def test_ожидание_простоя_пользуется_общей_проверкой(self, помощник):
        import ast
        дерево = ast.parse(Path(помощник.__file__).read_text(encoding="utf-8"))
        функция = next(у for у in ast.walk(дерево) if isinstance(у, ast.FunctionDef)
                       and у.name == "глагол_canary")
        тело = ast.unparse(функция)
        assert "_занят(" in тело, "канарейка снова сравнивает состояние вручную"
        assert "== 'active'" not in тело, "сравнение с одним 'active' вернулось"
