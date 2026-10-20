# Shared settings for the setup and fetch scripts. Sourced, not run.
# Uses whatever AWS credentials your shell has (AWS_PROFILE is honoured).
set -euo pipefail

# The ERA5 mirror (s3://nsf-ncar-era5, AWS Open Data) is in us-west-2; run next to the data.
REGION=us-west-2
ACCOUNT=$(aws sts get-caller-identity --query Account --output text)
# Your bucket for the runner, its pins and the results. Override with BUCKET=... if you like.
BUCKET=${BUCKET:-kiro-research-demo-$ACCOUNT-$REGION}
PREFIX="s3://$BUCKET"

sha256() { if command -v sha256sum >/dev/null 2>&1; then sha256sum "$@"; else shasum -a 256 "$@"; fi; }
