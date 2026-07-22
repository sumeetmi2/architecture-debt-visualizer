package com.example.linkshortener.repository;

import com.example.linkshortener.entity.Link;
import jakarta.enterprise.context.ApplicationScoped;
import java.util.Optional;

/** Illustrative only — no real persistence provider is wired up in this sample. */
@ApplicationScoped
public class LinkRepository {

    public Optional<Link> findByShortCode(String shortCode) {
        throw new UnsupportedOperationException("illustrative sample, not wired up");
    }

    public Optional<Link> findByIdempotencyKey(String idempotencyKey) {
        throw new UnsupportedOperationException("illustrative sample, not wired up");
    }

    public Link save(Link link) {
        throw new UnsupportedOperationException("illustrative sample, not wired up");
    }

    public int expireLinksPast(java.time.LocalDateTime cutoff) {
        throw new UnsupportedOperationException("illustrative sample, not wired up");
    }
}
