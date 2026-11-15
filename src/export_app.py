"""Export the fitted models to the web app (docs/index.html).

The app recomputes predictions in the browser from these parameters, so it needs no server:
  predicted yield = season quality + variety effect + slope x (season quality - average season)
with season quality from the ridge model on weather, location and year.
"""
import json
from pathlib import Path

import numpy as np
import pandas as pd

from seedgenius_eu import SeasonModel, fw_slopes, load, two_way

ROOT = Path(__file__).resolve().parents[1]
APP_YEAR = 2023            # latest season in the data; the model is not extrapolated beyond it
MIN_TRIALS = 9


def main():
    df, wcols = load()
    locations = sorted(df["location_code"].unique())
    veff, eeff = two_way(df)
    slopes = fw_slopes(df, veff, eeff)
    sm = SeasonModel().fit(df, eeff, wcols, locations)

    info = df.groupby("variety_code").agg(trials=("env", "nunique"), last=("year", "max"))
    recent = info[(info["last"] >= 2021) & (info["trials"] >= MIN_TRIALS)].index
    varieties = [{"code": v, "effect": round(float(veff[v]), 4), "slope": round(float(slopes.get(v, 0)), 4),
                  "trials": int(info.loc[v, "trials"]), "last": int(info.loc[v, "last"])} for v in recent]

    E = df.drop_duplicates("env")
    active = E.groupby("location_code")["year"].max()
    active = sorted(active[active >= 2023].index, key=lambda s: int(s[1:]))
    base = {}
    for loc in active:
        w = E[(E["location_code"] == loc) & (E["year"] >= 2004)][wcols].median()
        base[loc] = {k: round(float(v), 4) for k, v in w.items()}

    # history of every season at each active site: the scenarios for the probability simulation
    hist = {loc: E[E["location_code"] == loc].sort_values("year")[wcols].round(3).values.tolist()
            for loc in active}
    hist_years = {loc: E[E["location_code"] == loc].sort_values("year")["year"].tolist() for loc in active}

    # noise for the simulation: genotype x environment residual SD (degrees-of-freedom corrected)
    res = (df["yield_t_ha"] - df["variety_code"].map(veff) - df["env"].map(eeff)
           - df["variety_code"].map(slopes) * (df["env"].map(eeff) - eeff.mean()))
    resid_sd = float(res.std() * np.sqrt(len(df) / (len(df) - len(veff) - len(eeff))))
    # season-level error of the weather model on unseen years (leave-one-year-out)
    errs = []
    for yr in sorted(df["year"].unique()):
        tr, te = df[df["year"] != yr], df[df["year"] == yr].drop_duplicates("env")
        v_, e_ = two_way(tr)
        m_ = SeasonModel().fit(tr, e_, wcols, locations)
        errs += list(eeff.reindex(te["env"]).to_numpy() - m_.predict(te))
    season_rmse = float(np.sqrt(np.mean(np.square(errs))))
    print(f"resid_sd {resid_sd:.3f}  season_rmse {season_rmse:.3f}")

    coef = sm.coefficients()
    temp = [k for k in wcols if k.split("_")[0] in ("Tabs", "Tmin", "Tmax")]
    print("effect of +1 C on all Mar-Jul temperatures:", round(sum(coef[k] / sm.sd[k] for k in temp), 3), "t/ha")
    tr_rng = {k: [round(float(E[k].min()), 2), round(float(E[k].max()), 2)] for k in temp}
    dry = {}
    for m in ["May", "Jun", "Jul"]:
        b = np.polyfit(E[f"PrecipSum_{m}"], E[f"DryDays_{m}"], 1)
        dry[m] = [round(float(b[0]), 5), round(float(b[1]), 4)]

    metrics = pd.read_csv(ROOT / "results" / "variety_choice_leave_one_year_out.csv")
    season = pd.read_csv(ROOT / "results" / "season_quality_from_weather.csv").iloc[0]
    weff = pd.read_csv(ROOT / "results" / "season_quality_weather_effects.csv", index_col=0).iloc[:8, 0]

    data = {
        "year": APP_YEAR, "wcols": wcols, "locations": active, "base": base,
        "mu": {k: round(float(v), 6) for k, v in sm.mu.items()},
        "sd": {k: round(float(v), 6) for k, v in sm.sd.items()},
        "coef": {k: round(float(v), 6) for k, v in coef.items()},
        "intercept": round(float(sm.m.intercept_), 6), "mean_quality": round(sm.mean_quality, 6),
        "dry": dry, "varieties": varieties,
        "hist": hist, "hist_years": hist_years, "resid_sd": round(resid_sd, 4), "season_rmse": round(season_rmse, 4),
        "temp_cols": temp, "temp_range": tr_rng,
        "calibration": pd.read_csv(ROOT / "results" / "win_probability_calibration.csv")
        .iloc[:, 1:].round(3).values.tolist(),
        "metrics": metrics[["model", "picks_best_variety_pct", "yield_lost_vs_best_t_ha", "random_pick_pct"]]
        .round(3).to_dict("records"),
        "season": {"r2": round(float(season["r2_trial_mean_yield"]), 3), "mae": round(float(season["mae_t_ha"]), 2)},
        "weather_effects": [[k, round(float(v), 3)] for k, v in weff.items()],
    }
    tpl = (ROOT / "src" / "app_template.html").read_text()
    out = ROOT / "docs" / "index.html"
    out.write_text(tpl.replace("__DATA__", json.dumps(data, separators=(",", ":"))))
    print(f"Wrote {out} ({out.stat().st_size / 1024:.0f} KB): {len(varieties)} varieties, "
          f"{len(active)} locations")
    # reference values for checking the JavaScript
    ref = df[(df["year"] == APP_YEAR)].drop_duplicates("env").iloc[:1]
    print("python season prediction for", ref["env"].iloc[0], round(float(sm.predict(ref)[0]), 4))


if __name__ == "__main__":
    main()
