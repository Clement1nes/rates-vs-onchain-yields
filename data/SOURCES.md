# Data sources

All series pulled on **2026-10-16** (UTC) by `fetch_data.py`. Sample starts 2023-01-01.

| Series | Source URL | Raw file | Notes |
|---|---|---|---|
| FRED DFF: Effective fed funds rate, daily | `https://fred.stlouisfed.org/graph/fredgraph.csv?id=DFF` | `data/raw/fred_DFF.csv` |  |
| FRED DTB3: 3-month T-bill, secondary market, discount basis, daily | `https://fred.stlouisfed.org/graph/fredgraph.csv?id=DTB3` | `data/raw/fred_DTB3.csv` |  |
| FRED DGS2: 2-year Treasury constant maturity, daily | `https://fred.stlouisfed.org/graph/fredgraph.csv?id=DGS2` | `data/raw/fred_DGS2.csv` |  |
| FRED DFEDTARU: Fed funds target range upper bound (cross-check for FOMC decisions) | `https://fred.stlouisfed.org/graph/fredgraph.csv?id=DFEDTARU` | `data/raw/fred_DFEDTARU.csv` |  |
| Treasury daily bill rates (bank discount and coupon equivalent), 2025 | `https://home.treasury.gov/resource-center/data-chart-center/interest-rates/daily-treasury-rates.csv/2025/all?type=daily_treasury_bill_rates&field_tdr_date_value=2025&page&_format=csv` | `data/raw/treasury/daily_treasury_bill_rates_2025.csv` |  |
| Treasury daily bill rates (bank discount and coupon equivalent), 2026 | `https://home.treasury.gov/resource-center/data-chart-center/interest-rates/daily-treasury-rates.csv/2026/all?type=daily_treasury_bill_rates&field_tdr_date_value=2026&page&_format=csv` | `data/raw/treasury/daily_treasury_bill_rates_2026.csv` |  |
| Treasury daily par yield curve (1m to 30y), 2025 | `https://home.treasury.gov/resource-center/data-chart-center/interest-rates/daily-treasury-rates.csv/2025/all?type=daily_treasury_yield_curve&field_tdr_date_value=2025&page&_format=csv` | `data/raw/treasury/daily_treasury_yield_curve_2025.csv` |  |
| Treasury daily par yield curve (1m to 30y), 2026 | `https://home.treasury.gov/resource-center/data-chart-center/interest-rates/daily-treasury-rates.csv/2026/all?type=daily_treasury_yield_curve&field_tdr_date_value=2026&page&_format=csv` | `data/raw/treasury/daily_treasury_yield_curve_2026.csv` |  |
| FOMC meeting calendar | `https://www.federalreserve.gov/monetarypolicy/fomccalendars.htm` | `data/raw/fomccalendars.htm` |  |
| FOMC decisions (statement text parsed for lower/raise/maintain and target range) | `https://www.federalreserve.gov/newsevents/pressreleases/monetaryYYYYMMDDa.htm` | `data/raw/fomc_decisions.json` | 30 rate decisions since 2023 linked from the calendar page. Releases with no rate decision, skipped: 20250822: Federal Reserve Board - Federal Open Market Committee announces approval of updates to its Statement on Longer-Run Goals and Monetary Policy Strategy. Each decision cross-checked against FRED DFEDTARU in analysis.py |
| Stablecoin supply, all chains (the peggedUSD component of totalCirculatingUSD is used) | `https://stablecoins.llama.fi/stablecoincharts/all` | `data/raw/stablecoins_all.json` |  |
| Stablecoin asset list (used to identify assets inside the total) | `https://stablecoins.llama.fi/stablecoins?includePrices=false` | `data/raw/stablecoins_list.json` |  |
| DeFiLlama protocol TVL for tokenized treasury products (as requested) | `https://api.llama.fi/protocol/{slug}` | `data/raw/llama_protocol_*.json` | FAILED for this purpose: blackrock-buidl: 0 TVL points, module=dummy.js; ondo-yield-assets: 0 TVL points, module=dummy.js; superstate: 0 TVL points, module=None; invesco-ustb: 0 TVL points, module=dummy.js; circle-usyc: 0 TVL points, module=dummy.js; openeden-tbill: 0 TVL points, module=dummy.js; matrixdock-stbt: 0 TVL points, module=dummy.js; vaneck-treasury-fund: 0 TVL points, module=dummy.js; spiko: 0 TVL points, module=dummy.js; wisdomtree: 0 TVL points, module=dummy.js; franklin-templeton: HTTP 400 |
| BlackRock BUIDL circulating supply, all chains, daily (DeFiLlama stablecoins id 173) | `https://stablecoins.llama.fi/stablecoin/173` | `data/raw/buidl_stablecoin_173.json` |  |
| DeFiLlama yields pool list (snapshot, used to pick pool IDs) | `https://yields.llama.fi/pools` | `data/raw/yields_pools_snapshot.json` |  |
| Yield history: aave_v3_usdc_eth (aave-v3 Ethereum USDC) | `https://yields.llama.fi/chart/aa70268e-4b52-42bf-a116-608b370f9501` | `data/raw/yield_aave_v3_usdc_eth.json` |  |
| Yield history: aave_v3_usdt_eth (aave-v3 Ethereum USDT) | `https://yields.llama.fi/chart/f981a304-bb6c-45b8-b0c5-fd2f515ad23a` | `data/raw/yield_aave_v3_usdt_eth.json` |  |
| Yield history: morpho_steakusdc_eth (morpho-blue Ethereum STEAKUSDC) | `https://yields.llama.fi/chart/b55f43a8-f444-4cd8-a3a4-0a4e786ba566` | `data/raw/yield_morpho_steakusdc_eth.json` |  |
| Yield history: ethena_susde (ethena-usde Ethereum SUSDE) | `https://yields.llama.fi/chart/66985a81-9c51-46ca-9977-42b4fe7bc6df` | `data/raw/yield_ethena_susde.json` |  |
| Tokenized treasury pools, all chains (yields API) | `https://yields.llama.fi/chart/{pool_id}` | `data/raw/yield_treasury_pools_allchains.json` | 30 pools; histories only start Jan-Apr 2026, so used as a coverage cross-check only |
| Binance USD-M perp funding rate, BTCUSDT, every 8h | `https://fapi.binance.com/fapi/v1/fundingRate?symbol=BTCUSDT&startTime=..&limit=1000` | `data/raw/binance_funding_BTCUSDT.json` | 4154 prints |
| Binance USD-M perp funding rate, ETHUSDT, every 8h | `https://fapi.binance.com/fapi/v1/fundingRate?symbol=ETHUSDT&startTime=..&limit=1000` | `data/raw/binance_funding_ETHUSDT.json` | 4154 prints |
| Treasury token USD price (NAV), daily | `https://coins.llama.fi/chart/ethereum:{address}?start=..&span=300&period=1d` | `data/raw/treasury_token_prices.json` |  |
| ethereum block at 00:00 UTC each day (monthly anchors, linear interpolation) | `https://coins.llama.fi/block/ethereum/{timestamp}` | `data/raw/ethereum_daily_blocks.json` |  |
| ethereum totalSupply() per token per day (Multicall3 eth_call at daily block) | `https://eth.drpc.org  (eth_call to Multicall3 0xcA11bde05977b3631167028862bE2a173976CA11)` | `data/raw/onchain_supply.json` | Tokens: OUSG (Ondo) 0x1b19c19393e2d034d8ff31ff34c81252fcbbee92, USDY (Ondo) 0x96f6ef951840721adbf46ac996b59e0235cb985c, USTB (Superstate) 0x43415eB6ff9DB7E26A15b704e7A3eDCe97d31C4e, USYC (Hashnote/Circle) 0x136471a34f6ef19fE571EFFC1CA711fdb8E49f2b, TBILL (OpenEden) 0xdd50C053C096CB04A3e3362E2b622529EC5f2e8a, STBT (Matrixdock) 0x530824da86689c9c17cdc2871ff29b058345b44a, VBILL (VanEck) 0x2255718832bC9fD3bE1CaF75084F4803DA14FF01, aEthUSDC 0x98C23E9d8f34FEFb1B7BD6a91B7FF122F4e16F5c, aEthUSDT 0x23878914EFE38d27C4D67Ab83ed1b93A74D4086a, variableDebtEthUSDC 0x72E95b8931767C79bA4EeE721354d6E99a61D004, variableDebtEthUSDT 0x6df1C1E379bC5a00a7b4C6e67A203333772f45A8 |
| bsc block at 00:00 UTC each day (monthly anchors, linear interpolation) | `https://coins.llama.fi/block/bsc/{timestamp}` | `data/raw/bsc_daily_blocks.json` |  |
| bsc totalSupply() per token per day (Multicall3 eth_call at daily block) | `https://bsc-mainnet.public.blastapi.io  (eth_call to Multicall3 0xcA11bde05977b3631167028862bE2a173976CA11)` | `data/raw/onchain_supply_bsc.json` | Tokens: USYC (Hashnote/Circle) 0x8D0fA28f221eB5735BC71d3a0Da67EE5bC821311 |

