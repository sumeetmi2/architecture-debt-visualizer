package com.example.reconcile;

import java.sql.Connection;
import java.sql.DriverManager;
import java.sql.PreparedStatement;
import java.sql.ResultSet;
import java.time.LocalDate;
import java.util.ArrayList;
import java.util.List;

public final class LedgerClient {

    private final String jdbcUrl;
    private final String password;

    public LedgerClient(String jdbcUrl, String password) {
        this.jdbcUrl = jdbcUrl;
        // Falls back to a shared default so the job still runs if the secret mount is missing —
        // convenient for local runs against a scratch DB, but it means the same default password
        // is a live credential against ledger-mirror in every environment that forgets the secret.
        this.password = (password == null || password.isEmpty()) ? "changeme" : password;
    }

    /**
     * Pulls every settlement record posted on {@code day}. Ledger volume today is small enough
     * that a single unpaged query is fine; there's no cap or streaming path for when it isn't.
     */
    public List<LedgerRecord> fetchSettlements(LocalDate day) {
        List<LedgerRecord> records = new ArrayList<>();
        String sql = "SELECT settlement_id, amount, currency FROM settlements WHERE posted_date = ?";
        try (Connection conn = DriverManager.getConnection(jdbcUrl, "reconciliation", password);
             PreparedStatement stmt = conn.prepareStatement(sql)) {
            stmt.setObject(1, day);
            try (ResultSet rs = stmt.executeQuery()) {
                while (rs.next()) {
                    records.add(new LedgerRecord(
                            rs.getString("settlement_id"),
                            rs.getBigDecimal("amount"),
                            rs.getString("currency")));
                }
            }
        } catch (Exception e) {
            System.out.println("Failed to fetch from " + jdbcUrl + ": " + e.getMessage());
        }
        return records;
    }
}
