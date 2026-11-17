#!/bin/bash
# Re-extract ONE member of the RICH JPG test archive (e.g. a file truncated by an interrupted
# rich_extract run, reported there as "BAD ...") and check its size against the archive listing
# written by rich_extract.sbatch.
# Usage: H3R_DATA=/path/to/data sbatch --export=ALL repro/datasets_download/rich_fix_one.sbatch test/<seq>/cam_XX/<frame>.jpeg
#SBATCH --job-name=rich_fix_one
#SBATCH --partition=all
#SBATCH --cpus-per-task=2
#SBATCH --mem=4G
#SBATCH --time=02:00:00
#SBATCH --output=%x_%j.out
set -uo pipefail
DATA=${H3R_DATA:?set H3R_DATA to the data root}; A=$DATA/_archives/RICH; DST=$DATA/RICH; m=$1
want=$(awk -v m="$m" '$NF==m{print $3}' "$A/test_jpg_members.txt")
[ -n "$want" ] || { echo "not in archive: $m"; exit 1; }
echo "=== $m, want $want bytes, start $(date -Is) on $(hostname)"
rm -f "$DST/$m"
if [ -d "$A/test_jpg.parts" ]; then
    mapfile -t PIECES < <(ls "$A"/test_jpg.parts | grep -E '^[0-9]{12}$' | sort -n | sed "s|^|$A/test_jpg.parts/|")
else
    PIECES=("$A/test_jpg.tar.gz")
fi
for x in "${PIECES[@]}"; do dd if="$x" bs=64M status=none; done \
  | tar -xz -C "$DST" --no-same-owner --no-same-permissions --occurrence=1 "$m"
have=$(stat -c %s "$DST/$m" 2>/dev/null)
echo "=== have ${have:-missing} bytes, end $(date -Is)"
[ "$have" = "$want" ] || { echo "STILL BAD"; exit 1; }
echo "RICH JPG test: re-extracted $m, size-verified $(date -Is), job ${SLURM_JOB_ID:-none}" >> "$A/DOWNLOADED_AT"
echo OK
