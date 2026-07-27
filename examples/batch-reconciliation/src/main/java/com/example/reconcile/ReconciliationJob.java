package com.example.reconcile;

import java.time.LocalDate;
import java.util.List;

/**
 * Entry point for the nightly reconciliation run. Started by the {@code ledger-reconciliation-job}
 * CronJob at 02:00 UTC, runs once, exits. Not invoked interactively.
 */
public final class ReconciliationJob {

    public static void main(String[] args) {
        String primaryUrl = System.getenv("LEDGER_PRIMARY_URL");
        String mirrorUrl = System.getenv("LEDGER_MIRROR_URL");
        String password = System.getenv("LEDGER_DB_PASSWORD");

        LedgerClient primary = new LedgerClient(primaryUrl, password);
        LedgerClient mirror = new LedgerClient(mirrorUrl, password);
        AdjustmentWriter writer = new AdjustmentWriter(mirrorUrl, password);

        LocalDate yesterday = LocalDate.now().minusDays(1);

        try {
            List<LedgerRecord> primaryRecords = primary.fetchSettlements(yesterday);
            List<LedgerRecord> mirrorRecords = mirror.fetchSettlements(yesterday);

            int compared = 0;
            int adjusted = 0;

            // O(n*m) scan — fine at today's volume, but there's no index-by-settlement-ID path for
            // when either ledger's daily volume grows past a few thousand rows.
            for (LedgerRecord p : primaryRecords) {
                compared++;
                LedgerRecord match = null;
                for (LedgerRecord m : mirrorRecords) {
                    if (m.getSettlementId().equals(p.getSettlementId())) {
                        match = m;
                        break;
                    }
                }
                if (match == null || !match.matches(p)) {
                    writer.applyAdjustment(p);
                    adjusted++;
                }
            }

            System.out.println("Compared " + compared + " records, applied " + adjusted
                    + " adjustments.");
        } catch (Exception e) {
            // Logged to stdout only, no metric, no alert, and no non-zero exit — the CronJob
            // reports this run as succeeded even when reconciliation didn't actually run.
            System.out.println("Reconciliation run failed: " + e.getMessage());
        }
    }
}
