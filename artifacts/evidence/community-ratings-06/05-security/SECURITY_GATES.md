# Security gates COMMUNITY-RATINGS-06

Live matrix: `11-live-matrix/LIVE_MATRIX.json`

Denied: missing cookie, tampered signature, client user_id, cohort bypass, CSRF, bad Origin, rating 0/11/fraction/string, cross-space body.
Accepted only for eligible 1% identity with valid CSRF/Origin after PUBLIC_WRITE_ENABLED=1.
