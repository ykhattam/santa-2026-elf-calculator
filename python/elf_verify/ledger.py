"""Initialize and inspect the immutable provenance ledger."""

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
