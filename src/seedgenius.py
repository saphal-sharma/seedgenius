"""
SeedGenius: predicting which barley varieties perform best given the season's weather.

Data: Minnesota barley variety trials, 6 sites, 1927-1936 (Immer; Wright 2013), joined
with monthly NOAA weather for each site and year.

Pipeline
  1. Build features: variety, site (stands in for soil and location), growing-season weather.
  2. Compare three models with leave-one-YEAR-out cross-validation, i.e. always
     predicting a season the model has never seen:
       - Baseline A: variety mean
       - Baseline B: variety mean + site effect (additive, no weather)
       - Gradient boosting with weather features
  3. Evaluate yield accuracy AND decision quality: does the model pick the best variety
     in each trial, and how much yield is lost when it does not?
  4. Explain the model with SHAP values.
  5. Rank varieties for contrasting season types (hot-dry vs cool-wet).
"""
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import shap
from scipy.stats import spearmanr
from sklearn.ensemble import GradientBoostingRegressor
from sklearn.linear_model import LinearRegression

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "results"
OUT.mkdir(exist_ok=True)
MIN_RECORDS = 20
MONTHS = {4: "apr", 5: "may", 6: "jun", 7: "jul"}


def f_to_c(x):
    return (x - 32) * 5 / 9


def build_data() -> pd.DataFrame:
    y = pd.read_csv(ROOT / "data" / "minnesota.barley.yield.txt", sep="\t")
    w = pd.read_csv(ROOT / "data" / "minnesota.barley.weather.txt", sep="\t")
    y = y[y["year"].between(1927, 1936)]
    keep = y["gen_name"].value_counts()
    y = y[y["gen_name"].isin(keep[keep >= MIN_RECORDS].index)].copy()
    y["yield_t_ha"] = y["yield"] * 0.0538          # 1 bu/ac barley (48 lb) = 0.0538 t/ha

    w = w[w["mo"].isin(MONTHS)].copy()
    w["tmax_c"], w["tmin_c"] = f_to_c(w["max"]), f_to_c(w["min"])
    w["precip_mm"] = w["precip"] * 25.4
    wide = w.pivot_table(index=["site", "year"], columns="mo",
                         values=["precip_mm", "tmax_c", "tmin_c"])
    wide.columns = [f"{v}_{MONTHS[m]}" for v, m in wide.columns]
    wide = wide.reset_index()
    wide["season_precip_mm"] = wide[[f"precip_mm_{m}" for m in MONTHS.values()]].sum(axis=1)
    wide["season_tmax_c"] = wide[[f"tmax_c_{m}" for m in ["may", "jun", "jul"]]].mean(axis=1)
    df = y.merge(wide, on=["site", "year"], how="inner")
    return df


def features(df, cols_weather, varieties, sites):
    X = pd.DataFrame(index=df.index)
    for v in varieties:
        X[f"variety={v}"] = (df["gen_name"] == v).astype(int)
    for s in sites:
        X[f"site={s}"] = (df["site"] == s).astype(int)
    X[cols_weather] = df[cols_weather]
    return X


