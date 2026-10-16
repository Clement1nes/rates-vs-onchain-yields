"""Rates vs on-chain yield: clean, analyse, chart, and verify every figure quoted in the draft.

Run:  python analysis.py            (uses data/raw as pulled)
      python analysis.py --fetch    (re-pulls all raw data first)

Outputs: data/clean/*.parquet, output/results.json, output/tables/*.csv, charts/*.png,
and a figure check against report/draft.md printed at the end.
"""
import json
import re
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats

import charts

ROOT = Path(__file__).parent
RAW = ROOT / "data" / "raw"
CLEAN = ROOT / "data" / "clean"
OUT = ROOT / "output"
for p in (CLEAN, OUT, OUT / "tables"):
    p.mkdir(parents=True, exist_ok=True)

START = "2023-01-01"
H = 30            # forward / backward window in days
MIN_POOL_TVL = 10e6  # ignore lending-pool days with under $10m idle liquidity (Aave v3 launch weeks)
PRICE_CARRY_DAYS = 10
TEST_START = "2024-01-01"  # growth tests start after the Aave v2->v3 migration and early token launches


def rj(name):
    return json.loads((RAW / name).read_text(encoding="utf8"))


# =============================================================== CLEAN
def clean_rates():
    out = {}
    for sid in ["DFF", "DTB3", "DGS2", "DFEDTARU"]:
        df = pd.read_csv(RAW / f"fred_{sid}.csv")
        df.columns = ["date", sid]
        df["date"] = pd.to_datetime(df["date"])
        df[sid] = pd.to_numeric(df[sid], errors="coerce")  # FRED marks holidays with "."
        out[sid] = df.set_index("date")[sid].dropna()
    r = pd.DataFrame(out)
    r = r[r.index >= START]
    # DTB3 is quoted on a discount basis. Convert to bond-equivalent yield so it is comparable to APYs.
    d = r["DTB3"] / 100
    r["TBILL_BEY"] = 100 * 365 * d / (360 - 91 * d)
    return r


def clean_fomc():
    f = pd.DataFrame(rj("fomc_decisions.json"))
    f["date"] = pd.to_datetime(f["date"], format="%Y%m%d")
    f["change_bp"] = (f["upper"].diff() * 100).round()
    first = f.index[0]
    f.loc[first, "change_bp"] = np.nan
    return f


def clean_stablecoins():
    j = rj("stablecoins_all.json")
    s = pd.Series({pd.to_datetime(int(x["date"]), unit="s"): x["totalCirculatingUSD"].get("peggedUSD", np.nan)
                   for x in j}).sort_index()
    b = rj("buidl_stablecoin_173.json")["tokens"]
    buidl = pd.Series({pd.to_datetime(int(x["date"]), unit="s"): x["circulating"].get("peggedUSD", np.nan)
                       for x in b}).sort_index()
    buidl = buidl.groupby(buidl.index.normalize()).last()
    s = s.groupby(s.index.normalize()).last()
    df = pd.DataFrame({"stablecoin_total_usd": s, "buidl_usd": buidl})
    df["buidl_usd"] = df["buidl_usd"].where(df.index >= buidl.index.min(), 0.0)
    # BUIDL is listed as a USD 'stablecoin' by DeFiLlama; remove it so the two series do not overlap
    df["stablecoin_ex_buidl_usd"] = df["stablecoin_total_usd"] - df["buidl_usd"]
    return df[df.index >= START], buidl


def clean_treasuries(buidl):
    oc = rj("onchain_supply.json")
    meta = oc["_meta"]
    names = list(meta)
    rows = {}
    for day, v in oc.items():
        if day.startswith("_"):
            continue
        rows[pd.Timestamp(day)] = v["supply"]
    sup = pd.DataFrame.from_dict(rows, orient="index", columns=names).sort_index().astype(float)
    for n in names:
        sup[n] = sup[n] / 10 ** meta[n]["decimals"]
    # USYC on BNB Chain (from 2025): add to the Ethereum units of the same fund
    ob = rj("onchain_supply_bsc.json")
    bsc = pd.Series({pd.Timestamp(d): v["supply"][0] for d, v in ob.items() if not d.startswith("_")},
                    dtype=float).sort_index() / 10 ** ob["_meta"]["USYC (Hashnote/Circle)"]["decimals"]
    usyc = "USYC (Hashnote/Circle)"
    bsc = bsc.reindex(sup.index)
    bsc[sup.index < bsc.first_valid_index()] = 0.0
    sup[usyc] = sup[usyc].fillna(0).where(sup[usyc].notna() | bsc.notna()) + bsc.fillna(0)
    prices = rj("treasury_token_prices.json")
    vals = {}
    for n, pts in prices.items():
        p = pd.Series({pd.to_datetime(x["timestamp"], unit="s"): x["price"] for x in pts}).sort_index()
        p = p.groupby(p.index.normalize()).last()
        # NAV tokens accrue ~0.01%/day. Where DeFiLlama skips a day, use its last published price for up to
        # PRICE_CARRY_DAYS days; longer gaps stay blank. No prices are interpolated or assumed.
        p = p.reindex(pd.date_range(p.index.min(), sup.index.max())).ffill(limit=PRICE_CARRY_DAYS)
        units = sup[n]
        v = units * p.reindex(units.index)
        v[units.isna()] = 0.0  # contract not yet deployed: zero supply, a fact not an estimate
        v[units == 0] = 0.0
        vals[n] = v
    tt = pd.DataFrame(vals).astype(float)
    tt["BUIDL (BlackRock, all chains)"] = buidl.reindex(tt.index)
    tt.loc[tt.index < buidl.index.min(), "BUIDL (BlackRock, all chains)"] = 0.0
    tt = tt[tt.index >= START]
    aave = sup[[c for c in names if "Eth" in c]].copy()
    aave["aave_borrow_usd"] = aave["variableDebtEthUSDC"].fillna(0) + aave["variableDebtEthUSDT"].fillna(0)
    aave["aave_supply_usd"] = aave["aEthUSDC"].fillna(0) + aave["aEthUSDT"].fillna(0)
    aave.loc[aave["aEthUSDC"].isna() & aave["aEthUSDT"].isna(), ["aave_borrow_usd", "aave_supply_usd"]] = np.nan
    return tt, aave[aave.index >= START]


