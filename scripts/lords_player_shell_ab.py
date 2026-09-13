#!/usr/bin/env python3
"""Два макета внешней оболочки плеера — материал для решения владельца.

Ни один из макетов не подключается к рантайму и настоящего плеера не
содержит: внутри прямоугольник с сеткой, обозначающий область видео. Менять
плеер, его настройку и поведение нельзя, а сравнивать высоту оболочки нужно.

A — нынешняя безопасная геометрия: оболочка follows контейнер, высота из
    соотношения 16:9.
B — высота 460 px при ширине контейнера, как в единственном замере
    референса (1100×460, соотношение 2.39).

    python3 scripts/lords_player_shell_ab.py --out var/player-ab
"""
from __future__ import annotations

import argparse
import pathlib

ШАБЛОН = """<!doctype html>
<html lang="ru"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Оболочка плеера — вариант {буква}</title>
<style>
  :root {{ --container: 1100px; --gutter: 5px; --gutter-wide: 12px;
           --bg: #111111; --surface: #1c1c1c; --border: #353535;
           --text: #e6e6e6; --muted: #9a9a9a; }}
  * {{ box-sizing: border-box; }}
  body {{ margin: 0; background: var(--bg); color: var(--text);
          font: 14px/1.5 'Open Sans', 'Segoe UI', Roboto, Arial, sans-serif; }}
  .container {{ width: calc(100% - 2 * var(--gutter)); max-width: var(--container);
                margin: 0 auto; }}
  @media (min-width: 1024px) {{ .container {{ width: calc(100% - 2 * var(--gutter-wide)); }} }}
  header {{ background: var(--surface); border-bottom: 1px solid var(--border); }}
  .header-row {{ display: flex; align-items: center; min-height: 70px; }}
  h1 {{ font-size: 18px; font-weight: 600; margin: 16px 0 8px; }}
  .meta {{ color: var(--muted); margin-bottom: 12px; }}
  /* Область видео. Настоящего плеера здесь нет и быть не должно. */
  .player-shell {{ position: relative; background: #000; border: 1px solid var(--border);
                   {геометрия} }}
  .player-shell::after {{ content: "{подпись}"; position: absolute; inset: 0;
      display: flex; align-items: center; justify-content: center;
      color: #6a6a6a; font-size: 13px; letter-spacing: .02em;
      background-image: linear-gradient(45deg, #0c0c0c 25%, transparent 25%),
                        linear-gradient(-45deg, #0c0c0c 25%, transparent 25%);
      background-size: 24px 24px; }}
  {дополнительно}
  .after {{ margin-top: 16px; display: grid; gap: 12px;
            grid-template-columns: repeat(auto-fill, minmax(160px, 1fr)); }}
  .card {{ background: var(--surface); border: 1px solid var(--border); }}
  .card__poster {{ aspect-ratio: 2 / 3; background: #222; display: block; }}
  .card__title {{ display: block; padding: 8px; font-size: 14px; }}
</style></head>
<body>
<header><div class="container header-row"><strong>Lords</strong></div></header>
<main class="container">
  <h1>Название произведения</h1>
  <div class="meta">2024 · Фильм · 1 ч 52 мин</div>
  <div class="player-shell"></div>
  <div class="after">
    {карточки}
  </div>
</main>
</body></html>
"""

ВАРИАНТЫ = {
    "A": {"геометрия": "aspect-ratio: 16 / 9;",
          "подпись": "область видео — вариант A, 16:9",
          "дополнительно": ""},
    # Вариант B повторяет замер референса ЦЕЛИКОМ, а не одну его строку.
    # Высота 460 px измерена с 768; на 390 у референса 300 px. Задать 460
    # везде значило бы показать владельцу оболочку 380×460 — выше своей
    # ширины, — которой у референса нет, и решение принималось бы по
    # искажённой картине.
    "B": {"геометрия": "height: 300px;",
          "подпись": "область видео — вариант B, высота по замеру референса",
          "дополнительно": "@media (min-width: 768px) { .player-shell { height: 460px; } }"},
}


def главное(аргв=None) -> int:
    р = argparse.ArgumentParser(description=__doc__)
    р.add_argument("--out", default="var/player-ab")
    а = р.parse_args(аргв)
    куда = pathlib.Path(а.out)
    куда.mkdir(parents=True, exist_ok=True)
    карточки = "\n    ".join(
        '<div class="card"><span class="card__poster"></span>'
        f'<span class="card__title">Похожее {i}</span></div>' for i in range(1, 7))
    for буква, св in ВАРИАНТЫ.items():
        (куда / f"player-shell-{буква}.html").write_text(
            ШАБЛОН.format(буква=буква, карточки=карточки, **св), encoding="utf-8")
    print(f"макеты: {куда}/player-shell-A.html, {куда}/player-shell-B.html")
    return 0


if __name__ == "__main__":
    raise SystemExit(главное())
