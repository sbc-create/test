# Accepted base commit

The commit this line of work is based on, recorded so that later sessions and
reviewers can reproduce the starting state exactly.

| Field | Value |
| --- | --- |
| Repository | `sbc-create/test` |
| Accepted base commit | `124ae4febd062de3e74299b44fcdff746cf4ed6a` |
| Base commit subject | Seed repository with initial README |
| Base branch | `main` |
| Working branch | `claude/repo-prep-seo-session-j1wrji` |
| Recorded at | 2026-08-22T19:37:21Z |

## Why this commit

The repository was empty when this work started — no commits, no branches, on
GitHub or locally. `124ae4f` is the root commit that seeds the repository
and establishes `main` as the pull request base. It contains a README stub and
nothing else, so the pull request diff is exactly the work described in it.

## Reproducing this base

```bash
git fetch origin main
git checkout 124ae4febd062de3e74299b44fcdff746cf4ed6a
```

## Rule

Later work branches from `main` at or after this commit. This record is
updated only when a new base is deliberately accepted, and the change is
explained here.
