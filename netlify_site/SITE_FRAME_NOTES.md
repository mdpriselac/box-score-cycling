# Site frame notes

The public site frame (phase-1 slice of `CLOUDFLARE_DEPLOYMENT_PLAN.md`):
one machine-readable index over the campaign archives, a set of frame pages
rendered from it, and a minimal Cloudflare Worker that serves `netlify_site/`
as static assets behind the plan's clean URL scheme. The existing generated
pages (stage pages, GC trackers, stage diaries, `index.html`) are wrapped,
never modified.

Editorial framing: market probabilities are presented as the benchmark the
model is scored against — a measure of how much real information it captures
— never as betting guidance. Keep new frame copy in that register.

## URL scheme

| URL | Serves |
| --- | --- |
| `/` | `_frame/home.html` — recent predictions, live race, upcoming, retrospectives |
| `/races` | `_frame/races.html` — filterable race list (status/type), archive table |
| `/calendar` | 302 → the most relevant generated month |
| `/calendar/2026/08` | `_frame/calendar/2026-08.html` — month grid with status chips |
| `/race/<slug>/<year>` | `_frame/race/<slug>-<year>.html` — race hub (stage strip, views, stage log) |
| `/race/<slug>/<year>/stage-NN` | the existing flat stage page (e.g. `vuelta-stage07.html`) |
| `/race/<slug>/<year>/gc` | the existing GC tracker (`gc.html` / `vuelta-gc.html`) |
| `/race/<slug>/<year>/stages` | the existing stage-by-stage diary hub |
| `/race/<slug>/<year>/review` | extra pages (TdF `review.html`) |
| `/model` | the existing `index.html` architecture article |

Slugs: `tour-de-france`, `vuelta-a-espana` (see `CAMPAIGNS` in
`build/build_site_index.py`).

Legacy flat filenames (`stage07.html`, `vuelta-gc.html`, `stages.html`,
`review.html`, `index.html`, …) **301-redirect** to their clean URLs, so
every previously shared link keeps working.

When a flat page is served at a deeper clean path, the Worker injects
`<base href="/">` into `<head>` (HTMLRewriter) so the page's relative links
(`index.html`, etc.) still resolve against the site root. The files on disk
are untouched.

## Rebuilding

```bash
uv run python netlify_site/build/build_site_index.py   # -> netlify_site/site-index.json
uv run python netlify_site/build/build_site_frame.py   # -> netlify_site/_frame/…
```

Run both after building a new stage page or settling a stage (natural home:
the end of the `build_stage_page.py` flow, alongside `make_netlify.py`).
Everything the frame shows comes from `site-index.json`; neither script
parses campaign HTML.

- `build_site_index.py` scans `performance_eval/<campaign>/predictions/
  stage_NN/scenarios.json` (dates, labels, day keys, `void_stages`),
  `results/stage_NN/results.csv` (presence == settled), and the flat pages in
  `netlify_site/` (presence == published). The hand-maintained parts are the
  `CAMPAIGNS` registry (slug, prefix, race dates — mirror of
  `CAMPAIGN_BRANDING` in `build_stage_page.py`) and `ARCHIVE_CAMPAIGNS`
  (spring evaluation campaigns with no pages).
- `site-index.json` also carries the routing tables the Worker imports:
  `aliases` (flat → clean redirects) and `clean_routes` (clean URL → asset,
  `base: true` when `<base>` injection is needed).

Stage status vocabulary: `settled` (results archived) / `predicted` (pages
or prediction JSONs exist, no result yet) / `upcoming` / `cancelled`
(union of `void_stages` across the campaign's configs — e.g. Vuelta stage 3).

## Local preview

```bash
npx wrangler dev --config netlify_site/wrangler.jsonc --port 8787
```

(Also wired as the `site-frame` entry in `.claude/launch.json`.) No
Cloudflare account or login is needed for `wrangler dev`. Deploy later is
`npx wrangler deploy --config netlify_site/wrangler.jsonc` once the
account/domain decisions in the plan are made.

## Files

- `build/build_site_index.py` — generates `site-index.json`
- `build/build_site_frame.py` — renders `_frame/` pages from the index
- `worker/index.js` — router: aliases → 301, clean routes → assets (+`<base>`)
- `wrangler.jsonc` — Workers Static Assets config (`run_worker_first: true`,
  assets dir = this directory)
- `.assetsignore` — keeps `build/`, `worker/`, config and archives out of
  the deployed asset set
- `_frame/` — generated output; safe to delete and rebuild

## Deferred to later phases

- One-day race pages (`/race/milano-sanremo/2027`-style) — the index schema
  already allows `type: one_day`; the hub renderer will need a one-day
  variant when the first one publishes.
- `/retrospectives/<year>/<month>` monthly reviews.
- D1 replacing `site-index.json` as the index of record (plan phase 2).
- The archive campaigns' model-vs-market data is repo-only for now; their
  `/races` rows point at `performance_eval/` paths.
