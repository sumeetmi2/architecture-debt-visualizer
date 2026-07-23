package com.example.templates;

import java.util.LinkedHashMap;
import java.util.Map;

/**
 * In-memory LRU cache of compiled templates. MAX_SIZE is a literal, not read from any
 * system property, config file, or constructor argument — every embedding service gets the same
 * 200-entry ceiling regardless of how many distinct template names it actually renders.
 */
public class TemplateCache {
    private static final int MAX_SIZE = 200;

    private final Map<String, CompiledTemplate> cache = new LinkedHashMap<String, CompiledTemplate>(16, 0.75f, true) {
        @Override
        protected boolean removeEldestEntry(Map.Entry<String, CompiledTemplate> eldest) {
            return size() > MAX_SIZE;
        }
    };

    public CompiledTemplate get(String templateName) {
        return cache.get(templateName);
    }

    public void put(String templateName, CompiledTemplate compiled) {
        cache.put(templateName, compiled);
    }
}
