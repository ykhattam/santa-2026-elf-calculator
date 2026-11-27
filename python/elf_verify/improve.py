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


def naf_digits(value: int) -> list[int]:
    """Non-adjacent form: digits in {-1, 0, +1}, least significant first."""
    digits = []
    while value:
        if value & 1:
            digit = 2 - (value & 3)
            digits.append(digit)
            value -= digit
        else:
            digits.append(0)
        value >>= 1
    return digits


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

    def naf_positions(self, value: int) -> list[int]:
        digits = naf_digits(value)
        return [index for index, digit in enumerate(digits) if digit]

    def naf_available(self, value: int) -> bool:
        """NAF may carry one bit above the top; that power can exceed value_limit."""
        positions = self.naf_positions(value)
        return bool(positions) and (1 << positions[-1]) <= self.puzzle.value_limit

    def naf_cost(self, value: int) -> int:
        if not self.naf_available(value):
            return 10**9
        positions = self.naf_positions(value)
        high = sum(1 for position in positions if position > self.ladder_size)
        return max(1, len(positions)) + high

    def build_naf(self, value: int) -> None:
        digits = naf_digits(value)
        positions = [index for index, digit in enumerate(digits) if digit]
        if not positions:
            return
        highest = positions[-1]
        source = self.power_register(highest)
        self.emit("*", source, self.one, self.acc)
        # NAF partial sums stay positive, so subtraction is always legal.
        for position in positions[-2::-1]:
            source = self.power_register(position)
            if digits[position] == 1:
                self.emit("+", self.acc, source, self.acc)
            else:
                self.emit("-", self.acc, source, self.acc)

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
            cost = 2 + min(self.binary_cost(difference), self.naf_cost(difference))
            if exponent > self.ladder_size:
                cost += 1
            if best is None or cost < best[0]:
                best = (cost, exponent)
        return best

    def _build_subtractive(self, target: int, exponent: int) -> None:
        ceiling = 1 << exponent
        source = self.power_register(exponent)
        self.emit("*", source, self.one, self.aux)
        difference = ceiling - target
        if self.naf_available(difference) and self.naf_cost(difference) < self.binary_cost(difference):
            self.build_naf(difference)
        else:
            self.build_binary(difference, self.acc)
        # aux holds 2^k > d, so the subtraction is strictly positive.
        self.emit("-", self.aux, self.acc, self.acc)

    def build_target(self, target: int, strategy: str = "auto") -> None:
        if strategy == "binary":
            self.build_binary(target, self.acc)
            return
        if strategy == "naf":
            if self.naf_available(target):
                self.build_naf(target)
            else:
                self.build_binary(target, self.acc)
            return

        alternative = self.subtractive_cost(target)
        if strategy == "subtractive":
            if alternative is not None:
                self._build_subtractive(target, alternative[1])
            else:
                self.build_binary(target, self.acc)
            return

        # auto: pick the cheapest available construction.
        costs = [
            (self.binary_cost(target), "binary"),
            (self.naf_cost(target), "naf"),
        ]
        if alternative is not None:
            costs.append((alternative[0], "subtractive"))
        _, best = min(costs, key=lambda item: item[0])
        if best == "naf":
            self.build_naf(target)
        elif best == "subtractive":
            self._build_subtractive(target, alternative[1])
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
