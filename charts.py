"""Publication charts. One style for all: Roboto, fixed palette, recessive grid, source line under each."""
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

OUT = Path(__file__).parent / "charts"
OUT.mkdir(exist_ok=True)

# palette: reference categorical order (blue, orange, aqua, yellow, magenta) + text inks
BLUE, ORANGE, AQUA, YELLOW, MAGENTA = "#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4"
INK, INK2, MUTED, GRID = "#0b0b0b", "#52514e", "#8a8984", "#e6e5e1"
BLUE_FILL, ORANGE_FILL = "#cde2fb", "#fbdccf"

plt.rcParams.update({
    "font.family": "Roboto", "font.size": 9, "axes.titlesize": 11, "axes.titleweight": "bold",
    "axes.titlelocation": "left", "axes.labelsize": 9, "axes.labelcolor": INK2,
    "axes.edgecolor": MUTED, "axes.linewidth": 0.6, "axes.spines.top": False, "axes.spines.right": False,
    "axes.grid": True, "axes.grid.axis": "y", "grid.color": GRID, "grid.linewidth": 0.6,
    "xtick.color": INK2, "ytick.color": INK2, "xtick.major.size": 3, "ytick.major.size": 0,
    "legend.frameon": False, "legend.fontsize": 8.5, "lines.linewidth": 1.6,
    "figure.facecolor": "white", "axes.facecolor": "white", "savefig.facecolor": "white",
})
W, Hh = 7.2, 3.9  # inches


def _finish(fig, ax, title, subtitle, source, name):
    ax.set_title(title, pad=22, color=INK)
    ax.text(0, 1.02, subtitle, transform=ax.transAxes, fontsize=8.5, color=INK2, va="bottom")
    ax.xaxis.set_major_locator(mdates.MonthLocator(bymonth=[1, 7]))
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%b %Y"))
    fig.text(0.012, 0.012, "Source: " + source, fontsize=7, color=MUTED, ha="left", va="bottom")
    fig.tight_layout(rect=(0, 0.04, 1, 1))
    fig.savefig(OUT / name, dpi=300)
    plt.close(fig)


def _fomc_lines(ax, fomc, label=True):
    for _, r in fomc.iterrows():
        if r["decision"] == "cut":
            ax.axvline(r["date"], color=INK2, lw=0.8, ls="-", alpha=0.7, zorder=0)
        elif r["decision"] == "hike":
            ax.axvline(r["date"], color=INK2, lw=0.8, ls="--", alpha=0.7, zorder=0)
        else:
            ax.axvline(r["date"], color=MUTED, lw=0.5, ls=":", alpha=0.6, zorder=0)


def chart1(P, tt, fomc, R):
    fig, ax = plt.subplots(figsize=(W, Hh))
    tot = P["tt_total_usd"] / 1e9
    ax.fill_between(tot.index, 0, tot, color=BLUE_FILL, lw=0)
    ax.plot(tot.index, tot, color=BLUE, label="Tokenized Treasuries, $bn (left)")
    ax.set_ylabel("Tokenized Treasuries, $bn", color=BLUE)
    ax.tick_params(axis="y", colors=BLUE)
    ax.set_ylim(0, tot.max() * 1.12)
    ax2 = ax.twinx()
    ax2.plot(P.index, P["TBILL_BEY"], color=ORANGE, label="3m T-bill yield, % (right)")
    ax2.set_ylabel("3m T-bill yield, %", color=ORANGE)
    ax2.tick_params(axis="y", colors=ORANGE)
    ax2.spines["right"].set_visible(True)
    ax2.spines["right"].set_color(MUTED)
    ax2.set_ylim(0, 6)
    ax2.grid(False)
    _fomc_lines(ax, fomc[fomc["decision"].isin(["cut", "hike"])])
    h1, l1 = ax.get_legend_handles_labels()
    h2, l2 = ax2.get_legend_handles_labels()
    ax.legend(h1 + h2, l1 + l2, loc="center left", bbox_to_anchor=(0, 0.6))
    ax.text(0.01, 0.42, "Vertical lines: FOMC cuts (solid), hikes (dashed).\nA product is counted from the first day "
            "it has a public price:\nOUSG from Sep 2023, USYC from Jul 2024, USTB from Nov 2024.", transform=ax.transAxes,
            ha="left", va="top", fontsize=7, color=MUTED)
    _finish(fig, ax, "Tokenized Treasuries kept growing through the cuts",
            "Tracked tokenized T-bill funds (BUIDL all chains; OUSG, USDY, USYC, USTB, TBILL, STBT, VBILL on Ethereum)",
            "DeFiLlama stablecoins API (BUIDL), Ethereum totalSupply via eth.drpc.org priced with DeFiLlama coins API, "
            "FRED DTB3 (bond-equivalent), federalreserve.gov", "1_tokenized_treasuries_vs_tbill.png")


