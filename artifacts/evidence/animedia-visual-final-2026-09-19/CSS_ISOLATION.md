# CSS_ISOLATION

Animedia 1.2.4 styles are confined to `АНИМЕДИА_СТИЛЬ` + token substitution.

Guards verified by unit tests:

- No Animedia rule of the form `img,video,iframe{max-width:100%;height:auto}` inside `АНИМЕДИА_СТИЛЬ`.
- Player iframes sized only under `.zpl__f iframe` with `width/height:100% !important`.
- `[hidden]` semantics preserved: `.zpl [data-player-state][hidden],.zpl__s[hidden]{display:none !important}` only.
- Empty ads: `.zad,.zad-home,.zad-mid,.zad-title{display:none;height:0;margin:0}`.
- Shared `ОБЩЕЕ_1_1` still has a global img/iframe reset for all families; Animedia player overrides remain scoped and `!important`.
