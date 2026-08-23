# Reporting conventions

Applies to every deliverable that leaves this repository.

## Findings

A finding is a defect with a location and evidence. It has:

- an `id` matching `^[A-Z]{2,5}-[0-9]{3}$` (for example `IDX-001`), stable across
  runs so a finding can be tracked to closure;
- a `category` from the schema's fixed list;
- a `severity`;
- at least one `affected_urls` entry;
- an `evidence` string stating how it was verified.

If you cannot fill in `evidence`, it is not a finding yet. It is a hypothesis,
and it belongs in the notes rather than the report.

## Severity

Severity describes impact on organic visibility, not effort to fix:

| Severity | Meaning |
| --- | --- |
| `critical` | Pages that should rank cannot be crawled or indexed at all |
| `high` | Significant indexation or duplication problems affecting many pages |
| `medium` | On-page quality problems: duplicates, truncation, weak targeting |
| `low` | Isolated or cosmetic issues |
| `info` | Observations worth recording that are not defects |

A cheap fix for a `critical` issue is still `critical`. Do not downgrade
severity because the fix is easy, and do not inflate it because the fix is hard.

## Scores

If a report carries a `score`, it must name its `method`. The schema requires
this. A bare number out of 100 with no stated derivation is not
interpretable and not reproducible — two runs a week apart cannot be compared
if the method is unstated.

## Recommendations

Write recommendations that can be executed and then verified:

- Good: "Remove the `noindex` directive from the 24 URLs listed in `IDX-001`."
- Bad: "Improve indexation."

Each recommendation should imply a check that will confirm it worked.

## What not to claim

- Do not predict ranking positions or traffic numbers from an audit. Neither
  follows deterministically from the changes.
- Do not present third-party estimates as measurements. Label the source.
- Do not report a check you did not run. An unrun check is reported as not run;
  an empty `findings` array means "audited and clean", never "skipped".
- Do not describe search engine ranking systems with more certainty than the
  public documentation supports.

## Reproducibility

Every report states the commit it was generated from and the date. Two people
running the same audit at the same commit should produce the same findings; if
they do not, the process has an unrecorded input.
