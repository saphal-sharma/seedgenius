"""Check that SeedGenius win probabilities are honest (calibrated) on unseen seasons.

For each held-out year, variety effects are fitted on the other years. Yields are simulated as
variety effect + noise (genotype x environment residual SD plus estimation error), giving each
variety's probability of being the best in each trial. Those probabilities are then compared
with how often the variety actually won.
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import numpy as np, pandas as pd, warnings; warnings.filterwarnings("ignore")
from seedgenius_eu import load, two_way, fw_slopes
df, w = load()
veff, eeff = two_way(df); sl = fw_slopes(df, veff, eeff)
em = df.groupby("env")["yield_t_ha"].transform("mean")
res = df.yield_t_ha - df.variety_code.map(veff) - df.env.map(eeff) - df.variety_code.map(sl)*(df.env.map(eeff)-eeff.mean())
ntr = df.groupby("variety_code").env.nunique()
print("resid sd", res.std(), "dof-corrected", res.std()*np.sqrt(len(df)/(len(df)-len(veff)-len(eeff))))
rng = np.random.default_rng(0); rows=[]
for yr in sorted(df.year.unique()):
    tr, te = df[df.year!=yr], df[df.year==yr]
    v, e = two_way(tr); s = fw_slopes(tr, v, e)
    r = tr.yield_t_ha - tr.variety_code.map(v) - tr.env.map(e)
    sd = r.std()*np.sqrt(len(tr)/(len(tr)-len(v)-len(e)))
    n = tr.groupby("variety_code").env.nunique()
    for env, g in te.groupby("env"):
        g = g[g.variety_code.isin(v.index)]
        if len(g) < 4: continue
        mu = g.variety_code.map(v).to_numpy(); se = sd/np.sqrt(g.variety_code.map(n).to_numpy())
        sims = mu + rng.normal(0,1,(4000,len(g)))*np.sqrt(sd**2+se**2)
        p = np.bincount(sims.argmax(1), minlength=len(g))/4000
        win = (g.yield_t_ha.to_numpy()==g.yield_t_ha.max()).astype(int)
        rows += list(zip(p, win))
c = pd.DataFrame(rows, columns=["p","win"])
c["bin"] = pd.cut(c.p,[0,.05,.1,.2,.3,.5,.7,1],include_lowest=True)
t = c.groupby("bin", observed=True).agg(predicted_chance=("p","mean"),actual_win_rate=("win","mean"),varieties_in_trials=("win","size")).round(3)
print(t); t.to_csv(Path(__file__).resolve().parents[1] / "results" / "win_probability_calibration.csv")
