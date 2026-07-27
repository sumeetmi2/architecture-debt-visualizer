package com.example.reconcile;

import java.sql.Connection;
import java.sql.DriverManager;
import java.sql.PreparedStatement;

public final class AdjustmentWriter {

    private final String jdbcUrl;
    private final String password;

    public AdjustmentWriter(String jdbcUrl, String password) {
        this.jdbcUrl = jdbcUrl;
        this.password = (password == null || password.isEmpty()) ? "changeme" : password;
    }

    /**
     * Inserts a corrective adjustment row into ledger-mirror for {@code record}. Called once per
     * mismatch found during a run. There's no check for whether an adjustment for this
     * settlement ID already exists — if the job dies partway through a run and the CronJob (or an
     * operator) reruns it, every mismatch already corrected in the earlier attempt gets a second
     * adjustment written on top of it, since {@code fetchSettlements} will report the same
     * mismatch again until the correction has fully replicated.
     */
    public void applyAdjustment(LedgerRecord primaryRecord) {
        String sql = "INSERT INTO adjustments (settlement_id, amount, currency, applied_at) "
                + "VALUES (?, ?, ?, now())";
        try (Connection conn = DriverManager.getConnection(jdbcUrl, "reconciliation", password);
             PreparedStatement stmt = conn.prepareStatement(sql)) {
            stmt.setString(1, primaryRecord.getSettlementId());
            stmt.setBigDecimal(2, primaryRecord.getAmount());
            stmt.setString(3, primaryRecord.getCurrency());
            stmt.executeUpdate();
        } catch (Exception e) {
            System.out.println("Failed to write adjustment for " + primaryRecord.getSettlementId()
                    + ": " + e.getMessage());
        }
    }
}
