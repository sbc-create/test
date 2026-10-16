"""automation/local/wire-plural-counts.py: склонение числа серий/сезонов в шаблоне Lords."""
import importlib.util
import pathlib
import shutil

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
'''


def _копия(имя: str) -> pathlib.Path:
    корень = КОРЕНЬ / "var" / "test-wire-plural" / имя
    shutil.rmtree(корень, ignore_errors=True)
    (корень / "src").mkdir(parents=True)
    (корень / "src" / "lords-frontend.py").write_text(ОБРАЗЕЦ, encoding="utf-8")
    return корень


def test_склонение_и_повтор():
    к = _копия("a")
    assert м.главная(["--repo", str(к)]) == 0
    ns: dict = {}
    exec((к / "src/lords-frontend.py").read_text(encoding="utf-8"), ns)
    assert ns["факты"]([{"n": 1}], 24, "") == "Сезон 1 · 24 серии"
    assert ns["факты"]([{"n": 1}, {"n": 2}], 21, ", доступно 9") == "2 сезона, 21 серия, доступно 9"
    assert ns["факты"]([{}] * 5, 11, "") == "5 сезонов, 11 серий"
    assert ns["блок"]({"eps": 1}, "", 52) == "<span>1 серия</span><p>В сезоне 52 серии. Далее</p>"
    до = (к / "src/lords-frontend.py").read_text(encoding="utf-8")
    assert м.главная(["--repo", str(к)]) == 0
    assert (к / "src/lords-frontend.py").read_text(encoding="utf-8") == до


def test_сухой_прогон_не_пишет():
    к = _копия("b")
    assert м.главная(["--repo", str(к), "--dry-run"]) == 0
    assert (к / "src/lords-frontend.py").read_text(encoding="utf-8") == ОБРАЗЕЦ