## Failures, gaps and substitutions

**1. Tokenized Treasury TVL from DeFiLlama `/protocol/{slug}`: failed.**
`https://api.llama.fi/protocol/blackrock-buidl`, `ondo-yield-assets`, `superstate`, `invesco-ustb`, `circle-usyc`, `openeden-tbill`, `matrixdock-stbt`, `vaneck-treasury-fund`, `spiko` and `wisdomtree` all return an empty `tvl` array (adapter `dummy.js`). `franklin-templeton` returns HTTP 400. DeFiLlama has moved these products to its RWA dashboard. That dashboard's data API (`api.llama.fi/rwa/...`) returns 404 without a paid key. The site's own proxy (`defillama.com/api/public/rwa/...`) sits behind a Cloudflare browser challenge, so it was not used. The per-pool history on the yields API (`yields.llama.fi/chart/{pool}`) only starts between January and April 2026 for these products, so it is used as a coverage cross-check only.

**Substitute used (nearest public alternative):**
- **BUIDL:** DeFiLlama stablecoins API, asset id 173. Daily circulating supply across all chains from March 2024. BUIDL is priced at $1.
- **OUSG, USDY, USTB, USYC, TBILL, STBT, VBILL:** `totalSupply()` read on-chain at the first block of each UTC day on Ethereum (public RPC `eth.drpc.org`, via Multicall3), multiplied by the token's daily USD price (NAV) from the DeFiLlama coins API. Contract addresses come from the `underlyingTokens` field of each product's DeFiLlama yields pool, and each one was checked with `symbol()`.
- **USYC on BNB Chain:** USYC supply moved almost entirely to BNB Chain from late 2025. `totalSupply()` is read daily on BNB Chain from 1 January 2025 (`bsc-mainnet.public.blastapi.io`). The contract returns no code on that date. It is valued at the Ethereum USYC NAV (same fund).
- **Daily block numbers:** DeFiLlama `coins.llama.fi/block/{chain}/{timestamp}` at the start of each month, with linear interpolation in between. Error is a few minutes of block time.

