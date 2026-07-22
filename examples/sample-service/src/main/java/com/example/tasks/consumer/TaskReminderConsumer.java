package com.example.tasks.consumer;

import jakarta.enterprise.context.ApplicationScoped;
import org.eclipse.microprofile.reactive.messaging.Incoming;

/**
 * Planted issue: this is a real, fully-wired consumer — configured in
 * application.properties, enabled by default — but docs-bad/boundaries.md's
 * consumer table lists only task-events and presents itself as the complete list.
 * docs-good/boundaries.md documents this channel too.
 */
@ApplicationScoped
public class TaskReminderConsumer {

    @Incoming("task-reminders")
    public void onReminderDue(String payload) {
        // send a reminder notification for an incomplete task
    }
}
