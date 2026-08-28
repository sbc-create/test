"""Обложка показывается целиком, а не обрезанной по краям.

Источник отдаёт вертикальные постеры. Два профиля из трёх выводили их в рамке
3:2 и 16:9, а картинка растягивается по кадру `object-fit: cover` — то есть у
вертикального постера срезался верх и низ. На витрине это выглядело как набор
случайно обрезанных картинок, и три домена вдобавок выглядели по-разному:
1.5 у одного, 1.33 у другого.
"""
from __future__ import annotations

from factory.lords import plan as plan_mod
from factory.lords import theme as theme_mod

PRODUCT = ("lords-general", "lords-new", "lords-curated")


def _ratios() -> dict:
    profiles = plan_mod.load_profiles()
    return {name: theme_mod.layout_of(profile)["card_ratio"]
            for name, profile in profiles.items()}


class TestPosterFrameMatchesThePoster:
    def test_every_profile_frames_posters_upright(self):
        for name, ratio in _ratios().items():
            width, height = (int(part) for part in ratio.split("/"))
            assert height > width, f"{name}: кадр {ratio} шире, чем выше"

    def test_the_product_domains_use_one_and_the_same_frame(self):
        ratios = _ratios()
        assert len({ratios[name] for name in PRODUCT}) == 1

    def test_the_frame_is_the_usual_poster_proportion(self):
        for name in PRODUCT:
            assert _ratios()[name].replace(" ", "") == "2/3", name

    def test_the_ratio_reaches_the_stylesheet(self):
        profiles = plan_mod.load_profiles()
        for name in PRODUCT:
            css = theme_mod.stylesheet(profiles[name])
            assert "--card-ratio: 2 / 3;" in css, name
            assert "aspect-ratio: var(--card-ratio)" in css, name
