package com.example.webhookrelay.service;

import jakarta.enterprise.context.ApplicationScoped;
import jakarta.ws.rs.client.Client;
import jakarta.ws.rs.client.ClientBuilder;
import jakarta.ws.rs.client.Entity;
import jakarta.ws.rs.core.MediaType;
import jakarta.ws.rs.core.Response;

/**
 * Performs the actual outbound POST to a subscriber's {@code target_url}. Subscriber endpoints
 * are third-party (or at least third-team) URLs outside this service's control, so a non-2xx or a
 * timeout here is an expected, routine outcome, not an error to log loudly about — the retry job
 * is what decides whether and how to react to it.
 */
@ApplicationScoped
public class DeliverySender {

    private final Client client = ClientBuilder.newClient();

    public boolean attempt(String targetUrl, String payload) {
        try (Response response = client.target(targetUrl)
                .request()
                .post(Entity.entity(payload, MediaType.APPLICATION_JSON))) {
            return response.getStatus() >= 200 && response.getStatus() < 300;
        } catch (Exception e) {
            return false;
        }
    }
}
