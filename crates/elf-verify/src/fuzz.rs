//! Batch interface used by the differential fuzz harness.
//!
//! Input is newline-delimited JSON:
//!   {"id":"...", "puzzle":{"id":...,"starting_values":[...],"targets":[...],"value_limit":N},
//!    "program_json":"..."}
//!
//! Output is newline-delimited JSON:
//!   {"id":"...","ok":true,"steps":N}
//!   {"id":"...","ok":false,"reason":"..."}

use serde_json::Value;

use crate::model::{Puzzle, VerifyConfig, VerifyError, VerifyOutcome};
use crate::vm::verify_submission;

pub struct FuzzCase {
    pub id: String,
    pub puzzle: Puzzle,
    pub program_json: String,
}

fn number_array(value: Option<&Value>, field: &str) -> Result<Vec<u128>, String> {
    let array = value
        .and_then(Value::as_array)
        .ok_or_else(|| format!("puzzle.{field} must be an array"))?;
    array
        .iter()
        .map(|v| {
            v.as_u64()
                .map(u128::from)
                .ok_or_else(|| format!("puzzle.{field} contains a non-negative integer out of range"))
        })
        .collect()
}

pub fn decode_case(value: &Value) -> Result<FuzzCase, String> {
    let id = value
        .get("id")
        .and_then(Value::as_str)
        .unwrap_or("")
        .to_string();
    let raw = value.get("puzzle").ok_or("missing puzzle")?;
    let puzzle_id = raw
        .get("id")
        .and_then(Value::as_str)
        .unwrap_or(&id)
        .to_string();
    let value_limit = raw
        .get("value_limit")
        .and_then(Value::as_u64)
        .map(u128::from)
        .ok_or("puzzle.value_limit must be a non-negative integer")?;

    Ok(FuzzCase {
        id,
        puzzle: Puzzle {
            id: puzzle_id,
            starting_values: number_array(raw.get("starting_values"), "starting_values")?,
            targets: number_array(raw.get("targets"), "targets")?,
            value_limit,
        },
        program_json: value
            .get("program_json")
            .and_then(Value::as_str)
            .ok_or("missing program_json")?
            .to_string(),
    })
}

pub fn result_line(case: &FuzzCase, result: Result<VerifyOutcome, VerifyError>) -> String {
    match result {
        Ok(outcome) => format!(
            "{{\"id\":{},\"ok\":true,\"steps\":{}}}",
            serde_json::to_string(&case.id).unwrap_or_else(|_| "\"\"".to_string()),
            outcome.steps
        ),
        Err(error) => format!(
            "{{\"id\":{},\"ok\":false,\"reason\":{}}}",
            serde_json::to_string(&case.id).unwrap_or_else(|_| "\"\"".to_string()),
            serde_json::to_string(&error.to_string()).unwrap_or_else(|_| "\"error\"".to_string())
        ),
    }
}

pub fn verify_case(case: &FuzzCase, config: &VerifyConfig) -> Result<VerifyOutcome, VerifyError> {
    verify_submission(&case.puzzle, &case.program_json, config)
}