def main():
    df = build_data()
    varieties = sorted(df["gen_name"].unique())
    sites = sorted(df["site"].unique())
    wcols = ["season_precip_mm", "season_tmax_c"] + \
            [f"{v}_{m}" for v in ["precip_mm", "tmax_c", "tmin_c"] for m in MONTHS.values()]
    X = features(df, wcols, varieties, sites)
    y = df["yield_t_ha"].to_numpy()

    preds = {k: np.zeros(len(df)) for k in ["A_variety_mean", "B_variety_plus_site", "C_gbm_weather"]}
    for yr in sorted(df["year"].unique()):
        te = (df["year"] == yr).to_numpy()
        tr = ~te
        vm = df[tr].groupby("gen_name")["yield_t_ha"].mean()
        preds["A_variety_mean"][te] = df.loc[te, "gen_name"].map(vm).fillna(y[tr].mean())
        add_cols = [c for c in X.columns if c.startswith(("variety=", "site="))]
        lm = LinearRegression().fit(X.loc[tr, add_cols], y[tr])
        preds["B_variety_plus_site"][te] = lm.predict(X.loc[te, add_cols])
        gbm = GradientBoostingRegressor(n_estimators=400, learning_rate=0.03, max_depth=3,
                                        subsample=0.8, random_state=1)
        gbm.fit(X[tr], y[tr])
        preds["C_gbm_weather"][te] = gbm.predict(X[te])

    # --- Accuracy and decision metrics
    df = df.assign(**{f"pred_{k}": v for k, v in preds.items()})
    rows = []
    for k in preds:
        p = df[f"pred_{k}"]
        rmse = float(np.sqrt(np.mean((p - df["yield_t_ha"]) ** 2)))
        r2 = 1 - np.sum((p - df["yield_t_ha"]) ** 2) / np.sum((df["yield_t_ha"] - df["yield_t_ha"].mean()) ** 2)
        hits, regret, rhos = [], [], []
        for _, g in df.groupby(["site", "year"]):
            if len(g) < 3:
                continue
            best_true = g["yield_t_ha"].max()
            pick = g.loc[g[f"pred_{k}"].idxmax(), "yield_t_ha"]
            hits.append(pick == best_true)
            regret.append(best_true - pick)
            rhos.append(spearmanr(g[f"pred_{k}"], g["yield_t_ha"]).statistic)
        rows.append({"model": k, "rmse_t_ha": rmse, "r2": r2,
                     "top_variety_hit_rate_pct": 100 * np.mean(hits),
                     "mean_yield_lost_vs_best_t_ha": np.mean(regret),
                     "mean_rank_correlation_within_trial": np.nanmean(rhos),
                     "trials_evaluated": len(hits)})
    sizes = [len(g) for _, g in df.groupby(["site", "year"]) if len(g) >= 3]
    rows.append({"model": "Random pick (reference)", "top_variety_hit_rate_pct": 100 * np.mean([1 / n for n in sizes]),
                 "trials_evaluated": len(sizes)})
    metrics = pd.DataFrame(rows).round(3)
    metrics.to_csv(OUT / "model_comparison_leave_one_year_out.csv", index=False)

    # --- Final model on all data + SHAP explanation
    gbm = GradientBoostingRegressor(n_estimators=400, learning_rate=0.03, max_depth=3,
                                    subsample=0.8, random_state=1).fit(X, y)
    expl = shap.TreeExplainer(gbm)
    sv = expl.shap_values(X)
    imp = pd.Series(np.abs(sv).mean(axis=0), index=X.columns)
    group = {"Variety (genetics)": imp[[c for c in X.columns if c.startswith("variety=")]].sum(),
             "Site (soil & location)": imp[[c for c in X.columns if c.startswith("site=")]].sum(),
             "Weather": imp[wcols].sum()}
    group = pd.Series(group)
    group_pct = (100 * group / group.sum()).round(1)
    top_features = imp.sort_values(ascending=False).head(12).round(3)
    top_features.to_csv(OUT / "shap_top_features.csv", header=["mean_abs_shap_t_ha"])
    group_pct.to_csv(OUT / "shap_share_by_group.csv", header=["share_pct"])

    plt.figure()
    shap.summary_plot(sv, X, max_display=12, show=False)
    plt.title("What drives predicted barley yield? (SHAP)")
    plt.tight_layout()
    plt.savefig(OUT / "shap_summary.png", dpi=150, bbox_inches="tight")
    plt.close("all")

    # --- Variety recommendations for contrasting season types
    sy = df.drop_duplicates(["site", "year"])
    hot_dry = sy[(sy["season_tmax_c"] >= sy["season_tmax_c"].quantile(0.67)) &
                 (sy["season_precip_mm"] <= sy["season_precip_mm"].quantile(0.5))]
    cool_wet = sy[(sy["season_tmax_c"] <= sy["season_tmax_c"].quantile(0.33)) &
                  (sy["season_precip_mm"] >= sy["season_precip_mm"].quantile(0.5))]
    rec = {}
    for name, seasons in [("hot_dry", hot_dry), ("cool_wet", cool_wet)]:
        grid = []
        for _, s in seasons.iterrows():
            for v in varieties:
                r = s.copy()
                r["gen_name"] = v
                grid.append(r)
        g = pd.DataFrame(grid).reset_index(drop=True)
        g["pred"] = gbm.predict(features(g, wcols, varieties, sites))
        rec[name] = g.groupby("gen_name")["pred"].mean()
        rec[f"{name}_n_site_years"] = len(seasons)
    recommend = pd.DataFrame({"hot_dry_pred_t_ha": rec["hot_dry"], "cool_wet_pred_t_ha": rec["cool_wet"]})
    recommend["rank_hot_dry"] = recommend["hot_dry_pred_t_ha"].rank(ascending=False).astype(int)
    recommend["rank_cool_wet"] = recommend["cool_wet_pred_t_ha"].rank(ascending=False).astype(int)
    recommend = recommend.sort_values("rank_hot_dry").round(2)
    recommend.to_csv(OUT / "variety_ranking_by_season_type.csv")

    fig, ax = plt.subplots(figsize=(7, 5))
    ax.scatter(recommend["cool_wet_pred_t_ha"], recommend["hot_dry_pred_t_ha"])
    for v, r in recommend.iterrows():
        ax.annotate(v, (r["cool_wet_pred_t_ha"], r["hot_dry_pred_t_ha"]), fontsize=8,
                    xytext=(3, 3), textcoords="offset points")
    lims = [recommend.iloc[:, :2].min().min() - 0.1, recommend.iloc[:, :2].max().max() + 0.1]
    ax.plot(lims, lims, ls=":", color="grey")
    ax.set_xlabel("Predicted yield, cool-wet seasons (t/ha)")
    ax.set_ylabel("Predicted yield, hot-dry seasons (t/ha)")
    ax.set_title("Variety performance by season type")
    fig.tight_layout()
    fig.savefig(OUT / "variety_by_season_type.png", dpi=150)

    pd.set_option("display.width", 180)
    print(f"Records: {len(df)}, varieties: {len(varieties)}, site-years: {df[['site','year']].drop_duplicates().shape[0]}")
    print("\nLeave-one-year-out comparison\n", metrics.to_string(index=False))
    print("\nSHAP share by feature group (%)\n", group_pct)
    print("\nTop features\n", top_features)
    print(f"\nSeason types: hot-dry n={rec['hot_dry_n_site_years']}, cool-wet n={rec['cool_wet_n_site_years']}")
    print("Thresholds: hot >= %.1f C, cool <= %.1f C, precip median %.0f mm" % (
        sy["season_tmax_c"].quantile(0.67), sy["season_tmax_c"].quantile(0.33), sy["season_precip_mm"].quantile(0.5)))
    print(recommend)


if __name__ == "__main__":
    main()
