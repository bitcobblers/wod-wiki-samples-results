# Contributing content

Merge requests here add programs, workouts, dashboards, and efforts to the
community system. Every MR goes through the same validation the build runs.

## Quick path

1. Fork, branch, add/edit files under `markdown/` only.
2. `npm install && npx wod build` — the full compile + validation gates
   must pass.
3. Open the MR. CI runs the same `wod build` and posts a manifest summary
   comment on the MR.

## Corpus rules (enforced by the build)

- **Collections** — `markdown/collections/<catalog>/`: one directory per
  catalog, a `README.md` (frontmatter `category:` list + prose), and one
  `.md` per item. Workout blocks use the Whiteboard Language (```time /
  ```wod fences). A new catalog directory is picked up automatically as its
  own seed chunk.
- **Feeds** — `markdown/feeds/<slug>/<yyyy-mm-dd>/<item>.md`, one item per
  date directory.
- **Canvas guides** — live in the wod-wiki repo (`markdown/canvas/`), not
  here; the app's core-seed build compiles them there. Community seeds MAY
  carry routable pages the same way (frontmatter `template: canvas` +
  `route: /...`); fragments/snippets without a route stay out of the
  Library index by design.
- **Dashboards** — locked #899 note format; widget types and `$token`
  references are validated by the build itself (WQL bodies must parse).
- **Efforts** — frontmatter documents (`slug`, `label`, `aliases`,
  `baseAttributes.met` > 0, optional `discipline`/`intensityTier`, and an
  optional `equipment:` slug list). Unregistered effort labels referenced by
  workouts are reported by `wod build --scaffold`, which drafts stubs under
  `markdown/efforts/discovered/` for curation.
- **Equipment** — `markdown/equipment/<slug>.md`: frontmatter documents
  (`type: equipment`, `slug`, `label`, `aliases`, optional body). The
  compiler resolves equipment mentions in workout blocks against this
  registry (by slug, label, or alias) and emits per-block equipment rows;
  an effort's `equipment:` array auto-tags the blocks that use it.
- A new top-level directory under `markdown/` **fails the build** (parity
  gate) until the compiler's corpus partition learns it — open an issue in
  the wod-wiki repo (the compiler lives in
  `@bitcobblers/wod-wiki-tools`, the `wod build` CLI).

## What lands in an MR

- Content edits (the common case): only `markdown/` changes. The manifest
  and chunk hashes regenerate at release time — never commit `dist/`.
- Compiler/contract changes: live in the wod-wiki repo
  (`@bitcobblers/wod-wiki-tools`); they need discussion there — they
  affect every consumer of the artifacts. Keep the seed contract
  shape-compatible with the app's `apps/playground/src/types/seed.ts`.

## Release flow (maintainers)

Merges to `main` advance `manifest.version` (commit count) and deploy the
built `dist/` to GitHub Pages automatically. To cut a release the app
should pin: `git tag vX.Y.Z` — the next main build stamps the manifest
with `git describe`. The app diffs manifests to decide which chunks to
re-import.
