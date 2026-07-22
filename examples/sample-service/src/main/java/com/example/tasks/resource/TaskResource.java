package com.example.tasks.resource;

import com.example.tasks.entity.Task;
import com.example.tasks.service.TaskService;
import jakarta.inject.Inject;
import jakarta.ws.rs.*;
import jakarta.ws.rs.core.MediaType;
import java.util.List;

@Path("/api/v1/tasks")
public class TaskResource {

    @Inject
    TaskService taskService;

    @POST
    @Consumes(MediaType.APPLICATION_JSON)
    public Task create(Task task) {
        return taskService.create(task);
    }

    @GET
    @Path("/{id}")
    @Produces(MediaType.APPLICATION_JSON)
    public Task get(@PathParam("id") String id) {
        return taskService.get(id).orElse(null);
    }

    // Planted issue: this endpoint exists and is fully wired up, but is never mentioned
    // in docs-bad/boundaries.md's endpoint table, which reads as a complete list of two.
    @POST
    @Path("/bulk-import")
    @Consumes(MediaType.APPLICATION_JSON)
    public void bulkImport(List<Task> tasks) {
        taskService.bulkImport(tasks);
    }
}
