"""Stage 2 bounded-cone improvement solver.

For each target two constructions are compared:
  * binary expansion over a shared power-of-two ladder (the Stage 1 baseline);
  * subtractive construction `t = 2^k - d`, where `d` usually has a shorter
    binary expansion than `t`.

The cheaper one is emitted. Every emitted program is verified by the Rust
verifier before it reaches the ledger.
"""

import json

from .model import Puzzle


class Builder:
    def __init__(self, puzzle: Puzzle):
        self.puzzle = puzzle
        self.instructions: list[list] = []
        self.k = len(puzzle.starting_values)
        self.one = self.k
        self.acc = self.k + 1
        self.aux = self.k + 2
        self.scratch = self.k + 3
        self.first_power = self.k + 4
        capacity = 48 - self.first_power
        max_bit = max((t.bit_length() for t in puzzle.targets), default=0)
        self.ladder_size = min(
            capacity, max_bit, puzzle.value_limit.bit_length() - 1
        )

    def emit(self, op: str, i: int, j: int, d: int) -> None:
        self.instructions.append([op, i, j, d])

    def setup(self) -> None:
        self.emit("/", 0, 0, self.one)
        if self.ladder_size >= 1:
            self.emit("+", self.one, self.one, self.first_power)
            for offset in range(1, self.ladder_size):
                register = self.first_power + offset
                self.emit("+", register - 1, register - 1, register)

    def power_register(self, bit: int) -> int:
        if bit == 0:
            return self.one
        if bit <= self.ladder_size:
            return self.first_power + bit - 1
        left = self.ladder_size
        right = bit - self.ladder_size
        self.emit(
            "*",
            self.first_power + left - 1,
            self.first_power + right - 1,
            self.scratch,
        )
        return self.scratch

    def build_binary(self, value: int, dest: int) -> None:
        bits = [index for index in range(value.bit_length()) if (value >> index) & 1]
        if not bits:
            return
        source = self.power_register(bits[-1])
        self.emit("*", source, self.one, dest)
        for bit in bits[:-1]:
            source = self.power_register(bit)
            self.emit("+", dest, source, dest)

    def binary_cost(self, value: int) -> int:
        bits = [index for index in range(value.bit_length()) if (value >> index) & 1]
        high = sum(1 for bit in bits if bit > self.ladder_size)
        return max(1, len(bits)) + high

    def subtractive_cost(self, target: int) -> tuple[int, int] | None:
        """Return (cost, exponent) for the best `2^k - d` construction."""
        best = None
        for exponent in (
            target.bit_length(),
            target.bit_length() + 1,
            target.bit_length() + 2,
        ):
            ceiling = 1 << exponent
            if ceiling > self.puzzle.value_limit:
                continue
            difference = ceiling - target
            if difference <= 0 or difference > self.puzzle.value_limit:
                continue
            if difference == target:
                continue
            cost = 2 + self.binary_cost(difference)
            if exponent > self.ladder_size:
                cost += 1
            if best is None or cost < best[0]:
                best = (cost, exponent)
        return best

    def build_target(self, target: int, strategy: str = "auto") -> None:
        if strategy == "binary":
            self.build_binary(target, self.acc)
            return

        direct = self.binary_cost(target)
        alternative = self.subtractive_cost(target)
        if strategy == "subtractive":
            if alternative is not None:
                exponent = alternative[1]
                ceiling = 1 << exponent
                self.emit("*", self.power_register(exponent), self.one, self.aux)
                self.build_binary(ceiling - target, self.acc)
                self.emit("-", self.aux, self.acc, self.acc)
                return
            self.build_binary(target, self.acc)
            return

        if alternative is not None and alternative[0] < direct:
            exponent = alternative[1]
            ceiling = 1 << exponent
            if exponent <= self.ladder_size:
                self.emit("*", self.power_register(exponent), self.one, self.aux)
            else:
                source = self.power_register(exponent)
                self.emit("*", source, self.one, self.aux)
            self.build_binary(ceiling - target, self.acc)
            # aux holds 2^k > d, so the subtraction is strictly positive.
            self.emit("-", self.aux, self.acc, self.acc)
        else:
            self.build_binary(target, self.acc)


def solve(puzzle: Puzzle) -> str:
    """Return a compact program JSON string for `puzzle`."""
    starts = set(puzzle.starting_values)
    targets = sorted(set(t for t in puzzle.targets if t not in starts))
    if not targets:
        return "[]"
    builder = Builder(puzzle)
    builder.setup()
    for target in targets:
        builder.build_target(target)
    return json.dumps(builder.instructions, separators=(",", ":"))
