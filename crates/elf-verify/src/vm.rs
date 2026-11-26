//! Reference VM replay for the Elf Calculator.
//!
//! Both sources are read before the destination is written, so operand aliasing
//! (`d == i`, `d == j`, `d == i == j`) is naturally supported.

use std::collections::HashSet;

use crate::model::{Op, Puzzle, VerifyConfig, VerifyError, VerifyOutcome};
use crate::parser::parse_program;

/// Returns true when every whitespace character sits inside a JSON string literal.
pub fn is_compact_json(text: &str) -> bool {
    let mut in_string = false;
    let mut escaped = false;

    for ch in text.chars() {
        if in_string {
            if escaped {
                escaped = false;
            } else if ch == '\\' {
                escaped = true;
            } else if ch == '"' {
                in_string = false;
            }
            continue;
        }

        match ch {
            '"' => in_string = true,
            ' ' | '\t' | '\n' | '\r' => return false,
            _ => {}
        }
    }
    true
}

pub fn verify_submission(
    puzzle: &Puzzle,
    program_json: &str,
    config: &VerifyConfig,
) -> Result<VerifyOutcome, VerifyError> {
    let bytes = program_json.len();
    if bytes > config.max_cell_bytes {
        return Err(VerifyError::ProgramTooLarge {
            bytes,
            max: config.max_cell_bytes,
        });
    }
    if config.strict_compact_json && !is_compact_json(program_json) {
        return Err(VerifyError::NonCompactJson);
    }

    let value: serde_json::Value = serde_json::from_str(program_json)
        .map_err(|e| VerifyError::MalformedProgram(e.to_string()))?;
    let program = parse_program(&value, config)?;
    verify_program(puzzle, &program, config)
}

