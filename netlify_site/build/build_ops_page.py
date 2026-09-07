"""
Render the operator inbox (`netlify_site/_frame/ops.html`) — the human end of
the nightly control plane (NIGHTLY_AGENT_WORKFLOW.md §2.7).

    uv run python netlify_site/build/build_ops_page.py            # hosted project
    uv run python netlify_site/build/build_ops_page.py --local    # `supabase start` stack

The page is a single static file that talks to Supabase from the browser with
the **publishable** key and an operator identity (Supabase Auth, or a role JWT
minted by ``supabase/mint_keys.py operator``). Row-level security does all the
enforcement — 0002_roles.sql grants the operator the reads and the four writes
this page performs, and nothing else. No secret ever reaches the page.

It is deliberately **not part of the public site**: the output is gitignored,
listed in ``netlify_site/.assetsignore`` so it is never uploaded, and the
Worker 404s ``/ops`` and ``/_frame/ops.html`` even if a copy slipped into the
asset set. Serve it locally instead:

    uv run python -m http.server 8411 --directory netlify_site
    open http://localhost:8411/_frame/ops.html

What it shows (all from the tables in supabase/migrations/0001_control_plane.sql):

* **Waiting on you** — open ``operator_tasks``; agent ``day_key_decisions``
  with no approved key for their unit, beside a form for the human key;
  ``crosswalk_proposals`` still ``proposed``; finished runs with no
  ``approvals`` row. The total is the page title and a header badge, so the
  browser tab is the notification (there is no webhook by design — see
  supabase/README.md §6).
* **Last 14 nights** — ``run_status`` with per-step chips and durations, the
  Managed Agents Console session link, and the log object's Storage path.

Design follows the public frame (build_site_frame.py): paper, Charter serif,
yellow eyebrow, status chips. Market probabilities are a benchmark, never
betting guidance — that register applies here too.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
SITE_DIR = HERE.parent
PROJECT_ROOT = SITE_DIR.parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from build_site_frame import CSS, FAVICON  # noqa: E402

from cycling_project.nightly import keys  # noqa: E402
from cycling_project.nightly.day_key_record import (  # noqa: E402
    DISCOURAGED_ITEMS, FAMILY_OF, FORBIDDEN_ITEMS, MENU_ITEMS, WEIGHT_TOLERANCE,
)

OUT_PATH = SITE_DIR / "_frame" / "ops.html"

# The Managed Agents workspace that owns the nightly deployment (chip I,
# re-provisioned 2026-09-07). Session ids in runs.session_id are only
# resolvable inside it.
WORKSPACE_ID = "wrkspc_01EXAMPLEB3AA2FEB16D1B0B"
CONSOLE_BASE = f"https://platform.claude.com/workspaces/{WORKSPACE_ID}/sessions/"
SUPABASE_JS = "https://cdn.jsdelivr.net/npm/@supabase/supabase-js@2.58.0/+esm"

# Publishable keys are public by design (they only reach the API gateway; the
# JWT decides the role). A secret key here would be a mistake, so refuse one.
SECRET_KEY_PREFIXES = ("sb_secret_", "service_role")


def local_stack_env() -> dict:
    """The local `supabase start` stack's URL + keys, or {} when it is not up."""
    return keys.local_stack_env(PROJECT_ROOT)


