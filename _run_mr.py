import sys
sys.path.insert(0, "src")
import json
from research.evidence.mother_range_prior import run, CONTRACT_ID, OUT_DEFAULT

r = run()
print("CONTRACT:", CONTRACT_ID)
print("n_entries:", r["n_entries"])
print("arm_s:", r["arm_s"]["verdict"], "train", r["arm_s"]["train"]["contrast"],
      "holdout", r["arm_s"]["holdout"]["contrast"])
print("arm_t:", r["arm_t"]["verdict"], "train", r["arm_t"]["train"]["contrast"],
      "holdout", r["arm_t"]["holdout"]["contrast"])
print("split train/holdout:", r["split"]["n_train"], r["split"]["n_holdout"])
print("fingerprint:", r.get("fingerprint_sha256"))

# Also mirror reports into results/ so validation can cross-check.
import shutil, pathlib
src = pathlib.Path("docs/research-readiness/mother_range_prior/mc_mrprior_xauusd_m15_v1")
dst = pathlib.Path("results/research/mother_range_prior/mc_mrprior_xauusd_m15_v1")
dst.mkdir(parents=True, exist_ok=True)
for f in ("metrics.json", "population_fingerprint.json", "split_manifest.json"):
    shutil.copyfile(src / f, dst / f)
print("mirrored to", dst)