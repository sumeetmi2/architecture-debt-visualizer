package com.example.linkshortener.resource;

import com.example.linkshortener.entity.Link;
import com.example.linkshortener.service.LinkService;
import io.micrometer.core.instrument.MeterRegistry;
import jakarta.inject.Inject;
import jakarta.validation.Valid;
import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.Pattern;
import jakarta.ws.rs.*;
import jakarta.ws.rs.core.MediaType;
import jakarta.ws.rs.core.Response;

/**
 * Versioned from day one (/api/v1) — see technical-vision.md's Versioning & Deprecation Policy
 * for the stated bar for when a v2 would be introduced. Every endpoint here is covered by
 * AuthenticationFilter (a global @Provider, not a per-method annotation) and every request body
 * is @Valid — there is no endpoint in this resource that skips either.
 */
@Path("/api/v1/links")
public class LinkResource {

    @Inject
    LinkService linkService;

    @Inject
    MeterRegistry registry;

    public record CreateLinkRequest(
        @NotBlank @Pattern(regexp = "^https?://.+") String targetUrl
    ) {
    }

    @POST
    @Consumes(MediaType.APPLICATION_JSON)
    @Produces(MediaType.APPLICATION_JSON)
    public Response create(@Valid CreateLinkRequest request, @HeaderParam("Idempotency-Key") @NotBlank String idempotencyKey) {
        registry.counter("link_create_requests_total").increment();
        Link link = linkService.createLink(request.targetUrl(), idempotencyKey);
        return Response.status(Response.Status.CREATED).entity(link).build();
    }

    @GET
    @Path("/{code}")
    @Produces(MediaType.APPLICATION_JSON)
    public Response resolve(@PathParam("code") String code) {
        registry.counter("link_resolve_requests_total").increment();
        return linkService.resolve(code)
            .map(link -> Response.ok(link).build())
            .orElse(Response.status(Response.Status.NOT_FOUND).build());
    }
}
