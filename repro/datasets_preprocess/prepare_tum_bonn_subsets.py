"""Build the TUM-dynamics and Bonn evaluation subsets used by eval/relpose and eval/video_depth.

[REPRO] Not part of upstream Human3R. Human3R's docs/eval.md defers to MonST3R + TTT3R for these
subsets; this file is a faithful port of their four scripts (frame selection logic unchanged):
  MonST3R @574cc77  datasets_preprocess/prepare_tum.py        -> tum      (rgb_90)
  MonST3R @574cc77  datasets_preprocess/prepare_bonn.py       -> bonn     (rgb_110, depth_110)
  TTT3R   @edd6d8c  datasets_preprocess/long_prepare_tum.py   -> tum_N    (rgb_N, N=50..1000)
  TTT3R   @edd6d8c  datasets_preprocess/long_prepare_bonn.py  -> bonn_N   (rgb_N, depth_N, N=50..500)
Deviations (storage/layout only, see repro/REPRO_NOTES.md):
  * frames are hard-linked instead of copied (byte-identical, ~0 extra space); --copy to copy.
  * all subsets of a dataset go into ONE tree, outside the raw data:
      <data>/long_tum/<seq>/{rgb_90,groundtruth_90.txt,rgb_N,groundtruth_N.txt}
      <data>/long_bonn/rgbd_bonn_<seq>/{rgb_110,depth_110,groundtruth_110.txt,rgb_N,depth_N,...}
    (upstream writes rgb_90 / rgb_110 into the raw sequence folders and the long ones into
    long_tum_s1/ and long_bonn_s1/rgbd_bonn_dataset/).
  * Bonn: only the 5 sequences the eval uses (upstream processes every downloaded sequence).
Raw input: <data>/tum/rgbd_dataset_freiburg3_*/ and <data>/bonn/rgbd_bonn_*/ (official layout).

Usage:  python -I repro/datasets_preprocess/prepare_tum_bonn_subsets.py [--data DIR] [--copy]
"""
import argparse
import glob
import os
import shutil

import numpy as np

TUM_LONG = [50, 100, 150, 200, 300, 400, 500, 600, 700, 800, 900, 1000]
TUM_LONG_STRIDE = 1  # TTT3R SAMPLE_INTERVAL ("original 3"); Human3R does not state which it used
BONN_LONG = [50, 100, 150, 200, 250, 300, 350, 400, 450, 500]
BONN_START = 30
BONN_SEQS = ["balloon2", "crowd2", "crowd3", "person_tracking2", "synchronous"]


# --- verbatim from MonST3R/TTT3R (TUM RGB-D benchmark tools) --------------------------------
def read_file_list(filename):
    file = open(filename)
    data = file.read()
    lines = data.replace(",", " ").replace("\t", " ").split("\n")
    list = [[v.strip() for v in line.split(" ") if v.strip() != ""] for line in lines if len(line) > 0 and line[0] != "#"]
    list = [(float(l[0]), l[1:]) for l in list if len(l) > 1]
    return dict(list)


def associate(first_list, second_list, offset, max_difference):
    first_keys = set(first_list.keys())
    second_keys = set(second_list.keys())
    potential_matches = [(abs(a - (b + offset)), a, b)
                         for a in first_keys
                         for b in second_keys
                         if abs(a - (b + offset)) < max_difference]
    potential_matches.sort()
    matches = []
    for diff, a, b in potential_matches:
        if a in first_keys and b in second_keys:
            first_keys.remove(a)
            second_keys.remove(b)
            matches.append((a, b))
    matches.sort()
    return matches
# ---------------------------------------------------------------------------------------------


def put(files, new_dir, copy):
    """Fresh new_dir containing files (same basenames), hard-linked or copied."""
    if os.path.exists(new_dir):
        shutil.rmtree(new_dir)
    os.makedirs(new_dir)
    for f in files:
        dst = os.path.join(new_dir, os.path.basename(f))
        if copy:
            shutil.copy(f, dst)
        else:
            os.link(f, dst)


