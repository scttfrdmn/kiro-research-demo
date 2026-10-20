#!/usr/bin/env bash
# Copy Demo 2's results from your bucket into results/.
cd "$(dirname "$0")/.."
source scripts/common.sh
mkdir -p results
aws s3 cp --only-show-errors --recursive "$PREFIX/runs/era5-2023/" results/
ls -l results/
