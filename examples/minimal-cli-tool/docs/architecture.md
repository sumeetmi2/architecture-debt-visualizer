# Architecture

`json-formatter` is a two-class command-line tool, invoked once per process, that pretty-prints a
JSON file to stdout.

## Key Components

| Component | Responsibility |
|---|---|
| `cli.JsonFormatterCli` | Entry point (`main`) — reads the file named in `args[0]`, calls the formatter, prints the result. |
| `cli.JsonFormatter` | Pure, stateless indent/reformat logic. No parsing/validation — trusts the input is valid JSON. |

## Data flow

1. Process starts, `main(String[] args)` runs.
2. File contents are read fully into memory as a `String`.
3. `JsonFormatter.prettyPrint` reformats it in a single pass.
4. Result is written to stdout; process exits.

There is no server, no listener, no background thread, no persistent state between invocations —
every run is a fresh process that does one thing and exits.
