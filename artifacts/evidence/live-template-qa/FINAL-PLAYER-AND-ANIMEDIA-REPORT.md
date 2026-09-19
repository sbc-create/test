# Final report — Lords player ep7 + Animedia parity — 2026-09-19

## Lords player (critical)

### Root cause episode 7 / «Эпизод 3»
Details snapshot: `avail=3`, `eps=9`. Provider playlist has **3 items** (Серия 1–3).  
`/season-1/episode-7/` mounted `<video-player episode="7">` while the episode list already marked 4–9 as `data-off`. CDNVideoHub has no episode 7 → control UI showed last available («Эпизод 3»).

### Why 15s timeout fired
Client starts a 15s timer after mounting the SDK. For a missing episode the provider never reached a stable playable ready for the requested number → «Плеер не поднялся».

### Fix (systemic)
`серия_с_дорожкой` + `разметка_плеера`: if `episode > avail` → `unavailable`, no SDK, no script. Same identity as list `data-off`.

### Commits
| Hash | Message |
| --- | --- |
| `a67bf79` | fix(lords): gate player mount on avail, not eps alone |
| `4ac8183` | chore(nova): point closed runtime at player avail-gate tip |
| `ea5c939` | docs(qa): evidence for lords player avail-gate live fix |
| `cc83fd7` | fix(animedia): hero poster rail and new-episodes list rhythm |
| `b647dd9` | chore(nova): point closed runtime at Animedia parity tip |

### Tests
- `tests/unit/test_lords_player_episode_avail.py` (new)
- player cluster + overnight + animedia parity + provenance → green
- `git diff --check` on source: clean

### Live URL
https://lordserial33.biz/title/sudmedekspert-stavshaya-domohozyaykoy/season-1/episode-7/  
(user typo `…domokho…` → 404; live slug `…domoho…`)

### Actual player state (post-fix)
| URL | state | proof |
| --- | --- | --- |
| ep7 | `unavailable`, 0×video-player | honest copy; list current=7 |
| ep1 | playable `episode="1"` | readyState=4, currentTime↑, okcdn 2xx |
| ep3 | playable `episode="3"` | readyState=4, playing, playlist len=3 |
| hub | `awaiting` | no SDK |

Evidence: `artifacts/evidence/live-template-qa/PLAYER-EP7-FIX-REPORT.md`, `raw/player-acceptance.json`, `raw/player-real-playback.json`.

### Deploy / rollback / flags
| Field | Value |
| --- | --- |
| DEPLOY_PERFORMED | **yes** — lords-02 (avail-gate), then animedia-01+02 (parity; shared frontend) |
| rollback | `/srv/lords/.frontend/.rollback/pre-closed-update-20260919T074636Z` (lords), `…T075819Z` (animedia) |
| DNS_MUTATIONS | **none** |
| INDEXING_OPENED | **no** — `noindex, nofollow` preserved |

---

## Animedia parity (vs amd.online)

### Done this pass
- Accent logo (`Anime` + **`dia`**)
- Catalog-backed **hero poster rail** (`.ahero`, 12 cards) — no invented titles / no Telegram / no Premium
- **Новые серии аниме** as two-column **row list** (`.zsec--eps`) matching amd list rhythm (without inventing episode timestamps)
- Hamburger nav on 390 (prior fix retained); overflow=false at 1440 / 768 / 390
- Shelves: Новые серии / Новые аниме / Топ / С видео

### Visual check (live post-deploy)
| Viewport | icu | space |
| --- | --- | --- |
| 1440 | hero=12, epsRows=24, overflow=0 | same |
| 768 | same | same |
| 390 | burger opens full nav | same |

Screenshots: `artifacts/evidence/live-template-qa/screenshots/animedia-parity/*-home-post-*.png`

### Remaining blockers (honest — not “done”)
| ID | Item |
| --- | --- |
| B1 | `/poster/` same-origin proxy needs nginx on Animedia |
| B2 | Ongoing / Today need source fields |
| B3 | Circe font / Premium mega-menu / login / Telegram — rights/product |
| B4 | Episode timestamps in “new series” rows — not in snapshot |
| B5 | Pixel-parity pack still incomplete |

Animedia is **improved toward** amd structure, not claimed pixel-identical.
