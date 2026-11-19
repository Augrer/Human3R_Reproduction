"""Build the Hi4D annotation file for eval/global_human/launch.py (--eval_dataset hi4d).

[REPRO] Not part of upstream Human3R; Hi4D is not in the paper (extension: close two-person
interaction). Camera-frame local mesh metrics only: Hi4D's cameras are static, so the global
metrics (W-/WA-MPJPE, RTE) are not meaningful and the dataset entry sets is_global=False.

Input (official Hi4D layout, unpacked):  <data>/Hi4D/<pair>/<action>/
    images/<cam>/<frame>.jpg     8 static RGB cameras, 940x1280 (portrait), undistorted
    cameras/rgb_cameras.npz      ids, intrinsics (8,3,3), extrinsics (8,3,4) world->camera, dist_coeffs (all 0)
    smpl/<frame>.npz             per frame, both people: global_orient, body_pose (69), betas, transl
                                 (world frame), plus verts / joints_3d / contact
    meta.npz                     genders, mono_cam (the camera intended for monocular methods), start, end
Output:  eval/global_human/annots/hi4d_<split>.pkl  (gitignored) + hi4d_<split>.json (provenance)
    { "<pair>/<action>/cam<k>": {
        "cam": k, "K": (3,3), "T_w2c": (4,4), "size": (W,H), "genders": [g0, g1],
        "frames": [<frame stem>, ...]                       # contact range meta start..end, consecutive
        "smpl_root_pose": (F,2,3)  axis-angle, CAMERA frame
        "smpl_body_pose": (F,2,23,3), "smpl_shape": (F,2,10)
        "smpl_transl":    (F,2,3)  CAMERA frame
        "visible":        (F,2) bool   person counted as present in this view (see --min_joints_in)
    } }
The two people keep Hi4D's order (index 0/1 as in meta.npz genders) in every frame.

World -> camera conversion of the SMPL parameters (exact, no fitting): with x_c = R x_w + t and
the rest-pose pelvis J0(betas, gender),  root_c = R root_w  and  transl_c = R (J0 + transl_w) + t - J0.
Self-checks, per sequence (the script fails if either exceeds --tol_mm):
  (1) SMPL(gender, world params) vs the vertices Hi4D ships in smpl/*.npz  -> body model + gender
  (2) SMPL(gender, camera params) vs R * verts_w + t                         -> the conversion

Usage (from the repo root, CPU is enough):
    python repro/datasets_preprocess/prepare_hi4d.py --pairs pair00 --split test
    python repro/datasets_preprocess/prepare_hi4d.py --split test        # every pair under <data>/Hi4D
    BUDDI test split (REPRO_NOTES section 8):
    python repro/datasets_preprocess/prepare_hi4d.py --pairs pair12 pair15 pair32 --split test
    python repro/datasets_preprocess/prepare_hi4d.py --pairs pair12 pair15 pair32 --split test_allcams --cams all
"""
import argparse
import datetime
import glob
import json
import os
import pickle
import subprocess
import sys

import numpy as np
import torch

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(REPO, "src"))
import smplx  # noqa: E402

H3R_DATA = os.environ.get("H3R_DATA", os.path.normpath(os.path.join(REPO, "..", "data")))
SMPL_DIR = os.path.join(REPO, "src", "models")
ANNOT_DIR = os.path.join(REPO, "eval", "global_human", "annots")


def rotvec_to_rotmat(r):
    r = torch.as_tensor(r, dtype=torch.float64).reshape(-1, 3)
    theta = r.norm(dim=1, keepdim=True).clamp_min(1e-12)
    k = r / theta
    K = torch.zeros(len(r), 3, 3, dtype=r.dtype)
    K[:, 0, 1], K[:, 0, 2], K[:, 1, 2] = -k[:, 2], k[:, 1], -k[:, 0]
    K = K - K.transpose(1, 2)
    s, c = torch.sin(theta)[:, :, None], torch.cos(theta)[:, :, None]
    return torch.eye(3, dtype=r.dtype) + s * K + (1 - c) * (K @ K)


def rotmat_to_rotvec(R):
    # via quaternion (stable near 0 and pi)
    R = torch.as_tensor(R, dtype=torch.float64).reshape(-1, 3, 3)
    try:
        import roma
        return roma.rotmat_to_rotvec(R)
    except ImportError:
        from scipy.spatial.transform import Rotation
        return torch.from_numpy(Rotation.from_matrix(R.numpy()).as_rotvec())


