#!/usr/bin/env bash
set -euo pipefail

IN="${1:-docs/system_diagram.md}"
OUTDIR="docs-diagrams/out"
CFG=".github/scripts/puppeteer.json"   # your existing no-sandbox config
mkdir -p "$OUTDIR"

# 1) Extract the first ```mermaid fenced block cleanly
tmp="$(mktemp -t mmd.XXXX).mmd"
awk '
  BEGIN{f=0}
  /^```[[:space:]]*mermaid[[:space:]]*$/ {f=1; next}
  /^```[[:space:]]*$/ && f==1 {f=0; exit}
  f==1 {print}
' "$IN" > "$tmp"

# 2) Normalize line endings and trim BOM/zero-width chars
sed -i 's/\r$//' "$tmp"
LC_ALL=C tr -d "\xEF\xBB\xBF" < "$tmp" > "$tmp.clean" && mv "$tmp.clean" "$tmp"

# 3) Ensure first non-comment is `flowchart` (Mermaid v11 sometimes mis-detects)
first=$(grep -v '^[[:space:]]*$' "$tmp" | grep -v '^%%' | head -n1 || true)
case "$first" in
  flowchart*|graph* ) : ;;   # ok
  * ) echo "warn: first non-comment line is not a flowchart: '$first'";;
esac

# 4) Pin mermaid-cli to a stable version
npx --yes @mermaid-js/mermaid-cli@10.9.0 -V >/dev/null

# 5) Render (PNG + SVG)
base="${OUTDIR}/system_diagram"
npx --yes @mermaid-js/mermaid-cli@10.9.0 \
  -i "$tmp" -o "${base}.png" \
  -p "$CFG" --quiet --backgroundColor transparent
npx --yes @mermaid-js/mermaid-cli@10.9.0 \
  -i "$tmp" -o "${base}.svg" \
  -p "$CFG" --quiet --backgroundColor transparent

echo "Rendered ${base}.{png,svg}"
