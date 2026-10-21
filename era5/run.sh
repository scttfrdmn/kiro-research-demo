#!/usr/bin/env bash
# Demo 2's task: verify the staged inputs against their pins, run era5.py, check its sentinel.
# Staged as a file rather than inlined in the task spec: the spec rides in EC2 user data,
# which is capped at 16 KiB (spawn#1063).
set +e
set -uo pipefail
# spawn runs task commands under bash -e; `set -uo pipefail` does not clear it (spawn#707).
export PATH=/opt/conda/bin:$PATH TMPDIR=/tmp HOME=/tmp
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 ERA5_THREADS=8 ERA5_DIR=/tmp/era5
cd /tmp
echo "== staged bytes must match their pins =="
T0=$(date +%s)
sha256sum -c pins.sha256 || { echo "FAIL: a staged input does not match its pin"; exit 1; }
echo "sha256 of 13.35 GB in $(( $(date +%s) - T0 ))s"
lscpu | grep -iE 'model name|^cpu\(s\)|numa node\(s\)' > cpu.txt; cat cpu.txt
df -h /tmp | tee -a cpu.txt
T0=$(date +%s)
python3 -u era5.py > era5.log 2>&1
RC=$?
# Everything in /tmp/out/ is staged to the results prefix, pass or fail.
mkdir -p /tmp/out && cp -f era5.log cpu.txt /tmp/out/ && cp -f era5-results.tsv annual_mean_2023.nc daily_2023.csv /tmp/out/ 2>/dev/null
echo "era5.py exit $RC in $(( $(date +%s) - T0 ))s"
cat era5.log
df -h /tmp
test "$RC" = 0 || { echo "FAIL: the workload failed"; exit 1; }
grep -q 'ERA5 REAL OK' era5.log || { echo "FAIL: no completion sentinel"; exit 1; }
uname -m | awk '{print "arch\t"$1}'
echo DONE
