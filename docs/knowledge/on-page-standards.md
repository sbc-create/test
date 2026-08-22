# On-page standards

These are the constraints encoded in
[`page-metadata.schema.json`](../../schemas/page-metadata.schema.json). Data
that violates them fails validation, so treat them as hard limits rather than
style preferences.

## Title tags

- **Length: 1-60 characters.** Beyond roughly 60 the title is truncated in
  results. The schema enforces 60 as a hard ceiling.
- One title per page, unique across the site. Duplicate titles across templated
  pages are the single most common on-page finding.
- Front-load the distinguishing term. "Technical SEO Guide | Example" beats
  "Example | Technical SEO Guide" because truncation eats the end.
- Describe the page, not the site. The brand belongs at the end, if at all.

## Meta descriptions

- **Length: 1-160 characters.** Not a ranking factor directly, but it is the
  copy that determines whether a result gets clicked.
- Unique per page. A templated description repeated site-wide is worth less
  than none, because search engines will rewrite it anyway.
- Include the primary keyword where it is natural — matched terms are bolded in
  results, which draws the eye.

## Headings

- Exactly one `H1` per page. The schema stores `h1` as an array precisely so
  that a page with two can be detected and reported.
- Heading levels descend without skipping (`H1` then `H2`, not `H1` then `H3`).
- Headings describe the section beneath them. They are a document outline, not
  a styling mechanism.

## Canonicals

- Self-referencing by default. Omit the `canonical` field in page metadata when
  it points at the page's own URL.
- A canonical is a strong hint, not a directive. Conflicting signals (canonical
  to A, sitemap lists B, internal links point to C) get resolved by the search
  engine, not by you.

## Structured data

- Record the `@type` values present in `structured_data_types`.
- Markup must describe content visible on the page.
- Prefer JSON-LD over microdata: it is separable from the markup and therefore
  survives template changes.

## Word count

`word_count` is recorded because it is diagnostically useful — a page with 40
words competing against pages with 2,000 is worth flagging — but it is **not a
target**. There is no threshold that makes a page rank. Do not produce
recommendations of the form "increase this page to N words".

## Indexability

`indexable` is false when *any* of these is true: blocked in `robots.txt`,
carries `noindex`, requires authentication, or returns a non-200 status. When
reporting a non-indexable page, state which of those caused it.
