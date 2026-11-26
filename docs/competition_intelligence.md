# Competition intelligence — why the Stage 2 ceiling is not a quick fix

Source: official Kaggle competition pages (Description, Evaluation, Data, Rules, Timeline)
and public competition-forum method discussion, retrieved 2026-11-26. **No leaked answer
CSV or third-party solution file was downloaded or used** — the forum explicitly asks
participants not to publish or reuse those files.

## Corrected facts

- Competition **started 2026-11-18**, not 2026-11-26. Today is effectively Day 9.
- Rudolph Prize window: 2026-11-18 → 2027-01-28.
- Final deadline: 2027-01-28 23:59 UTC. Entry/team-merge deadline: 2027-01-21.
- `lower_bound` in `practice_puzzles.csv` is exactly
  `len(set(targets) - set(starting_values))` — a loose bound, not an achievable target.
- Targets are sorted increasing. Score = total instruction count; no partial credit;
  any invalid program rejects the whole submission.

## What the public method discussion established

1. **Independent targets behave like uniform random numbers.** Eleven structural probes
   (ratio links, large GCDs, smooth differences, residue concentration, target-derived
   trunks, etc.) found no generator shortcut for roughly a third of the score. Our own
   experiments agree: bounded forward search to depth 3 covered 0 targets on hard
   puzzles, and 0 targets were reachable in one op from our own value pool.
2. **The public frontier (~128,239–128,486 steps) is a compute/engineering result**, not
   a clever trick. Its builders report long multi-engine campaigns with thousands of
   CPU-hours spent on single-instruction wins.
3. **Cheap levers are exhausted at the frontier**: exact recombination across hundreds
   of programs proved no shorter solution in 152/153 tested puzzles; adding 16 registers
   gained 1 instruction total; Belady rescheduling gained 0 on the frontier (though it
   gains ~16.6% on the naive sample).
4. Register pressure is real but not the binding constraint at the top (48 registers
   are saturated on the most expensive puzzles, yet relaxing to 64 changed almost nothing).

## Consequence for this project

Our 551,171-step submission is valid and verified, but the remaining ~423k gap to the
frontier cannot be closed by a new heuristic discovered in one session. The forum's
estimate of every measurable "clever idea" ceiling adds up to far less than the gap.

Legitimate remaining levers (all expensive):
- deep value-DAG LNS / beam search with restarts and plateau moves,
- GPU meet-in-the-middle rebuilds of ~887 long exclusive chains (ceiling ~1,176 steps),
- multi-engine, multi-seed campaigns over weeks.

We will not use the public frontier CSV as a shortcut; that conflicts with the
competition's data-sharing guidance and with the spirit of the rules.
