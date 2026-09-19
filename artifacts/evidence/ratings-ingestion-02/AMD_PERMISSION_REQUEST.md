# AMD.online permission request (NOT SENT)

Prepared for Stage 2. **Do not auto-send.**

## Recipient

Owner / rights contact of https://amd.online/

## Requested grant

We request written permission for Site Factory to:

1. Fetch public anime **detail pages** of the form
   `https://amd.online/{id}-{slug}.html` only.
2. Extract and store:
   - overall score (`multirating-itog-rateval`)
   - vote count (`multirating-itog-votes`)
   - component scores (story/actors/graph/sound)
   - titles (h1 / amd-sub)
   - stable numeric `source_id`
3. Cache observations with provenance URL, fetch time, content digest.
4. Display AMD scores on our Animedia templates with attribution.
5. Compute a **derivative** combined score:
   `animedia_blend_v1` = AMD baseline (weight capped at 100) + our users' votes.
6. Stop immediately on 403/429/CAPTCHA/challenge/robots change.

## Proposed operational limits

- concurrency = 1
- ≤ 0.1 request/sec (min 10s between requests)
- identifiable User-Agent with contact
- conditional GET / caching where possible
- daily new-coverage target up to 500 titles after approval
- deletion/revocation procedure on request

## Not requested

- search/query endpoints
- user profiles, comments, reactions
- voting endpoints
- video assets
- authenticated pages
- bypass of bot protection

## Response fields needed

- permitted fields list
- permitted endpoints
- frequency / daily volume
- storage & cache rules
- attribution text
- commercial display yes/no
- derivative formula yes/no
- revocation / deletion procedure
