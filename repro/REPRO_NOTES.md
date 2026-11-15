# Reproduction notes: observations, ambiguities and our choices

Running list of points where the Human3R paper (arXiv:2510.06219v2 (HTML version read 2026-11-15), ICLR 2026) and/or the code
(fanegg/Human3R, `main` as cloned) are unclear, inconsistent, or depend on other repos, plus what we
did about each. Input for the "reproducibility" discussion in the report. Environment/install
problems are in [SETUP_NOTES.md](SETUP_NOTES.md); this file is about **data and evaluation
protocol**.

Status tags: **[paper]** not or not fully specified in the paper · **[code]** code issue or
code/paper mismatch · **[upstream]** behaviour inherited from MonST3R / TTT3R / GVHMR ·
**[ours]** our choice where the authors' choice is unknown.

---

## 1. General

| # | Observation | Our handling |
|---|---|---|
| G1 | **[code]** No data-root option. All dataset paths are hard-coded `/path/to/...` placeholders in `eval/*/metadata.py`, `eval/video_depth/eval_depth.py` and `eval/dataset/prepare_3dpw.py`. | **Done** (2026-11-15): env var `H3R_DATA`, default `<repo>/../data`, one marked `# REPRO:` constant per file; see SETUP_NOTES "Code changes". |
| G2 | **[paper]** For camera pose and video depth, the paper only says "following prior works [12, 97]". Frame selection, start frame, stride and sequence lengths are not given. The results are shown as **plots over sequence length**, not tables, so the comparison has to be against read-off curve values. | Follow the code's dataset lists (`run.sh`) and the upstream preprocessing (sections 2 and 3). |
| G3 | **[code] vs [paper]** The paper says "the state is reset every 100 frames". The scripts set it per benchmark: 100 for 3DPW / EMDB-1 (`global_human/run.sh`) and TUM (`relpose/run.sh`), **50** for EMDB-2 (`run_emdb2.sh`), effectively never for RICH (`run_rich.sh`, 1e6) and Bonn (`video_depth/run.sh`, 1e9). | Run as in the scripts (which presumably produced the published numbers); report the per-benchmark table; reset ablation planned (see G10). |
| G4 | **[paper]** The Bonn numbers in Table 10 (Abs Rel 0.086, δ<1.25 95.4) do not say which Bonn variant, length or alignment was used. | **Resolved (2026-11-15):** our `bonn_100` **metric-scale** result is exactly 0.0860 / 95.4. Table 10 = metric depth, 100 frames. |
| G5 | **[code]** Checkpoint name mismatch: the README downloads `src/human3r_896L.pth`, but `eval/relpose/run.sh` and `eval/video_depth/run.sh` load `./src/human3r.pth`. | Symlink `src/human3r.pth -> human3r_896L.pth` (gitignored); scripts unchanged. |
| G6 | **[code]** `requirements.txt` pins only 7 of 29 packages (evo, matplotlib, torch etc. are unpinned), and the evals crash with current versions of two libraries, both only at the very end of a run: **evo** 1.38.1 (`main_ape.ape()` / `main_rpe.rpe()` no longer take `est_name=`) in TUM scoring, and **matplotlib** 3.11.2 (`cm.get_cmap` removed in 3.9) in the coloured depth maps that `video_depth/launch.py` saves before Bonn scoring. The authors' versions are unknown, so a fresh install today cannot run the published scripts unmodified. Library changes that alter numbers without crashing would go unnoticed. | Minimal `# REPRO` fixes that only touch labels and colours (SETUP_NOTES code changes 2 and 3, commits a55c18f and 452e340). Exact versions are in `pip_freeze_2026-11-13.txt`. Report as a reproducibility issue. |
| G7 | **[code]** Both `run.sh` use `set -e` and loop over all sequence lengths, and a crash in one sequence's *visualisation* (Bonn saves a coloured depth and confidence PNG per frame as part of the eval) aborts the whole sweep, including all later sequence lengths. | Fixed the crashes rather than changing the scripts. A rerun starts from scratch (we delete the partial output dir first). |
| G8 | **[paper]** Table 10 header is mislabelled in the PDF: it reads PA-MPJPE / MPJPE / PVE and WA-MPJPE / W-MPJPE, but the values are in reverse order (84.9 / 71.2 / 44.1 and 267.9 / 112.2, cf. Tables 1, 2). | Read by value, not by header; report it. |
| G9 | **[paper]** Speed and accuracy headlines come from different models: Tables 1–2 use ViT-L/896 (~5 FPS per the ablation table), the 15 FPS claim is ViT-S/672 (EMDB-2 WA-MPJPE 129.9, Table 8). Sec. A.5 says "approximately WA-MPJPE 100" for that setting, which does not match 129.9. | Report speed per checkpoint; compare our ViT-L/896 timing to 5 FPS, not 15. |
| G10 | **[ours] hypothesis, untested** In Fig. 9a, Human3R and TTT3R appear to coincide up to 100 frames and separate from 150, where the first state reset takes effect; on Bonn (no reset) they differ by ≤ ~0.003 Abs Rel. The TUM gain attributed to human prompt tuning ("mutual benefit") may partly come from the reset. | Planned control: TUM and Bonn with reset 100 vs none, with and without TTT3R, plus TTT3R/CUT3R baselines under the same subsets. |
| G11 | **[paper]** Not stated in the paper, only in code/config: the dataset behind Table 9, Fig. 12 and Table 11 (code suggests the BEDLAM test split); the human detection threshold (0.3 per review, unverified) and 2D matching (greedy, IoU ≥ 0.05, `global_human/utils.py`); training settings (40 epochs × 4000 samples, weight decay 0.05, 5 warm-up epochs, seed 0, per review of the config). | Cite the code values in the report. |
| G12 | **[code]** `global_human/launch.py` catches out-of-memory errors (and "Degenerate covariance rank" / "Eigenvalues did not converge") per sequence, writes one line to `_error_log_*.txt`, and **continues**; the final averages are taken over the remaining sequences. A video that runs out of memory (more likely for long RICH / EMDB videos with no reset) silently drops out of the reported number. | After every global-human run, grep the error logs for `OOM` / `Exception` and report the number of evaluated videos (RICH: 191 expected). |
| G13 | **[code], to verify** The eval summary (`get_summary_log`, `global_human/utils.py`) labels the global metrics "(cm)", but our RICH pre-check gives WA-MPJPE 84.4 / W-MPJPE 132.3, the same scale as the paper's 110.0 / 184.9 **mm** (Table 2). Most likely a label error (GVHMR-style metrics in mm; RTE in %). | Check the conversion factors in the metric code before quoting units in the report. |
| G14 | **[code]** The 3DPW preparation command given in `docs/eval.md` does not run as published (circular import in `prepare_3dpw.py`, job 21562622). Together with G1, G5, G6 this means none of the documented eval paths ran unmodified on a fresh install. | One-line import-order fix (SETUP_NOTES code change 4). |

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
H100 PCIe (80 GB), `H3R_DATA=$PROJ/data`, checkpoint `human3r_896L.pth` via the G5 symlink. Logs:
`$PROJ/logs/<name>_<jobid>.out` (node, GPU, commit, command, runtime). Results:
`$PROJ/outputs/eval_results/` (outside the repo, reached via the gitignored `eval_results` link).

