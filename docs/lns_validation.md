# Local LNS worker — validation result (2026-11-27)

## Acceptance criteria (from the revised plan)

- Single-puzzle worker, deterministic seeds, verification in the loop, improvement logging.
- Test set: top-20 regret puzzles, 5 seeds, 1 h per puzzle per seed (100 CPU-hours).
- Minimum success: ≥5 puzzles improved. Failure: <5 puzzles improved.

## What was built

`python/elf_verify/lns.py` + CLI `lns` / `lns-commit`. The worker destroys one target's
construction strategy and rebuilds it from `{auto, binary, subtractive}`, re-emits the full
program, and verifies it in Python before accepting. Candidates are Rust-verified via
`check --allow-partial` and only then committed with `lns-commit --require-check`.

The builder was checked to reproduce the incumbent program byte-for-byte (5/5 sampled
puzzles), so the test is not biased by a weaker candidate generator.

## Smoke result (not the full campaign)

- 20 puzzles × 5 seeds × 2 s = **100 runs / 200 CPU-seconds**
- `outputs/lns_validation_report.csv`: **0 improved runs, 0 puzzles improved**
- `outputs/lns_candidates.csv`: empty

## Interpretation

This neighborhood is **exhausted by construction**: `improve.py` already selects the
cheaper of binary and subtractive for every target, so re-choosing among
`{auto, binary, subtractive}` can only tie or worsen. Running the full 100 CPU-hour
campaign with this worker would deterministically return zero.

Therefore this is a valid harness validation but **not** a valid test of LNS in general.
Per the forum evidence, gains require a constructor that proposes *new intermediate
values* absent from the incumbent program. The next worker must implement a
value-proposing neighborhood (bridge values, MITM reconstruction of long exclusive
chains) before the full campaign is worth running.

## Follow-up: value-proposing constructor (2026-11-27)

A genuine new constructor was added: **NAF signed-digit chains**. Instead of
re-selecting among existing options, it changes the value DAG by allowing negative
powers of two (`t = Σ ±2^k`). Across all 26,902 targets this cuts nonzero digits by
30.2% with zero invalid partial sums. A power above `value_limit` is rejected
(NAF can carry one bit above the top), falling back to binary for that target.

Result: **551,171 → 442,326 steps** (−19.7%), confirmed by Kaggle score `58991194`.

The LNS re-selection harness was re-run with `naf` added to its neighborhood
(20 puzzles × 3 seeds × 1 s): 60 runs, 0 improvements, as expected — `auto`
already selects the cheapest constructor per target. The gain came from the new
constructor applied globally, not from LNS search.

## Follow-up 2: higher-radix signed digits — no-go (2026-11-27)

Implemented width-4 wNAF (digits ±1, ±3, … ±15) with a shared odd-digit bank.
The theory looked favorable (332,898 vs 354,173 weighted ops across all 26,902
targets), but the odd-digit bank consumes 7 registers, shrinking the power ladder
from 40 to 33 entries. Every high-bit power then needs extra multiplications, which
more than cancels the digit saving.

Measured on 100 puzzles: **wNAF 47,655 vs NAF 44,834 steps** (6.3% worse); wNAF
won on only 9/100 puzzles. Not adopted. Width-5 is worse still because it needs a
15-register odd bank.

Conclusion: under the 48-register constraint, higher radix does not pay. NAF
remains the best constructor found so far.

## Final test: subtractive ceiling + NAF remainder (2026-11-27)

Combined the subtractive construction with NAF for the remainder. Result on 100
puzzles: **44,834 steps — identical to NAF alone**, zero invalid programs. Full
1,000-puzzle rollout produced 0 improvements. Not materially useful; kept because it
is a strict generalization (never worse) of the subtractive path.

## Consolidation

Best verified submission remains **442,326 steps**, Kaggle score `58991194`,
1,000/1,000 rows valid. No further constructor iterations are planned: NAF was the
one measured win, higher-radix regressed, and all re-selection neighborhoods are
locally optimal by construction.

## Reproduce

```bash
PYTHONPATH=python python3 -m elf_verify.cli lns --limit 20 --seeds 5 --seconds 7200 \
  --out outputs/lns_validation_report.csv --submission-out outputs/lns_candidates.csv
```

(Not recommended with the current neighborhood — see above.)
