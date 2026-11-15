#!/bin/bash
# Submit a Human3R repro job that runs from a frozen code snapshot (git worktree) taken NOW,
# so later edits to the working tree cannot leak into queued or running jobs.
# Usage (from anywhere):
#   bash repro/slurm/submit.sh <jobname> [sbatch options --] <command...>
#   e.g. bash repro/slurm/submit.sh relpose_tum bash eval/relpose/run.sh
#        bash repro/slurm/submit.sh rich -t 20:00:00 -- bash eval/global_human/run_rich.sh
# Refuses to run with uncommitted changes to tracked files. Gitignored runtime files (checkpoints,
# body models, compiled curope, annots, eval_results link) are symlinked into the snapshot.
# Snapshots: $PROJ/runs/<jobname>_<commit>_<timestamp>/ (remove when done + `git worktree prune`).
set -euo pipefail
PROJ=/d/hpc/projects/supv2/yt82121/human3r
REPO=$PROJ/Human3R
[ $# -ge 2 ] || { sed -n 2,10p "$0"; exit 1; }
name=$1; shift
sb=()
if printf '%s\n' "$@" | grep -qx -- '--'; then
    while [ "$1" != "--" ]; do sb+=("$1"); shift; done; shift
fi

cd "$REPO"
if ! git diff --quiet || ! git diff --cached --quiet; then
    echo "Uncommitted changes to tracked files; commit first:"; git status --short --untracked-files=no; exit 1
fi
commit=$(git rev-parse --short HEAD)
snap=$PROJ/runs/${name}_${commit}_$(date +%Y%m%d-%H%M%S)
git worktree add --quiet --detach "$snap" HEAD

# link every gitignored item of the main tree (except caches) into the snapshot
git status --ignored --porcelain | sed -n 's/^!! //p' | grep -v '__pycache__' | sed 's:/$::' |
while read -r p; do
    [ -e "$snap/$p" ] || [ -L "$snap/$p" ] && continue
    mkdir -p "$(dirname "$snap/$p")"
    ln -s "$REPO/$p" "$snap/$p"
done

cd "$snap"
sbatch --job-name="$name" "${sb[@]}" repro/slurm/run.sbatch "$@"
echo "snapshot: $snap (commit $commit)"
