#!/bin/bash
# One pass over the RICH JPG test archive: extract only the 191 camera folders the eval needs
# (the GVHMR rich_test_labels.pt videos = repro/splits/rich_chunk[0-3].txt), list ALL members, and
# SHA256 the archive (compare with SHA256SUMS.txt). Reading to the end of the gzip stream is the
# integrity check (RICH publishes no checksum). Result: $H3R_DATA/RICH/test/<seq>/cam_XX/*.jpeg,
# 191 folders / 114,264 jpeg / ~207 GB.
# The archive is either $H3R_DATA/_archives/RICH/test_jpg.tar.gz or, as in this study, byte-range
# pieces in test_jpg.parts/ named by their 12-digit start offset (concatenated = the archive).
# Usage, from the repo root (CPU job; adapt partition and log path to your cluster):
#   H3R_DATA=/path/to/data sbatch --export=ALL repro/datasets_download/rich_extract.sbatch
#SBATCH --job-name=rich_extract
#SBATCH --partition=all
#SBATCH --cpus-per-task=4
#SBATCH --mem=8G
#SBATCH --time=24:00:00
#SBATCH --output=%x_%j.out
set -euo pipefail
DATA=${H3R_DATA:?set H3R_DATA to the data root}
REPO=${SLURM_SUBMIT_DIR:-$PWD}
A=$DATA/_archives/RICH
DST=$DATA/RICH
mkdir -p "$DST"
cat "$REPO"/repro/splits/rich_chunk[0-3].txt | sort > "$A/needed_videos.txt"
[ "$(wc -l < "$A/needed_videos.txt")" = 191 ] || { echo "expected 191 videos in repro/splits"; exit 1; }
if [ -d "$A/test_jpg.parts" ]; then
    # pieces are named by their 12-digit byte offset; numeric order = archive order
    mapfile -t PIECES < <(ls "$A"/test_jpg.parts | grep -E '^[0-9]{12}$' | sort -n | sed "s|^|$A/test_jpg.parts/|")
else
    PIECES=("$A/test_jpg.tar.gz")
fi
echo "=== pieces: ${PIECES[*]##*/}"
echo "=== start $(date -Is) on $(hostname)"
size=$(stat -c %s "${PIECES[@]}" | awk '{s+=$1} END{printf "%d", s}')
echo "=== archive total $size bytes (expected 242598234351)"
[ "$size" = 242598234351 ] || { echo "SIZE MISMATCH"; exit 1; }

# dd with 64 MB blocks: on our CephFS, cat (128 KB reads) gave ~10 MB/s, 64 MB reads ~20 MB/s
for x in "${PIECES[@]}"; do dd if="$x" bs=64M status=none; done \
  | tee >(sha256sum | sed 's/-$/JPG_images\/test.tar.gz/' > "$A/test_jpg.sha256") \
        >(tar -tvz > "$A/test_jpg_members.txt") \
  | tar -xz -C "$DST" --no-same-owner --no-same-permissions --skip-old-files -T "$A/needed_videos.txt" && rc=0 || rc=$?
sleep 30   # let the process substitutions flush
echo "=== tar rc=$rc, end $(date -Is)"
cat "$A/test_jpg.sha256"
echo "=== archive members: $(wc -l < "$A/test_jpg_members.txt") lines, $(grep -c '\.jpeg$' "$A/test_jpg_members.txt") jpeg"
echo "=== extracted cam folders: $(find "$DST/test" -mindepth 2 -maxdepth 2 -type d -name 'cam_*' | wc -l) (expected 191)"
echo "=== extracted jpeg: $(find "$DST/test" -name '*.jpeg' | wc -l) (expected 114264)"
du -sh "$DST"
# verify: every needed member exists with the archive's byte size (catches truncated files from an
# interrupted earlier run, which --skip-old-files would otherwise keep; fix with rich_fix_one.sbatch)
awk 'NR==FNR{need[$0]=1; next} {n=$NF; split(n,a,"/"); k=a[1]"/"a[2]"/"a[3]} (k in need) && n ~ /\.jpeg$/ {print $3, n}' \
    "$A/needed_videos.txt" "$A/test_jpg_members.txt" | sort -k2 > "$A/needed_members.txt"
bad=0; while read -r sz n; do
    [ "$(stat -c %s "$DST/$n" 2>/dev/null)" = "$sz" ] || { echo "BAD $n (want $sz)"; bad=$((bad+1)); }
done < "$A/needed_members.txt"
echo "=== verify: $(wc -l < "$A/needed_members.txt") needed jpeg in archive, $bad missing or wrong size"
[ $bad -eq 0 ] || rc=2
echo "RICH JPG test: 191 cam folders extracted to RICH/test $(date -Is), job ${SLURM_JOB_ID:-none}, rc=$rc" >> "$A/DOWNLOADED_AT"
exit $rc
