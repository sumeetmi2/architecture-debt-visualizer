package com.example.webhookrelay.entity;

import jakarta.persistence.*;
import java.time.Instant;
import java.util.UUID;

@Entity
@Table(name = "webhook_delivery")
public class WebhookDelivery {

    @Id
    private UUID id;

    @Column(name = "subscription_id", nullable = false)
    private UUID subscriptionId;

    @Column(name = "target_url", nullable = false)
    private String targetUrl;

    @Column(name = "payload", nullable = false, columnDefinition = "jsonb")
    private String payload;

    @Enumerated(EnumType.STRING)
    @Column(nullable = false)
    private DeliveryStatus status;

    @Column(name = "attempt_count", nullable = false)
    private int attemptCount;

    @Column(name = "next_attempt_at", nullable = false)
    private Instant nextAttemptAt;

    @Column(name = "created_at", nullable = false)
    private Instant createdAt;

    @Column(name = "delivered_at")
    private Instant deliveredAt;

    public enum DeliveryStatus { PENDING, DELIVERED, FAILED }

    protected WebhookDelivery() {
    }

    public WebhookDelivery(UUID id, UUID subscriptionId, String targetUrl, String payload,
                            DeliveryStatus status, Instant createdAt) {
        this.id = id;
        this.subscriptionId = subscriptionId;
        this.targetUrl = targetUrl;
        this.payload = payload;
        this.status = status;
        this.attemptCount = 0;
        this.nextAttemptAt = createdAt;
        this.createdAt = createdAt;
    }

    public UUID getId() { return id; }
    public String getTargetUrl() { return targetUrl; }
    public String getPayload() { return payload; }
    public DeliveryStatus getStatus() { return status; }
    public int getAttemptCount() { return attemptCount; }

    public void markDelivered(Instant when) {
        this.status = DeliveryStatus.DELIVERED;
        this.deliveredAt = when;
    }

    public void scheduleRetry(Instant nextAttempt) {
        this.attemptCount++;
        this.nextAttemptAt = nextAttempt;
    }

    // No corresponding "give up" transition to FAILED exists on this entity — see
    // DeliveryRetryJob.retryDue(), which is the only caller of scheduleRetry().
}