def clean_yields():
    out = {}
    for k in ["aave_v3_usdc_eth", "aave_v3_usdt_eth", "morpho_steakusdc_eth", "ethena_susde"]:
        d = pd.DataFrame(rj(f"yield_{k}.json")["data"])
        d["date"] = pd.to_datetime(d["timestamp"]).dt.tz_localize(None).dt.normalize()
        d = d.groupby("date").last()
        # Aave v3 Ethereum launched 27 Jan 2023: drop launch-period days with < $10m idle liquidity
        launch = (d.index < "2023-06-01") & (d["tvlUsd"] < MIN_POOL_TVL)
        apy = d["apy"].where(~launch) if k.startswith("aave") else d["apy"]
        out[f"{k}_apy"] = apy
        out[f"{k}_tvl"] = d["tvlUsd"]
    y = pd.DataFrame(out)
    return y[y.index >= START]


def clean_funding():
    out = {}
    for sym in ["BTCUSDT", "ETHUSDT"]:
        d = pd.DataFrame(rj(f"binance_funding_{sym}.json"))
        d["t"] = pd.to_datetime(d["fundingTime"], unit="ms")
        d["r"] = d["fundingRate"].astype(float)
        daily = d.groupby(d["t"].dt.normalize())["r"].agg(["sum", "count"])
        # annualised: the sum of a day's funding prints x 365, in percent
        out[sym[:3] + "_funding_ann"] = (daily["sum"] * 365 * 100).where(daily["count"] >= 3)
        out[sym[:3] + "_prints"] = daily["count"]
    f = pd.DataFrame(out)
    return f[f.index >= START]


def build_panel():
    rates = clean_rates()
    fomc = clean_fomc()
    sc, buidl = clean_stablecoins()
    tt, aave = clean_treasuries(buidl)
    y = clean_yields()
    fund = clean_funding()
    idx = pd.date_range(START, min(tt.index.max(), sc.index.max(), fund.index.max()), freq="D")
    # Rates: FRED publishes business days only. Weekends/holidays carry the last published rate (max 4 days).
    rates_d = rates.reindex(idx).ffill(limit=4)
    P = pd.concat([rates_d, sc.reindex(idx), y.reindex(idx), fund.reindex(idx),
                   aave[["aave_borrow_usd", "aave_supply_usd"]].reindex(idx)], axis=1)
    # level: sum of products that have a published price that day (see SOURCES.md for unpriced spells)
    P["tt_total_usd"] = tt.reindex(idx).sum(axis=1, min_count=1)
    P["tt_products_priced"] = tt.reindex(idx).notna().sum(axis=1)
    for name, df in [("rates", rates), ("fomc", fomc.set_index("date")), ("stablecoins", sc),
                     ("tokenized_treasuries", tt), ("aave_onchain", aave), ("yields", y),
                     ("funding", fund), ("panel", P)]:
        df.to_parquet(CLEAN / f"{name}.parquet")
    return P, tt, fomc


def rates_published_days(P):
    """Days on which FRED actually published DTB3 (excludes carried-forward weekend/holiday values)."""
    return clean_rates()["DTB3"].dropna().index


MONTH_NO = {m: i for i, m in enumerate(["January", "February", "March", "April", "May", "June", "July", "August",
                                         "September", "October", "November", "December"], 1)}


def next_fomc_decision(after):
    """First scheduled FOMC decision day after `after`, from the federalreserve.gov calendar page."""
    h = (RAW / "fomccalendars.htm").read_text(encoding="utf8")
    out = []
    for ym in re.finditer(r"(\d{4}) FOMC Meetings", h):
        year = int(ym.group(1))
        seg = h[ym.end():ym.end() + 60000].split("FOMC Meetings")[0]
        for mon, days in re.findall(r"fomc-meeting__month[^>]*><strong>([^<]+)</strong>.*?"
                                    r"fomc-meeting__date[^>]*>([^<]+)<", seg, re.S):
            end_mon = mon.split("/")[-1].strip()
            end_mon = next(m for m in MONTH_NO if m.startswith(end_mon[:3]))
            end_day = int(re.findall(r"\d+", days)[-1])
            out.append(pd.Timestamp(year, MONTH_NO[end_mon], end_day))
    return min(d for d in out if d > after)


# =============================================================== ANALYSE
def chain_linked_growth(tt, h, forward=True):
    """Log growth over h days using only products valued on both dates (entry of a product is not growth)."""
    a = tt
    b = tt.shift(-h) if forward else tt.shift(h)
    ok = a.notna() & b.notna()
    num = b.where(ok).sum(axis=1)
    den = a.where(ok).sum(axis=1)
    den = den.where(den > 0)
    g = np.log(num / den)
    return g if forward else -g


def log_growth(s, h, forward=True):
    return np.log(s.shift(-h) / s) if forward else np.log(s / s.shift(h))


def spearman(x, y):
    d = pd.concat([x, y], axis=1).dropna()
    if len(d) < 8:
        return {"rho": np.nan, "p": np.nan, "n": len(d)}
    r, p = stats.spearmanr(d.iloc[:, 0], d.iloc[:, 1])
    return {"rho": float(r), "p": float(p), "n": int(len(d))}


