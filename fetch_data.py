"""Pull every raw series used in the piece and record where it came from.

Run:  python fetch_data.py
Writes raw responses to data/raw/ and a source log to data/SOURCES.md.
Nothing here estimates or fills values. If a source fails, the failure is logged.
"""
import datetime as dt
import html as html_lib
import json
import re
import time
from pathlib import Path

import requests
from eth_abi import decode, encode

ROOT = Path(__file__).parent
RAW = ROOT / "data" / "raw"
RAW.mkdir(parents=True, exist_ok=True)
START = dt.datetime(2023, 1, 1, tzinfo=dt.timezone.utc)
TODAY = dt.datetime.now(dt.timezone.utc)
PULL_DATE = TODAY.strftime("%Y-%m-%d")
UA = {}  # FRED stalls on custom user agents; use the library default

LOG = []  # (series, url, file, note)


def log(series, url, file, note=""):
    LOG.append((series, url, file, note))
    print(f"  ok  {series}  ->  {file}")


def get(url, params=None, tries=5, **kw):
    for i in range(tries):
        try:
            r = requests.get(url, params=params, headers=UA, timeout=90, **kw)
            if r.status_code == 429:
                time.sleep(5 * (i + 1))
                continue
            r.raise_for_status()
            return r
        except requests.RequestException:
            if i == tries - 1:
                raise
            time.sleep(3 * (i + 1))


def save_json(obj, name):
    p = RAW / name
    p.write_text(json.dumps(obj), encoding="utf8")
    return p.relative_to(ROOT).as_posix()


# ---------------------------------------------------------------- 1. FRED
def fetch_fred():
    for sid, desc in [("DFF", "Effective fed funds rate, daily"),
                      ("DTB3", "3-month T-bill, secondary market, discount basis, daily"),
                      ("DGS2", "2-year Treasury constant maturity, daily"),
                      ("DFEDTARU", "Fed funds target range upper bound (cross-check for FOMC decisions)")]:
        url = f"https://fred.stlouisfed.org/graph/fredgraph.csv?id={sid}"
        r = get(url)
        p = RAW / f"fred_{sid}.csv"
        p.write_bytes(r.content)
        log(f"FRED {sid}: {desc}", url, p.relative_to(ROOT).as_posix())


def fetch_treasury_curve():
    """US Treasury published daily bill rates and par yield curve (cross-check for FRED and front-end pricing)."""
    tdir = RAW / "treasury"
    tdir.mkdir(exist_ok=True)
    for typ, desc in [("daily_treasury_bill_rates", "Treasury daily bill rates (bank discount and coupon equivalent)"),
                      ("daily_treasury_yield_curve", "Treasury daily par yield curve (1m to 30y)")]:
        for year in range(TODAY.year - 1, TODAY.year + 1):
            url = (f"https://home.treasury.gov/resource-center/data-chart-center/interest-rates/daily-treasury-rates.csv/"
                   f"{year}/all?type={typ}&field_tdr_date_value={year}&page&_format=csv")
            p = tdir / f"{typ}_{year}.csv"
            p.write_bytes(get(url).content)
            log(f"{desc}, {year}", url, p.relative_to(ROOT).as_posix())


# ---------------------------------------------------------------- 6. FOMC
FRAC = {"": 0.0, "1/4": 0.25, "1/2": 0.5, "3/4": 0.75, "1/8": 0.125, "3/8": 0.375, "5/8": 0.625, "7/8": 0.875}


def _pct(s):
    m = re.fullmatch(r"(\d+)(?:-(\d/\d))?", s.strip())
    if m:
        return int(m.group(1)) + FRAC[m.group(2) or ""]
    m = re.fullmatch(r"(\d/\d)", s.strip())
    return FRAC[m.group(1)]


