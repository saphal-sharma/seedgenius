"""
SeedGenius Europe: weather-aware winter wheat variety selection in Switzerland.

Data: official Swiss winter wheat variety trials (VCU, low-input), Agroscope, 1990-2023.
98 varieties, 16 locations, ~300 trial environments, with seasonal weather for every
site and year (Levy Häner et al. 2025, Zenodo 10.5281/zenodo.16420898, CC BY 4.0).

Questions
  Q1. Which varieties should be chosen for a season that has not happened yet?
  Q2. Does knowing the season's weather improve that choice?
  Q3. How well does weather predict how good a season will be, and which weather matters?

Every model is tested with leave-one-YEAR-out validation: each season is predicted by a
model trained only on the other 33 seasons, as when choosing varieties before sowing.

Models compared for variety choice
  A  Raw average yield of each variety (a common quick rule)
  B  Variety effects from a two-way variety + trial model (standard breeding practice:
     corrects for varieties having been tested in good or bad seasons)
  C  Gradient boosting on variety, location and 42 weather variables (machine learning)
  D  B plus a Finlay-Wilkinson response: each variety's sensitivity to season quality,
     with season quality predicted from weather, location and year (weather-aware)
"""
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from scipy.sparse import csr_matrix, hstack
from scipy.sparse.linalg import lsqr
from scipy.stats import spearmanr
from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.linear_model import RidgeCV

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
OUT = ROOT / "results"
OUT.mkdir(exist_ok=True)
SLOPE_SHRINK = 50.0     # shrinks Finlay-Wilkinson slopes of rarely tested varieties to 0


def load():
    y = pd.read_csv(DATA / "yield_v1.0.0.csv", sep=";")
    w = pd.read_csv(DATA / "weatherVariables_v1.0.0.csv", sep=";")
    df = (y.dropna(subset=["yield_dtPerHa"])
          .groupby(["year", "location_code", "variety_code"], as_index=False)["yield_dtPerHa"].mean())
    df["yield_t_ha"] = df["yield_dtPerHa"] / 10
    wcols = [c for c in w.columns if c not in ("year", "location_code")]
    w[wcols] = w[wcols].fillna(w[wcols].median())          # 25 missing values out of ~22,000
    df = df.merge(w, on=["year", "location_code"], how="inner")
    df["env"] = df["location_code"] + "_" + df["year"].astype(str)
    return df, wcols


def two_way(tr):
    """Least-squares variety and trial effects: yield = variety + trial + error."""
    v = pd.Categorical(tr["variety_code"])
    e = pd.Categorical(tr["env"])
    n = len(tr)
    Xv = csr_matrix((np.ones(n), (np.arange(n), v.codes)), shape=(n, len(v.categories)))
    Xe = csr_matrix((np.ones(n), (np.arange(n), e.codes)), shape=(n, len(e.categories)))
    sol = lsqr(hstack([Xv, Xe]).tocsr(), tr["yield_t_ha"].to_numpy(), damp=0.01)[0]
    veff = pd.Series(sol[:len(v.categories)], index=v.categories)
    eeff = pd.Series(sol[len(v.categories):], index=e.categories)
    # centre variety effects (only differences between varieties matter)
    return veff - veff.mean(), eeff + veff.mean()


def fw_slopes(tr, veff, eeff):
    """Finlay-Wilkinson slope of each variety's deviation on the trial mean (shrunk)."""
    tr = tr.assign(em=tr.groupby("env")["yield_t_ha"].transform("mean"))
    tr["dev"] = tr["yield_t_ha"] - tr["variety_code"].map(veff) - tr["env"].map(eeff)

    def slope(g):
        x = g["em"] - g["em"].mean()
        return float((x * g["dev"]).sum() / ((x ** 2).sum() + SLOPE_SHRINK))
    return tr.groupby("variety_code")[["em", "dev"]].apply(slope)


def env_features(d, wcols, locations):
    return pd.concat([d[wcols], d[["year"]],
                      pd.get_dummies(d["location_code"]).reindex(columns=locations, fill_value=0)
                      .add_prefix("location=")], axis=1).astype(float)