def chart2(P, fomc, R):
    fig, ax = plt.subplots(figsize=(W, Hh))
    tb = P["TBILL_BEY"]
    lend = P["lend_apy_7d"]
    ok = lend.notna() & tb.notna()
    ax.fill_between(P.index, tb, lend, where=ok & (lend >= tb), color=BLUE_FILL, lw=0, interpolate=True,
                    label="Aave spread over T-bill: positive")
    ax.fill_between(P.index, tb, lend, where=ok & (lend < tb), color=ORANGE_FILL, lw=0, interpolate=True,
                    label="Aave spread over T-bill: negative")
    ax.plot(P.index, tb, color=INK, lw=1.4, label="3m T-bill (bond-equivalent)")
    ax.plot(P.index, lend, color=BLUE, label="Aave v3 USDC/USDT supply APY")
    ax.plot(P.index, P["morpho_apy_7d"], color=AQUA, lw=1.2, label="Morpho steakUSDC vault APY")
    ax.plot(P.index, P["susde_apy_7d"].clip(upper=20), color=MAGENTA, lw=1.2, label="Ethena sUSDe APY (capped at 20%)")
    ax.set_ylim(0, 20)
    ax.set_ylabel("% a year, 7-day average")
    ax.legend(loc="upper center", bbox_to_anchor=(0.5, -0.09), ncol=3, fontsize=7.5)
    _finish(fig, ax, "On-chain dollar yields against the T-bill",
            "Shaded area is the Aave lending spread over the 3m T-bill",
            "DeFiLlama yields API (Aave v3 Ethereum USDC and USDT, Morpho steakUSDC, Ethena sUSDe), FRED DTB3",
            "2_onchain_yields_vs_tbill.png")


def chart3(P, fomc, R):
    fig, ax = plt.subplots(figsize=(W, Hh))
    _fomc_lines(ax, fomc)
    ax.axhline(0, color=MUTED, lw=0.6)
    ax.plot(P.index, P["BTC_funding_ann"].rolling(7, min_periods=5).mean(), color=ORANGE, label="BTC perp funding")
    ax.plot(P.index, P["ETH_funding_ann"].rolling(7, min_periods=5).mean(), color=BLUE, label="ETH perp funding")
    ax.plot(P.index, P["TBILL_BEY"], color=INK, lw=1.2, ls="-", label="3m T-bill")
    ax.set_ylabel("% a year, 7-day average")
    ax.legend(loc="upper right", ncol=3)
    ax.text(0.995, 0.03, "FOMC: cut (solid), hike (dashed), hold (dotted)", transform=ax.transAxes,
            fontsize=7, color=MUTED, va="bottom", ha="right", backgroundcolor="white")
    _finish(fig, ax, "Perp funding swamps the policy rate",
            "Binance USD-M BTCUSDT and ETHUSDT funding, annualised (daily sum of 8-hour prints x 365)",
            "Binance fapi/v1/fundingRate, FRED DTB3, federalreserve.gov FOMC statements",
            "3_funding_with_fomc.png")


def chart4(P, fomc, R):
    fig, (a1, a2) = plt.subplots(2, 1, figsize=(W, Hh + 0.6), sharex=True, gridspec_kw={"height_ratios": [1.4, 1]})
    a1.axhline(0, color=MUTED, lw=0.6)
    a1.plot(P.index, P["sc_90d_ann"], color=BLUE)
    a1.set_ylabel("Supply growth,\n90-day annualised, %")
    a2.step(P.index, P["DFF"], where="post", color=ORANGE)
    a2.set_ylabel("Fed funds\neffective, %")
    a2.set_ylim(0, 6)
    for a in (a1, a2):
        _fomc_lines(a, fomc[fomc["decision"].isin(["cut", "hike"])])
    a1.set_title("Stablecoin growth follows the crypto cycle more than the Fed", pad=22, color=INK)
    a1.text(0, 1.03, "USD stablecoins excluding BUIDL. Vertical lines: FOMC cuts (solid), hike (dashed)",
            transform=a1.transAxes, fontsize=8.5, color=INK2, va="bottom")
    a2.xaxis.set_major_locator(mdates.MonthLocator(bymonth=[1, 7]))
    a2.xaxis.set_major_formatter(mdates.DateFormatter("%b %Y"))
    fig.text(0.012, 0.012, "Source: DeFiLlama stablecoins API (stablecoincharts/all less BUIDL), FRED DFF",
             fontsize=7, color=MUTED)
    fig.tight_layout(rect=(0, 0.04, 1, 1))
    fig.savefig(OUT / "4_stablecoin_growth_vs_fedfunds.png", dpi=300)
    plt.close(fig)


