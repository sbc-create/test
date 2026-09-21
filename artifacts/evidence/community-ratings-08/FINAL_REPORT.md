# COMMUNITY-RATINGS-08 — WIDGET & OBSERVABILITY — FINAL REPORT

```text
VERDICT=READY_FOR_OWNER_DEPLOY
STAGE=COMMUNITY-RATINGS-08-WIDGET-OBSERVABILITY
BRANCH=cursor/ratings-ingestion-01
START_HEAD=58834386001603e8ab12c6bdf0dd269347635389
TESTS=228_PASS_x2
TEST_RUNS_CONSECUTIVE=2
WORKTREE_CLEAN=YES (source paths; one pre-existing unrelated change in tests/operator)
SOURCE_ARTIFACT_RUNTIME_MATCH=PREPARED_AND_VERIFIED_NOT_YET_INSTALLED
WIDGET_SOURCE_IMPLEMENTED=YES
WIDGET_DEPLOYED_LIVE=NO (privileged install pending)
PUBLIC_WRITE_ROLLOUT_PERCENT=1
OBSERVATION_OLD_WINDOW_DISCARDED=YES
MIN_24H_COMPLETE=NO
READY_FOR_OWNER_10PCT_APPROVAL=NO
```

## What this stage did

COMMUNITY-RATINGS-07 found the 1% canary had run 15.5 hours with **zero
exposure**: the API was live, but no page ever offered the widget. This stage
built the widget onto the real integration point, rebuilt the measurement layer
so it cannot report zeros it never measured, and prepared a verified release.

One thing is left, and it is genuinely privileged.

## Why the deploy was not performed

| | |
| --- | --- |
| `/srv/lords/.frontend/yummy-frontend.py` | `root:root 0755` — not writable |
| `sudo` | blocked: `[factory-guard G-PRIV] Неконтролируемый sudo/su запрещён` |
| `systemctl restart` | requires root |

The containing directory *is* writable, so the file could have been replaced by
unlink-and-create. That was deliberately not done: it would silently turn a
root-owned runtime file into one owned by this session — circumventing a
privilege boundary rather than deploying through it.

**One unit serves the domain:** `nova-yummy-site.service` → `yummyani.site`
(`YUMMY_VARIANT_DOMAIN=yummyani.site`, port 9132). `nova-yummy-org.service` and
`nova-yummy-biz.service` are untouched. The command also restarts
`community-ratings-gateway.service`, which already runs this worktree's code
from disk but holds the old code in memory.

The exact command is in
[`04-deploy/OWNER_DEPLOY_COMMAND.md`](04-deploy/OWNER_DEPLOY_COMMAND.md).

## The integration point, and why it is the only safe one

The frontend refuses to rewrite upstream markup on purpose: nodes inside the
React tree broke hydration (`Minified React error #418`) and took the whole
client side down, and foreign pages are streamed rather than buffered to keep
TTFB at 0.2 s instead of 1.2 s.

Both constraints hold:

- exactly **one** `<script>` is injected, as the **last node of `<body>`** —
  the one position this frontend's own history shows to be safe. Nothing enters
  `<head>`, nothing enters the app tree;
- injection runs through a rolling tail window holding back fewer bytes than
  `</body>` is long, so pages still stream. A full fetch of the patched
  artifact measured **0.79 s**;
- `Content-Length` is adjusted by exactly the injected length — without it the
  browser truncates the document by that many bytes.

The widget then waits for `load` and mounts a fixed-position panel appended to
`<body>`: outside the framework tree, outside document flow.

## Verified in a real browser, before asking anyone to install it

A local harness ran the real gateway, the real frontend and the real Next.js
upstream against scratch data. Eligibility was obtained by minting an identity
that genuinely falls in bucket 0 under the local salt — **the 1% gate was never
widened**.

| Check | Result |
| --- | --- |
| Cast → update → retract | `7.0` → `9.0` → «Пока нет пользовательских оценок» |
| Repeat vote | one active row, never a second |
| Preview vs write | identical, 4 scores checked live plus 73 transitions in tests |
| Ineligible visitor | loader tag present, **widget never mounts** |
| Kill switch / read-only | loader node withdrawn entirely (1 → 0), restored after |
| Console errors | **0**, with and without the injection |
| Layout shift attributable to the widget | **0.0** — every shift traced to the host app's own `portal-*` elements |
| Page geometry before/after mount | unchanged |
| Responsive 320/390/768/1024/1440/1920 | panel fits, no horizontal page scroll |
| Keyboard | all controls tabbable, `aria-label` on each, `radiogroup` + `aria-checked`, visible `:focus-visible` outline |
| No JavaScript | page renders, widget simply absent |
| API dead | page keeps rendering, no page errors |
| Assets | `200`, correct content types, `nosniff` |

