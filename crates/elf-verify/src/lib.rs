//! Fast in-loop verifier for the Santa 2026 Elf Calculator VM.
//!
//! The independent Python implementation lives in `python/elf_verify/verifier.py`
//! and is only used in CI/nightly differential runs.

pub mod csv;
pub mod fuzz;
pub mod model;
pub mod parser;
pub mod vm;

pub use model::{
    Instruction, Op, Program, Puzzle, VerifyConfig, VerifyError, VerifyOutcome,
    MAX_CELL_BYTES, MAX_INSTRUCTIONS, MAX_REGISTERS,
};
pub use vm::{is_compact_json, verify_program, verify_submission};