def chart5(P, R):
    """Independent 30-day windows: lending spread vs tokenized T-bill growth; sUSDe spread vs sUSDe growth."""
    samp = P.loc[R["test_start"]:R["last_ts"]].iloc[::-1].iloc[::30].iloc[::-1]
    fig, (a1, a2) = plt.subplots(1, 2, figsize=(W, Hh + 0.3), sharey=False)
    for ax, xcol, ycol, color, xlab, ylab, key, thr in [
        (a1, "spread_lend", "tt_fwd", BLUE, "Aave lending yield minus 3m T-bill, pp",
         "Tokenized Treasuries, next 30 days, %", "spread_lend_vs_tt_fwd", None),
        (a2, "spread_susde", "susde_fwd", MAGENTA, "sUSDe yield minus 3m T-bill, pp",
         "sUSDe TVL, next 30 days, %", "spread_susde_vs_susde_fwd", 2.0)]:
        d = samp[[xcol, ycol]].dropna()
        y = 100 * (np.exp(d[ycol]) - 1)
        ax.axhline(0, color=MUTED, lw=0.6)
        ax.axvline(0, color=MUTED, lw=0.6)
        ax.scatter(d[xcol], y, s=34, color=color, edgecolor="white", linewidth=1, zorder=3)
        if thr is not None:
            ax.axvline(thr, color=INK2, lw=0.9, ls="--")
            # medians come from the analysis output so the chart and the text quote the same figure
            t = next(x for x in R["thresholds_susde"] if x["threshold_pp"] == thr)
            for lo, hi, med, n in [(-np.inf, thr, t["susde_fwd_below_pct"], t["n_below"]),
                                   (thr, np.inf, t["susde_fwd_above_pct"], t["n_above"])]:
                x0, x1 = max(d[xcol].min(), lo), min(d[xcol].max(), hi)
                ax.plot([x0, x1], [med, med], color=INK, lw=1.4)
                ax.annotate(f"median {med:+.1f}%\n(n={n})", xy=((x0 + x1) / 2, med),
                            xytext=(x1 + 0.4, -45) if hi != np.inf else (13, 170),
                            fontsize=7.5, color=INK, ha="left" if hi != np.inf else "center",
                            arrowprops=dict(arrowstyle="-", color=INK2, lw=0.6))
        c = R["corr"][key]
        ax.text(0.02, 0.97, f"Spearman rho {c['rho']:.2f}, p = {c['p']:.2f}, n = {c['n']}", transform=ax.transAxes,
                fontsize=7.5, color=INK2, va="top")
        ax.set_xlabel(xlab)
        ax.set_ylabel(ylab)
        ax.grid(axis="x", visible=True)
    a1.set_title("Lending spread: no signal", pad=8, color=INK, fontsize=10)
    a2.set_title("Basis spread: flows follow it", pad=8, color=INK, fontsize=10)
    fig.suptitle("Capital chases the basis spread, not the lending spread", x=0.012, y=0.985, ha="left", va="top",
                 fontweight="bold", fontsize=11, color=INK)
    fig.text(0.012, 0.925, f"Non-overlapping 30-day windows, {R['test_window_label']}. Each dot is the spread on one day\n"
             "(7-day average) and the change over the following 30 days. Dashed line: +2pp split.", fontsize=8.5,
             color=INK2, va="top")
    fig.text(0.012, 0.012, "Source: DeFiLlama yields API (Aave v3, Ethena sUSDe), tokenized T-bill series as chart 1, "
             "FRED DTB3 (bond-equivalent)", fontsize=7, color=MUTED)
    fig.tight_layout(rect=(0, 0.04, 1, 0.87))
    fig.savefig(OUT / "5_spread_vs_next_30d_flows.png", dpi=300)
    plt.close(fig)


def make_all(P, tt, fomc, R):
    chart1(P, tt, fomc, R)
    chart2(P, fomc, R)
    chart3(P, fomc, R)
    chart4(P, fomc, R)
    chart5(P, R)
    print("charts written to charts/")