The release artifact itself — built from the **live** runtime file, not the repo
copy — was then run and re-verified: one loader node on a known title, zero on
an unknown slug, zero on the home page, zero under the kill switch.

## Observability: the zeros are gone

`monitor_once` ran in its own process and snapshotted its own empty counters, so
all 63 Stage07 ticks published structural zeros that read like measurements.

Counters now go to a SQLite sink the gateway writes and any process reads. The
rules are explicit:

- a counter never recorded → `UNMEASURED` with a reason, never `0`;
- an unreachable store → `UNMEASURED` with a reason, never `0`;
- a counter recorded as zero → `MEASURED 0`, a real observation;
- a **refused** write → counted and surfaced; affected counters become
  `PARTIAL` and are described as a lower bound.

Every metric carries provenance: source, window, last update. Exposure is
counted server-side from a beacon the mounted widget sends, accepted only from a
genuinely eligible identity — the injector can only attest the widget was
*offered*. Distinct visitors are counted through a keyed HMAC, so the store
answers "how many" without holding anything that identifies one.

## Two bugs found while building this

1. **Metric writes were being silently dropped.** The cached SQLite connection
   could not be used from `ThreadingHTTPServer`'s per-request threads; sqlite
   refused, the error was swallowed to protect the request, and counters read
   low — a fresh instance of the same silent-zero failure. Fixed, with a
   concurrency regression test. Afterwards the browser flow's cast, update and
   retract appeared in the store with real latency samples.

2. **Test runs wrote into production telemetry.** The store's default path is
   the production one — that default is what lets the monitor read what the
   gateway wrote — so any unisolated test writing through `metrics.incr` landed
   there. A full suite run had already put **37 cast attempts and 13 accepted
   casts** into the production store, and a monitor tick duly reported them as
   observations. Fixed with a package-level autouse fixture and two assertions
   that the redirect is in force. The polluted store was **deleted**; it held
   only test data, since the gateway still runs pre-deploy code and had never
   written to it.

   **The production ratings ledger was not affected**: 0 votes, 0 accepted,
   integrity `ok`, 57 historical `vote_events` from the Stage06 canary unchanged.

A third, smaller one: `CommunityStore` called `.parent` on a `str`, so the
gateway's `--db` flag crashed before the service could start.

## Pre-deploy gates

| Gate | Result |
| --- | --- |
| Rollback prepared | 2 levels; flag-only rollback needs no privileges and was verified |
| Artifact digests + manifest | recorded; 7 named patches, every anchor asserted unique |
| Source clean at build | yes |
| Exact-domain binding | `nova-yummy-site.service` → `yummyani.site` only |
| Rollout percent | exactly **1**, max 1 |
| Kill switch | ready, state 0, verified by toggling |
| DB backup + integrity | `ok`, 0 FK failures, 0 votes |

## Live baseline (two consecutive runs, pre-deploy)

Widget absent, assets 404, rollout 1, kill switch 0, `yummyani.site` **OPEN**,
Animedia `CLOSED_NOINDEX` unchanged, no `aggregateRating`, no Shikimori on any
page, all title pages 200 with well-formed HTML and consistent `Content-Length`.

## The observation window has not started, and cannot be faked

Stage07's 15.544 hours are discarded: there was no exposure to observe.

`06-observation/start_observation.py` refuses to record a start time unless six
conditions hold at once — widget on a live page, assets served, rollout exactly
1% and live, metrics store reachable, **at least one real eligible impression
and one widget-rendered beacon**, and indexability still OPEN. Run now, it
correctly refuses:

```
READY_TO_START: False
FAILED: C1_widget_on_live_pages, C2_assets_served,
        C4_metrics_store_reachable, C5_real_exposure_recorded
```

It changes no flag and enables nothing. After the owner deploys, running it
opens the window — or explains exactly why it will not.

## Owner actions

1. Run the single command in `04-deploy/OWNER_DEPLOY_COMMAND.md`.
2. Run `06-observation/start_observation.py` to open the window on evidence.
3. Optional hardening: set `COMMUNITY_METRICS_PEPPER_FILE` to the existing
   `/etc/site-factory/secrets/community_ip_hmac` at the next wrapper edit.

No 10% approval is requested, and none is implied by this stage.