OPS_CSS = """
  .badge{display:inline-flex;align-items:center;gap:7px;font-family:var(--sans);
    font-size:13px;font-weight:700;padding:3px 12px;border-radius:99px;
    background:var(--yellow-soft);color:#7a6410;border:1px solid #eedf9e}
  .badge.clear{background:var(--green-soft);color:var(--green);border-color:#cfe0d6}
  .signin{background:var(--card);border:1px solid var(--line);border-radius:8px;
    padding:20px 22px;max-width:520px;margin:26px 0}
  .signin h2{font-size:19px;margin:0 0 6px}
  .signin p{font-size:14px;font-family:var(--sans);color:var(--slate);margin:0 0 14px}
  label{display:block;font-family:var(--sans);font-size:12px;font-weight:600;
    letter-spacing:.06em;text-transform:uppercase;color:var(--slate);margin:12px 0 4px}
  input,select,textarea{font-family:var(--sans);font-size:14px;padding:7px 9px;
    border:1px solid var(--line);border-radius:6px;background:var(--paper);
    color:var(--ink);width:100%;max-width:420px}
  textarea{min-height:56px;resize:vertical;max-width:100%}
  input[type=number]{max-width:110px}
  select{max-width:200px}
  button{font-family:var(--sans);font-size:13px;font-weight:600;cursor:pointer;
    padding:6px 14px;border-radius:6px;border:1px solid var(--ink);
    background:var(--ink);color:var(--paper)}
  button.ghost{background:var(--card);color:var(--ink);border-color:var(--line)}
  button.ghost:hover{border-color:var(--blue);color:var(--blue)}
  button:disabled{opacity:.45;cursor:not-allowed}
  .btnrow{display:flex;flex-wrap:wrap;gap:8px;align-items:center;margin-top:12px}
  .item{background:var(--card);border:1px solid var(--line);border-radius:8px;
    padding:15px 18px;margin:12px 0}
  .item.urgent{border-left:4px solid var(--red)}
  .item.blocks{border-left:4px solid var(--yellow)}
  .item h3{margin:0 0 3px;font-size:16px}
  .item .sub{font-family:var(--sans);font-size:12.5px;color:var(--slate);
    display:flex;flex-wrap:wrap;gap:4px 14px;margin-bottom:8px}
  .item .sub b{color:var(--ink);font-weight:600}
  details{font-family:var(--sans);font-size:13px;margin-top:8px}
  summary{cursor:pointer;color:var(--blue);font-weight:600}
  pre{font-family:var(--mono);font-size:11.5px;line-height:1.5;background:var(--paper);
    border:1px solid var(--line);border-radius:6px;padding:10px;overflow-x:auto;
    max-height:280px;margin:8px 0 0}
  .keyform{display:flex;flex-wrap:wrap;gap:8px;align-items:flex-end;margin-top:10px}
  .keyform .pair{display:flex;gap:6px;align-items:center}
  .sum{font-family:var(--mono);font-size:12.5px;color:var(--slate)}
  .sum.bad{color:var(--red);font-weight:700}
  .agentkey{background:var(--blue-soft);border-radius:6px;padding:9px 12px;
    font-family:var(--sans);font-size:13px;margin:8px 0}
  .agentkey .k{font-family:var(--mono);font-size:12.5px;color:var(--ink)}
  .flagged{color:var(--red);font-weight:700}
  .empty{font-family:var(--sans);font-size:14px;color:var(--slate);
    padding:12px 0;border-top:1px solid var(--line)}
  .steps{display:flex;flex-wrap:wrap;gap:4px;margin-top:4px}
  .step{font-family:var(--mono);font-size:11px;padding:1px 7px;border-radius:4px;
    border:1px solid var(--line);color:var(--slate);background:var(--paper);white-space:nowrap}
  .step.ok{background:var(--green-soft);color:var(--green);border-color:#cfe0d6}
  .step.error{background:#f3e2de;color:var(--red);border-color:#e3cdc7}
  .step.timeout{background:#f3e2de;color:var(--red);border-color:#e3cdc7}
  .step.started{background:var(--blue-soft);color:var(--blue);border-color:#cfe0d6}
  .step.skipped{opacity:.6}
  .chip.s-ok{background:var(--green-soft);color:var(--green);border-color:#cfe0d6}
  .chip.s-started{background:var(--blue-soft);color:var(--blue);border-color:#cfe0d6}
  .chip.s-waiting{background:var(--yellow-soft);color:#7a6410;border-color:#eedf9e}
  .chip.s-failed,.chip.s-error,.chip.s-timeout{background:#f3e2de;color:var(--red);border-color:#e3cdc7}
  .chip.s-skipped{opacity:.7}
  .toast{position:fixed;left:50%;bottom:26px;transform:translateX(-50%);
    font-family:var(--sans);font-size:14px;padding:10px 18px;border-radius:8px;
    background:var(--ink);color:var(--paper);box-shadow:0 6px 22px rgba(0,0,0,.22);
    max-width:min(720px,92vw);z-index:20}
  .toast.bad{background:var(--red)}
  .toast.hidden{display:none}
  .who{font-family:var(--sans);font-size:12.5px;color:var(--slate);
    display:flex;flex-wrap:wrap;gap:6px 16px;align-items:center}
  .who input{max-width:230px;padding:4px 8px;font-size:12.5px}
  .note{font-family:var(--sans);font-size:13px;color:var(--slate);max-width:680px}
  .rowactions{display:flex;flex-wrap:wrap;gap:8px;align-items:center;margin-top:10px}
  .rowactions input,.rowactions textarea{max-width:340px}
  @media (max-width:640px){ .keyform{gap:6px} select{max-width:150px} }
"""


def build_html(url: str, publishable_key: str, *, local: bool, project_ref: str) -> str:
    cfg = {
        "url": url.rstrip("/"),
        "key": publishable_key,
        "local": local,
        "projectRef": project_ref,
        "consoleBase": CONSOLE_BASE,
        "workspaceId": WORKSPACE_ID,
        "menuItems": list(MENU_ITEMS),
        "forbidden": list(FORBIDDEN_ITEMS),
        "discouraged": list(DISCOURAGED_ITEMS),
        "familyOf": dict(FAMILY_OF),
        "tolerance": WEIGHT_TOLERANCE,
        "days": 14,
    }
    dash = (f"https://supabase.com/dashboard/project/{project_ref}" if project_ref else "")
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="robots" content="noindex, nofollow">
<title>Operator inbox · Cycling Race Predictor</title>
{FAVICON}
<style>{CSS}{OPS_CSS}</style>
</head>
<body>
<div class="wrap">
<nav class="topnav"><a class="brand" href="/">Cycling Race Predictor</a>
<span class="muted">Operator inbox — not part of the public site</span></nav>

