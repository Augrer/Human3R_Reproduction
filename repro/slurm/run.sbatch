#!/bin/bash
# Generic Slurm wrapper for Human3R repro runs: runs "$@" inside the conda env from the directory
# the job was submitted from, and logs node, GPU, git commit, checkpoint hash, DINOv2 code hash,
# command, runtime and peak GPU memory (for every number that goes into the report).
# Preferred: submit through repro/slurm/submit.sh, which freezes the code in a git worktree first.
# Direct use (runs the live tree, NOT frozen):
#   cd $PROJ/Human3R && sbatch --job-name=X repro/slurm/run.sbatch bash eval/relpose/run.sh
# Defaults: one full H100 on partition gpu. Logs: $PROJ/logs/<jobname>_<jobid>.out
#SBATCH --partition=gpu
#SBATCH --constraint=h100
#SBATCH --gres=gpu:1
#SBATCH --cpus-per-task=8
#SBATCH --mem=64G
#SBATCH --time=12:00:00
#SBATCH --output=/d/hpc/projects/supv2/yt82121/human3r/logs/%x_%j.out
set -euo pipefail
PROJ=/d/hpc/projects/supv2/yt82121/human3r
module load Mamba/23.11.0-0 CUDA/12.6.0
source "$(conda info --base)/etc/profile.d/conda.sh"
set +u; conda activate "$PROJ/envs/human3r"; set -u
cd "${SLURM_SUBMIT_DIR:-$PROJ/Human3R}"
export H3R_DATA=${H3R_DATA:-$PROJ/data}

# checkpoint hash, cached by path+size+mtime (hashing 4.7 GB on CephFS is slow)
ckpt_info() {
    local f; f=$(readlink -f src/human3r.pth 2>/dev/null) || { echo "src/human3r.pth missing"; return; }
    local key; key="$f $(stat -c '%s %Y' "$f")"
    local cache=$PROJ/checkpoints/SHA256_CACHE
    local h; h=$(grep -F "$key " "$cache" 2>/dev/null | awk '{print $NF}' | tail -1)
    if [ -z "$h" ]; then h=$(sha256sum "$f" | cut -d' ' -f1); echo "$key $h" >> "$cache"; fi
    echo "$(basename "$f") sha256=$h"
}
hub=$HOME/.cache/torch/hub/facebookresearch_dinov2_main
hubhash=$( [ -d "$hub" ] && find "$hub" -name '*.py' | sort | xargs sha256sum | sha256sum | cut -c1-16 || echo none)

echo "=== job $SLURM_JOB_ID ($SLURM_JOB_NAME) on $(hostname), start $(date -Is)"
echo "=== dir: $PWD"
echo "=== git: $(git rev-parse --short HEAD) ($(git rev-parse --abbrev-ref HEAD))$(git diff --quiet || echo ' (+uncommitted changes)')"
echo "=== gpu: $(nvidia-smi --query-gpu=name,memory.total,driver_version --format=csv,noheader)"
echo "=== torch: $(python -c 'import torch; print(torch.__version__, torch.version.cuda)')"
echo "=== ckpt: $(ckpt_info)"
echo "=== dinov2 hub code hash: $hubhash"
echo "=== H3R_DATA=$H3R_DATA"
echo "=== cmd: $*"

# sample GPU memory every 5 s in the background; report the peak at the end
memlog=$(mktemp)
nvidia-smi --query-gpu=memory.used --format=csv,noheader,nounits -l 5 > "$memlog" 2>/dev/null &
mempid=$!
t0=$(date +%s)
rc=0; "$@" || rc=$?
kill $mempid 2>/dev/null || true
peak=$(sort -n "$memlog" | tail -1); rm -f "$memlog"
echo "=== exit $rc, runtime $(( ($(date +%s) - t0) / 60 )) min, peak GPU mem ${peak:-?} MiB (5 s sampling), end $(date -Is)"
exit $rc
