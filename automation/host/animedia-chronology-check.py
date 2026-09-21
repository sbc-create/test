#!/usr/bin/env python3
"""Проверка хронологии Animedia на отрисованных страницах.

Правильная сортировка в коде ничего не гарантирует на странице: порядок может
разойтись при нормализации, при сборке разметки и ещё раз в сетке, если она
раскладывает элементы по колонкам сверху вниз. Поэтому сверяются четыре
порядка: ожидаемый по снимку, порядок в разметке, визуальный порядок (сверху
вниз, слева направо) и порядок между страницами листалки.

    .venv/bin/python automation/host/animedia-chronology-check.py \\
        --runtime automation/host/animedia-frontend.py --out <каталог>
"""
from __future__ import annotations

import argparse
import json
import os
import socket
import subprocess
import sys
import time
from pathlib import Path

КОРЕНЬ = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(КОРЕНЬ))

from factory.animedia import chronology as хронология  # noqa: E402

ШИРИНЫ = (390, 1440)
СТРАНИЦЫ = ("/collection/recently_added/", "/collection/recently_added/?page=2",
            "/collection/recently_added/?page=3")

ПОРЯДОК = r"""
() => {
  const видим = (el) => {
    const r = el.getBoundingClientRect(), s = getComputedStyle(el);
    return r.width > 0 && r.height > 0 && s.visibility !== 'hidden' && s.display !== 'none';
  };
  const карточки = [...document.querySelectorAll('.zg a.zt')].filter(видим);
  const в_разметке = карточки.map((к) => к.getAttribute('href'));
  // Визуальный порядок: сверху вниз, затем слева направо. Ряды считаются с
  // допуском, иначе карточки разной высоты рассыпаются по мнимым рядам.
  const с_коробками = карточки.map((к) => {
    const r = к.getBoundingClientRect();
    return {href: к.getAttribute('href'), x: Math.round(r.x),
            y: Math.round(r.y + window.scrollY)};
  });
  const допуск = 24;
  const визуально = [...с_коробками].sort((a, b) =>
    (Math.abs(a.y - b.y) > допуск ? a.y - b.y : a.x - b.x)).map((к) => к.href);
  return {dom: в_разметке, visual: визуально, count: карточки.length};
}
"""


def поднять(рантайм: Path, витрина: str, лог: Path):
    корень = Path(os.environ.get("ANIMEDIA_RUNTIME_ROOT", "/srv/lords/.frontend"))
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        порт = s.getsockname()[1]
    окр = dict(os.environ)
    окр.update({"ANIMEDIA_TEMPLATE_MANIFEST": str(корень / f"template-manifest-{витрина}.json"),
                "ANIMEDIA_CATALOG": str(корень / f"{витрина}-catalog.json"),
                "ANIMEDIA_SITE_NAME": "Animedia", "PYTHONDONTWRITEBYTECODE": "1"})
    for чужое in ("LORDS_TEMPLATE_MANIFEST", "LORDS_CATALOG", "LORDS_DETAILS"):
        окр.pop(чужое, None)
    p = subprocess.Popen(["/usr/bin/python3", str(рантайм), "--port", str(порт)],
                         stdout=лог.open("w", encoding="utf-8"),
                         stderr=subprocess.STDOUT, env=окр, cwd=str(КОРЕНЬ))
    for _ in range(600):
        time.sleep(0.5)
        if p.poll() is not None:
            raise SystemExit(f"рантайм не поднялся, см. {лог}")
        try:
            with socket.create_connection(("127.0.0.1", порт), timeout=0.5):
                return p, порт
        except OSError:
            continue
    raise SystemExit("порт не открылся")