<header>
<div class="eyebrow">Control plane · human decisions</div>
<h1>Operator inbox <span id="badge" class="badge">…</span></h1>
<p class="standfirst">Everything the nightly run cannot decide for itself: day keys,
rider identities, publication approvals, and whatever the run flagged on its way past.
The count above is the whole notification system — this page is polled, not pushed.</p>
<div class="meta">
<span id="who" class="who"></span>
</div>
</header>

<div id="signin" class="signin" hidden>
<h2>Sign in as an operator</h2>
<p>Row-level security decides what you can do; this page only ever holds the
publishable key. Sign in with the operator account, or paste a role token from
<span class="mono">supabase/mint_keys.py operator</span>.</p>
<label for="email">Email</label>
<input id="email" type="email" autocomplete="username" placeholder="you@example.com">
<label for="password">Password</label>
<input id="password" type="password" autocomplete="current-password">
<div class="btnrow">
<button id="btn-password">Sign in</button>
<button id="btn-magic" class="ghost">Email me a link</button>
</div>
<p class="note" style="margin-top:10px">A magic link only works once the project's
Auth <b>Site URL</b> points at this page; while it is still the localhost placeholder
the link will bounce. Password sign-in is unaffected.</p>
<label for="token">…or an operator role token</label>
<input id="token" type="password" placeholder="eyJhbGciOi…" autocomplete="off">
<div class="btnrow"><button id="btn-token" class="ghost">Use token</button></div>
<p class="note" style="margin-top:10px">The token is kept in this tab only
(<span class="mono">sessionStorage</span>) and is gone when you close it.</p>
<p id="signin-error" class="note" style="color:var(--red)"></p>
</div>

<div id="app" hidden>
<section>
<p class="kicker">Waiting on you</p>
<h2 id="waiting-head">Nothing is waiting</h2>
<div id="tasks"></div>
<div id="daykeys"></div>
<div id="proposals"></div>
<div id="runs-pending"></div>
</section>

<section>
<p class="kicker">Ledger</p>
<h2>The last 14 nights</h2>
<p class="note">One row per run — a campaign, a unit and a phase. State comes from
the <span class="mono">finish</span> step; runs are append-only, so a missing finish
means the container stopped mid-run.</p>
<div id="runs"></div>
</section>

<div class="btnrow" style="margin-top:36px">
<button id="btn-refresh" class="ghost">Refresh</button>
<button id="btn-signout" class="ghost">Sign out</button>
<span id="loaded" class="note"></span>
</div>
</div>

<div class="footer">Generated by <span class="mono">build_ops_page.py</span> from
<span class="mono">{esc_py(cfg["url"])}</span>. Local page: gitignored, never deployed.
Market probabilities appear across this project as a benchmark — a measure of how much
real information the model captures — not as betting guidance.
{f'<br><a href="{dash}">Supabase dashboard</a> · <a href="https://platform.claude.com/workspaces/{WORKSPACE_ID}">Managed Agents workspace</a>' if dash else ''}</div>
</div>

<div id="toast" class="toast hidden"></div>

<script type="module">
import {{ createClient }} from "{SUPABASE_JS}";

const CFG = {json.dumps(cfg, indent=2, sort_keys=True)};
const DASH = {json.dumps(dash)};

const $ = (id) => document.getElementById(id);
const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) =>
  ({{"&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;"}}[c]));

let sb = null;          // supabase client
let mode = null;        // 'auth' | 'token'
let identity = localStorage.getItem("ops.identity") || "";
let data = {{}};

// ---------------------------------------------------------------- toast
let toastTimer = null;
function toast(msg, bad) {{
  const el = $("toast");
  el.textContent = msg;
  el.className = "toast" + (bad ? " bad" : "");
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => el.classList.add("hidden"), bad ? 9000 : 4000);
}}

// ---------------------------------------------------------------- clients
function anonClient() {{
  return createClient(CFG.url, CFG.key, {{
    auth: {{ persistSession: true, storageKey: "ops.auth" }},
  }});
}}
function tokenClient(token) {{
  return createClient(CFG.url, CFG.key, {{
    auth: {{ persistSession: false, autoRefreshToken: false }},
    global: {{ headers: {{ Authorization: "Bearer " + token }} }},
  }});
}}

