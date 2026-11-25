//! Minimal RFC4180 CSV reader plus the two competition-specific loaders.
//!
//! Deliberately dependency-free so the verifier can be built offline.

use std::collections::HashMap;
use std::fs;

use crate::model::Puzzle;

/// Parse CSV text, honoring quoted fields, doubled quotes, and embedded newlines.
pub fn parse_csv(input: &str) -> Result<Vec<Vec<String>>, String> {
    let chars: Vec<char> = input.chars().collect();
    let mut records = Vec::new();
    let mut record: Vec<String> = Vec::new();
    let mut field = String::new();
    let mut in_quotes = false;
    let mut i = 0;

    while i < chars.len() {
        let ch = chars[i];

        if in_quotes {
            if ch == '"' {
                if i + 1 < chars.len() && chars[i + 1] == '"' {
                    field.push('"');
                    i += 2;
                    continue;
                }
                in_quotes = false;
                i += 1;
                continue;
            }
            field.push(ch);
            i += 1;
            continue;
        }

        match ch {
            '"' => {
                in_quotes = true;
                i += 1;
            }
            ',' => {
                record.push(std::mem::take(&mut field));
                i += 1;
            }
            '\r' | '\n' => {
                record.push(std::mem::take(&mut field));
                records.push(std::mem::take(&mut record));
                if ch == '\r' && i + 1 < chars.len() && chars[i + 1] == '\n' {
                    i += 1;
                }
                i += 1;
            }
            _ => {
                field.push(ch);
                i += 1;
            }
        }
    }

    if in_quotes {
        return Err("unterminated quoted field".to_string());
    }
    if !field.is_empty() || !record.is_empty() {
        record.push(field);
        records.push(record);
    }

    Ok(records)
}

fn find_column(header: &[String], exact: &[&str], contains: &[&str]) -> Option<usize> {
    for wanted in exact {
        if let Some(index) = header.iter().position(|h| h.trim().eq_ignore_ascii_case(wanted)) {
            return Some(index);
        }
    }
    for needle in contains {
        if let Some(index) = header
            .iter()
            .position(|h| h.trim().to_ascii_lowercase().contains(needle))
        {
            return Some(index);
        }
    }
    None
}

/// Extract every unsigned integer token from a cell. This tolerates `[1,2,3]`,
/// `1;2;3`, `1 2 3`, and other separators used by the competition data.
pub fn parse_number_list(cell: &str) -> Vec<u128> {
    let mut values = Vec::new();
    let mut current: Option<u128> = None;

    for ch in cell.chars() {
        if let Some(digit) = ch.to_digit(10) {
            let value = current.unwrap_or(0);
            current = Some(value.saturating_mul(10).saturating_add(digit as u128));
        } else if let Some(value) = current.take() {
            values.push(value);
        }
    }
    if let Some(value) = current.take() {
        values.push(value);
    }
    values
}

fn cell<'a>(row: &'a [String], index: usize, column: &str) -> Result<&'a str, String> {
    row.get(index)
        .map(|s| s.as_str())
        .ok_or_else(|| format!("row is missing column {column}"))
}

pub fn load_puzzles(path: &str) -> Result<Vec<Puzzle>, String> {
    let text = fs::read_to_string(path).map_err(|e| format!("cannot read {path}: {e}"))?;
    let records = parse_csv(&text)?;
    let header = records.first().ok_or("puzzles.csv is empty")?;

    let id_col = find_column(header, &["id", "puzzle_id"], &["id"])
        .ok_or("puzzles.csv has no id column")?;
    let start_col = find_column(header, &["starting_values"], &["starting", "initial"])
        .ok_or("puzzles.csv has no starting_values column")?;
    let target_col = find_column(header, &["targets"], &["target"])
        .ok_or("puzzles.csv has no targets column")?;
    let limit_col = find_column(header, &["value_limit"], &["limit"])
        .ok_or("puzzles.csv has no value_limit column")?;

    let mut puzzles = Vec::new();
    for (line, row) in records.iter().enumerate().skip(1) {
        if row.len() == 1 && row[0].trim().is_empty() {
            continue;
        }
        let id = cell(row, id_col, "id")?.trim().to_string();
        if id.is_empty() {
            return Err(format!("puzzles.csv line {}: empty id", line + 1));
        }
        let starting_values = parse_number_list(cell(row, start_col, "starting_values")?);
        let targets = parse_number_list(cell(row, target_col, "targets")?);
        let limits = parse_number_list(cell(row, limit_col, "value_limit")?);
        let value_limit = limits
            .first()
            .copied()
            .ok_or_else(|| format!("puzzles.csv line {}: empty value_limit", line + 1))?;

        puzzles.push(Puzzle {
            id,
            starting_values,
            targets,
            value_limit,
        });
    }
    Ok(puzzles)
}

/// Return `(puzzle_id, program_json)` pairs in submission row order.
pub fn load_submission(path: &str) -> Result<Vec<(String, String)>, String> {
    let text = fs::read_to_string(path).map_err(|e| format!("cannot read {path}: {e}"))?;
    let records = parse_csv(&text)?;
    let header = records.first().ok_or("submission.csv is empty")?;

    let id_col = find_column(header, &["id", "puzzle_id"], &["id"])
        .ok_or("submission.csv has no id column")?;
    let program_col = find_column(header, &["program", "answer", "solution"], &[
        "program", "answer", "solution", "submission",
    ])
    .ok_or("submission.csv has no program column")?;

    let mut rows = Vec::new();
    for (line, row) in records.iter().enumerate().skip(1) {
        if row.len() == 1 && row[0].trim().is_empty() {
            continue;
        }
        let id = cell(row, id_col, "id")?.trim().to_string();
        let program = cell(row, program_col, "program")?.to_string();
        if id.is_empty() {
            return Err(format!("submission.csv line {}: empty id", line + 1));
        }
        rows.push((id, program));
    }
    Ok(rows)
}

pub fn index_puzzles(puzzles: Vec<Puzzle>) -> Result<HashMap<String, Puzzle>, String> {
    let mut map = HashMap::with_capacity(puzzles.len());
    for puzzle in puzzles {
        let id = puzzle.id.clone();
        if map.insert(id.clone(), puzzle).is_some() {
            return Err(format!("duplicate puzzle id in puzzles.csv: {id}"));
        }
    }
    Ok(map)
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn csv_handles_quotes_and_embedded_newlines() {
        let text = "id,program\n1,\"a,b\n\"\"c\"\"\"\n";
        let rows = parse_csv(text).unwrap();
        assert_eq!(rows.len(), 2);
        assert_eq!(rows[1][1], "a,b\n\"c\"");
    }

    #[test]
    fn number_list_is_separator_agnostic() {
        assert_eq!(parse_number_list("[1,2,3]"), vec![1, 2, 3]);
        assert_eq!(parse_number_list("1;2 3"), vec![1, 2, 3]);
    }
}
