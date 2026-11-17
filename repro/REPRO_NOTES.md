# Reproduction notes: observations, ambiguities and our choices

Running list of points where the Human3R paper (arXiv:2510.06219v2 (HTML version read 2026-11-15), ICLR 2026) and/or the code
(fanegg/Human3R, branch `master` at 402f2b2, as cloned) are unclear, inconsistent, or depend on other repos, plus what we
did about each. Input for the "reproducibility" discussion in the report. Environment/install
problems are in [SETUP_NOTES.md](SETUP_NOTES.md); this file is about **data and evaluation
protocol**.

Status tags: **[paper]** not or not fully specified in the paper · **[code]** code issue or
code/paper mismatch · **[upstream]** behaviour inherited from MonST3R / TTT3R / GVHMR ·
**[ours]** our choice where the authors' choice is unknown.

---

## ⚑ Open items to check

Flagged issues that must be resolved, or explicitly reported as open, before the report. Details in the linked G-item.

### ⚑ F1: 3DPW numbers above Table 1 (unexplained), see G18 (flagged 2026-11-16)

Job 21592963 (commit 42a2d62, H100 SXM, released `human3r_896L.pth`, all 24 sequences, 35,080 matched people):

| mm | PA-MPJPE | MPJPE | PVE |
|---|---|---|---|
| Ours | 44.6 | 72.8 | 86.6 |
| Paper Table 1 | 44.1 | 71.2 | 84.9 |
| Gap | +0.5 | +1.6 | +1.7 |

Pose is nearly identical (small PA gap); most of the difference is in size / scale (root-aligned metrics). TUM and Bonn reproduce to the last digit with the same environment and checkpoint (on H100 PCIe; 3DPW and RICH ran on H100 SXM), so the cause is specific to the human branch or to 3DPW.

