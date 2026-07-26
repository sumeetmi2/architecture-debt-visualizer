package com.example.webhookrelay.scheduler;

import com.example.webhookrelay.entity.WebhookDelivery;
import com.example.webhookrelay.repository.WebhookDeliveryRepository;
import com.example.webhookrelay.service.DeliverySender;
import io.quarkus.scheduler.Scheduled;
import jakarta.enterprise.context.ApplicationScoped;
import jakarta.inject.Inject;
import jakarta.transaction.Transactional;
import org.eclipse.microprofile.config.inject.ConfigProperty;

import java.time.Instant;
import java.time.temporal.ChronoUnit;
import java.util.List;

@ApplicationScoped
public class DeliveryRetryJob {

    @Inject
    WebhookDeliveryRepository deliveryRepository;

    @Inject
    DeliverySender deliverySender;

    @ConfigProperty(name = "webhookrelay.retry-job.interval")
    String interval;

    private static final int BATCH_SIZE = 200;

    @Scheduled(every = "${webhookrelay.retry-job.interval:1m}")
    @Transactional
    public void retryDue() {
        List<WebhookDelivery> due = deliveryRepository.findDueForRetry(Instant.now(), BATCH_SIZE);
        for (WebhookDelivery delivery : due) {
            boolean delivered = deliverySender.attempt(delivery.getTargetUrl(), delivery.getPayload());
            if (delivered) {
                delivery.markDelivered(Instant.now());
            } else {
                // Every failure just pushes next_attempt_at out with the same fixed backoff and
                // increments attempt_count — there's no ceiling on attempt_count anywhere in this
                // method, and no branch that ever sets status to FAILED. A subscriber whose
                // target_url is permanently gone (404, DNS failure, decommissioned) stays PENDING
                // and keeps consuming a retry slot every interval, forever.
                delivery.scheduleRetry(Instant.now().plus(5, ChronoUnit.MINUTES));
            }
        }
    }
}
