package com.example.linkshortener.service;

import com.example.linkshortener.entity.Link;
import com.example.linkshortener.repository.LinkRepository;
import jakarta.enterprise.context.ApplicationScoped;
import jakarta.inject.Inject;
import java.util.Optional;

@ApplicationScoped
public class LinkService {

    @Inject
    LinkRepository linkRepository;

    /**
     * Idempotency-key-first: a client that retries a create call with the same key gets the
     * original link back, not a duplicate row (see the unique index on idempotencyKey).
     * A single-table write with no follow-on event to publish — creating a link has no second
     * system to keep consistent with, so there's no dual-write/outbox question here at all.
     */
    public Link createLink(String targetUrl, String idempotencyKey) {
        Optional<Link> existing = linkRepository.findByIdempotencyKey(idempotencyKey);
        if (existing.isPresent()) {
            return existing.get();
        }
        throw new UnsupportedOperationException("illustrative sample, not wired up");
    }

    public Optional<Link> resolve(String shortCode) {
        throw new UnsupportedOperationException("illustrative sample, not wired up");
    }

    public void recordClick(String shortCode) {
        throw new UnsupportedOperationException("illustrative sample, not wired up");
    }
}
