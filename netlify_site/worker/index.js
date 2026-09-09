/**
 * Cloudflare Worker router for the cycling-prediction site (phase 1 of
 * CLOUDFLARE_DEPLOYMENT_PLAN.md).
 *
 * Serves netlify_site/ as static assets behind the clean URL scheme:
 *   /                            -> _frame/home.html
 *   /races                       -> _frame/races.html
 *   /calendar[/YYYY/MM]          -> _frame/calendar/YYYY-MM.html
 *   /race/:slug/:year[/:page]    -> frame hub or the existing flat page
 *   /model                       -> index.html (the architecture article)
 *   /ops, /_frame/ops.html       -> 404 (operator inbox, never public)
 * Legacy flat filenames (stage07.html, vuelta-gc.html, ...) 301-redirect to
 * their clean URLs, so old links keep working.
 *
 * All routing data comes from site-index.json (bundled at build time —
 * `wrangler dev` picks up changes on re-save). Flat pages served at deeper
 * clean paths get a <base href="/"> injected so their relative links still
 * resolve against the site root; the pages themselves are never modified.
 */

import siteIndex from "../site-index.json";

const BASE_TAG = '<base href="/">';
const NAV_STYLE = `<style>
  .site-nav-shell{max-width:1020px;margin:0 auto;padding:18px 24px 0}
  .site-topnav{font-family:"Avenir Next","Avenir","Segoe UI",-apple-system,BlinkMacSystemFont,"Helvetica Neue",sans-serif;
    font-size:13px;display:flex;flex-wrap:wrap;align-items:center;gap:10px 22px;padding-bottom:12px;
    border-bottom:1px solid #E5E3DB}
  .site-topnav a{color:#3E6B8F;text-decoration:none;border-bottom:1px solid transparent}
  .site-topnav a:hover{border-bottom-color:#E7EEF4}
  .site-topnav .brand{font-weight:700;font-size:14px;letter-spacing:-.01em;color:#22272F;margin-right:auto}
  .site-topnav .brand::before{content:"";display:inline-block;width:18px;height:7px;background:#F5C518;margin-right:9px}
  .site-topnav a.here{color:#22272F;font-weight:600;border-bottom:2px solid #F5C518}
  @media(max-width:600px){.site-nav-shell{padding-top:12px}.site-topnav{gap:8px 14px}.site-topnav .brand{width:100%;margin-bottom:2px}}
</style>`;

// Never served, under any URL that could reach it.
const OPS_PATHS = new Set(["/ops", "/ops.html", "/_frame/ops", "/_frame/ops.html"]);

const withSiteNav = (res, { base = false, active = "races" } = {}) => {
  const here = (name) => name === active ? ' class="here"' : "";
  const nav = `<div class="site-nav-shell"><nav class="site-topnav" aria-label="Site navigation">
    <a class="brand" href="/">Cycling Race Predictor</a>
    <a href="/races"${here("races")}>Races</a>
    <a href="/calendar"${here("calendar")}>Calendar</a>
    <a href="/model"${here("model")}>How the model works</a>
  </nav></div>`;
  return new HTMLRewriter()
    .on("head", {
      element(head) {
        head.prepend(`${base ? BASE_TAG : ""}${NAV_STYLE}`, { html: true });
      },
    })
    .on("body", {
      element(body) {
        body.prepend(nav, { html: true });
      },
    })
    .transform(res);
};

export default {
  async fetch(request, env) {
    const url = new URL(request.url);
    let path = url.pathname;
    if (path.length > 1 && path.endsWith("/")) path = path.slice(0, -1);

    // The operator inbox (_frame/ops.html) is a local page against the Supabase
    // control plane and is not public. .assetsignore already keeps it out of the
    // deployed asset set; this is the second lock, so a stray copy still 404s.
    if (OPS_PATHS.has(path.toLowerCase())) {
      return new Response("Not found", { status: 404 });
    }

    // Legacy flat filename -> clean URL.
    const alias = siteIndex.aliases[path];
    if (alias) {
      return Response.redirect(new URL(alias, url.origin), 301);
    }

    // Calendar root -> the most relevant generated month.
    if (path === "/calendar" && siteIndex.default_month) {
      const m = siteIndex.default_month.replace("-", "/");
      return Response.redirect(new URL(`/calendar/${m}`, url.origin), 302);
    }

    // Clean URL -> asset (frame page, or a wrapped legacy page).
    const route = siteIndex.clean_routes[path];
    if (route) {
      const res = await env.ASSETS.fetch(new URL(route.asset, url.origin));
      return route.chrome ? withSiteNav(res, { base: route.base, active: route.active }) : res;
    }

    // Everything else (favicons, un-aliased files, 404s) falls through to
    // static assets untouched.
    return env.ASSETS.fetch(request);
  },
};
