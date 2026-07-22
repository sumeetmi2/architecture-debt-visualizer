package com.example.cli;

import java.io.IOException;
import java.nio.file.Files;
import java.nio.file.Path;

/**
 * Entry point. Reads a JSON file given as the first argument, pretty-prints it to stdout.
 * Single invocation, single process, no server, no persistent state.
 */
public final class JsonFormatterCli {

    public static void main(String[] args) throws IOException {
        if (args.length != 1) {
            System.err.println("usage: json-formatter <file>");
            System.exit(2);
        }
        String raw = Files.readString(Path.of(args[0]));
        System.out.println(JsonFormatter.prettyPrint(raw));
    }
}
