"""[REPRO] CPU check of the Hi4D eval path (extension), before any GPU run.

Loads annots/hi4d_<split>.pkl through the same functions launch.py uses (metadata.get_seq_hi4d,
metadata.load_view_hi4d) and builds the GT meshes with SMPLModel.forward_smpl('hi4d'), then:
  (1) compares them with Hi4D's own vertices (smpl/<frame>.npz 'verts', world frame) moved into the
      camera with the extrinsics: catches gender mix-ups, person order and camera-convention errors;
  (2) checks that GT joints project inside the image for visible people (2D matching in launch.py
      relies on this);
  (3) writes overlay JPGs (GT vertices projected with the annotation K) for a visual check.

Usage (from the repo root):
  H3R_HI4D_SPLIT=pair00 python repro/checks/check_hi4d_annots.py --out <dir> [--frames_per_seq 3]
"""
import argparse
import os
import sys

import numpy as np
import torch

repo = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, repo)
sys.path.insert(0, os.path.join(repo, "src"))
os.chdir(repo)  # metadata.get_annot and SMPLModel use repo-relative paths

from eval.global_human.metadata import dataset_metadata, get_seq_hi4d, load_view_hi4d  # noqa: E402
import dust3r.utils  # noqa: E402,F401  (import first: dust3r.smpl_model first is a circular import, as in prepare_3dpw.py)
from dust3r.smpl_model import SMPLModel  # noqa: E402

ap = argparse.ArgumentParser()
ap.add_argument("--out", required=True)
ap.add_argument("--frames_per_seq", type=int, default=3)
ap.add_argument("--tol_mm", type=float, default=1.0)
a = ap.parse_args()
os.makedirs(a.out, exist_ok=True)
torch.set_grad_enabled(False)

md = dataset_metadata["hi4d"]
annots = md["get_annot_func"](md["img_path"], md["split"])
seqs, seq_to_images = get_seq_hi4d(md["img_path"], md["split"], annots)
smpl = SMPLModel("cpu", eval_args={"dataset": "hi4d"})
print(f"split={md['split']}: {len(seqs)} sequences; joints: {smpl.j_regressor.shape[0]}, pelvis_idx={smpl.pelvis_idx}")

from PIL import Image, ImageDraw  # noqa: E402

worst = 0.0
for seq in seqs:
    names = seq_to_images[seq]
    files = [os.path.join(md["dir_path_func"](md["img_path"], seq), n) for n in names]
    assert all(os.path.isfile(f) for f in files), f"{seq}: missing image files"
    pick = np.linspace(0, len(files) - 1, a.frames_per_seq).round().astype(int)
    # fake 'images' as prepare_input passes them (no resize: true_shape == ori_shape)
    W, H = annots[seq]["size"]
    views = [{"true_shape": np.array([[H, W]]), "ori_shape": np.array([[H, W]])} for _ in pick]
    views = load_view_hi4d([files[i] for i in pick], views, annots, list(pick))

    smpl_dict = {k: torch.from_numpy(np.stack([v[k] for v in views])) for k in views[0] if "smpl" in k}
    mask = smpl_dict["smpl_mask"]
    verts, joints = smpl.forward_smpl("hi4d", smpl_dict, mask)

    # reference: Hi4D's shipped world-frame vertices -> camera
    T = views[0]["T_w2c"].astype(np.float64)
    seq_dir = os.path.join(md["img_path"], seq.rsplit("/", 1)[0])
    ref = []
    for i, m in zip(pick, mask.numpy()):
        vw = np.load(os.path.join(seq_dir, "smpl", f"{annots[seq]['frames'][i]}.npz"))["verts"]
        ref.append((vw @ T[:3, :3].T + T[:3, 3])[m])
    ref = torch.from_numpy(np.concatenate(ref)).float()
    err = (verts - ref).norm(dim=-1).max().item() * 1000
    worst = max(worst, err)

    K = torch.from_numpy(views[0]["intrinsics"])
    uv = joints @ K.T
    uv = uv[..., :2] / uv[..., 2:3]
    inside = ((uv[..., 0] >= 0) & (uv[..., 0] < W) & (uv[..., 1] >= 0) & (uv[..., 1] < H)).float().mean().item()
    genders = annots[seq]["genders"]
    print(f"{seq}: frames {len(files)}, visible person-frames {int(annots[seq]['visible'].sum())}/{2 * len(files)}, "
          f"genders {genders}, max vertex error vs Hi4D verts {err:.4f} mm, joints inside image {inside:.1%}")

    # overlays
    vuv = verts @ K.T
    vuv = (vuv[..., :2] / vuv[..., 2:3]).numpy()
    h_idx = np.concatenate([np.where(m)[0] for m in mask.numpy()])
    f_idx = np.concatenate([[k] * int(m.sum()) for k, m in enumerate(mask.numpy())])
    colors = {"female": (255, 60, 60), "male": (60, 120, 255)}
    for k, i in enumerate(pick):
        im = Image.open(files[i]).convert("RGB")
        layer = Image.new("RGB", im.size)
        alpha = Image.new("L", im.size, 0)
        dr, da = ImageDraw.Draw(layer), ImageDraw.Draw(alpha)
        for row in np.where(f_idx == k)[0]:
            c = colors[genders[h_idx[row]]]
            for x, y in vuv[row][::3]:
                box = (float(x) - 2, float(y) - 2, float(x) + 2, float(y) + 2)
                dr.ellipse(box, fill=c)
                da.ellipse(box, fill=150)
        im = Image.composite(layer, im, alpha)
        im.save(os.path.join(a.out, f"{seq.replace('/', '_')}_{annots[seq]['frames'][i]}.jpg"), quality=85)

assert worst < a.tol_mm, f"max vertex error {worst:.3f} mm >= {a.tol_mm} mm"
print(f"OK: max vertex error over all checked frames {worst:.4f} mm; overlays in {a.out} (red = female, blue = male)")
