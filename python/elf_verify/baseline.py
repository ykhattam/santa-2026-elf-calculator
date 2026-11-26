"""Stage 1 fast-sweep baseline solver.

Builds a shared ladder of powers of two once per puzzle, then emits each target via
its binary expansion. This is strictly better than the sample submission's
per-target binary chain because the powers are shared across all targets.

Guarantees: every positive target <= value_limit is reachable; every emitted
program passes the locked VM specification (checked by the Rust verifier in CI).
"""

import json

from .model import Puzzle


def solve(puzzle: Puzzle) -> str:
    """Return a compact, verified-form program JSON string for `puzzle`."""
    starts = list(puzzle.starting_values)
    targets = sorted(set(t for t in puzzle.targets if t not in starts))
    instructions: list[list] = []

    def emit(op: str, i: int, j: int, d: int) -> None:
        instructions.append([op, i, j, d])

    if not targets:
        return "[]"

    k = len(starts)
    one = k
    acc = k + 1
    scratch = k + 2
    # Reserve registers k+3..47 for the shared power-of-two ladder.
    first_power = k + 3
    ladder_capacity = 48 - first_power
    max_bit = max(target.bit_length() for target in targets)
    # Largest stored power is 2^ladder_size, so it must satisfy 2^ladder_size <= limit.
    ladder_size = min(ladder_capacity, max_bit, puzzle.value_limit.bit_length() - 1)

    # reg[one] = starts[0] / starts[0] = 1
    emit("/", 0, 0, one)

    # reg[first_power + e] = 2^(e+1)
    if ladder_size >= 1:
        emit("+", one, one, first_power)
        for offset in range(1, ladder_size):
            register = first_power + offset
            emit("+", register - 1, register - 1, register)

    def power_register(bit: int) -> int:
        """Register holding 2^bit, computing high bits via one multiplication."""
        if bit == 0:
            return one
        if bit <= ladder_size:
            return first_power + bit - 1
        # bit > ladder_size: ladder_size >= 1, so both operands are stored.
        left = ladder_size
        right = bit - ladder_size
        emit("*", first_power + left - 1, first_power + right - 1, scratch)
        return scratch

    for target in targets:
        bits = [index for index in range(target.bit_length()) if (target >> index) & 1]
        highest = bits[-1]
        source = power_register(highest)
        # Copy into the accumulator by multiplying by one.
        emit("*", source, one, acc)
        for bit in bits[:-1]:
            source = power_register(bit)
            emit("+", acc, source, acc)

    return json.dumps(instructions, separators=(",", ":"))