def fetch_fomc():
    url = "https://www.federalreserve.gov/monetarypolicy/fomccalendars.htm"
    html = get(url).text
    (RAW / "fomccalendars.htm").write_text(html, encoding="utf8")
    log("FOMC meeting calendar", url, "data/raw/fomccalendars.htm")
    dates = sorted(set(re.findall(r"/newsevents/pressreleases/monetary(\d{8})a\.htm", html)))
    dates = [d for d in dates if d >= "20230101" and d <= TODAY.strftime("%Y%m%d")]
    out, skipped = [], []
    sdir = RAW / "fomc_statements"
    sdir.mkdir(exist_ok=True)
    for d in dates:
        surl = f"https://www.federalreserve.gov/newsevents/pressreleases/monetary{d}a.htm"
        h = get(surl).content.decode("utf-8", errors="replace")
        (sdir / f"monetary{d}a.htm").write_text(h, encoding="utf8")
        text = html_lib.unescape(re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", h)))
        text = re.sub("[‐‑‒–]", "-", text).replace("\xa0", " ")
        m = re.search(r"Committee decided to (lower|raise|maintain) the target range for the federal funds rate"
                      r"(?: by [\w/ -]+? percentage point)? (?:to|at) ([\d/-]+) to ([\d/-]+) percent", text)
        if not m:
            title = re.search(r"<title>(.*?)</title>", h, re.S)
            skipped.append(f"{d}: {title.group(1).strip() if title else 'no title'}")
            print(f"  -- no rate decision in {surl} (skipped)")
            continue
        act = {"lower": "cut", "raise": "hike", "maintain": "hold"}[m.group(1)]
        out.append({"date": d, "decision": act, "lower": _pct(m.group(2)), "upper": _pct(m.group(3)), "url": surl})
        time.sleep(0.3)
    p = save_json(out, "fomc_decisions.json")
    log("FOMC decisions (statement text parsed for lower/raise/maintain and target range)",
        "https://www.federalreserve.gov/newsevents/pressreleases/monetaryYYYYMMDDa.htm", p,
        f"{len(out)} rate decisions since 2023 linked from the calendar page. Releases with no rate decision, "
        f"skipped: {'; '.join(skipped) or 'none'}. Each decision cross-checked against FRED DFEDTARU in analysis.py")


# ---------------------------------------------------------------- 3. stablecoins
def fetch_stablecoins():
    url = "https://stablecoins.llama.fi/stablecoincharts/all"
    p = save_json(get(url).json(), "stablecoins_all.json")
    log("Stablecoin supply, all chains (the peggedUSD component of totalCirculatingUSD is used)", url, p)
    url = "https://stablecoins.llama.fi/stablecoins?includePrices=false"
    p = save_json(get(url).json(), "stablecoins_list.json")
    log("Stablecoin asset list (used to identify assets inside the total)", url, p)


# ---------------------------------------------------------------- 2. tokenized treasuries
# DeFiLlama /protocol/{slug} returns an empty TVL history for these products (pull logged below).
TREASURY_SLUGS = ["blackrock-buidl", "ondo-yield-assets", "superstate", "invesco-ustb", "circle-usyc",
                  "openeden-tbill", "matrixdock-stbt", "vaneck-treasury-fund", "spiko", "wisdomtree",
                  "franklin-templeton"]

# Ethereum contracts (taken from DeFiLlama yields pool `underlyingTokens` for each product)
ETH_TOKENS = {
    "OUSG (Ondo)": "0x1b19c19393e2d034d8ff31ff34c81252fcbbee92",
    "USDY (Ondo)": "0x96f6ef951840721adbf46ac996b59e0235cb985c",
    "USTB (Superstate)": "0x43415eB6ff9DB7E26A15b704e7A3eDCe97d31C4e",
    "USYC (Hashnote/Circle)": "0x136471a34f6ef19fE571EFFC1CA711fdb8E49f2b",
    "TBILL (OpenEden)": "0xdd50C053C096CB04A3e3362E2b622529EC5f2e8a",
    "STBT (Matrixdock)": "0x530824da86689c9c17cdc2871ff29b058345b44a",
    "VBILL (VanEck)": "0x2255718832bC9fD3bE1CaF75084F4803DA14FF01",
}
# Aave v3 Ethereum stablecoin markets (aToken = deposits, variable debt token = borrows)
AAVE_TOKENS = {
    "aEthUSDC": "0x98C23E9d8f34FEFb1B7BD6a91B7FF122F4e16F5c",
    "aEthUSDT": "0x23878914EFE38d27C4D67Ab83ed1b93A74D4086a",
    "variableDebtEthUSDC": "0x72E95b8931767C79bA4EeE721354d6E99a61D004",
    "variableDebtEthUSDT": "0x6df1C1E379bC5a00a7b4C6e67A203333772f45A8",
}
MULTICALL3 = "0xcA11bde05977b3631167028862bE2a173976CA11"
SEL_TOTAL_SUPPLY = bytes.fromhex("18160ddd")
SEL_DECIMALS = bytes.fromhex("313ce567")
SEL_SYMBOL = bytes.fromhex("95d89b41")
SEL_AGG3 = bytes.fromhex("82ad56cb")  # aggregate3((address,bool,bytes)[])


RPCS = {"ethereum": "https://eth.drpc.org", "bsc": "https://bsc-mainnet.public.blastapi.io"}
# USYC moved most of its supply to BNB Chain from late 2025; same fund, same NAV as the Ethereum token
BSC_TOKENS = {"USYC (Hashnote/Circle)": "0x8D0fA28f221eB5735BC71d3a0Da67EE5bC821311"}
BSC_START = dt.datetime(2025, 1, 1, tzinfo=dt.timezone.utc)  # contract returns no code on this date (checked)


def rpc_call(to, data, block="latest", chain="ethereum"):
    body = {"jsonrpc": "2.0", "id": 1, "method": "eth_call",
            "params": [{"to": to, "data": "0x" + data.hex()}, block]}
    for i in range(6):
        try:
            r = requests.post(RPCS[chain], json=body, timeout=60)
            j = r.json()
            if "result" in j:
                return bytes.fromhex(j["result"][2:])
            err = j.get("error")
        except Exception as e:  # noqa: BLE001
            err = e
        time.sleep(2 * (i + 1))
    raise RuntimeError(f"rpc failed: {err}")


def multicall(addrs, sel, block, chain="ethereum"):
    calls = [(a, True, sel) for a in addrs]
    data = SEL_AGG3 + encode(["(address,bool,bytes)[]"], [calls])
    res = decode(["(bool,bytes)[]"], rpc_call(MULTICALL3, data, block, chain))[0]
    return [int.from_bytes(b, "big") if ok and len(b) == 32 else None for ok, b in res]


def daily_blocks(chain="ethereum", start=START):
    """Block at ~00:00 UTC each day. Monthly anchors from DeFiLlama, linear interpolation in between."""
    anchors = []
    d = start
    while d < TODAY:
        j = get(f"https://coins.llama.fi/block/{chain}/{int(d.timestamp())}").json()
        anchors.append((j["height"], j["timestamp"]))
        d = (d + dt.timedelta(days=32)).replace(day=1)
    j = get(f"https://coins.llama.fi/block/{chain}/{int(TODAY.timestamp()) - 3600}").json()
    anchors.append((j["height"], j["timestamp"]))
    out = []
    day = start
    while day < TODAY - dt.timedelta(hours=1):
        ts = int(day.timestamp())
        for (b0, r0), (b1, r1) in zip(anchors, anchors[1:]):
            if r0 - 120 <= ts <= r1:
                out.append((day.strftime("%Y-%m-%d"), max(b0, int(b0 + (b1 - b0) * (ts - r0) / (r1 - r0)))))
                break
        day += dt.timedelta(days=1)
    return anchors, out


def _supply_series(chain, tokens, start, cache_name):
    addrs, names = list(tokens.values()), list(tokens)
    meta = {}
    for n, a in zip(names, addrs):
        sym = decode(["string"], rpc_call(a, SEL_SYMBOL, chain=chain))[0]
        dec = decode(["uint8"], rpc_call(a, SEL_DECIMALS, chain=chain))[0]
        meta[n] = {"address": a, "symbol": sym, "decimals": dec, "chain": chain}
        print(f"     {chain} {n}: symbol={sym} decimals={dec}")
    anchors, blocks = daily_blocks(chain, start)
    save_json({"anchors": anchors, "blocks": blocks}, f"{chain}_daily_blocks.json")
    log(f"{chain} block at 00:00 UTC each day (monthly anchors, linear interpolation)",
        f"https://coins.llama.fi/block/{chain}/{{timestamp}}", f"data/raw/{chain}_daily_blocks.json")
    cache_p = RAW / cache_name
    cache = json.loads(cache_p.read_text()) if cache_p.exists() else {}
    if cache.get("_addrs") != addrs:
        cache = {"_addrs": addrs}
    for i, (day, b) in enumerate(blocks):
        if day in cache and day < (TODAY - dt.timedelta(days=2)).strftime("%Y-%m-%d"):
            continue
        cache[day] = {"block": b, "supply": multicall(addrs, SEL_TOTAL_SUPPLY, hex(b), chain)}
        if i % 100 == 0:
            print(f"     {chain} on-chain supply {day}")
            cache_p.write_text(json.dumps(cache))
    cache["_meta"] = meta
    cache_p.write_text(json.dumps(cache))
    log(f"{chain} totalSupply() per token per day (Multicall3 eth_call at daily block)",
        RPCS[chain] + "  (eth_call to Multicall3 0xcA11bde05977b3631167028862bE2a173976CA11)",
        f"data/raw/{cache_name}", "Tokens: " + ", ".join(f"{n} {a}" for n, a in zip(names, addrs)))


def fetch_onchain():
    _supply_series("ethereum", {**ETH_TOKENS, **AAVE_TOKENS}, START, "onchain_supply.json")


def fetch_onchain_bsc():
    _supply_series("bsc", BSC_TOKENS, BSC_START, "onchain_supply_bsc.json")


def fetch_prices():
    """Daily USD price (NAV) for each Ethereum treasury token, DeFiLlama coins API, 300-day chunks."""
    out = {}
    for n, a in ETH_TOKENS.items():
        pts = []
        start = int(START.timestamp())
        while start < TODAY.timestamp():
            j = get(f"https://coins.llama.fi/chart/ethereum:{a}",
                    params={"start": start, "span": 300, "period": "1d", "searchWidth": "12h"}).json()
            c = j.get("coins", {})
            if c:
                pts += list(c.values())[0]["prices"]
            start += 300 * 86400
            time.sleep(0.3)
        out[n] = pts
    p = save_json(out, "treasury_token_prices.json")
    log("Treasury token USD price (NAV), daily", "https://coins.llama.fi/chart/ethereum:{address}?start=..&span=300&period=1d", p)


def fetch_treasury_defillama():
    status = {}
    for s in TREASURY_SLUGS:
        url = f"https://api.llama.fi/protocol/{s}"
        r = requests.get(url, headers=UA, timeout=90)
        if r.status_code != 200:
            status[s] = f"HTTP {r.status_code}"
            continue
        j = r.json()
        save_json(j, f"llama_protocol_{s}.json")
        status[s] = f"{len(j.get('tvl') or [])} TVL points, module={j.get('module')}"
    save_json(status, "llama_protocol_status.json")
    log("DeFiLlama protocol TVL for tokenized treasury products (as requested)",
        "https://api.llama.fi/protocol/{slug}", "data/raw/llama_protocol_*.json",
        "FAILED for this purpose: " + "; ".join(f"{k}: {v}" for k, v in status.items()))
    # BUIDL is also tracked as a 'stablecoin' with full daily history across chains
    url = "https://stablecoins.llama.fi/stablecoin/173"
    p = save_json(get(url).json(), "buidl_stablecoin_173.json")
    log("BlackRock BUIDL circulating supply, all chains, daily (DeFiLlama stablecoins id 173)", url, p)


# ---------------------------------------------------------------- 4. yields
YIELD_POOLS = {
    "aave_v3_usdc_eth": "aa70268e-4b52-42bf-a116-608b370f9501",
    "aave_v3_usdt_eth": "f981a304-bb6c-45b8-b0c5-fd2f515ad23a",
    "morpho_steakusdc_eth": "b55f43a8-f444-4cd8-a3a4-0a4e786ba566",
    "ethena_susde": "66985a81-9c51-46ca-9977-42b4fe7bc6df",
}
TREASURY_POOL_PROJECTS = {"blackrock-buidl", "ondo-yield-assets", "circle-usyc", "invesco-ustb", "openeden-tbill",
                          "matrixdock-stbt", "vaneck-treasury-fund", "theo-network-thbill"}


def fetch_yields():
    url = "https://yields.llama.fi/pools"
    pools = get(url).json()["data"]
    save_json(pools, "yields_pools_snapshot.json")
    log("DeFiLlama yields pool list (snapshot, used to pick pool IDs)", url, "data/raw/yields_pools_snapshot.json")
    for k, pid in YIELD_POOLS.items():
        url = f"https://yields.llama.fi/chart/{pid}"
        p = save_json(get(url).json(), f"yield_{k}.json")
        meta = next((x for x in pools if x["pool"] == pid), {})
        log(f"Yield history: {k} ({meta.get('project')} {meta.get('chain')} {meta.get('symbol')})", url, p)
    # all-chain treasury pools: only a recent history, used as a coverage cross-check
    tp = [x for x in pools if x["project"] in TREASURY_POOL_PROJECTS and x["tvlUsd"] > 1e6]
    out = {}
    for x in tp:
        out[x["pool"]] = {"project": x["project"], "chain": x["chain"], "symbol": x["symbol"],
                          "data": get(f"https://yields.llama.fi/chart/{x['pool']}").json()["data"]}
        time.sleep(0.2)
    p = save_json(out, "yield_treasury_pools_allchains.json")
    log("Tokenized treasury pools, all chains (yields API)", "https://yields.llama.fi/chart/{pool_id}", p,
        f"{len(out)} pools; histories only start Jan-Apr 2026, so used as a coverage cross-check only")


# ---------------------------------------------------------------- 5. funding
def fetch_funding():
    for sym in ["BTCUSDT", "ETHUSDT"]:
        url = "https://fapi.binance.com/fapi/v1/fundingRate"
        rows, start = [], int(START.timestamp() * 1000)
        while True:
            j = get(url, params={"symbol": sym, "startTime": start, "limit": 1000}).json()
            if not j:
                break
            rows += j
            start = j[-1]["fundingTime"] + 1
            if len(j) < 1000:
                break
            time.sleep(0.3)
        p = save_json(rows, f"binance_funding_{sym}.json")
        log(f"Binance USD-M perp funding rate, {sym}, every 8h", url + f"?symbol={sym}&startTime=..&limit=1000", p,
            f"{len(rows)} prints")


def write_sources():
    lines = ["# Data sources", "",
             f"All series pulled on **{PULL_DATE}** (UTC) by `fetch_data.py`. Sample starts 2023-01-01.", "",
             "| Series | Source URL | Raw file | Notes |", "|---|---|---|---|"]
    for s, u, f, n in LOG:
        lines.append(f"| {s} | `{u}` | `{f}` | {n} |")
    notes = (ROOT / "data" / "SOURCES_NOTES.md")
    if notes.exists():
        lines += ["", notes.read_text(encoding="utf8")]
    (ROOT / "data" / "SOURCES.md").write_text("\n".join(lines) + "\n", encoding="utf8")
    print("wrote data/SOURCES.md")


def main():
    steps = [fetch_fred, fetch_treasury_curve, fetch_fomc, fetch_stablecoins, fetch_treasury_defillama, fetch_yields,
             fetch_funding, fetch_prices, fetch_onchain, fetch_onchain_bsc]
    for f in steps:
        print(f.__name__)
        try:
            f()
        except Exception as e:  # noqa: BLE001
            LOG.append((f.__name__, "-", "-", f"FAILED: {e}"))
            print(f"  !! {f.__name__} failed: {e}")
    write_sources()


if __name__ == "__main__":
    main()
