# template-lib

A small, embeddable Java templating library: compiles a named template plus a variable map into
rendered text. Published as a versioned Maven artifact (`com.example:template-lib`) and linked
directly into other services' processes — not a service of its own. See `docs/architecture.md` for
the component layout and `docs/technical-vision.md` for why it stays a library rather than growing
into a hosted rendering service.
