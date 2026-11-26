"""Independent unit tests for the Python reference verifier."""

import json

import pytest

from elf_verify.model import Puzzle, VerifyError, VerifyConfig, VerifyOutcome
from elf_verify.verifier import is_compact_json, verify_program, verify_submission

BASE = Puzzle(
    id="p",
    starting_values=(2, 3),
    targets=(5,),
    value_limit=1_000,
)


def instructions(values):
    return [tuple(item) for item in values]


def test_step_zero_coverage():
    puzzle = Puzzle(id="p", starting_values=(2, 3), targets=(3,), value_limit=100)
    assert verify_program(puzzle, []) == VerifyOutcome(
        steps=0, targets_covered=1, max_value_seen=3
    )


def test_intermediate_coverage():
    # reg2 = 5 (target), then overwritten; coverage must still count.
    program = instructions([("+", 2, 0, 1), ("*", 2, 2, 2)])
    assert verify_program(BASE, program).steps == 2


def test_read_before_write_aliasing():
    puzzle = Puzzle(id="p", starting_values=(3, 4), targets=(9,), value_limit=100)
    program = instructions([("*", 0, 0, 0), ("*", 1, 0, 1)])
    assert verify_program(puzzle, program).steps == 2


def test_strict_subtraction():
    with pytest.raises(VerifyError):
        verify_program(BASE, instructions([("-", 2, 0, 0)]))


def test_exact_division():
    with pytest.raises(VerifyError):
        verify_program(BASE, instructions([("/", 2, 0, 1)]))
    assert verify_program(
        Puzzle(id="p", starting_values=(6, 3), targets=(2,), value_limit=100),
        instructions([("/", 2, 0, 1)]),
    ).steps == 1


def test_limit_on_every_step():
    puzzle = Puzzle(id="p", starting_values=(2, 3), targets=(8,), value_limit=6)
    with pytest.raises(VerifyError):
        verify_program(puzzle, instructions([("+", 2, 0, 1), ("+", 3, 2, 2)]))


def test_undefined_source():
    with pytest.raises(VerifyError):
        verify_program(BASE, instructions([("+", 2, 9, 0)]))


def test_compact_json():
    assert is_compact_json('[["+",0,1,2]]')
    assert not is_compact_json('[ ["+",0,1,2] ]')
    assert is_compact_json('[["a b",0,1,2]]')


def test_submission_byte_and_format_checks():
    with pytest.raises(VerifyError):
        verify_submission(BASE, "[]", VerifyConfig(max_cell_bytes=1))
    with pytest.raises(VerifyError):
        verify_submission(BASE, "[ [\"+\",0,0,2] ]", VerifyConfig(strict_compact_json=True))
    with pytest.raises(VerifyError):
        verify_submission(BASE, "{}")


def test_instruction_cap():
    program = [["+", 0, 0, 0]] * 4097
    with pytest.raises(VerifyError):
        verify_submission(
            Puzzle(id="p", starting_values=(1,), targets=(1,), value_limit=10**18),
            json.dumps(program, separators=(",", ":")),
        )


def test_float_register_is_rejected():
    program = '[["+",0.0,0,0]]'
    with pytest.raises(VerifyError):
        verify_submission(BASE, program)
