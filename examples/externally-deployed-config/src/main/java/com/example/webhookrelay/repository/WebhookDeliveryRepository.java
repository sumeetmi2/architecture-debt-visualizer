package com.example.webhookrelay.repository;

import com.example.webhookrelay.entity.WebhookDelivery;
import io.quarkus.hibernate.orm.panache.PanacheRepositoryBase;
import jakarta.enterprise.context.ApplicationScoped;
import java.time.Instant;
import java.util.List;
import java.util.UUID;

@ApplicationScoped
public class WebhookDeliveryRepository implements PanacheRepositoryBase<WebhookDelivery, UUID> {

    public List<WebhookDelivery> findDueForRetry(Instant now, int limit) {
        return find("status = ?1 and nextAttemptAt <= ?2", WebhookDelivery.DeliveryStatus.PENDING, now)
                .page(0, limit)
                .list();
    }
}
