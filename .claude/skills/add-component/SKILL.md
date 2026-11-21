---
name: add-component
description: Use when adding any new class to spacegeo (scraper, reader, preprocessor, feature, model, metric, trainer helper) or changing an interface. The general OOP/SOLID recipe the more specific skills build on.
---

# Add a component

## 1. Place it

- Which layer owns this responsibility? `data/scraping`, `data/io`,
  `data/preprocessing`, `features`, `models`, `evaluation`, `training`.
- Does it need anything from a layer **above** it? Then it's in the wrong
  layer, or the dependency should be injected as an abstraction.
- Is any part of it useful to another layer? Put that part in
  `spacegeo/common/` first, with its own tests, then use it.

## 2. Check `common` before writing helpers

Search `src/spacegeo/common/` for time, geo, validation, provenance,
registry, config, http, fitting and logging utilities. Extend an existing
utility rather than writing a near-duplicate. CI's duplicate-code check and
`tests/architecture` will flag copies.

## 3. Implement against the interface

- Subclass the layer's ABC from its `base.py`. Implement only the abstract
  hooks; let the base class own the shared workflow.
- If the ABC doesn't fit, change the ABC deliberately (and every
  implementation and contract test) rather than working around it.
  Prefer adding a new small interface over growing an existing one.
- Constructor takes its collaborators as abstractions (protocols/ABCs) with
  sensible defaults; no hidden globals, no I/O in `__init__`.
- Public methods: typed, Google-style docstrings with units.
- Keep methods small; ruff fails at complexity > 8 or > 6 args. Split
  responsibilities into private methods or collaborator classes.
- No public module-level functions outside `common`.
- Register the class in its layer registry: `@FEATURES.register("name")`.

## 4. Test it

- Unit tests in `tests/<layer>/` for its specific behaviour.
- It is automatically picked up by `tests/contracts/` for its interface. If
  the interface has no contract test yet and you're adding the second
  implementation, write the contract test now.
- Use fakes for collaborators (e.g. a fake `HttpClient`), never the network.

## 5. Verify

```
uv run ruff format . && uv run ruff check . && uv run pyright \
  && uv run lint-imports && uv run pytest
```

All green, then commit on a branch.
