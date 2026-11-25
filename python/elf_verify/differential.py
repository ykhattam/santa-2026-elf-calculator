"""Compare the Rust and Python verifiers on an identical fuzz corpus.

Only semantic-validity disagreements (accept/reject and step count) count as
divergences. Difference in error wording is tolerated by design.
"""

import json
import subprocess
from pathlib import Path

from .verifier import verify_case


def python_results(cases_path: str) -> list[dict]:
    results = []
    with Path(cases_path).open("r", encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                results.append(verify_case(json.loads(line)))
    return results


def rust_results(cases_path: str, rust_bin: str) -> list[dict]:
    completed = subprocess.run(
        [rust_bin, "fuzz", "--cases", cases_path],
        check=True,
        capture_output=True,
        text=True,
    )
    results = []
    for line in completed.stdout.splitlines():
        if line.strip():
            results.append(json.loads(line))
    return results


def compare(python_side: list[dict], rust_side: list[dict], examples: int = 10) -> dict:
    divergences = []
    if len(python_side) != len(rust_side):
        return {
            "python_count": len(python_side),
            "rust_count": len(rust_side),
            "divergences": [{"reason": "result count mismatch"}],
            "divergence_count": 1,
        }

    for index, (py, rs) in enumerate(zip(python_side, rust_side)):
        if py["ok"] != rs["ok"] or (py["ok"] and py["steps"] != rs["steps"]):
            divergences.append(
                {
                    "index": index,
                    "id": py.get("id"),
                    "python": py,
                    "rust": rs,
                }
            )

    return {
        "python_count": len(python_side),
        "rust_count": len(rust_side),
        "divergence_count": len(divergences),
        "divergences": divergences[:examples],
    }


def run(cases_path: str, rust_bin: str, report_path: str | None = None) -> dict:
    py = python_results(cases_path)
    rs = rust_results(cases_path, rust_bin)
    report = compare(py, rs)

    if report_path:
        destination = Path(report_path)
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(
            json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )

    return report
