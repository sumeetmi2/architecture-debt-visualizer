package com.example.linkshortener.scheduler;

import com.example.linkshortener.repository.LinkRepository;
import io.micrometer.core.instrument.MeterRegistry;
import io.quarkus.scheduler.Scheduled;
import jakarta.enterprise.context.ApplicationScoped;
import jakarta.inject.Inject;
import java.time.LocalDateTime;

/**
 * Marks links past their expiresAt as expired. Idempotent by construction — re-running against
 * rows already marked 'expired' is a no-op (the UPDATE ... WHERE status != 'expired' clause in
 * the repository query), so a retry after a partial failure never double-processes. Worker
 * concurrency and interval are both env-overridable, unlike sample-service's hardcoded
 * equivalent.
 */
@ApplicationScoped
public class LinkExpiryJob {

    @Inject
    LinkRepository linkRepository;

    @Inject
    MeterRegistry registry;

    @Scheduled(every = "{linkshortener.expiry-job.interval:1h}")
    public void expireOldLinks() {
        int expired = linkRepository.expireLinksPast(LocalDateTime.now());
        registry.gauge("links_expired_last_run", expired);
    }
}
