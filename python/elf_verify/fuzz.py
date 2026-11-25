"""Deterministic grammar-based generator for the 50k differential fuzz corpus.

Every case is written as one JSON line so both verifiers can consume exactly the
same bytes. Categories target the edge cases called out in the Stage 0 plan:
aliasing, read-before-write, zero/negative results, division exactness, value-limit
overflow, duplicate targets, step-0 coverage, JSON whitespace, and UTF-8 byte caps.
"""

import json
import random
from collections import Counter
from pathlib import Path

_CATEGORIES = (
    ("valid_random", 28),
    ("alias", 12),
    ("negative", 10),
    ("nondiv", 8),
    ("limit_overflow", 8),
    ("step0", 8),
    ("undefined_source", 6),
    ("bad_register", 6),
    ("bad_op", 5),
    ("whitespace", 5),
    ("dup_target", 4),
)

_LARGE_CATEGORIES = ("too_many", "byte_cap")
_LARGE_LIMIT = 10


def compact(value) -> str:
    return json.dumps(value, separators=(",", ":"), ensure_ascii=False)


def _make_puzzle(rng: random.Random, limit: int | None = None) -> dict:
    if limit is None:
        limit = rng.choice((rng.randint(20, 200), rng.randint(1_000, 10**18), 10**18))
    count = rng.randint(2, 6)
    ceiling = max(2, limit // 10)
    start = [rng.randint(1, ceiling) for _ in range(count)]
    return {
        "id": "p",
        "starting_values": start,
        "targets": [rng.randint(1, limit)],
        "value_limit": limit,
    }


def _valid_program(rng: random.Random, start: list[int], limit: int):
    values: list[int | None] = [None] * 8
    for position, value in enumerate(start):
        values[position] = value
    defined = list(range(len(start)))
    instructions = []

    for _ in range(rng.randint(0, 10)):
        i = rng.choice(defined)
        j = rng.choice(defined)
        left, right = values[i], values[j]
        assert left is not None and right is not None

        candidates = []
        if left + right <= limit:
            candidates.append(("+", left + right))
        if left * right <= limit:
            candidates.append(("*", left * right))
        if left > right:
            candidates.append(("-", left - right))
        if right and left % right == 0:
            candidates.append(("/", left // right))
        if not candidates:
            break

        op, result = rng.choice(candidates)
        destination = rng.randrange(8)
        instructions.append({"op": op, "d": destination, "i": i, "j": j})
        values[destination] = result
        if destination not in defined:
            defined.append(destination)
            defined.sort()

    observed = set(start) | {value for value in values if value is not None}
    targets = [rng.choice(sorted(observed)) for _ in range(rng.randint(1, 3))]
    return instructions, targets


def _alias_program(rng: random.Random, start: list[int], limit: int):
    instructions, targets = _valid_program(rng, start, limit)
    for instruction in instructions:
        pattern = rng.randrange(3)
        if pattern == 0:
            instruction["d"] = instruction["i"]
        elif pattern == 1:
            instruction["d"] = instruction["j"]
        else:
            instruction["i"] = instruction["j"] = instruction["d"]
    return instructions, targets


def _generate_one(rng: random.Random, index: int, category: str) -> dict:
    if category == "byte_cap":
        puzzle = _make_puzzle(rng, 10**18)
        instruction = {"op": "+", "d": 0, "i": 0, "j": 0, "pad": "x" * 200}
        program = [dict(instruction) for _ in range(4096)]
    elif category == "too_many":
        puzzle = _make_puzzle(rng, 10**18)
        program = [{"op": "+", "d": 0, "i": 0, "j": 0} for _ in range(4097)]
    else:
        puzzle = _make_puzzle(rng)
        start = puzzle["starting_values"]
        limit = puzzle["value_limit"]

        if category in ("valid_random", "whitespace", "dup_target"):
            program, targets = _valid_program(rng, start, limit)
            if category == "dup_target" and targets:
                targets = [targets[0], targets[0]]
            puzzle["targets"] = targets
        elif category == "alias":
            program, targets = _alias_program(rng, start, limit)
            puzzle["targets"] = targets
        elif category == "step0":
            program, _ = _valid_program(rng, start, limit)
            puzzle["targets"] = [start[0]]
        elif category == "negative":
            program = [{"op": "-", "d": 0, "i": 0, "j": 0}]
        elif category == "nondiv":
            program = [{"op": "/", "d": 0, "i": 0, "j": 1}]
        elif category == "limit_overflow":
            puzzle = _make_puzzle(rng, 10)
            big = 10**18 - 1
            puzzle["starting_values"] = [big, big]
            program = [{"op": "*", "d": 0, "i": 0, "j": 1}]
        elif category == "undefined_source":
            program = [{"op": "+", "d": 0, "i": 47, "j": 0}]
        elif category == "bad_register":
            program = [{"op": "+", "d": 48, "i": 0, "j": 0}]
        elif category == "bad_op":
            program = [{"op": "%", "d": 0, "i": 0, "j": 1}]
        else:
            raise ValueError(f"unknown category: {category}")

    program_json = compact(program)
    if category == "whitespace":
        program_json = program_json.replace(",", ", ")

    return {
        "id": f"case-{index:06d}",
        "puzzle": puzzle,
        "program_json": program_json,
        "category": category,
    }


def _weighted_category(rng: random.Random) -> str:
    names = [name for name, _ in _CATEGORIES]
    weights = [weight for _, weight in _CATEGORIES]
    return rng.choices(names, weights=weights, k=1)[0]


def generate(count: int, seed: int, path: str) -> Counter:
    """Write `count` cases plus a fixed set of oversized cases to `path`."""
    rng = random.Random(seed)
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    tally: Counter = Counter()
    large_used: Counter = Counter()

    with destination.open("w", encoding="utf-8", newline="\n") as handle:
        for index in range(count):
            category = _weighted_category(rng)
            case = _generate_one(rng, index, category)
            handle.write(compact(case) + "\n")
            tally[category] += 1

        for offset, category in enumerate(_LARGE_CATEGORIES):
            for repeat in range(_LARGE_LIMIT):
                case = _generate_one(
                    rng,
                    count + offset * _LARGE_LIMIT + repeat,
                    category,
                )
                handle.write(compact(case) + "\n")
                large_used[category] += 1

    tally.update(large_used)
    return tally
