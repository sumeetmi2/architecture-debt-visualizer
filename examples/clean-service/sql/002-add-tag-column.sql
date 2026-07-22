-- Expand step of an expand/contract migration: added nullable, backfilled by a one-off script
-- (not checked in — ran once against production, documented in the PR that shipped this file),
-- left nullable rather than immediately enforced. No application code depends on tag being
-- non-null yet; the NOT NULL constraint is a deliberate later step once 100% of rows are backfilled.
ALTER TABLE Link ADD COLUMN tag VARCHAR(64) NULL;
CREATE INDEX IdxTag ON Link (tag);
