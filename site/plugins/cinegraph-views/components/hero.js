import { h } from "preact"

// --- server-rendered film hero -----------------------------------------------
export const asArr = (v) => (v == null ? [] : Array.isArray(v) ? v.filter(Boolean) : [v])
const slugifyName = (s) => String(s).trim().toLowerCase().replace(/\s+/g, "-")

const filmChip = (name, folder) =>
  h("a", { class: "film-chip", href: "/" + folder + "/" + slugifyName(name) }, name)

const chipRow = (label, names, folder) =>
  !names || !names.length
    ? null
    : h("div", { class: "film-row" }, [
        h("span", { class: "film-row-label" }, label),
        h("span", { class: "film-chips" }, names.map((n) => filmChip(n, folder))),
      ])

export const filmHero = (fm) => {
  const cast = asArr(fm.cast), studios = asArr(fm.studios), genres = asArr(fm.genres)
  const providers = asArr(fm.providers)
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
      providers.length
        ? h("div", { class: "film-row film-streaming" }, [
            h("span", { class: "film-row-label" }, "Where to watch"),
            h("span", { class: "film-chips" }, providers.map((p) => h("span", { class: "film-provider" }, p))),
          ])
        : null,
      fm.director ? chipRow("Director", [fm.director], "people") : null,
      chipRow("Cast", cast, "people"),
      chipRow("Studios", studios, "studios"),
      chipRow("Genres", genres, "genres"),
      chipRow("Themes", asArr(fm.themes), "themes"),
    ]),
    h("script", { type: "application/json", "data-cinegraph-film": "1", dangerouslySetInnerHTML: { __html: payload } }),
  ])
}
