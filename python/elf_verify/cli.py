"""Command line entry point for the Python verifier and fuzz tooling."""

import argparse
import csv
import json
import sqlite3
from pathlib import Path

from . import differential, fuzz, ledger
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

    classifier = subparsers.add_parser("classify", help="train and apply the family classifier")
    classifier.add_argument("--practice", default="data/practice_puzzles.csv")
    classifier.add_argument("--scored", default="data/puzzles.csv")
    classifier.add_argument("--out", default="outputs/families.csv")

    seed = subparsers.add_parser("seed-puzzles", help="seed puzzle facts into the ledger")
    seed.add_argument("--puzzles", default="data/puzzles.csv")
    seed.add_argument("--families", default="outputs/families.csv")
    seed.add_argument("--db", default="solutions.db")

    parity = subparsers.add_parser("record-parity", help="record Kaggle live-scorer parity")
    parity.add_argument("--submission-ref", required=True)
    parity.add_argument("--local-steps", type=int, required=True)
    parity.add_argument("--kaggle-score", type=int, required=True)
    parity.add_argument("--submission-file", required=True)
    parity.add_argument("--db", default="solutions.db")

    profiler = subparsers.add_parser("profile", help="compute lower bounds and regret ranking")
    profiler.add_argument("--puzzles", default="data/puzzles.csv")
    profiler.add_argument("--db", default="solutions.db")
    profiler.add_argument("--out", default="outputs/regret_ranking.csv")

    export = subparsers.add_parser("export-submission", help="export the best verified solution per puzzle")
    export.add_argument("--db", default="solutions.db")
    export.add_argument("--out", default="outputs/submission.csv")

    allocate = subparsers.add_parser("stage2-allocate", help="select puzzles by bandit allocation")
    allocate.add_argument("--budget", type=int, default=100)
    allocate.add_argument("--db", default="solutions.db")

    improve_cmd = subparsers.add_parser("stage2-improve", help="run one bounded improvement round")
    improve_cmd.add_argument("--budget", type=int, default=100)
    improve_cmd.add_argument("--db", default="solutions.db")
    improve_cmd.add_argument("--out", default="outputs/stage2_submission.csv")

    ceiling = subparsers.add_parser("ceiling", help="check a Stage 2 step ceiling")
    ceiling.add_argument("--day", type=int, required=True)
    ceiling.add_argument("--db", default="solutions.db")

    yields = subparsers.add_parser("yield", help="measure per-family step improvement per CPU-second")
    yields.add_argument("--puzzles", default="data/puzzles.csv")
    yields.add_argument("--db", default="solutions.db")
    yields.add_argument("--out", default="outputs/yield_baseline.csv")

    baseline = subparsers.add_parser("baseline", help="generate Stage 1 baseline programs")
    baseline.add_argument("--puzzles", default="data/puzzles.csv")
    baseline.add_argument("--out", default="outputs/baseline_submission.csv")

    seed_solutions = subparsers.add_parser(
        "seed-solutions", help="insert already-verified solutions into the ledger"
    )
    seed_solutions.add_argument("--submission", required=True)
    seed_solutions.add_argument("--tag", required=True)
    seed_solutions.add_argument("--note", default="")
    seed_solutions.add_argument("--db", default="solutions.db")
    seed_solutions.add_argument(
        "--require-check",
        help="path to Rust `check --json` output; seeding aborts unless ok=true",
    )

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

    elif args.command == "classify":
        from .families import classify_scored, validate_and_train

        model, accuracy, training_rows = validate_and_train(args.practice)
        counts = classify_scored(model, args.scored, args.out)
        print(f"trained on {training_rows} practice puzzles")
        print(f"5-fold CV accuracy: {accuracy:.3f} (gate: 0.850)")
        print(f"predictions written to {args.out}")
        for family, count in sorted(counts.items()):
            print(f"  {family}: {count}")

    elif args.command == "seed-puzzles":
        with Path(args.families).open("r", encoding="utf-8") as handle:
            families = {
                row["id"]: row["pseudo_family"] for row in csv.DictReader(handle)
            }
        count = ledger.seed_puzzles(args.db, load_puzzles(args.puzzles), families)
        print(f"seeded {count} puzzles into {args.db}")

    elif args.command == "record-parity":
        ledger.record_parity(
            args.db,
            args.submission_ref,
            args.local_steps,
            args.kaggle_score,
            args.submission_file,
        )
        print("parity result recorded in ledger")

    elif args.command == "profile":
        from .profile import profile

        summary = profile(args.db, load_puzzles(args.puzzles), args.out)
        print(f"profiled {summary['puzzles']} puzzles")
        print(f"total steps:       {summary['total_steps']}")
        print(f"total lower bound: {summary['total_lower_bound']}")
        print(f"total regret:      {summary['total_regret']}")
        print(f"ranking: {summary['ranking_path']}")
        with sqlite3.connect(args.db) as connection:
            for family, count, regret in connection.execute(
                "SELECT pseudo_family, COUNT(*), SUM(regret) FROM puzzles "
                "GROUP BY pseudo_family ORDER BY SUM(regret) DESC"
            ):
                print(f"  {family}: {count} puzzles, regret {regret}")

    elif args.command == "export-submission":
        with sqlite3.connect(args.db) as connection:
            rows = connection.execute(
                "SELECT s.puzzle_id, s.program_json FROM solutions s "
                "JOIN (SELECT puzzle_id, MIN(steps) AS steps FROM solutions GROUP BY puzzle_id) b "
                "ON s.puzzle_id = b.puzzle_id AND s.steps = b.steps "
                "ORDER BY s.puzzle_id"
            ).fetchall()
        destination = Path(args.out)
        destination.parent.mkdir(parents=True, exist_ok=True)
        with destination.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.writer(handle)
            writer.writerow(["id", "program"])
            writer.writerows(rows)
        print(f"exported {len(rows)} solutions to {args.out}")

    elif args.command == "stage2-allocate":
        from .bandit import BanditAllocator

        selected = BanditAllocator(args.db).select(args.budget)
        print(f"selected {len(selected)} puzzles")
        print(" ".join(selected[:20]))

    elif args.command == "stage2-improve":
        from .bandit import BanditAllocator
        from .improve import solve as improve_solve
        from .stage2 import log_allocation

        selected = BanditAllocator(args.db).select(args.budget)
        with sqlite3.connect(args.db) as connection:
            best = {
                puzzle_id: steps
                for puzzle_id, steps in connection.execute(
                    "SELECT puzzle_id, MIN(steps) FROM solutions GROUP BY puzzle_id"
                )
            }
        puzzles = {puzzle.id: puzzle for puzzle in load_puzzles("data/puzzles.csv")}
        rows = []
        improved = 0
        before = after = 0
        for puzzle_id in selected:
            puzzle = puzzles.get(puzzle_id)
            if puzzle is None:
                continue
            program = improve_solve(puzzle)
            steps = len(json.loads(program))
            if puzzle_id in best and steps >= best[puzzle_id]:
                continue
            rows.append((puzzle_id, program))
            before += best.get(puzzle_id, 0)
            after += steps
            improved += 1

        destination = Path(args.out)
        destination.parent.mkdir(parents=True, exist_ok=True)
        with destination.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.writer(handle)
            writer.writerow(["id", "program"])
            writer.writerows(rows)
        log_allocation(args.db, selected, "subtractive_cone_v1")
        print(f"selected {len(selected)}, improved {improved}, steps {before} -> {after}")
        print(f"wrote {args.out}")

    elif args.command == "ceiling":
        from .stage2 import check_ceiling

        result = check_ceiling(args.db, args.day)
        print(json.dumps(result, sort_keys=True))

    elif args.command == "yield":
        from .profile import yield_baseline

        summary = yield_baseline(args.db, load_puzzles(args.puzzles), args.out)
        print(f"yield priors for {summary['families']} families written to {summary['ranking_path']}")
        print(Path(summary["ranking_path"]).read_text(encoding="utf-8"), end="")

    elif args.command == "baseline":
        from .baseline import solve

        puzzles = load_puzzles(args.puzzles)
        destination = Path(args.out)
        destination.parent.mkdir(parents=True, exist_ok=True)
        total = 0
        with destination.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.writer(handle)
            writer.writerow(["id", "program"])
            for puzzle in puzzles:
                program = solve(puzzle)
                total += len(json.loads(program))
                writer.writerow([puzzle.id, program])
        print(f"wrote {len(puzzles)} baseline programs, {total} total steps to {args.out}")

    elif args.command == "seed-solutions":
        if args.require_check:
            report = json.loads(Path(args.require_check).read_text(encoding="utf-8"))
            if not report.get("ok"):
                print("refusing to seed: Rust verifier check did not pass", file=__import__("sys").stderr)
                return 1
        rows = load_submission(args.submission)
        written = ledger.seed_solutions(args.db, rows, args.tag, args.note)
        print(f"inserted {written} improved solutions into {args.db}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
