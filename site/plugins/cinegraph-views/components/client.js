// --- Client script -----------------------------------------------------------
// Runs in the browser (bundled into postscript.js, executed on every page). It
// only acts when a mount element exists on the page:
//   [data-poster-grid]            → the Films folder page (all films)
//   [data-poster-grid][data-field]→ an entity page (films filtered by that entity)
//   [data-stats]                  → the Stats dashboard page
// Serialized via .toString(), so it must be fully self-contained (no closures).
export function cinegraphViewsClient() {
  var CACHE = null // films.json, fetched once and reused across SPA navigations
  var DETAIL = null // films-detail.json — only the views below pull it in; see detailPayload
  var BASE = ""    // deploy base path (e.g. "/cinegraph" under project GitHub Pages); see computeBase

  function esc(s) {
    return String(s == null ? "" : s).replace(/[&<>"']/g, function (c) {
      return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]
    })
  }

  // Base-path support so the *same* build works at the domain root (local `--serve`) and
  // under a subpath (project GitHub Pages, e.g. /cinegraph/). Quartz stamps <body data-slug>;
  // the deploy base is the current path with that slug stripped off. Every root-absolute URL
  // the client builds — fetches, entity links, and the URLs baked into films.json — is then
  // prefixed with it. An empty base (root deploy) makes withBase a no-op.
  function computeBase() {
    var slug = (document.body && document.body.dataset && document.body.dataset.slug) || ""
    var path = decodeURIComponent(location.pathname)
      .replace(/\.html$/, "").replace(/\/index$/, "").replace(/\/+$/, "")
    var tail = slug.replace(/(^|\/)index$/, "")   // "index"->"", "films/index"->"films"
    if (!tail) return path                          // home / folder index: the whole path is base
    var suffix = "/" + tail
    return path.length >= suffix.length && path.slice(-suffix.length) === suffix
      ? path.slice(0, -suffix.length)
      : ""
  }
  function withBase(p) {
    return typeof p === "string" && p.charAt(0) === "/" ? BASE + p : p
  }

  async function filmsPayload() {
    if (!CACHE) {
      CACHE = await (await fetch(withBase("/static/films.json"))).json()
      ;(CACHE.films || []).forEach(function (f) { f.url = withBase(f.url) })
      ;(CACHE.islands || []).forEach(function (i) {
        ;(i.examples || []).forEach(function (e) { e.url = withBase(e.url) })
      })
    }
    return CACHE
  }
  async function films() {
    return (await filmsPayload()).films || []
  }

  // The heavy tail (keywords / related / taste-map markers) lives in a second file so the
  // ~80% of pages that never read it don't pay for it. Only Stats, film pages, and the
  // constellation call this. Rows are index-aligned with films.json (see gen_index.split_detail)
  // and merged *into* the cached film objects, so every view downstream reads them as
  // ordinary fields. A length mismatch means a skewed cache — skip the merge rather than
  // join the wrong rows together.
  async function detailPayload() {
    if (!DETAIL) {
      var base = await filmsPayload()
      var payload = await (await fetch(withBase("/static/films-detail.json"))).json()
      var list = base.films || []
      var rows = payload.detail || []
      if (rows.length === list.length)
        for (var i = 0; i < list.length; i++)
          for (var k in rows[i]) list[i][k] = rows[i][k]
      DETAIL = payload
    }
    return DETAIL
  }

  // --- filtering: which films belong to an entity page -----------------------
  function matches(f, field, value) {
    if (field === "person")
      return f.director === value || (f.cast || []).indexOf(value) !== -1
    if (field === "director") return f.director === value
    if (field === "genre") return (f.genres || []).indexOf(value) !== -1
    if (field === "studio") return (f.studios || []).indexOf(value) !== -1
    return true
  }

  // --- poster grid (all films, or an entity's filmography) -------------------
  function card(f) {
    var poster = f.poster
      ? '<img loading="lazy" src="' + esc(f.poster) + '" alt="' + esc(f.title) + '">'
      : '<div class="poster-fallback">' + esc(f.title) + "</div>"
    var year = f.year ? " (" + f.year + ")" : ""
    var rating = f.rating != null ? '<span class="poster-rating">★ ' + f.rating + "</span>" : ""
    return (
      '<a class="poster-card" href="' + esc(f.url) + '" title="' +
      esc(f.title) + esc(year) + '">' + poster +
      '<div class="poster-meta"><span class="poster-title">' +
      esc(f.title) + "</span>" + rating + "</div></a>"
    )
  }

  function sortFilms(arr, mode) {
    arr = arr.slice()
    if (mode === "year") arr.sort(function (a, b) { return (b.year || 0) - (a.year || 0) })
    else if (mode === "title") arr.sort(function (a, b) { return String(a.title).localeCompare(String(b.title)) })
    // ISO "YYYY-MM-DD" dates compare correctly as plain strings; "" sinks the undated.
    else if (mode === "watched") arr.sort(function (a, b) {
      return String(b.watched || "").localeCompare(String(a.watched || "")) ||
        String(a.title).localeCompare(String(b.title))
    })
    else arr.sort(function (a, b) { return (b.rating || -1) - (a.rating || -1) || (b.year || 0) - (a.year || 0) })
    return arr
  }

  async function renderGrid(mount) {
    if (mount.dataset.rendered) return
    mount.dataset.rendered = "1"
    var field = mount.dataset.field || null
    var value = mount.dataset.value || null
    mount.innerHTML =
      '<div class="poster-grid-toolbar">' +
      '<span class="poster-grid-status">Loading…</span>' +
      '<label class="poster-grid-sort">Sort' +
      '<select><option value="watched">Watch date</option><option value="rating">Rating</option>' +
      '<option value="year">Year</option><option value="title">Title</option></select>' +
      "</label></div>" +
      '<div class="poster-grid"></div>'
    var status = mount.querySelector(".poster-grid-status")
    var grid = mount.querySelector(".poster-grid")
    var select = mount.querySelector("select")
    var list
    try {
      list = await films()
    } catch (e) {
      status.textContent = "Could not load films.json"
      return
    }
    if (field) list = list.filter(function (f) { return matches(f, field, value) })
    // All films defaults to watch date (the diary read); filmographies stay chronological.
    select.value = field ? "year" : "watched"
    function draw() {
      var arr = sortFilms(list, select.value)
      grid.innerHTML = arr.map(card).join("")
      status.textContent = arr.length + (arr.length === 1 ? " film" : " films")
    }
    select.addEventListener("change", draw)
    draw()
  }

  // --- stats dashboard -------------------------------------------------------
  function bars(entries, opts) {
    opts = opts || {}
    var max = opts.max || 0
    if (!opts.max)
      for (var i = 0; i < entries.length; i++) if (entries[i].value > max) max = entries[i].value
    max = max || 1
    return entries.map(function (e) {
      var pct = Math.round((e.value / max) * 100)
      var label = opts.link
        ? '<a href="' + esc(e.link) + '">' + esc(e.label) + "</a>"
        : esc(e.label)
      return (
        '<div class="stat-row"><span class="stat-label">' + label + "</span>" +
        '<span class="stat-bar"><span class="stat-fill" style="width:' + pct + '%"></span></span>' +
        '<span class="stat-value">' + e.value + "</span></div>"
      )
    }).join("")
  }

  function tally(list, pick) {
    var m = {}
    for (var i = 0; i < list.length; i++) {
      var vals = pick(list[i])
      for (var j = 0; j < vals.length; j++) {
        var v = vals[j]
        if (v == null || v === "") continue
        m[v] = (m[v] || 0) + 1
      }
    }
    return Object.keys(m)
      .map(function (k) { return { label: k, value: m[k] } })
      .sort(function (a, b) { return b.value - a.value })
  }

  // avg rating per attribute value, over rated films only. Returns
  // [{label, value: avg(2dp), count}] sorted by avg desc, filtered to count >= minCount.
  function avgBy(list, pick, minCount) {
    var m = {}
    for (var i = 0; i < list.length; i++) {
      var f = list[i]
      if (f.rating == null) continue
      var vals = pick(f)
      for (var j = 0; j < vals.length; j++) {
        var v = vals[j]
        if (v == null || v === "") continue
        if (!m[v]) m[v] = { sum: 0, n: 0 }
        m[v].sum += f.rating
        m[v].n += 1
      }
    }
    return Object.keys(m)
      .filter(function (k) { return m[k].n >= (minCount || 1) })
      .map(function (k) { return { label: k, value: Math.round((m[k].sum / m[k].n) * 100) / 100, count: m[k].n } })
      .sort(function (a, b) { return b.value - a.value })
  }

  function section(title, html) {
    return '<section class="stat-block"><h2>' + esc(title) + "</h2>" + html + "</section>"
  }

  async function renderStats(mount) {
    if (mount.dataset.rendered) return
    mount.dataset.rendered = "1"
    var list
    try {
      list = await films()
      await detailPayload() // "Themes you love/avoid" reads f.keywords
    } catch (e) {
      mount.innerHTML = "<p>Could not load films.json</p>"
      return
    }
    var rated = list.filter(function (f) { return f.rating != null })
    var meanRating = rated.length
      ? (rated.reduce(function (s, f) { return s + f.rating }, 0) / rated.length).toFixed(2)
      : "—"
    var totalMins = list.reduce(function (s, f) { return s + (f.runtime || 0) }, 0)
    var hours = Math.round(totalMins / 60)

    // rating distribution 0.5 .. 5.0 in half-steps
    var buckets = {}
    for (var r = 0.5; r <= 5.0001; r += 0.5) buckets[r.toFixed(1)] = 0
    rated.forEach(function (f) {
      var k = (Math.round(f.rating * 2) / 2).toFixed(1)
      if (k in buckets) buckets[k]++
    })
    var ratingRows = Object.keys(buckets).map(function (k) {
      return { label: "★ " + k, value: buckets[k] }
    })

    // decades
    var decRows = tally(list, function (f) {
      return f.year ? [String(Math.floor(f.year / 10) * 10) + "s"] : []
    }).sort(function (a, b) { return a.label < b.label ? -1 : 1 })

    function base(field) {
      return "/" + field + "/"
    }
    function slug(name) {
      return String(name).trim().toLowerCase().replace(/\s+/g, "-")
    }
    function linked(rows, folder) {
      return rows.map(function (e) {
        return { label: e.label, value: e.value, link: withBase("/" + folder + "/" + slug(e.label)) }
      })
    }

    var directors = tally(list, function (f) { return f.director ? [f.director] : [] }).slice(0, 15)
    var actors = tally(list, function (f) { return f.cast || [] }).slice(0, 15)
    var genres = tally(list, function (f) { return f.genres || [] }).slice(0, 12)
    var studios = tally(list, function (f) { return f.studios || [] }).slice(0, 15)

    // Themes you love / avoid — TMDB keywords ranked by your avg rating (>= 4 rated films).
    var themes = avgBy(list, function (f) { return f.keywords || [] }, 4)
    var themesTop = themes.slice(0, 12)
    var themesBottom = themes.slice(-10).reverse()

    // Runtime vs rating — do you actually reward long films?
    var rtBins = [
      { label: "< 90m", lo: 0, hi: 90 },
      { label: "90–119m", lo: 90, hi: 120 },
      { label: "120–149m", lo: 120, hi: 150 },
      { label: "150m +", lo: 150, hi: 1e9 },
    ]
    var rtRows = rtBins.map(function (b) {
      var sub = rated.filter(function (f) { return f.runtime && f.runtime >= b.lo && f.runtime < b.hi })
      var avg = sub.length ? Math.round((sub.reduce(function (s, f) { return s + f.rating }, 0) / sub.length) * 100) / 100 : 0
      return { label: b.label + " (" + sub.length + ")", value: avg }
    }).filter(function (r) { return r.value > 0 })

    // Country / language — how international is your taste
    var LANG = {
      en: "English", ja: "Japanese", ko: "Korean", fr: "French", es: "Spanish",
      de: "German", it: "Italian", zh: "Chinese", cn: "Chinese", hi: "Hindi",
      ru: "Russian", pt: "Portuguese", sv: "Swedish", da: "Danish", no: "Norwegian",
      nl: "Dutch", pl: "Polish", th: "Thai", fa: "Persian", ta: "Tamil", tr: "Turkish",
      ar: "Arabic", he: "Hebrew", is: "Icelandic", fi: "Finnish", cs: "Czech",
      el: "Greek", hu: "Hungarian", ro: "Romanian", uk: "Ukrainian", id: "Indonesian",
    }
    var countries = tally(list, function (f) { return f.country ? [f.country] : [] }).slice(0, 12)
    var languages = tally(list, function (f) {
      return f.language ? [LANG[f.language] || String(f.language).toUpperCase()] : []
    }).slice(0, 10)

    mount.innerHTML =
      '<div class="stat-cards">' +
      '<div class="stat-card"><span class="stat-num">' + list.length + "</span><span>films</span></div>" +
      '<div class="stat-card"><span class="stat-num">' + rated.length + "</span><span>rated</span></div>" +
      '<div class="stat-card"><span class="stat-num">' + meanRating + "</span><span>avg ★</span></div>" +
      '<div class="stat-card"><span class="stat-num">' + hours.toLocaleString() + "</span><span>hours</span></div>" +
      "</div>" +
      '<div class="stat-grid">' +
      section("Rating distribution", bars(ratingRows)) +
      section("Films by decade", bars(decRows)) +
      section("Top directors", bars(linked(directors, "people"), { link: true })) +
      section("Most-watched actors", bars(linked(actors, "people"), { link: true })) +
      section("Genres", bars(linked(genres, "genres"), { link: true })) +
      section("Top studios", bars(linked(studios, "studios"), { link: true })) +
      section("Themes you love (avg ★)", bars(themesTop, { max: 5 })) +
      section("Themes you rate lowest", bars(themesBottom, { max: 5 })) +
      section("Runtime vs rating (avg ★)", bars(rtRows, { max: 5 })) +
      section("Countries you watch", bars(countries)) +
      section("Languages", bars(languages)) +
      "</div>" +
      '<section class="stat-block stat-map"><h2>World map of your cinema</h2>' +
      '<div class="cinemap">Loading map…</div></section>'
    var mapEl = mount.querySelector(".cinemap")
    if (mapEl) renderChoropleth(mapEl, list)
  }

  // --- actor collaboration network -------------------------------------------
  function slugify(s) {
    return String(s).trim().toLowerCase().replace(/\s+/g, "-")
  }

  function ensureScript(src, id, ready, cb) {
    if (ready()) return cb()
    var existing = document.querySelector('script[data-cg="' + id + '"]')
    if (existing) return existing.addEventListener("load", cb)
    var s = document.createElement("script")
    s.src = src
    s.setAttribute("data-cg", id)
    s.onload = function () { cb() }
    document.head.appendChild(s)
  }
  function ensureD3(cb) {
    ensureScript("https://cdn.jsdelivr.net/npm/d3@7/dist/d3.min.js", "d3",
      function () { return !!window.d3 }, cb)
  }
  function ensureTopojson(cb) {
    ensureScript("https://cdn.jsdelivr.net/npm/topojson-client@3/dist/topojson-client.min.js",
      "topojson", function () { return !!window.topojson }, cb)
  }

  async function renderEnsemble(mount) {
    if (mount.dataset.rendered) return
    mount.dataset.rendered = "1"
    var list
    try {
      list = await films()
    } catch (e) {
      mount.innerHTML = "<p>Could not load films.json</p>"
      return
    }
    var MIN_FILMS = 4, MIN_PAIR = 3, MAX_NODES = 90
    var actorFilms = {}, pairs = {}
    list.forEach(function (f) {
      var uniq = []
      ;(f.cast || []).forEach(function (c) { if (c && uniq.indexOf(c) < 0) uniq.push(c) })
      uniq.forEach(function (c) { actorFilms[c] = (actorFilms[c] || 0) + 1 })
      for (var i = 0; i < uniq.length; i++)
        for (var j = i + 1; j < uniq.length; j++) {
          var a = uniq[i], b = uniq[j]
          if (a > b) { var t = a; a = b; b = t }
          var k = a + " " + b
          pairs[k] = (pairs[k] || 0) + 1
        }
    })
    var keep = {}
    Object.keys(actorFilms).forEach(function (a) { if (actorFilms[a] >= MIN_FILMS) keep[a] = true })
    var edges = []
    Object.keys(pairs).forEach(function (k) {
      if (pairs[k] < MIN_PAIR) return
      var ab = k.split(" ")
      if (keep[ab[0]] && keep[ab[1]]) edges.push({ source: ab[0], target: ab[1], w: pairs[k] })
    })
    var deg = {}
    edges.forEach(function (e) { deg[e.source] = 1; deg[e.target] = 1 })
    var names = Object.keys(deg).sort(function (a, b) { return actorFilms[b] - actorFilms[a] })
    if (names.length > MAX_NODES) names = names.slice(0, MAX_NODES)
    var inSet = {}
    names.forEach(function (n) { inSet[n] = true })
    edges = edges.filter(function (e) { return inSet[e.source] && inSet[e.target] })
    var nodes = names.map(function (n) { return { id: n, films: actorFilms[n] } })
    if (!nodes.length) {
      mount.innerHTML = "<p>Not enough co-appearances yet — rate/log more films.</p>"
      return
    }
    ensureD3(function () { drawForce(mount, nodes, edges) })
  }

  function drawForce(mount, nodes, links) {
    var d3 = window.d3
    if (!d3) { mount.innerHTML = "<p>Could not load the graph library.</p>"; return }
    var W = mount.clientWidth || 700, H = 580
    mount.innerHTML = ""
    var svg = d3.select(mount).append("svg")
      .attr("width", "100%").attr("height", H).attr("viewBox", "0 0 " + W + " " + H)
    var g = svg.append("g")
    svg.call(d3.zoom().scaleExtent([0.3, 4]).on("zoom", function (ev) { g.attr("transform", ev.transform) }))
    var link = g.append("g").attr("stroke", "var(--lightgray)").attr("stroke-opacity", 0.7)
      .selectAll("line").data(links).join("line")
      .attr("stroke-width", function (d) { return Math.min(1 + d.w * 0.4, 4) })
    var node = g.append("g").selectAll("g").data(nodes).join("g").style("cursor", "pointer")
      .on("click", function (_, d) { window.location.href = withBase("/people/" + slugify(d.id)) })
    node.append("circle").attr("r", function (d) { return 4 + Math.sqrt(d.films) * 2 })
      .attr("fill", "var(--tertiary)").attr("stroke", "var(--light)").attr("stroke-width", 1.2)
    node.append("title").text(function (d) { return d.id + " — " + d.films + " films" })
    var label = g.append("g").selectAll("text").data(nodes).join("text")
      .text(function (d) { return d.id }).attr("font-size", 10).attr("fill", "var(--darkgray)")
      .attr("dx", 9).attr("dy", 3).style("pointer-events", "none")
    var sim = d3.forceSimulation(nodes)
      .force("link", d3.forceLink(links).id(function (d) { return d.id }).distance(65).strength(0.35))
      .force("charge", d3.forceManyBody().strength(-140))
      .force("center", d3.forceCenter(W / 2, H / 2))
      .force("collide", d3.forceCollide(20))
      .on("tick", function () {
        link.attr("x1", function (d) { return d.source.x }).attr("y1", function (d) { return d.source.y })
          .attr("x2", function (d) { return d.target.x }).attr("y2", function (d) { return d.target.y })
        node.attr("transform", function (d) { return "translate(" + d.x + "," + d.y + ")" })
        label.attr("x", function (d) { return d.x }).attr("y", function (d) { return d.y })
      })
    node.call(d3.drag()
      .on("start", function (ev, d) { if (!ev.active) sim.alphaTarget(0.3).restart(); d.fx = d.x; d.fy = d.y })
      .on("drag", function (ev, d) { d.fx = ev.x; d.fy = ev.y })
      .on("end", function (ev, d) { if (!ev.active) sim.alphaTarget(0); d.fx = null; d.fy = null }))
  }

  // --- world map (choropleth of your cinema by country) ----------------------
  // Match TMDB country names to the world-atlas feature names; a few differ.
  var COUNTRY_ALIAS = {
    "czechia": "czech republic", "united states": "united states of america",
    "bosnia and herz.": "bosnia and herzegovina", "dominican rep.": "dominican republic",
    "s. sudan": "south sudan", "eq. guinea": "equatorial guinea",
    "central african rep.": "central african republic",
    "dem. rep. congo": "democratic republic of the congo", "korea": "south korea",
    "w. sahara": "western sahara", "côte d'ivoire": "ivory coast",
  }
  function normCountry(s) {
    s = String(s || "").toLowerCase().trim()
    return COUNTRY_ALIAS[s] || s
  }

  function renderChoropleth(mount, list) {
    var data = {}
    list.forEach(function (f) {
      if (!f.country) return
      var k = normCountry(f.country)
      if (!data[k]) data[k] = { count: 0, sum: 0, rated: 0, name: f.country }
      data[k].count += 1
      if (f.rating != null) { data[k].sum += f.rating; data[k].rated += 1 }
    })
    ensureD3(function () {
      ensureTopojson(function () {
        var d3 = window.d3, topojson = window.topojson
        fetch("https://cdn.jsdelivr.net/npm/world-atlas@2/countries-110m.json")
          .then(function (r) { return r.json() })
          .then(function (topo) {
            var geo = topojson.feature(topo, topo.objects.countries)
            var W = mount.clientWidth || 700, H = Math.round(W * 0.52)
            mount.innerHTML = ""
            var svg = d3.select(mount).append("svg")
              .attr("viewBox", "0 0 " + W + " " + H).attr("width", "100%").attr("height", H)
            var proj = d3.geoNaturalEarth1().fitSize([W, H], geo)
            var path = d3.geoPath(proj)
            var maxc = 0
            Object.keys(data).forEach(function (k) { if (data[k].count > maxc) maxc = data[k].count })
            var color = d3.scaleSequential(d3.interpolateYlGnBu).domain([0, Math.sqrt(maxc || 1)])
            svg.append("g").selectAll("path").data(geo.features).join("path")
              .attr("d", path)
              .attr("fill", function (d) {
                var e = data[normCountry(d.properties.name)]
                return e ? color(Math.sqrt(e.count)) : "var(--lightgray)"
              })
              .attr("stroke", "var(--light)").attr("stroke-width", 0.4)
              .append("title").text(function (d) {
                var e = data[normCountry(d.properties.name)]
                if (!e) return d.properties.name
                var avg = e.rated ? ", avg ★" + (Math.round((e.sum / e.rated) * 100) / 100) : ""
                return d.properties.name + " — " + e.count + " films" + avg
              })
          })
          .catch(function () { mount.innerHTML = "<p>Couldn't load the world map data.</p>" })
      })
    })
  }

  // --- film page: related films ----------------------------------------------
  // The hero (poster/meta/streaming/chips) is server-rendered from frontmatter; the
  // "Related films" section is computed here from films.json by taste similarity and
  // appended to the end of the article so it reads below the overview.
  async function renderFilmPage() {
    var el = document.querySelector("[data-cinegraph-film]")
    if (!el || el.dataset.done) return
    el.dataset.done = "1"
    // The hero chips (Director/Cast/Studios/Genres/Themes) are server-rendered with
    // root-absolute hrefs; prefix them with the deploy base before adding anything else.
    if (BASE) {
      var chips = document.querySelectorAll(".film-hero a[href^='/']")
      for (var ci = 0; ci < chips.length; ci++) {
        chips[ci].setAttribute("href", BASE + chips[ci].getAttribute("href"))
      }
    }
    var cur
    try { cur = JSON.parse(el.textContent || "{}") } catch (e) { return }
    var list
    try {
      list = await films()
      await detailPayload() // the "Related films" fast path reads f.related
    } catch (e) { return }
    var byId = {}
    list.forEach(function (f) { if (f.tmdb_id != null) byId[f.tmdb_id] = f })

    var top
    var self = cur.tmdb_id != null ? byId[cur.tmdb_id] : null

    // Theme chips (keywords that have a Theme page) appended to the hero, near genres.
    if (self && self.themes && self.themes.length) {
      var info = document.querySelector(".film-info")
      if (info && !info.querySelector(".film-themes")) {
        var row = document.createElement("div")
        row.className = "film-row film-themes"
        row.innerHTML = '<span class="film-row-label">Themes</span><span class="film-chips">' +
          self.themes.slice(0, 12).map(function (t) {
            return '<a class="film-chip" href="' + withBase("/themes/" + slugify(t)) + '">' + esc(t) + "</a>"
          }).join("") + "</span>"
        info.appendChild(row)
      }
    }
    if (self && self.related && self.related.length) {
      // Fast path: use the precomputed similarity edges (same ones the constellation uses).
      top = self.related.map(function (r) { return byId[r[0]] }).filter(Boolean).slice(0, 12)
    } else {
      // Fallback (e.g. a watchlist film, not in films.json): score on the fly.
      var inCast = {}, inKw = {}, inGen = {}
      ;(cur.cast || []).forEach(function (c) { inCast[c] = 1 })
      ;(cur.keywords || []).forEach(function (k) { inKw[k] = 1 })
      ;(cur.genres || []).forEach(function (g) { inGen[g] = 1 })
      var scored = []
      list.forEach(function (f) {
        if (cur.tmdb_id && f.tmdb_id === cur.tmdb_id) return
        var s = 0
        if (cur.director && f.director === cur.director) s += 5
        ;(f.cast || []).forEach(function (c) { if (inCast[c]) s += 2 })
        ;(f.keywords || []).forEach(function (k) { if (inKw[k]) s += 1.2 })
        ;(f.genres || []).forEach(function (g) { if (inGen[g]) s += 0.6 })
        if (s > 0) scored.push({ f: f, s: s })
      })
      scored.sort(function (a, b) { return b.s - a.s || (b.f.rating || 0) - (a.f.rating || 0) })
      top = scored.slice(0, 12).map(function (x) { return x.f })
    }
    if (!top.length) return

    var sec = document.createElement("section")
    sec.className = "film-related"
    sec.innerHTML = "<h2>Related films</h2><div class='poster-grid'></div>"
    sec.querySelector(".poster-grid").innerHTML = top.map(card).join("")
    var host = document.querySelector("article") || document.querySelector(".center") || el.parentNode
    if (host) host.appendChild(sec)
  }

  // --- film constellation: taste islands, bridges, orphans -------------------
  // Fixed 20-colour palette so the graph nodes and the panel swatches always agree.
  var ISLAND_PALETTE = [
    "#4e79a7", "#f28e2c", "#e15759", "#76b7b2", "#59a14f", "#edc949", "#af7aa1", "#ff9da7",
    "#9c755f", "#bab0ab", "#86bcb6", "#d37295", "#a0cbe8", "#8cd17d", "#b6992d", "#499894",
    "#fabfd2", "#d4a6c8", "#b07aa1", "#79706e",
  ]
  function islandColor(id) {
    return id == null ? "var(--gray)" : ISLAND_PALETTE[id % ISLAND_PALETTE.length]
  }

  async function renderConstellation(mount) {
    if (mount.dataset.rendered) return
    mount.dataset.rendered = "1"
    var payload, detail
    try {
      payload = await filmsPayload()
      detail = await detailPayload() // edges (f.related) + island/bridge/orphan markers
    } catch (e) { mount.innerHTML = "<p>Could not load films.json</p>"; return }
    var list = payload.films || [], islands = detail.islands || []
    var EDGE_MIN = 4, MAX_NODES = 220
    var byId = {}
    list.forEach(function (f) { if (f.tmdb_id != null) byId[f.tmdb_id] = f })
    var edgeW = {}
    list.forEach(function (f) {
      if (f.tmdb_id == null) return
      ;(f.related || []).forEach(function (r) {
        if (r[1] < EDGE_MIN || byId[r[0]] == null) return
        var a = f.tmdb_id, b = r[0]
        if (a > b) { var t = a; a = b; b = t }
        var k = a + "|" + b
        if (!edgeW[k] || edgeW[k] < r[1]) edgeW[k] = r[1]
      })
    })
    var edges = Object.keys(edgeW).map(function (k) {
      var p = k.split("|"); return { source: +p[0], target: +p[1], w: edgeW[k] }
    })
    var deg = {}
    edges.forEach(function (e) { deg[e.source] = (deg[e.source] || 0) + 1; deg[e.target] = (deg[e.target] || 0) + 1 })
    var ids = Object.keys(deg).map(Number).sort(function (a, b) {
      return (byId[b].rating || 0) - (byId[a].rating || 0) || deg[b] - deg[a]
    })
    if (ids.length > MAX_NODES) ids = ids.slice(0, MAX_NODES)
    var keep = {}
    ids.forEach(function (id) { keep[id] = 1 })
    edges = edges.filter(function (e) { return keep[e.source] && keep[e.target] })
    var used = {}
    edges.forEach(function (e) { used[e.source] = 1; used[e.target] = 1 })
    var nodes = Object.keys(used).map(function (id) {
      var f = byId[id]
      return { id: +id, title: f.title, url: f.url, rating: f.rating, community: f.community, bridge: f.bridge || 0 }
    })

    // Home shows just the graph; the Taste Map page adds the island/bridge/orphan panel.
    var withPanel = mount.dataset.panel === "1"
    mount.innerHTML = "<div class='constellation-graph'></div>" + (withPanel ? "<div class='taste-map'></div>" : "")
    if (withPanel) renderTasteMap(mount.querySelector(".taste-map"), islands, list)
    var graphEl = mount.querySelector(".constellation-graph")
    if (!nodes.length) { graphEl.innerHTML = "<p>Not enough connections yet.</p>"; return }
    ensureD3(function () { drawFilmForce(graphEl, nodes, edges, islands) })
  }

  function renderTasteMap(el, islands, list) {
    if (!el) return
    var bridges = list.filter(function (f) { return f.bridge }).sort(function (a, b) { return b.bridge - a.bridge }).slice(0, 8)
    var orphans = list.filter(function (f) { return f.orphan })
    function chip(f) { return '<a class="film-chip" href="' + esc(f.url) + '">' + esc(f.title) + "</a>" }
    var islandsHtml = islands.slice(0, 30).map(function (i) {
      var ex = (i.examples || []).map(function (e) { return '<a href="' + esc(e.url) + '">' + esc(e.title) + "</a>" }).join(", ")
      return '<div class="island-row"><span class="island-dot" style="background:' + islandColor(i.id) + '"></span>' +
        '<div class="island-body"><div class="island-name">' + esc(i.name) +
        ' <span class="person-count">' + i.size + "</span></div>" +
        '<div class="island-ex">' + ex + "</div></div></div>"
    }).join("")
    el.innerHTML =
      '<h2 class="upnext-h">Your taste islands <span class="person-count">' + islands.length + "</span></h2>" +
      '<p class="tm-note">Communities the constellation falls into, each named by the tags its films share most. Click a title to open it.</p>' +
      '<div class="island-list">' + islandsHtml + "</div>" +
      (bridges.length ? '<h2 class="upnext-h">Bridge films</h2><p class="tm-note">The connectors — films that link your separate taste-worlds.</p><div class="film-chips">' + bridges.map(chip).join("") + "</div>" : "") +
      (orphans.length ? '<h2 class="upnext-h">Orphans <span class="person-count">' + orphans.length + '</span></h2><p class="tm-note">Outliers connected to nothing else you\'ve seen — your experiments.</p><div class="film-chips">' + orphans.slice(0, 24).map(chip).join("") + "</div>" : "")
  }

  function drawFilmForce(mount, nodes, links, islands) {
    var d3 = window.d3
    if (!d3) { mount.innerHTML = "<p>Could not load the graph library.</p>"; return }
    var W = mount.clientWidth || 700, H = 620
    mount.innerHTML = ""
    var svg = d3.select(mount).append("svg").attr("width", "100%").attr("height", H).attr("viewBox", "0 0 " + W + " " + H)
    var g = svg.append("g")
    svg.call(d3.zoom().scaleExtent([0.2, 5]).on("zoom", function (ev) { g.attr("transform", ev.transform) }))
    var link = g.append("g").attr("stroke", "var(--lightgray)").attr("stroke-opacity", 0.55)
      .selectAll("line").data(links).join("line").attr("stroke-width", function (d) { return Math.min(0.5 + d.w * 0.12, 3) })
    var node = g.append("g").selectAll("circle").data(nodes).join("circle")
      .attr("r", function (d) { return 3 + (d.rating || 2.5) * 1.3 + (d.bridge > 0.02 ? 2 : 0) })
      .attr("fill", function (d) { return islandColor(d.community) })
      .attr("stroke", function (d) { return d.bridge > 0.02 ? "var(--dark)" : "var(--light)" })
      .attr("stroke-width", function (d) { return d.bridge > 0.02 ? 1.6 : 0.8 })
      .style("cursor", "pointer").on("click", function (_, d) { window.location.href = d.url })
    node.append("title").text(function (d) { return d.title + (d.rating ? " — ★" + d.rating : "") + (d.bridge > 0.02 ? "  · bridge film" : "") })

    // Island labels: the island's lead tag, floated at the centroid of its visible nodes.
    var nameById = {}
    islands.forEach(function (i) { nameById[i.id] = (i.name || "").split(" · ")[0] })
    var present = {}
    nodes.forEach(function (n) { if (n.community != null) (present[n.community] = present[n.community] || []).push(n) })
    var big = Object.keys(present).filter(function (c) { return present[c].length >= 4 })
      .sort(function (a, b) { return present[b].length - present[a].length }).slice(0, 10)
    var labels = g.append("g").selectAll("text").data(big).join("text")
      .text(function (c) { return nameById[c] || "" })
      .attr("font-size", 12).attr("font-weight", 700).attr("text-anchor", "middle")
      .attr("fill", function (c) { return islandColor(+c) }).attr("opacity", 0.92)
      .attr("stroke", "var(--light)").attr("stroke-width", 3).attr("paint-order", "stroke")
      .style("pointer-events", "none")

    var sim = d3.forceSimulation(nodes)
      .force("link", d3.forceLink(links).id(function (d) { return d.id }).distance(42).strength(0.28))
      .force("charge", d3.forceManyBody().strength(-70))
      .force("center", d3.forceCenter(W / 2, H / 2))
      .force("collide", d3.forceCollide(9))
      .on("tick", function () {
        link.attr("x1", function (d) { return d.source.x }).attr("y1", function (d) { return d.source.y })
          .attr("x2", function (d) { return d.target.x }).attr("y2", function (d) { return d.target.y })
        node.attr("cx", function (d) { return d.x }).attr("cy", function (d) { return d.y })
        labels.attr("x", function (c) { return d3.mean(present[c], function (n) { return n.x }) })
          .attr("y", function (c) { return d3.mean(present[c], function (n) { return n.y }) })
      })
    node.call(d3.drag()
      .on("start", function (ev, d) { if (!ev.active) sim.alphaTarget(0.3).restart(); d.fx = d.x; d.fy = d.y })
      .on("drag", function (ev, d) { d.fx = ev.x; d.fy = ev.y })
      .on("end", function (ev, d) { if (!ev.active) sim.alphaTarget(0); d.fx = null; d.fy = null }))
  }

  // --- person page: directed vs acted, related actors/directors --------------
  var ACTOR_INDEX = null // actor name -> [films], built once
  function actorIndex(list) {
    if (ACTOR_INDEX) return ACTOR_INDEX
    ACTOR_INDEX = {}
    list.forEach(function (f) {
      ;(f.cast || []).forEach(function (a) { (ACTOR_INDEX[a] || (ACTOR_INDEX[a] = [])).push(f) })
    })
    return ACTOR_INDEX
  }

  async function renderPerson(mount) {
    if (mount.dataset.done) return
    mount.dataset.done = "1"
    var name = mount.dataset.name
    if (!name) return
    var list
    try { list = await films() } catch (e) { return }

    var directed = [], acted = []
    list.forEach(function (f) {
      if (f.director === name) directed.push(f)
      if ((f.cast || []).indexOf(name) >= 0) acted.push(f)
    })
    var seen = {}, myFilms = []
    directed.concat(acted).forEach(function (f) {
      if (f.tmdb_id != null) { if (seen[f.tmdb_id]) return; seen[f.tmdb_id] = 1 }
      myFilms.push(f)
    })

    // Related actors: people who share these films (co-stars / a director's regulars).
    var actorC = {}
    myFilms.forEach(function (f) {
      ;(f.cast || []).forEach(function (a) { if (a !== name) actorC[a] = (actorC[a] || 0) + 1 })
    })
    var relActors = Object.keys(actorC).map(function (a) { return { name: a, n: actorC[a] } })
      .sort(function (x, y) { return y.n - x.n }).slice(0, 12)

    // Related directors: first the directors you've actually worked with (by films
    // together). If that's thin (e.g. a pure director), top up with *peer* directors who
    // cast the same actors — never blended, so real collaborators are never outranked.
    var directC = {}
    myFilms.forEach(function (f) { if (f.director && f.director !== name) directC[f.director] = (directC[f.director] || 0) + 1 })
    var relDirs = Object.keys(directC).map(function (d) { return { name: d, n: directC[d] } })
      .sort(function (x, y) { return y.n - x.n })
    if (relDirs.length < 6) {
      var idx = actorIndex(list)
      var have = { }; have[name] = 1
      relDirs.forEach(function (d) { have[d.name] = 1 })
      var myActors = {}
      myFilms.forEach(function (f) { (f.cast || []).forEach(function (a) { myActors[a] = 1 }) })
      var peerC = {}
      Object.keys(myActors).forEach(function (a) {
        ;(idx[a] || []).forEach(function (g) { if (g.director && !have[g.director]) peerC[g.director] = (peerC[g.director] || 0) + 1 })
      })
      relDirs = relDirs.concat(Object.keys(peerC).map(function (d) { return { name: d, n: peerC[d] } })
        .sort(function (x, y) { return y.n - x.n }))
    }
    relDirs = relDirs.slice(0, 12)

    function gridSec(title, arr) {
      if (!arr.length) return ""
      return '<section class="person-sec"><h2>' + esc(title) +
        ' <span class="person-count">' + arr.length + "</span></h2>" +
        '<div class="poster-grid">' + sortFilms(arr, "rating").map(card).join("") + "</div></section>"
    }
    function chipSec(title, people, showCount) {
      if (!people.length) return ""
      return '<section class="person-sec"><h2>' + esc(title) + "</h2>" +
        '<div class="film-chips">' + people.map(function (p) {
          var count = showCount ? ' <span class="chip-count">' + p.n + "</span>" : ""
          return '<a class="film-chip" href="' + withBase("/people/" + slugify(p.name)) + '">' + esc(p.name) + count + "</a>"
        }).join("") + "</div></section>"
    }
    mount.innerHTML =
      gridSec("Directed", directed) + gridSec("Acted in", acted) +
      chipSec("Related actors", relActors, true) + chipSec("Related directors", relDirs, false) ||
      "<p>No films found.</p>"
  }

  // --- studio / genre / theme pages ------------------------------------------
  // theme uses the cleaned `themes` field (page-backed keywords) so its film filter and
  // "Related themes" chips never touch junk keywords or link to non-existent pages.
  var ENTITY_FIELD = { studio: "studios", genre: "genres", theme: "themes" }
  var ENTITY_FOLDER = { studio: "studios", genre: "genres", theme: "themes" }

  async function renderEntity(mount) {
    if (mount.dataset.done) return
    mount.dataset.done = "1"
    var kind = mount.dataset.kind, name = mount.dataset.name
    var field = ENTITY_FIELD[kind]
    if (!field || !name) return
    var list
    try { list = await films() } catch (e) { return }
    var mine = list.filter(function (f) { return (f[field] || []).indexOf(name) >= 0 })
    if (!mine.length) { mount.innerHTML = "<p>No films found.</p>"; return }

    function tallyField(getter) {
      var c = {}
      mine.forEach(function (f) { (getter(f) || []).forEach(function (v) { if (v && v !== name) c[v] = (c[v] || 0) + 1 }) })
      return Object.keys(c).map(function (v) { return { name: v, n: c[v] } }).sort(function (a, b) { return b.n - a.n })
    }
    var related = tallyField(function (f) { return f[field] }).slice(0, 12)
    var dirs = tallyField(function (f) { return f.director ? [f.director] : [] }).slice(0, 10)
    var actors = tallyField(function (f) { return f.cast }).slice(0, 12)

    function gridSec(title, arr) {
      return '<section class="person-sec"><h2>' + esc(title) + ' <span class="person-count">' + arr.length +
        "</span></h2><div class='poster-grid'>" + sortFilms(arr, "rating").map(card).join("") + "</div></section>"
    }
    function chipSec(title, people, folder) {
      if (!people.length) return ""
      return '<section class="person-sec"><h2>' + esc(title) + "</h2><div class='film-chips'>" +
        people.map(function (p) {
          return '<a class="film-chip" href="' + withBase("/" + folder + "/" + slugify(p.name)) + '">' +
            esc(p.name) + ' <span class="chip-count">' + p.n + "</span></a>"
        }).join("") + "</div></section>"
    }
    mount.innerHTML =
      gridSec("Films", mine) +
      chipSec("Related " + kind + "s", related, ENTITY_FOLDER[kind]) +
      chipSec("Top directors", dirs, "people") +
      chipSec("Top actors", actors, "people")
  }

  // --- discover gallery ------------------------------------------------------
  async function renderDiscover(mount) {
    if (mount.dataset.done) return
    mount.dataset.done = "1"
    var data
    try { data = await (await fetch(withBase("/static/discover.json"))).json() }
    catch (e) { mount.innerHTML = "<p>Could not load recommendations.</p>"; return }
    var recs = data.recs || []
    recs.forEach(function (r) { r.url = withBase(r.url) })
    var KEY = "cinegraph-dismissed"
    function getDismissed() { try { return JSON.parse(localStorage.getItem(KEY) || "[]") } catch (e) { return [] } }
    function setDismissed(a) { try { localStorage.setItem(KEY, JSON.stringify(a)) } catch (e) {} }

    function recCard(r) {
      var poster = r.poster
        ? '<img loading="lazy" src="' + esc(r.poster) + '" alt="' + esc(r.title) + '">'
        : '<div class="poster-fallback">' + esc(r.title) + "</div>"
      var provs = (r.providers || []).slice(0, 5).map(function (p) { return '<span class="film-provider">' + esc(p) + "</span>" }).join("")
      var genres = (r.genres || []).slice(0, 3).map(esc).join(" · ")
      var tmdb = r.tmdb_id != null
        ? '<a class="disc-link" href="https://www.themoviedb.org/movie/' + esc(r.tmdb_id) + '" target="_blank" rel="noopener">TMDB ↗</a>'
        : ""
      return '<div class="disc-card" data-id="' + esc(r.tmdb_id) + '">' +
        '<a class="disc-poster" href="' + esc(r.url) + '">' + poster + "</a>" +
        '<div class="disc-body">' +
        '<div class="disc-title"><a href="' + esc(r.url) + '">' + esc(r.title) + "</a>" +
        (r.year ? ' <span class="disc-year">(' + r.year + ")</span>" : "") + "</div>" +
        '<div class="disc-sub">' + (r.director ? "dir. " + esc(r.director) : "") + (genres ? " · " + genres : "") + "</div>" +
        (r.why ? '<div class="disc-why">' + esc(r.why) + "</div>" : "") +
        (provs
          ? '<div class="disc-stream"><span class="film-row-label">Watch</span>' + provs + "</div>"
          : '<div class="disc-stream disc-nostream">Not currently streaming</div>') +
        '<div class="disc-actions">' + tmdb + '<button class="disc-dismiss" type="button">Dismiss</button></div>' +
        "</div></div>"
    }

    function draw() {
      var dis = getDismissed()
      var visible = recs.filter(function (r) { return dis.indexOf(r.tmdb_id) < 0 })
      var hidden = recs.length - visible.length
      mount.innerHTML =
        '<div class="disc-toolbar"><span class="disc-status">' + visible.length + " recommendations</span>" +
        (hidden ? '<button class="disc-toggle" type="button">↺ Restore ' + hidden + " dismissed</button>" : "") +
        '</div><div class="disc-grid">' + visible.map(recCard).join("") + "</div>"
      var dismissBtns = mount.querySelectorAll(".disc-dismiss")
      for (var i = 0; i < dismissBtns.length; i++) {
        dismissBtns[i].addEventListener("click", function () {
          var id = Number(this.closest(".disc-card").dataset.id)
          var d = getDismissed()
          if (d.indexOf(id) < 0) d.push(id)
          setDismissed(d)
          draw()
        })
      }
      var toggle = mount.querySelector(".disc-toggle")
      if (toggle) toggle.addEventListener("click", function () { setDismissed([]); draw() })
    }
    draw()
  }

  // --- Up Next hub (watchlist ranked by taste + suggestions, shared filters) --
  async function renderUpNext(mount) {
    if (mount.dataset.done) return
    mount.dataset.done = "1"
    async function load(name, key) {
      try { return (await (await fetch(withBase("/static/" + name))).json())[key] || [] } catch (e) { return [] }
    }
    var wlData = {}
    try { wlData = await (await fetch(withBase("/static/watchlist.json"))).json() } catch (e) {}
    var wl = wlData.watchlist || []
    var acc = wlData.accuracy
    var dc = await load("discover.json", "recs")
    wl.forEach(function (r) { r.url = withBase(r.url) })
    dc.forEach(function (r) { r.url = withBase(r.url) })
    if (!wl.length && !dc.length) { mount.innerHTML = "<p>Nothing to show yet.</p>"; return }
    var KEY = "cinegraph-dismissed"
    function getDismissed() { try { return JSON.parse(localStorage.getItem(KEY) || "[]") } catch (e) { return [] } }
    function setDismissed(a) { try { localStorage.setItem(KEY, JSON.stringify(a)) } catch (e) {} }
    var filters = { stream: false, short: false }
    function pass(r) {
      if (filters.stream && !(r.providers && r.providers.length)) return false
      if (filters.short && r.runtime && r.runtime > 120) return false
      return true
    }

    function card(r, kind) {
      var poster = r.poster
        ? '<img loading="lazy" src="' + esc(r.poster) + '" alt="' + esc(r.title) + '">'
        : '<div class="poster-fallback">' + esc(r.title) + "</div>"
      var provs = (r.providers || []).slice(0, 4).map(function (p) { return '<span class="film-provider">' + esc(p) + "</span>" }).join("")
      var meta = []
      if (r.director) meta.push("dir. " + esc(r.director))
      var g = (r.genres || []).slice(0, 2).map(esc).join(" · ")
      if (g) meta.push(g)
      if (r.runtime) meta.push(r.runtime + "m")
      var badge = kind === "watchlist"
        ? (r.predicted != null ? '<span class="upnext-badge">★' + r.predicted + " likely</span>" : "")
        : (r.score != null ? '<span class="upnext-badge alt">match ' + r.score + "</span>" : "")
      var note = kind === "watchlist" ? r.reason : r.why
      var actions = kind === "suggested"
        ? '<div class="disc-actions">' +
          (r.tmdb_id != null ? '<a class="disc-link" href="https://www.themoviedb.org/movie/' + esc(r.tmdb_id) + '" target="_blank" rel="noopener">TMDB ↗</a>' : "") +
          '<button class="disc-dismiss" type="button">Dismiss</button></div>'
        : ""
      return '<div class="disc-card" data-id="' + esc(r.tmdb_id) + '">' +
        '<a class="disc-poster" href="' + esc(r.url) + '">' + poster + "</a>" +
        '<div class="disc-body">' +
        '<div class="disc-title"><a href="' + esc(r.url) + '">' + esc(r.title) + "</a>" +
        (r.year ? ' <span class="disc-year">(' + r.year + ")</span>" : "") + " " + badge + "</div>" +
        '<div class="disc-sub">' + meta.join(" · ") + "</div>" +
        (note ? '<div class="disc-why">' + esc(note) + "</div>" : "") +
        (provs
          ? '<div class="disc-stream"><span class="film-row-label">Watch</span>' + provs + "</div>"
          : '<div class="disc-stream disc-nostream">Not currently streaming</div>') +
        actions + "</div></div>"
    }

    function draw() {
      var dis = getDismissed()
      var wlv = wl.filter(pass).slice(0, 30)
      var dcv = dc.filter(function (r) { return pass(r) && dis.indexOf(r.tmdb_id) < 0 })
      mount.innerHTML =
        '<div class="disc-toolbar">' +
        '<label class="upnext-filter"><input type="checkbox" class="f-stream"' + (filters.stream ? " checked" : "") + "> Streamable now</label>" +
        '<label class="upnext-filter"><input type="checkbox" class="f-short"' + (filters.short ? " checked" : "") + "> Under 2h</label>" +
        (acc ? '<span class="upnext-acc" title="leave-one-out backtest on your ' + acc.n + ' rated films">predictions ≈ ±' + acc.mae + "★ · r " + acc.r + "</span>" : "") +
        "</div>" +
        '<h2 class="upnext-h">From your watchlist <span class="person-count">top ' + wlv.length + "</span></h2>" +
        "<div class='disc-grid'>" + wlv.map(function (r) { return card(r, "watchlist") }).join("") + "</div>" +
        '<h2 class="upnext-h">Suggested for you <span class="person-count">' + dcv.length + "</span></h2>" +
        "<div class='disc-grid'>" + dcv.map(function (r) { return card(r, "suggested") }).join("") + "</div>"
      var fs = mount.querySelector(".f-stream")
      if (fs) fs.addEventListener("change", function () { filters.stream = fs.checked; draw() })
      var fsh = mount.querySelector(".f-short")
      if (fsh) fsh.addEventListener("change", function () { filters.short = fsh.checked; draw() })
      var btns = mount.querySelectorAll(".disc-dismiss")
      for (var i = 0; i < btns.length; i++) {
        btns[i].addEventListener("click", function () {
          var id = Number(this.closest(".disc-card").dataset.id)
          var d = getDismissed(); if (d.indexOf(id) < 0) d.push(id); setDismissed(d); draw()
        })
      }
    }
    draw()
  }

  // --- dispatch --------------------------------------------------------------
  function render() {
    BASE = computeBase()
    var upnext = document.querySelector("[data-upnext]")
    if (upnext) renderUpNext(upnext)
    var discover = document.querySelector("[data-discover]")
    if (discover) renderDiscover(discover)
    var person = document.querySelector("[data-person]")
    if (person) renderPerson(person)
    var entity = document.querySelector("[data-entity]")
    if (entity) renderEntity(entity)
    var grid = document.querySelector("[data-poster-grid]")
    if (grid) renderGrid(grid)
    var stats = document.querySelector("[data-stats]")
    if (stats) renderStats(stats)
    var ensemble = document.querySelector("[data-ensemble]")
    if (ensemble) renderEnsemble(ensemble)
    var film = document.querySelector("[data-cinegraph-film]")
    if (film) renderFilmPage()
    var constellation = document.querySelector("[data-constellation]")
    if (constellation) renderConstellation(constellation)
  }

  document.addEventListener("nav", render)
  render()
}
