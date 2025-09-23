import csv, random
from datetime import date, timedelta
random.seed(42)
rows = []
syms = ["SPY","QQQ"]
headers = ["DATE"] + [f"{s}_{f}" for s in syms for f in ("Open","High","Low","Close","Volume")]
price = {s: 100.0 + i*5 for i,s in enumerate(syms)}
start = date(2024, 1, 1)
for d in range(60):
    day = start + timedelta(days=d)
    row = [day.isoformat()]
    for s in syms:
        drift = (random.random()-0.5)*0.8
        price[s] = max(1.0, price[s] + drift)
        o = price[s]
        h = o + abs(drift)*0.7
        l = o - abs(drift)*0.7
        c = o + (random.random()-0.5)*0.3
        v = int(1e6 + random.random()*5e5)
        row += [round(o,2),round(h,2),round(l,2),round(c,2),v]
    rows.append(row)

with open("data/sample_multi_asset_data.csv","w",newline="") as f:
    w=csv.writer(f); w.writerow(headers); w.writerows(rows)
print("Wrote data/sample_multi_asset_data.csv")
