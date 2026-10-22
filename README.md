# kiro-research-demo

The demo repository for the talk *From Research Question to Results: Kiro, Specs, and MCP for Academic Research*. Everything shown in the talk runs from this README, in your own AWS account.

**This repository contains a deliberate bug.** `global_mean.py` averages temperature over every grid point equally. On a latitude–longitude grid, cells near the poles are much smaller than cells near the equator, so an unweighted mean overweights the poles and comes out too cold. On a full year of real data the bug is not subtle:

| 2023 global-mean 2 m temperature (ERA5) | Value |
|---|---|
| `np.mean(temp)`, every grid point equal (the bug) | 6.08 °C |
| Area-weighted | 14.98 °C |
| Published by Copernicus C3S | 14.98 °C |

Demo 1 finds and fixes the bug on a small synthetic file whose correct answer is known exactly. Demo 2 runs a full year of hourly ERA5 data on AWS and checks your fixed code against the published value. Do not fix the bug on `main`; the demos start from it.

## What you need

| | |
|---|---|
| AWS | An account whose credentials work in your shell (`aws sts get-caller-identity`). Demo 2 runs in **us-west-2**, where the ERA5 mirror lives. It needs permission to launch EC2 instances, create an IAM instance profile, and create one S3 bucket, and a network to launch into: the default VPC in us-west-2, or, if your account has none, a subnet that gives instances public IPs. `scripts/setup-aws.sh` finds one, or set `SUBNET=subnet-...` to choose. Needs spawn 0.140.0 or later. |
| Cost | One Demo 2 run is about **$0.16**: an r8g.2xlarge On-Demand for about 20 minutes. The task spec caps it: a 45-minute TTL, termination when the job finishes, and a $0.50 cost limit. Results in S3 cost cents per month. |
| Kiro | The [Kiro IDE](https://kiro.dev) for Demo 1 and the [Kiro CLI](https://kiro.dev/docs/cli/) (`kiro-cli`) for Demo 2, both signed in. |
| spore.host | `brew install spore-host/tap/spore-host-mcp` (0.43.0 or later) — the MCP server that gives Kiro the truffle and spawn tools ([spore-host-mcp](https://github.com/spore-host/spore-host-mcp)). |
| Python | [uv](https://docs.astral.sh/uv/). |

```sh
git clone https://github.com/scttfrdmn/kiro-research-demo && cd kiro-research-demo
uv venv && uv pip install -r requirements.txt
uv run python global_mean.py          # Global-mean temperature: 274.999 K  (the wrong answer)
```

## Demo 1 — find and fix the bug (Kiro IDE)

Open this folder in the Kiro IDE. The prompts are in [`demo/prompts.md`](demo/prompts.md), typed verbatim in the talk.

1. Read `.kiro/steering/research.md`, the lab rules Kiro loads into every session: tests assert known values, tolerances are stated, no number is reported that was not computed.
2. Start a **bugfix spec** with the Demo 1 prompt. Review what it proposes before approving: the expected value, and whether its tests assert known values.
3. Run the tasks. The hook in `.kiro/hooks/identity-tests.json` runs `pytest` every time Kiro saves a Python file.
4. `uv run python global_mean.py` should now print **283.331 K**.

Kiro writes different code on different runs. What makes a fix correct is the tests, not matching anyone else's code.

## Demo 2 — the real year on AWS (Kiro CLI)

One-time setup, in your account. This creates a private bucket named `kiro-research-demo-<account>-us-west-2`, uploads the runner and its checksums, and writes `era5/era5-2023.task.json`. It launches nothing.

```sh
scripts/setup-aws.sh
```

Then start the CLI with this repository's agent and use the Demo 2 prompts from [`demo/prompts.md`](demo/prompts.md):

```sh
kiro-cli chat --agent research
```

If you use a named AWS profile, `export AWS_PROFILE=<name>` first; the spore.host server inherits it.

What happens:

- **Right-sizing** (`truffle_find`, `truffle_spot_prices`, `truffle_quota_check`): the instance comes from a measurement of this workload, not a guess.
- **Dry run, then launch** (`spawn_task_run`): Kiro asks before each call. The instance reads 12 monthly ERA5 files (13.35 GB) straight from the public mirror, checks every file against `era5/pins.sha256`, and runs `era5/run.sh`, which runs `era5/era5.py`.
- **The instance ends itself** when the job finishes; `spawn_status` reports the outcome and the cost.
- **Results** (`results/`): your fixed `global_mean.py` runs on the year's annual-mean field and should print **288.133 K** (14.98 °C). On `main` it prints 279.230 K (6.08 °C).
- **The graph**: `results/era5-2023.png`, the daily 2023 global mean, area-weighted against `np.mean`.

You can also run the last steps yourself:

```sh
scripts/fetch-results.sh
uv run python global_mean.py results/annual_mean_2023.nc
uv run plot_2023.py
```

`era5/era5.py` checks its own work before it prints `ERA5 REAL OK`: the area weights sum to the sphere exactly, every day has 24 hours, time and area averages commute, dask matches an eager re-read, and the annual, July and record-day values match C3S to ±0.01 °C. If any check fails, the run fails.

## What the agent may do

`.kiro/agents/research.json` is the whole of the `research` agent's toolbelt, and it is meant to be read:

| Without asking | Asks first | Not available |
|---|---|---|
| Read files in the repo; truffle and other read-only spore.host tools; `scripts/fetch-results.sh`, the `global_mean.py` check, `plot_2023.py` | `spawn_task_run`, `spawn_terminate`, any other shell command | Web search and fetch, direct AWS API calls |

## Cleaning up

```sh
kiro-cli chat --agent research "What do I have running?"     # expect nothing named era5-2023
aws s3 rb "s3://kiro-research-demo-$(aws sts get-caller-identity --query Account --output text)-us-west-2" --force
```

The second command deletes the demo bucket and everything in it. spawn keeps the IAM instance profile it created for the task, and reuses it on later runs; it costs nothing.

## Files

| Path | What it is |
|---|---|
| `global_mean.py` | The analysis script, with the bug |
| `make_sample.py`, `data/sample.nc` | The synthetic test file for Demo 1 (fixed seed) |
| `tests/` | Empty on `main`; Demo 1 fills it |
| `.kiro/steering/research.md` | Lab rules loaded into every Kiro session |
| `.kiro/hooks/identity-tests.json` | Runs `pytest` whenever a Python file is saved |
| `uv.toml` | Keeps uv's cache in `.uv-cache/`, inside the repo, where Kiro's command sandbox allows writes |
| `.kiro/agents/research.json` | The Demo 2 agent and what it may do |
| `.kiro/settings/mcp.json` | Connects Kiro to spore-host-mcp |
| `era5/run.sh`, `era5/era5.py`, `era5/pins.sha256` | The task script, the ERA5 runner, and the checksums of everything the instance reads |
| `era5/task.template.json` | The Demo 2 task spec; `scripts/setup-aws.sh` fills in your bucket |
| `scripts/` | Setup and fetch |
| `plot_2023.py` | The closing graph |
| `demo/prompts.md` | The prompts used in the talk, and reference values |

## Resetting between takes

```sh
git checkout main -- . && git clean -fd tests .kiro/specs
```

## Data and credits

Generated using Copernicus Climate Change Service information 2023. ERA5 hourly data on single levels, read from the NSF NCAR Research Data Archive's mirror on the AWS Open Data registry (dataset ds633.0, `s3://nsf-ncar-era5`). Reference values from C3S Global Climate Highlights 2023. `era5/era5.py` is adapted from the scientific-codes-cookbook recipe `measurements/climate-real`.

Licensed under the [Apache License 2.0](LICENSE).
