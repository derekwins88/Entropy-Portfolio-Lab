# CSV schemas

## Single-asset files (per symbol)
```
datetime,open,high,low,close,volume
2024-01-02T00:00:00Z,100.1,101.2,99.8,100.9,1234567
...
```

## Multi-asset “wide” sample
```
datetime,SPY_Close,QQQ_Close,TLT_Close
2024-01-02T00:00:00Z,470.12,390.45,97.10
...
```

Notes:
- Timestamps should be ISO8601 UTC.
- Column names are case-sensitive.
- The engine’s wide-loader looks for `*_Close` columns.
