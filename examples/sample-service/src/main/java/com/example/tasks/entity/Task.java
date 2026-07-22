package com.example.tasks.entity;

import jakarta.persistence.Entity;
import jakarta.persistence.Id;
import java.time.Instant;

/**
 * Planted issue: this entity's JPA identity is a single column (id), but the real
 * table (see sql/001-task.sql) has a composite primary key (CreatedDate, Id) and is
 * partitioned by CreatedDate. Two rows with the same id but different CreatedDate
 * would collide as "the same entity" from Hibernate's point of view.
 */
@Entity
public class Task {

    @Id
    private String id;

    private String status;
    private String assigneeId;
    private int priority;
    private Instant createdAt;
    private Instant completedAt;
}