pub fn verify_program(
    puzzle: &Puzzle,
    program: &crate::model::Program,
    config: &VerifyConfig,
) -> Result<VerifyOutcome, VerifyError> {
    if puzzle.starting_values.is_empty() {
        return Err(VerifyError::InvalidPuzzle(
            "starting_values must not be empty".to_string(),
        ));
    }
    if puzzle.value_limit == 0 {
        return Err(VerifyError::InvalidPuzzle(
            "value_limit must be positive".to_string(),
        ));
    }

    let width = config.max_registers as usize;
    let mut registers: Vec<Option<u128>> = vec![None; width];

    for (index, &value) in puzzle.starting_values.iter().enumerate() {
        if index >= width {
            return Err(VerifyError::InvalidPuzzle(format!(
                "starting_values has {} entries but only {width} registers exist",
                puzzle.starting_values.len()
            )));
        }
        if value == 0 {
            return Err(VerifyError::InvalidPuzzle(format!(
                "starting_values[{index}] is zero"
            )));
        }
        if value > puzzle.value_limit {
            return Err(VerifyError::InvalidPuzzle(format!(
                "starting_values[{index}]={value} exceeds value_limit"
            )));
        }
        registers[index] = Some(value);
    }

    // Step 0 counts for coverage.
    let mut seen: HashSet<u128> = puzzle.starting_values.iter().copied().collect();
    let mut max_value_seen = puzzle
        .starting_values
        .iter()
        .copied()
        .max()
        .unwrap_or(0);

    for (index, instruction) in program.instructions.iter().enumerate() {
        for (field, register) in [
            ("d", instruction.d),
            ("i", instruction.i),
            ("j", instruction.j),
        ] {
            if register as usize >= width {
                return Err(VerifyError::RegisterOutOfRange {
                    index,
                    field,
                    value: register as u64,
                    max: config.max_registers,
                });
            }
        }

        let a = registers[instruction.i as usize].ok_or(VerifyError::UndefinedSource {
            index,
            field: "i",
            register: instruction.i,
        })?;
        let b = registers[instruction.j as usize].ok_or(VerifyError::UndefinedSource {
            index,
            field: "j",
            register: instruction.j,
        })?;

        let result = match instruction.op {
            Op::Add => a
                .checked_add(b)
                .ok_or(VerifyError::Overflow { index, op: "+" })?,
            Op::Sub => {
                if a <= b {
                    return Err(VerifyError::NegativeResult { index, a, b });
                }
                a - b
            }
            Op::Mul => a
                .checked_mul(b)
                .ok_or(VerifyError::Overflow { index, op: "*" })?,
            Op::Div => {
                if b == 0 {
                    return Err(VerifyError::DivisionByZero { index });
                }
                if a % b != 0 {
                    return Err(VerifyError::NonExactDivision { index, a, b });
                }
                a / b
            }
        };

        if result == 0 {
            return Err(VerifyError::NonPositiveIntermediate { index });
        }
        if result > puzzle.value_limit {
            return Err(VerifyError::ValueLimitExceeded {
                index,
                value: result,
                limit: puzzle.value_limit,
            });
        }

        // Write only after both sources have been read.
        registers[instruction.d as usize] = Some(result);
        seen.insert(result);
        max_value_seen = max_value_seen.max(result);
    }

    for &target in &puzzle.targets {
        if !seen.contains(&target) {
            return Err(VerifyError::UncoveredTarget { target });
        }
    }

    Ok(VerifyOutcome {
        steps: program.instructions.len(),
        targets_covered: puzzle.targets.len(),
        max_value_seen,
    })
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::model::{Instruction, Op, Program};

    fn puzzle() -> Puzzle {
        Puzzle {
            id: "p".to_string(),
            starting_values: vec![2, 3],
            targets: vec![5],
            value_limit: 1_000,
        }
    }

    fn program(instructions: Vec<Instruction>) -> Program {
        Program { instructions }
    }

    fn ins(op: Op, d: u8, i: u8, j: u8) -> Instruction {
        Instruction { op, d, i, j }
    }

    #[test]
    fn read_before_write_aliasing_is_valid() {
        // reg0 = 2 + 2 = 4, reg1 = 4 * 3 = 12; target 4 was covered at step 0.
        let p = Puzzle {
            targets: vec![4],
            ..puzzle()
        };
        let prog = program(vec![ins(Op::Add, 0, 0, 0), ins(Op::Mul, 1, 0, 1)]);
        let out = verify_program(&p, &prog, &VerifyConfig::default()).unwrap();
        assert_eq!(out.steps, 2);
    }

    #[test]
    fn step_zero_coverage_counts() {
        let p = Puzzle {
            targets: vec![2],
            ..puzzle()
        };
        let out = verify_program(&p, &program(vec![]), &VerifyConfig::default()).unwrap();
        assert_eq!(out.steps, 0);
    }

    #[test]
    fn subtraction_requires_strict_greater() {
        let p = puzzle();
        let prog = program(vec![ins(Op::Sub, 2, 0, 0)]);
        assert!(matches!(
            verify_program(&p, &prog, &VerifyConfig::default()),
            Err(VerifyError::NegativeResult { .. })
        ));
    }

    #[test]
    fn division_requires_exactness() {
        let p = puzzle();
        let prog = program(vec![ins(Op::Div, 2, 1, 0)]);
        assert!(matches!(
            verify_program(&p, &prog, &VerifyConfig::default()),
            Err(VerifyError::NonExactDivision { .. })
        ));
    }

    #[test]
    fn value_limit_applies_every_step() {
        let p = Puzzle {
            value_limit: 6,
            ..puzzle()
        };
        let prog = program(vec![ins(Op::Add, 2, 0, 1), ins(Op::Add, 3, 2, 2)]);
        assert!(matches!(
            verify_program(&p, &prog, &VerifyConfig::default()),
            Err(VerifyError::ValueLimitExceeded { index: 1, .. })
        ));
    }

    #[test]
    fn undefined_source_is_rejected() {
        let p = puzzle();
        let prog = program(vec![ins(Op::Add, 2, 5, 0)]);
        assert!(matches!(
            verify_program(&p, &prog, &VerifyConfig::default()),
            Err(VerifyError::UndefinedSource { .. })
        ));
    }

    #[test]
    fn compact_json_detection() {
        assert!(is_compact_json("[[\"+\",0,1,2]]"));
        assert!(!is_compact_json("[ [\"+\",0,1,2] ]"));
        assert!(is_compact_json("[[\"a b\",0,1,2]]"));
    }

    #[test]
    fn submission_checks_byte_cap_and_compactness() {
        let p = puzzle();
        let cfg = VerifyConfig {
            max_cell_bytes: 1,
            ..VerifyConfig::default()
        };
        assert!(matches!(
            verify_submission(&p, "[]", &cfg),
            Err(VerifyError::ProgramTooLarge { .. })
        ));

        let cfg = VerifyConfig::default();
        assert!(matches!(
            verify_submission(&p, "[ [\"+\",0,0,2] ]", &cfg),
            Err(VerifyError::NonCompactJson)
        ));
    }
}
