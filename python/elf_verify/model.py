"""Data model for the Python reference verifier."""

from dataclasses import dataclass

MAX_REGISTERS = 48
MAX_INSTRUCTIONS = 4096
MAX_CELL_BYTES = 131072
MAX_JSON_INTEGER = 2**64 - 1  # mirrors serde_json's u64-backed integers in Rust


@dataclass(frozen=True)
class Puzzle:
    id: str
    starting_values: tuple[int, ...]
    targets: tuple[int, ...]
    value_limit: int


@dataclass(frozen=True)
class VerifyConfig:
    max_instructions: int = MAX_INSTRUCTIONS
    max_registers: int = MAX_REGISTERS
    max_cell_bytes: int = MAX_CELL_BYTES
    strict_compact_json: bool = True


@dataclass(frozen=True)
class VerifyOutcome:
    steps: int
    targets_covered: int
    max_value_seen: int


class VerifyError(Exception):
    """Raised when a program or puzzle violates the locked VM specification."""


DEFAULT_CONFIG = VerifyConfig()
