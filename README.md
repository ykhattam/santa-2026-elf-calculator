# Santa 2026 — The Elf Calculator

Execution repository for the Santa 2026 Kaggle competition. Architecture is locked; see
[`SPEC.md`](SPEC.md) for VM semantics and [`config/competition.json`](config/competition.json)
for the machine-readable rule facts seeded into the ledger.

**Hardware budget:** 4-core CPU / 16 GiB RAM
**Timeline:** 2026-11-26 → 2027-01-28 (63 days)
**Target:** Top-3 finish + Rudolph Prize contention
**Baseline:** ~130,100 steps (public, Day 1)

## Current status

| Stage | Window | Status |
|-------|--------|--------|
| Stage 0 — Lock & smoke test | Days 1–2 | **Dual verifier + fuzz harness built** — 0 divergences on 50,020 cases; awaiting real CSVs for parity gate |
| Stage 1 — Full 1,000-puzzle profile | Days 3–4 | Not started |
| Stage 2 — Bandit-routed heavy optimization | Days 5–40 | Not started |
| Stage 3 — Global recipe-graph CP-SAT | Days 41–52 | Not started |
| Stage 4 — Final polish & audit | Days 53–63 | Not started |

Stage 0 gate (not yet passed):
- [x] Semantic divergence = 0 on 50k fuzz corpus (50,020 cases, 2026-11-26)
- [ ] Kaggle live score = local Rust verifier total (exact match)
- [ ] Family classifier trained, ≥ 85% accuracy on `practice_puzzles.csv` held-out fold
- [ ] Prize rules + submission limits recorded in `solutions.db` metadata

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
  --submission data/submission.csv
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
