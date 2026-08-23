# Technical SEO checklist

Work top to bottom. Each item earlier in the list can invalidate everything
after it: a page that cannot be crawled cannot be indexed, and a page that is
not indexed cannot rank, no matter how good its content is.

## 1. Crawlability

- [ ] `robots.txt` returns 200 and does not block resources the renderer needs
      (CSS, JS). Blocking those makes pages render incorrectly to a crawler.
- [ ] XML sitemap exists, returns 200, lists only canonical, indexable, 200-status URLs.
- [ ] Sitemap is referenced from `robots.txt`.
- [ ] No orphan pages: every page worth ranking is reachable by internal links.
- [ ] Crawl depth from the homepage to any commercially important page is <= 3 clicks.
- [ ] No crawl traps: faceted navigation, infinite calendars, and session IDs are
      either blocked or canonicalized.

## 2. Indexation

- [ ] Pages intended to rank do **not** carry `noindex`.
- [ ] Pages not intended to rank (internal search results, thin tag pages,
      staging) **do** carry `noindex`, and are not merely blocked in `robots.txt`
      — a blocked page cannot be crawled, so its `noindex` is never seen.
- [ ] `rel=canonical` is self-referencing by default; cross-domain or
      cross-URL canonicals are deliberate and documented.
- [ ] Canonical targets are themselves indexable and return 200.
- [ ] No conflicting signals: a page canonicalized elsewhere should not also be
      in the sitemap.

## 3. Status codes and redirects

- [ ] No soft 404s (a "not found" page returning 200).
- [ ] Redirect chains are at most one hop.
- [ ] No redirect loops.
- [ ] Permanent moves use 301, temporary use 302 — the distinction affects
      whether ranking signals transfer.
- [ ] Internal links point at final URLs, not at redirects.

## 4. Duplication

- [ ] One canonical URL per piece of content across protocol (http/https),
      host (www/non-www), trailing slash, and case.
- [ ] Parameterized URLs resolve to a canonical form.
- [ ] Paginated series handle their own canonicals correctly: page 2 canonicalizes
      to page 2, not to page 1.

## 5. Internationalization

- [ ] `hreflang` annotations are reciprocal — if A points to B, B points back to A.
- [ ] Every `hreflang` value is a valid BCP 47 code; `x-default` is present.
- [ ] `hreflang` targets are indexable and canonical.

## 6. Performance

- [ ] Core Web Vitals measured on field data, not only lab data. Lab data
      diagnoses; field data is what is assessed.
- [ ] Largest Contentful Paint element is identified per template, not per page.
- [ ] Layout shift sources traced to specific elements (usually images without
      dimensions, or late-injected banners).

## 7. Structured data

- [ ] JSON-LD parses and matches the visible page content.
- [ ] Types used are ones search engines actually consume for the page's purpose.
- [ ] Required properties for each type are present.
- [ ] No markup for content that is not on the page — that is a policy violation,
      not a clever trick.

## Recording results

Each failed item becomes a finding in an audit document that validates against
[`seo-audit.schema.json`](../../schemas/seo-audit.schema.json), with a
`category`, a `severity`, the `affected_urls`, and an `evidence` field naming
how it was checked.
