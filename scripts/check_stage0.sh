#!/usr/bin/env bash
# Stage 0 readiness check. Run from the repository root.
set -euo pipefail

cd "$(dirname "$0")/.."

export PYTHONPATH="python"

echo "== Rust tests =="
cargo test --release --quiet

echo "== Python reference tests =="
python3 -m pytest python/tests -q

echo "== Fuzz corpus (10k local smoke; CI runs 50k) =="
python3 -m elf_verify.cli fuzz --count 10000 --out outputs/fuzz-smoke.ndjson
python3 -m elf_verify.cli differential \
  --cases outputs/fuzz-smoke.ndjson \
  --rust-bin target/release/elf-verify \
  --report outputs/fuzz-smoke-report.json

echo "== Ledger =="
python3 -m elf_verify.cli init-db --db solutions.db

if [[ -f data/puzzles.csv && -f data/sample_submission.csv ]]; then
  echo "== Real data: both verifiers =="
  target/release/elf-verify check --puzzles data/puzzles.csv --submission data/sample_submission.csv --json
  python3 -m elf_verify.cli check --puzzles data/puzzles.csv --submission data/sample_submission.csv --json

  echo "== Family classifier gate =="
  python3 -m elf_verify.cli classify
fi

echo "Stage 0 checks complete."
