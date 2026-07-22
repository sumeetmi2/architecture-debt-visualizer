# json-formatter

A tiny command-line tool: reads a JSON file, pretty-prints it to stdout.

```
json-formatter path/to/file.json
```

Single invocation, single process, no server, no persistent state between runs. See
`docs/architecture.md` for the two-class structure and `docs/technical-vision.md` for why this
stays a CLI tool rather than growing into a service.
