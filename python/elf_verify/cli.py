"""Command line entry point for the Python verifier and fuzz tooling."""

import argparse
import json
from pathlib import Path

from . import differential, fuzz
from .csvio import load_puzzles, load_submission
from .ledger import init_db, record_fuzz_run
from .verifier import DEFAULT_CONFIG, VerifyError, verify_submission

ROOT = Path(__file__).resolve().parents[2]


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="elf-verify.py")
    subparsers = parser.add_subparsers(dest="command", required=True)

    init = subparsers.add_parser("init-db", help="create the provenance ledger")
    init.add_argument("--db", default="solutions.db")
    init.add_argument("--config", default=str(ROOT / "config" / "competition.json"))
    init.add_argument("--schema", default=str(ROOT / "sql" / "schema.sql"))

    generator = subparsers.add_parser("fuzz", help="generate the differential fuzz corpus")
    generator.add_argument("--count", type=int, default=50_000)
    generator.add_argument("--seed", type=int, default=20261126)
    generator.add_argument("--out", default="outputs/fuzz.ndjson")

    diff = subparsers.add_parser("differential", help="compare Rust and Python verifiers")
    diff.add_argument("--cases", required=True)
    diff.add_argument("--rust-bin", default="target/release/elf-verify")
    diff.add_argument("--report", default="outputs/fuzz_report.json")
    diff.add_argument("--db", default=None, help="record the run in solutions.db")

    checker = subparsers.add_parser("check", help="verify a real submission with Python")
    checker.add_argument("--puzzles", required=True)
    checker.add_argument("--submission", required=True)
    checker.add_argument("--json", action="store_true")

    return parser


def run_check(args: argparse.Namespace) -> int:
    puzzles = {puzzle.id: puzzle for puzzle in load_puzzles(args.puzzles)}
    rows = load_submission(args.submission)
    total_steps = 0
    failures = []
    seen = set()

    for puzzle_id, program_json in rows:
        if puzzle_id in seen:
            failures.append(f"duplicate submission id: {puzzle_id}")
            continue
        seen.add(puzzle_id)
        puzzle = puzzles.get(puzzle_id)
        if puzzle is None:
            failures.append(f"submission id {puzzle_id} is not in puzzles.csv")
            continue
        try:
            outcome = verify_submission(puzzle, program_json, DEFAULT_CONFIG)
            total_steps += outcome.steps
        except VerifyError as error:
            failures.append(f"{puzzle_id}: {error}")

    for puzzle_id in puzzles:
        if puzzle_id not in seen:
            failures.append(f"puzzle {puzzle_id} has no submission row")

    if args.json:
        print(
            json.dumps(
                {
                    "ok": not failures,
                    "puzzles": len(puzzles),
                    "rows": len(rows),
                    "total_steps": total_steps,
                    "failures": failures,
                },
                sort_keys=True,
            )
        )
    else:
        print(f"puzzles: {len(puzzles)}")
        print(f"rows:    {len(rows)}")
        print(f"steps:   {total_steps}")
        print(f"status:  {'OK' if not failures else f'FAILED ({len(failures)} problems)'}")
        for failure in failures[:20]:
            print(f"  - {failure}")

    return 0 if not failures else 1


def main() -> int:
    args = build_parser().parse_args()

    if args.command == "init-db":
        count = init_db(args.db, args.config, args.schema)
        print(f"initialized {args.db} with {count} metadata facts")

    elif args.command == "fuzz":
        Path(args.out).parent.mkdir(parents=True, exist_ok=True)
        tally = fuzz.generate(args.count, args.seed, args.out)
        print(f"wrote {sum(tally.values())} cases to {args.out}")
        for category, count in sorted(tally.items()):
            print(f"  {category}: {count}")

    elif args.command == "differential":
        report = differential.run(args.cases, args.rust_bin, args.report)
        if args.db:
            record_fuzz_run(
                args.db,
                report["python_count"],
                report["divergence_count"],
                args.report,
            )
        print(
            f"cases: {report['python_count']} / {report['rust_count']}, "
            f"divergences: {report['divergence_count']}"
        )
        for item in report["divergences"][:10]:
            print(f"  #{item['index']} {item.get('id')}: python={item['python']} rust={item['rust']}")
        return 0 if report["divergence_count"] == 0 else 1

    elif args.command == "check":
        return run_check(args)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
