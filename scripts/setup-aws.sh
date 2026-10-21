#!/usr/bin/env bash
# One-time setup for Demo 2, in your own AWS account:
#   1. checks era5/run.sh and era5/era5.py still match their pins,
#   2. creates a private bucket for this demo if it does not exist,
#   3. uploads them and the pins,
#   4. writes era5/era5-2023.task.json, the task spec Demo 2 runs, with the network to use.
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

# Where the task's instance goes. With a default VPC, spawn uses it. Without one (as in
# accounts built by Control Tower), the task names a subnet: SUBNET=subnet-... if you set
# it, otherwise one that gives instances a public IP, so they reach S3 and the ERA5 mirror.
default_vpc=$(aws ec2 describe-vpcs --region "$REGION" --filters Name=is-default,Values=true \
  --query 'Vpcs[0].VpcId' --output text 2>/dev/null)
if [ -n "${SUBNET:-}" ]; then
  echo "network: subnet $SUBNET (from SUBNET)"
elif [ -n "$default_vpc" ] && [ "$default_vpc" != "None" ]; then
  SUBNET=""
  echo "network: the default VPC in $REGION"
else
  SUBNET=$(aws ec2 describe-subnets --region "$REGION" --filters Name=map-public-ip-on-launch,Values=true \
    --query 'sort_by(Subnets, &AvailabilityZone)[0].SubnetId' --output text 2>/dev/null)
  if [ -z "$SUBNET" ] || [ "$SUBNET" = "None" ]; then
    echo "No default VPC in $REGION and no subnet that maps public IPs." >&2
    echo "Set SUBNET=subnet-... to a subnet with a route to S3, or: aws ec2 create-default-vpc --region $REGION" >&2
    exit 1
  fi
  echo "network: no default VPC in $REGION; using public subnet $SUBNET (set SUBNET=... to choose another)"
fi

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

sed -e "s|__BUCKET__|$BUCKET|g" -e "s|__SUBNET__|$SUBNET|g" era5/task.template.json > era5/era5-2023.task.json
echo "wrote:   era5/era5-2023.task.json (results go to $PREFIX/runs/era5-2023/)"