def analyse(P, tt, fomc):
    R = {}
    # --- spreads (7-day averages to remove day-to-day noise), percentage points
    P["lend_apy"] = P[["aave_v3_usdc_eth_apy", "aave_v3_usdt_eth_apy"]].mean(axis=1, skipna=False)
    P["lend_apy_7d"] = P["lend_apy"].rolling(7, min_periods=5).mean()
    P["morpho_apy_7d"] = P["morpho_steakusdc_eth_apy"].rolling(7, min_periods=5).mean()
    P["susde_apy_7d"] = P["ethena_susde_apy"].rolling(7, min_periods=5).mean()
    P["funding_ann"] = P[["BTC_funding_ann", "ETH_funding_ann"]].mean(axis=1, skipna=False)
    P["funding_ann_7d"] = P["funding_ann"].rolling(7, min_periods=5).mean()
    P["funding_ann_30d"] = P["funding_ann"].rolling(30, min_periods=25).mean()
    tb = P["TBILL_BEY"]
    P["spread_lend"] = P["lend_apy_7d"] - tb
    P["spread_morpho"] = P["morpho_apy_7d"] - tb
    P["spread_susde"] = P["susde_apy_7d"] - tb
    P["spread_funding"] = P["funding_ann_7d"] - tb

    # --- growth measures
    P["tt_fwd"] = chain_linked_growth(tt.reindex(P.index), H, True)
    P["tt_back"] = chain_linked_growth(tt.reindex(P.index), H, False)
    P["borrow_fwd"] = log_growth(P["aave_borrow_usd"], H)
    P["borrow_back"] = log_growth(P["aave_borrow_usd"], H, False)
    P["susde_fwd"] = log_growth(P["ethena_susde_tvl"], H)
    P["sc_fwd"] = log_growth(P["stablecoin_ex_buidl_usd"], H)
    P["sc_back"] = log_growth(P["stablecoin_ex_buidl_usd"], H, False)
    P["sc_90d_ann"] = 100 * (np.exp(log_growth(P["stablecoin_ex_buidl_usd"], 90, False) * 365 / 90) - 1)
    P["rotation_lend"] = P["borrow_fwd"] - P["tt_fwd"]     # >0: Aave stablecoin borrowing outgrows tokenized T-bills
    P["rotation_basis"] = P["susde_fwd"] - P["tt_fwd"]     # >0: sUSDe outgrows tokenized T-bills
    # robustness: BUIDL alone (one product, all chains, one consistent source)
    P["buidl_usd"] = tt["BUIDL (BlackRock, all chains)"].reindex(P.index)
    P["buidl_fwd"] = log_growth(P["buidl_usd"].where(P["buidl_usd"] > 0), H)
    P["rotation_lend_buidl"] = P["borrow_fwd"] - P["buidl_fwd"]
    P.to_parquet(CLEAN / "panel_analysis.parquet")

    last = P.dropna(subset=["spread_lend", "TBILL_BEY", "tt_total_usd"]).index.max()
    R["last_date"] = last.strftime("%d %B %Y").lstrip("0")
    R["last_ts"] = last.strftime("%Y-%m-%d")
    R["test_start"] = TEST_START
    R["test_window_label"] = f"{pd.Timestamp(TEST_START):%B %Y} to {last:%B %Y}"
    R["dff_now"] = P.at[last, "DFF"]
    R["tbill_now"] = P.at[last, "TBILL_BEY"]
    R["dgs2_now"] = P.at[last, "DGS2"]
    R["lend_now"] = P.at[last, "lend_apy_7d"]
    R["morpho_now"] = P.at[last, "morpho_apy_7d"]
    R["susde_now"] = P.at[last, "susde_apy_7d"]
    R["funding30_now"] = P.at[last, "funding_ann_30d"]
    R["spread_lend_now"] = P.at[last, "spread_lend"]
    R["spread_susde_now"] = P.at[last, "spread_susde"]
    R["spread_funding_now"] = P.at[last, "funding_ann_30d"] - P.at[last, "TBILL_BEY"]

    # --- FOMC
    cuts = fomc[fomc["decision"] == "cut"].copy()
    R["n_meetings"] = int(len(fomc))
    R["n_cuts"] = int(len(cuts))
    R["cuts_total_bp"] = float(cuts["change_bp"].sum())
    R["first_cut"] = cuts["date"].min().strftime("%d %B %Y").lstrip("0")
    R["last_cut"] = cuts["date"].max().strftime("%d %B %Y").lstrip("0")
    R["peak_upper"] = float(fomc["upper"].max())
    R["upper_now"] = float(fomc["upper"].iloc[-1])
    R["lower_now"] = float(fomc["lower"].iloc[-1])
    # cross-check statement parse against FRED target upper bound
    tu = P["DFEDTARU"]
    mism = [d.strftime("%Y-%m-%d") for d, u in zip(fomc["date"], fomc["upper"])
            if not np.isclose(tu.loc[d + pd.Timedelta(days=1):].dropna().iloc[0], u)]
    R["fomc_parse_mismatches"] = mism
    fc = cuts["date"].min()
    R["tbill_at_first_cut"] = P.loc[fc - pd.Timedelta(days=1), "TBILL_BEY"]
    R["tbill_change_since_first_cut_bp"] = (R["tbill_now"] - R["tbill_at_first_cut"]) * 100

    # --- levels
    tot = P["tt_total_usd"]
    first_valid = tot.first_valid_index()
    R["tt_start_date"] = first_valid.strftime("%d %B %Y").lstrip("0")
    R["tt_start_bn"] = tot[first_valid] / 1e9
    R["tt_now_bn"] = tot[last] / 1e9
    R["tt_at_first_cut_bn"] = tot[fc - pd.Timedelta(days=1)] / 1e9
    R["tt_peak_bn"] = tot.max() / 1e9
    R["tt_peak_date"] = tot.idxmax().strftime("%B %Y")
    R["buidl_now_bn"] = tt.loc[last, "BUIDL (BlackRock, all chains)"] / 1e9
    R["tt_growth_since_first_cut_x"] = np.exp(chain_linked_growth(tt, (last - (fc - pd.Timedelta(days=1))).days)
                                               .loc[fc - pd.Timedelta(days=1)])
    # coverage cross-check against DeFiLlama all-chain treasury pools (recent history only)
    pools = rj("yield_treasury_pools_allchains.json")
    pdf = []
    for pid, v in pools.items():
        d = pd.DataFrame(v["data"])
        d["date"] = pd.to_datetime(d["timestamp"]).dt.tz_localize(None).dt.normalize()
        pdf.append(d.groupby("date")["tvlUsd"].last().rename(pid))
    allc = pd.concat(pdf, axis=1).sum(axis=1, min_count=1)
    allc_last = allc.loc[:last].dropna()
    R["allchain_pools_bn"] = allc_last.iloc[-1] / 1e9
    R["coverage_pct"] = 100 * tot[last] / allc_last.iloc[-1]
    R["n_allchain_pools"] = len(pools)
    R["allchain_start"] = allc.dropna().index.min().strftime("%B %Y")
    all_live = max(s.first_valid_index() for s in pdf)  # date by which every pool has history
    R["coverage_from"] = all_live.strftime("%d %B %Y").lstrip("0")
    cov = (tot / allc).loc[all_live:last].dropna()
    R["coverage_min_pct"], R["coverage_max_pct"] = 100 * float(cov.min()), 100 * float(cov.max())

    sc = P["stablecoin_ex_buidl_usd"]
    R["sc_now_bn"] = sc[last] / 1e9
    R["sc_start_bn"] = sc.dropna().iloc[0] / 1e9
    R["sc_at_first_cut_bn"] = sc[fc - pd.Timedelta(days=1)] / 1e9
    R["sc_growth_since_first_cut_pct"] = 100 * (R["sc_now_bn"] / R["sc_at_first_cut_bn"] - 1)
    R["aave_borrow_now_bn"] = P.at[last, "aave_borrow_usd"] / 1e9
    R["aave_borrow_at_first_cut_bn"] = P.at[fc - pd.Timedelta(days=1), "aave_borrow_usd"] / 1e9
    R["susde_tvl_now_bn"] = P.at[last, "ethena_susde_tvl"] / 1e9

    # --- events worth naming in the text
    hikes = fomc[fomc["decision"] == "hike"]
    R["last_hike"] = hikes["date"].max().strftime("%d %B %Y").lstrip("0")
    R["last_hike_bp"] = float(hikes.sort_values("date")["change_bp"].iloc[-1])
    sup = P["aave_supply_usd"].dropna()
    chg7 = sup / sup.shift(7) - 1
    worst = chg7.loc["2024-01-01":].idxmin()
    R["aave_run_end"] = worst.strftime("%d %B %Y").lstrip("0")
    R["aave_run_from_bn"] = sup.loc[worst - pd.Timedelta(days=7)] / 1e9
    R["aave_run_to_bn"] = sup.loc[worst] / 1e9
    R["aave_run_pct"] = 100 * chg7.loc[worst]
    st = P["ethena_susde_tvl"].dropna()
    R["susde_peak_bn"] = st.max() / 1e9
    R["susde_peak_date"] = st.idxmax().strftime("%B %Y")
    R["susde_from_peak_pct"] = 100 * (st.iloc[-1] / st.max() - 1)
    ob = rj("onchain_supply_bsc.json")
    oe = rj("onchain_supply.json")
    i = list(oe["_meta"]).index("USYC (Hashnote/Circle)")
    bsc_u = ob[last.strftime("%Y-%m-%d")]["supply"][0]
    eth_u = oe[last.strftime("%Y-%m-%d")]["supply"][i] or 0
    R["usyc_bsc_share_pct"] = 100 * bsc_u / (bsc_u + eth_u)
    R["usyc_now_bn"] = tt.loc[last, "USYC (Hashnote/Circle)"] / 1e9

    # --- front end of the curve from Treasury's own published rates
    bills = pd.concat([pd.read_csv(p) for p in sorted((RAW / "treasury").glob("daily_treasury_bill_rates_*.csv"))])
    bills["Date"] = pd.to_datetime(bills["Date"])
    bills = bills.set_index("Date").sort_index()
    curve = pd.concat([pd.read_csv(p) for p in sorted((RAW / "treasury").glob("daily_treasury_yield_curve_*.csv"))])
    curve["Date"] = pd.to_datetime(curve["Date"])
    curve = curve.set_index("Date").sort_index()
    # check the discount -> bond-equivalent conversion against Treasury's 13-week coupon equivalent
    ce = bills["13 WEEKS COUPON EQUIVALENT"]
    both = pd.concat([P["TBILL_BEY"], ce], axis=1, join="inner").dropna()
    both = both[both.index.isin(rates_published_days(P))]
    R["bey_check_days"] = int(len(both))
    R["bey_check_max_diff_bp"] = float((both.iloc[:, 0] - both.iloc[:, 1]).abs().max() * 100)
    cd = curve.loc[:last].index.max()
    R["curve_date"] = cd.strftime("%d %B %Y").lstrip("0")
    for col, k in [("1 Mo", "1m"), ("3 Mo", "3m"), ("6 Mo", "6m"), ("1 Yr", "1y"), ("2 Yr", "2y")]:
        R[f"curve_{k}"] = float(curve.at[cd, col])
    R["ce_13w_on_curve_date"] = float(ce.loc[:cd].iloc[-1])
    R["curve_1y_over_top_bp"] = (R["curve_1y"] - R["upper_now"]) * 100
    R["curve_2y_over_top_bp"] = (R["curve_2y"] - R["upper_now"]) * 100
    R["curve_1m_over_top_bp"] = (R["curve_1m"] - R["upper_now"]) * 100
    R["next_fomc_decision"] = next_fomc_decision(fomc["date"].max()).strftime("%d %B %Y").lstrip("0")

    # --- USYC and BNB Chain
    bsc_all = pd.Series({pd.Timestamp(d): v["supply"][0] for d, v in ob.items() if not d.startswith("_")},
                        dtype=float).sort_index()
    first_bsc = bsc_all[bsc_all > 0].index.min()
    R["usyc_bsc_first"] = first_bsc.strftime("%B %Y")
    R["usyc_before_bsc_bn"] = tt.loc[first_bsc - pd.Timedelta(days=1), "USYC (Hashnote/Circle)"] / 1e9
    R["usyc_share_of_tt_pct"] = 100 * tt.loc[last, "USYC (Hashnote/Circle)"] / P.at[last, "tt_total_usd"]

    # --- correlations on non-overlapping 30-day samples (every 30th day from the end)
    samp = P.loc[TEST_START:last].iloc[::-1].iloc[::H].iloc[::-1]
    C = {
        "tbill_vs_tt_back": spearman(samp["TBILL_BEY"], samp["tt_back"]),
        "tbill_vs_sc_back": spearman(samp["TBILL_BEY"], samp["sc_back"]),
        "spread_lend_vs_tt_fwd": spearman(samp["spread_lend"], samp["tt_fwd"]),
        "spread_lend_vs_borrow_fwd": spearman(samp["spread_lend"], samp["borrow_fwd"]),
        "spread_lend_vs_rotation": spearman(samp["spread_lend"], samp["rotation_lend"]),
        "spread_susde_vs_susde_fwd": spearman(samp["spread_susde"], samp["susde_fwd"]),
        "spread_susde_vs_rotation_basis": spearman(samp["spread_susde"], samp["rotation_basis"]),
        "spread_funding_vs_susde_fwd": spearman(samp["spread_funding"], samp["susde_fwd"]),
        "spread_lend_vs_sc_fwd": spearman(samp["spread_lend"], samp["sc_fwd"]),
        "spread_lend_vs_buidl_fwd": spearman(samp["spread_lend"], samp["buidl_fwd"]),
        "spread_lend_vs_rotation_buidl": spearman(samp["spread_lend"], samp["rotation_lend_buidl"]),
        "tbill_vs_borrow_back": spearman(samp["TBILL_BEY"], samp["borrow_back"]),
    }
    R["corr"] = C
    pd.DataFrame(C).T.to_csv(OUT / "tables" / "correlations_nonoverlapping.csv")
    # rolling 180-day correlation (daily, overlapping: descriptive only)
    P["roll_corr_spread_tt"] = P["spread_lend"].rolling(180, min_periods=150).corr(P["tt_back"])
    P["roll_corr_tbill_tt"] = P["TBILL_BEY"].rolling(180, min_periods=150).corr(P["tt_back"])
    rc = P["roll_corr_spread_tt"].dropna()
    R["rollcorr_min"], R["rollcorr_max"] = float(rc.min()), float(rc.max())
    R["rollcorr_share_neg_pct"] = 100 * float((rc < 0).mean())

    # --- FOMC cut event windows: 30 days before vs 30 days after
    ev = []
    for _, c in cuts.iterrows():
        d = c["date"]
        pre, post = d - pd.Timedelta(days=1), d + pd.Timedelta(days=H)
        if post > last:
            continue
        def g(col):
            return P.at[pre, col]
        ev.append({
            "date": d.strftime("%Y-%m-%d"), "cut_bp": c["change_bp"],
            "tt_pre_pct": 100 * (np.exp(P.at[pre, "tt_back"]) - 1),
            "tt_post_pct": 100 * (np.exp(P.at[d, "tt_fwd"]) - 1),
            "borrow_pre_pct": 100 * (np.exp(P.at[pre, "borrow_back"]) - 1),
            "borrow_post_pct": 100 * (np.exp(P.at[d, "borrow_fwd"]) - 1),
            "sc_pre_pct": 100 * (np.exp(P.at[pre, "sc_back"]) - 1),
            "sc_post_pct": 100 * (np.exp(P.at[d, "sc_fwd"]) - 1),
            "spread_pre": P.loc[pre - pd.Timedelta(days=H - 1):pre, "spread_lend"].mean(),
            "spread_post": P.loc[d:post, "spread_lend"].mean(),
            "susde_spread_pre": P.loc[pre - pd.Timedelta(days=H - 1):pre, "spread_susde"].mean(),
            "susde_spread_post": P.loc[d:post, "spread_susde"].mean(),
        })
    E = pd.DataFrame(ev)
    E.to_csv(OUT / "tables" / "fomc_cut_windows.csv", index=False)
    R["events"] = ev
    R["n_events"] = len(E)
    R["ev_tt_slower_after"] = int((E["tt_post_pct"] < E["tt_pre_pct"]).sum())
    R["ev_borrow_faster_after"] = int((E["borrow_post_pct"] > E["borrow_pre_pct"]).sum())
    R["ev_both"] = int(((E["tt_post_pct"] < E["tt_pre_pct"]) & (E["borrow_post_pct"] > E["borrow_pre_pct"])).sum())
    R["ev_tt_pre_median"] = float(E["tt_pre_pct"].median())
    R["ev_tt_post_median"] = float(E["tt_post_pct"].median())
    R["ev_borrow_pre_median"] = float(E["borrow_pre_pct"].median())
    R["ev_borrow_post_median"] = float(E["borrow_post_pct"].median())
    R["ev_spread_pre_median"] = float(E["spread_pre"].median())
    R["ev_spread_post_median"] = float(E["spread_post"].median())

    # --- spread buckets vs forward 30-day growth
    edges = [-np.inf, -1, 0, 1, 2, np.inf]
    labels = ["below -1", "-1 to 0", "0 to 1", "1 to 2", "above 2"]
    D = P.loc[TEST_START:last].dropna(subset=["spread_lend", "tt_fwd", "borrow_fwd"]).copy()
    D["bucket"] = pd.cut(D["spread_lend"], edges, labels=labels)
    B = D.groupby("bucket", observed=False).agg(
        days=("spread_lend", "size"),
        spread_mean=("spread_lend", "mean"),
        tt_fwd_pct=("tt_fwd", lambda s: 100 * (np.exp(s.mean()) - 1)),
        borrow_fwd_pct=("borrow_fwd", lambda s: 100 * (np.exp(s.mean()) - 1)),
        rotation_pp=("rotation_lend", lambda s: 100 * s.mean()),
        share_rotation_pos=("rotation_lend", lambda s: 100 * (s > 0).mean()),
    )
    B["independent_30d_windows"] = (B["days"] / H).round(1)
    B.to_csv(OUT / "tables" / "spread_buckets.csv")
    R["buckets"] = B.reset_index().to_dict(orient="records")
    R["n_bucket_days"] = int(len(D))
    R["bucket_sample_start"] = D.index.min().strftime("%B %Y")

    # threshold test: rotation above vs below each candidate spread on non-overlapping samples
    S = samp.dropna(subset=["spread_lend", "rotation_lend"])
    th = []
    for t in [-1.0, -0.5, 0.0, 0.5, 1.0, 1.5, 2.0]:
        a, b = S.loc[S["spread_lend"] > t, "rotation_lend"], S.loc[S["spread_lend"] <= t, "rotation_lend"]
        if len(a) >= 4 and len(b) >= 4:
            u = stats.mannwhitneyu(a, b, alternative="greater")
            th.append({"threshold_pp": t, "n_above": len(a), "n_below": len(b),
                       "rot_above_pp": 100 * a.median(), "rot_below_pp": 100 * b.median(), "p": float(u.pvalue)})
    T = pd.DataFrame(th)
    T.to_csv(OUT / "tables" / "threshold_tests.csv", index=False)
    R["thresholds"] = th
    best = T.loc[T["p"].idxmin()] if len(T) else None
    R["best_threshold"] = None if best is None else best.to_dict()
    R["n_samp"] = int(len(S))

    Sb = samp.dropna(subset=["spread_susde", "susde_fwd"])
    thb = []
    for t in [0.0, 2.0, 3.0, 4.0, 5.0, 7.5, 10.0]:
        a_, b_ = Sb.loc[Sb["spread_susde"] > t, "susde_fwd"], Sb.loc[Sb["spread_susde"] <= t, "susde_fwd"]
        if len(a_) >= 4 and len(b_) >= 4:
            u = stats.mannwhitneyu(a_, b_, alternative="greater")
            thb.append({"threshold_pp": t, "n_above": len(a_), "n_below": len(b_),
                        "susde_fwd_above_pct": 100 * (np.exp(a_.median()) - 1),
                        "susde_fwd_below_pct": 100 * (np.exp(b_.median()) - 1), "p": float(u.pvalue)})
    pd.DataFrame(thb).to_csv(OUT / "tables" / "threshold_tests_susde.csv", index=False)
    R["thresholds_susde"] = thb
    R["n_samp_susde"] = int(len(Sb))

    # sUSDe / basis buckets
    Db = P.loc[TEST_START:last].dropna(subset=["spread_susde", "susde_fwd", "tt_fwd"]).copy()
    Db["bucket"] = pd.cut(Db["spread_susde"], [-np.inf, 0, 2, 5, 10, np.inf],
                          labels=["below 0", "0 to 2", "2 to 5", "5 to 10", "above 10"])
    BB = Db.groupby("bucket", observed=False).agg(
        days=("spread_susde", "size"),
        susde_fwd_pct=("susde_fwd", lambda s: 100 * (np.exp(s.mean()) - 1)),
        tt_fwd_pct=("tt_fwd", lambda s: 100 * (np.exp(s.mean()) - 1)),
        rotation_pp=("rotation_basis", lambda s: 100 * s.mean()),
    )
    BB["independent_30d_windows"] = (BB["days"] / H).round(1)
    BB.to_csv(OUT / "tables" / "susde_spread_buckets.csv")
    R["basis_buckets"] = BB.reset_index().to_dict(orient="records")

    # share of time the lending spread was positive, by year
    yr = P.loc[:last, "spread_lend"].dropna()
    R["share_spread_pos_by_year"] = {str(k): 100 * float((v > 0).mean()) for k, v in yr.groupby(yr.index.year)}
    R["spread_lend_mean_by_year"] = {str(k): float(v.mean()) for k, v in yr.groupby(yr.index.year)}
    P.to_parquet(CLEAN / "panel_analysis.parquet")
    return P, R


