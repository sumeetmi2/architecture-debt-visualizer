package com.example.linkshortener.consumer;

import com.example.linkshortener.client.AnalyticsClient;
import com.example.linkshortener.service.LinkService;
import io.micrometer.core.instrument.Counter;
import io.micrometer.core.instrument.MeterRegistry;
import io.micrometer.core.instrument.Timer;
import jakarta.enterprise.context.ApplicationScoped;
import jakarta.inject.Inject;
import org.eclipse.microprofile.reactive.messaging.Incoming;

/**
 * Consumes click events for the async click-counting path. Unlike sample-service's deliberate
 * drop-on-failure design, this channel is configured failure-strategy=dead-letter-queue (see
 * application.properties) — a message that can't be processed lands somewhere inspectable, it
 * doesn't vanish. Idempotent by construction: incrementing a counter is safe to replay from a
 * DLQ requeue (worst case, a click is counted twice on a genuine redelivery, an accepted
 * trade-off documented in technical-vision.md — exact-once click counting was judged not worth
 * the complexity for an analytics signal).
 */
@ApplicationScoped
public class ClickEventConsumer {

    @Inject
    LinkService linkService;

    @Inject
    AnalyticsClient analyticsClient;

    @Inject
    MeterRegistry registry;

    @Incoming("click-events")
    public void onClickEvent(String shortCode) {
        Timer.Sample sample = Timer.start(registry);
        try {
            linkService.recordClick(shortCode);
            analyticsClient.forwardClickEvent(shortCode);
            registry.counter("click_events_processed_total").increment();
        } catch (RuntimeException e) {
            registry.counter("click_events_failed_total").increment();
            throw e;
        } finally {
            sample.stop(Timer.builder("click_event_processing_duration").register(registry));
        }
    }
}
