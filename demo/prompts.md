# Demo prompts

Typed verbatim in the recordings, so takes are comparable.

## Before recording

- Kiro: Command sandbox **on**; editor and chat font size raised; light theme for projectors.
- `git status` clean on `main`; `tests/` holds only `.gitkeep`; no `.kiro/specs/`.
- `python global_mean.py` prints `Global-mean temperature: 274.999 K` (the wrong answer).

## Demo 1 — IDE, bugfix spec

1. Open `.kiro/steering/research.md` and show it. No prompt.
2. New bugfix spec:

   > The global-mean temperature from `global_mean.py` is biased cold. On a latitude-longitude grid, polar cells are smaller than equatorial cells, but the script weights every grid point equally. Fix it so the mean is area-weighted.

3. Review the generated current-vs-expected behavior and proposed tests; approve. If the tests it proposes compare outputs rather than assert known values, say so in the review and ask for:

   > Tests must assert known values: a constant field returns that constant, and cell areas sum to 4π to rounding error.

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
| cos(latitude) weights, sum / 4π − 1 | 5.08e-5 (approximate, not exact) |
| Constant field 273.15 K, weighted mean error | 5.7e-14 K |
| Continuous analytic mean of the generating field, 300 − 50/3 | 283.333 K |

The last row is the mean of the smooth field before gridding and noise; the gridded value differs from it by the discretization and the seeded noise, so it is a sanity check with a stated tolerance, not an exact identity.

## Demo 2 — CLI, spore.host

Prompts are in the talk outline, section 6. To be finalized when the TaskSpec and container image are pinned.
