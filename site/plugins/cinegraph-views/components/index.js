import { h } from "preact"
import { cinegraphViewsCss } from "./styles.js"
import { cinegraphViewsClient } from "./client.js"
import { asArr, filmHero } from "./hero.js"

// --- Component ---------------------------------------------------------------
// One component, mounted beforeBody on every page. It emits the right mount for
// the current page and returns null everywhere else; the client script above
// fills whichever mount is present.
export const PosterGrid = () => {
  // stub `type` → the entity kind rendered by the client (studio/genre/theme pages)
  const KIND_BY_TYPE = { studio: "studio", genre: "genre", theme: "theme", logtag: "logtag" }
  const cap = (r) => (r ? r[0].toUpperCase() + r.slice(1) : r)

  const View = ({ fileData }) => {
    const slug = fileData?.slug
    const fm = fileData?.frontmatter || {}

    if (slug === "stats" || slug === "Stats")
      return h("div", { class: "stats-wrapper", "data-stats": "1" })

    if (slug === "ensemble" || slug === "Ensemble")
      return h("div", { class: "ensemble-wrapper", "data-ensemble": "1" })

    if (slug === "tag-graph" || slug === "Tag graph")
      return h("div", { class: "ensemble-wrapper", "data-tag-graph": "1" })

    // The film constellation is the hero graph on the home page (graph only)…
    if (slug === "index")
      return h("div", { class: "constellation-wrapper", "data-constellation": "1" })

    // …and the full atlas (graph + island/bridge/orphan panel) lives on its own page.
    if (slug === "taste-map" || slug === "Taste Map")
      return h("div", { class: "constellation-wrapper", "data-constellation": "1", "data-panel": "1" })

    if (slug === "films/index")
      return h("div", { class: "poster-grid-wrapper", "data-poster-grid": "1" })

    if (slug === "discover/index")
      return h("div", { class: "disc-wrapper", "data-discover": "1" })

    if (slug === "up-next" || slug === "Up Next")
      return h("div", { class: "disc-wrapper", "data-upnext": "1" })

    // Film pages (Films/, Watchlist/) and individual recommendations get the rich hero.
    if ((fm.type === "film" || fm.type === "recommendation") && slug !== "films/index")
      return filmHero(fm)

    // Person pages: a stats line + a client-filled body (directed/acted/related).
    if (fm.type === "person") {
      const name = fm.title || slug?.split("/").pop()
      const meta = []
      const roles = asArr(fm.roles).map(cap).join(" · ")
      if (roles) meta.push(roles)
      if (fm.film_count) meta.push(fm.film_count + (fm.film_count === 1 ? " film" : " films"))
      if (fm.avg_rating != null) meta.push("your avg ★ " + fm.avg_rating)
      return h("div", { class: "person-wrapper" }, [
        meta.length ? h("div", { class: "person-meta" }, meta.join("  ·  ")) : null,
        h("div", { class: "person-body", "data-person": "1", "data-name": name }),
      ])
    }

    // Studio / genre / theme pages: stats line + client-filled body.
    const kind = KIND_BY_TYPE[fm.type]
    if (kind) {
      const name = fm.title || slug?.split("/").pop()
      const meta = []
      if (fm.film_count) meta.push(fm.film_count + (fm.film_count === 1 ? " film" : " films"))
      if (fm.avg_rating != null) meta.push("your avg ★ " + fm.avg_rating)
      return h("div", { class: "person-wrapper" }, [
        meta.length ? h("div", { class: "person-meta" }, meta.join("  ·  ")) : null,
        h("div", { class: "person-body", "data-entity": "1", "data-kind": kind, "data-name": name }),
      ])
    }
    return null
  }
  View.displayName = "PosterGrid"
  View.css = cinegraphViewsCss
  View.afterDOMLoaded = "(" + cinegraphViewsClient.toString() + ")();"
  return View
}
