# Getting the evaluation data

Scripts we used to fetch the raw data for the reproduction. They only download from the official
sources into `$H3R_DATA` (the data root the eval code reads). **This repository contains no
dataset files, annotations, body models, checkpoints or credentials**, and the scripts do not
work around any login: for RICH you need your own account and must accept its licence yourself.

| Dataset | How | Access |
|---|---|---|
| TUM RGB-D, 8 freiburg3 dynamic sequences | `tum_download.sh` | open download |
| Bonn RGB-D Dynamic, 5 sequences | `bonn_download.sh` | open download |
| RICH test images (JPG) | `rich_download_test_jpg.sh`, then `rich_extract.sbatch` (`rich_fix_one.sbatch` repairs a single file) | registration at <https://rich.is.tue.mpg.de> |
| RICH labels (GVHMR), camera parameters | links in `docs/eval.md`; see `repro/REPRO_NOTES.md` R2 | as stated there |
| 3DPW | by hand from <https://virtualhumans.mpi-inf.mpg.de/3DPW/> (`imageFiles.zip`, `sequenceFiles.zip`), unzip into `$H3R_DATA/3DPW/` | licence accepted on download |
| SMPL / SMPL-X body models, Human3R checkpoint | upstream README (`fetch_smplx.sh`, Hugging Face) | registration for SMPL and SMPL-X |

Usage: `H3R_DATA=/path/to/data bash repro/datasets_download/<script>` from the repo root.
Archives are kept in `$H3R_DATA/_archives/<dataset>/` with a `SHA256SUMS` file; the hashes of the
archives we used are in [`SHA256SUMS.txt`](SHA256SUMS.txt). The eval subsets for TUM and Bonn are
then built with `repro/datasets_preprocess/prepare_tum_bonn_subsets.py`.

Each dataset has its own terms of use (research-only and no redistribution for RICH, 3DPW, SMPL
and SMPL-X). Read them on the dataset pages, cite the dataset papers, and do not commit or share
data, derived annotation files or model files.

Status of these copies: `tum_download.sh` and `bonn_download.sh` are the scripts as run, with
the data root taken from `H3R_DATA`. The RICH scripts are the ones we ran with paths generalised
and support for a single archive file added; `rich_extract.sbatch` and `rich_fix_one.sbatch`
have not been re-run in this form, and the archive itself was fetched in two byte-range pieces
(see the header of `rich_download_test_jpg.sh`).
