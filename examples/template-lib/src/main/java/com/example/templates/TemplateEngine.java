package com.example.templates;

import com.example.templates.helpers.UpperCaseHelper;

import java.io.IOException;
import java.io.InputStream;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.Paths;
import java.util.Map;

/**
 * Public entry point. `render` widened its `vars` parameter from Map&lt;String, String&gt; to
 * Map&lt;String, Object&gt; in 1.2.0 (see ../../../../../../CHANGELOG.md) — a source-breaking
 * change for callers with an explicitly-typed Map&lt;String, String&gt; variable, shipped as a
 * minor version bump. `renderSafe` (the pre-1.1.0 escaping entry point) was removed outright in
 * 1.1.0, also a minor bump, with no deprecation cycle in between.
 */
public class TemplateEngine {
    private static final Path TEMPLATE_ROOT = Paths.get("templates");

    private final TemplateCache cache = new TemplateCache();
    private final TemplateCompiler compiler = new TemplateCompiler();
    private final HelperRegistry helpers = new HelperRegistry();

    public TemplateEngine() {
        helpers.register("upper", new UpperCaseHelper());
    }

    public String render(String templateName, Map<String, Object> vars) throws IOException {
        CompiledTemplate compiled = cache.get(templateName);
        if (compiled == null) {
            compiled = compiler.compile(loadTemplateBody(templateName));
            cache.put(templateName, compiled);
        }
        return compiled.render(vars, helpers);
    }

    // templateName is concatenated straight into a filesystem path with no validation that it
    // stays within TEMPLATE_ROOT — a caller-supplied "../../etc/passwd"-shaped name resolves
    // outside the templates directory rather than being rejected.
    private String loadTemplateBody(String templateName) throws IOException {
        Path resolved = TEMPLATE_ROOT.resolve(templateName + ".tmpl");
        try (InputStream in = Files.newInputStream(resolved)) {
            return new String(in.readAllBytes(), StandardCharsets.UTF_8);
        }
    }
}
