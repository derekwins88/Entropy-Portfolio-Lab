#!/usr/bin/env python
"""
Generate a tiny, deterministic multi-asset sample CSV for docs/CI.
Writes: data/sample_multi_asset_data.csv
"""
from __future__ import annotations

import csv
import datetime as dt
import os
import random
from typing import List

SYMS: List[str] = [s.strip() for s in os.environ.get("SAMPLE_SYMS", "SPY,QQQ,TLT").split(",") if s.strip()]
N = int(os.environ.get("SAMPLE_DAYS", "40"))
SEED = int(os.environ.get("SAMPLE_SEED", "42"))
OUT = os.environ.get("SAMPLE_OUT", "data/sample_multi_asset_data.csv")


def main() -> None:
    random.seed(SEED)
    start = dt.date(2024, 1, 2)
    cols = ["datetime"] + [f"{sym}_Close" for sym in SYMS]
    out_dir = os.path.dirname(OUT)
    if out_dir:
        os.makedirs(out_dir, exist_ok=True)

    with open(OUT, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(cols)
        prices = {sym: 100.0 + 5.0 * idx for idx, sym in enumerate(SYMS)}
        sym_offsets = {sym: sum(ord(ch) for ch in sym) for sym in SYMS}

        for i in range(N):
            day = start + dt.timedelta(days=i)
            row = [day.isoformat() + "T00:00:00Z"]
            for sym in SYMS:
                rng = random.Random(SEED + i * 17 + sym_offsets[sym])
                prices[sym] *= 1.0 + rng.uniform(-0.01, 0.01)
                row.append(round(prices[sym], 4))
            writer.writerow(row)

    print(f"wrote {OUT} with {N} rows and syms {SYMS}")


if __name__ == "__main__":
    main()
