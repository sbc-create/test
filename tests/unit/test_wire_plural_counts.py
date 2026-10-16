"""automation/local/wire-plural-counts.py: склонение числа серий/сезонов в шаблоне Lords."""
import importlib.util
import pathlib
import shutil
import subprocess
import sys

КОРЕНЬ = pathlib.Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location("wire_plural", КОРЕНЬ / "automation/local/wire-plural-counts.py")
м = importlib.util.module_from_spec(spec)
spec.loader.exec_module(м)

ОБРАЗЕЦ = '''import html


def всего_серий(деталь: dict) -> int:
    return 0


def факты(сезоны, серий, хвост):
    return (f"Сезон {сезоны[-1].get('n') or len(сезоны)} · {серий} серий{хвост}"
            if len(сезоны) == 1 else
            f"{len(сезоны)} сезона, {серий} серий{хвост}")


def блок(сезон, хвост, серий):
    return (f'<span>{сезон["eps"]} серий{хвост}</span>'
            f'<p>В сезоне {серий} серий. Далее</p>')


def всего(сезоны):
    return (f'<p>Всего в произведении {sum(с["eps"] for с in сезоны) or "?"} '
            f'серий · далее</p>')
'''
ПРОГОН = '''#!/usr/bin/env bash
check "records-plural"     python3 checks/records_plural.py
exit "$fail"
'''


def _копия(имя: str) -> pathlib.Path:
    корень = КОРЕНЬ / "var" / "test-wire-plural" / имя
    shutil.rmtree(корень, ignore_errors=True)
    (корень / "src").mkdir(parents=True)
    (корень / "src" / "lords-frontend.py").write_text(ОБРАЗЕЦ, encoding="utf-8")
    (корень / "checks").mkdir()
    (корень / "checks" / "run.sh").write_text(ПРОГОН, encoding="utf-8")
    return корень


def _проверка(к: pathlib.Path) -> int:
    return subprocess.run([sys.executable, "checks/plural_counts.py"], cwd=к, capture_output=True).returncode


def test_склонение_и_повтор():
    к = _копия("a")
    shutil.copy(КОРЕНЬ / "automation/host/plural_counts_check.py", к / "checks/plural_counts.py")
    assert _проверка(к) == 1  # на исходном шаблоне проверка видит дефект
    assert м.главная(["--repo", str(к)]) == 0
    assert _проверка(к) == 0
    прогон = (к / "checks/run.sh").read_text(encoding="utf-8").splitlines()
    assert прогон[2].startswith('check "plural-counts"') and прогон[1].startswith('check "records-plural"')
    ns: dict = {}
    exec((к / "src/lords-frontend.py").read_text(encoding="utf-8"), ns)
    assert ns["факты"]([{"n": 1}], 24, "") == "Сезон 1 · 24 серии"
    assert ns["факты"]([{"n": 1}, {"n": 2}], 21, ", доступно 9") == "2 сезона, 21 серия, доступно 9"
    assert ns["факты"]([{}] * 5, 11, "") == "5 сезонов, 11 серий"
    assert ns["блок"]({"eps": 1}, "", 52) == "<span>1 серия</span><p>В сезоне 52 серии. Далее</p>"
    assert ns["всего"]([{"eps": 21}, {"eps": 2}]) == "<p>Всего в произведении 23 серии · далее</p>"
    assert ns["всего"]([]) == "<p>Всего в произведении ? серий · далее</p>"
    до = (к / "src/lords-frontend.py").read_text(encoding="utf-8")
    assert м.главная(["--repo", str(к)]) == 0
    assert (к / "src/lords-frontend.py").read_text(encoding="utf-8") == до


def test_сухой_прогон_не_пишет():
    к = _копия("b")
    assert м.главная(["--repo", str(к), "--dry-run"]) == 0
    assert (к / "src/lords-frontend.py").read_text(encoding="utf-8") == ОБРАЗЕЦ
    assert (к / "checks/run.sh").read_text(encoding="utf-8") == ПРОГОН
    assert not (к / "checks/plural_counts.py").exists()


LORDS02 = '''def карточка(доступно, заявлено):
    class Т:
        @staticmethod
        def склонение(n, одна, две, много):
            n = abs(int(n))
            if 11 <= n % 100 <= 14:
                return много
            return одна if n % 10 == 1 else (две if 2 <= n % 10 <= 4 else много)
    return (f'<b>{доступно}</b> из '
            f"{заявлено} серий доступно</span>")
'''


def test_lords02_родительный_после_из():
    к = _копия("c")
    (к / "src" / "lords02_view.py").write_text(LORDS02, encoding="utf-8")
    shutil.copy(КОРЕНЬ / "automation/host/plural_counts_check.py", к / "checks/plural_counts.py")
    assert м.главная(["--repo", str(к)]) == 0
    assert _проверка(к) == 0
    ns: dict = {}
    exec((к / "src/lords02_view.py").read_text(encoding="utf-8"), ns)
    assert ns["карточка"](70, 201) == "<b>70</b> из 201 серии доступно</span>"
    assert ns["карточка"](6, 44) == "<b>6</b> из 44 серий доступно</span>"
    assert ns["карточка"](6, 11) == "<b>6</b> из 11 серий доступно</span>"
