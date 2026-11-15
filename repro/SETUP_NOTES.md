# Human3R reproduction: setup log (2026-11-13)

## Environment
- Cluster: Arnes HPC (Slurm), node gwn07
- GPU: NVIDIA H100 PCIe, MIG slice 1g.10gb (paper used a 48 GB GPU)
- Python 3.11 (conda env via Mamba/23.11.0-0 module, env at $PROJ/envs/human3r)
- torch 2.5.1+cu124, torchvision 0.20.1+cu124 (pip wheels; README uses conda pytorch-cuda=12.4)
- Full package list: notes/pip_freeze_2026-11-13.txt

## Deviations from the README
1. CUDA toolkit: no 12.4 module on Arnes, so curope (RoPE kernels) was built with
   CUDA/12.6.0 and TORCH_CUDA_ARCH_LIST="7.0;9.0" (V100S + H100).
2. Skipped conda gcc_linux-64/gxx_linux-64; the cluster's module toolchain built everything.
3. gsplat installed from git HEAD (README doesn't pin a commit); used --no-build-isolation.
   Version installed: <fill in from `pip show gsplat`>
4. xFormers not installed: DINOv2 falls back to standard attention (same results, slower).

## Repo issues found
1. chumpy (git dependency in requirements.txt) fails under pip build isolation
   (setup.py imports pip), and that aborts the whole requirements install.
   Fix: install chumpy with --no-build-isolation, then the rest of requirements separately.
2. requirements.txt is unpinned, so a fresh install today resolves to newer versions:
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
- Not comparable to the paper's ~15 FPS yet (1/7 of an H100, no xFormers, warm-up)
- Output: camera/ color/ conf/ depth/ smpl/ as per-frame .npz, ~3 MB per frame
- Qualitatively: 3 people tracked with consistent identities, bodies on the floor plane

## Practical things
- Viewer: run demo.py in a job, then VS Code Ports tab -> Forward a Port -> <node>:8080.
## Data preparation (2026-11-15)
- TUM-dynamics (8 freiburg3 seqs) and Bonn (5 seqs) downloaded raw to $PROJ/data/{tum,bonn}/
  (scripts outside the repo: tools/tum_download.sh, tools/bonn_download.sh).
- Eval subsets built with `python -I repro/datasets_preprocess/prepare_tum_bonn_subsets.py`
  (port of MonST3R + TTT3R preprocessing; frames hard-linked) into $PROJ/data/long_tum/ and
  $PROJ/data/long_bonn/. 72,334 files, 52 s on the login node, ~0 extra disk.
- Protocol ambiguities and upstream quirks found while doing this: see REPRO_NOTES.md.
