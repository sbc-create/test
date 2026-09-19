# PAGINATION_CONTRACT

- Route: `/new/` (home shows page 1 of the same query)
- page_size = 10
- page=1 canonical `/new/`
- page=N canonical `/new/?page=N`
- Invalid / out-of-range → HTTP 404 + existing not-found shell
- Prev/Next with aria-disabled at ends
- aria-current="page" on active page
- Home pager links to `/new/?page=N`
