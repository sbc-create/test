---
paths:
  - "factory/seo/**"
  - "themes/**"
  - "knowledge/SEO_INDEXABILITY_MATRIX.yaml"
---

# SEO

- Матрица `knowledge/SEO_INDEXABILITY_MATRIX.yaml` — вход для рендера, а не отчёт.
  Тип страницы без записи в матрице не рендерится (`BLOCKED_SEO`).
- indexable + 200 → абсолютный self-canonical. Canonical не указывает на redirect, 4xx,
  noindex или другой язык.
- Пагинация: серверные `<a href>`, self-canonical на каждой странице, один канонический
  URL для page 1, детерминированный порядок с tie-breaker, out-of-range → 404.
- Sitemap: только canonical + indexable + 200. Никаких redirects, 4xx, noindex, фильтров,
  поиска, staging-URL.
- `lastmod` меняется только при существенном изменении контента, не при каждом деплое.
- JSON-LD только по фактически присутствующим данным. `VideoObject` — только если видео
  доступно и является видимой существенной частью страницы.
- Фасеты индексируются только из allowlist пакета. Комбинаторные фильтры, сортировки и
  внутренний поиск — `noindex,follow` и вне sitemap.
- Удалённая страница — честный 404/410, не пустой 200.
