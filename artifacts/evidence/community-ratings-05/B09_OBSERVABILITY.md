# Daily observability report contract — COMMUNITY-RATINGS-05

Immutable JSON/Markdown daily report fields (no new scheduler enabled):

```text
votes_cast
votes_updated
votes_retracted
unique_active_voters
score_distribution_1_to_10
rejected_by_reason
rate_limit_events
csrf_origin_failures
concurrency_conflicts
quarantined_votes
aggregate_rebuild_mismatches
source_lineage_violations
double_count_attempts
ui_api_error_rate
write_latency_p50_p95
db_lock_time_ms
kill_switch_state
read_only_state
indexability_state
unexplained_score_change_count
canary_residue_count
```

Alert conditions (configured in evidence; not auto-paged without owner scope):

* canary_residue_count > 0
* aggregate_rebuild_mismatches > 0
* indexability OPEN→CLOSED
* double_count_attempts > 0
* kill_switch unexpectedly ON in production

```text
SCHEDULER_ENABLED=0
Qwen delivery absence does not block JSON/Markdown report generation.
```
