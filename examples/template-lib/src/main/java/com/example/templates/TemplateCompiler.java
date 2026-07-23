package com.example.templates;

import java.time.LocalDate;
import java.time.format.DateTimeFormatter;
import java.util.ArrayList;
import java.util.List;
import java.util.Map;
import java.util.regex.Matcher;
import java.util.regex.Pattern;

/**
 * Compiles a template string containing {{helperName varName}} expressions into a
 * {@link CompiledTemplate}. Every helper *except* "dateFormat" dispatches through
 * {@link HelperRegistry} per the documented extension pattern (docs/architecture.md) — dateFormat
 * is special-cased inline below instead of being a registered TemplateHelper, because it predates
 * HelperRegistry and nobody has circled back to move it. Same shape of extension
 * (helperName -> transform(value)) modeled two structurally different ways in the same file.
 */
public class TemplateCompiler {
    private static final Pattern EXPR = Pattern.compile("\\{\\{(\\w+)\\s+(\\w+)}}");
    private static final DateTimeFormatter DATE_FORMAT = DateTimeFormatter.ofPattern("yyyy-MM-dd");

    public CompiledTemplate compile(String templateBody) {
        List<CompiledTemplate.Segment> segments = new ArrayList<>();
        Matcher m = EXPR.matcher(templateBody);
        int last = 0;
        while (m.find()) {
            if (m.start() > last) {
                String literal = templateBody.substring(last, m.start());
                segments.add((vars, helpers) -> literal);
            }
            String helperName = m.group(1);
            String varName = m.group(2);
            segments.add(buildSegment(helperName, varName));
            last = m.end();
        }
        if (last < templateBody.length()) {
            String literal = templateBody.substring(last);
            segments.add((vars, helpers) -> literal);
        }
        return new CompiledTemplate(segments);
    }

    private CompiledTemplate.Segment buildSegment(String helperName, String varName) {
        if ("dateFormat".equals(helperName)) {
            // Inline special case — bypasses HelperRegistry entirely, unlike every other helper.
            return (vars, helpers) -> {
                Object value = vars.get(varName);
                return value instanceof LocalDate ? ((LocalDate) value).format(DATE_FORMAT) : String.valueOf(value);
            };
        }
        return (vars, helpers) -> {
            TemplateHelper helper = helpers.get(helperName);
            return helper == null ? "" : helper.apply(vars.get(varName));
        };
    }
}
