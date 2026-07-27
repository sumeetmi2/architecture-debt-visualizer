# ledger-reconciliation-job

Nightly batch job that reconciles settlement records between the payments ledger (`ledger-primary`)
and the downstream accounting mirror (`ledger-mirror`), correcting drift caused by replication lag.

## What it does

Once per night, the job:

1. Pulls the full set of settlement records posted `yesterday` from both ledgers.
2. Compares them by settlement ID.
3. For any record present in `ledger-primary` but missing or mismatched in `ledger-mirror`, writes
   a corrective adjustment to `ledger-mirror`.
4. Prints a summary of records compared and adjustments applied.

## Running it

Not run interactively. Deployed as a Kubernetes `CronJob` (`deploy/cronjob.yaml`), scheduled for
02:00 UTC, after both ledgers' end-of-day close jobs finish. There is no HTTP endpoint, no long-
running process, and no operator-facing CLI — the container starts, runs one reconciliation pass,
and exits.

## Layout

- `src/main/java/com/example/reconcile/ReconciliationJob.java` — entry point, orchestrates one run.
- `src/main/java/com/example/reconcile/LedgerClient.java` — fetches a day's records from a ledger.
- `src/main/java/com/example/reconcile/LedgerRecord.java` — settlement record shape.
- `src/main/java/com/example/reconcile/AdjustmentWriter.java` — writes corrective adjustments to
  `ledger-mirror`.
- `deploy/cronjob.yaml` — schedule and container spec.