def main() -> int:
    р = argparse.ArgumentParser(description=__doc__)
    р.add_argument("--runtime", default="automation/host/animedia-frontend.py")
    р.add_argument("--site", default="animedia-01")
    р.add_argument("--domain", default="animedia.icu")
    р.add_argument("--out", required=True)
    a = р.parse_args()
    вывод = Path(a.out)
    вывод.mkdir(parents=True, exist_ok=True)

    корень_рантайма = Path(os.environ.get("ANIMEDIA_RUNTIME_ROOT", "/srv/lords/.frontend"))
    снимок = json.loads((корень_рантайма / f"{a.site}-catalog.json").read_text(encoding="utf-8"))
    записи = снимок["items"] if isinstance(снимок, dict) else снимок
    ожидаемый = [з["url"] for з in хронология.по_добавлению(записи)]
    нарушения_снимка = хронология.проверить_порядок(хронология.по_добавлению(записи))

    процесс, порт = поднять(Path(a.runtime), a.site, вывод / "runtime.log")
    from playwright.sync_api import sync_playwright

    итог = {"task": "ANIMEDIA-CHRONOLOGY-CHECK", "tenant": "animedia",
            "checked_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "snapshot_items": len(записи),
            "snapshot_order_violations": нарушения_снимка[:5],
            "expected_head": ожидаемый[:5], "pages": [], "failures": []}
    провалы = итог["failures"]
    правило = f"MAP {a.domain} 127.0.0.1:{порт}"
    try:
        with sync_playwright() as pw:
            b = pw.chromium.launch(args=[f"--host-resolver-rules={правило}"])
            try:
                for ширина in ШИРИНЫ:
                    ctx = b.new_context(viewport={"width": ширина, "height": 900})
                    стр = ctx.new_page()
                    все_страницы: list[list[str]] = []
                    for путь in СТРАНИЦЫ:
                        стр.goto(f"http://{a.domain}{путь}", wait_until="load", timeout=60000)
                        стр.wait_for_timeout(250)
                        п = стр.evaluate(ПОРЯДОК)
                        ключ = f"{путь}@{ширина}"
                        итог["pages"].append({"path": путь, "width": ширина, **п})
                        все_страницы.append(п["dom"])
                        if п["dom"] != п["visual"]:
                            расхождение = next(
                                (i for i, (д, в) in enumerate(zip(п["dom"], п["visual"]))
                                 if д != в), None)
                            провалы.append(
                                f"{ключ}: визуальный порядок расходится с разметкой "
                                f"с позиции {расхождение}")
                        # Ожидаемый срез для этой страницы берётся из снимка.
                        начало = СТРАНИЦЫ.index(путь) * п["count"]
                        срез = ожидаемый[начало:начало + п["count"]]
                        if п["dom"] != срез:
                            где = next((i for i, (д, э) in enumerate(zip(п["dom"], срез))
                                        if д != э), min(len(п["dom"]), len(срез)))
                            провалы.append(
                                f"{ключ}: порядок в разметке расходится с порядком снимка "
                                f"с позиции {где}: {п['dom'][где:где + 2]} вместо {срез[где:где + 2]}")
                        print(f"  {ширина:>5} {путь:<44} карточек {п['count']:>3} "
                              f"первая {п['dom'][0] if п['dom'] else '—'}", flush=True)
                    подряд = [h for стр_ in все_страницы for h in стр_]
                    повторы = len(подряд) - len(set(подряд))
                    if повторы:
                        провалы.append(f"@{ширина}: {повторы} повторов карточек между страницами")
                    ctx.close()
            finally:
                b.close()
    finally:
        процесс.terminate()
        try:
            процесс.wait(timeout=20)
        except subprocess.TimeoutExpired:
            процесс.kill()
    итог["CHRONOLOGY_PASS"] = not провалы and not нарушения_снимка
    (вывод / "CHRONOLOGY_CHECK.json").write_text(
        json.dumps(итог, ensure_ascii=False, indent=1), encoding="utf-8")
    print("CHRONOLOGY_PASS:", итог["CHRONOLOGY_PASS"])
    for f in провалы[:10]:
        print("  провал:", f)
    return 0 if итог["CHRONOLOGY_PASS"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
