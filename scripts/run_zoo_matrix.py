import yaml, pandas as pd
from pathlib import Path
from copy import deepcopy
from lab.run import load_prices
from lab.strategies.etrp import run_etrp

SCENARIOS = ["trend_up","trend_down","mean_revert","regime_switch","vol_spike","jumps","diversification_failure","black_swan"]

def main():
    with open("configs/etrp.yml","r") as f:
        base = yaml.safe_load(f)
    rows = []
    for scen in SCENARIOS:
        cfg = deepcopy(base)
        cfg["data"]["data_dir"] = f"stress_zoo:{scen}"
        px = load_prices(cfg)
        res = run_etrp(px, cfg)
        m = res["metrics"]
        rows.append({"scenario": scen, **{k: float(v) for k,v in m.items()}})
        print(f"[{scen}] CAGR={m['CAGR']:.2%} Vol={m['VolAnn']:.2%} Sharpe={m['Sharpe']:.2f} MaxDD={m['MaxDD']:.2%}")
    df = pd.DataFrame(rows).set_index("scenario")
    Path("runs").mkdir(exist_ok=True)
    df.to_csv("runs/zoo_summary.csv")
    print("\nSaved runs/zoo_summary.csv")

if __name__ == "__main__":
    main()
