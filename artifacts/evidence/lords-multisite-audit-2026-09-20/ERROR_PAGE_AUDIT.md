# Error page audit

* Expected unknown URL → HTTP 404 with site template (`Такой страницы на витрине нет`) on all three — PASS (not soft-404).
* `X-Robots-Tag: noindex, nofollow` set on responses via handler.
* Infrastructure: HTTP error responses may expose `Server: nginx/1.18.0` (infra finding; no change without approval).
* Country facet 404s use the same branded 404 page (correct status, wrong that the link exists).
