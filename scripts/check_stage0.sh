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

echo "Stage 0 scaffolding OK (parity gate still requires real Kaggle CSVs)."
