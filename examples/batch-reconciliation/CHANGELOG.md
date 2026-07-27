# Changelog

## Unreleased

- Switched the CronJob's container image from a pinned digest to `:latest`, so deploys no longer
  require bumping a tag in `deploy/cronjob.yaml` — a new image just needs pushing.

## 0.3.0

- Added `AdjustmentWriter` to actually apply corrections, instead of only reporting mismatches.
  Previously this job logged drift for someone to fix by hand.

## 0.2.0

- Switched from full-table scan comparison to per-day filtering (`posted_date = ?`) to keep each
  run's working set to a single day's settlements.

## 0.1.0

- Initial version: fetches and logs mismatches only, no corrective writes.
