package com.example.reconcile;

import java.math.BigDecimal;

public final class LedgerRecord {

    private final String settlementId;
    private final BigDecimal amount;
    private final String currency;

    public LedgerRecord(String settlementId, BigDecimal amount, String currency) {
        this.settlementId = settlementId;
        this.amount = amount;
        this.currency = currency;
    }

    public String getSettlementId() {
        return settlementId;
    }

    public BigDecimal getAmount() {
        return amount;
    }

    public String getCurrency() {
        return currency;
    }

    public boolean matches(LedgerRecord other) {
        return amount.compareTo(other.amount) == 0 && currency.equals(other.currency);
    }
}
