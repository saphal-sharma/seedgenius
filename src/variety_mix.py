"""
SeedGenius: grow one variety, or split the farm across several?

Farmers and advisers often spread their area over 2-3 varieties to reduce risk. This script tests
whether that pays off, on seasons the model has never seen (leave-one-year-out):

  For every held-out year, variety effects are estimated from the other years only (two-way model).
  In every trial of the held-out year (at least 4 varieties already known), the strategies are:
    - top 1: all area on the variety ranked best
    - top 2 / top 3 / top 4: area split equally across the 2, 3 or 4 best-ranked varieties
  and each is scored on what the varieties actually yielded in that trial.

Measured per strategy: average yield above an average variety in the same trial, the result in the
worst 1 in 20 trials, how often the strategy ended below an average variety, the shortfall against
the trial's best variety, and how often the mix beat the single best-ranked variety.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from seedgenius_eu import OUT, load, two_way

STRATEGIES = [1, 2, 3, 4]


def evaluate(df):
    rows = []
    for yr in sorted(df["year"].unique()):
        tr, te = df[df["year"] != yr], df[df["year"] == yr]
        veff, _ = two_way(tr)
        for env, g in te.groupby("env"):
            g = g[g["variety_code"].isin(veff.index)]
            if len(g) < max(STRATEGIES):
                continue
            ranked = g.assign(score=g["variety_code"].map(veff)).sort_values("score", ascending=False)
            best = g["yield_t_ha"].max()
            for k in STRATEGIES:
                realised = ranked["yield_t_ha"].iloc[:k].mean()
                rows.append({"year": yr, "env": env, "k": k, "realised_t_ha": realised,
                             "shortfall_t_ha": best - realised, "trial_mean_t_ha": g["yield_t_ha"].mean()})
    return pd.DataFrame(rows)


def summarise(r):
    r = r.assign(gain=r["realised_t_ha"] - r["trial_mean_t_ha"])
    top1 = r[r["k"] == 1].set_index("env")["realised_t_ha"]
    out = []
    for k, g in r.groupby("k"):
        mine = g.set_index("env")["realised_t_ha"]
        out.append({"strategy": "Best-ranked variety only" if k == 1 else f"Equal mix of top {k}",
                    "varieties": k,
                    "avg_gain_over_average_variety_t_ha": g["gain"].mean(),
                    "worst_1_in_20_gain_t_ha": g["gain"].quantile(0.05),
                    "trials_below_average_variety_pct": 100 * (g["gain"] < 0).mean(),
                    "avg_shortfall_vs_trial_best_t_ha": g["shortfall_t_ha"].mean(),
                    "beats_top1_pct": None if k == 1 else 100 * (mine > top1.reindex(mine.index)).mean(),
                    "trials": len(g)})
    return pd.DataFrame(out).round(3)


def main():
    df, _ = load()
    r = evaluate(df)
    s = summarise(r)
    print(s.to_string(index=False))
    s.to_csv(OUT / "variety_mix_leave_one_year_out.csv", index=False)

    fig, (a1, a2) = plt.subplots(1, 2, figsize=(9, 3.8))
    labels = ["Top 1", "Mix of 2", "Mix of 3", "Mix of 4"]
    a1.bar(labels, s["avg_gain_over_average_variety_t_ha"], color=["#1f5c3f"] + ["#9aa39d"] * 3)
    a1.set_title("Average yield above an average variety (t/ha)", fontsize=10)
    a2.bar(labels, s["trials_below_average_variety_pct"], color=["#b8473a"] + ["#9aa39d"] * 3)
    a2.set_title("Trials that ended below an average variety (%)", fontsize=10)
    for ax in (a1, a2):
        for side in ["top", "right"]:
            ax.spines[side].set_visible(False)
    fig.suptitle(f"One variety or a mix? {int(s['trials'].iloc[0])} unseen Swiss wheat trials", fontsize=11)
    fig.tight_layout()
    fig.savefig(OUT / "variety_mix_comparison.png", dpi=160)
    plt.close(fig)


if __name__ == "__main__":
    main()
