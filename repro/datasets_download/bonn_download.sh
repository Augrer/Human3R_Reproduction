#!/bin/bash
# Download + extract the 5 Bonn RGB-D Dynamic sequences used by the video-depth eval
# (seq list from eval/video_depth/metadata.py). Resumable: re-run to continue; finished archives are skipped.
# Archives + SHA256SUMS -> data/_archives/bonn/, extracted (official layout) -> data/bonn/.
# Usage: H3R_DATA=/path/to/data bash repro/datasets_download/bonn_download.sh
set -euo pipefail
DATA=${H3R_DATA:?set H3R_DATA to the data root}
ARC=$DATA/_archives/bonn
DST=$DATA/bonn
BASE=https://www.ipb.uni-bonn.de/html/projects/rgbd_dynamic2019
SEQS="balloon2 crowd2 crowd3 person_tracking2 synchronous"
mkdir -p "$ARC" "$DST"

for s in $SEQS; do
    f=rgbd_bonn_$s.zip
    want=$(curl -sIL "$BASE/$f" | tr -d '\r' | awk 'tolower($1)=="content-length:"{n=$2} END{print n}')
    have=$(stat -c %s "$ARC/$f" 2>/dev/null || echo 0)
    if [ "$have" != "$want" ]; then
        echo "$(date +%T) downloading $f ($want bytes)"
        curl -sS -fL --retry 5 -C - -o "$ARC/$f" "$BASE/$f"
        [ "$(stat -c %s "$ARC/$f")" = "$want" ] || { echo "SIZE MISMATCH $f"; exit 1; }
    else
        echo "$(date +%T) have $f"
    fi
    if [ ! -f "$DST/rgbd_bonn_$s/groundtruth.txt" ]; then
        echo "$(date +%T) extracting $f"
        unzip -q -o "$ARC/$f" -d "$DST"; rm -rf "$DST/__MACOSX"
    fi
done

(cd "$ARC" && sha256sum rgbd_bonn_*.zip > SHA256SUMS)
echo "5 Bonn RGB-D Dynamic sequences from $BASE, finished $(date -Is)" > "$ARC/DOWNLOADED_AT"
echo "$(date +%T) DONE"
for d in "$DST"/rgbd_bonn_*/; do
    printf '%-45s rgb=%5d depth=%5d gt_lines=%5d\n' "$(basename "$d")" \
        "$(ls "$d/rgb" | wc -l)" "$(ls "$d/depth" | wc -l)" "$(grep -vc '^#' "$d/groundtruth.txt")"
done
du -sh "$ARC" "$DST"
