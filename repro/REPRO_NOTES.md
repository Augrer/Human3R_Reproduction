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
| G3 | **[code] vs [paper]** The paper says "the state is reset every 100 frames". `eval/relpose/run.sh` uses `--reset_interval 100`, but `eval/video_depth/run.sh` uses `--reset_interval 1000000000` (no reset). | Run as in the scripts (which presumably produced the figures); report the mismatch; optional ablation with reset 100 on Bonn. |
| G4 | **[paper]** The Bonn ablation table (Abs Rel, δ<1.25 next to 3DPW / EMDB-2) does not say which Bonn variant was used (110-frame `bonn` or a `bonn_N`). | Assume `bonn` (110 frames, the default in `eval_depth.py`); flag it. |

## 2. TUM-dynamics (camera pose, `eval/relpose`)

Built with [`datasets_preprocess/prepare_tum_bonn_subsets.py`](datasets_preprocess/prepare_tum_bonn_subsets.py),
a faithful port of MonST3R@574cc77 `prepare_tum.py` and TTT3R@edd6d8c `long_prepare_tum.py`.
Raw data: the 8 freiburg3 `sitting_*` / `walking_*` (`static`, `xyz`, `halfsphere`, `rpy`) sequences,
the same list as MonST3R's `data/download_tum_dynamics.sh`.

| # | Observation | Our handling |
|---|---|---|
| T1 | **[code]** `rgb_90` / `groundtruth_90.txt` (dataset `tum`) and `rgb_N` (dataset `tum_N`) are not raw TUM content, and nothing in this repo creates them. `docs/eval.md` defers to MonST3R (download) and TTT3R (prepare). | Ported the upstream scripts (see above). |
| T2 | **[upstream]** `tum`: RGB frames are matched to GT poses by timestamp (TUM `associate`, max 0.02 s), then every 3rd matched frame is taken, first 90. | Unchanged. Verified that all subsets have \|t_rgb − t_gt\| < 0.02 s. |
| T3 | **[paper]/[upstream]** `tum_N`: TTT3R's script uses stride `SAMPLE_INTERVAL = 1`, with the comment "original 3", and writes `long_tum_s1/` (TTT3R names these `tum_s1_N`). Human3R expects `long_tum/` and never states the stride. With stride 1, `tum_N` covers N/30 s of video; with stride 3, 3× longer. | **[ours]** stride 1 (current TTT3R script). Possible check: if our TTT3R baseline curve matches the one in the paper's figure, stride 1 is confirmed. |
| T4 | **[upstream]** Several sequences are shorter than the longest N. Matched frames: sitting_static 703, walking_static 740, sitting_rpy 817, walking_xyz 857, walking_rpy 906, the rest ≥ 1064. So `tum_800` … `tum_1000` silently contain fewer frames for those sequences, and `tum_1000` is really a mix of 703–1000-frame sequences. | Unchanged; state it in the report next to the curves. |

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
| R3 | **[upstream]** GVHMR RICH labels: `frame_id` indexes the **sorted listing** of each `cam_XX` folder and does not start at 0, so the folder must contain the full frame sequence, or frames silently shift. Labels cover 191 videos (50 sequences, 106,446 frames). | Extract complete cam folders; check counts after extraction. |
| R4 | **[paper]** EMDB and RICH: "we divide each sequence into 100-frame segments" (following GVHMR/TRAM). | Check that the code does the same when we get there. |

## 5. Storage-only deviations (no effect on results)

- Derived frame subsets are **hard links** to the raw frames (byte-identical, ~0 extra space;
  upstream copies). `--copy` gives real copies.
- Derived subsets live in `data/long_tum/` and `data/long_bonn/` (one tree per dataset), not inside
  the raw sequence folders.
- Each raw archive is kept with SHA256 checksums in `data/_archives/<dataset>/` (outside the repo).
