# Human3R reproduction: setup log (2026-11-13)

## Environment
- Cluster: Arnes HPC (Slurm), node gwn07
- GPU: NVIDIA H100 PCIe, MIG slice 1g.10gb (setup and smoke test only; paper: RTX 4090 for inference
  timing, one 48 GB GPU for training). GPUs of the eval jobs: REPRO_NOTES section 6.
- Python 3.11 (conda env via Mamba/23.11.0-0 module, env at $PROJ/envs/human3r)
- torch 2.5.1+cu124, torchvision 0.20.1+cu124 (pip wheels; README uses conda pytorch-cuda=12.4)
- Full package list: repro/pip_freeze_2026-11-13.txt

## Deviations from the README
1. CUDA toolkit: no 12.4 module on Arnes, so curope (RoPE kernels) was built with
   CUDA/12.6.0 and TORCH_CUDA_ARCH_LIST="7.0;9.0" (V100S + H100).
2. Skipped conda gcc_linux-64/gxx_linux-64; the cluster's module toolchain built everything.
3. gsplat installed from git HEAD (README doesn't pin a commit); used --no-build-isolation.
   Version installed: gsplat 1.5.3 (from the pip freeze).
4. xFormers not installed: DINOv2 falls back to standard attention (slower; results expected equal
   up to float rounding, but not verified, see REPRO_NOTES G18).

## Repo issues found
1. chumpy (git dependency in requirements.txt) fails under pip build isolation
   (setup.py imports pip), and that aborts the whole requirements install.
   Fix: install chumpy with --no-build-isolation, then the rest of requirements separately.
2. requirements.txt is mostly unpinned (REPRO_NOTES G6), so a fresh install today resolves to newer versions:
   - transformers 5.x requires torch >= 2.6 and silently disables itself. Pinned transformers<5.
   - numpy ends up at 1.26.4; keep numpy<2 in all later installs.
   - opencv: requirements pull opencv-python; use opencv-python-headless==4.11.0.86 on headless nodes.
3. scikit-image is imported by viser_utils.py but missing from requirements.txt.
4. huggingface-cli isn't installed by requirements; installed huggingface_hub[cli]
   (the CLI is now called `hf`).
5. fetch_smplx.sh:
   - SMPL and SMPL-X need separate registrations on their respective sites.
   - gdown missing from requirements.
   - The four Google Drive helper files (J_regressor_h36m.npy, smpl_mean_params.npz,
     smplx2smpl.pkl, smplx2smpl_joints.npy) hit Drive's rate limit; downloaded via browser.
   - Newer gdown saves them to src/models/body_models/, so the script's mv lines fail.
     Copied manually: J_regressor_h36m.npy -> src/models/smpl/,
     smplx2smpl.pkl -> src/models/smplx/, the other two -> src/models/.
6. DINOv2 is fetched at runtime from torch hub's facebookresearch/dinov2 main branch
   (unpinned; could change upstream).

## Smoke test
- demo.py on examples/GoodMornin1.mp4, --size 512, --use_ttt3r: PASSED
- 229 frames, inference 211.5 s (0.92 s/frame, ~1.1 FPS) on MIG 1g.10gb, no xFormers, first run
- Not comparable to the paper's speed numbers (1/7 of an H100, no xFormers, warm-up). The paper's
  15 FPS is the ViT-S/672 model; this checkpoint (ViT-L/896) is listed at ~5 FPS (REPRO_NOTES G9).
- Output: camera/ color/ conf/ depth/ smpl/ as per-frame .npz, ~3 MB per frame
- Qualitatively: 3 people tracked with consistent identities, bodies on the floor plane

## Practical things
- Viewer: run demo.py in a job, then VS Code Ports tab -> Forward a Port -> <node>:8080.

## Data preparation (2026-11-15)
- TUM-dynamics (8 freiburg3 seqs) and Bonn (5 seqs) downloaded raw to $PROJ/data/{tum,bonn}/
  (`repro/datasets_download/tum_download.sh`, `bonn_download.sh`; RICH and 3DPW: see the README there).
- Eval subsets built with `python -I repro/datasets_preprocess/prepare_tum_bonn_subsets.py`
  (port of MonST3R + TTT3R preprocessing; frames hard-linked) into $PROJ/data/long_tum/ and
  $PROJ/data/long_bonn/. 72,334 files, 52 s on the login node, ~0 extra disk.
- Protocol ambiguities and upstream quirks found while doing this: see REPRO_NOTES.md.

## Code changes to upstream (all marked `# REPRO`)
1. Dataset paths (2026-11-15). Every `/path/to/...` placeholder in the eval code now reads env var
   `H3R_DATA` (default `<repo>/../data` = $PROJ/data, derived from the file location; no user path
   in code). Files: eval/global_human/metadata.py, eval/relpose/metadata.py,
   eval/video_depth/metadata.py, eval/video_depth/eval_depth.py, eval/dataset/prepare_3dpw.py.
   Mapping: 3DPW/EMDB/RICH/processed_bedlam -> $H3R_DATA/<name>; `tum` and `tum_N` ->
   $H3R_DATA/long_tum; `bonn` and `bonn_N` (launch AND eval_depth) -> $H3R_DATA/long_bonn
   (fixes the inconsistent Bonn roots, REPRO_NOTES B1); sintel -> $H3R_DATA/sintel/training/...
   Not changed: docs/, usage strings, config/trian_human3r.yaml + preprocess_bedlam.py (training).
   Verified: tum (8x90), tum_1000, bonn (5x110), bonn_500 resolve with frames + GT present.
   Caveat: in a job snapshot (`$PROJ/runs/<job>/`) the default would resolve to `$PROJ/runs/data`,
   which does not exist. `repro/slurm/run.sbatch` exports `H3R_DATA` explicitly; set it by hand when
   running anything from inside a snapshot.
2. evo API (2026-11-15). requirements.txt does not pin `evo`; pip installed 1.38.1, whose
   `main_ape.ape()` / `main_rpe.rpe()` no longer accept `est_name=` (the label is read from
   `traj.name`). The first TUM run (job 21558187) crashed with `TypeError: ape() got an unexpected
   keyword argument 'est_name'`. Fix in eval/relpose/evo_utils.py: set `.name = "traj"` on the
   estimated trajectory and drop the 4 `est_name=` kwargs. Label only, no effect on numbers;
   alignment / metric calls unchanged. Tested on the saved sitting_halfsphere prediction before
   resubmitting (eval + plot OK).
3. matplotlib API (2026-11-15). requirements.txt does not pin matplotlib; env has 3.11.2, where
   `matplotlib.cm.get_cmap` no longer exists (removed in 3.9). The first Bonn run (job 21558188)
   crashed in `save_depth_maps -> colorize_np` with `AttributeError: module 'matplotlib.cm' has no
   attribute 'get_cmap'`. Replaced all 8 `cm.get_cmap(cmap_name)` with `mpl.colormaps[cmap_name]`
   (same colormap, checked numerically) in eval/video_depth/utils.py, eval/relpose/utils.py,
   src/dust3r/viz.py, viser_utils.py. Visualisation only; metrics unaffected.
   TUM rerun job 21559068 started on a55c18f (before this fix); its code path never calls colorize.
4. 3DPW annotation script (2026-11-15). The documented command
   `python -m eval.dataset.prepare_3dpw "create_annots()"` fails with `ImportError: cannot import
   name 'SMPLX_DIR' from partially initialized module 'dust3r.smpl_model'` (circular import:
   smpl_model -> dust3r.utils -> smpl_layer -> smpl_model). launch.py is unaffected because it
   imports dust3r.utils first. Fix: one line `import dust3r.utils` before the smpl_model import in
   eval/dataset/prepare_3dpw.py. No effect on the annotations.
5. Hi4D eval support (2026-11-19, extension, not in the paper; additions only, no existing code path
   changed). eval/global_human/metadata.py: new `hi4d` entry (camera-frame metrics only,
   `is_global=False`; annotation file `annots/hi4d_<split>.pkl`, split from env `H3R_HI4D_SPLIT`,
   default `test`) plus `get_seq_hi4d` / `load_view_hi4d`. src/dust3r/smpl_model.py
   `forward_smpl`: new `hi4d` branch that picks the SMPL gender per person on the masked list
   (the `3dpw` branch's indexing, REPRO_NOTES G18 d, would mix up genders in Hi4D's female + male
   frames). Joints: the default branch of `_setup_dataset_config` (24 SMPL joints, pelvis [1, 2],
   as for EMDB). Annotations built by repro/datasets_preprocess/prepare_hi4d.py (self-checks
   against Hi4D's shipped vertices); eval path checked on CPU by repro/checks/check_hi4d_annots.py.
