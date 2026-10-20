# Demo prompts

Typed verbatim in the recordings, so takes are comparable.

## Before recording

- Kiro: Command sandbox **on**; editor and chat font size raised; light theme for projectors.
- `git status` clean on `main`; `tests/` holds only `.gitkeep`; no `.kiro/specs/`.
- `uv run python global_mean.py` prints `Global-mean temperature: 274.999 K` (the wrong answer).

## Demo 1 — IDE, bugfix spec

1. Open `.kiro/steering/research.md` and show it. No prompt.
2. New bugfix spec:

   > The global-mean temperature from `global_mean.py` is biased cold. On a latitude-longitude grid, polar cells are smaller than equatorial cells, but the script weights every grid point equally. Fix it so the mean is area-weighted.

3. Review the generated current-vs-expected behavior and proposed tests; approve. If the tests it proposes compare outputs rather than assert known values, say so in the review and ask for:

   > Tests must assert known values: a constant field returns that constant, and cell areas computed from lat_bnds/lon_bnds sum to 4π to rounding error.

   Also check the requirements document's expected value. In the first rehearsal (Oct 20) the bugfix spec stated the correct mean was 275 K, which is the buggy value, while the tests it wrote used 283.3 K.

4. Run the tasks. The hook runs `pytest` when the agent saves a Python file. Kiro's docs describe `PostFileSave` as firing after the agent saves or edits a file; whether a manual save also fires it is unverified, so check on the first take.
5. Reveal: `python global_mean.py`.

### Reference values for this data file

Computed from `data/sample.nc` as committed (sha256 `766614bd7cd884d131aec35a7eab0b930690789823e9f6f80232ad52a14c5ad6`):

| Quantity | Value |
|---|---|
| Unweighted mean (the bug) | 274.999 K |
| Area-weighted mean, exact cell areas from `lat_bnds`/`lon_bnds` | 283.331 K |
| Error from the bug | 8.33 K too cold |
| Exact cell areas, sum / 4π − 1 | 0.0 |
| cos(latitude) weights, sum / 4π − 1 | 5.08e-5 as absolute areas, but on this regular grid cos(lat) is exactly proportional to cell area, so the normalized mean is identical (difference 5.7e-14 K) |
| Constant field 273.15 K, weighted mean error | 5.7e-14 K |
| Continuous analytic mean of the generating field, 300 − 50/3 | 283.333 K |

The last row is the mean of the smooth field before gridding and noise; the gridded value differs from it by the discretization and the seeded noise, so it is a sanity check with a stated tolerance, not an exact identity.

## Demo 2 — CLI, spore.host

Before: `scripts/setup-aws.sh` has written `era5/era5-2023.task.json`, and `spawn_list` shows nothing named `era5-2023`. Start the CLI with the repo's agent:

```sh
kiro-cli chat --agent research
```

1. Right-size from a measurement, not a guess. Read-only tools; no prompts.

   > The cookbook measured this workload at ~31 GiB peak memory on 8 vCPUs and picked r8g.2xlarge as the best cost per result. Use truffle to confirm r8g.2xlarge is offered in us-west-2, get its On-Demand and Spot prices, and check my On-Demand quota for it. Do not launch anything.

2. See the plan before anything launches. Kiro asks once: approve once, not "trust".

   > Dry-run era5/era5-2023.task.json with spawn_task_run in us-west-2. Show me what it would launch, the TTL, and what happens when the job finishes. Do not launch for real.

3. Launch. Kiro asks again: this is the billable call.

   > Launch era5/era5-2023.task.json for real, On-Demand, in us-west-2.

4. While it runs (about 20 minutes), and again after:

   > What is the status of era5-2023, and what has it cost so far?

5. Bring the results back and check them with the code fixed in Demo 1. These three commands run without asking; nothing else does.

   > Fetch the results, then run my global_mean.py on results/annual_mean_2023.nc and compare it with the C3S published 2023 mean of 14.98 °C.

6. The closing graph.

   > Draw the 2023 graph.

7. Confirm nothing is left running.

   > What do I have running?

### Reference values for the real run

From the Oct 20 rehearsal (`ERA5 REAL OK`), computed by `era5/era5.py` and recomputed independently from its outputs:

| Quantity | Value |
|---|---|
| 2023 global mean, exact cell areas | 14.9829 °C (C3S: 14.98) |
| Same, cos-latitude weights | 14.9830 °C |
| Same, `np.mean` (the bug) | 6.0804 °C — 8.90 °C too cold |
| July 2023 | 16.953 °C (C3S: 16.95) |
| Warmest day | 17.0797 °C on 6 July (C3S: 17.08) |
| r8g.2xlarge On-Demand, us-west-2 | $0.4713/hr (truffle) |
| Billed time, one run | 1190 s: about $0.16 |
