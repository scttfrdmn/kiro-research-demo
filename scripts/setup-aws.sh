#!/usr/bin/env bash
# One-time setup for Demo 2, in your own AWS account:
#   1. checks era5/run.sh and era5/era5.py still match their pins,
#   2. creates a private bucket for this demo if it does not exist,
#   3. uploads them and the pins,
#   4. writes era5/era5-2023.task.json, the task spec Demo 2 runs.
# Nothing here launches an instance or costs more than a few cents of S3.
cd "$(dirname "$0")/.."
source scripts/common.sh

for f in run.sh era5.py; do
  want=$(awk -v f="$f" '$2 == f {print $1}' era5/pins.sha256)
  got=$(cd era5 && sha256 "$f" | awk '{print $1}')
  if [ "$want" != "$got" ]; then
    echo "era5/$f does not match its pin in era5/pins.sha256." >&2
    echo "If you changed it on purpose, update that line to: $got  $f" >&2
    exit 1
  fi
done

if aws s3api head-bucket --bucket "$BUCKET" --region "$REGION" >/dev/null 2>&1; then
  echo "bucket:  s3://$BUCKET (exists)"
else
  aws s3api create-bucket --bucket "$BUCKET" --region "$REGION" \
    --create-bucket-configuration LocationConstraint="$REGION" >/dev/null
  echo "bucket:  s3://$BUCKET (created, private)"
fi

for f in run.sh era5.py pins.sha256; do
  aws s3 cp --only-show-errors "era5/$f" "$PREFIX/code/$f"
done
echo "uploaded: run.sh, era5.py, pins.sha256 to $PREFIX/code/"

sed "s|__BUCKET__|$BUCKET|g" era5/task.template.json > era5/era5-2023.task.json
echo "wrote:   era5/era5-2023.task.json (results go to $PREFIX/runs/era5-2023/)"
