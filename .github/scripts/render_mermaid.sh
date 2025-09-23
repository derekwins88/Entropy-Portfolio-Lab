#!/usr/bin/env bash
set -euo pipefail
IN="${1:-docs/system_diagram.md}"
OUTDIR="docs-diagrams/out"
CFG="docs-diagrams/puppeteer.json"
mkdir -p "$OUTDIR"
MERMAID_CLI=(npx -y @mermaid-js/mermaid-cli@10.9.0)

rm -f "$OUTDIR"/block-*.mmd

awk -v outdir="$OUTDIR" '
  BEGIN { block = -1; in_block = 0 }
  /^```mermaid/ { block += 1; in_block = 1; next }
  /^```/ {
    if (in_block) {
      file = sprintf("%s/block-%02d.mmd", outdir, block)
      close(file)
    }
    in_block = 0
    next
  }
  {
    if (in_block) {
      file = sprintf("%s/block-%02d.mmd", outdir, block)
      print >> file
    }
  }
' "$IN"

shopt -s nullglob
i=0
for f in "$OUTDIR"/block-*.mmd; do
  png="${f%.mmd}.png"
  "${MERMAID_CLI[@]}" -i "$f" -o "$png" --backgroundColor transparent --scale 1.5 --puppeteerConfigFile "$CFG"
  echo "Rendered $png"
  i=$((i+1))
done
echo "Done ($i diagrams)."
