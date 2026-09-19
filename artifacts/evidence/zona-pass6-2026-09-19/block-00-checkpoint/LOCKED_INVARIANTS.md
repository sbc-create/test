# Locked invariants (regression-only)

Do not change without REGRESSION_REPRODUCED + ROOT_CAUSE_PROVEN + SCOPED_FIX:

- full catalog oracle / join
- year facets and year counts (2019=2144, movie facets=92)
- hard cap removed
- route canonicalization / pagination / sort
- card grid 8/7/4/2 (~175px @1440, poster ~260)
- player state machine / overlay / golden 10/10
- noindex
- deploy isolation zona-01-only

Global CSS touching cards/player requires full re-gate.
