//! Decode a JSON value into a validated `Program`.
//!
//! The parser is deliberately strict about instruction shape but tolerant of extra keys,
//! since the competition format is pinned by `SPEC.md` and extra keys may be added later.

use serde_json::Value;

use crate::model::{Instruction, Op, Program, VerifyConfig, VerifyError};

fn read_register(
    obj: &serde_json::Map<String, Value>,
    field: &'static str,
    index: usize,
    config: &VerifyConfig,
) -> Result<u8, VerifyError> {
    let raw = obj.get(field).ok_or_else(|| VerifyError::BadField {
        index,
        field,
        reason: "missing field".to_string(),
    })?;
    let n = raw.as_u64().ok_or_else(|| VerifyError::BadField {
        index,
        field,
        reason: "expected a non-negative integer".to_string(),
    })?;
    if n >= config.max_registers as u64 {
        return Err(VerifyError::RegisterOutOfRange {
            index,
            field,
            value: n,
            max: config.max_registers,
        });
    }
    Ok(n as u8)
}

pub fn parse_program(value: &Value, config: &VerifyConfig) -> Result<Program, VerifyError> {
    let array = value.as_array().ok_or_else(|| {
        VerifyError::MalformedProgram("top-level JSON value must be an array".to_string())
    })?;

    if array.len() > config.max_instructions {
        return Err(VerifyError::TooManyInstructions {
            got: array.len(),
            max: config.max_instructions,
        });
    }

    let mut instructions = Vec::with_capacity(array.len());

    for (index, item) in array.iter().enumerate() {
        let obj = item.as_object().ok_or_else(|| VerifyError::BadField {
            index,
            field: "instruction",
            reason: "expected a JSON object".to_string(),
        })?;

        let op_raw = obj.get("op").ok_or_else(|| VerifyError::BadField {
            index,
            field: "op",
            reason: "missing field".to_string(),
        })?;
        let op_str = op_raw.as_str().ok_or_else(|| VerifyError::BadField {
            index,
            field: "op",
            reason: "expected a string".to_string(),
        })?;
        let op = Op::parse(op_str).ok_or_else(|| VerifyError::UnknownOp {
            index,
            op: op_str.to_string(),
        })?;

        let d = read_register(obj, "d", index, config)?;
        let i = read_register(obj, "i", index, config)?;
        let j = read_register(obj, "j", index, config)?;

        instructions.push(Instruction { op, d, i, j });
    }

    Ok(Program { instructions })
}
