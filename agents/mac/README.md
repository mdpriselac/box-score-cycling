# Mac-side scheduled jobs

The cloud nightly cannot reach FirstCycling or ProCyclingStats (Cloudflare),
the UCI gives it a calendar and results but no field and no route, and Kambi
lists WorldTour only. Everything else is captured here, on the owner's Mac,
and handed over as Supabase artifacts.

## `com.cycling.horizon.plist` + `com.cycling.horizon.late.plist` — horizon capture

    uv run python -m cycling_project.nightly.horizon --store auto

For every unit the cloud is about to preview (default: the next 3 days) it
captures the start list, the FirstCycling stage page and the route facts,
fills the campaign's stage metadata, and uploads all of it as
`nightly-artifacts` objects keyed `<run_id>/<campaign>/<relpath>` — which
`nightly bootstrap` overlays onto the release bundle on the next tick. Every
run is a `runs` row with phase `horizon` and `host = 'mac'`.

**This job needs the private browser backend**, which isn't part of this repo, so it runs on the
Mac during the working day, in a logged-in GUI session.

Timing: two captures a day (2026-10-05), one per cloud tick:

| Job | Local time | Feeds | Extra flag |
|---|---|---|---|
| `com.cycling.horizon` | 10:30 | 19:45 UTC tick (12:45 PDT / 11:45 PST) | — |
| `com.cycling.horizon.late` | 22:00 | 23:00 Pacific tick (race morning in Europe) | `--max-age-hours 10` |

FirstCycling posts European start lists overnight European time (Tre Valli
Varesine 2026: placeholder at 10:30 PT, 170 riders at 21:44 PT), so the late
job re-fetches anything the 10:30 run captured. Both append to the same
`horizon_<date>.log`. Re-time them if a tick or the Mac's timezone moves — a
capture that lands after its tick is only seen by the next one. If the Mac is
asleep at 22:00, launchd runs the job at wake, which may be after the race.

### Install / remove

```bash
cp agents/mac/com.cycling.horizon.plist agents/mac/com.cycling.horizon.late.plist ~/Library/LaunchAgents/
launchctl load   ~/Library/LaunchAgents/com.cycling.horizon.plist          # enable (each job)
launchctl load   ~/Library/LaunchAgents/com.cycling.horizon.late.plist
launchctl unload ~/Library/LaunchAgents/com.cycling.horizon.late.plist     # disable
launchctl list | grep com.cycling.horizon                                  # both loaded?
launchctl start  com.cycling.horizon.late                                  # run it now
```

Reload after editing a plist: `unload`, then `load`. launchd's own output goes
to `/tmp/com.cycling.horizon{,.late}.{out,err}`.

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
