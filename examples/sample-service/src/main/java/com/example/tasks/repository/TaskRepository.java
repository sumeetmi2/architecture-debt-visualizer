package com.example.tasks.repository;

import com.example.tasks.entity.Task;
import jakarta.enterprise.context.ApplicationScoped;
import java.util.Optional;

@ApplicationScoped
public class TaskRepository {

    public Optional<Task> findById(String id) {
        // Illustrative only — no real persistence provider is wired up in this sample.
        return Optional.empty();
    }

    public Task save(Task task) {
        return task;
    }
}
