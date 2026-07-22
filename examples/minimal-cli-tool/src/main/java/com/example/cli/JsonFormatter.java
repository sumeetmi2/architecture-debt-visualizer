package com.example.cli;

/**
 * Minimal, dependency-free JSON pretty-printer (indent-only, no re-parsing/validation — this
 * tool trusts its input is valid JSON and reformats whitespace around structural characters).
 */
public final class JsonFormatter {

    private JsonFormatter() {
    }

    public static String prettyPrint(String raw) {
        StringBuilder out = new StringBuilder();
        int indent = 0;
        boolean inString = false;
        for (int i = 0; i < raw.length(); i++) {
            char c = raw.charAt(i);
            if (c == '"' && (i == 0 || raw.charAt(i - 1) != '\\')) {
                inString = !inString;
                out.append(c);
            } else if (inString) {
                out.append(c);
            } else if (c == '{' || c == '[') {
                indent++;
                out.append(c).append('\n').append("  ".repeat(indent));
            } else if (c == '}' || c == ']') {
                indent--;
                out.append('\n').append("  ".repeat(indent)).append(c);
            } else if (c == ',') {
                out.append(c).append('\n').append("  ".repeat(indent));
            } else if (Character.isWhitespace(c)) {
                // collapse existing whitespace, we own formatting
            } else {
                out.append(c);
            }
        }
        return out.toString();
    }
}