// ---------------------------------------------------------------- sign in
async function start() {{
  const token = sessionStorage.getItem("ops.token");
  if (token) {{
    sb = tokenClient(token);
    mode = "token";
    if (await ok()) return show();
    sessionStorage.removeItem("ops.token");
  }}
  sb = anonClient();
  mode = "auth";
  const {{ data: {{ session }} }} = await sb.auth.getSession();
  if (session) {{
    identity = identity || session.user.email || "";
    if (await ok()) return show();
  }}
  $("signin").hidden = false;
  $("app").hidden = true;
}}

async function ok() {{
  const {{ data: rows, error }} = await sb.from("operator_tasks").select("id").limit(1);
  if (error) {{ $("signin-error").textContent = error.message; return false; }}
  return true;
}}

async function show() {{
  $("signin").hidden = true;
  $("app").hidden = false;
  renderWho();
  await load();
}}

$("btn-password").onclick = async () => {{
  const email = $("email").value.trim(), password = $("password").value;
  sb = anonClient(); mode = "auth";
  const {{ error }} = await sb.auth.signInWithPassword({{ email, password }});
  if (error) return ($("signin-error").textContent = error.message);
  identity = email;
  localStorage.setItem("ops.identity", identity);
  if (await ok()) show();
}};

$("btn-magic").onclick = async () => {{
  const email = $("email").value.trim();
  if (!email) return ($("signin-error").textContent = "Enter your email first.");
  sb = anonClient(); mode = "auth";
  const {{ error }} = await sb.auth.signInWithOtp(
    {{ email, options: {{ emailRedirectTo: location.href }} }});
  $("signin-error").textContent = error ? error.message
    : "Link sent. It only lands here if the project's Auth Site URL points at this page.";
}};

$("btn-token").onclick = async () => {{
  const token = $("token").value.trim();
  if (!token) return;
  sb = tokenClient(token); mode = "token";
  if (await ok()) {{
    sessionStorage.setItem("ops.token", token);
    $("token").value = "";
    show();
  }}
}};

$("btn-signout").onclick = async () => {{
  sessionStorage.removeItem("ops.token");
  if (mode === "auth" && sb) await sb.auth.signOut();
  location.reload();
}};

$("btn-refresh").onclick = () => load();

function renderWho() {{
  $("who").innerHTML =
    `<span>Signed in via <b>${{mode === "token" ? "role token" : "Supabase Auth"}}</b></span>` +
    `<span>Acting as <input id="identity" value="${{esc(identity)}}" placeholder="your name or email"></span>` +
    (DASH ? `<span><a href="${{DASH}}/editor">Table editor →</a></span>` : "");
  $("identity").onchange = (e) => {{
    identity = e.target.value.trim();
    localStorage.setItem("ops.identity", identity);
  }};
}}

function requireIdentity() {{
  if (!identity) {{
    toast("Fill in “Acting as” first — it is written to approved_by / resolved_by.", true);
    return false;
  }}
  return true;
}}

// ---------------------------------------------------------------- load
const since = () => new Date(Date.now() - CFG.days * 864e5).toISOString();

async function load() {{
  $("loaded").textContent = "loading…";
  const q = [
    sb.from("operator_tasks").select("*").eq("resolved", false).order("created_at", {{ ascending: false }}),
    sb.from("day_key_decisions").select("*").order("created_at", {{ ascending: false }}).limit(400),
    sb.from("crosswalk_proposals").select("*").eq("status", "proposed").order("created_at", {{ ascending: false }}),
    sb.from("run_status").select("*").gte("started_at", since()).order("started_at", {{ ascending: false }}),
    sb.from("approvals").select("*").order("created_at", {{ ascending: false }}).limit(500),
  ];
  const res = await Promise.all(q);
  const bad = res.find((r) => r.error);
  if (bad) {{ toast("Query failed: " + bad.error.message, true); $("loaded").textContent = ""; return; }}
  const [tasks, keys, proposals, runs, approvals] = res.map((r) => r.data || []);

  let steps = [];
  if (runs.length) {{
    const ids = runs.map((r) => r.run_id);
    const s = await sb.from("run_steps").select("*").in("run_id", ids).order("id");
    if (s.error) toast("run_steps: " + s.error.message, true);
    steps = s.data || [];
  }}
  data = {{ tasks, keys, proposals, runs, approvals, steps }};
  render();
  $("loaded").textContent = "loaded " + new Date().toLocaleTimeString();
}}

// ---------------------------------------------------------------- render
function render() {{
  const pendingKeys = pendingDayKeys();
  const pendingRuns = runsAwaitingApproval();
  const n = data.tasks.length + pendingKeys.length + data.proposals.length + pendingRuns.length;

  document.title = (n ? `(${{n}}) ` : "") + "Operator inbox · Cycling Race Predictor";
  const badge = $("badge");
  badge.textContent = n ? `${{n}} waiting` : "clear";
  badge.className = "badge" + (n ? "" : " clear");
  $("waiting-head").textContent = n
    ? `${{n}} decision${{n === 1 ? "" : "s"}} for you`
    : "Nothing is waiting";

  renderTasks();
  renderDayKeys(pendingKeys);
  renderProposals();
  renderPendingRuns(pendingRuns);
  renderRuns();
}}

