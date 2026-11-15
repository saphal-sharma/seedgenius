"""Precompute model predictions over a weather grid and build the web app (docs/index.html).

The app runs entirely in the browser: it looks up predictions computed here, so it needs
no server and works on GitHub Pages.
"""
import json
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.ensemble import GradientBoostingRegressor

from seedgenius import MONTHS, build_data, features

ROOT = Path(__file__).resolve().parents[1]


def main():
    df = build_data()
    varieties = sorted(df["gen_name"].unique())
    sites = sorted(df["site"].unique())
    wcols = ["season_precip_mm", "season_tmax_c"] + \
            [f"{v}_{m}" for v in ["precip_mm", "tmax_c", "tmin_c"] for m in MONTHS.values()]
    X = features(df, wcols, varieties, sites)
    model = GradientBoostingRegressor(n_estimators=400, learning_rate=0.03, max_depth=3,
                                      subsample=0.8, random_state=1).fit(X, df["yield_t_ha"])

    sy = df.drop_duplicates(["site", "year"])
    p_lo, p_hi = np.floor(sy["season_precip_mm"].quantile(0.05) / 20) * 20, \
        np.ceil(sy["season_precip_mm"].quantile(0.95) / 20) * 20
    precip_grid = np.arange(p_lo, p_hi + 1, 20)
    dt_grid = np.arange(-2.0, 2.01, 0.5)
    months = list(MONTHS.values())

    pred = {}
    observed = {}
    for site in sites:
        s = sy[sy["site"] == site]
        base = s[wcols].median()
        share = base[[f"precip_mm_{m}" for m in months]] / base[[f"precip_mm_{m}" for m in months]].sum()
        rows = []
        for p in precip_grid:
            for dt in dt_grid:
                r = base.copy()
                for m in months:
                    r[f"precip_mm_{m}"] = p * share[f"precip_mm_{m}"]
                    r[f"tmax_c_{m}"] = base[f"tmax_c_{m}"] + dt
                    r[f"tmin_c_{m}"] = base[f"tmin_c_{m}"] + dt
                r["season_precip_mm"] = p
                r["season_tmax_c"] = np.mean([r[f"tmax_c_{m}"] for m in ["may", "jun", "jul"]])
                for v in varieties:
                    q = r.copy()
                    q["gen_name"], q["site"] = v, site
                    rows.append(q)
        g = pd.DataFrame(rows).reset_index(drop=True)
        yhat = model.predict(features(g, wcols, varieties, sites))
        pred[site] = np.round(yhat.reshape(len(precip_grid), len(dt_grid), len(varieties)), 3).tolist()
        observed[site] = {"precip_min": round(float(s["season_precip_mm"].min())),
                          "precip_max": round(float(s["season_precip_mm"].max())),
                          "tmax_median": round(float(base["season_tmax_c"]), 1),
                          "precip_median": round(float(base["season_precip_mm"])),
                          "n_years": int(len(s))}

    variety_mean = df.groupby("gen_name")["yield_t_ha"].mean().round(3).reindex(varieties).tolist()
    metrics = pd.read_csv(ROOT / "results" / "model_comparison_leave_one_year_out.csv")
    shap_top = pd.read_csv(ROOT / "results" / "shap_top_features.csv").head(6)
    data = {"sites": sites, "varieties": varieties, "precip": precip_grid.tolist(),
            "dt": dt_grid.tolist(), "pred": pred, "observed": observed,
            "variety_mean": variety_mean,
            "metrics": metrics.fillna("").to_dict("records"),
            "shap": shap_top.to_dict("records")}
    tpl = (ROOT / "src" / "app_template.html").read_text()
    out = ROOT / "docs" / "index.html"
    out.parent.mkdir(exist_ok=True)
    out.write_text(tpl.replace("__DATA__", json.dumps(data, separators=(",", ":"))))
    print(f"Wrote {out} ({out.stat().st_size/1024:.0f} KB); precip grid {precip_grid[0]}-{precip_grid[-1]} mm")


if __name__ == "__main__":
    main()
