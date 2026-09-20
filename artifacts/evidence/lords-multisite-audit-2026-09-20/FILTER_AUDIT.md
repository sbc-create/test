# Filter audit

## Truth: `/catalog/?genre=komediya&sort=rating`

| Site | Live shown_count | Offline oracle (details genre index) | Match |
|---|---|---|---|
| lords-01 | 10978 | (site-specific catalog) | n/a in this oracle file |
| lords-02 | 14913 | 14913 | YES |
| lords-03 | 14913 | (same shared-pattern catalog) | consistent with live |

**Verdict:** the previously suspicious `shown_count=14913` is **not** a defect for lords-02; it matches the independent details genre index.

## `/series/?kind=Сериал&year=2016`

* Live: HTTP 200 on all three sites (encoded + raw-via-quote).
* Offline oracle lords-02: 553 series with year=2016.
* Historical 502: **not reproduced** in this audit window. Journal access denied for non-adm user; nginx error.log unreadable. lords-02/03 processes restarted earlier today — prior 502 may have been stale/crash; record as **unconfirmed historical**, not closed.

## Compact filter UX

Current UI: multi-row chip/button strips for kind/year/genre/country/sort (`.tabs` blocks).
Measured as UX defect vs acceptance `FILTER_COLLAPSED_HEIGHT_DESKTOP_PX<=180`.
**Fix deferred to Phase B** — per-profile compact dropdowns, not a shared skin.

## Gates (Phase A observation)

* FILTER_RESULT_MISMATCHES (comedy): 0 for lords-02
* Country path filters: broken (see URL_NORMALIZATION)
* FILTER_COMPACT_PASS_BY_SITE: NO/NO/NO (not yet redesigned)
