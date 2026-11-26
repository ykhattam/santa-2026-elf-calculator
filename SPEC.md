# Elf Calculator VM — Working Specification

This file is the executable contract for both verifiers. It is derived from the locked facts
in the execution plan and reconciled against the real Kaggle data on 2026-11-26. The only
early assumption — object-form instructions — was wrong and has been replaced with the
verified positional `[op, i, j, d]` form documented below.

## Registers

- 48 registers, indexed `0..=47`.
- Registers `0..len(starting_values)` are initialized to the corresponding starting values.
  All other registers are undefined.
- Every register value is a strictly positive integer.

## Program representation

A program is a JSON array of instruction arrays serialized compactly
(`separators=(",", ":")`, no insignificant whitespace, UTF-8 encoded).

```json
[["+",0,1,2],["*",2,2,3]]
```

Each instruction is exactly four elements: `[op, i, j, d]` — **both sources first,
destination last**.

| Position | Type | Meaning |
|----------|------|---------|
| `0` (`op`) | string | One of `+`, `-`, `*`, `/` |
| `1` (`i`)  | integer `0..=47` | First source register |
| `2` (`j`)  | integer `0..=47` | Second source register |
| `3` (`d`)  | integer `0..=47` | Destination register |

This order was verified against the real `sample_submission.csv`: 100/100 sampled programs
replay successfully as `[op, i, j, d]`, and 0/100 as `[op, d, i, j]`. Both verifiers reject
any instruction that is not a four-element array.

## Semantics

Both source registers are read **before** the destination is overwritten. Therefore `d == i`,
`d == j`, and `d == i == j` are all valid and use the pre-instruction values.

| op | precondition | result |
|----|--------------|--------|
| `+` | none (beyond defined sources) | `reg[i] + reg[j]` |
| `-` | `reg[i] > reg[j]` (strict) | `reg[i] - reg[j]` |
| `*` | none | `reg[i] * reg[j]` |
| `/` | `reg[j] != 0` and `reg[i] % reg[j] == 0` | `reg[i] / reg[j]` |

Because every value is positive and sources are defined, `+` and `*` cannot produce zero or
negative results; `-` is guarded by the strict inequality and `/` by exact divisibility.

## Limits

| Constraint | Value |
|------------|-------|
| Instruction count | ≤ 4,096 per program |
| Register index | 0–47 |
| Per-step value | `0 < value ≤ value_limit` (≤ 10^18) |
| Cell size | < 131,072 UTF-8 bytes per submission row |
| JSON form | compact, no whitespace outside string literals |

Arithmetic is evaluated with `u128` in Rust (checked add/mul) and arbitrary-precision
integers in Python. The `value_limit` check is applied on **every** step, not just the final
one, and also to starting values at step 0.

## Target coverage

Every target must equal the value of some register at the end of **some** step — not
necessarily the last step. A target present in `starting_values` is covered at step 0.
Duplicate targets are counted once. The verifier tracks the set of all values that appeared
in any register after step 0 and after each instruction.

## Score

One program per puzzle. Score = total number of instructions summed across all 1,000
puzzles. Lower is better. There is no public/private split: public leaderboard = final score.

## Deliberate non-goals for Stage 0

- No semantic equivalence checking between programs.
- No solver logic.
- No optimization of program length.
- No CSV column auto-detection beyond the tolerant heuristics in `csv.rs`.
