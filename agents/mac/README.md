# Mac-side scheduled jobs

The cloud nightly cannot reach FirstCycling or ProCyclingStats (Cloudflare),
the UCI gives it a calendar and results but no field and no route, and Kambi
lists WorldTour only. Everything else is captured here, on the owner's Mac,
and handed over as Supabase artifacts.

## `com.cycling.horizon.plist` — daily horizon capture

    uv run python -m cycling_project.nightly.horizon --store auto

For every unit the cloud is about to preview (default: the next 3 days) it
captures the start list, the FirstCycling stage page and the route facts,
fills the campaign's stage metadata, and uploads all of it as
`nightly-artifacts` objects keyed `<run_id>/<campaign>/<relpath>` — which
`nightly bootstrap` overlays onto the release bundle on the next tick. Every
run is a `runs` row with phase `horizon` and `host = 'mac'`.

**A visible Chrome window is required.** `SCRAPER_USE_BROWSER=1` drives real
challenge — so the job is scheduled during the working day, in a logged-in GUI
session, and the window will appear while it runs. Do not close it mid-run.

Timing: the cloud tick is **19:45 UTC**; the job runs at **10:30 local**
(17:30 UTC on US Pacific). Re-time it if the tick or the Mac's timezone moves —
a capture that lands after the tick is only seen the following night.

### Install / remove

```bash
cp agents/mac/com.cycling.horizon.plist ~/Library/LaunchAgents/
launchctl load   ~/Library/LaunchAgents/com.cycling.horizon.plist     # enable
launchctl unload ~/Library/LaunchAgents/com.cycling.horizon.plist     # disable
launchctl list | grep com.cycling.horizon                             # is it loaded?
launchctl start  com.cycling.horizon                                  # run it now
```

Reload after editing the plist: `unload`, then `load`.

### Where it logs

`performance_eval/runs/horizon_<date>.log` (one file per day, appended), plus
`/tmp/com.cycling.horizon.{out,err}` for anything launchd itself has to say.
The JSON summary is the last thing on stdout: one entry per campaign, its due
units, the steps and the artifact keys.

### Checking it by hand

```bash
# what would be captured, no fetch, no writes, fake store
uv run python -m cycling_project.nightly.horizon --dry-run --days 4

# one campaign, hosted ledger
uv run python -m cycling_project.nightly.horizon --campaign giro-d-abruzzo-2026

# anything that failed is an operator task of kind horizon_failed
uv run python -m cycling_project.nightly.promote --help   # the inbox lives elsewhere
```

`--store auto` writes to the **hosted** control plane whenever Supabase
operator credentials load from `~/.config/cycling-project/secrets.env` — which
is the case on this Mac. Every test and experiment passes `--store fake` or
`--dry-run` (see the gotcha in `CLAUDE.md`).

Nothing here bypasses the scraper's 3-second minimum between requests, and a
unit whose capture is younger than `--max-age-hours` (default 20) is reused
rather than re-fetched: a normal day costs one race page plus one stage page
per due unit.
