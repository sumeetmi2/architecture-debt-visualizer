# Architecture

`template-lib` compiles a named template plus a variable map into rendered text.

## Key Components

| Component | Responsibility |
|---|---|
| `TemplateEngine` | Public facade — `render(templateName, vars)`. Resolves the template, compiles it (cache permitting), and applies `vars`. |
| `TemplateCache` | In-memory LRU cache of compiled templates, keyed by template name. |
| `TemplateCompiler` | Parses a template string into an executable form; invokes registered helper functions for `{{helperName ...}}` expressions. |
| `HelperRegistry` | Extension point — where a template helper function registers itself so `TemplateCompiler` can dispatch to it by name. |

## Data flow

1. Caller invokes `TemplateEngine.render(templateName, vars)`.
2. `TemplateCache` returns the already-compiled template if present, else `TemplateCompiler`
   compiles it and the cache stores the result for reuse.
3. The compiled template's helper expressions are dispatched through `HelperRegistry`.
4. The rendered `String` is returned to the caller — no I/O, no network call, no disk write.

## Adding a new helper function

The supported pattern: implement `TemplateHelper` and register the instance with
`HelperRegistry.register(name, helper)` (see `helpers/UpperCaseHelper.java` for the reference
implementation) — `TemplateCompiler` dispatches to whatever's registered by name, so a new helper
never requires touching `TemplateCompiler` itself.