function block(title, html) {{
  return html ? `<h3 style="margin-top:26px">${{esc(title)}}</h3>${{html}}` : "";
}}

// -- operator_tasks
function renderTasks() {{
  const rows = data.tasks.map((t) => {{
    const cls = t.urgency === "urgent" ? "urgent"
      : (t.urgency || "").startsWith("blocks") ? "blocks" : "";
    return `<div class="item ${{cls}}">
      <h3>${{esc(t.summary)}}</h3>
      <div class="sub"><span>${{esc(t.kind)}}</span>
        <span>${{esc(t.campaign_slug || "—")}}</span>
        <span>urgency <b>${{esc(t.urgency)}}</b></span>
        <span>${{esc((t.created_at || "").slice(0, 16).replace("T", " "))}}</span></div>
      ${{detailBlock(t.detail)}}
      <div class="rowactions">
        <input id="res-${{t.id}}" placeholder="how you resolved it (optional)">
        <button data-task="${{t.id}}">Mark resolved</button>
      </div></div>`;
  }}).join("");
  $("tasks").innerHTML = block("Flagged by the run", rows);
  $("tasks").querySelectorAll("button[data-task]").forEach((b) => {{
    b.onclick = () => resolveTask(Number(b.dataset.task));
  }});
}}

function detailBlock(detail) {{
  if (!detail || (typeof detail === "object" && !Object.keys(detail).length)) return "";
  return `<details><summary>detail</summary><pre>${{esc(JSON.stringify(detail, null, 2))}}</pre></details>`;
}}

async function resolveTask(id) {{
  if (!requireIdentity()) return;
  const resolution = ($(`res-${{id}}`) || {{}}).value || null;
  const {{ error }} = await sb.from("operator_tasks")
    .update({{ resolved: true, resolved_by: identity, resolution }}).eq("id", id);
  if (error) return toast("Could not resolve: " + error.message, true);
  toast("Task resolved.");
  load();
}}

// -- day_key_decisions
function unitKey(r) {{ return `${{r.campaign_slug}}::${{r.unit}}`; }}

function pendingDayKeys() {{
  const approved = new Set(data.keys.filter((k) => k.approved_by).map(unitKey));
  const seen = new Set();
  const out = [];
  for (const k of data.keys) {{
    if (k.approved_by || k.author === "human") continue;
    const u = unitKey(k);
    if (approved.has(u) || seen.has(u)) continue;   // newest proposal per unit
    seen.add(u);
    out.push(k);
  }}
  return out;
}}

function keyText(map) {{
  if (!map || typeof map !== "object") return "—";
  return Object.entries(map).sort((a, b) => b[1] - a[1])
    .map(([k, v]) => `${{k}} ${{Number(v).toFixed(2)}}`).join(" · ");
}}

function agentKeyMap(row) {{
  const ev = row.evidence || {{}};
  const rec = ev.record || {{}};
  if (rec.key && typeof rec.key === "object") return rec.key;
  if (ev.key && typeof ev.key === "object") return ev.key;
  return row.day_key ? {{ [row.day_key]: 1 }} : {{}};
}}

