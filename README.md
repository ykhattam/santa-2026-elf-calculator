# Santa 2026 — The Elf Calculator

Execution repository for the Santa 2026 Kaggle competition. Architecture is locked; see
[`SPEC.md`](SPEC.md) for VM semantics and [`config/competition.json`](config/competition.json)
for the machine-readable rule facts seeded into the ledger.

**Hardware budget:** 4-core CPU / 16 GiB RAM
**Timeline:** competition started 2026-11-18 (today is ~Day 9); deadline 2027-01-28.
See [`docs/competition_intelligence.md`](docs/competition_intelligence.md) for corrected
facts and why the ceiling is not a quick fix.
**Target:** Top-3 finish + Rudolph Prize contention
**Baseline:** 124,494 steps (live leaderboard best observed 2026-11-26); sample submission verifies at 1,490,379 steps

## Current status

| Stage | Window | Status |
|-------|--------|--------|
| Stage 0 — Lock & smoke test | Days 1–2 | **GATE PASSED** (2026-11-26) — dual verifiers, 0 divergences on 50,020 cases, Kaggle parity exact, classifier 92.5% |
| Stage 1 — Full 1,000-puzzle profile | Days 3–4 | **GATE PASSED** — 100% baseline coverage, 591,002 steps, regret 551,843 |
| Stage 2 — Bandit-routed heavy optimization | Days 5–40 | **CONSOLIDATED** — NAF chains: 551,171 → **442,326** steps (Kaggle confirmed); ceiling still missed |
| Stage 3 — Global recipe-graph CP-SAT | Days 41–52 | Not started |
| Stage 4 — Final polish & audit | Days 53–63 | Not started |

Stage 0 gate — **passed 2026-11-26**:
- [x] Semantic divergence = 0 on 50k fuzz corpus (50,020 cases)
- [x] Kaggle live score = local verifier total (1,490,379, exact match, submission `58947698`)
- [x] Family classifier trained, 92.5% 5-fold CV accuracy on `practice_puzzles.csv` (gate: 85%)
- [x] Prize rules + submission limits recorded in `solutions.db` metadata
- [x] All 1,000 puzzles seeded into `solutions.db` with predicted pseudo-families

Stage 1 gate — **passed 2026-11-26**:
- [x] 100% of puzzles have a verifier-approved baseline in `solutions.db`
- [x] Total baseline steps computed: **591,002** (sample was 1,490,379; plan's 130k reference is not yet met — Stage 2 must close the gap)
- [x] Lower bounds (39,159 total) and absolute-regret ranking (551,843 total) published to `outputs/regret_ranking.csv`
- [x] Yield priors per pseudo-family published to `outputs/yield_baseline.csv`
- [x] Memory high-water measured (25 MB); Stage 2 subprocess cap set to 2,100 MB (measured + ~2 GiB margin)

Stage 2 progress (2026-11-26):
- [x] Bandit allocator (85% regret exploit / 15% family exploration, stalled-family throttle)
- [x] Subtractive-cone solver: `t = 2^k - d` chosen when cheaper than binary expansion
- [x] Two verified rounds; 863 puzzles improved by the subtractive solver (551,171 steps)
- [x] NAF signed-digit constructor: 867 further improvements, best total **442,326** (Kaggle score `58991194`)
- [x] Daily export `outputs/submission.csv`, full verifier check passes
- [ ] Ceiling gates: **missed** — Day 15 target <128,000 vs current 551,171

Ceiling diagnosis (updated after checking official pages + public forum method threads):
independent targets are uniform random numbers with no generator shortcut; the public
frontier (~128,239 steps) is the product of weeks of multi-engine search, not one trick.
Cheap levers (recombination, register relaxation, rescheduling) are already exhausted there.
We will not use leaked frontier answer files. A full resolution requires a long compute
campaign, not a single new heuristic — see `docs/competition_intelligence.md`.

Local LNS worker status: harness built and verified; re-selection neighborhoods
return 0 gains by construction. A genuine value-proposing constructor (NAF signed-digit
chains) delivered −19.7%; see [`docs/lns_validation.md`](docs/lns_validation.md).
Further gains require new constructors, not more re-selection. Width-4 wNAF was
tested and rejected (6.3% worse — its odd-digit bank shrinks the power ladder), and
subtractive+NAF produced zero further gains. See `docs/lns_validation.md`.

## Architecture (locked — do not add more)

```
PYTHON ORCHESTRATOR (1 core, pinned)
  SQLite ledger (solutions.db) | stage gates + kill criteria | alerting
  bandit allocator (stratified by pseudo-family) | family classifier
            |
            v
RUST CORE (3 cores, pinned)
  elf-verify (in-loop, u128) | solver portfolio (one heavy at a time)
            |
            v
CI / NIGHTLY (off-loop)
  Python reference verifier | conformance corpus | Kaggle parity check
```

Hard invariants: one heavy solver at a time; Rust verifier in-loop, Python only in CI/nightly;
per-puzzle subprocess isolation with measured memory caps; all outputs immutable in SQLite with
idempotent resume; no global hypergraph across puzzles.

## Layout

```
crates/elf-verify/     Rust verifier (library + CLI: check, fuzz)
python/elf_verify/     Independent Python reference verifier + fuzzer + ledger
python/tests/          Python unit tests
config/                Machine-readable competition facts
sql/                   SQLite schema
scripts/               Readiness + orchestration helpers
data/                  Drop site for Kaggle CSVs (gitignored)
outputs/               Generated submissions and reports (gitignored)
```

## Quick start

```bash
# Build the Rust verifier
cargo build --release

# Initialize the provenance ledger and seed competition metadata
python3 -m elf_verify.cli init-db --db solutions.db

# Generate the 50k differential fuzz corpus (deterministic)
python3 -m elf_verify.cli fuzz --count 50000 --seed 20261126 --out outputs/fuzz.ndjson

# Run both verifiers and compare accept/reject + step count
python3 -m elf_verify.cli differential \
  --cases outputs/fuzz.ndjson \
  --rust-bin target/release/elf-verify

# Verify a real submission once the CSVs are in data/
target/release/elf-verify check \
  --puzzles data/puzzles.csv \
  --submission data/sample_submission.csv

# Train the family classifier and seed the ledger with all 1,000 puzzles
python3 -m elf_verify.cli classify
python3 -m elf_verify.cli seed-puzzles

# Stage 1 fast sweep (verify before seeding — --require-check enforces this)
python3 -m elf_verify.cli baseline
target/release/elf-verify check \
  --puzzles data/puzzles.csv --submission outputs/baseline_submission.csv --json \
  > outputs/baseline_check.json
python3 -m elf_verify.cli seed-solutions --submission data/sample_submission.csv --tag sample_greedy
python3 -m elf_verify.cli seed-solutions \
  --submission outputs/baseline_submission.csv --tag baseline_shared_powers \
  --require-check outputs/baseline_check.json
python3 -m elf_verify.cli profile
python3 -m elf_verify.cli yield
```

`PYTHONPATH=python` is required for the Python CLI unless a virtualenv is configured.

## What is deliberately NOT here yet

- Solver portfolio (BFS/IDDFS, backward search, e-graph, LNS, SA/GP)
- CP-SAT recipe merging
- Family classifier (needs `practice_puzzles.csv`)
- Bandit allocator and alerting daemon

These are Stage 1+ work and are intentionally absent to keep Stage 0 simple.

## Provenance

Every accepted solution will be written to `solutions.db` with
`(puzzle_id, steps, solver_tag, program_json, sha256, verified_at, git_sha, seed)`.
No solution is written unless the Rust verifier exits 0.
