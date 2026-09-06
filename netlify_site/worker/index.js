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

const withBase = (res) =>
  new HTMLRewriter()
    .on("head", {
      element(head) {
        head.prepend(BASE_TAG, { html: true });
      },
    })
    .transform(res);

export default {
  async fetch(request, env) {
    const url = new URL(request.url);
    let path = url.pathname;
    if (path.length > 1 && path.endsWith("/")) path = path.slice(0, -1);

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
      return route.base ? withBase(res) : res;
    }

    // Everything else (favicons, un-aliased files, 404s) falls through to
    // static assets untouched.
    return env.ASSETS.fetch(request);
  },
};
