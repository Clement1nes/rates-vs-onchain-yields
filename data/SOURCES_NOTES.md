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
