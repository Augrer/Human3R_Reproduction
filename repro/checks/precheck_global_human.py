"""[REPRO] End-to-end pre-check of eval/global_human/launch.py on a tiny slice, without editing it.

Restricts the dataset table in memory to the given videos and the first --max_frames frames of each,
then runs the unmodified launch.py (same args as run*.sh). Catches crashes in loading, inference,
matching, metrics and result writing before a long job is submitted. Numbers from a pre-check
are NOT report numbers (too few frames, chunk boundaries differ).

Usage (from the repo root, on a GPU node):
  python repro/checks/precheck_global_human.py --dataset rich \
      --videos test/LectureHall_019_wipingchairs1/cam_00 --max_frames 250 -- \
      --weights ./src/human3r.pth --output_dir ./eval_results/prechecks/rich \
      --eval_dataset rich --size 512 --reset_interval 1000000 --use_ttt3r
"""
import argparse
import os
import runpy
import sys

repo = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, repo)

p = argparse.ArgumentParser()
p.add_argument("--dataset", required=True)
p.add_argument("--videos", nargs="+", required=True, help="sequence keys as the dataset uses them")
p.add_argument("--max_frames", type=int, default=250)
ours, launch_args = p.parse_known_args(sys.argv[1:sys.argv.index("--")] if "--" in sys.argv else sys.argv[1:])
launch_args = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []

from eval.global_human.metadata import dataset_metadata  # noqa: E402  (same module object launch.py imports)

md = dataset_metadata[ours.dataset]
orig_seq = md["get_seq_func"]


def restricted(img_path, split, annots):
    # filter the annotations BEFORE the upstream loader, which lists every video's image folder
    # keys are per video (RICH: "test/<seq>/cam_XX") or per image (3DPW: "<seq>/image_XXXXX.jpg")
    vids = set(ours.videos)
    sub = {k: v for k, v in annots.items() if k in vids or k.rsplit("/", 1)[0] in vids}
    found = {k if k in vids else k.rsplit("/", 1)[0] for k in sub}
    assert found == vids, f"unknown videos: {sorted(vids - found)}"
    seq_list, seq_to_images = orig_seq(img_path, split, sub)
    return seq_list, seq_to_images


md["get_seq_func"] = restricted
md["max_frames"] = ours.max_frames
print(f"[precheck] {ours.dataset}: videos={ours.videos} max_frames={ours.max_frames}", flush=True)

sys.argv = [os.path.join(repo, "eval/global_human/launch.py")] + launch_args
runpy.run_path(sys.argv[0], run_name="__main__")
