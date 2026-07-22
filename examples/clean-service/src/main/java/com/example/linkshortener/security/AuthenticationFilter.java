package com.example.linkshortener.security;

import jakarta.annotation.Priority;
import jakarta.ws.rs.Priorities;
import jakarta.ws.rs.container.ContainerRequestContext;
import jakarta.ws.rs.container.ContainerRequestFilter;
import jakarta.ws.rs.core.Response;
import jakarta.ws.rs.ext.Provider;
import org.eclipse.microprofile.config.inject.ConfigProperty;

/**
 * Global JAX-RS filter — applies to every REST resource in this service by construction (no
 * per-endpoint opt-in), so a new endpoint can't accidentally ship unprotected. The credential is
 * read from config (env-backed), never hardcoded.
 */
@Provider
@Priority(Priorities.AUTHENTICATION)
public class AuthenticationFilter implements ContainerRequestFilter {

    @ConfigProperty(name = "linkshortener.auth-credential")
    String configuredCredential;

    @Override
    public void filter(ContainerRequestContext ctx) {
        String provided = ctx.getHeaderString("X-Auth-Credential");
        if (provided == null || !constantTimeEquals(provided, configuredCredential)) {
            ctx.abortWith(Response.status(Response.Status.UNAUTHORIZED).build());
        }
    }

    private boolean constantTimeEquals(String a, String b) {
        if (a.length() != b.length()) return false;
        int result = 0;
        for (int i = 0; i < a.length(); i++) {
            result |= a.charAt(i) ^ b.charAt(i);
        }
        return result == 0;
    }
}