def smpl_forward(layer, root, body, betas, transl):
    f = lambda x: torch.as_tensor(np.asarray(x), dtype=torch.float32)
    out = layer(global_orient=f(root).reshape(-1, 3), body_pose=f(body).reshape(-1, 69),
                betas=f(betas).reshape(-1, 10), transl=f(transl).reshape(-1, 3))
    return out.vertices.detach().double(), out.joints.detach().double()


def convert_sequence(seq_dir, cam_id, layers, min_joints_in, tol_mm):
    meta = np.load(os.path.join(seq_dir, "meta.npz"))
    cams = np.load(os.path.join(seq_dir, "cameras", "rgb_cameras.npz"))
    ci = list(cams["ids"]).index(cam_id)
    assert np.abs(cams["dist_coeffs"][ci]).max() == 0, "non-zero distortion: images would need undistorting"
    K = cams["intrinsics"][ci].astype(np.float64)
    E = cams["extrinsics"][ci].astype(np.float64)
    R, t = E[:, :3], E[:, 3]
    T_w2c = np.eye(4); T_w2c[:3] = E
    genders = [str(g) for g in meta["genders"]]
    assert int(meta["num_persons"]) == 2 and len(genders) == 2

    img_dir = os.path.join(seq_dir, "images", str(cam_id))
    imgs = {os.path.splitext(f)[0] for f in os.listdir(img_dir) if f.endswith(".jpg")}
    # contact range: meta start..end ("the start and end frame from/to which each sequence involves
    # physical contact", BUDDI Sup. S4.2). Frames must be consecutive: eval_stride counts by position.
    start, end = int(meta["start"]), int(meta["end"])
    smpl_all = sorted(glob.glob(os.path.join(seq_dir, "smpl", "*.npz")))
    smpl_files = [f for f in smpl_all if start <= int(os.path.splitext(os.path.basename(f))[0]) <= end]
    frames = [os.path.splitext(os.path.basename(f))[0] for f in smpl_files]
    ids = [int(f) for f in frames]
    assert ids == list(range(start, end + 1)), f"SMPL frames are not exactly {start}..{end} (gaps?)"
    missing = [f for f in frames if f not in imgs]
    assert not missing, f"{len(missing)} SMPL frames without an image, e.g. {missing[:3]}"
    from PIL import Image
    W, H = Image.open(os.path.join(img_dir, frames[0] + ".jpg")).size

    P = len(frames)
    d = {k: np.stack([np.load(f)[k] for f in smpl_files]) for k in
         ["global_orient", "body_pose", "betas", "transl", "verts"]}
    out = {k: np.zeros(s, np.float32) for k, s in [
        ("smpl_root_pose", (P, 2, 3)), ("smpl_body_pose", (P, 2, 23, 3)),
        ("smpl_shape", (P, 2, 10)), ("smpl_transl", (P, 2, 3))]}
    visible = np.zeros((P, 2), bool)
    err_world, err_cam = 0.0, 0.0
    for h in range(2):
        layer = layers[genders[h]]
        root_w, body, betas, transl_w = (d["global_orient"][:, h], d["body_pose"][:, h],
                                         d["betas"][:, h], d["transl"][:, h])
        v_w, _ = smpl_forward(layer, root_w, body, betas, transl_w)
        err_world = max(err_world, (v_w - torch.from_numpy(d["verts"][:, h]).double()).norm(dim=-1).max().item())

        # rest-pose pelvis J0(betas): joints of the zero-pose, zero-transl body
        _, j_rest = smpl_forward(layer, np.zeros((P, 3)), np.zeros((P, 69)), betas, np.zeros((P, 3)))
        J0 = j_rest[:, 0].numpy()
        root_c = rotmat_to_rotvec(torch.from_numpy(R)[None] @ rotvec_to_rotmat(root_w)).numpy()
        transl_c = (J0 + transl_w) @ R.T + t - J0

        v_c, j_c = smpl_forward(layer, root_c, body, betas, transl_c)
        v_c_ref = v_w.numpy() @ R.T + t
        err_cam = max(err_cam, (v_c - torch.from_numpy(v_c_ref)).norm(dim=-1).max().item())

        # visibility in this view: in front of the camera and enough of the 24 joints inside the image
        j = j_c[:, :24].numpy()
        uv = j @ K.T; uv = uv[..., :2] / uv[..., 2:3]
        inside = (j[..., 2] > 0) & (uv[..., 0] >= 0) & (uv[..., 0] < W) & (uv[..., 1] >= 0) & (uv[..., 1] < H)
        visible[:, h] = inside.sum(1) >= min_joints_in

        out["smpl_root_pose"][:, h] = root_c
        out["smpl_body_pose"][:, h] = body.reshape(P, 23, 3)
        out["smpl_shape"][:, h] = betas
        out["smpl_transl"][:, h] = transl_c

    err_world, err_cam = err_world * 1000, err_cam * 1000
    assert err_world < tol_mm, f"SMPL(world params) vs shipped verts: {err_world:.3f} mm (gender / model mismatch?)"
    assert err_cam < tol_mm, f"camera-frame conversion error {err_cam:.3f} mm"
    ann = dict(cam=cam_id, K=K.astype(np.float32), T_w2c=T_w2c.astype(np.float32),
               size=np.array([W, H], np.int32), genders=genders, frames=frames, visible=visible, **out)
    stats = dict(frames=P, contact_range=[start, end], smpl_files_outside_range=len(smpl_all) - P,
                 person_frames_visible=int(visible.sum()), person_frames_total=2 * P,
                 max_err_world_mm=round(err_world, 4), max_err_cam_mm=round(err_cam, 4), genders=genders)
    return ann, stats


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--data", default=os.path.join(H3R_DATA, "Hi4D"))
    ap.add_argument("--pairs", nargs="*", default=None, help="pair folders (default: all under --data)")
    ap.add_argument("--split", default="test", help="output name: annots/hi4d_<split>.pkl")
    ap.add_argument("--cams", default="mono", help="'mono' (meta mono_cam, default), 'all' (all 8 cameras, one sequence each), or a comma list of ids")
    ap.add_argument("--min_joints_in", type=int, default=12,
                    help="a person counts as visible in a frame if at least this many of 24 joints project inside the image")
    ap.add_argument("--tol_mm", type=float, default=1.0)
    a = ap.parse_args()

    torch.set_grad_enabled(False)
    layers = {g: smplx.create(SMPL_DIR, "smpl", gender=g) for g in ["male", "female"]}
    pairs = a.pairs or sorted(p for p in os.listdir(a.data) if p.startswith("pair"))
    annots, report = {}, {}
    for pair in pairs:
        for action in sorted(os.listdir(os.path.join(a.data, pair))):
            seq_dir = os.path.join(a.data, pair, action)
            if not os.path.isfile(os.path.join(seq_dir, "meta.npz")):
                continue
            if a.cams == "mono":
                cams = [int(np.load(os.path.join(seq_dir, "meta.npz"))["mono_cam"])]
            elif a.cams == "all":
                cams = [int(c) for c in np.load(os.path.join(seq_dir, "cameras", "rgb_cameras.npz"))["ids"]]
            else:
                cams = [int(c) for c in a.cams.split(",")]
            for cam in cams:
                key = f"{pair}/{action}/cam{cam}"
                annots[key], report[key] = convert_sequence(seq_dir, cam, layers, a.min_joints_in, a.tol_mm)
                print(key, report[key], flush=True)

    os.makedirs(ANNOT_DIR, exist_ok=True)
    pkl = os.path.join(ANNOT_DIR, f"hi4d_{a.split}.pkl")
    with open(pkl, "wb") as f:
        pickle.dump(annots, f, protocol=pickle.HIGHEST_PROTOCOL)
    commit = subprocess.run(["git", "-C", REPO, "rev-parse", "--short", "HEAD"], capture_output=True, text=True).stdout.strip()
    prov = dict(created=datetime.datetime.now().isoformat(timespec="seconds"), commit=commit, data=a.data,
                pairs=pairs, cams=a.cams, min_joints_in=a.min_joints_in, sequences=report,
                totals=dict(sequences=len(annots), frames=sum(r["frames"] for r in report.values()),
                            person_frames_visible=sum(r["person_frames_visible"] for r in report.values())))
    with open(pkl[:-4] + ".json", "w") as f:
        json.dump(prov, f, indent=1)
    print(f"wrote {pkl}: {prov['totals']}")


if __name__ == "__main__":
    main()
