"""[REPRO] Offline Hi4D metrics from the matched meshes that launch.py dumps (--eval_dataset hi4d).

Hi4D is an extension (not in the Human3R paper); protocol and sources in REPRO_NOTES section 8.
launch.py logs the upstream per-person camera-frame metrics with 24 SMPL joints. Published Hi4D
numbers use other conventions, so this script adds, from <output_dir>/matched/*.npz:
  * per-person MPJPE / PA-MPJPE / PVE with 24 SMPL joints (pelvis = mean of hips [1, 2]); must
    reproduce the launch.py log lines (self-check, --tol 0.051 mm on the 0.1 mm-rounded log);
  * the same with the 14 H36M joints used for 3DPW in this repo ("3DPW (14)"; PromptHMR reports
    "HI4D (14)" without naming the joints; our assumption, see section 8);
  * Pair-PA-MPJPE (PromptHMR Sec. 8.4: "aligns two people as a whole with the ground truth before
    computing MPJPE"): one similarity transform for the stacked joints of both people, then MPJPE;
    BUDDI calls it "joint PA-MPJPE". Only frames where both people are matched.
Every function used for alignment and errors is upstream's (eval/global_human/utils.py); the joint
regressors are the ones SMPLModel sets up for '3dpw' (14) and for the other datasets (24).
Averages: per sequence over matched person-frames (pair: matched pair-frames); overall pooled over
all of them, which equals upstream's n_human-weighted mean of unrounded per-sequence values.

Usage (repo root):  python repro/hi4d_metrics.py <output_dir> [--log <output_dir>/_error_log_0.txt]
Writes <output_dir>/hi4d_metrics.json and prints a table.
"""
import argparse
import glob
import json
import os
import re
import sys

import numpy as np
import torch

repo = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, repo)
sys.path.insert(0, os.path.join(repo, "src"))
os.chdir(repo)
from eval.global_human.utils import eval_camcoord, batch_compute_similarity_transform_torch, compute_jpe  # noqa: E402
import dust3r.utils  # noqa: E402,F401  (import first: circular import otherwise)
from dust3r.smpl_model import SMPLModel  # noqa: E402

ap = argparse.ArgumentParser()
ap.add_argument("output_dir")
ap.add_argument("--log", default=None, help="launch.py per-sequence log for the self-check (default: _error_log_0.txt)")
ap.add_argument("--tol", type=float, default=0.051, help="mm; the log is rounded to 0.1 mm")
a = ap.parse_args()
torch.set_grad_enabled(False)

joint_sets = {}
for name, ds in [("smpl24", "hi4d"), ("h36m14", "3dpw")]:
    m = SMPLModel("cpu", eval_args={"dataset": ds})
    joint_sets[name] = (m.j_regressor.float(), list(m.pelvis_idx))


def pair_pa_mpjpe(pred_j, gt_j):
    """pred_j, gt_j: (F, 2, J, 3) -> (F,) mm, one similarity transform per frame for both people."""
    F, P, J, _ = pred_j.shape
    pj, gj = pred_j.reshape(F, P * J, 3), gt_j.reshape(F, P * J, 3)
    return compute_jpe(batch_compute_similarity_transform_torch(pj, gj), gj) * 1000


