"""Local LNS worker for the Stage 2 go/no-go validation.

Neighborhood: one target's construction strategy is destroyed and rebuilt from
{auto, binary, subtractive} over the incumbent builder. The whole program is
re-emitted and verified before an improvement is accepted.

This is a deliberately small, falsifiable neighborhood — not the final engine.
"""

import json
import random
import time

from .improve import Builder
from .model import Puzzle, VerifyError
from .verifier import verify_submission

STRATEGIES = ("auto", "binary", "subtractive")


def targets_of(puzzle: Puzzle) -> list[int]:
    return sorted(set(puzzle.targets) - set(puzzle.starting_values))


def build_program(puzzle: Puzzle, strategies: dict[int, str]) -> str:
    builder = Builder(puzzle)
    builder.setup()
    for target in targets_of(puzzle):
        builder.build_target(target, strategies.get(target, "auto"))
    return json.dumps(builder.instructions, separators=(",", ":"))


def initial_strategies(puzzle: Puzzle) -> dict[int, str]:
    return {target: "auto" for target in targets_of(puzzle)}


def improve(
    puzzle: Puzzle,
    seed: int,
    budget_seconds: float,
    starting_program: str | None = None,
) -> dict:
    """Randomized LNS loop with Python verification on every candidate."""
    rng = random.Random(seed)
    targets = targets_of(puzzle)
    if not targets:
        return {"initial_steps": 0, "final_steps": 0, "iterations": 0, "program": "[]"}

    strategies = initial_strategies(puzzle)
    best = starting_program or build_program(puzzle, strategies)
    try:
        verify_submission(puzzle, best)
    except VerifyError as exc:
        raise RuntimeError(f"initial program is invalid: {exc}") from exc
    initial_steps = len(json.loads(best))
    best_steps = initial_steps

    started = time.perf_counter()
    iterations = 0
    while time.perf_counter() - started < budget_seconds:
        iterations += 1
        target = rng.choice(targets)
        previous = strategies[target]
        candidate_strategy = rng.choice(STRATEGIES)
        if candidate_strategy == previous:
            continue
        strategies[target] = candidate_strategy
        candidate = build_program(puzzle, strategies)
        try:
            verify_submission(puzzle, candidate)
        except VerifyError:
            strategies[target] = previous
            continue
        steps = len(json.loads(candidate))
        if steps < best_steps:
            best, best_steps = candidate, steps
        else:
            strategies[target] = previous

    return {
        "initial_steps": initial_steps,
        "final_steps": best_steps,
        "iterations": iterations,
        "program": best,
    }