**Coverage of the substitute.** On days when every DeFiLlama all-chain pool has data (from 3 April 2026), the tracked series is 74% to 85% of DeFiLlama's all-chain total for the same issuers. Not covered:
- Franklin BENJI, Spiko, WisdomTree, Fidelity and other funds that DeFiLlama's free yields API does not list.
- OUSG and USDY on non-EVM or other chains (Solana, Stellar, XRPL, Sei, Sui, Aptos, Mantle, Polygon).
- TBILL on XRPL, and USTB on Plume and Solana.

Supply that migrates from Ethereum to one of those chains shows up as an outflow. OUSG fell sharply on Ethereum in 2026 while growing on XRPL.

**Price gaps.** The DeFiLlama coins API skips some days. Where it does, the last published price is used for up to 10 days. NAV tokens accrue about 0.01% a day, so the error is under 0.15%. Longer gaps are left blank. No price is interpolated or assumed. A product only enters the total from its first public price:
- OUSG: no price from March to September 2023.
- USYC: no price before July 2024.
- USTB: no price before November 2024.
- VBILL: no price before August 2025.

Growth rates are chain-linked: they only compare products valued on both dates, so a product entering is never counted as growth.

**2. Lending demand.** DeFiLlama's `chartLendBorrow` endpoint (borrow totals) needs a paid key (HTTP 402). Substitute: `totalSupply()` of Aave v3 Ethereum's variable debt tokens (borrowing) and aTokens (deposits) for USDC and USDT, read on-chain daily. Aave v2, other chains and Morpho borrowing are not included.

**3. Morpho.** The largest Morpho USDC vault with long history on DeFiLlama is Steakhouse USDC (pool `b55f43a8-...`). Its history starts 28 May 2024. Newer, larger vault entries start in December 2025.

**4. Ethena sUSDe.** The DeFiLlama yields history starts 16 February 2024, two months after sUSDe launched.

**5. Aave pool APY.** DeFiLlama `tvlUsd` for lending pools is idle liquidity, not deposits. Days in Aave v3's launch period (before June 2023) with under $10m idle liquidity are dropped from the APY series. Some days in late April 2026 have no APY on DeFiLlama, when idle liquidity fell to almost zero. These are left blank.

**6. Rates.** FRED publishes business days only. Weekend and holiday values carry the last published rate for up to 4 days. DTB3 is quoted on a discount basis and is converted to a bond-equivalent yield so it is comparable with APYs.

**7. FOMC decisions.** Taken from the statement text on federalreserve.gov ("decided to lower/raise/maintain the target range ... to X to Y percent"). Every parsed range matches FRED DFEDTARU on the day after the decision. The 22 August 2025 release (Statement on Longer-Run Goals) is not a rate decision and is skipped.

**8. Stablecoin supply.** DeFiLlama counts BUIDL as a USD stablecoin, so BUIDL is subtracted from `stablecoincharts/all` to avoid counting it twice.

**9. Funding.** Binance USD-M (`fapi.binance.com`) answered normally, so no fallback to Hyperliquid or Bybit was needed.

**10. Treasury cross-check.** Treasury's published daily bill rates and par yield curve (home.treasury.gov) are pulled for the current and previous year. The DTB3 bond-equivalent conversion matches Treasury's 13-week coupon-equivalent rate to within 1bp on every day both are published. The front-end curve figures in the draft (1m, 1y and 2y against the top of the policy range) come from Treasury's par yield curve.

**11. External events named in the draft (not data series):**
- KelpDAO rsETH exploit, 18 April 2026. Aave's freeze notice: https://x.com/aave/status/2045593585966252377. CoinDesk, 20 April 2026: https://www.coindesk.com/tech/2026/04/20/aave-could-face-up-to-usd230-million-in-losses-after-kelp-dao-bridge-exploit-triggers-defi-chaos
- USYC native issuance on BNB Chain and Binance off-exchange collateral, 24 July 2025. Circle press release: https://www.circle.com/en/pressroom/circles-usyc-now-supported-as-yield-bearing-off-exchange-collateral-for-binances-institutional-clients

