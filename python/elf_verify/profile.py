"""Stage 1 lower bounds, absolute-regret ranking, and empirical yield priors."""

import csv
import json
import sqlite3
import time
from pathlib import Path

from .baseline import solve


def lower_bound(puzzle) -> int:
    """Lower bound on instructions needed to cover all targets.

    Two independent bounds are combined by taking the maximum:
      1. every distinct target absent at step 0 needs its own instruction;
      2. reaching the largest target from the largest starting value needs at
         least ceil(log2(target / max_start)) doublings.
    """
    starts = set(puzzle.starting_values)
    missing = sorted(set(puzzle.targets) - starts)
    if not missing:
        return 0
    ceiling = max(puzzle.starting_values)
    hardest = 0
    for target in missing:
        steps = 0
        value = ceiling
        while value < target:
            value *= 2
            steps += 1
        hardest = max(hardest, max(1, steps))
    return max(len(missing), hardest)


def profile(db_path: str, puzzles, out_csv: str) -> dict:
    """Write puzzle LBs/regret to the ledger and publish the ranking."""
    with sqlite3.connect(db_path) as connection:
        best_steps = {
            puzzle_id: steps
            for puzzle_id, steps in connection.execute(
                "SELECT puzzle_id, MIN(steps) FROM solutions GROUP BY puzzle_id"
            )
        }
        families = dict(
            connection.execute("SELECT id, COALESCE(pseudo_family, 'unknown') FROM puzzles")
        )

        records = []
        for puzzle in puzzles:
            lb = lower_bound(puzzle)
            steps = best_steps.get(puzzle.id)
            regret = None if steps is None else steps - lb
            family = families.get(puzzle.id, "unknown")
            connection.execute(
                "UPDATE puzzles SET lower_bound = ?, profile_steps = ?, regret = ?, "
                "profiled_at = datetime('now') WHERE id = ?",
                (lb, steps, regret, puzzle.id),
            )
            records.append((puzzle.id, family, lb, steps, regret))

        connection.commit()

    destination = Path(out_csv)
    destination.parent.mkdir(parents=True, exist_ok=True)
    with destination.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(["id", "pseudo_family", "lower_bound", "steps", "regret"])
        for record in sorted(records, key=lambda row: -(row[4] or 0)):
            writer.writerow(record)

    total_steps = sum(row[3] or 0 for row in records)
    total_lb = sum(row[2] for row in records)
    return {
        "puzzles": len(records),
        "total_steps": total_steps,
        "total_lower_bound": total_lb,
        "total_regret": total_steps - total_lb,
        "ranking_path": str(destination),
    }


def yield_baseline(db_path: str, puzzles, out_csv: str) -> dict:
    """Measure step improvement per CPU-second, stratified by pseudo-family."""
    with sqlite3.connect(db_path) as connection:
        reference = {
            puzzle_id: steps
            for puzzle_id, steps in connection.execute(
                "SELECT puzzle_id, steps FROM solutions WHERE solver_tag = 'sample_greedy'"
            )
        }
        families = dict(
            connection.execute("SELECT id, COALESCE(pseudo_family, 'unknown') FROM puzzles")
        )

    stats: dict[str, dict[str, float]] = {}
    for puzzle in puzzles:
        started = time.perf_counter()
        program = solve(puzzle)
        elapsed = time.perf_counter() - started
        improved = reference.get(puzzle.id, 0) - len(json.loads(program))
        family = families.get(puzzle.id, "unknown")
        row = stats.setdefault(family, {"puzzles": 0, "improvement": 0, "seconds": 0.0})
        row["puzzles"] += 1
        row["improvement"] += max(0, improved)
        row["seconds"] += elapsed

    destination = Path(out_csv)
    destination.parent.mkdir(parents=True, exist_ok=True)
    with destination.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(
            ["pseudo_family", "puzzles", "improvement", "cpu_seconds", "improvement_per_second"]
        )
        for family, row in sorted(stats.items()):
            rate = row["improvement"] / row["seconds"] if row["seconds"] else 0.0
            writer.writerow(
                [
                    family,
                    row["puzzles"],
                    row["improvement"],
                    f"{row['seconds']:.3f}",
                    f"{rate:.0f}",
                ]
            )
    return {"families": len(stats), "ranking_path": str(destination)}