| Date | Job | Eval | Commit | Outcome |
|---|---|---|---|---|
| 2026-11-15 | 21558187 | TUM camera pose | 9025e2a | Crashed after the first sequence's inference (`sitting_halfsphere`, 90 frames), in scoring: evo `est_name` (G6). Runtime 23 min. |
| 2026-11-15 | 21558188 | Bonn video depth | 9025e2a | Crashed after the first sequence's inference (`balloon2`, 110 frames), in `save_depth_maps`: matplotlib `get_cmap` (G6). Runtime 11 min. |
| 2026-11-15 | 21559068 | TUM camera pose | a55c18f (logged) | **Done**, exit 0, 253 min, H100 PCIe (gwn03), 8/8 sequences in all 13 sets. **Provenance caveat:** the job started 12:34:03 and `eval/relpose/utils.py` changed at 12:34:26 (matplotlib fix, 452e340); each subset starts a fresh Python process, so at least `tum_50` onward ran 452e340 code. Only the colour-map line differs and the camera-pose path never calls `colorize`, so the numbers are unaffected. Lesson: see the snapshot rule below. |
| 2026-11-15 | 21559168 | Bonn video depth | c5e94f3 | **Done**, exit 0, 118 min, H100 PCIe (gwn06), clean tree (code identical to 452e340), 5/5 sequences in all 11 sets, no errors. |
| 2026-11-15 | 21568115 | RICH global motion (`run_rich.sh`, 191 videos) | 52fc487 | Submitted 18:24 via `submit.sh` (snapshot `runs/rich_eval_52fc487_…`), H100, 20 h limit. |
| 2026-11-15 | 21569212 | 3DPW local mesh (`launch.py` with the `run.sh` arguments, `--eval_dataset 3dpw` only; `run.sh` would continue to EMDB-1, which we lack) | 3e97ce8 | Submitted 19:07 via `submit.sh`, H100, 4 h limit. Annotations: `3dpw_test.pkl` (24 seqs, 24,547 frames; job 21563583). Pre-check 21568279 passed. |

Practical observations:

- **Code snapshot rule.** Jobs execute the live working tree, and `run.sh` starts a new Python process per subset, so edits made while a job runs leak into it. From commit 0ae6199 on, jobs are submitted with `repro/slurm/submit.sh`, which refuses uncommitted changes and runs the job from a git worktree frozen at submission (`$PROJ/runs/<job>_<commit>_<time>/`, gitignored runtime files symlinked in). The log also records the checkpoint SHA256 (`human3r_896L.pth`: `1c5d8907…a9377`), a hash of the cached DINOv2 hub code, and peak GPU memory. The jobs 21559068 and 21559168 predate this and run the live tree: do not edit `eval/`, `src/` or `*.py` until they finish.

- **Slow cold start.** On the cluster's CephFS, a job's first reads of the conda env and checkpoint were very slow on 2026-11-15. The first TUM job needed about 25 min before inference began (Python imports at about 350 KB/s; `import trimesh, pyglet` took 123 s cold vs 1.3 s warm). It is storage, not the model. **For speed claims (paper: 15 FPS on an RTX 4090), time only the inference loop, never job wall-clock.**
- **Pre-checks.** After two late crashes we test the scoring and visualisation code on CPU before resubmitting: TUM scoring on the saved `sitting_halfsphere` prediction (ATE 0.037 m, 90 frames; a check, not a report number) and `save_depth_maps` on fake 512×384 tensors.
- **RICH pre-check (2026-11-15, job 21561273, commit 92a56d7, MIG 1g.10gb):** `repro/checks/precheck_global_human.py` on `LectureHall_019_wipingchairs1/cam_00`, first 250 frames, same args as `run_rich.sh`. Full pipeline ran (load, inference, matching, metrics, logs) in 8 min; recall 100%. Crash test only, not report numbers.

## 7. Results

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
