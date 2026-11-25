"""Independent Python reference verifier for the Santa 2026 Elf Calculator.

This package is intentionally standalone from the Rust implementation: CI runs both
against the same fuzz corpus and fails on any semantic-validity divergence.
"""

from .verifier import VerifyError, is_compact_json, verify_case, verify_submission

__all__ = ["VerifyError", "is_compact_json", "verify_case", "verify_submission"]