def write_gt(poses, path):  # same text format as upstream: "stamp tx ty tz qx qy qz qw"
    with open(path, "w") as f:
        for pose in poses:
            f.write(f"{' '.join(map(str, pose))}\n")


def tum(data, copy):
    out = os.path.join(data, "long_tum")
    dirs = sorted(glob.glob(os.path.join(data, "tum", "rgbd_dataset_freiburg3_*") + "/"))
    assert len(dirs) == 8, f"expected 8 TUM sequences, found {len(dirs)}"
    for d in dirs:
        first_list = read_file_list(d + "rgb.txt")
        second_list = read_file_list(d + "groundtruth.txt")
        matches = associate(first_list, second_list, 0.0, 0.02)
        frames = [d + first_list[a][0] for a, b in matches]
        gt = [[b] + second_list[b] for a, b in matches]
        name = os.path.basename(os.path.dirname(d))
        seq_out = os.path.join(out, name)
        # MonST3R prepare_tum.py: stride 3, first 90
        put(frames[::3][:90], os.path.join(seq_out, "rgb_90"), copy)
        write_gt(gt[::3][:90], os.path.join(seq_out, "groundtruth_90.txt"))
        # TTT3R long_prepare_tum.py: stride SAMPLE_INTERVAL, first N
        counts = []
        for n in TUM_LONG:
            sel = frames[::TUM_LONG_STRIDE][:n]
            put(sel, os.path.join(seq_out, f"rgb_{n}"), copy)
            write_gt(gt[::TUM_LONG_STRIDE][:n], os.path.join(seq_out, f"groundtruth_{n}.txt"))
            counts.append(len(sel))
        print(f"tum  {name:42s} matched={len(frames):5d}  rgb_90={len(frames[::3][:90])}  "
              f"rgb_N={dict(zip(TUM_LONG, counts))}")


def bonn(data, copy):
    out = os.path.join(data, "long_bonn")
    for seq in BONN_SEQS:
        d = os.path.join(data, "bonn", f"rgbd_bonn_{seq}") + "/"
        rgb = sorted(glob.glob(d + "rgb/*.png"))
        depth = sorted(glob.glob(d + "depth/*.png"))
        gt = np.loadtxt(d + "groundtruth.txt")
        seq_out = os.path.join(out, f"rgbd_bonn_{seq}")
        # MonST3R prepare_bonn.py: index slice [30:140] of each modality independently
        put(rgb[30:140], os.path.join(seq_out, "rgb_110"), copy)
        put(depth[30:140], os.path.join(seq_out, "depth_110"), copy)
        np.savetxt(os.path.join(seq_out, "groundtruth_110.txt"), gt[30:140])
        # TTT3R long_prepare_bonn.py: [30:30+n], truncated to the shortest modality
        counts = []
        for n in BONN_LONG:
            k = min(len(rgb) - BONN_START, len(depth) - BONN_START, len(gt) - BONN_START, n)
            put(rgb[BONN_START:BONN_START + k], os.path.join(seq_out, f"rgb_{n}"), copy)
            put(depth[BONN_START:BONN_START + k], os.path.join(seq_out, f"depth_{n}"), copy)
            np.savetxt(os.path.join(seq_out, f"groundtruth_{n}.txt"), gt[BONN_START:BONN_START + k])
            counts.append(k)
        print(f"bonn {seq:18s} rgb={len(rgb)} depth={len(depth)} gt={len(gt)}  "
              f"rgb_N={dict(zip(BONN_LONG, counts))}")


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--data", default=os.environ.get(
        "H3R_DATA", "/d/hpc/projects/supv2/yt82121/human3r/data"))
    p.add_argument("--copy", action="store_true", help="copy frames instead of hard-linking")
    a = p.parse_args()
    tum(a.data, a.copy)
    bonn(a.data, a.copy)
