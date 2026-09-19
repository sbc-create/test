# DB migration audit

```json
{
  "migrations": [
    {
      "version": "0002",
      "description": "ratings ingestion: registry, mappings, observations, queue, runs",
      "applied_at": "2026-09-19T20:04:26Z"
    },
    {
      "version": "0003",
      "description": "amd local votes combined daily ratings",
      "applied_at": "2026-09-19T20:04:26Z"
    },
    {
      "version": "0004",
      "description": "rating_source_absence for zero-score/no-vote deferred retry",
      "applied_at": "2026-09-19T20:04:26Z"
    }
  ],
  "checksums": {
    "0002_ratings_ingestion.py": "558557e1436a6ec1da8a73edd32e5ac497a3e587a114c672ab5acdd2bfda3c66",
    "0003_ratings_local_amd.py": "43f4980bcfc93a6251a64133144eeda9cdb4863e21220e76fd51d661da931e95",
    "0004_ratings_absence.py": "56bbd0bbb49287c9b814a6f098b8526ad4b44d05abdfcf2332c15d3a45e790b8"
  },
  "DB_SCHEMA_VERSION": "0004"
}
```
