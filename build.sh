#!/usr/bin/env bash
set -euo pipefail

# Simple helper to compile the public C# strategies/sizers into a NinjaTrader-ready DLL.
# Private logic files (e.g., AlphaBreakoutEntropyPrivateLogic.cs) are intentionally
# excluded from public builds so they can be stored outside the repo.

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CS_DIR="$ROOT_DIR/csharp"
OUT_DIR="$CS_DIR/bin"
DLL_NAME="EntropyPortfolioLab.dll"

mkdir -p "$OUT_DIR"

mapfile -d '' PUBLIC_SOURCES < <(find "$CS_DIR" -maxdepth 1 -name '*.cs' -not -name '*PrivateLogic.cs' -print0 | sort -z)

if [[ ${#PUBLIC_SOURCES[@]} -eq 0 ]]; then
  echo "No public C# sources found in $CS_DIR" >&2
  exit 1
fi

if command -v mcs >/dev/null 2>&1; then
  echo "Compiling public C# sources into $OUT_DIR/$DLL_NAME"
  mcs -target:library -out:"$OUT_DIR/$DLL_NAME" "${PUBLIC_SOURCES[@]}"
  echo "Build complete. Copy the DLL into your NinjaTrader bin/Custom folder as needed."
else
  echo "Mono C# compiler (mcs) not found. Install mono-devel or open the files in NinjaTrader/Visual Studio." >&2
  exit 1
fi
