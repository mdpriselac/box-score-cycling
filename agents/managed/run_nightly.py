"""Fire one manual run of the scheduled `nightly` deployment and watch it.

    uv run --group agents python agents/managed/run_nightly.py --api-key            # asks y/N (paid), streams, collects
    uv run --group agents python agents/managed/run_nightly.py --api-key --session-id sesn_…   # re-collect only

A manual run fires exactly what the 19:45 UTC tick would fire ("Run the nightly
cycle." with the deployment's budget), is allowed while the deployment is
paused, and is the last check before unpausing.  Nothing here changes the
deployment; outputs land under performance_eval/runs/manual_<stamp>/.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import provision as pv          # noqa: E402
import smoke_test as st         # noqa: E402
from cycling_project.nightly.secrets import load_local_env  # noqa: E402

RUNS_DIR = HERE.parent.parent / "performance_eval" / "runs"


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--api-key", action="store_true", help="authenticate with ANTHROPIC_API_KEY (the cycling-nightly workspace)")
    ap.add_argument("--session-id", default=None, help="re-collect an existing session instead of firing a run")
    ap.add_argument("--max-minutes", type=float, default=90.0)
    ap.add_argument("--yes", action="store_true", help="skip the paid-run confirmation")
    args = ap.parse_args(argv)

    # Match provision.py: load the cycling-nightly credential before creating
    # the client.  Otherwise --api-key may inherit an unrelated ambient key
    # and make the correct workspace's resources appear to be missing.
    load_local_env(require=("ANTHROPIC_API_KEY",) if args.api_key else ())
    ids = json.loads(pv.IDS_PATH.read_text())
    client = pv.make_client(use_api_key=args.api_key, workspace_id=ids.get("workspace_id"))
    depl = ids["deployments"]["nightly"]
    ws = ids.get("workspace_id") or "default"

    if args.session_id:
        sid = args.session_id
    else:
        # The managed-agents API can return 404 from the direct retrieve
        # endpoint even when the deployment is visible in the workspace-scoped
        # collection.  Resolve it from that collection, which is also what the
        # provisioner uses for idempotent updates.
        d = pv._find(client.beta.deployments.list(limit=100), "id", depl["id"])
        if d is None:
            raise SystemExit(f"deployment not found in workspace {ws}: {depl['id']}")
        print(f"deployment {d.name} ({depl['id']}) status={getattr(d, 'status', '?')} "
              f"agent={d.agent.id} v{d.agent.version} env={d.environment_id}")
        if not args.yes:
            ans = input("Fire one manual run now (paid, capped by the deployment budget)? [y/N] ").strip().lower()
            if ans != "y":
                print("not fired")
                return 1
        run = client.beta.deployments.run(depl["id"])
        if not run.session_id:
            raise SystemExit(f"deployment run failed: {run.error}")
        sid = run.session_id
        print(f"fired: run {getattr(run, 'id', '?')} → session {sid}")
        print(f"console: https://platform.claude.com/workspaces/{ws}/sessions/{sid}", flush=True)
        st.stream_until_idle(client, sid, max_minutes=args.max_minutes)

    stamp = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out_dir = RUNS_DIR / f"manual_{stamp}"
    summary = st.collect(client, sid, out_dir)
    print(json.dumps({k: v for k, v in summary.items() if k != "events"}, indent=1, default=str)[:4000])
    print(f"saved under {out_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
