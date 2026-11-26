//! Decode a JSON value into a validated `Program`.
//!
//! Real competition format is positional: `[op, i, j, d]` — both source registers
//! first, destination last. This was confirmed against `sample_submission.csv`:
//! 100/100 sample programs replay successfully with this order and 0/100 with
//! `[op, d, i, j]`.

use serde_json::Value;

use crate::model::{Instruction, Op, Program, VerifyConfig, VerifyError};

fn read_register(
    value: &Value,
    field: &'static str,
    index: usize,
    config: &VerifyConfig,
) -> Result<u8, VerifyError> {
    let n = value.as_u64().ok_or_else(|| VerifyError::BadField {
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
        let parts = item.as_array().ok_or_else(|| VerifyError::BadField {
            index,
            field: "instruction",
            reason: "expected a JSON array".to_string(),
        })?;
        if parts.len() != 4 {
            return Err(VerifyError::BadField {
                index,
                field: "instruction",
                reason: format!("expected 4 elements, got {}", parts.len()),
            });
        }

        let op_str = parts[0].as_str().ok_or_else(|| VerifyError::BadField {
            index,
            field: "op",
            reason: "expected a string".to_string(),
        })?;
        let op = Op::parse(op_str).ok_or_else(|| VerifyError::UnknownOp {
            index,
            op: op_str.to_string(),
        })?;

        let i = read_register(&parts[1], "i", index, config)?;
        let j = read_register(&parts[2], "j", index, config)?;
        let d = read_register(&parts[3], "d", index, config)?;

        instructions.push(Instruction { op, d, i, j });
    }

    Ok(Program { instructions })
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn positional_array_decodes() {
        let cfg = VerifyConfig::default();
        let value: Value = serde_json::from_str("[[\"+\",0,1,2],[\"*\",2,2,3]]").unwrap();
        let program = parse_program(&value, &cfg).unwrap();
        assert_eq!(program.instructions.len(), 2);
        assert_eq!(program.instructions[0].i, 0);
        assert_eq!(program.instructions[0].j, 1);
        assert_eq!(program.instructions[0].d, 2);
    }

    #[test]
    fn object_form_is_rejected() {
        let cfg = VerifyConfig::default();
        let value: Value = serde_json::from_str("[{\"op\":\"+\",\"d\":2,\"i\":0,\"j\":1}]").unwrap();
        assert!(parse_program(&value, &cfg).is_err());
    }
}
