package com.example.webhookrelay.consumer;

import com.example.webhookrelay.client.SubscriptionRegistryClient;
import com.example.webhookrelay.entity.WebhookDelivery;
import com.example.webhookrelay.repository.WebhookDeliveryRepository;
import io.smallrye.reactive.messaging.annotations.Blocking;
import jakarta.enterprise.context.ApplicationScoped;
import jakarta.inject.Inject;
import jakarta.transaction.Transactional;
import org.eclipse.microprofile.reactive.messaging.Incoming;
import org.eclipse.microprofile.rest.client.inject.RestClient;

import java.time.Instant;
import java.util.UUID;

@ApplicationScoped
public class DomainEventConsumer {

    @Inject
    WebhookDeliveryRepository deliveryRepository;

    @Inject
    @RestClient
    SubscriptionRegistryClient registryClient;

    // Fixed at 4 regardless of upstream event volume — no env override, unlike this repo's other
    // tunables. Raising it means editing this literal and redeploying, not a config change.
    @Incoming("domain-events")
    @Blocking(value = "domain-events-pool", ordered = false)
    @Transactional
    public void onEvent(DomainEvent event) {
        for (SubscriptionRegistryClient.Subscriber subscriber : registryClient.resolveSubscribers(event.type())) {
            WebhookDelivery delivery = new WebhookDelivery(
                    UUID.randomUUID(),
                    subscriber.subscriptionId(),
                    subscriber.targetUrl(),
                    event.payload(),
                    WebhookDelivery.DeliveryStatus.PENDING,
                    Instant.now());
            deliveryRepository.persist(delivery);
        }
    }

    public record DomainEvent(String type, String payload) {}
}