# =============================================================== FIGURE CHECK
def figure_registry(R):
    """Every number the draft quotes, as formatted text, keyed to its computed value."""
    f1 = lambda x: f"{x:.1f}"
    f2 = lambda x: f"{x:.2f}"
    f0 = lambda x: f"{x:.0f}"
    C = R["corr"]
    reg = {
        "dff_now": f2(R["dff_now"]), "tbill_now": f2(R["tbill_now"]), "lend_now": f2(R["lend_now"]),
        "susde_now": f2(R["susde_now"]), "morpho_now": f2(R["morpho_now"]),
        "funding30_now": f1(R["funding30_now"]),
        "spread_lend_now": f2(R["spread_lend_now"]), "spread_susde_now": f2(R["spread_susde_now"]),
        "n_cuts": f0(R["n_cuts"]), "cuts_total_bp": f0(R["cuts_total_bp"]),
        "peak_upper": f2(R["peak_upper"]), "upper_now": f2(R["upper_now"]), "lower_now": f2(R["lower_now"]),
        "tbill_at_first_cut": f2(R["tbill_at_first_cut"]),
        "tt_start_bn": f2(R["tt_start_bn"]), "tt_now_bn": f1(R["tt_now_bn"]),
        "tt_at_first_cut_bn": f1(R["tt_at_first_cut_bn"]), "tt_peak_bn": f1(R["tt_peak_bn"]),
        "buidl_now_bn": f1(R["buidl_now_bn"]),
        "tt_growth_since_first_cut_x": f1(R["tt_growth_since_first_cut_x"]),
        "allchain_pools_bn": f1(R["allchain_pools_bn"]), "coverage_pct": f0(R["coverage_pct"]),
        "sc_now_bn": f0(R["sc_now_bn"]), "sc_at_first_cut_bn": f0(R["sc_at_first_cut_bn"]),
        "sc_growth_since_first_cut_pct": f0(R["sc_growth_since_first_cut_pct"]),
        "aave_borrow_now_bn": f1(R["aave_borrow_now_bn"]),
        "aave_borrow_at_first_cut_bn": f1(R["aave_borrow_at_first_cut_bn"]),
        "susde_tvl_now_bn": f1(R["susde_tvl_now_bn"]),
        "n_events": f0(R["n_events"]), "ev_tt_slower_after": f0(R["ev_tt_slower_after"]),
        "ev_borrow_faster_after": f0(R["ev_borrow_faster_after"]), "ev_both": f0(R["ev_both"]),
        "ev_tt_pre_median": f1(R["ev_tt_pre_median"]), "ev_tt_post_median": f1(R["ev_tt_post_median"]),
        "ev_borrow_pre_median": f1(R["ev_borrow_pre_median"]),
        "ev_borrow_post_median": f1(R["ev_borrow_post_median"]),
        "n_samp": f0(R["n_samp"]), "n_bucket_days": f0(R["n_bucket_days"]),
        "rollcorr_share_neg_pct": f0(R["rollcorr_share_neg_pct"]),
        "rollcorr_min": f2(R["rollcorr_min"]), "rollcorr_max": f2(R["rollcorr_max"]),
        "dgs2_now": f2(R["dgs2_now"]), "tbill_change_since_first_cut_bp": f0(R["tbill_change_since_first_cut_bp"]),
        "coverage_min_pct": f0(R["coverage_min_pct"]), "coverage_max_pct": f0(R["coverage_max_pct"]),
        "last_hike_bp": f0(R["last_hike_bp"]), "aave_run_from_bn": f1(R["aave_run_from_bn"]),
        "aave_run_to_bn": f1(R["aave_run_to_bn"]), "aave_run_pct": f0(R["aave_run_pct"]),
        "susde_peak_bn": f1(R["susde_peak_bn"]), "susde_from_peak_pct": f0(R["susde_from_peak_pct"]),
        "usyc_bsc_share_pct": f0(R["usyc_bsc_share_pct"]), "usyc_now_bn": f1(R["usyc_now_bn"]),
        "spread_funding_now": f2(R["spread_funding_now"]), "n_samp_susde": f0(R["n_samp_susde"]),
        "n_meetings": f0(R["n_meetings"]), "n_allchain_pools": f0(R["n_allchain_pools"]),
        "price_carry_days": f0(PRICE_CARRY_DAYS),
        # dates quoted in the text
        "date.first_cut": R["first_cut"], "date.last_cut": R["last_cut"], "date.last_hike": R["last_hike"],
        "date.aave_run_end": R["aave_run_end"], "date.susde_peak": R["susde_peak_date"],
        "date.tt_peak": R["tt_peak_date"], "date.last_date": R["last_date"],
        "date.coverage_from": pd.Timestamp(R["coverage_from"]).strftime("%B %Y"),
        "date.curve_date": R["curve_date"], "date.next_fomc_decision": R["next_fomc_decision"],
        "date.usyc_bsc_first": R["usyc_bsc_first"],
        "bey_check_days": f0(R["bey_check_days"]), "bey_check_max_diff_bp": f0(R["bey_check_max_diff_bp"]),
        "ce_13w_on_curve_date": f2(R["ce_13w_on_curve_date"]),
        "curve_1m": f2(R["curve_1m"]), "curve_3m": f2(R["curve_3m"]), "curve_6m": f2(R["curve_6m"]),
        "curve_1y": f2(R["curve_1y"]), "curve_2y": f2(R["curve_2y"]),
        "curve_1m_over_top_bp": f0(R["curve_1m_over_top_bp"]), "curve_1y_over_top_bp": f0(R["curve_1y_over_top_bp"]),
        "curve_2y_over_top_bp": f0(R["curve_2y_over_top_bp"]),
        "usyc_before_bsc_bn": f1(R["usyc_before_bsc_bn"]), "usyc_share_of_tt_pct": f0(R["usyc_share_of_tt_pct"]),
    }
    for t in R["thresholds_susde"]:
        k = f"threshold_susde[{t['threshold_pp']:+.1f}]"
        reg[k + ".above_pct"] = f1(t["susde_fwd_above_pct"])
        reg[k + ".below_pct"] = f1(t["susde_fwd_below_pct"])
        reg[k + ".p"] = f2(t["p"])
        reg[k + ".n_above"] = f0(t["n_above"])
        reg[k + ".n_below"] = f0(t["n_below"])
    for k, v in C.items():
        reg[f"corr.{k}.rho"] = f2(v["rho"])
        reg[f"corr.{k}.p"] = f2(v["p"])
        reg[f"corr.{k}.n"] = f0(v["n"])
    for b in R["buckets"]:
        L = b["bucket"]
        for c in ["tt_fwd_pct", "borrow_fwd_pct", "rotation_pp", "share_rotation_pos", "independent_30d_windows"]:
            reg[f"bucket[{L}].{c}"] = f1(b[c])
        reg[f"bucket[{L}].days"] = f0(b["days"])
    for b in R["basis_buckets"]:
        L = b["bucket"]
        for c in ["susde_fwd_pct", "tt_fwd_pct", "rotation_pp", "independent_30d_windows"]:
            reg[f"basis_bucket[{L}].{c}"] = f1(b[c])
        reg[f"basis_bucket[{L}].days"] = f0(b["days"])
    for t in R["thresholds"]:
        k = f"threshold[{t['threshold_pp']:+.1f}]"
        reg[k + ".rot_above_pp"] = f1(t["rot_above_pp"])
        reg[k + ".rot_below_pp"] = f1(t["rot_below_pp"])
        reg[k + ".p"] = f2(t["p"])
        reg[k + ".n_above"] = f0(t["n_above"])
        reg[k + ".n_below"] = f0(t["n_below"])
    for y, v in R["share_spread_pos_by_year"].items():
        reg[f"share_spread_pos[{y}]"] = f0(v)
    for y, v in R["spread_lend_mean_by_year"].items():
        reg[f"spread_lend_mean[{y}]"] = f2(v)
    for i, e in enumerate(R["events"]):
        reg[f"event[{e['date']}].tt_pre_pct"] = f1(e["tt_pre_pct"])
        reg[f"event[{e['date']}].tt_post_pct"] = f1(e["tt_post_pct"])
        reg[f"event[{e['date']}].borrow_pre_pct"] = f1(e["borrow_pre_pct"])
        reg[f"event[{e['date']}].borrow_post_pct"] = f1(e["borrow_post_pct"])
    return reg


