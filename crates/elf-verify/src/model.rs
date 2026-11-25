//! Core data model for the Elf Calculator VM.
//!
//! This module intentionally contains no verification logic; see `vm.rs`.

use std::fmt;

pub const MAX_REGISTERS: u8 = 48;
pub const MAX_INSTRUCTIONS: usize = 4_096;
pub const MAX_CELL_BYTES: usize = 131_072;

#[derive(Debug, Clone)]
pub struct Puzzle {
    pub id: String,
    pub starting_values: Vec<u128>,
    pub targets: Vec<u128>,
    pub value_limit: u128,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum Op {
    Add,
    Sub,
    Mul,
    Div,
}

impl Op {
    pub fn parse(s: &str) -> Option<Self> {
        match s {
            "+" => Some(Op::Add),
            "-" => Some(Op::Sub),
            "*" => Some(Op::Mul),
            "/" => Some(Op::Div),
            _ => None,
        }
    }

    #[allow(dead_code)]
    pub fn as_str(self) -> &'static str {
        match self {
            Op::Add => "+",
            Op::Sub => "-",
            Op::Mul => "*",
            Op::Div => "/",
        }
    }
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub struct Instruction {
    pub op: Op,
    pub d: u8,
    pub i: u8,
    pub j: u8,
}

#[derive(Debug, Clone)]
pub struct Program {
    pub instructions: Vec<Instruction>,
}

#[derive(Debug, Clone)]
pub struct VerifyConfig {
    pub max_instructions: usize,
    pub max_registers: u8,
    pub max_cell_bytes: usize,
    pub strict_compact_json: bool,
}

impl Default for VerifyConfig {
    fn default() -> Self {
        Self {
            max_instructions: MAX_INSTRUCTIONS,
            max_registers: MAX_REGISTERS,
            max_cell_bytes: MAX_CELL_BYTES,
            strict_compact_json: true,
        }
    }
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct VerifyOutcome {
    pub steps: usize,
    pub targets_covered: usize,
    pub max_value_seen: u128,
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub enum VerifyError {
    ProgramTooLarge { bytes: usize, max: usize },
    NonCompactJson,
    MalformedProgram(String),
    TooManyInstructions { got: usize, max: usize },
    BadField { index: usize, field: &'static str, reason: String },
    UnknownOp { index: usize, op: String },
    RegisterOutOfRange { index: usize, field: &'static str, value: u64, max: u8 },
    UndefinedSource { index: usize, field: &'static str, register: u8 },
    NegativeResult { index: usize, a: u128, b: u128 },
    DivisionByZero { index: usize },
    NonExactDivision { index: usize, a: u128, b: u128 },
    Overflow { index: usize, op: &'static str },
    NonPositiveIntermediate { index: usize },
    ValueLimitExceeded { index: usize, value: u128, limit: u128 },
    UncoveredTarget { target: u128 },
    InvalidPuzzle(String),
}

impl fmt::Display for VerifyError {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        match self {
            VerifyError::ProgramTooLarge { bytes, max } => {
                write!(f, "program is {bytes} bytes, cap is {max}")
            }
            VerifyError::NonCompactJson => write!(f, "program JSON contains insignificant whitespace"),
            VerifyError::MalformedProgram(msg) => write!(f, "malformed program: {msg}"),
            VerifyError::TooManyInstructions { got, max } => {
                write!(f, "{got} instructions exceeds cap {max}")
            }
            VerifyError::BadField { index, field, reason } => {
                write!(f, "instruction {index} field {field}: {reason}")
            }
            VerifyError::UnknownOp { index, op } => write!(f, "instruction {index}: unknown op {op:?}"),
            VerifyError::RegisterOutOfRange { index, field, value, max } => {
                write!(f, "instruction {index}: {field}={value} outside 0..{max}")
            }
            VerifyError::UndefinedSource { index, field, register } => {
                write!(f, "instruction {index}: {field} register {register} is undefined")
            }
            VerifyError::NegativeResult { index, a, b } => {
                write!(f, "instruction {index}: subtraction {a} - {b} is not positive")
            }
            VerifyError::DivisionByZero { index } => write!(f, "instruction {index}: division by zero"),
            VerifyError::NonExactDivision { index, a, b } => {
                write!(f, "instruction {index}: {a} is not divisible by {b}")
            }
            VerifyError::Overflow { index, op } => write!(f, "instruction {index}: {op} overflowed u128"),
            VerifyError::NonPositiveIntermediate { index } => {
                write!(f, "instruction {index}: non-positive intermediate value")
            }
            VerifyError::ValueLimitExceeded { index, value, limit } => {
                write!(f, "instruction {index}: value {value} exceeds limit {limit}")
            }
            VerifyError::UncoveredTarget { target } => write!(f, "target {target} was never covered"),
            VerifyError::InvalidPuzzle(msg) => write!(f, "invalid puzzle: {msg}"),
        }
    }
}
