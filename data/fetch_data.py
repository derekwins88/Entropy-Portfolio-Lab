import os
import pandas as pd

HERE = os.path.dirname(__file__)
EXPECTED = ["datetime", "open", "high", "low", "close", "volume"]

def validate_csv(path: str):
    if not os.path.exists(path):
        raise FileNotFoundError(f"CSV missing: {path}")
    df = pd.read_csv(path, nrows=2)
    missing = [c for c in EXPECTED if c not in df.columns]
    if missing:
        raise ValueError(f"{os.path.basename(path)} missing columns: {missing}")

def main():
    for f in sorted(os.listdir(HERE)):
        if f.endswith(".csv"):
            try:
                validate_csv(os.path.join(HERE, f))
                print(f"✅ {f} OK")
            except Exception as e:
                print(f"❌ {f}: {e}")
                raise

if __name__ == "__main__":
    main()
