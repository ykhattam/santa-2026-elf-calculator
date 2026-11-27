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

## Reproduce

```bash
PYTHONPATH=python python3 -m elf_verify.cli lns --limit 20 --seeds 5 --seconds 7200 \
  --out outputs/lns_validation_report.csv --submission-out outputs/lns_candidates.csv
```

(Not recommended with the current neighborhood — see above.)
