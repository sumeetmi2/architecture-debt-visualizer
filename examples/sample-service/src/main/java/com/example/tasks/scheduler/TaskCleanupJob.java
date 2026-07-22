package com.example.tasks.scheduler;

import io.quarkus.scheduler.Scheduled;
import jakarta.enterprise.context.ApplicationScoped;

/**
 * Planted issue: worker-count is a hardcoded literal (see application.properties,
 * task.cleanup.worker-count=1) with no environment override — unlike
 * notification.batch-size in the same file, which is env-overridable. Scaling
 * this job's throughput today requires a code change and redeploy, not a config
 * change.
 */
@ApplicationScoped
public class TaskCleanupJob {

    @Scheduled(every = "1h")
    public void archiveOldTasks() {
        // moves completed tasks older than the retention window into TaskArchive
    }
}
