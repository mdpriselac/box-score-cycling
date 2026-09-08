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
# Objects over 4 MiB are stored as <name>.part0000, .part0001, … (store.PART_SIZE); try the whole
# object first, then list the tag folder and concatenate the parts in order.
if ! curl -fsS "${auth[@]}" -o "$DEST/.release/$zip" \
     "$SUPABASE_URL/storage/v1/object/authenticated/releases/$tag/$zip" 2>/dev/null; then
  parts=$(curl -fsS "${auth[@]}" -H "Content-Type: application/json" \
    -d "{\"prefix\":\"$tag\",\"limit\":1000,\"sortBy\":{\"column\":\"name\",\"order\":\"asc\"}}" \
    "$SUPABASE_URL/storage/v1/object/list/releases" \
    | python3 -c "import json,sys; print(' '.join(sorted(o['name'] for o in json.load(sys.stdin) if o['name'].startswith('$zip.part'))))")
  if [ -z "$parts" ]; then
    echo "stage0: $zip is neither a whole object nor chunked under releases/$tag/ — stop and report (exit 4)" >&2
    exit 4
  fi
  : > "$DEST/.release/$zip"
  for part in $parts; do
    curl -fsS "${auth[@]}" "$SUPABASE_URL/storage/v1/object/authenticated/releases/$tag/$part" >> "$DEST/.release/$zip"
  done
  echo "stage0: $zip reassembled from $(echo $parts | wc -w | tr -d ' ') parts"
fi
python3 - "$DEST/.release/$zip" "$DEST" <<'PY'
import sys, zipfile
zipfile.ZipFile(sys.argv[1]).extractall(sys.argv[2])
PY
export PATH="$HOME/.local/bin:$PATH"
command -v uv >/dev/null 2>&1 || python3 -m pip install --quiet --user uv
cd "$DEST"
uv sync --quiet
exec uv run python -m cycling_project.nightly.bootstrap --dest "$DEST" "$@"
