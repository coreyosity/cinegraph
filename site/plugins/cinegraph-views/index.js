// Entry point for the "." export. The plugin manifest is read from the "quartz"
// field in package.json (see config-loader's readManifestFromPackageJson), so this
// only needs to exist for the exports map. Components live in ./components.
export const manifest = null

import fs from "fs"
import path from "path"

// Every build starts with `rm -rf public` (quartz/build.ts), which used to wipe the data
// indexes gen_index.py had written into public/static → "Could not load films.json" until
// the generator was re-run. So the generator's durable output lives in site/data/ and this
// emitter copies it into the build on every pass, making a rebuild self-healing.
//
// site/data/ is deliberately outside both watchers: the content watcher only sees
// `argv.directory` (content/ → the vault), and serve's source watcher globs *.ts/*.tsx/
// *.scss, quartz/cli/*.js, quartz/static/**/*, package.json and quartz.config*.yaml
// (quartz/cli/handlers.js). Writing JSON there triggers nothing.
export const cinegraphData = (opts) => {
  const dir = opts?.dir ?? "data"
  return {
    name: "CinegraphData",
    async *emit({ argv }) {
      if (!fs.existsSync(dir)) return
      const outDir = path.join(argv.output, "static")
      await fs.promises.mkdir(outDir, { recursive: true })
      for (const name of await fs.promises.readdir(dir)) {
        if (!name.endsWith(".json")) continue
        const dest = path.join(outDir, name)
        await fs.promises.copyFile(path.join(dir, name), dest)
        yield dest
      }
    },
    // Partial rebuilds leave public/ in place, so the files copied above are still there.
    async *partialEmit() {},
  }
}

cinegraphData.quartzCategory = "emitter"
