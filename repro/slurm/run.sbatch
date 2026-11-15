#!/bin/bash
# Generic Slurm wrapper for Human3R repro runs: runs "$@" from the repo root inside the conda env
# and logs node, GPU, git commit, command and runtime (for every number that goes into the report).
# Usage (from $PROJ/Human3R):  sbatch [--job-name=X] [-t HH:MM:SS] repro/slurm/run.sbatch <command...>
#   e.g. sbatch --job-name=relpose repro/slurm/run.sbatch bash eval/relpose/run.sh
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
cd "$PROJ/Human3R"
export H3R_DATA=${H3R_DATA:-$PROJ/data}

echo "=== job $SLURM_JOB_ID ($SLURM_JOB_NAME) on $(hostname), start $(date -Is)"
echo "=== git: $(git rev-parse --short HEAD) on $(git branch --show-current)$(git diff --quiet || echo ' (+uncommitted changes)')"
echo "=== gpu: $(nvidia-smi --query-gpu=name,memory.total,driver_version --format=csv,noheader)"
echo "=== torch: $(python -c 'import torch; print(torch.__version__, torch.version.cuda)')"
echo "=== H3R_DATA=$H3R_DATA"
echo "=== cmd: $*"
t0=$(date +%s)
rc=0; "$@" || rc=$?
echo "=== exit $rc, runtime $(( ($(date +%s) - t0) / 60 )) min, end $(date -Is)"
exit $rc
