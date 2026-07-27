# Technical vision

## Why this job exists

Settlement drift between `ledger-primary` and `ledger-mirror` is a finance-reporting risk, not just
an engineering inconvenience — accounting closes the books off `ledger-mirror`, so any uncorrected
drift shows up as a real discrepancy in a financial report. This job's job is to make sure that
never happens silently.

## What "correct" means here

Every corrective adjustment this job writes should be traceable and should never be applied twice
for the same underlying drift — a duplicated adjustment would itself become a new discrepancy,
which is the exact failure mode this job exists to prevent.

## What we haven't scoped

We haven't set a target for how large a single night's settlement volume can grow before this job's
current approach needs to change, or a maximum acceptable run time before it risks overlapping with
the next day's ledger close jobs. Both are open questions as settlement volume grows.
