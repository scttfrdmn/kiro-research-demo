# kiro-research-demo

Demo repository for the talk *From Research Question to Results: Kiro, Specs, and MCP for Academic Research*.

**This repository contains a deliberate bug.** `global_mean.py` averages temperature over every grid point equally. On a latitude-longitude grid, cells near the poles are much smaller than cells near the equator, so an unweighted mean overweights the poles and comes out too cold. Demo 1 fixes this with a Kiro bugfix spec. Do not fix it in `main`.

## Contents

| Path | What it is |
|---|---|
| `global_mean.py` | The analysis script, with the unweighted-mean bug |
| `make_sample.py` | Builds `data/sample.nc` deterministically (fixed seed) |
| `data/sample.nc` | Synthetic monthly temperature field, 2-degree grid, 12 months |
| `tests/` | Empty; Demo 1 fills it |
| `.kiro/steering/research.md` | Lab rules loaded into every Kiro session |
| `.kiro/hooks/identity-tests.json` | Runs `pytest` whenever a Python file is saved |
| `demo/prompts.md` | The exact prompts used in the recorded demos |

## Setup

```sh
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python make_sample.py        # only needed if data/sample.nc is missing
python global_mean.py        # prints the (wrong) unweighted mean
```

## Resetting between takes

```sh
git checkout main -- . && git clean -fd tests .kiro/specs
```
