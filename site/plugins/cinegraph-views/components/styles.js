export const cinegraphViewsCss = `
.poster-grid-wrapper { margin: 1rem 0; }
.poster-grid-toolbar { display: flex; align-items: center; gap: 1rem; margin-bottom: 0.75rem; flex-wrap: wrap; }
.poster-grid-status { color: var(--gray); font-size: 0.9rem; }
.poster-grid-sort { font-size: 0.85rem; color: var(--darkgray); display: inline-flex; align-items: center; gap: 0.3rem; }
.poster-grid-sort select { font: inherit; padding: 0.15rem 0.3rem; border-radius: 4px; border: 1px solid var(--lightgray); background: var(--light); color: var(--darkgray); }
.poster-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(110px, 1fr)); gap: 0.7rem; }
.poster-card { position: relative; display: block; aspect-ratio: 2 / 3; border-radius: 6px; overflow: hidden; background: var(--lightgray); text-decoration: none; box-shadow: 0 1px 3px rgba(0, 0, 0, 0.15); }
.poster-card img { width: 100%; height: 100%; object-fit: cover; display: block; }
.poster-fallback { display: flex; align-items: center; justify-content: center; height: 100%; padding: 0.4rem; font-size: 0.75rem; text-align: center; color: var(--darkgray); }
.poster-meta { position: absolute; left: 0; right: 0; bottom: 0; padding: 0.6rem 0.4rem 0.35rem; display: flex; flex-direction: column; gap: 0.1rem; font-size: 0.72rem; line-height: 1.2; color: #fff; background: linear-gradient(transparent, rgba(0, 0, 0, 0.88)); opacity: 0; transition: opacity 0.15s ease; }
.poster-card:hover .poster-meta { opacity: 1; }
.poster-title { font-weight: 600; overflow: hidden; text-overflow: ellipsis; display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; }
.poster-rating { color: #ffd24a; font-weight: 600; }

/* --- stats dashboard --- */
.stats-wrapper { margin: 1rem 0; }
.stat-cards { display: grid; grid-template-columns: repeat(auto-fit, minmax(90px, 1fr)); gap: 0.75rem; margin-bottom: 1.5rem; }
.stat-card { display: flex; flex-direction: column; align-items: center; padding: 0.9rem 0.5rem; border-radius: 8px; background: var(--lightgray); color: var(--darkgray); font-size: 0.8rem; }
.stat-card .stat-num { font-size: 1.6rem; font-weight: 700; color: var(--secondary); line-height: 1.1; }
.stat-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(300px, 1fr)); gap: 1.2rem 2rem; }
.stat-block h2 { font-size: 1rem; margin: 0 0 0.6rem; border: none; }
.stat-row { display: grid; grid-template-columns: 8.5rem 1fr 2.2rem; align-items: center; gap: 0.5rem; margin: 0.2rem 0; font-size: 0.82rem; }
.stat-label { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; color: var(--darkgray); }
.stat-label a { text-decoration: none; }
.stat-bar { background: var(--lightgray); border-radius: 4px; height: 0.7rem; overflow: hidden; }
.stat-fill { display: block; height: 100%; background: var(--tertiary); border-radius: 4px; }
.stat-value { text-align: right; color: var(--gray); font-variant-numeric: tabular-nums; }

/* --- actor collaboration network --- */
.ensemble-wrapper { margin: 1rem 0; }
.ensemble-wrapper svg { width: 100%; height: 580px; background: var(--light); border: 1px solid var(--lightgray); border-radius: 8px; }
.ensemble-wrapper text { font-family: var(--bodyFont, inherit); }
.constellation-wrapper { margin: 1rem 0; }
.constellation-wrapper svg { width: 100%; height: 620px; background: var(--light); border: 1px solid var(--lightgray); border-radius: 8px; }
.taste-map { margin-top: 1.6rem; }
.tm-note { color: var(--gray); font-size: 0.82rem; margin: 0.1rem 0 0.7rem; }
.island-list { display: grid; grid-template-columns: repeat(auto-fill, minmax(310px, 1fr)); gap: 0.6rem 1.4rem; margin-bottom: 1rem; }
.island-row { display: flex; gap: 0.5rem; align-items: baseline; min-width: 0; }
.island-dot { flex: 0 0 auto; width: 0.7rem; height: 0.7rem; border-radius: 50%; position: relative; top: 1px; }
.island-body { min-width: 0; }
.island-name { font-weight: 600; font-size: 0.9rem; }
.island-ex { font-size: 0.75rem; color: var(--gray); white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.island-ex a { color: var(--gray); text-decoration: none; }
.island-ex a:hover { text-decoration: underline; }

/* --- world map --- */
.stat-map { grid-column: 1 / -1; margin-top: 0.5rem; }
.cinemap { color: var(--gray); font-size: 0.9rem; }
.cinemap svg { width: 100%; height: auto; }
.cinemap path { transition: fill 0.1s ease; }
.cinemap path:hover { stroke: var(--dark); stroke-width: 0.8; }

/* --- film page hero --- */
.film-hero { display: flex; gap: 1.4rem; margin: 0.3rem 0 1.6rem; flex-wrap: wrap; }
.film-poster { flex: 0 0 auto; width: 190px; max-width: 42vw; }
.film-poster img { width: 100%; border-radius: 8px; box-shadow: 0 2px 12px rgba(0, 0, 0, 0.22); display: block; }
.film-info { flex: 1 1 260px; min-width: 240px; display: flex; flex-direction: column; gap: 0.6rem; }
.film-tagline { color: var(--gray); font-size: 0.95rem; }
.film-rating { color: #e0a200; font-weight: 700; white-space: nowrap; }
.film-row { display: flex; gap: 0.6rem; align-items: baseline; flex-wrap: wrap; }
.film-row-label { flex: 0 0 auto; min-width: 6rem; font-size: 0.7rem; text-transform: uppercase; letter-spacing: 0.05em; color: var(--gray); }
.film-chips { display: flex; flex-wrap: wrap; gap: 0.35rem; }
.film-watched { font-size: 0.85rem; color: var(--darkgray); font-variant-numeric: tabular-nums; }
.film-chip { font-size: 0.82rem; padding: 0.12rem 0.55rem; border-radius: 999px; background: var(--lightgray); color: var(--darkgray); text-decoration: none; }
.film-chip:hover { background: var(--tertiary); color: #fff; }
.film-provider { font-size: 0.8rem; padding: 0.12rem 0.55rem; border-radius: 6px; background: var(--secondary); color: #fff; font-weight: 500; }
.film-related { margin-top: 2rem; }
.film-related h2 { margin-bottom: 0.75rem; }

/* --- film "Log" callout: subtle neutral card, always open (no blue, no fold arrow) --- */
/* doubled [data-callout="log"] outranks Quartz's equal-specificity .callout[data-callout] blue default */
.callout[data-callout="log"][data-callout="log"] { --color: var(--gray); --border: var(--lightgray); --bg: var(--lightgray); margin: 0.5rem 0 1.3rem; padding: 0.35rem 0.9rem; border: none; border-left: 3px solid var(--gray); border-radius: 5px; }
.callout[data-callout="log"] .callout-title { padding: 0.2rem 0 0.05rem; }
.callout[data-callout="log"] .callout-icon { display: none; }
.callout[data-callout="log"] .callout-title-inner p { font-size: 0.68rem; font-weight: 600; text-transform: uppercase; letter-spacing: 0.06em; color: var(--gray); }
.callout[data-callout="log"] .callout-content { font-size: 0.9rem; color: var(--darkgray); }
.callout[data-callout="log"] .callout-content p { margin: 0.1rem 0 0.15rem; }

/* --- person page --- */
.person-wrapper { margin: 0.2rem 0 0.5rem; }
.person-meta { color: var(--gray); font-size: 0.92rem; margin-bottom: 1rem; }
.person-sec { margin: 1.5rem 0; }
.person-sec h2 { font-size: 1.05rem; margin: 0 0 0.7rem; }
.person-count { color: var(--gray); font-weight: 400; font-size: 0.85rem; }
.chip-count { color: var(--gray); font-size: 0.72rem; }

/* --- discover gallery --- */
.disc-wrapper { margin: 1rem 0; }
.disc-toolbar { display: flex; align-items: center; gap: 1rem; margin-bottom: 0.9rem; flex-wrap: wrap; }
.disc-status { color: var(--gray); font-size: 0.9rem; }
.disc-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(330px, 1fr)); gap: 1rem; }
.disc-card { display: flex; gap: 0.8rem; background: var(--lightgray); border-radius: 8px; overflow: hidden; }
.disc-poster { flex: 0 0 92px; }
.disc-poster img { width: 92px; height: 138px; object-fit: cover; display: block; }
.disc-poster .poster-fallback { width: 92px; height: 138px; }
.disc-body { padding: 0.6rem 0.7rem 0.6rem 0; display: flex; flex-direction: column; gap: 0.3rem; min-width: 0; flex: 1; }
.disc-title a { font-weight: 600; text-decoration: none; }
.disc-year { color: var(--gray); font-weight: 400; }
.disc-sub { font-size: 0.8rem; color: var(--darkgray); }
.disc-why { font-size: 0.77rem; color: var(--gray); line-height: 1.35; }
.disc-stream { display: flex; flex-wrap: wrap; align-items: center; gap: 0.3rem; margin-top: auto; padding-top: 0.3rem; }
.disc-nostream { color: var(--gray); font-size: 0.74rem; font-style: italic; }
.disc-actions { display: flex; gap: 0.7rem; align-items: center; margin-top: 0.15rem; }
.disc-link { font-size: 0.78rem; }
.disc-dismiss, .disc-toggle { font: inherit; font-size: 0.74rem; padding: 0.12rem 0.5rem; border: 1px solid var(--gray); border-radius: 5px; background: transparent; color: var(--darkgray); cursor: pointer; }
.disc-dismiss:hover, .disc-toggle:hover { background: var(--light); }

/* --- Up Next hub --- */
.upnext-filter { font-size: 0.85rem; color: var(--darkgray); display: inline-flex; align-items: center; gap: 0.35rem; cursor: pointer; }
.upnext-h { font-size: 1.1rem; margin: 1.6rem 0 0.8rem; }
.upnext-h:first-of-type { margin-top: 0.4rem; }
.upnext-badge { font-size: 0.68rem; font-weight: 600; padding: 0.05rem 0.4rem; border-radius: 999px; background: var(--tertiary); color: #fff; white-space: nowrap; vertical-align: middle; }
.upnext-badge.alt { background: var(--secondary); }
.upnext-acc { margin-left: auto; color: var(--gray); font-size: 0.8rem; font-variant-numeric: tabular-nums; cursor: help; }
`
