"""
SeedGenius Europe, part 2: what do the DNA markers tell us?

Data: 12,106 SNP markers for the 98 trial varieties (Agroscope, same Zenodo record).

Questions
  G1. How related are the varieties? (genomic relationship matrix, principal components)
  G2. Genomic prediction: can markers predict a variety's yield merit (variety effect from the
      two-way trial model) without field data for that variety?
        - random cross-validation across varieties (standard in breeding papers)
        - forward validation: train on varieties that entered the trials up to a year, predict
          the varieties that came later (the real use: screening new candidates)
  G3. Can markers predict a variety's weather sensitivity (Finlay-Wilkinson slope)?

Method: markers coded 0/1/2 (homozygous major / heterozygous / homozygous minor allele),
minor allele frequency >= 5%, missing values set to the marker mean. Prediction with ridge
regression on all markers (equivalent to GBLUP), penalty chosen by internal cross-validation.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from scipy.stats import pearsonr, spearmanr
from sklearn.linear_model import RidgeCV
from sklearn.model_selection import KFold

from seedgenius_eu import OUT, DATA, fw_slopes, load, two_way

MIN_TRIALS = 5
HET = set("KMRYSW")


def markers():
    raw = pd.read_csv(DATA / "SNP_v1.0.0.csv", sep=";", index_col=0, dtype=str)
    Z = pd.DataFrame(np.nan, index=raw.index, columns=raw.columns)
    for c in raw.columns:
        col = raw[c]
        homo = col[col.isin(list("ACGT"))]
        if homo.empty:
            continue
        major = homo.value_counts().idxmax()
        Z[c] = np.where(col == major, 0.0, np.where(col.isin(HET), 1.0, np.where(col.isna(), np.nan, 2.0)))
    p = Z.mean() / 2
    maf = np.minimum(p, 1 - p)
    Z = Z.loc[:, maf >= 0.05]
    Z = Z.fillna(Z.mean())
    return Z


def grm(Z):
    """VanRaden (2008) genomic relationship matrix."""
    p = Z.mean() / 2
    W = Z - 2 * p
    return W @ W.T / (2 * (p * (1 - p)).sum())


def ridge():
    return RidgeCV(alphas=np.logspace(0, 6, 40))


def cv_random(X, y, reps=20, k=5):
    rs = []
    for rep in range(reps):
        pred = pd.Series(index=y.index, dtype=float)
        for tr, te in KFold(k, shuffle=True, random_state=rep).split(X):
            m = ridge().fit(X.iloc[tr], y.iloc[tr])
            pred.iloc[te] = m.predict(X.iloc[te])
        rs.append(pearsonr(pred, y)[0])
    return float(np.mean(rs)), float(np.std(rs)), pred


def main():
    df, _ = load()
    veff, eeff = two_way(df)
    slopes = fw_slopes(df, veff, eeff)
    info = df.groupby("variety_code").agg(trials=("env", "nunique"), first=("year", "min"), last=("year", "max"))

    Z = markers()
    print(f"markers after filtering (MAF >= 5%): {Z.shape[1]} of 12,106; varieties: {Z.shape[0]}")
    G = grm(Z)
    G.round(4).to_csv(OUT / "genomic_relationship_matrix.csv")

    keep = info.index[(info["trials"] >= MIN_TRIALS)].intersection(Z.index)
    X = Z.loc[keep]
    X = (X - X.mean()) / X.std().replace(0, 1)
    y = veff.reindex(keep)
    s = slopes.reindex(keep)
    first = info.loc[keep, "first"]
    print(f"varieties with >= {MIN_TRIALS} trials: {len(keep)}")

    # G2a random cross-validation. Newer varieties are better (breeding progress), so year of
    # entry alone predicts merit. The genomic model therefore fits the year trend first and uses
    # the markers to predict what the trend misses; everything is refitted inside each fold.
    def fit_predict(tr, te):
        b = np.polyfit(first[tr], y[tr], 1)
        res = y[tr] - np.polyval(b, first[tr])
        m = ridge().fit(X[tr], res)
        return np.polyval(b, first[te]), m.predict(X[te])

    r_year, r_both, r_beyond, r_slope = [], [], [], []
    y_beyond = y - np.polyval(np.polyfit(first, y, 1), first)
    for rep in range(20):
        py = pd.Series(index=y.index, dtype=float); pm = py.copy(); ps = py.copy()
        for tr, te in KFold(5, shuffle=True, random_state=rep).split(X):
            trm = y.index.isin(y.index[tr]); tem = ~trm
            a_, b_ = fit_predict(trm, tem)
            py[tem], pm[tem] = a_, b_
            ps[tem] = ridge().fit(X[trm], s[trm]).predict(X[tem])
        r_year.append(pearsonr(py, y)[0]); r_both.append(pearsonr(py + pm, y)[0])
        r_beyond.append(pearsonr(pm, y_beyond)[0]); r_slope.append(pearsonr(ps, s)[0])
    summary = pd.DataFrame([
        {"prediction": "Year of entry only (breeding-progress trend)", "r": np.mean(r_year), "sd": np.std(r_year)},
        {"prediction": "Year of entry + DNA markers", "r": np.mean(r_both), "sd": np.std(r_both)},
        {"prediction": "DNA markers, merit beyond the year trend", "r": np.mean(r_beyond), "sd": np.std(r_beyond)},
        {"prediction": "DNA markers, weather sensitivity (slope)", "r": np.mean(r_slope), "sd": np.std(r_slope)},
    ]).round(3)
    print(summary.to_string(index=False))
    summary.to_csv(OUT / "genomic_prediction_random_cv.csv", index=False)

    # G2b forward validation: train on varieties that entered up to a cut-off year, predict later ones
    fwd = []
    for cut in [2005, 2008, 2011, 2014]:
        tr, te = (first <= cut).to_numpy(), (first > cut).to_numpy()
        py, pm = fit_predict(tr, te)
        yt = y[te]
        n_top = int(round(len(yt) / 4))
        top_true = set(yt.nlargest(n_top).index)
        hit = lambda pred: 100 * len(top_true & set(pd.Series(pred, yt.index).nlargest(n_top).index)) / n_top
        fwd.append({"trained_on_entries_up_to": cut, "training_varieties": int(tr.sum()), "new_varieties": int(te.sum()),
                    "r_year_only": round(pearsonr(py, yt)[0], 3), "r_year_plus_markers": round(pearsonr(py + pm, yt)[0], 3),
                    "top_quarter_found_year_only_pct": round(hit(py), 0), "top_quarter_found_with_markers_pct": round(hit(py + pm), 0)})
    fwd = pd.DataFrame(fwd)
    print(fwd.to_string(index=False))
    fwd.to_csv(OUT / "genomic_prediction_forward.csv", index=False)

    # G1 relatedness: PCA from the relationship matrix
    vals, vecs = np.linalg.eigh(G.values)
    order = np.argsort(vals)[::-1]
    pcs = vecs[:, order[:2]] * np.sqrt(vals[order[:2]])
    share = vals[order[:2]] / vals[vals > 0].sum()
    pca = pd.DataFrame(pcs, index=G.index, columns=["PC1", "PC2"])
    pca["first_year"] = info["first"].reindex(pca.index)
    pca["variety_effect"] = veff.reindex(pca.index)
    pca.round(4).to_csv(OUT / "genomic_pca.csv")
    print("PC1/PC2 share of variation:", np.round(share * 100, 1),
          " corr PC1 with entry year:", round(spearmanr(pca["PC1"], pca["first_year"], nan_policy="omit")[0], 2))

    fig, ax = plt.subplots(figsize=(7, 5))
    sc = ax.scatter(pca["PC1"], pca["PC2"], c=pca["first_year"], cmap="viridis", s=36, edgecolor="white", lw=0.5)
    fig.colorbar(sc, label="First year in the trials")
    ax.set_xlabel(f"Genetic component 1 ({share[0] * 100:.0f}% of variation)")
    ax.set_ylabel(f"Genetic component 2 ({share[1] * 100:.0f}%)")
    ax.set_title(f"Genetic map of the 98 Swiss trial varieties ({Z.shape[1]:,} SNPs)")
    fig.tight_layout(); fig.savefig(OUT / "genomic_pca.png", dpi=160); plt.close(fig)

    # final model on all varieties -> genomic estimate for every variety
    tr_all = np.ones(len(y), bool)
    py, pm = fit_predict(tr_all, tr_all)
    gpred = pd.Series(py + pm, index=y.index)
    # relatives: share of identical marker genotypes (identity by state)
    Zv = Z.values
    ibs = pd.DataFrame(1 - np.abs(Zv[:, None, :] - Zv[None, :, :]).mean(axis=2) / 2, index=Z.index, columns=Z.index)
    ibs.round(4).to_csv(OUT / "genetic_similarity_ibs.csv")
    # leave-one-variety-out: what the DNA would have predicted had this variety never been tested
    loo = pd.Series(index=y.index, dtype=float)
    for v in y.index:
        tr, te = (y.index != v), (y.index == v)
        a_, b_ = fit_predict(tr, te)
        loo[v] = float(a_[0] + b_[0])
    print(f"leave-one-variety-out r = {pearsonr(loo, y)[0]:.3f}")
    fig, ax = plt.subplots(figsize=(6, 5))
    ax.scatter(loo, y, s=28, color="#1f5c3f", alpha=.8)
    lim = [min(loo.min(), y.min()) - .2, max(loo.max(), y.max()) + .2]
    ax.plot(lim, lim, color="grey", lw=.8, ls=":")
    ax.set_xlabel("Predicted from DNA + entry year, variety left out (t/ha)"); ax.set_ylabel("Field estimate from trials, t/ha")
    ax.set_title(f"Yield merit: DNA prediction vs field result (r = {pearsonr(loo, y)[0]:.2f})")
    fig.tight_layout(); fig.savefig(OUT / "genomic_vs_field.png", dpi=160); plt.close(fig)

    out = pd.DataFrame({"genomic_estimate_t_ha": gpred.round(3), "genomic_estimate_untested_t_ha": loo.round(3), "field_estimate_t_ha": y.round(3),
                        "weather_slope": s.round(4), "trials": info["trials"].reindex(y.index),
                        "first_year": first, "last_year": info["last"].reindex(y.index)})
    out.to_csv(OUT / "genomic_estimates.csv")
    off = ibs.values[np.triu_indices(len(ibs), 1)]
    print(f"genetic similarity between varieties: median {np.median(off):.1%}, range {off.min():.1%}-{off.max():.1%}")


if __name__ == "__main__":
    main()
