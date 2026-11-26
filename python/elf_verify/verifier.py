"""Independent Python reference implementation of the Elf Calculator VM.

This is a clean-room implementation used only by CI/nightly differential testing.
It must agree with crates/elf-verify on accept/reject and step count for every case
in the fuzz corpus. Implementation style is intentionally different from the Rust
version (dictionary registers, explicit validators) so shared bugs are unlikely.
"""

import json

from .model import (
    DEFAULT_CONFIG,
    MAX_JSON_INTEGER,
    Puzzle,
    VerifyConfig,
    VerifyError,
    VerifyOutcome,
)

_OPERATORS = frozenset(("+", "-", "*", "/"))


def is_compact_json(text: str) -> bool:
    """True if no whitespace occurs outside JSON string literals."""
    quoted = False
    backslash = False
    for character in text:
        if quoted:
            if backslash:
                backslash = False
            elif character == "\\":
                backslash = True
            elif character == '"':
                quoted = False
            continue
        if character == '"':
            quoted = True
        elif character in " \t\n\r":
            return False
    return True


def _reject_constant(_value: str):
    raise ValueError("non-finite JSON numbers are not permitted")


def _parse_program(text: str, config: VerifyConfig):
    try:
        document = json.loads(text, parse_constant=_reject_constant)
    except (ValueError, TypeError) as exc:
        raise VerifyError(f"malformed program: {exc}") from exc

    if not isinstance(document, list):
        raise VerifyError("malformed program: top-level JSON value must be an array")
    if len(document) > config.max_instructions:
        raise VerifyError(
            f"{len(document)} instructions exceeds cap {config.max_instructions}"
        )

    instructions = []
    for position, item in enumerate(document):
        # Real format is positional: [op, i, j, d] (sources first, destination last).
        if not isinstance(item, list) or len(item) != 4:
            raise VerifyError(f"instruction {position}: expected a 4-element JSON array")

        op = item[0]
        if not isinstance(op, str) or op not in _OPERATORS:
            raise VerifyError(f"instruction {position}: unknown op {op!r}")

        operands = []
        for label, value in zip(("i", "j", "d"), item[1:]):
            if isinstance(value, bool) or not isinstance(value, int):
                raise VerifyError(f"instruction {position}: {label} must be an integer")
            if value < 0 or value >= config.max_registers:
                raise VerifyError(
                    f"instruction {position}: {label}={value} outside 0..{config.max_registers}"
                )
            operands.append(value)

        source_i, source_j, destination = operands
        instructions.append((op, destination, source_i, source_j))
    return instructions


def _check_puzzle(puzzle: Puzzle, config: VerifyConfig) -> None:
    if not puzzle.starting_values:
        raise VerifyError("invalid puzzle: starting_values must not be empty")
    if puzzle.value_limit <= 0:
        raise VerifyError("invalid puzzle: value_limit must be positive")
    if len(puzzle.starting_values) > config.max_registers:
        raise VerifyError("invalid puzzle: too many starting values")
    for position, value in enumerate(puzzle.starting_values):
        if value <= 0:
            raise VerifyError(f"invalid puzzle: starting_values[{position}] is not positive")
        if value > puzzle.value_limit:
            raise VerifyError(f"invalid puzzle: starting_values[{position}] exceeds value_limit")


def verify_program(
    puzzle: Puzzle,
    instructions,
    config: VerifyConfig = DEFAULT_CONFIG,
) -> VerifyOutcome:
    """Replay a decoded program against a puzzle."""
    _check_puzzle(puzzle, config)

    registers: dict[int, int] = {}
    for position, value in enumerate(puzzle.starting_values):
        registers[position] = value

    observed = set(registers.values())
    highest = max(observed)

    for position, (op, destination, source_i, source_j) in enumerate(instructions):
        # Both operands are captured before the destination is rewritten.
        left = registers.get(source_i)
        right = registers.get(source_j)
        if left is None:
            raise VerifyError(f"instruction {position}: source i register {source_i} is undefined")
        if right is None:
            raise VerifyError(f"instruction {position}: source j register {source_j} is undefined")

        if op == "+":
            result = left + right
        elif op == "-":
            if left <= right:
                raise VerifyError(f"instruction {position}: subtraction is not positive")
            result = left - right
        elif op == "*":
            result = left * right
        else:
            if right == 0:
                raise VerifyError(f"instruction {position}: division by zero")
            if left % right != 0:
                raise VerifyError(f"instruction {position}: division is not exact")
            result = left // right

        if result <= 0:
            raise VerifyError(f"instruction {position}: non-positive intermediate value")
        if result > puzzle.value_limit:
            raise VerifyError(
                f"instruction {position}: value {result} exceeds limit {puzzle.value_limit}"
            )

        registers[destination] = result
        observed.add(result)
        highest = max(highest, result)

    for target in puzzle.targets:
        if target not in observed:
            raise VerifyError(f"target {target} was never covered")

    return VerifyOutcome(
        steps=len(instructions),
        targets_covered=len(puzzle.targets),
        max_value_seen=highest,
    )


def verify_submission(
    puzzle: Puzzle,
    program_json: str,
    config: VerifyConfig = DEFAULT_CONFIG,
) -> VerifyOutcome:
    """Validate serialized form, decode, then replay."""
    byte_length = len(program_json.encode("utf-8"))
    if byte_length > config.max_cell_bytes:
        raise VerifyError(f"program is {byte_length} bytes, cap is {config.max_cell_bytes}")
    if config.strict_compact_json and not is_compact_json(program_json):
        raise VerifyError("program JSON contains insignificant whitespace")

    instructions = _parse_program(program_json, config)
    return verify_program(puzzle, instructions, config)


def _uint(value) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise VerifyError("expected a non-negative integer")
    if value < 0 or value > MAX_JSON_INTEGER:
        raise VerifyError("integer out of range")
    return value


def _uint_array(value, label: str) -> tuple[int, ...]:
    if not isinstance(value, list):
        raise VerifyError(f"{label} must be an array")
    return tuple(_uint(item) for item in value)


def verify_case(case: dict, config: VerifyConfig = DEFAULT_CONFIG) -> dict:
    """Verify one NDJSON fuzz case and return the comparison-friendly result."""
    case_id = str(case.get("id", "")) if isinstance(case, dict) else ""
    try:
        if not isinstance(case, dict):
            raise VerifyError("case must be an object")
        raw_puzzle = case.get("puzzle")
        if not isinstance(raw_puzzle, dict):
            raise VerifyError("missing puzzle")
        puzzle = Puzzle(
            id=str(raw_puzzle.get("id", case_id)),
            starting_values=_uint_array(raw_puzzle.get("starting_values"), "starting_values"),
            targets=_uint_array(raw_puzzle.get("targets"), "targets"),
            value_limit=_uint(raw_puzzle.get("value_limit")),
        )
        program_json = case.get("program_json")
        if not isinstance(program_json, str):
            raise VerifyError("missing program_json")
        outcome = verify_submission(puzzle, program_json, config)
        return {"id": case_id, "ok": True, "steps": outcome.steps}
    except (VerifyError, KeyError, TypeError, ValueError) as exc:
        return {"id": case_id, "ok": False, "reason": str(exc)}
