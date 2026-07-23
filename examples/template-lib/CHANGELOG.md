# Changelog

## 1.2.1
- Internal: `TemplateCache` eviction bug fix (stale entries could survive past their reload
  window under high churn).

## 1.2.0
- `TemplateEngine.render(String, Map<String, Object>)` — widened the second parameter from
  `Map<String, String>` to `Map<String, Object>` so templates can bind non-string values (numbers,
  nested maps) directly. Existing callers passing a `Map<String, String>` continue to compile
  against the wider type.

## 1.1.0
- Removed `TemplateEngine.renderSafe(String, Map<String, String>)` — superseded by `render`, which
  now HTML-escapes by default. No replacement needed for most callers; inline the escaping
  yourself if you relied on `renderSafe`'s specific behavior.

## 1.0.0
- Initial release: `TemplateEngine`, `TemplateCache`, helper-function registration via
  `HelperRegistry`.