function renderDayKeys(pending) {{
  const rows = pending.map((k) => {{
    const rec = (k.evidence || {{}}).record || {{}};
    const map = agentKeyMap(k);
    const flagged = rec.human_review_required
      ? `<span class="flagged">flagged for review${{rec.review_reason ? ": " + esc(rec.review_reason) : ""}}</span>` : "";
    const opts = CFG.menuItems.map((i) => `<option value="${{i}}">${{i}}</option>`).join("");
    const pair = (n) => `<span class="pair">
      <select id="k-${{k.id}}-i${{n}}"><option value="">—</option>${{opts}}</select>
      <input id="k-${{k.id}}-w${{n}}" type="number" step="0.05" min="0" max="1" placeholder="w"></span>`;
    return `<div class="item">
      <h3>${{esc(k.campaign_slug)}} · ${{esc(k.unit)}}</h3>
      <div class="sub"><span>proposed by <b>${{esc(k.author)}}</b></span>
        <span>confidence <b>${{k.confidence == null ? "—" : Number(k.confidence).toFixed(2)}}</b></span>
        <span>${{esc((k.created_at || "").slice(0, 16).replace("T", " "))}}</span>${{flagged}}</div>
      <div class="agentkey"><span class="k">${{esc(keyText(map))}}</span>
        ${{k.rationale ? `<div style="margin-top:5px">${{esc(k.rationale)}}</div>` : ""}}</div>
      ${{detailBlock(k.evidence)}}
      <div class="keyform">${{pair(0)}}${{pair(1)}}${{pair(2)}}
        <span class="sum" id="k-${{k.id}}-sum">sum 0.00</span></div>
      <div class="rowactions">
        <textarea id="k-${{k.id}}-note" placeholder="your reasoning (stored as rationale)"></textarea>
      </div>
      <div class="btnrow">
        <button data-key="${{k.id}}">Approve as the serving key</button>
        <button class="ghost" data-adopt="${{k.id}}">Prefill the agent's key</button>
      </div></div>`;
  }}).join("");
  $("daykeys").innerHTML = block("Day keys with no human read", rows);

  for (const k of pending) {{
    const recompute = () => keySum(k.id);
    [0, 1, 2].forEach((n) => {{
      $(`k-${{k.id}}-i${{n}}`).onchange = recompute;
      $(`k-${{k.id}}-w${{n}}`).oninput = recompute;
    }});
    $("daykeys").querySelector(`button[data-adopt="${{k.id}}"]`).onclick = () => {{
      const entries = Object.entries(agentKeyMap(k)).sort((a, b) => b[1] - a[1]).slice(0, 3);
      [0, 1, 2].forEach((n) => {{
        $(`k-${{k.id}}-i${{n}}`).value = entries[n] ? entries[n][0] : "";
        $(`k-${{k.id}}-w${{n}}`).value = entries[n] ? Number(entries[n][1]).toFixed(2) : "";
      }});
      recompute();
    }};
    $("daykeys").querySelector(`button[data-key="${{k.id}}"]`).onclick = () => approveKey(k);
  }}
}}

function readKeyForm(id) {{
  const map = {{}};
  for (const n of [0, 1, 2]) {{
    const item = $(`k-${{id}}-i${{n}}`).value;
    const w = parseFloat($(`k-${{id}}-w${{n}}`).value);
    if (!item) continue;
    if (!Number.isFinite(w)) return {{ map, errors: [`weight missing for ${{item}}`] }};
    map[item] = (map[item] || 0) + w;
  }}
  return {{ map, errors: keyErrors(map) }};
}}

function keyErrors(map) {{
  const items = Object.keys(map);
  const errors = [];
  if (!items.length) errors.push("pick at least one menu item");
  if (items.length > 3) errors.push("at most 3 items");
  let total = 0;
  for (const [i, w] of Object.entries(map)) {{
    if (CFG.forbidden.includes(i)) errors.push(`${{i}} is never keyed`);
    if (!(w > 0 && w <= 1 + CFG.tolerance)) errors.push(`weight for ${{i}} must be in (0, 1]`);
    total += w;
  }}
  if (items.length && Math.abs(total - 1) > CFG.tolerance)
    errors.push(`weights sum to ${{total.toFixed(3)}}, not 1`);
  const fams = new Set(items.map((i) => CFG.familyOf[i]).filter(Boolean));
  if (fams.has("escape") && fams.has("power_sprint"))
    errors.push("no hedging across escape and power_sprint");
  return errors;
}}

function keySum(id) {{
  const {{ map, errors }} = readKeyForm(id);
  const total = Object.values(map).reduce((a, b) => a + b, 0);
  const el = $(`k-${{id}}-sum`);
  el.textContent = `sum ${{total.toFixed(2)}}` + (errors.length ? ` — ${{errors[0]}}` : "");
  el.className = "sum" + (errors.length ? " bad" : "");
}}

async function approveKey(row) {{
  if (!requireIdentity()) return;
  const {{ map, errors }} = readKeyForm(row.id);
  if (errors.length) return toast(errors.join("; "), true);
  const top = Object.entries(map).sort((a, b) => b[1] - a[1] || (a[0] < b[0] ? -1 : 1))[0][0];
  const note = $(`k-${{row.id}}-note`).value.trim();
  const {{ error }} = await sb.from("day_key_decisions").insert({{
    campaign_slug: row.campaign_slug,
    unit: row.unit,
    author: "human",
    day_key: top,
    family: CFG.familyOf[top] || null,
    rationale: note || null,
    approved_by: identity,
    evidence: {{
      key: Object.fromEntries(Object.entries(map).map(([k, v]) => [k, Number(v.toFixed(4))])),
      source: "ops_page",
      agent_proposal_id: row.id,
      agent_key: agentKeyMap(row),
    }},
  }});
  if (error) return toast("Insert refused: " + error.message, true);
  toast(`Key approved for ${{row.campaign_slug}} ${{row.unit}} — ${{keyText(map)}}`);
  load();
}}

