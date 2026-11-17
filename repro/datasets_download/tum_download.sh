#!/bin/bash
# Download + extract the 8 TUM RGB-D freiburg3 dynamic-object sequences used by the camera-pose
# eval (CUT3R/MonST3R "TUM-dynamics"). Resumable: re-run to continue; finished archives are skipped.
# Archives + SHA256SUMS -> data/_archives/tum/, extracted (official layout) -> data/tum/.
# Usage: H3R_DATA=/path/to/data bash repro/datasets_download/tum_download.sh
set -euo pipefail
DATA=${H3R_DATA:?set H3R_DATA to the data root}
ARC=$DATA/_archives/tum
DST=$DATA/tum
BASE=https://cvg.cit.tum.de/rgbd/dataset/freiburg3
SEQS="sitting_static sitting_xyz sitting_halfsphere sitting_rpy walking_static walking_xyz walking_halfsphere walking_rpy"
mkdir -p "$ARC" "$DST"

for s in $SEQS; do
    f=rgbd_dataset_freiburg3_$s.tgz
    want=$(curl -sIL "$BASE/$f" | tr -d '\r' | awk 'tolower($1)=="content-length:"{n=$2} END{print n}')
    have=$(stat -c %s "$ARC/$f" 2>/dev/null || echo 0)
    if [ "$have" != "$want" ]; then
        echo "$(date +%T) downloading $f ($want bytes)"
        curl -sS -fL --retry 5 -C - -o "$ARC/$f" "$BASE/$f"
        [ "$(stat -c %s "$ARC/$f")" = "$want" ] || { echo "SIZE MISMATCH $f"; exit 1; }
    else
        echo "$(date +%T) have $f"
    fi
    if [ ! -f "$DST/rgbd_dataset_freiburg3_$s/groundtruth.txt" ]; then
        echo "$(date +%T) extracting $f"
        tar -xzf "$ARC/$f" -C "$DST" --no-same-owner
    fi
done

(cd "$ARC" && sha256sum rgbd_dataset_freiburg3_*.tgz > SHA256SUMS)
echo "8 TUM RGB-D freiburg3 dynamic sequences from $BASE, finished $(date -Is)" > "$ARC/DOWNLOADED_AT"
echo "$(date +%T) DONE"
for d in "$DST"/rgbd_dataset_freiburg3_*/; do
    printf '%-45s rgb=%5d depth=%5d gt_lines=%5d\n' "$(basename "$d")" \
        "$(ls "$d/rgb" | wc -l)" "$(ls "$d/depth" | wc -l)" "$(grep -vc '^#' "$d/groundtruth.txt")"
done
du -sh "$ARC" "$DST"
