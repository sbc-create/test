"""REQ-SEO-EXPOSURE-CLASSIFIER: признак раскрытия судит по имени И по значению.

Инструмент `healthz-exposure.py` отвечает на вопрос «сколько полей служебного
ответа описывают устройство машины». Признак дважды оказывался слишком узким,
и оба раза это измерялось, а не обсуждалось:

1. закрытый перечень имён (десять штук) находил 4 поля там, где раскрывающих
   было около 21 — поля добавляются выпусками, и каждое новое по умолчанию
   считалось безобидным;
2. перечень ВИДОВ имени (`_path`, `_sha256`, …) на animeg0.site нашёл 10
   полей, а разбор по смыслу у линии animego — 15. Разница: поле с путём
   внутри, названное иначе, и список файлов артефакта (признак умел смотреть
   строки, но не списки).

После правки признак даёт на том же ответе 15 — столько же, сколько разбор по
смыслу. Счёт при этом остаётся НИЖНЕЙ оценкой, и инструмент это печатает.
"""
from __future__ import annotations

import importlib.util
from pathlib import Path

ПУТЬ = (Path(__file__).resolve().parents[2] / "automation" / "local"
        / "healthz-exposure.py")


def _модуль():
    спец = importlib.util.spec_from_file_location("healthz_exposure", ПУТЬ)
    м = importlib.util.module_from_spec(спец)
    спец.loader.exec_module(м)
    return м


МОД = _модуль()


def test_состояние_службы_не_раскрытие():
    """Отрицательный контроль: иначе «починкой» стало бы пустое поле."""
    assert МОД.раскрывает("ok", True) is False
    assert МОД.раскрывает("runtime_digest_match", True) is False


def test_путь_опознаётся_по_имени():
    assert МОД.раскрывает("runtime_path", "/srv/x/y/z.py") is True
    assert МОД.раскрывает("release_dir", "/srv/x/releases/aaa") is True


def test_путь_опознаётся_по_значению_при_чужом_имени():
    """Тот случай, который признак по имени терял.

    Измерено на animeg0.site: поле `bound_release_link` со значением-путём.
    """
    assert МОД.раскрывает("bound_release_link", "/srv/animeg0-site/current") is True


def test_сумма_и_коммит_опознаются_по_значению():
    assert МОД.раскрывает("whatever", "a" * 64) is True
    assert МОД.раскрывает("whatever", "b" * 40) is True


def test_список_путей_опознаётся():
    """Поле со списком путей раскрывает столько же, сколько поле с одним."""
    assert МОД.раскрывает("files", ["/srv/a/b/c.py", "x"]) is True


def test_имя_юнита_это_настройка_машины():
    """`service_name` — тот же `unit` под другим именем (измерено)."""
    assert МОД.раскрывает("service_name", "nova-animeg0-site.service") is True


def test_про_витрину_а_не_про_машину_не_раскрытие():
    """Граница названа явно: это про витрину, и опознавать их нельзя.

    Иначе признак начал бы считать раскрытием любое поле, и число перестало
    бы что-либо значить.
    """
    for имя, значение in (("design_version", "1.4.0"),
                          ("expected_indexability", "open"),
                          ("details_coverage", 8649),
                          ("domain", "animeg0.site"),
                          ("template_family", "animego")):
        assert МОД.раскрывает(имя, значение) is False, имя


def test_короткая_строка_со_слэшем_не_путь():
    """Отрицательный контроль к признаку по значению: «index, follow» и
    «noindex/nofollow» путями не являются."""
    assert МОД.раскрывает("robots", "index, follow") is False
    assert МОД.раскрывает("mode", "open/closed") is False
