#!/usr/bin/env bash
set -euo pipefail
IN="${1:-docs/system_diagram.md}"
OUTDIR="docs-diagrams/out"
CFG="docs-diagrams/puppeteer.json"
mkdir -p "$OUTDIR"
npm -g i @mermaid-js/mermaid-cli@10.9.0 >/dev/null 2>&1 || true

awk '/^```mermaid/{flag=1;next} /^```/{flag=0} flag' "$IN" \
| awk 'BEGIN{b=0} /^ *$/{next}{print} END{}' \
| csplit -s -f "$OUTDIR/block-" -b "%02d.mmd" - "/^$/"+1 "{*}"

shopt -s nullglob
i=0
for f in "$OUTDIR"/block-*.mmd; do
  png="${f%.mmd}.png"
  mmdc -i "$f" -o "$png" -p "$CFG" --backgroundColor transparent
  echo "Rendered $png"
  i=$((i+1))
done
echo "Done ($i diagrams)."
