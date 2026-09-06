#!/usr/bin/env bash
# Stage 0 — the only code that runs before any repo code exists in the container.
# Fetches the newest APPROVED release's code zip from Supabase Storage (releases/<tag>/), unpacks it,
# then hands over to cycling_project.nightly.bootstrap, which verifies every bundle file by sha256,
# checks the model contract, `uv sync`s, hydrates campaign dirs and writes nightly_env.sh.
# Needs: SUPABASE_URL, SUPABASE_PUBLISHABLE_KEY (plain values), SUPABASE_NIGHTLY_KEY (vault placeholder,
# substituted at egress — it goes in the Authorization header and nowhere else).
set -euo pipefail
DEST="${NIGHTLY_DEST:-/workspace/cycling}"
: "${SUPABASE_URL:?}" "${SUPABASE_PUBLISHABLE_KEY:?}" "${SUPABASE_NIGHTLY_KEY:?}"
auth=(-H "apikey: ${SUPABASE_PUBLISHABLE_KEY}" -H "Authorization: Bearer ${SUPABASE_NIGHTLY_KEY}")
mkdir -p "$DEST/.release"
row=$(curl -fsS "${auth[@]}" \
  "$SUPABASE_URL/rest/v1/releases?approved=eq.true&order=created_at.desc,tag.desc&limit=1&select=tag,git_sha,manifest")
tag=$(printf '%s' "$row" | python3 -c 'import json,sys; r=json.load(sys.stdin); print(r[0]["tag"] if r else "")')
if [ -z "$tag" ]; then
  echo "stage0: no approved release in the releases table — stop and report (exit 3)" >&2
  exit 3
fi
zip=$(printf '%s' "$row" | python3 -c '
import json, sys
r = json.load(sys.stdin)[0]
m = r.get("manifest") or {}
print((m.get("git") or {}).get("code_zip") or "code-%s.zip" % r["git_sha"])')
echo "stage0: release $tag, code $zip"
curl -fsS "${auth[@]}" -o "$DEST/.release/$zip" \
  "$SUPABASE_URL/storage/v1/object/authenticated/releases/$tag/$zip"
python3 - "$DEST/.release/$zip" "$DEST" <<'PY'
import sys, zipfile
zipfile.ZipFile(sys.argv[1]).extractall(sys.argv[2])
PY
export PATH="$HOME/.local/bin:$PATH"
command -v uv >/dev/null 2>&1 || python3 -m pip install --quiet --user uv
cd "$DEST"
uv sync --quiet
exec uv run python -m cycling_project.nightly.bootstrap --dest "$DEST" "$@"
