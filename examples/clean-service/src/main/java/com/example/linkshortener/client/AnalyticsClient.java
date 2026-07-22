package com.example.linkshortener.client;

import jakarta.enterprise.context.ApplicationScoped;
import org.eclipse.microprofile.faulttolerance.CircuitBreaker;
import org.eclipse.microprofile.faulttolerance.Fallback;
import org.eclipse.microprofile.faulttolerance.Timeout;
import java.time.temporal.ChronoUnit;

/**
 * The only outbound call this service makes to another system. Forwarding a click event here is
 * best-effort — a slow/unavailable analytics backend must never block or fail link resolution,
 * so this is timeout + circuit-breaker + fallback, not a bare HTTP call.
 */
@ApplicationScoped
public class AnalyticsClient {

    @Timeout(value = 500, unit = ChronoUnit.MILLIS)
    @CircuitBreaker(requestVolumeThreshold = 10, failureRatio = 0.5, delay = 30, delayUnit = ChronoUnit.SECONDS)
    @Fallback(fallbackMethod = "recordSkipped")
    public void forwardClickEvent(String shortCode) {
        throw new UnsupportedOperationException("illustrative sample, not wired up");
    }

    void recordSkipped(String shortCode) {
        // Fallback path: the click was already durably recorded via the click-events consumer's
        // own Link.clickCount update before this call — analytics forwarding is a secondary,
        // droppable side effect, never the source of truth. See ClickEventConsumer.
    }
}
