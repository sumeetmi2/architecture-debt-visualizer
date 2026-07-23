package com.example.templates;

import java.util.List;

/** A template broken into literal-text and helper-invocation segments, ready to apply a vars map. */
public class CompiledTemplate {
    public interface Segment {
        String render(java.util.Map<String, Object> vars, HelperRegistry helpers);
    }

    private final List<Segment> segments;

    public CompiledTemplate(List<Segment> segments) {
        this.segments = segments;
    }

    public String render(java.util.Map<String, Object> vars, HelperRegistry helpers) {
        StringBuilder out = new StringBuilder();
        for (Segment s : segments) {
            out.append(s.render(vars, helpers));
        }
        return out.toString();
    }
}
