"""Tests for SeedGenius Europe: core models on simulated data, the real data, and the web app."""
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from seedgenius_eu import SeasonModel, fw_slopes, load, two_way  # noqa: E402


def simulated_trials(seed=1, n_var=12, n_env=30, slopes=None):
    """Unbalanced trials with known variety and trial effects."""
    rng = np.random.default_rng(seed)
    v_true = pd.Series(rng.normal(0, 0.6, n_var), index=[f"V{i}" for i in range(n_var)])
    v_true -= v_true.mean()
    e_true = pd.Series(rng.normal(7, 1.2, n_env), index=[f"E{j}" for j in range(n_env)])
    rows = []
    for e in e_true.index:
        for v in rng.choice(v_true.index, size=7, replace=False):     # each trial tests 7 varieties
            b = 0 if slopes is None else slopes[v]
            y = e_true[e] + v_true[v] + b * (e_true[e] - e_true.mean()) + rng.normal(0, 0.05)
            rows.append({"variety_code": v, "env": e, "yield_t_ha": y})
    return pd.DataFrame(rows), v_true, e_true


def test_two_way_recovers_known_variety_effects():
    tr, v_true, _ = simulated_trials()
    veff, _ = two_way(tr)
    assert np.allclose(veff.reindex(v_true.index), v_true, atol=0.05)


def test_two_way_beats_raw_means_when_varieties_meet_different_seasons():
    tr, v_true, _ = simulated_trials(seed=3)
    veff, _ = two_way(tr)
    raw = tr.groupby("variety_code")["yield_t_ha"].mean()
    raw -= raw.mean()
    err_two_way = (veff.reindex(v_true.index) - v_true).abs().mean()
    err_raw = (raw.reindex(v_true.index) - v_true).abs().mean()
    assert err_two_way < err_raw / 3


def test_finlay_wilkinson_slope_has_the_right_sign():
    slopes = {f"V{i}": (0.3 if i == 0 else -0.3 if i == 1 else 0.0) for i in range(12)}
    tr, _, _ = simulated_trials(seed=5, slopes=slopes)
    veff, eeff = two_way(tr)
    b = fw_slopes(tr, veff, eeff)
    # slopes are deliberately shrunk towards zero (SLOPE_SHRINK), so only sign and order are tested
    assert b["V0"] > 0.05 and b["V1"] < -0.05
    assert b.drop(["V0", "V1"]).abs().max() < 0.02


@pytest.fixture(scope="module")
def data():
    return load()


def test_real_data_has_expected_size(data):
    df, wcols = data
    assert len(df) == 3880
    assert df["env"].nunique() == 303
    assert df["variety_code"].nunique() == 98
    assert len(wcols) == 42
    assert df[wcols].isna().sum().sum() == 0


def test_published_validation_results():
    m = pd.read_csv(ROOT / "results" / "variety_choice_leave_one_year_out.csv").set_index("model")
    assert m.loc["B_two_way_variety_effect", "picks_best_variety_pct"] == pytest.approx(54.3, abs=0.1)
    assert m.loc["A_raw_variety_mean", "picks_best_variety_pct"] == pytest.approx(45.0, abs=0.1)
    calib = pd.read_csv(ROOT / "results" / "win_probability_calibration.csv")
    # predicted win chances should be close to observed win rates in well-populated bins
    big = calib[calib["varieties_in_trials"] >= 100]
    assert (big["predicted_chance"] - big["actual_win_rate"]).abs().max() < 0.13


def app_data():
    html = (ROOT / "docs" / "index.html").read_text()
    return json.loads(html.split("const D = ")[1].split(";\nconst $")[0])


def test_web_app_formula_matches_python_model(data):
    """The browser recomputes season quality from exported ridge coefficients; it must equal Python."""
    df, wcols = data
    D = app_data()
    veff, eeff = two_way(df)
    locations = sorted(df["location_code"].unique())
    sm = SeasonModel().fit(df, eeff, wcols, locations)
    for env in ["L1_2023", "L9_2015", "L12_1998"]:
        row = df[df["env"] == env].drop_duplicates("env")
        if row.empty:
            continue
        r = row.iloc[0]
        x = {k: r[k] for k in wcols}
        x["year"] = D["year"]
        loc = r["location_code"]
        s = D["intercept"]
        for k, c in D["coef"].items():
            v = (1.0 if k == f"location={loc}" else 0.0) if k.startswith("location=") else x[k]
            s += c * (v - D["mu"][k]) / D["sd"][k]
        py = sm.predict(row.assign(year=D["year"]))[0]
        assert s == pytest.approx(py, abs=1e-3)


def test_web_app_lists_recent_varieties_only():
    D = app_data()
    assert len(D["varieties"]) >= 20
    assert all(v["last"] >= 2021 and v["trials"] >= 9 for v in D["varieties"])
    assert len(D["genomics"]["varieties"]) == 98


def test_variety_mix_trade_off():
    """A mix should cost average yield but lower the chance of a below-average result."""
    m = pd.read_csv(ROOT / "results" / "variety_mix_leave_one_year_out.csv").set_index("varieties")
    assert m.loc[1, "avg_gain_over_average_variety_t_ha"] > m.loc[3, "avg_gain_over_average_variety_t_ha"]
    assert m.loc[3, "trials_below_average_variety_pct"] < m.loc[1, "trials_below_average_variety_pct"]
    assert (m["trials"] == m["trials"].iloc[0]).all()
