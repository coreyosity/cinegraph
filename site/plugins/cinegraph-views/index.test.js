// Regression tests for the CinegraphData emitter.
//
// The bug these guard: every quartz build starts with `rm -rf public` (quartz/build.ts),
// which deleted the data indexes gen_index.py had written into public/static, leaving the
// browser on "Could not load films.json" until the generator was re-run by hand. The emitter
// is what makes a build restore them instead, so it has to keep working — and it fails
// *silently* if it stops being registered (config-loader only console.warn()s an unresolvable
// plugin category, then carries on building a site with no data indexes).

import { test, describe } from "node:test"
import assert from "node:assert/strict"
import fs from "fs"
import os from "os"
import path from "path"
import { createRequire } from "module"

import { cinegraphData } from "./index.js"

const require = createRequire(import.meta.url)
const pkg = require("./package.json")

const mkTmp = () => fs.mkdtempSync(path.join(os.tmpdir(), "cinegraph-emitter-"))

// Drain the emit() async generator, returning the paths it yielded.
const runEmit = async (emitter, output) => {
  const yielded = []
  for await (const p of emitter.emit({ argv: { output } })) yielded.push(p)
  return yielded
}

describe("CinegraphData emitter", () => {
  test("copies data/*.json into <output>/static and yields each destination", async () => {
    const tmp = mkTmp()
    const dataDir = path.join(tmp, "data")
    fs.mkdirSync(dataDir)
    fs.writeFileSync(path.join(dataDir, "films.json"), '{"count":1}')
    fs.writeFileSync(path.join(dataDir, "discover.json"), '{"count":2}')

    const output = path.join(tmp, "public")
    const yielded = await runEmit(cinegraphData({ dir: dataDir }), output)

    const films = path.join(output, "static", "films.json")
    assert.equal(fs.readFileSync(films, "utf8"), '{"count":1}')
    assert.equal(fs.readFileSync(path.join(output, "static", "discover.json"), "utf8"), '{"count":2}')
    assert.deepEqual(yielded.sort(), [path.join(output, "static", "discover.json"), films].sort())
  })

  test("restores the indexes into an output dir the build just cleaned", async () => {
    // The actual regression: build.ts rm -rf's output, then emitters run. A missing
    // static/ subdir must not stop the copy.
    const tmp = mkTmp()
    fs.mkdirSync(path.join(tmp, "data"))
    fs.writeFileSync(path.join(tmp, "data", "films.json"), '{"films":[]}')

    const output = path.join(tmp, "public")
    assert.equal(fs.existsSync(output), false, "precondition: output was cleaned away")

    await runEmit(cinegraphData({ dir: path.join(tmp, "data") }), output)
    assert.ok(fs.existsSync(path.join(output, "static", "films.json")))
  })

  test("ignores non-JSON files", async () => {
    const tmp = mkTmp()
    fs.mkdirSync(path.join(tmp, "data"))
    fs.writeFileSync(path.join(tmp, "data", "films.json"), "{}")
    fs.writeFileSync(path.join(tmp, "data", "notes.txt"), "not an index")

    const output = path.join(tmp, "public")
    const yielded = await runEmit(cinegraphData({ dir: path.join(tmp, "data") }), output)

    assert.equal(yielded.length, 1)
    assert.equal(fs.existsSync(path.join(output, "static", "notes.txt")), false)
  })

  test("no-ops when the data dir is absent (fresh clone, generator never run)", async () => {
    const tmp = mkTmp()
    const output = path.join(tmp, "public")
    const yielded = await runEmit(cinegraphData({ dir: path.join(tmp, "nope") }), output)
    assert.deepEqual(yielded, [])
  })

  test("defaults to the cwd-relative 'data' dir that gen_index.py writes", async () => {
    // gen_index.write_json targets <site>/data, and quartz builds run with cwd=site/.
    // If this default drifts, the generator and the emitter silently disagree.
    const tmp = mkTmp()
    fs.mkdirSync(path.join(tmp, "data"))
    fs.writeFileSync(path.join(tmp, "data", "films.json"), '{"ok":true}')

    const cwd = process.cwd()
    try {
      process.chdir(tmp)
      await runEmit(cinegraphData(), "public")
      assert.ok(fs.existsSync(path.join(tmp, "public", "static", "films.json")))
    } finally {
      process.chdir(cwd)
    }
  })

  test("partialEmit yields nothing (partial rebuilds leave public/ intact)", async () => {
    const yielded = []
    for await (const p of cinegraphData().partialEmit()) yielded.push(p)
    assert.deepEqual(yielded, [])
  })
})

// These mirror how quartz/plugins/loader/config-loader.ts actually resolves a plugin. If any
// of them break, the build still succeeds — it just quietly stops emitting the data indexes.
describe("emitter registration contract", () => {
  test("package.json declares both the component and emitter categories", () => {
    const category = pkg.quartz.category
    assert.ok(Array.isArray(category), "category must be an array to claim two roles")
    assert.ok(category.includes("emitter"), "without this the emitter is never instantiated")
    assert.ok(category.includes("component"), "without this PosterGrid stops rendering")
  })

  test("the module exposes exactly one factory for findFactory to resolve", async () => {
    // findFactory prefers `default`, then `plugin`, then the *sole* exported function.
    const mod = await import("./index.js")
    assert.equal(typeof mod.default, "undefined")
    assert.equal(typeof mod.plugin, "undefined")
    const fns = Object.entries(mod).filter(
      ([k, v]) => typeof v === "function" && !k.startsWith("__"),
    )
    assert.equal(fns.length, 1, "a second exported function makes resolution ambiguous")
  })

  test("the factory is tagged and returns an instance validateCategory accepts", () => {
    assert.equal(cinegraphData.quartzCategory, "emitter")
    const instance = cinegraphData()
    assert.ok(instance && typeof instance === "object")
    assert.ok("emit" in instance, "validateCategory('emitter') requires an emit method")
    assert.equal(typeof instance.name, "string")
  })

  test("the manifest still declares the PosterGrid component", () => {
    assert.ok(pkg.quartz.components?.PosterGrid, "components drive loadComponentsFromPackage")
  })
})