class SeasonModel:
    """Predict season quality (the trial effect from the two-way model, i.e. how good the
    season was net of which varieties were grown) from weather, location and year.
    Ridge regression on standardised inputs; penalty chosen by internal cross-validation."""

    def fit(self, tr, eeff, wcols, locations):
        E = tr.drop_duplicates("env").set_index("env")
        X = env_features(E, wcols, locations)
        self.cols, self.wcols, self.locations = X.columns, wcols, locations
        self.mu, self.sd = X.mean(), X.std().replace(0, 1)
        self.m = RidgeCV(alphas=np.logspace(-2, 3, 30)).fit((X - self.mu) / self.sd, eeff.reindex(E.index))
        self.mean_quality = float(eeff.reindex(E.index).mean())
        return self

    def predict(self, d):
        X = env_features(d, self.wcols, self.locations)[self.cols]
        return self.m.predict((X - self.mu) / self.sd)

    def coefficients(self):
        return pd.Series(self.m.coef_, index=self.cols)


def gbm_features(d, wcols, varieties, locations):
    X = pd.concat([
        pd.get_dummies(d["variety_code"]).reindex(columns=varieties, fill_value=0).add_prefix("variety="),
        pd.get_dummies(d["location_code"]).reindex(columns=locations, fill_value=0).add_prefix("location="),
        d[wcols]], axis=1).astype(float)
    return X


def decision_metrics(df, col):
    hits, lost, rhos, rand = [], [], [], []
    for _, g in df.dropna(subset=[col]).groupby("env"):
        if len(g) < 4:
            continue
        best = g["yield_t_ha"].max()
        pick = g.loc[g[col].idxmax(), "yield_t_ha"]
        hits.append(pick == best)
        lost.append(best - pick)
        rhos.append(spearmanr(g[col], g["yield_t_ha"]).statistic)
        rand.append(1 / len(g))
    return dict(picks_best_variety_pct=100 * np.mean(hits), yield_lost_vs_best_t_ha=np.mean(lost),
                rank_correlation_within_trial=np.nanmean(rhos), random_pick_pct=100 * np.mean(rand),
                trials=len(hits))