// -- crosswalk_proposals
function renderProposals() {{
  const rows = data.proposals.map((p) => `<div class="item">
    <h3>${{esc(p.pcs_name || p.pcs_slug)}} → ${{esc(p.fc_name || p.fc_rider_id || "no candidate")}}</h3>
    <div class="sub"><span>${{esc(p.campaign_slug || "—")}}</span>
      <span>confidence <b>${{p.confidence == null ? "—" : Number(p.confidence).toFixed(2)}}</b></span>
      <span>fc id <b>${{esc(p.fc_rider_id || "—")}}</b></span>
      <span>${{esc(p.pcs_team || "")}}</span></div>
    ${{p.evidence ? `<p class="note">${{esc(p.evidence)}}</p>` : ""}}
    ${{Array.isArray(p.alternates) && p.alternates.length ? detailBlock(p.alternates) : ""}}
    <div class="btnrow">
      <button data-confirm="${{p.id}}"${{p.fc_rider_id ? "" : " disabled"}}>Confirm this match</button>
      <button class="ghost" data-reject="${{p.id}}">Reject</button>
    </div></div>`).join("");
  $("proposals").innerHTML = block("Rider identities to confirm", rows);
  $("proposals").querySelectorAll("button[data-confirm]").forEach((b) => {{
    b.onclick = () => resolveProposal(Number(b.dataset.confirm), true);
  }});
  $("proposals").querySelectorAll("button[data-reject]").forEach((b) => {{
    b.onclick = () => resolveProposal(Number(b.dataset.reject), false);
  }});
}}

async function resolveProposal(id, confirm) {{
  if (!requireIdentity()) return;
  const p = data.proposals.find((x) => x.id === id);
  if (!p) return;
  if (confirm) {{
    const {{ error }} = await sb.from("crosswalk").upsert({{
      pcs_slug: p.pcs_slug, fc_rider_id: p.fc_rider_id, internal_rider_id: p.internal_rider_id,
      pcs_name: p.pcs_name, fc_name: p.fc_name, confidence: p.confidence,
      source: "human", confirmed_by: identity,
    }}, {{ onConflict: "pcs_slug" }});
    if (error) return toast("Crosswalk write refused: " + error.message, true);
  }}
  const {{ error }} = await sb.from("crosswalk_proposals")
    .update({{ status: confirm ? "confirmed" : "rejected", resolved_by: identity,
              resolved_at: new Date().toISOString() }}).eq("id", id);
  if (error) return toast("Proposal update refused: " + error.message, true);
  toast(confirm ? `Confirmed ${{p.pcs_slug}}. Re-export the crosswalk CSV before the next release.`
                : `Rejected ${{p.pcs_slug}}.`);
  load();
}}

// -- runs awaiting publication approval
const PUBLISHABLE_PHASES = ["settle", "preview"];

function runsAwaitingApproval() {{
  const approved = new Set(data.approvals.filter((a) => a.decision === "approve").map((a) => a.run_id));
  const decided = new Set(data.approvals.map((a) => a.run_id));
  return data.runs.filter((r) =>
    PUBLISHABLE_PHASES.includes(r.phase) && r.state === "ok" &&
    !approved.has(r.run_id) && !decided.has(r.run_id));
}}

function renderPendingRuns(pending) {{
  const rows = pending.map((r) => `<div class="item">
    <h3>${{esc(r.campaign_slug || "—")}} · ${{esc(r.unit || "—")}} · ${{esc(r.phase)}}</h3>
    <div class="sub"><span>${{esc((r.started_at || "").slice(0, 16).replace("T", " "))}}</span>
      <span>release <b>${{esc(r.release_tag || "—")}}</b></span>
      <span>${{stepChips(r.run_id)}}</span></div>
    <p class="note">Approving inserts an <span class="mono">approvals</span> row.
      Nothing is published until <span class="mono">promote</span> runs on the Mac.</p>
    <div class="rowactions">
      <input id="ap-${{r.run_id}}" placeholder="note (visible to the agent)">
      <button data-approve="${{r.run_id}}">Approve for publication</button>
      <button class="ghost" data-hold="${{r.run_id}}">Hold</button>
    </div>
    <p class="note mono" style="font-size:11.5px;margin-top:8px">${{esc(r.run_id)}}</p>
    </div>`).join("");
  $("runs-pending").innerHTML = block("Runs waiting for a publication decision", rows);
  $("runs-pending").querySelectorAll("button[data-approve]").forEach((b) => {{
    b.onclick = () => decideRun(b.dataset.approve, "approve");
  }});
  $("runs-pending").querySelectorAll("button[data-hold]").forEach((b) => {{
    b.onclick = () => decideRun(b.dataset.hold, "hold");
  }});
}}

async function decideRun(runId, decision) {{
  if (!requireIdentity()) return;
  const r = data.runs.find((x) => x.run_id === runId);
  const note = ($(`ap-${{runId}}`) || {{}}).value || null;
  const {{ error }} = await sb.from("approvals").insert({{
    run_id: runId, campaign_slug: r ? r.campaign_slug : null, unit: r ? r.unit : null,
    kind: "publish", decision, approved_by: identity, note,
  }});
  if (error) return toast("Approval refused: " + error.message, true);
  toast(decision === "approve"
    ? "Approved. Publish it with: python -m cycling_project.nightly.promote --run " + runId
    : "Held — promote will skip it.");
  load();
}}

