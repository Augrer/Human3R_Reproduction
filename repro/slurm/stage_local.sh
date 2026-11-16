#!/bin/bash
# Copy the given dataset folders to node-local disk with many parallel readers, point H3R_DATA at
# the copy, run the command, delete the copy. Reason: the eval loaders read images one file at a
# time, which on CephFS ran at ~4 files/s (GPU idle); 32 parallel readers gave ~25 files/s.
# Paths are relative to $H3R_DATA and keep their layout, so no eval code changes are needed.
# Usage (inside a job, e.g. via submit.sh):
#   bash repro/slurm/stage_local.sh RICH/test/<seq>/cam_00 RICH/test/<seq>/cam_01 -- <command...>
#   bash repro/slurm/stage_local.sh --list paths.txt -- <command...>
set -euo pipefail
SRC=${H3R_DATA:?H3R_DATA not set}
paths=()
while [ $# -gt 0 ] && [ "$1" != "--" ]; do
    if [ "$1" = "--list" ]; then mapfile -t -O "${#paths[@]}" paths < "$2"; shift 2; else paths+=("$1"); shift; fi
done
[ "${1:-}" = "--" ] || { echo "usage: stage_local.sh <paths...> | --list FILE -- <command...>"; exit 1; }
shift
DST=${TMPDIR:-/tmp}/h3r_stage_${SLURM_JOB_ID:-$$}/data
mkdir -p "$DST"
trap 'rm -rf "$(dirname "$DST")"' EXIT

t0=$(date +%s)
cd "$SRC"
for p in "${paths[@]}"; do [ -e "$p" ] || { echo "missing: $SRC/$p"; exit 1; }; done
# Create the directory tree first: parallel `cp --parents` calls race on mkdir of shared parent
# folders ("cannot make directory ...: File exists", job 21592959).
find "${paths[@]}" -type d -print0 | (cd "$DST" && xargs -0 mkdir -p)
find "${paths[@]}" -type f -print0 | xargs -0 -P 32 -n 64 cp --parents -t "$DST"
n_src=$(find "${paths[@]}" -type f | wc -l); n_dst=$(cd "$DST" && find "${paths[@]}" -type f | wc -l)
[ "$n_src" = "$n_dst" ] || { echo "STAGING INCOMPLETE: $n_dst of $n_src files"; exit 1; }
echo "=== staged ${#paths[@]} folders, $n_dst files, $(du -sh "$DST" | cut -f1) to $DST in $(( $(date +%s) - t0 )) s"
cd - >/dev/null

export H3R_DATA=$DST
echo "=== H3R_DATA=$H3R_DATA (local copy)"
"$@"
