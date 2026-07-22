package com.example.tasks.service;

import com.example.tasks.entity.Task;
import com.example.tasks.repository.TaskRepository;
import jakarta.enterprise.context.ApplicationScoped;
import jakarta.inject.Inject;
import java.util.Optional;

@ApplicationScoped
public class TaskService {

    @Inject
    TaskRepository taskRepository;

    public Task create(Task task) {
        return taskRepository.save(task);
    }

    public Optional<Task> get(String id) {
        return taskRepository.findById(id);
    }

    public void bulkImport(java.util.List<Task> tasks) {
        tasks.forEach(taskRepository::save);
    }
}
