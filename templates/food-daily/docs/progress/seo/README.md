# Технический SEO-аудит 30 превью (13.10.2026)

`seo-audit.json` — обход всех URL sitemap и внутренних ссылок (ответ, canonical, title/description, h1, lang, JSON-LD, noindex, alt, битые ссылки).
`seo-snip.json` — длины title/description и обязательные поля JSON-LD (Recipe, HowTo, VideoObject и др.).

Скрипты обходят превью всех сайтов, поэтому в шаблоне не хранятся (тест изоляции); это инструменты сессии:

| файл | sha256 |
| --- | --- |
| `seo_audit.py` | `b8725f589552d34619a575edf4f96e430949950c8ab7c2fe03a8c447087fe04a` |
| `seo_snip.py` | `bd80ce7e4d8e025968864904a9a78fed6a303115aa92e3d75aed52229fb5c2ca` |
