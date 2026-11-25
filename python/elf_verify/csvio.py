"""Tolerant CSV loaders for competition data (Python side of `csv.rs`)."""

import csv
import re
from pathlib import Path

from .model import Puzzle

_INTEGER = re.compile(r"\d+")


def parse_number_list(cell: str) -> tuple[int, ...]:
    return tuple(int(token) for token in _INTEGER.findall(cell))


def _find_column(header: list[str], exact: tuple[str, ...], contains: tuple[str, ...]) -> int:
    lowered = [column.strip().lower() for column in header]
    for wanted in exact:
        if wanted in lowered:
            return lowered.index(wanted)
    for needle in contains:
        for index, column in enumerate(lowered):
            if needle in column:
                return index
    raise ValueError(f"no column matching {exact} or {contains} in {header}")


def load_puzzles(path: str) -> list[Puzzle]:
    with Path(path).open("r", encoding="utf-8", newline="") as handle:
        reader = csv.reader(handle)
        rows = list(reader)
    header = rows[0]
    id_col = _find_column(header, ("id", "puzzle_id"), ("id",))
    start_col = _find_column(header, ("starting_values",), ("starting", "initial"))
    target_col = _find_column(header, ("targets",), ("target",))
    limit_col = _find_column(header, ("value_limit",), ("limit",))

    puzzles = []
    for line, row in enumerate(rows[1:], start=2):
        if len(row) == 1 and not row[0].strip():
            continue
        limits = parse_number_list(row[limit_col])
        if not limits:
            raise ValueError(f"{path}:{line}: empty value_limit")
        puzzles.append(
            Puzzle(
                id=row[id_col].strip(),
                starting_values=parse_number_list(row[start_col]),
                targets=parse_number_list(row[target_col]),
                value_limit=limits[0],
            )
        )
    return puzzles


def load_submission(path: str) -> list[tuple[str, str]]:
    with Path(path).open("r", encoding="utf-8", newline="") as handle:
        reader = csv.reader(handle)
        rows = list(reader)
    header = rows[0]
    id_col = _find_column(header, ("id", "puzzle_id"), ("id",))
    program_col = _find_column(
        header,
        ("program", "answer", "solution"),
        ("program", "answer", "solution", "submission"),
    )
    output = []
    for line, row in enumerate(rows[1:], start=2):
        if len(row) == 1 and not row[0].strip():
            continue
        output.append((row[id_col].strip(), row[program_col]))
    return output
