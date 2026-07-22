package com.example.tasks.consumer;

import jakarta.enterprise.context.ApplicationScoped;
import org.eclipse.microprofile.reactive.messaging.Incoming;

/**
 * Documented in docs-good/boundaries.md and docs-bad/boundaries.md alike.
 * failure-strategy=ignore (see application.properties) — failed messages are dropped,
 * not dead-lettered, matching both doc sets' claim about this channel.
 */
@ApplicationScoped
public class TaskEventConsumer {

    @Incoming("task-events")
    public void onTaskEvent(String payload) {
        // process a task-created/updated event
    }
}