**Ruled out**
- GT set: 24 sequences, 24,547 frames, 35,515 person-frames (standard 3DPW test size); prep = upstream + import fix only (G14).
- Protocol: 14 H36M joints as in "3DPW (14)"; full sequences; `run.sh` arguments (reset 100, size 512, TTT3R).
- DINOv2 torch-hub drift: no ViT-L forward change since 2024 (checked the dinov2 git history).
- Upstream female-GT indexing bug in `SMPLModel.forward_smpl`: never triggers, because all 3DPW test subjects are labelled `m` in the official files.
- Precision / framework: fp32 inference; torch 2.5.1 as the authors used.
- GPU variant and run-to-run noise, for 18 of 24 sequences (found 2026-11-17 in the audit): the timed-out first run (job 21569212, **H100 PCIe**, gwn03, commit 3e97ce8 with `eval/` and `src/` identical to 42a2d62, images read from CephFS instead of the staged copy) finished 18 sequences. Against job 21592963 (**H100 SXM**) every per-sequence PA-MPJPE / MPJPE / PVE agrees within 0.1 mm (the log's rounding); the matched-people count differs by 1 in one sequence (`downtown_walking_00`, 2593 vs 2594), so the runs are not bit-identical; the n_human-weighted means over the 18 are equal to 0.01 mm (46.27 / 75.32 / 89.68 in both). Noise of this kind is therefore ≤ 0.1 mm, far below the 0.5–1.7 mm gap. Missing from the comparison: `downtown_weeklyMarket_00`, `downtown_windowShopping_00`, `flat_guitar_01`, `flat_packBags_00`, `office_phoneCall_00`, `outdoors_fencing_01` (covered by the rerun below).
- Averaging: the unweighted mean over the 24 sequences is 43.6 / 72.7 / 86.2, which does not match Table 1 either (PA below the paper, the other two above), so a different weighting does not explain the gap.

**Still open**
- [ ] Run-to-run repeatability: identical H100 rerun **queued 2026-11-17, job 21623368** (same command and arguments, same H100 SXM type, eval code identical to 42a2d62, fresh folder `3dpw_human3r_rerun1`). If it moves ~1 mm, the gap is noise; if it is bit-identical, noise is ruled out. (Also closes the G17 repeatability question.) The PCIe-vs-SXM comparison under "Ruled out" already bounds this at ≤ 0.1 mm for 18 sequences; the rerun adds the other 6 and the same-GPU case.
- [ ] GPU-numerics sensitivity: TF32-off run **queued 2026-11-17, job 21623935** (`NVIDIA_TF32_OVERRIDE=0`, otherwise identical, folder `3dpw_human3r_tf32off`). Check on MIG beforehand (vs float64, 2048² matmul / 3×3 conv): TF32 as configured max error 7.5e-2 / 3.5e-2, with the override 4.8e-4 / 1.2e-4, so **all our evals so far ran matmuls and convolutions in TF32** (`croco.py` sets matmul TF32; cuDNN conv TF32 is PyTorch's default). The authors' RTX 4090 also uses TF32, with different hardware rounding. Optionally later: with xFormers (not installed here, so DINOv2 uses plain attention).
- [ ] Checkpoint identity: is the released checkpoint the one behind Table 1? Only the authors can answer (possible comment on upstream issue #11; not posted).
- [x] Re-check after RICH is merged (2026-11-17): RICH reproduces Table 2 (110.0 / 184.4 / 3.3 vs 110.0 / 184.9 / 3.3), so the human branch as a whole reproduces; the gap looks 3DPW-specific (e.g. the multi-person matching or the 3DPW GT path, `forward_smpl` 3DPW branch / H36M regressor, used only by 3DPW).

**Not usable as reference:** upstream issue #4 (44.3 / 71.9 / 85.7), whose 60,838 "Total Humans" vs our 35,080 indicates a contaminated output folder (G15).

### ⚑ F2: Other open items (short)
- [x] RICH: merged 2026-11-17, 191/191 videos, matches Table 2 (section 7).
- [x] G17: MIG `bonn_500` scored (job 21612587); drift grows with length but stays at the last reported digit (G17).
- [ ] G17: H100 run-to-run repeatability: answered by the F1 rerun (job 21623368, queued).
- [ ] Traceability: the 2026-11-15 review that the claims list (section 0) is based on is not in the repo or under `$PROJ`. Add it, or state that the list was re-derived from the paper (C1–C7 numbers and G11 values have since been checked against the paper text and the code).
- [ ] Traceability: the TF32 pre-check cited in F1 was run from `$PROJ/logs/_tf32check.py`, which is outside the repo and has no job log; move it to `repro/checks/` and record node and output.
- [x] Artifact completeness (2026-11-17): the data scripts are now in `repro/datasets_download/` (TUM, Bonn, RICH single-connection download, RICH extraction, archive SHA256 list), with paths from `H3R_DATA` and no usernames, credentials or data. Not published: the 2-connection RICH downloader and the login diagnostics (they stay in `$PROJ/tools/`), and `notes/decisions.md`.

---

## 0. Paper claims and what we test

Status as of 2026-11-17. ✅ reproduced · ⏳ running/queued · 🔜 planned · ⛔ blocked · ✗ not testable by us.
Claim list follows the 2026-11-15 Fable review (file not in the repo, see F2); C1/C2 numbers checked against the PDF. Table numbering re-checked 2026-11-17 against the paper text: Table 3 = main-paper ablation (prior, naive baseline, TTT3R; EMDB-2), Table 4 = FPS per dataset, Tables 5–7 = runtime breakdown, Table 8 = prior / backbone ablation with FPS, Table 9 = comparison with Multi-HMR across resolutions, Table 10 = multi-task ablation, Table 11 = feature resolution.

| # | Claim (paper) | Status | Evidence / plan |
|---|---|---|---|
| C1 | Local human mesh, Table 1: 3DPW 44.1 / 71.2 / 84.9 and EMDB-1 48.5 / 73.9 / 86.0 (PA-MPJPE / MPJPE / PVE, mm) | ≈ 3DPW (0.5–1.7 mm above paper) · ⛔ EMDB-1 | 3DPW job 21592963 (all 24 seqs): 44.6 / 72.8 / 86.6, section 7; gap not yet explained (G18). EMDB access requested 2026-11-12. |
| C2 | Global human motion, Table 2: RICH 110.0 / 184.9 / 3.3 and EMDB-2 112.2 / 267.9 / 2.2 (WA-MPJPE / W-MPJPE mm / RTE %) | ✅ RICH · ⛔ EMDB-2 | RICH as 4 parts, merged with upstream averaging (G15, G16). All 4 parts done and merged (191/191 videos): **110.0 / 184.4 / 3.3**, section 7. |
| C3 | Camera pose, Fig. 9a: Human3R ATE on TUM-D, lower than TTT3R and CUT3R | ✅ Human3R curve · 🔜 comparison | Section 7: all 12 lengths match. Baseline curves not yet run. |
| C4 | Video depth, Fig. 9b and Table 10: Bonn metric-scale Abs Rel / δ<1.25 | ✅ Human3R curve and Table 10 · 🔜 comparison | Section 7: all 10 lengths match; Table 10 = `bonn_100` metric exactly (G4). |
| C5 | Real-time: 15 FPS on an RTX 4090, 8 GB, speed independent of the number of people | 🔜 partly | 15 FPS is the ViT-S/672 model (G9), not downloaded yet; no 4090 here, report H100 inference-only timing (G16). Reference values per dataset: Table 4 (RTX 4090): ViT-S/672 13.6–15.9 FPS, ViT-L/896 5.1–5.4 FPS. People-count dependence: CMU Panoptic extension. |
| C6 | Training: 1 day on one 48 GB GPU, BEDLAM, CUT3R and Multi-HMR frozen | ✗ for now | Needs BEDLAM + retraining; scope decision pending. |
| C7 | Ablations (Tables 3, 8–11) | 🔜 partly | Backbone / resolution: the four released checkpoints (inference only). "w/o TTT3R": drop the flag. Naive CUT3R+Multi-HMR baseline: code path `--is_naive`, needs CUT3R and Multi-HMR weights and an undocumented config. "w/o prior", cross-attention, joint decoder: need retraining. |
| C8 | Robust to crowds, tracking, truncation | ✗ in paper (qualitative only) → 🔜 extension | CMU Panoptic crowd protocol (notes/extension_ideas.md). |
| C9 | "Mutual benefit": human prompt tuning also improves scene reconstruction | 🔜 | Needs TTT3R / CUT3R baselines on our subsets and the reset control (G10). |

## 1. General

| # | Observation | Our handling |
|---|---|---|
| G1 | **[code]** No data-root option. All dataset paths are hard-coded `/path/to/...` placeholders in `eval/*/metadata.py`, `eval/video_depth/eval_depth.py` and `eval/dataset/prepare_3dpw.py`. | **Done** (2026-11-15): env var `H3R_DATA`, default `<repo>/../data`, one marked `# REPRO:` constant per file; see SETUP_NOTES "Code changes". |
| G2 | **[paper]** For camera pose and video depth, the paper only says "following prior works [12, 97]". Frame selection, start frame, stride and sequence lengths are not given. The results are shown as **plots over sequence length**, not tables, so the comparison has to be against read-off curve values. | Follow the code's dataset lists (`run.sh`) and the upstream preprocessing (sections 2 and 3). |
| G3 | **[code] vs [paper]** The paper says "the state is reset every 100 frames". The scripts set it per benchmark: 100 for 3DPW / EMDB-1 (`global_human/run.sh`) and TUM (`relpose/run.sh`), **50** for EMDB-2 (`run_emdb2.sh`), effectively never for RICH (`run_rich.sh`, 1e6) and Bonn (`video_depth/run.sh`, 1e9). | Run as in the scripts (which presumably produced the published numbers); report the per-benchmark table; reset ablation planned (see G10). |
| G4 | **[paper]** The Bonn numbers in Table 10 (Abs Rel 0.086, δ<1.25 95.4) do not say which Bonn variant, length or alignment was used. | **Resolved (2026-11-15):** our `bonn_100` **metric-scale** result is exactly 0.0860 / 95.4. Table 10 = metric depth, 100 frames. |
| G5 | **[code]** Checkpoint name mismatch: the README downloads `src/human3r_896L.pth`, but all five eval scripts (`eval/global_human/run.sh`, `run_emdb2.sh`, `run_rich.sh`, `eval/relpose/run.sh`, `eval/video_depth/run.sh`) load `./src/human3r.pth`. | Symlink `src/human3r.pth -> human3r_896L.pth` (gitignored); scripts unchanged. |
| G6 | **[code]** `requirements.txt` gives an exact version for only 6 of its 28 distinct packages (numpy, pillow, pyrender, pyvista, spaces, the chumpy commit; `pyglet<2` and `huggingface-hub>=0.22` are only bounds; torch, matplotlib etc. are open, and evo comes from a separate unpinned `pip install evo` in the README), and the evals crash with current versions of two libraries, both only at the very end of a run: **evo** 1.38.1 (`main_ape.ape()` / `main_rpe.rpe()` no longer take `est_name=`) in TUM scoring, and **matplotlib** 3.11.2 (`cm.get_cmap` removed in 3.9) in the coloured depth maps that `video_depth/launch.py` saves before Bonn scoring. The authors' versions are unknown, so a fresh install today cannot run the published scripts unmodified. Library changes that alter numbers without crashing would go unnoticed. | Minimal `# REPRO` fixes that only touch labels and colours (SETUP_NOTES code changes 2 and 3, commits a55c18f and 452e340). Exact versions are in `pip_freeze_2026-11-13.txt`. Report as a reproducibility issue. |
| G7 | **[code]** Both `run.sh` use `set -e` and loop over all sequence lengths, and a crash in one sequence's *visualisation* (Bonn saves a coloured depth and confidence PNG per frame as part of the eval) aborts the whole sweep, including all later sequence lengths. | Fixed the crashes rather than changing the scripts. A rerun starts from scratch (we delete the partial output dir first). |
| G8 | **[paper]** Table 10 header is mislabelled in the PDF: it reads PA-MPJPE / MPJPE / PVE and WA-MPJPE / W-MPJPE, but the values are in reverse order (84.9 / 71.2 / 44.1 and 267.9 / 112.2, cf. Tables 1, 2). | Read by value, not by header; report it. |
| G9 | **[paper]** Speed and accuracy headlines come from different models: Tables 1–2 use ViT-L/896 (5 FPS in Table 8; 5.1–5.4 by dataset in Table 4), the 15 FPS claim is ViT-S/672 (EMDB-2 WA-MPJPE 129.9, Table 8). Sec. A.5 says "approximately WA-MPJPE 100" for that setting, which does not match 129.9. | Report speed per checkpoint; compare our ViT-L/896 timing to 5 FPS, not 15. |
| G10 | **[ours] hypothesis, untested** In Fig. 9a, Human3R and TTT3R appear to coincide up to 100 frames and separate from 150, where the first state reset takes effect; on Bonn (no reset) they differ by ≤ ~0.003 Abs Rel. The TUM gain attributed to human prompt tuning ("mutual benefit") may partly come from the reset. | Planned control: TUM and Bonn with reset 100 vs none, with and without TTT3R, plus TTT3R/CUT3R baselines under the same subsets. |
| G11 | **[paper]** Not stated in the paper, only in code/config: the dataset behind Table 9, Fig. 12 and Table 11 (code suggests the BEDLAM test split); the human detection threshold (0.3, hard-coded in `src/dust3r/model.py`, `apply_threshold(0.3, …)`) and 2D matching (greedy, IoU ≥ 0.05, `global_human/utils.py`); training settings (40 epochs × 4000 samples, weight decay 0.05, 5 warm-up epochs, seed 0; `config/trian_human3r.yaml`). Code values verified 2026-11-17. The paper does give batch size 8, 4 frames per sequence, AdamW, learning rate 1e-4 (Sec. C), which match the config. | Cite the code values in the report. |
| G12 | **[code]** `global_human/launch.py` catches out-of-memory errors (and "Degenerate covariance rank" / "Eigenvalues did not converge") per sequence, writes one line to `_error_log_*.txt`, and **continues**; the final averages are taken over the remaining sequences. A video that runs out of memory (more likely for long RICH / EMDB videos with no reset) silently drops out of the reported number. | After every global-human run, grep the error logs for `OOM` / `Exception` and report the number of evaluated videos (RICH: 191 expected). |
| G13 | **[code]** The eval summary (`get_summary_log`, `global_human/utils.py`) labels the global metrics "(cm)". The code computes W-/WA-MPJPE in **mm** (`m2mm = 1000`), RTE in **%** (root error after rigid alignment without scale, divided by the total GT displacement, × 100), jitter in 10 m/s³ (÷ 10) and foot sliding in mm, which matches the paper's text (Sec. 4.2: mm; RTE in %). | **Resolved (2026-11-16):** cosmetic label error only; report mm / %. |
| G14 | **[code]** The 3DPW preparation command given in `docs/eval.md` does not run as published (circular import in `prepare_3dpw.py`, job 21562622). Together with G1, G5, G6 this means none of the documented eval paths ran unmodified on a fresh install. | One-line import-order fix (SETUP_NOTES code change 4). |
| G15 | **[code]** `global_human/launch.py` computes its final numbers from **every `.txt` file in the output folder** (`process_directory`: n_human-weighted mean over all per-video lines), and per-video lines are appended, never overwritten. Re-running into an existing output folder therefore counts earlier videos twice. | Always use a fresh output folder; partial folders are renamed, not reused. Split runs are merged with the same upstream functions (`repro/merge_global_human.py`), which gives the same number as one run. |
| G16 | **[ours] compute** The human-mesh evals were bound by image reading, not the GPU: `launch.py` reads a video's images one at a time, which on our CephFS ran at ~4 images/s (GPU at 0 %). RICH (106k frames) would have needed ~29 h; 3DPW hit its 4 h limit after 18/24 sequences. 32 parallel readers gave ~25 images/s. | Jobs copy their images to node-local disk first (`repro/slurm/stage_local.sh`, data unchanged, `H3R_DATA` points at the copy); RICH runs as 4 jobs over fixed video lists (`repro/splits/rich_chunk*.txt`) and is merged. Report staging and inference time separately. Staging takes 4–5 min (2.1 GB for 3DPW, 51–54 GB per RICH part). Bug fixed 2026-11-16: the parallel `cp --parents` calls raced on creating shared parent folders (`cannot make directory …: File exists`, job 21592959). The script now creates the directory tree first. |
| G17 | **[ours] hardware** MIG 1g.10gb vs full H100 (job 21596637 vs 21559168, `bonn_50`, same commit code, same checkpoint): depth maps **not bit-identical** (median relative pixel difference 1.1e-4, p99 4.2e-3; 0.35 % of pixels > 1 %, likely depth edges), growing along the sequence (≈3e-5 at frame 0 → 2–8e-4 at frame 50) as the recurrent state accumulates float differences. Metrics agree to ≤ 1.2e-4 (scale Abs Rel 0.076907 vs 0.076882; metric 0.084595 vs 0.084592; metric δ<1.25 0.95395 vs 0.95407). | Headline numbers on full H100 only. MIG allowed for ablations if all compared variants run on MIG, labelled. **`bonn_500` (2026-11-17, MIG job 21597188 inference, scored on V100S job 21612587):** differences grow with length but stay at the reported precision: scale Abs Rel 0.07603 vs 0.07648 (−4.5e-4), metric Abs Rel 0.09869 vs 0.09883 (−1.4e-4), metric δ<1.25 92.66 vs 92.78 % (−0.12 pp); at the paper's rounding only the δ last digit can flip. Scoring of `bonn_500` needs ~25 GB GPU memory (OOM on the 10 GB slice). Still open: H100 run-to-run repeatability. |
| G18 | **[ours] result** 3DPW (job 21592963) is consistently a little above Table 1: PA-MPJPE 44.6 vs 44.1, MPJPE 72.8 vs 71.2, PVE 86.6 vs 84.9 mm. The gap is smallest after Procrustes alignment (+0.5) and larger on root-aligned MPJPE / PVE (+1.6 / +1.7), so pose is near-identical and the difference sits mostly in size / scale. **Checked and ruled out (2026-11-16):** (a) GT set: our `3dpw_test.pkl` has 24 sequences, 24,547 frames, **35,515 person-frames** (the standard 3DPW test count); our prep differs from upstream only by the import fix (G14). (b) Protocol: 14 H36M joints (`J_regressor_h36m`), matching "3DPW (14)" in Table 1; full sequences, subsample 1, `run.sh` arguments; the paper gives nothing more ("following [3, 100]"). (c) DINOv2 torch-hub code (unpinned, we got HEAD 7764ea0 of 2026-06-03): no change to the ViT-L forward pass since 2024; the 2024 interpolation fix (e1277af) gives identical output with the default `interpolate_offset=0.1`. (d) Gender handling: `SMPLModel.forward_smpl` has a female-GT indexing bug for 3DPW (index from `torch.where(...)[1]` is the person slot, used on the flattened person list), but it never triggers: **all 3DPW test subjects are labelled `m`** in the official sequence files (train / validation do have `f`). (e) Precision: eval inference is fp32 (autocast disabled); torch 2.5.1 as tested by the authors (upstream issue #3). **Reference point:** upstream issue #4 (Oct 2025) posts a released-checkpoint 3DPW run on an A6000: 44.3 / 71.9 / 85.7, precision 71.1, recall 98.8, but with "Total Humans: 60838" vs our 35,080. That suggests their folder mixed a crashed multi-GPU attempt with the single-GPU run (the G15 effect), so it is not a clean reference. Upstream issue #11 (retraining gap) was answered with "GPU model, random seeds". **Remaining candidates:** GPU-dependent numerics (`croco.py` sets `torch.backends.cuda.matmul.allow_tf32 = True` at import, so H100 and RTX 4090 both run TF32 matmuls with hardware-specific rounding; no xFormers here, so DINOv2 uses plain attention), run-to-run nondeterminism, or a released checkpoint that differs from the one behind Table 1. | Open. Report as is with the gap and this list. Next tests: an identical H100 rerun (repeatability, also G17) and a TF32-off or other-GPU run (sensitivity). |
| G19 | **[code]** The summary's detection precision / recall / F1 are not dataset-level rates. `compute_prf1` rounds each video's value to a whole percent, and the summary is the mean of those values weighted by the number of *matched* people (`extract_metrics`), which favours videos with high recall. The error metrics are likewise weighted means of per-video values rounded to 0.1 mm. From the counts (assuming every labelled person-frame is evaluated): 3DPW 35,080 matched of 35,515 = 98.8 % (log: 98.9 %); RICH 104,468 of 106,446 = 98.1 % (log: 98.6 %). | Report matched / labelled counts next to the logged recall (refines R4). Found 2026-11-17. |
| G20 | **[ours] hardware** RICH on H100 PCIe vs SXM, 4 videos (cancelled job 21568115, PCIe gwn04, vs the same videos in the SXM parts; same eval code): per-video WA-MPJPE differs by 0.1–0.6 mm and W-MPJPE by 0–0.9 mm, camera-frame PA-MPJPE / MPJPE by ≤ 0.1 mm. RICH runs without state reset, so float differences accumulate (same pattern as G17), whereas 3DPW with reset 100 stays within 0.1 mm (F1). | Our RICH W-MPJPE of 184.4 vs the paper's 184.9 is within this hardware spread. Only 4 of 191 videos, so indicative. Found 2026-11-17. |

## 2. TUM-dynamics (camera pose, `eval/relpose`)

Built with [`datasets_preprocess/prepare_tum_bonn_subsets.py`](datasets_preprocess/prepare_tum_bonn_subsets.py),
a faithful port of MonST3R@574cc77 `prepare_tum.py` and TTT3R@edd6d8c `long_prepare_tum.py`.
Raw data: the 8 freiburg3 `sitting_*` / `walking_*` (`static`, `xyz`, `halfsphere`, `rpy`) sequences,
the same list as MonST3R's `data/download_tum_dynamics.sh`.

| # | Observation | Our handling |
|---|---|---|
| T1 | **[code]** `rgb_90` / `groundtruth_90.txt` (dataset `tum`) and `rgb_N` (dataset `tum_N`) are not raw TUM content, and nothing in this repo creates them. `docs/eval.md` defers to MonST3R (download) and TTT3R (prepare). | Ported the upstream scripts (see above). |
| T2 | **[upstream]** `tum`: RGB frames are matched to GT poses by timestamp (TUM `associate`, max 0.02 s), then every 3rd matched frame is taken, first 90. | Unchanged. Verified that all subsets have \|t_rgb − t_gt\| < 0.02 s. |
| T3 | **[paper]/[upstream]** `tum_N`: TTT3R's script uses stride `SAMPLE_INTERVAL = 1`, with the comment "original 3", and writes `long_tum_s1/` (TTT3R names these `tum_s1_N`). Human3R expects `long_tum/` and never states the stride. With stride 1, `tum_N` covers N/30 s of video; with stride 3, 3× longer. | **[ours]** stride 1 (current TTT3R script). Possible check: if our TTT3R baseline curve matches the one in the paper's figure, stride 1 is confirmed. **Supported 2026-11-15:** with stride 1 our ATE matches Fig. 9a at all 12 lengths (section 7). |
| T4 | **[upstream]** Several sequences are shorter than the longest N. Matched frames: sitting_static 703, walking_static 740, sitting_rpy 817, walking_xyz 857, walking_rpy 906, the rest ≥ 1064. So `tum_800` … `tum_1000` silently contain fewer frames for those sequences, and `tum_1000` is really a mix of 703–1000-frame sequences. | Unchanged; state it in the report next to the curves. |
| T5 | **[code]** `pred_traj.txt` is written as `t x y z qw qx qy qz` (wxyz, `save_trajectory_tum_format`), but standard TUM order is `qx qy qz qw`. The metrics use the in-memory poses, so the numbers are not affected, but re-reading saved predictions with evo / TUM tools gives wrong rotations (RPE rot, plots). | Note only; when re-evaluating from files, reorder the quaternion first. |

## 3. Bonn RGB-D Dynamic (video depth, `eval/video_depth`)

Same script, porting MonST3R@574cc77 `prepare_bonn.py` and TTT3R@edd6d8c `long_prepare_bonn.py`.
Raw data: only the 5 sequences the eval uses (`balloon2`, `crowd2`, `crowd3`, `person_tracking2`,
`synchronous`). MonST3R downloads all of `rgbd_bonn_dataset.zip`, but the code only ever reads
these 5.

| # | Observation | Our handling |
|---|---|---|
| B1 | **[code]** Inconsistent roots. `video_depth/launch.py` reads plain `bonn` from `<rgbd_bonn_dataset>/rgbd_bonn_<seq>/rgb_110`, but `eval_depth.py` reads `rgb_110` + `depth_110` **and** all `rgb_N`/`depth_N` from `<long_bonn>/rgbd_bonn_<seq>/`. Upstream writes the 110 subset into the raw folders and the long ones elsewhere, so following the docs literally makes `eval_depth.py` fail to find the GT for `bonn`. | All Bonn subsets go in one tree, `data/long_bonn/`; point both roots at it. |
| B2 | **[upstream]** Frames are chosen **by index in the sorted file list, not by timestamp**: rgb, depth and GT rows are each sliced `[30:140]` (`bonn`) or `[30:30+N]` (`bonn_N`) independently. In `crowd3` the camera dropped depth frames (854 rgb vs 847 depth), so rgb/depth pairs drift apart by up to **0.10 s** within `bonn` and **0.21 s** by frame 530 (`bonn_500`). The other 4 sequences stay ≤ 0.017 s. The "GT depth" for part of crowd3 therefore belongs to a slightly different image. | Reproduce as-is (it is what the published numbers are based on). Possible extension: timestamp-associated variant to measure the effect. |
| B3 | **[upstream]** GT pose rows are also index-sliced, not time-associated (471 GT rows vs 469 frames in balloon2, etc.). Irrelevant for video depth (depth only), but matters if anyone evaluates Bonn poses (`eval/relpose` has a `bonn` entry). | Note only. |
| B4 | **[upstream]** Short sequences: `bonn_N` is truncated to the available frames: balloon2 gives 439 for N ≥ 450, synchronous gives 302 for N ≥ 350. | Unchanged; state it in the report. |
| B5 | **[upstream]** The first 30 frames are always skipped ("following DepthCrafter", MonST3R docs); there is no reason given in the Human3R paper. | Unchanged. |

## 4. Human mesh / motion datasets

| # | Observation | Our handling |
|---|---|---|
| R1 | **[paper]** RICH image format is not stated. The RICH site offers test PNG (~3 TB, per-sequence scripts) or JPG (`JPG_images/test.tar.gz`, 242.6 GB). JPG compression can slightly change the numbers. | **[ours]** JPG (practical). Flag it. |
| R2 | **[code]** The Google Drive link for `rich_test_labels.pt` in `docs/eval.md` actually serves GVHMR's `RICH_hmr4d_support.tar.gz` (labels + a 459 MB `rich_test_preproc.pt`). | Extracted only `rich_test_labels.pt`. |
| R3 | **[upstream]** GVHMR RICH labels: `frame_id` indexes the **sorted listing** of each `cam_XX` folder and does not start at 0, so the folder must contain the full frame sequence, or frames silently shift. Labels cover 191 videos (50 sequences, 106,446 frames). | Extract complete cam folders; check counts after extraction. **Done 2026-11-15:** 191 folders / 114,264 jpeg extracted, every file size-checked against the archive listing; for all 191 videos every `frame_id` falls inside the sorted listing and the indexed frames are distinct and increasing (106,446 labelled frames). |
| R4 | **[paper]/[code]** EMDB and RICH: "we divide each sequence into 100-frame segments" (following GVHMR/TRAM). In the code, errors are computed **only on matched detections** (`match_2d` then 3D metrics on `bestMatch`, `global_human/launch.py`), and the 100-frame chunks are cut over the stack of matched frames (`global_human/utils.py`), so missed frames shift the chunk boundaries. | Closed with this caveat: report detection recall (logged by the eval) next to every error. |

## 5. Storage-only deviations (no effect on results)

- Derived frame subsets are **hard links** to the raw frames (byte-identical, ~0 extra space;
  upstream copies). `--copy` gives real copies.
- Derived subsets live in `data/long_tum/` and `data/long_bonn/` (one tree per dataset), not inside
  the raw sequence folders.
- Each raw archive is kept with SHA256 checksums in `data/_archives/<dataset>/` (outside the repo).

## 6. Running the evals (log)

Every run (until 2026-11-15 afternoon): `sbatch --job-name=<name> repro/slurm/run.sbatch bash eval/<task>/run.sh`; from then on `bash repro/slurm/submit.sh <name> bash eval/<task>/run.sh`, one full
H100 (80 GB), `H3R_DATA=$PROJ/data`, checkpoint `human3r_896L.pth` via the G5 symlink. The H100 variant
differs between jobs: PCIe (gwn03 / 04 / 06) for everything up to 2026-11-15 (TUM, Bonn, the timed-out
3DPW and cancelled RICH runs), SXM ("H100 80GB HBM3", gwn10) for the 3DPW and RICH results; see F1 and
G20 for the measured effect. Logs: `$PROJ/logs/<name>_<jobid>.out` (node, GPU, commit, command, runtime;
gwn10 writes timestamps in UTC, the other nodes in CET). Results:
`$PROJ/outputs/eval_results/` (outside the repo, reached via the gitignored `eval_results` link).

| Date | Job | Eval | Commit | Outcome |
|---|---|---|---|---|
| 2026-11-15 | 21558187 | TUM camera pose | 9025e2a | Crashed after the first sequence's inference (`sitting_halfsphere`, 90 frames), in scoring: evo `est_name` (G6). Runtime 23 min. |
| 2026-11-15 | 21558188 | Bonn video depth | 9025e2a | Crashed after the first sequence's inference (`balloon2`, 110 frames), in `save_depth_maps`: matplotlib `get_cmap` (G6). Runtime 11 min. |
| 2026-11-15 | 21559068 | TUM camera pose | a55c18f (logged) | **Done**, exit 0, 253 min, H100 PCIe (gwn03), 8/8 sequences in all 13 sets. **Provenance caveat:** the job started 12:34:03 and `eval/relpose/utils.py` changed at 12:34:26 (matplotlib fix, 452e340); each subset starts a fresh Python process, so at least `tum_50` onward ran 452e340 code. Only the colour-map line differs and the camera-pose path never calls `colorize`, so the numbers are unaffected. Lesson: see the snapshot rule below. |
| 2026-11-15 | 21559168 | Bonn video depth | c5e94f3 | **Done**, exit 0, 118 min, H100 PCIe (gwn06), clean tree (code identical to 452e340), 5/5 sequences in all 11 sets, no errors. |
| 2026-11-15 | 21568115 | RICH global motion (`run_rich.sh`, 191 videos) | 52fc487 | Submitted 18:24 via `submit.sh` (snapshot `runs/rich_eval_52fc487_…`), H100, 20 h limit. |
| 2026-11-15 | 21569212 | 3DPW local mesh (`launch.py` with the `run.sh` arguments, `--eval_dataset 3dpw` only; `run.sh` would continue to EMDB-1, which we lack) | 3e97ce8 | Submitted 19:07 via `submit.sh`, H100, 4 h limit. Annotations: `3dpw_test.pkl` (24 seqs, 24,547 frames; job 21563583). Pre-check 21568279 passed. |
| 2026-11-15 | 21569212 (3DPW) / 21568115 (RICH) | | | **3DPW: TIMEOUT** at 4 h after 18/24 sequences; **RICH: cancelled** after 1 h 05 min (4/191 videos; projected ~29 h). Cause: G16. (RICH waited in the queue until 2026-11-16 10:25 and was cancelled at 11:31.) Both ran on H100 PCIe (gwn03 / gwn04). Partial folders kept as `3dpw_human3r_timeout_21569212` and `rich_human3r_cancelled_21568115`: not used for results, but used as PCIe-vs-SXM comparisons (F1, G20). |
| 2026-11-16 | 21592959–62 | RICH, 4 parts (`repro/splits/rich_chunk{0..3}.txt`, 47–48 videos / ~26.6k frames each), staged to local disk, `precheck_global_human.py` harness without `--max_frames` (full videos), `run_rich.sh` arguments | 42a2d62 | Submitted 11:40, H100, 8 h each. Merge with `repro/merge_global_human.py --expect 191`. |
| 2026-11-16 | 21592963 | 3DPW, all 24 sequences, fresh output folder, staged to local disk, `run.sh` arguments | 42a2d62 | Submitted 11:40, H100, 8 h. |
| 2026-11-16 | 21596637 | MIG equivalence check: `bonn_50` (`video_depth/run.sh` args) on MIG 1g.10gb | f6aa318 | Done, 25 min. Not bit-identical, metrics within 1.2e-4 (G17). Output `eval_results/mig_check/`. |
| 2026-11-16 | 21592959 | RICH part 0 | 42a2d62 | **Failed** after 4 min (exit 123), before inference: staging race in `stage_local.sh` (G16). No output folder created. Resubmitted after the fix (below). |
| 2026-11-16 | 21592960–62 | RICH parts 1–3 | 42a2d62 | **Done**, exit 0, 165 / 158 / 160 min, H100 SXM (gwn10), 47 + 48 + 48 videos, no OOM or exception lines. Staging 233–283 s each, peak GPU memory 7.6 GB. Per-part numbers are not report numbers (merge pending part 0). |
| 2026-11-16 | 21592963 | 3DPW | 42a2d62 | **Done**, exit 0, 165 min, H100 SXM (gwn10), 24/24 sequences, no OOM or exception lines. Staging 222 s, peak GPU memory 7.7 GB. Result in section 7 (G18). |
| 2026-11-16 | 21597188 | MIG drift check: `bonn_500` (`video_depth/run.sh` args) on MIG 1g.10gb | 1db8a89 | Inference **done** for 5/5 sequences (47 min); then **OOM in `eval_depth.py`** (`depth_evaluation`, 10 GB slice). Depth maps are kept in `eval_results/mig_check/bonn_500_human3r/`; only the scoring is rerun on a bigger GPU (below). |
| 2026-11-16 | 21612586 | RICH part 0 resubmitted (same command and arguments as parts 1–3, fresh output folder `rich_human3r_part0`) | cb31dfa | Submitted 22:50, H100, 8 h. Code differs from 42a2d62 only in `stage_local.sh` and notes, so the eval code is identical to parts 1–3. After it finishes: `merge_global_human.py --expect 191` over the 4 parts. |
| 2026-11-16 | 21612587 | `bonn_500` MIG drift check, scoring only: `eval_depth.py --align scale` and `--align metric` on the MIG depth maps from 21597188 | cb31dfa | Submitted 22:50, V100S 32 GB (scoring only; the depth maps stay MIG-made), 2 h. Compare with the H100 `bonn_500` from 21559168 (G17). |
| 2026-11-16 | 21612587 | `bonn_500` MIG scoring | cb31dfa | **Done**, exit 0, 26 min, V100S (wn206), peak GPU memory 24.7 GB. Result in G17. |
| 2026-11-17 | 21612586 | RICH part 0 | cb31dfa | **Done**, exit 0, 166 min, H100 SXM (gwn10), 48 videos, staging 301 s (fix worked), peak GPU memory 7.6 GB. |
| 2026-11-17 | – (login node, CPU) | RICH merge: `python repro/merge_global_human.py --out eval_results/global_human/rich_human3r_merged --expect 191 …/rich_human3r_part{0,1,2,3}` | 6238b72 | 191/191 videos, no duplicates, OOM or exception lines; 104,468 matched people. ~10 min, almost all of it cold CephFS imports. Result in section 7. |
| 2026-11-17 | 21623368 | 3DPW **identical rerun** (repeatability, F1 / G17): same command as 21592963 except the fresh output folder `3dpw_human3r_rerun1` (G15); `--constraint="h100&sxm"` so the GPU type matches the first run (gwn10, H100 80GB HBM3) | c538f03 (`src/`, `eval/` identical to 42a2d62) | Submitted 08:16, 8 h limit. Compare per-sequence lines of `_error_log_0.txt` with `3dpw_human3r`. |
| 2026-11-17 | 21623935 | 3DPW **TF32 off** (numerics sensitivity, F1): same as 21623368 but prefixed `env NVIDIA_TF32_OVERRIDE=0` (forces full fp32 in cuBLAS / cuDNN, overriding `allow_tf32`), folder `3dpw_human3r_tf32off`, `--main_process_port 29551` (avoids a clash if both jobs share a node; no effect on results), 10 h limit (fp32 is slower) | a3dc794 (`src/`, `eval/` identical to 42a2d62) | Submitted 08:25. Compare with 21592963 and 21623368: the spread between them is the numerics effect. |

Practical observations:

- **Code snapshot rule.** Jobs execute the live working tree, and `run.sh` starts a new Python process per subset, so edits made while a job runs leak into it. From commit 0ae6199 on, jobs are submitted with `repro/slurm/submit.sh`, which refuses uncommitted changes and runs the job from a git worktree frozen at submission (`$PROJ/runs/<job>_<commit>_<time>/`, gitignored runtime files symlinked in). The log also records the checkpoint SHA256 (`human3r_896L.pth`: `1c5d8907…a9377`), a hash of the cached DINOv2 hub code, and peak GPU memory. The jobs 21559068 and 21559168 predate this and ran the live tree. Snapshots of three dead jobs were removed on 2026-11-17 (`precheck_3dpw_3e97ce8_…`, `rich_part0_42a2d62_…` which failed in staging, `rich_eval_52fc487_…` which was cancelled); they held only tracked files and symlinks, and can be recreated with `git worktree add --detach <dir> <commit>`.

- **Slow cold start.** On the cluster's CephFS, a job's first reads of the conda env and checkpoint were very slow on 2026-11-15. The first TUM job needed about 25 min before inference began (Python imports at about 350 KB/s; `import trimesh, pyglet` took 123 s cold vs 1.3 s warm). It is storage, not the model. **For speed claims (paper: 15 FPS on an RTX 4090), time only the inference loop, never job wall-clock.**
- **Pre-checks.** After two late crashes we test the scoring and visualisation code on CPU before resubmitting: TUM scoring on the saved `sitting_halfsphere` prediction (ATE 0.037 m, 90 frames; a check, not a report number) and `save_depth_maps` on fake 512×384 tensors.
- **RICH pre-check (2026-11-15, job 21561273, commit 92a56d7, MIG 1g.10gb):** `repro/checks/precheck_global_human.py` on `LectureHall_019_wipingchairs1/cam_00`, first 250 frames, same args as `run_rich.sh`. Full pipeline ran (load, inference, matching, metrics, logs) in 8 min; recall 100%. Crash test only, not report numbers.

## 7. Results

### 3DPW local human mesh (job 21592963; Table 1)

All 24 test sequences, `run.sh` arguments, mm, n_human-weighted mean (upstream `launch.py`).

| | PA-MPJPE | MPJPE | PVE | PA-PVE |
|---|---|---|---|---|
| Ours | 44.6 | 72.8 | 86.6 | 60.6 |
| Paper Table 1 | 44.1 | 71.2 | 84.9 | – |
| Difference | +0.5 | +1.6 | +1.7 | |

Detection: precision 70.0 %, recall 98.9 %, F1 79.0 %. Global metrics are 0 for 3DPW (not evaluated upstream).
Matched / labelled person-frames: 35,080 / 35,515 = 98.8 % (G19).
**Close but not exact** (G18). Annotations and protocol are checked (G18 a, b); the remaining tests are listed in F1.

### RICH global human motion (jobs 21612586, 21592960–62, merged; Table 2)

All 191 test videos (4 parts, merged with the upstream averaging, G15), `run_rich.sh` arguments (reset 1e6, size 512, TTT3R), H100 SXM.
Units: WA-/W-MPJPE in mm, RTE in % (the log labels them cm, G13).

| | WA-MPJPE | W-MPJPE | RTE |
|---|---|---|---|
| Ours | 110.0 | 184.4 | 3.3 |
| Paper Table 2 | 110.0 | 184.9 | 3.3 |

Not in the paper's table: PA-MPJPE 47.6, MPJPE 71.1, PVE 78.9 mm (camera frame); precision 83.5 %, recall 98.6 % (logged; 104,468 matched of 106,446 labelled frames = 98.1 %, G19).
**Reproduced** (W-MPJPE 0.5 mm lower, the others identical).

### TUM-dynamics camera pose (job 21559068; Fig. 9a)

ATE in m after Sim(3) alignment, mean over the 8 sequences; paper values read off the red curve
of Fig. 9a (PDF p. 8, precision about ±0.002 m). RPE from `_error_log.txt` (not plotted in the paper).

| Frames | 50 | 100 | 150 | 200 | 300 | 400 | 500 | 600 | 700 | 800 | 900 | 1000 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| ATE ours | 0.0142 | 0.0200 | 0.0244 | 0.0311 | 0.0430 | 0.0469 | 0.0514 | 0.0583 | 0.0681 | 0.0764 | 0.0828 | 0.0929 |
| ATE paper (read off) | 0.014 | 0.020 | 0.025 | 0.031 | 0.042 | 0.047 | 0.051 | 0.058 | 0.068 | 0.077 | 0.083 | 0.092 |
| RPE trans ours | 0.0076 | 0.0082 | 0.0076 | 0.0079 | 0.0081 | 0.0079 | 0.0077 | 0.0074 | 0.0073 | 0.0071 | 0.0069 | 0.0075 |
| RPE rot ours (°) | 0.298 | 0.292 | 0.293 | 0.298 | 0.304 | 0.308 | 0.332 | 0.331 | 0.334 | 0.338 | 0.353 | 0.376 |

`tum` (90 frames, stride 3, not in the figure): ATE 0.0285, RPE trans 0.0129, RPE rot 0.380°.
**Reproduced** within read-off precision at every length.

### Bonn video depth (job 21559168; Fig. 9b, Table 10)

Mean over the 5 sequences. Fig. 9b plots **metric scale** only, for `bonn_50`…`bonn_500`.

| Set | Scale AbsRel | Scale δ<1.25 (%) | Metric AbsRel | Metric δ<1.25 (%) | Paper metric AbsRel / δ (read off) |
|---|---|---|---|---|---|
| bonn (110) | 0.0680 | 95.7 | 0.0872 | 95.3 | not plotted |
| bonn_50 | 0.0769 | 95.7 | 0.0846 | 95.4 | 0.085 / 95.4 |
| bonn_100 | 0.0667 | 95.7 | **0.0860** | **95.4** | 0.086 / 95.4; **Table 10: 0.086 / 95.4** |
| bonn_150 | 0.0677 | 95.7 | 0.0919 | 94.1 | 0.092 / 93.8 |
| bonn_200 | 0.0687 | 95.4 | 0.0988 | 90.9 | 0.099 / 90.7 |
| bonn_250 | 0.0692 | 95.6 | 0.1010 | 91.0 | 0.101 / 90.8 |
| bonn_300 | 0.0790 | 95.1 | 0.1057 | 91.2 | 0.106 / 91.0 |
| bonn_350 | 0.0784 | 95.2 | 0.1034 | 91.7 | 0.103 / 91.5 |
| bonn_400 | 0.0784 | 95.2 | 0.1021 | 92.1 | 0.102 / 91.9 |
| bonn_450 | 0.0776 | 95.3 | 0.1006 | 92.5 | 0.101 / 92.3 |
| bonn_500 | 0.0765 | 95.4 | 0.0988 | 92.8 | 0.099 / 92.6 |

**Reproduced** within read-off precision at every length; Table 10 matches `bonn_100` metric exactly.
Scale-aligned numbers are not reported in the paper.

Caveat for both: these confirm the released checkpoint + scripts reproduce the published curves.
They do not test the TTT3R / CUT3R baseline curves or the reset effect (G10).