# Numbers in the draft that are not data-derived figures (section labels, chart numbers, the window length,
# bucket edges and thresholds that are choices of method). Each must be justified here.
NON_FIGURES = {
    "30": "forward/backward window in days (method choice)",
    "7": "7-day smoothing window; 7 split points tested for sUSDe (method choices)",
    "180": "rolling-correlation window in days (method choice)",
    "1": "-1pp: lowest lending split point tested (method choice)",
    "2": "2pp split point; also '2-year', 'v2' (labels)",
    "3": "3pp split point; also '3m', 'v3' (labels)",
    "4": "4pp split point (method choice)",
    "8": "Binance funding interval, 8 hours (exchange parameter)",
    "365": "annualisation factor (method choice)",
    "13": "Treasury 13-week bill (instrument label)",
    "10": "price carry-forward limit in days (method choice, also mapped to price_carry_days)",
}
MONTHS = "January|February|March|April|May|June|July|August|September|October|November|December"


def figure_check(R):
    draft = ROOT / "report" / "draft.md"
    reg = figure_registry(R)
    (OUT / "figures.json").write_text(json.dumps(reg, indent=1))
    if not draft.exists():
        print("\n[figure check] report/draft.md not found; registry written to output/figures.json")
        return
    text = draft.read_text(encoding="utf8")
    # map draft numbers to registry keys via {{key}} tags in an HTML comment block at the end of the draft,
    # written as  <!-- figures: key=quoted, key=quoted -->
    tags = re.findall(r"<!--\s*figures:(.*?)-->", text, flags=re.S)
    pairs = []
    for block in tags:
        for item in re.split(r"[,\n]", block):
            if "=" in item:
                k, v = item.split("=", 1)
                pairs.append((k.strip(), v.strip()))
    body = re.sub(r"<!--.*?-->", "", text, flags=re.S)
    body_nums = re.sub(rf"\b\d{{1,2}} (?:{MONTHS}) \d{{4}}\b", " ", body)        # full dates
    body_nums = re.sub(rf"\b(?:{MONTHS}) \d{{4}}\b", " ", body_nums)               # month-year
    body_nums = re.sub(r"\b20(2[3-9])\b", " ", body_nums)                          # years
    body_nums = re.sub(r"(?i)chart \d", " ", body_nums)
    body_nums = re.sub(r"\]\([^)]*\)", "] ", body_nums)  # link and image targets (URLs, paths)
    quoted = re.findall(r"(?<![\w.])[-−+]?\d+(?:\.\d+)?", body_nums)
    quoted = [q.replace("−", "-") for q in quoted]

    print("\n" + "=" * 92)
    print("FIGURE CHECK: every number quoted in report/draft.md vs the value computed in this run")
    print("=" * 92)
    print(f"{'quoted':>10} | {'computed':>10} | status       | key")
    print("-" * 92)
    bad = 0
    used = set()
    flat = body.replace("−", "-")
    for k, q in pairs:
        comp = reg.get(k)
        qn = q.replace("−", "-")
        if comp is None:
            st = "NO KEY"
        elif comp == qn:
            st = "OK"
        elif comp.lstrip("-") == qn.lstrip("-"):
            st = "OK (abs)"  # the text gives the size and states the direction in words
        else:
            st = "MISMATCH"
        if not re.search(r"(?<![\d.])" + re.escape(qn.lstrip("-")) + r"(?![\d])", flat):
            st += " NOT IN TEXT"
        if st not in ("OK", "OK (abs)"):
            bad += 1
        used.add(qn.lstrip("-"))
        print(f"{q:>10} | {str(comp):>10} | {st:12} | {k}")
    orphans = sorted(set(q.lstrip("-+") for q in quoted) - used - set(NON_FIGURES))
    print("-" * 92)
    if orphans:
        print("Numbers in the text with no mapping to an analysis output: " + ", ".join(orphans))
        bad += len(orphans)
    else:
        print("Every number in the text maps to an analysis output or a stated method choice.")
    for q in sorted(set(x.lstrip("-+") for x in quoted) & set(NON_FIGURES)):
        print(f"  (method choice, not a data figure) {q}: {NON_FIGURES[q]}")
    print(f"\n{len(pairs)} mapped figures checked, {bad} problem(s).")


# =============================================================== MAIN
def main():
    if "--fetch" in sys.argv:
        import fetch_data
        fetch_data.main()
    P, tt, fomc = build_panel()
    P, R = analyse(P, tt, fomc)
    (OUT / "results.json").write_text(json.dumps(R, indent=1, default=lambda o: float(o) if np.isscalar(o) else str(o)))
    charts.make_all(P, tt, fomc, R)
    figure_check(R)


if __name__ == "__main__":
    main()
