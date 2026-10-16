# Rate cuts didn't move on-chain dollars. Funding did.

**Read the report: [report/report.pdf](report/report.pdf)** ([markdown version](report/draft.md))

Macro-to-crypto research note: what the 2024 to 2025 Fed cutting cycle did to tokenized Treasuries, yield-bearing stablecoins, DeFi lending and the basis trade, and at what spread capital moves. Data to 16 October 2026. Sources and pull dates: [data/SOURCES.md](data/SOURCES.md).

## Reproduce

```
pip install pandas pyarrow matplotlib scipy requests eth-abi markdown
python analysis.py --fetch   # pull raw data, clean, analyse, chart, check draft figures
python analysis.py           # same, using data/raw as already pulled
python make_report.py        # report/draft.md -> report/report.pdf (needs Chrome or Edge)
```

| Path | What |
|---|---|
| `fetch_data.py` | All pulls. Writes `data/raw/` and `data/SOURCES.md` (with `data/SOURCES_NOTES.md` appended) |
| `analysis.py` | Cleaning to `data/clean/*.parquet`, analysis, `output/results.json`, `output/tables/*.csv`, figure check |
| `charts.py` | The five charts in `charts/` |
| `report/draft.md` | The note. The comment block at the end maps each quoted number to its key in `output/figures.json` |

The on-chain supply pull caches by day in `data/raw/onchain_supply*.json`. Delete those files to force a full re-read.
