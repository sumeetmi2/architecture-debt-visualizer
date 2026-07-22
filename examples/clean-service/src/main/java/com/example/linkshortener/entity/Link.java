package com.example.linkshortener.entity;

import jakarta.persistence.EmbeddedId;
import jakarta.persistence.Entity;
import jakarta.persistence.Table;
import java.time.LocalDate;
import java.time.LocalDateTime;

/**
 * Composite identity mirrors the real DDL primary key (createdDate, id) exactly via
 * {@link LinkId} — no @Id-vs-DDL mismatch. Every DDL column (including the nullable `tag`
 * added in 002-add-tag-column.sql) has a matching field; nothing here is a partial mapping.
 */
@Entity
@Table(name = "Link")
public class Link {

    @EmbeddedId
    private LinkId id;

    private String shortCode;
    private String targetUrl;
    private String idempotencyKey;
    private long clickCount;
    private LocalDateTime expiresAt;
    private String status;
    private LocalDateTime createdAt;
    private String tag;

    public record LinkId(LocalDate createdDate, Long id) {
    }
}