files = sorted(glob.glob(os.path.join(a.output_dir, "matched", "*.npz")))
assert files, f"no matched/*.npz in {a.output_dir} (run launch.py --eval_dataset hi4d)"
per_seq, pooled = {}, {}
for f in files:
    seq = os.path.basename(f)[:-4].replace("__", "/")
    d = np.load(f)
    pv, tv = torch.from_numpy(d["pred_v3d"]), torch.from_numpy(d["target_v3d"])
    f_id, gid = d["f_id"], d["gid"]
    r = {"n_person_frames": int(len(f_id)), "n_scored_frames": int(len(range(0, int(d["n_frames"]), int(d["eval_stride"])))),
         "eval_stride": int(d["eval_stride"])}
    vals = {}
    for js, (jr, pelvis) in joint_sets.items():
        m = eval_camcoord({"pred_j3d": jr @ pv, "target_j3d": jr @ tv, "pred_v3d": pv, "target_v3d": tv}, pelvis)
        vals[f"{js}_MPJPE"], vals[f"{js}_PA-MPJPE"] = np.asarray(m["ca_mpjpe"]).reshape(-1), np.asarray(m["pa_mpjpe"]).reshape(-1)
        if js == "smpl24":
            vals["PVE"] = np.asarray(m["ca_pve"]).reshape(-1)
        # pair frames: both GT people matched in the frame
        frames_with_two = [k for k in np.unique(f_id) if (f_id == k).sum() == 2]
        if frames_with_two:
            order = [np.where(f_id == k)[0][np.argsort(gid[f_id == k])] for k in frames_with_two]
            idx = torch.from_numpy(np.stack(order))
            pj, gj = (jr @ pv)[idx], (jr @ tv)[idx]
            vals[f"{js}_Pair-PA-MPJPE"] = np.asarray(pair_pa_mpjpe(pj, gj)).reshape(-1)
        r["n_pair_frames"] = len(frames_with_two)
    for k, v in vals.items():
        r[k] = float(v.mean()) if len(v) else None
        pooled.setdefault(k, []).append(v)
    per_seq[seq] = r

overall = {k: float(np.concatenate(v).mean()) for k, v in pooled.items()}
overall["n_person_frames"] = sum(r["n_person_frames"] for r in per_seq.values())
overall["n_pair_frames"] = sum(r["n_pair_frames"] for r in per_seq.values())
overall["n_scored_frames"] = sum(r["n_scored_frames"] for r in per_seq.values())
overall["n_sequences"] = len(per_seq)

# self-check against the launch.py log (24 SMPL joints, upstream metric code)
log = a.log or os.path.join(a.output_dir, "_error_log_0.txt")
worst = 0.0
pat = re.compile(r"hi4d-(\S+)\s*\|\s*n_human:\s*(\d+)\s*\|\s*PVE: ([\d.]+),.*? MPJPE: ([\d.]+), PA-MPJPE: ([\d.]+),")
for line in open(log):
    mm = pat.search(line)
    if not mm or mm.group(1) not in per_seq:
        continue
    r = per_seq[mm.group(1)]
    assert int(mm.group(2)) == r["n_person_frames"], f"{mm.group(1)}: n_human {mm.group(2)} vs dump {r['n_person_frames']}"
    for logged, ours in [(mm.group(3), r["PVE"]), (mm.group(4), r["smpl24_MPJPE"]), (mm.group(5), r["smpl24_PA-MPJPE"])]:
        worst = max(worst, abs(float(logged) - ours))
assert worst <= a.tol, f"offline 24-joint metrics differ from the launch.py log by {worst:.3f} mm"

cols = ["smpl24_PA-MPJPE", "smpl24_MPJPE", "PVE", "smpl24_Pair-PA-MPJPE", "h36m14_PA-MPJPE", "h36m14_MPJPE", "h36m14_Pair-PA-MPJPE"]
fmt = lambda x: "  -  " if x is None else f"{x:6.1f}"
print(f"{'sequence':34s} {'n':>5s} {'pairs':>5s} " + " ".join(f"{c:>21s}" for c in cols))
for s, r in per_seq.items():
    print(f"{s:34s} {r['n_person_frames']:5d} {r['n_pair_frames']:5d} " + " ".join(f"{fmt(r.get(c)):>21s}" for c in cols))
print(f"{'ALL (pooled)':34s} {overall['n_person_frames']:5d} {overall['n_pair_frames']:5d} " + " ".join(f"{fmt(overall.get(c)):>21s}" for c in cols))
print(f"self-check vs launch.py log ({os.path.basename(log)}): max |diff| {worst:.3f} mm (log rounded to 0.1 mm) OK")
out = os.path.join(a.output_dir, "hi4d_metrics.json")
json.dump({"overall": overall, "per_sequence": per_seq, "self_check_max_abs_diff_mm": worst}, open(out, "w"), indent=1)
print(f"wrote {out}")
