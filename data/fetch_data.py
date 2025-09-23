import csv
import os
import pathlib
import re
import sys

HERE = pathlib.Path(__file__).parent
GENERIC = {"datetime", "open", "high", "low", "close", "volume"}
WIDE_COL = re.compile(r"^[A-Za-z0-9]+_(open|high|low|close|volume)$", re.I)


def validate_csv(path: os.PathLike):
    if not os.path.exists(path):
        raise FileNotFoundError(f"CSV missing: {path}")

    with open(path, newline="") as f:
        header = [h.strip() for h in next(csv.reader(f))]

    lower = [h.lower() for h in header]

    if "date" in lower and "datetime" not in lower:
        lower = ["datetime" if h == "date" else h for h in lower]

    if GENERIC.issubset(set(lower)):
        return

    if ("datetime" in lower or "date" in lower) and any(WIDE_COL.match(h) for h in lower):
        return

    missing = sorted(GENERIC - set(lower))
    raise ValueError(f"{os.path.basename(path)} missing columns: {missing}")


def main():
    for f in sorted(p.name for p in HERE.glob("*.csv")):
        try:
            validate_csv(os.path.join(HERE, f))
            print(f"✅ {f} OK")
        except Exception as e:
            print(f"❌ {f}: {e}")
            sys.exit(1)


if __name__ == "__main__":
    main()
