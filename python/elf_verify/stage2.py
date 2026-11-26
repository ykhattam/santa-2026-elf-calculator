"""Stage 2 orchestration helpers: ceilings, alerts, and allocation logging."""

import json
import sqlite3

CEILINGS = {15: 128_000, 25: 125_000, 35: 120_000, 40: 115_000}


def best_total(db_path: str) -> int:
    with sqlite3.connect(db_path) as connection:
        return connection.execute(
            "SELECT COALESCE(SUM(s), 0) FROM "
            "(SELECT MIN(steps) AS s FROM solutions GROUP BY puzzle_id)"
        ).fetchone()[0]


def check_ceiling(db_path: str, day: int) -> dict:
    target = CEILINGS.get(day)
    if target is None:
        return {"day": day, "status": "no ceiling defined"}
    current = best_total(db_path)
    passed = current < target
    result = {
        "day": day,
        "current_steps": current,
        "ceiling": target,
        "status": "pass" if passed else "miss",
    }
    with sqlite3.connect(db_path) as connection:
        connection.execute(
            "INSERT INTO telemetry(event, payload) VALUES('stage2_ceiling', ?)",
            (json.dumps(result, sort_keys=True),),
        )
        if not passed:
            connection.execute(
                "INSERT INTO alerts(kind, detail) VALUES('stage_ceiling_missed', ?)",
                (json.dumps(result, sort_keys=True),),
            )
    return result


def log_allocation(db_path: str, selected: list[str], solver_tag: str) -> None:
    with sqlite3.connect(db_path) as connection:
        connection.execute(
            "INSERT INTO telemetry(event, payload) VALUES('stage2_allocation', ?)",
            (json.dumps({"solver_tag": solver_tag, "puzzle_ids": selected}, sort_keys=True),),
        )
