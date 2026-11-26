"""Initialize and inspect the immutable provenance ledger."""

import hashlib
import json
import sqlite3
from datetime import date, timedelta
from pathlib import Path

_DAY_ZERO = date(2026, 11, 26)

_STAGE_GATES = (
    ("stage_0_gate", 2),
    ("stage_1_gate", 4),
    ("stage_2_day_15_ceiling", 15),
    ("stage_2_day_25_ceiling", 25),
    ("stage_2_day_35_ceiling", 35),
    ("stage_2_exit_gate", 40),
    ("stage_3_exit_gate", 52),
    ("final_submission_lock", 61),
)


def _flatten(value, prefix=""):
    if isinstance(value, dict):
        for key, item in value.items():
            yield from _flatten(item, f"{prefix}.{key}" if prefix else key)
    else:
        yield prefix, value


def init_db(db_path: str, config_path: str, schema_path: str) -> int:
    facts = json.loads(Path(config_path).read_text(encoding="utf-8"))
    schema = Path(schema_path).read_text(encoding="utf-8")

    connection = sqlite3.connect(db_path)
    try:
        connection.executescript(schema)
        for key, value in _flatten(facts):
            connection.execute(
                "INSERT INTO meta(key, value, updated_at) VALUES(?, ?, datetime('now')) "
                "ON CONFLICT(key) DO UPDATE SET value=excluded.value, "
                "updated_at=excluded.updated_at",
                (key, json.dumps(value) if not isinstance(value, str) else value),
            )
        for name, day in _STAGE_GATES:
            target = _DAY_ZERO + timedelta(days=day - 1)
            connection.execute(
                "INSERT INTO stage_gates(name, target_date, status) "
                "VALUES(?, ?, 'pending') ON CONFLICT(name) DO NOTHING",
                (name, target.isoformat()),
            )
        connection.commit()
        return connection.execute("SELECT COUNT(*) FROM meta").fetchone()[0]
    finally:
        connection.close()


def record_fuzz_run(db_path: str, case_count: int, divergences: int, report_path: str) -> None:
    with sqlite3.connect(db_path) as connection:
        connection.execute(
            "INSERT INTO fuzz_runs(case_count, divergences, report_path) VALUES(?, ?, ?)",
            (case_count, divergences, report_path),
        )


def record_parity(
    db_path: str,
    submission_ref: str,
    local_steps: int,
    kaggle_score: int,
    submission_path: str,
) -> None:
    """Record the Stage 0 live-scorer parity result as immutable metadata."""
    matched = str(local_steps == kaggle_score).lower()
    facts = {
        "parity.submission_ref": submission_ref,
        "parity.submission_file": submission_path,
        "parity.local_steps": str(local_steps),
        "parity.kaggle_score": str(kaggle_score),
        "parity.exact_match": matched,
    }
    with sqlite3.connect(db_path) as connection:
        for key, value in facts.items():
            connection.execute(
                "INSERT INTO meta(key, value, updated_at) VALUES(?, ?, datetime('now')) "
                "ON CONFLICT(key) DO UPDATE SET value=excluded.value, "
                "updated_at=excluded.updated_at",
                (key, value),
            )
        connection.execute(
            "INSERT INTO telemetry(event, payload) VALUES('stage0_parity', ?)",
            (json.dumps(facts, sort_keys=True),),
        )


def seed_solutions(db_path: str, rows, tag: str, note: str = "") -> int:
    """Insert verified solutions, keeping only strict improvements per puzzle."""
    written = 0
    with sqlite3.connect(db_path) as connection:
        for puzzle_id, program_json in rows:
            steps = len(json.loads(program_json))
            digest = hashlib.sha256(program_json.encode("utf-8")).hexdigest()
            best = connection.execute(
                "SELECT MIN(steps) FROM solutions WHERE puzzle_id = ?", (puzzle_id,)
            ).fetchone()[0]
            if best is not None and best <= steps:
                continue
            connection.execute(
                "INSERT INTO solutions(puzzle_id, steps, solver_tag, program_json, sha256, note) "
                "VALUES(?, ?, ?, ?, ?, ?)",
                (puzzle_id, steps, tag, program_json, digest, note),
            )
            written += 1
        connection.commit()
    return written


def seed_puzzles(db_path: str, puzzles, families: dict[str, str]) -> int:
    """Seed the puzzle table; no solution rows are written here."""
    with sqlite3.connect(db_path) as connection:
        for puzzle in puzzles:
            connection.execute(
                "INSERT INTO puzzles(id, starting_values, targets, value_limit, pseudo_family) "
                "VALUES(?, ?, ?, ?, ?) ON CONFLICT(id) DO UPDATE SET "
                "pseudo_family=excluded.pseudo_family",
                (
                    puzzle.id,
                    json.dumps(list(puzzle.starting_values), separators=(",", ":")),
                    json.dumps(list(puzzle.targets), separators=(",", ":")),
                    str(puzzle.value_limit),
                    families.get(puzzle.id),
                ),
            )
        connection.commit()
        return connection.execute("SELECT COUNT(*) FROM puzzles").fetchone()[0]