def main():
    df, wcols = load()
    varieties = sorted(df["variety_code"].unique())
    locations = sorted(df["location_code"].unique())
    print(f"{len(df)} variety-trial means, {df['env'].nunique()} trials, {len(varieties)} varieties, "
          f"{len(locations)} locations, {df['year'].min()}-{df['year'].max()}")

    P = {k: np.full(len(df), np.nan) for k in ["A_raw_variety_mean", "B_two_way_variety_effect",
                                                "C_gbm_weather", "D_variety_effect_plus_weather_response"]}
    env_pred = {}
    for yr in sorted(df["year"].unique()):
        te = (df["year"] == yr).to_numpy()
        tr = ~te
        T = df[tr]
        seen = df.loc[te, "variety_code"].isin(T["variety_code"]).to_numpy()
        idx = np.where(te)[0][seen]
        if len(idx) == 0:
            continue
        S = df.iloc[idx]
        P["A_raw_variety_mean"][idx] = S["variety_code"].map(T.groupby("variety_code")["yield_t_ha"].mean())
        veff, eeff = two_way(T)
        P["B_two_way_variety_effect"][idx] = S["variety_code"].map(veff)
        gbm = HistGradientBoostingRegressor(max_iter=300, learning_rate=0.05, max_leaf_nodes=15,
                                            min_samples_leaf=20, random_state=1)
        gbm.fit(gbm_features(T, wcols, varieties, locations), T["yield_t_ha"])
        P["C_gbm_weather"][idx] = gbm.predict(gbm_features(S, wcols, varieties, locations))
        sm = SeasonModel().fit(T, eeff, wcols, locations)
        b = fw_slopes(T, veff, eeff)
        season = sm.predict(S)
        P["D_variety_effect_plus_weather_response"][idx] = (S["variety_code"].map(veff).to_numpy()
                                                            + S["variety_code"].map(b).fillna(0).to_numpy()
                                                            * (season - sm.mean_quality))
        for env, val in zip(S["env"], season):
            env_pred[env] = val

    rows = []
    for k, v in P.items():
        df["_p"] = v
        rows.append({"model": k, **decision_metrics(df, "_p")})
    metrics = pd.DataFrame(rows).round(3)
    metrics.to_csv(OUT / "variety_choice_leave_one_year_out.csv", index=False)

    # Q3: how well does weather predict season quality (trial mean yield)?
    _, eeff_all = two_way(df)
    envs = df.groupby("env").agg(year=("year", "first"))
    envs["mean_yield"] = eeff_all.reindex(envs.index)   # season quality net of variety mix
    envs["pred"] = envs.index.map(env_pred)
    ok = envs["pred"].notna()
    r2_env = 1 - ((envs.loc[ok, "pred"] - envs.loc[ok, "mean_yield"]) ** 2).sum() / \
        ((envs.loc[ok, "mean_yield"] - envs.loc[ok, "mean_yield"].mean()) ** 2).sum()
    mae_env = (envs.loc[ok, "pred"] - envs.loc[ok, "mean_yield"]).abs().mean()
    pd.DataFrame([{"r2_trial_mean_yield": r2_env, "mae_t_ha": mae_env, "trials": int(ok.sum()),
                   "sd_season_quality_t_ha": envs["mean_yield"].std()}]).round(3) \
        .to_csv(OUT / "season_quality_from_weather.csv", index=False)

    # Final models on all data
    veff, eeff = two_way(df)
    b = fw_slopes(df, veff, eeff)
    n_trials = df.groupby("variety_code")["env"].nunique()
    last = df.groupby("variety_code")["year"].max()
    vt = pd.DataFrame({"variety_effect_t_ha": veff, "weather_response_slope": b,
                       "trials": n_trials, "last_year_tested": last}).round(3)
    vt.sort_values("variety_effect_t_ha", ascending=False).to_csv(OUT / "variety_effects.csv")
    sm = SeasonModel().fit(df, eeff, wcols, locations)
    coef = sm.coefficients()
    wcoef = coef[wcols].sort_values(key=np.abs, ascending=False)
    wcoef.round(3).to_csv(OUT / "season_quality_weather_effects.csv", header=["t_ha_per_sd"])
    top = wcoef.head(12)[::-1]
    fig, ax = plt.subplots(figsize=(7.5, 4.8))
    ax.barh(top.index, top.values, color=["#1f5c3f" if v > 0 else "#a3312b" for v in top.values])
    ax.axvline(0, color="black", lw=0.8)
    ax.set_xlabel("Change in season yield (t/ha) for +1 standard deviation")
    ax.set_title("Which weather makes a good wheat season? (ridge model)")
    fig.tight_layout()
    fig.savefig(OUT / "season_quality_weather_effects.png", dpi=150)

    # Figures
    fig, ax = plt.subplots(figsize=(7.5, 4.2))
    lab = {"A_raw_variety_mean": "Raw average", "B_two_way_variety_effect": "Two-way variety effect",
           "C_gbm_weather": "Machine learning + weather", "D_variety_effect_plus_weather_response": "Variety effect + weather response"}
    vals = metrics.set_index("model")["picks_best_variety_pct"]
    ax.barh([lab[k] for k in vals.index][::-1], vals.values[::-1], color=["#9aa39d", "#6c8f7d", "#9aa39d", "#1f5c3f"][::-1])
    ax.axvline(metrics["random_pick_pct"].iloc[0], ls=":", color="grey")
    ax.text(metrics["random_pick_pct"].iloc[0] + 0.5, -0.45, "random pick", fontsize=8, color="grey")
    for i, v in enumerate(vals.values[::-1]):
        ax.text(v + 0.5, i, f"{v:.0f}%", va="center", fontsize=9)
    ax.set_xlabel("Unseen trials where the method picked the best variety (%)")
    ax.set_title("Choosing varieties for a new season (Swiss wheat, 1990-2023)")
    fig.tight_layout()
    fig.savefig(OUT / "variety_choice_comparison.png", dpi=150)

    trend = df.groupby("year")["yield_t_ha"].mean()
    fig, ax = plt.subplots(figsize=(8, 3.8))
    ax.plot(trend.index, trend.values, marker="o", ms=3, color="#1f5c3f")
    ax.set_ylabel("Mean trial yield (t/ha)")
    ax.set_title("Swiss low-input winter wheat trials: mean yield by season")
    for yr in trend.nsmallest(3).index:
        ax.annotate(str(yr), (yr, trend[yr]), xytext=(0, -12), textcoords="offset points", ha="center", fontsize=8)
    fig.tight_layout()
    fig.savefig(OUT / "mean_yield_by_year.png", dpi=150)

    pd.set_option("display.width", 200)
    print(metrics.to_string(index=False))
    print(f"Season quality from weather: R2 = {r2_env:.3f}, MAE = {mae_env:.2f} t/ha, "
          f"SD of season quality = {envs['mean_yield'].std():.2f}")
    print(wcoef.head(10).round(3))
    print("year coef", round(coef["year"], 3))
    print(vt[vt["last_year_tested"] >= 2021].sort_values("variety_effect_t_ha", ascending=False).head(12))
    print("worst", trend.nsmallest(3).round(2).to_dict(), "best", trend.nlargest(3).round(2).to_dict())


if __name__ == "__main__":
    main()
