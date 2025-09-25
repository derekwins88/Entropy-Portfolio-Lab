# C# Components

This directory holds the NinjaTrader / C# implementations that align with the Python backtesting toolkit. Drop in files like `MultiAssetPortfolioSizer.cs` and `AethelredAegis.cs` when you port the execution layer.

## AlphaBreakoutEntropy_v1_1

- `AlphaBreakoutEntropy_v1_1.cs` is the public entry point that wires the entropy breakout logic for NinjaTrader.
- Keep any proprietary helpers (e.g., `AlphaBreakoutEntropyPrivateLogic.cs`) out of the repository or encrypted. The build tooling intentionally skips files matching `*PrivateLogic.cs` so private code never lands in public releases.

## Building

Use the repo-level helper to compile the public C# components into a DLL:

```bash
./build.sh
```

The script looks for `mcs` (Mono) and excludes private helpers by default. If you need to test with your private logic locally, copy the helper next to this directory before running the build or compile from within NinjaTrader/Visual Studio.
