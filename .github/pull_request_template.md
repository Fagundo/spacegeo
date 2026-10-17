## What and why

## Design check

- [ ] Code is in the layer that owns the responsibility; shared parts are in `common`
- [ ] New classes subclass their layer's interface and are registered
- [ ] No new public functions outside `common`
- [ ] Collaborators are injected as abstractions

## Science check (if features, splits, targets or evaluation changed)

- [ ] Ran the `science-review` skill; results pasted below
- [ ] No test-period data touched (or unlock recorded in `docs/test-unlocks.md`)
