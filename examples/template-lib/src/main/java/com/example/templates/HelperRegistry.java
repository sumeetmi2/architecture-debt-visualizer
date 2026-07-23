package com.example.templates;

import java.util.HashMap;
import java.util.Map;

/** Registration point for {@link TemplateHelper}s — see docs/architecture.md. */
public class HelperRegistry {
    private final Map<String, TemplateHelper> helpers = new HashMap<>();

    public void register(String name, TemplateHelper helper) {
        helpers.put(name, helper);
    }

    public TemplateHelper get(String name) {
        return helpers.get(name);
    }
}
