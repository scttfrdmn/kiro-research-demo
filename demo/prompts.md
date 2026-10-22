# Demo prompts

Typed verbatim in the recordings, so takes are comparable.

## Before recording

- Kiro: Autopilot on, command sandbox on; editor and chat font size raised; light theme.
- `git status` clean on `main`; `tests/` holds only `.gitkeep`; no `.kiro/specs/`.
- `uv run python global_mean.py` prints `Global-mean temperature: 274.999 K` (the wrong answer).

## Demo 1 — IDE, bugfix spec

1. Open `.kiro/steering/research.md` and show it. No prompt.
2. New bugfix spec:

   > `global_mean.py` weights every grid point equally, so the poles count too much. Weight by cos(latitude).

3. Review the spec. If its tests don't assert a known answer, reply:

   > Tests: a constant field returns that constant.

4. Run all tasks. The hook runs the tests when the agent saves a Python file.
5. Reveal: `uv run python global_mean.py` prints `283.331 K`.

The proportionate fix is one line:

```python
return float(ds["tas"].weighted(np.cos(np.deg2rad(ds["lat"]))).mean())
```

For comparison, the first delivery's take (v5, PR #2, before the sizing rule) changed 12 lines and wrote 442 lines of tests and 4,713 words of spec.

## Demo 2 — CLI, spore.host

Before: `scripts/setup-aws.sh` has written `era5/era5-2023.task.json`. Start the CLI with the repo's agent:

```sh
kiro-cli chat --agent research
```

1. Read-only; no approvals.

   > Use truffle to confirm r8g.2xlarge is offered in us-west-2, its On-Demand price, and my quota for it. Don't launch anything.

2. The billable call. Kiro asks once: approve once, not "trust".

   > Launch era5/era5-2023.task.json in us-west-2.

3. About 20 minutes later:

   > Fetch the results, run global_mean.py on results/annual_mean_2023.nc, and confirm nothing is still running.

### Reference values

| Quantity | Value |
|---|---|
| `data/sample.nc`, unweighted (the bug) | 274.999 K |
| `data/sample.nc`, area-weighted | 283.331 K |
| ERA5 2023, area-weighted | 288.133 K (14.98 °C) |
| One Demo 2 run, r8g.2xlarge On-Demand | about $0.16 |
