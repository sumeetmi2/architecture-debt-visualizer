package com.example.webhookrelay.resource;

import com.example.webhookrelay.entity.WebhookDelivery;
import com.example.webhookrelay.repository.WebhookDeliveryRepository;
import jakarta.inject.Inject;
import jakarta.ws.rs.GET;
import jakarta.ws.rs.NotFoundException;
import jakarta.ws.rs.Path;
import jakarta.ws.rs.PathParam;
import jakarta.ws.rs.Produces;
import jakarta.ws.rs.core.MediaType;

import java.util.UUID;

/**
 * Operator-facing read endpoint — lets on-call look up a specific delivery's status without a DB
 * console. Not part of the ingestion or delivery path itself.
 */
@Path("/api/v1/deliveries")
@Produces(MediaType.APPLICATION_JSON)
public class DeliveryResource {

    @Inject
    WebhookDeliveryRepository deliveryRepository;

    @GET
    @Path("/{id}")
    public WebhookDelivery get(@PathParam("id") UUID id) {
        return deliveryRepository.findByIdOptional(id)
                .orElseThrow(NotFoundException::new);
    }
}
