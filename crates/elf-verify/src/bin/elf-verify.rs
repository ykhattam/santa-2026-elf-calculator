//! CLI for the Santa 2026 verifier.
//!
//! Subcommands:
//!   check --puzzles <csv> --submission <csv> [--json]
//!   fuzz  --cases <ndjson> [--out <path>]

use std::collections::{HashMap, HashSet};
use std::fs::File;
use std::io::{self, BufRead, BufReader, BufWriter, Write};
use std::process::ExitCode;

use elf_verify::csv::{index_puzzles, load_puzzles, load_submission};
use elf_verify::fuzz::{decode_case, result_line, verify_case};
use elf_verify::model::VerifyConfig;

fn usage() -> ! {
    eprintln!(
        "usage:\n  elf-verify check --puzzles <csv> --submission <csv> [--json] [--allow-partial]\n  elf-verify fuzz --cases <ndjson> [--out <path>]"
    );
    std::process::exit(2);
}

fn flags(args: &[String]) -> HashMap<String, String> {
    let mut out = HashMap::new();
    let mut i = 0;
    while i < args.len() {
        let key = args[i].trim_start_matches('-').to_string();
        if key.is_empty() {
            i += 1;
            continue;
        }
        match args.get(i + 1) {
            Some(value) if !value.starts_with('-') => {
                out.insert(key, value.clone());
                i += 2;
            }
            _ => {
                out.insert(key, "true".to_string());
                i += 1;
            }
        }
    }
    out
}

fn json_escape(text: &str) -> String {
    serde_json::to_string(text).unwrap_or_else(|_| "\"\"".to_string())
}

fn check(args: &[String]) -> Result<bool, String> {
    let opts = flags(args);
    let puzzles_path = opts.get("puzzles").ok_or("check requires --puzzles")?;
    let submission_path = opts.get("submission").ok_or("check requires --submission")?;
    let as_json = opts.contains_key("json");
    let allow_partial = opts.contains_key("allow-partial");

    let puzzles = index_puzzles(load_puzzles(puzzles_path)?)?;
    let rows = load_submission(submission_path)?;
    let config = VerifyConfig::default();

    let mut total_steps: u64 = 0;
    let mut seen_ids: HashSet<String> = HashSet::new();
    let mut failures: Vec<String> = Vec::new();

    for (id, program_json) in &rows {
        if !seen_ids.insert(id.clone()) {
            failures.push(format!("duplicate submission id: {id}"));
            continue;
        }
        let puzzle = match puzzles.get(id) {
            Some(puzzle) => puzzle,
            None => {
                failures.push(format!("submission id {id} is not in puzzles.csv"));
                continue;
            }
        };
        match elf_verify::verify_submission(puzzle, program_json, &config) {
            Ok(outcome) => total_steps += outcome.steps as u64,
            Err(error) => failures.push(format!("{id}: {error}")),
        }
    }

    if !allow_partial {
        for id in puzzles.keys() {
            if !seen_ids.contains(id) {
                failures.push(format!("puzzle {id} has no submission row"));
            }
        }
    }

    let ok = failures.is_empty();
    if as_json {
        let rendered: Vec<String> = failures.iter().map(|f| json_escape(f)).collect();
        println!(
            "{{\"ok\":{},\"puzzles\":{},\"rows\":{},\"total_steps\":{},\"failures\":[{}]}}",
            ok,
            puzzles.len(),
            rows.len(),
            total_steps,
            rendered.join(",")
        );
    } else {
        println!("puzzles: {}", puzzles.len());
        println!("rows:    {}", rows.len());
        println!("steps:   {}", total_steps);
        if ok {
            println!("status:  OK");
        } else {
            println!("status:  FAILED ({} problems)", failures.len());
            for failure in failures.iter().take(20) {
                println!("  - {failure}");
            }
            if failures.len() > 20 {
                println!("  ... and {} more", failures.len() - 20);
            }
        }
    }
    Ok(ok)
}

fn fuzz(args: &[String]) -> Result<bool, String> {
    let opts = flags(args);
    let cases_path = opts.get("cases").ok_or("fuzz requires --cases")?;
    let config = VerifyConfig::default();

    let file = File::open(cases_path).map_err(|e| format!("cannot read {cases_path}: {e}"))?;
    let reader = BufReader::new(file);
    let mut writer: Box<dyn Write> = match opts.get("out") {
        Some(path) => Box::new(BufWriter::new(
            File::create(path).map_err(|e| format!("cannot create {path}: {e}"))?,
        )),
        None => Box::new(BufWriter::new(io::stdout().lock())),
    };

    let mut count = 0usize;
    let mut accepted = 0usize;
    for line in reader.lines() {
        let line = line.map_err(|e| format!("reading cases: {e}"))?;
        if line.trim().is_empty() {
            continue;
        }
        let value: serde_json::Value = serde_json::from_str(&line)
            .map_err(|e| format!("line {}: invalid JSON: {e}", count + 1))?;
        let rendered = match decode_case(&value) {
            Ok(case) => {
                let result = verify_case(&case, &config);
                if result.is_ok() {
                    accepted += 1;
                }
                result_line(&case, result)
            }
            Err(error) => format!(
                "{{\"id\":\"\",\"ok\":false,\"reason\":{}}}",
                json_escape(&format!("invalid fuzz case: {error}"))
            ),
        };
        writeln!(writer, "{rendered}").map_err(|e| format!("writing results: {e}"))?;
        count += 1;
    }
    writer.flush().map_err(|e| format!("flushing results: {e}"))?;
    eprintln!("fuzz cases: {count} (accepted {accepted}, rejected {})", count - accepted);
    Ok(true)
}

fn main() -> ExitCode {
    let mut args = std::env::args().skip(1);
    let command = match args.next() {
        Some(command) => command,
        None => usage(),
    };
    let rest: Vec<String> = args.collect();

    let result = match command.as_str() {
        "check" => check(&rest),
        "fuzz" => fuzz(&rest),
        "--version" | "-V" => {
            println!("elf-verify 0.1.0");
            Ok(true)
        }
        _ => {
            eprintln!("unknown command: {command}");
            usage();
        }
    };

    match result {
        Ok(true) => ExitCode::SUCCESS,
        Ok(false) => ExitCode::FAILURE,
        Err(error) => {
            eprintln!("error: {error}");
            ExitCode::FAILURE
        }
    }
}
