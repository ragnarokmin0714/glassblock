#!/usr/bin/env bash
# Refresh the generated rule files from the upstream filter lists.
# Safe to run from anywhere (including cron): downloads, converts and generates
# into a temp dir first, and only replaces the shipped files if every step
# succeeded, so a network failure can never leave you with corrupt rules.
set -euo pipefail
cd "$(dirname "$0")/.."

tmp=$(mktemp -d)
trap 'rm -rf "$tmp"' EXIT

echo "Downloading filter lists..."
curl -sSL --fail --max-time 120 -o "$tmp/easylist.txt"      https://easylist.to/easylist/easylist.txt
curl -sSL --fail --max-time 120 -o "$tmp/easyprivacy.txt"   https://easylist.to/easylist/easyprivacy.txt
curl -sSL --fail --max-time 120 -o "$tmp/easylistchina.txt" https://easylist-downloads.adblockplus.org/easylistchina.txt

python3 tools/convert.py "$tmp/easylist.txt"      "$tmp/rules_easylist.json"
python3 tools/convert.py "$tmp/easyprivacy.txt"   "$tmp/rules_easyprivacy.json"
python3 tools/convert.py "$tmp/easylistchina.txt" "$tmp/rules_easylistchina.json"

python3 tools/gen-cosmetic.py "$tmp/easylist.txt" "$tmp/easylistchina.txt" > "$tmp/hide-generic.css"

# Sanity-check the output before it is allowed anywhere near the extension.
# --fail catches an HTTP error and curl catches a truncated transfer, but a
# server that answers 200 with a maintenance page would sail through both and
# convert cleanly into almost nothing. The floors below are deliberately far
# under the real counts: they catch a gutted list, not normal upstream churn.
python3 - "$tmp" <<'EOF'
import json, re, sys

tmp = sys.argv[1]
FLOORS = {
    "rules_easylist.json": 1000,
    "rules_easylistchina.json": 1000,
    "rules_easyprivacy.json": 1000,
}
COSMETIC_FLOOR = 5000

total = len(json.load(open("rules_custom.json")))
for name, floor in FLOORS.items():
    n = len(json.load(open(f"{tmp}/{name}")))
    if n < floor:
        sys.exit(f"ABORTED: {name} converted to only {n} rules (floor {floor}) "
                 f"- upstream list looks truncated or replaced")
    total += n
    print(f"  {name}: {n} rules")

css = open(f"{tmp}/hide-generic.css", encoding="utf-8").read()
selectors = css.count(",\n") + css.count("{display:none!important}")
if selectors < COSMETIC_FLOOR:
    sys.exit(f"ABORTED: hide-generic.css has only {selectors} selectors "
             f"(floor {COSMETIC_FLOOR})")
print(f"  hide-generic.css: {selectors} selectors")

# Chrome guarantees only 30,000 static rules across all enabled rulesets.
if total > 30000:
    sys.exit(f"ABORTED: {total} total rules exceeds Chrome's guaranteed 30,000 limit")
print(f"Total rules: {total} / 30000")
EOF

mv "$tmp/rules_easylist.json"      rules_easylist.json
mv "$tmp/rules_easyprivacy.json"   rules_easyprivacy.json
mv "$tmp/rules_easylistchina.json" rules_easylistchina.json
mv "$tmp/hide-generic.css"         hide-generic.css

echo "Done. Reload the extension at chrome://extensions (click the ↻ icon) to apply."
