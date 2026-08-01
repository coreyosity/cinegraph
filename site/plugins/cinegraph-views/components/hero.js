import { h } from "preact"

// --- server-rendered film hero -----------------------------------------------
export const asArr = (v) => (v == null ? [] : Array.isArray(v) ? v.filter(Boolean) : [v])
const slugifyName = (s) => String(s).trim().toLowerCase().replace(/\s+/g, "-")

// Relative prefix from the current page's slug up to the site root, so chip links
// survive a subpath deploy (project GitHub Pages, /cinegraph/) the same way Quartz's
// own internal links do. A root-absolute "/themes/…" would drop the base and 404.
// slug "films/disturbia" (one folder deep) -> "..".
export const pathToRoot = (slug) => {
  const depth = String(slug || "").split("/").filter(Boolean).length - 1
  return depth < 1 ? "." : Array(depth).fill("..").join("/")
}

const filmChip = (name, folder, root) =>
  h("a", { class: "film-chip", href: root + "/" + folder + "/" + slugifyName(name) }, name)

const chipRow = (label, names, folder, root) =>
  !names || !names.length
    ? null
    : h("div", { class: "film-row" }, [
        h("span", { class: "film-row-label" }, label),
        h("span", { class: "film-chips" }, names.map((n) => filmChip(n, folder, root))),
      ])

const MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]

// "2023-02-24" -> "24 Feb 2023". Formatted from the string parts rather than via `new Date`,
// which reads a bare ISO date as UTC midnight and shifts it a day west of Greenwich.
const watchDate = (v) => {
  const m = /^(\d{4})-(\d{2})-(\d{2})/.exec(String(v))
  return m ? Number(m[3]) + " " + MONTHS[Number(m[2]) - 1] + " " + m[1] : String(v)
}

export const filmHero = (fm, slug) => {
  const cast = asArr(fm.cast), studios = asArr(fm.studios), genres = asArr(fm.genres)
  const providers = asArr(fm.providers)
  const root = pathToRoot(slug)
  const tagline = []
  if (fm.year) tagline.push(String(fm.year))
  if (fm.runtime) tagline.push(fm.runtime + " min")
  if (fm.country) tagline.push(fm.country)
  // Compact payload the client uses to compute "Related films" from films.json.
  const payload = JSON.stringify({
    tmdb_id: fm.tmdb_id != null ? fm.tmdb_id : null,
    director: fm.director || null,
    cast, genres, keywords: asArr(fm.keywords),
  }).replace(/</g, "\\u003c")

  return h("div", { class: "film-hero" }, [
    fm.poster
      ? h("div", { class: "film-poster" }, h("img", { src: fm.poster, alt: fm.title || "", loading: "lazy" }))
      : null,
    h("div", { class: "film-info" }, [
      h("div", { class: "film-tagline" }, [
        tagline.join("  ·  "),
        fm.rating != null ? h("span", { class: "film-rating" }, "  ★ " + fm.rating) : null,
      ]),
      fm.watched
        ? h("div", { class: "film-row" }, [
            h("span", { class: "film-row-label" }, "Watched"),
            h("span", { class: "film-watched" }, watchDate(fm.watched)),
          ])
        : null,
      providers.length
        ? h("div", { class: "film-row film-streaming" }, [
            h("span", { class: "film-row-label" }, "Where to watch"),
            h("span", { class: "film-chips" }, providers.map((p) => h("span", { class: "film-provider" }, p))),
          ])
        : null,
      fm.director ? chipRow("Director", [fm.director], "people", root) : null,
      chipRow("Cast", cast, "people", root),
      chipRow("Studios", studios, "studios", root),
      chipRow("Genres", genres, "genres", root),
      chipRow("Themes", asArr(fm.themes), "themes", root),
    ]),
    h("script", { type: "application/json", "data-cinegraph-film": "1", dangerouslySetInnerHTML: { __html: payload } }),
  ])
}
