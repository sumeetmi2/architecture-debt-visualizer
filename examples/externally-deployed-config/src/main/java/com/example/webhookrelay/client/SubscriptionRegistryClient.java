package com.example.webhookrelay.client;

import org.eclipse.microprofile.faulttolerance.CircuitBreaker;
import org.eclipse.microprofile.faulttolerance.Fallback;
import org.eclipse.microprofile.faulttolerance.Timeout;
import org.eclipse.microprofile.rest.client.inject.RegisterRestClient;

import java.time.temporal.ChronoUnit;
import java.util.List;
import java.util.UUID;

/**
 * Subscriber-to-target-URL lookup is owned by the separate {@code subscription-registry} service
 * (its own repo, its own deploy) — this service only relays events, it never stores who's
 * subscribed to what. See {@code docs/architecture.md} for why that boundary exists.
 */
@RegisterRestClient(configKey = "subscription-registry")
public interface SubscriptionRegistryClient {

    @Timeout(value = 500, unit = ChronoUnit.MILLIS)
    @CircuitBreaker(requestVolumeThreshold = 10, failureRatio = 0.5, delay = 30, delayUnit = ChronoUnit.SECONDS)
    @Fallback(fallbackMethod = "emptySubscriberList")
    List<Subscriber> resolveSubscribers(String eventType);

    default List<Subscriber> emptySubscriberList(String eventType) {
        // Registry is unreachable — relay nothing for this event rather than guess. The
        // circuit-breaker/fallback pair means a registry outage degrades delivery, it doesn't
        // take this service down with it.
        return List.of();
    }

    record Subscriber(UUID subscriptionId, String targetUrl) {}
}
