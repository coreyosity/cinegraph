# Quartz provenance & local changes

`site/` is a **vendored** checkout of Quartz (the static-site generator that publishes the
vault). It is committed in-tree rather than as a submodule because (a) this modular Quartz
is designed to live in-tree, (b) we patch the engine source itself (see below), which a
submodule handles badly, and (c) it's a fast-moving release where vendoring is the
reproducible choice.

- **Upstream:** https://github.com/jackyzha0/quartz  (`@jackyzha0/quartz`)
- **Version:** 5.0.0 (the modular rewrite; plugins are `@quartz-community/*` npm packages,
  config is `quartz.config.yaml`)
- **Not committed** (see `.gitignore`): `node_modules/`, `public/` (build output),
  `.quartz-cache/`.

## What is *ours* (the real work under `site/`)

1. `quartz.config.yaml` — site configuration + plugin selection.
2. `plugins/cinegraph-views/` — our local Quartz plugin (poster grid & client-side views
   over `static/films.json`).
3. One engine patch (below).

## Local engine patch

**`quartz/plugins/loader/config-loader.ts`** — `extractPluginName()` didn't strip the npm
scope, so scoped plugins (`@quartz-community/footer`) never matched the unscoped names used
in the footer special-case and `byPageType` exclude lists. The footer slot was left unset
and rendered as a literal `<undefined>` blob with the whole file list inlined into every
page (~10× page bloat). The fix strips the scope:

```ts
// npm scoped package (e.g. "@quartz-community/footer") — strip the scope so the
// plugin name matches unscoped identifiers used in config.
if (source.startsWith("@") && source.includes("/")) {
  return source.split("/").pop()!
}
```

Full write-up (impact table, root cause, reproduction) is in the project's local
`.ai/quartz-bloat-bug-report.md`.

**TODO:** file this as an upstream PR to `jackyzha0/quartz`. Once merged and released, drop
the patch and bump the vendored version so we stop carrying it.