// -- ledger
function stepChips(runId) {{
  return data.steps.filter((s) => s.run_id === runId).map((s) => {{
    const ms = s.duration_ms ? ` ${{(s.duration_ms / 1000).toFixed(1)}}s` : "";
    return `<span class="step ${{esc(s.state)}}" title="${{esc(s.log_key || "")}}">${{esc(s.step)}}${{ms}}</span>`;
  }}).join("");
}}

function renderRuns() {{
  if (!data.runs.length) {{
    $("runs").innerHTML = `<p class="empty">No runs in the last ${{CFG.days}} days.</p>`;
    return;
  }}
  const approved = new Map(data.approvals.map((a) => [a.run_id, a.decision]));
  const rows = data.runs.map((r) => {{
    const steps = data.steps.filter((s) => s.run_id === r.run_id);
    const logs = steps.filter((s) => s.log_key);
    const session = r.session_id
      ? `<a href="${{CFG.consoleBase}}${{encodeURIComponent(r.session_id)}}">session →</a>` : "—";
    const logLink = logs.length && DASH
      ? `<a href="${{DASH}}/storage/buckets/nightly-artifacts?path=${{encodeURIComponent(r.run_id + "/")}}">${{logs.length}} log${{logs.length === 1 ? "" : "s"}} →</a>`
      : (logs.length ? `${{logs.length}} log${{logs.length === 1 ? "" : "s"}}` : "—");
    const dec = approved.get(r.run_id);
    return `<tr>
      <td>${{esc((r.started_at || "").slice(5, 16).replace("T", " "))}}</td>
      <td>${{esc(r.campaign_slug || "—")}}</td>
      <td>${{esc(r.unit || "—")}}</td>
      <td>${{esc(r.phase)}}</td>
      <td><span class="chip s-${{esc(r.state)}}">${{esc(r.state)}}</span></td>
      <td>${{r.exit_code == null ? "—" : r.exit_code}}</td>
      <td><div class="steps">${{stepChips(r.run_id)}}</div></td>
      <td>${{dec ? esc(dec) : "—"}}</td>
      <td>${{session}}</td>
      <td>${{logLink}}</td></tr>`;
  }}).join("");
  $("runs").innerHTML = `<div class="tablewrap"><table>
    <thead><tr><th>Started</th><th>Campaign</th><th>Unit</th><th>Phase</th><th>State</th>
    <th>Exit</th><th>Steps</th><th>Decision</th><th>Console</th><th>Logs</th></tr></thead>
    <tbody>${{rows}}</tbody></table></div>`;
}}

start();
setInterval(() => {{ if (!$("app").hidden) load(); }}, 120000);
</script>
</body>
</html>
"""


def esc_py(s: str) -> str:
    return (str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"))


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--local", action="store_true",
                    help="point the page at the local `supabase start` stack")
    ap.add_argument("--url", help="Supabase project URL (default: SUPABASE_URL)")
    ap.add_argument("--key", help="publishable key (default: SUPABASE_PUBLISHABLE_KEY)")
    ap.add_argument("--out", type=Path, default=OUT_PATH)
    args = ap.parse_args(argv)

    url, key, ref = args.url, args.key, ""
    if args.local:
        env = local_stack_env()
        if not env:
            print("no local stack — run `supabase start` in the repo root", file=sys.stderr)
            return 2
        url = url or env.get("API_URL", "")
        key = key or env.get("PUBLISHABLE_KEY") or env.get("ANON_KEY", "")
    else:
        from cycling_project.nightly.secrets import load_local_env
        load_local_env()
        url = url or os.environ.get("SUPABASE_URL", "")
        key = key or os.environ.get("SUPABASE_PUBLISHABLE_KEY", "")
        ref = os.environ.get("SUPABASE_PROJECT_REF", "")

    if not url or not key:
        print("missing SUPABASE_URL / SUPABASE_PUBLISHABLE_KEY (see CLAUDE.md 'Credentials')",
              file=sys.stderr)
        return 2
    if any(key.startswith(p) for p in SECRET_KEY_PREFIXES):
        print("refusing to embed a secret key in a page; pass the PUBLISHABLE key",
              file=sys.stderr)
        return 2

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(build_html(url, key, local=args.local, project_ref=ref))
    print(f"wrote {args.out.relative_to(PROJECT_ROOT)} → {url}"
          f"{' (local stack)' if args.local else ''}\n"
          f"preview: uv run python -m http.server 8411 --directory netlify_site"
          f"  →  http://localhost:8411/_frame/ops.html")
    return 0


if __name__ == "__main__":
    sys.exit(main())
