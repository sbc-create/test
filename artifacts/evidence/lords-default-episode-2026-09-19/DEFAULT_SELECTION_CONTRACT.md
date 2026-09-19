# DEFAULT_SELECTION_CONTRACT

Order on generic series detail:

1. Exact season/episode deep-link (route handler) — never overwritten by hub default
2. No new resume/tracking invented
3. No API `defaultEpisodeId` in sidecar → skipped
4. First playable: seasons by `n` ASC, episodes `1..avail` ASC
5. If `avail=0` but `eps>=1` → first released `(season, 1)` for one resolve
6. If no released episodes → episode `None` → compact empty (no SDK)

Movies: no season list → direct movie source bind (no episode prompt).

Invariants:

* `episodes/seasons present with avail|eps > 0` ⇒ `selectedEpisodeId != null` after SSR
* `sources candidates > 0` ⇒ descriptor present when player state is resolving/ready
* `AUTOPLAY_COUNT=0` (no autoplay attribute added)
* `PLAYER_INSTANCE_MAX=1` (single `video-player` / host)
