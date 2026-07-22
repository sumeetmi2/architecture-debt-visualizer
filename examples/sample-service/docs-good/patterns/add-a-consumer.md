# How to: Add a New Message Consumer

Reference: `consumer/TaskEventConsumer.java` and `consumer/TaskReminderConsumer.java` — both follow
the same shape.

## Steps

1. Add a channel block in `application.properties`: `connector=smallrye-kafka`, `topic`,
   `failure-strategy` (`ignore` is this service's default — see
   [Technical Vision](../technical-vision.md) for why), and an `enabled=${ENV:default}` flag.
2. Add a class annotated `@ApplicationScoped` with a method annotated `@Incoming("<channel>")`.
3. Document the new channel in [Boundaries](../boundaries.md)'s Message Consumers table — this is
   the table the architecture-debt-visualizer skill checks for completeness.
