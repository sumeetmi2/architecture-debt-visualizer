# Architecture

## Shape

A single-purpose batch job, not a service. There is no listener, no HTTP surface, and no process
that stays up between runs — the container is started by the `ledger-reconciliation-job` CronJob,
runs one reconciliation pass end to end, and exits. Kubernetes handles scheduling and retries at
the job level (`concurrencyPolicy: Forbid` keeps two runs from overlapping if one runs long).

## Flow

```
ledger-primary (source of truth) ──fetch──▶ ReconciliationJob ◀──fetch── ledger-mirror
                                                    │
                                            compare by settlement ID
                                                    │
                                          write corrective adjustment
                                                    ▼
                                              ledger-mirror
```

`ledger-primary` is authoritative. Any settlement present there but missing or mismatched in
`ledger-mirror` gets a corrective `adjustments` row written to `ledger-mirror` — the job never
writes to `ledger-primary`.

## Why a nightly batch job instead of a stream

`ledger-mirror` already replicates from `ledger-primary` continuously; this job exists to catch the
residual drift that continuous replication doesn't guarantee against (replay gaps, dropped events
during a `ledger-mirror` deploy, etc.), not to be the primary sync path. A nightly cadence matches
how often those gaps have historically been discovered — this isn't meant to close a real-time
consistency gap.

## Credentials

Both `LedgerClient` and `AdjustmentWriter` read `LEDGER_DB_PASSWORD` from the environment, sourced
from the `ledger-db-credentials` Kubernetes secret in `deploy/cronjob.yaml`.
