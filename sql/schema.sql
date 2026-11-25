-- Immutable provenance ledger for Santa 2026.
-- All writes are append-only; corrections are new rows, never updates to solutions.

CREATE TABLE IF NOT EXISTS meta (
    key         TEXT PRIMARY KEY,
    value       TEXT NOT NULL,
    updated_at  TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS puzzles (
    id              TEXT PRIMARY KEY,
    starting_values TEXT NOT NULL,
    targets         TEXT NOT NULL,
    value_limit     TEXT NOT NULL,
    pseudo_family   TEXT,
    design_tier     TEXT,
    profile_steps   INTEGER,
    lower_bound     INTEGER,
    regret          INTEGER,
    profiled_at     TEXT
);

CREATE TABLE IF NOT EXISTS solutions (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    puzzle_id    TEXT NOT NULL REFERENCES puzzles(id),
    steps        INTEGER NOT NULL,
    solver_tag   TEXT NOT NULL,
    program_json TEXT NOT NULL,
    sha256       TEXT NOT NULL,
    verified_at  TEXT NOT NULL DEFAULT (datetime('now')),
    git_sha      TEXT,
    seed         TEXT,
    note         TEXT,
    UNIQUE(puzzle_id, sha256)
);

CREATE INDEX IF NOT EXISTS idx_solutions_puzzle_steps
    ON solutions(puzzle_id, steps ASC);

CREATE TABLE IF NOT EXISTS fuzz_runs (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    ts           TEXT NOT NULL DEFAULT (datetime('now')),
    case_count   INTEGER NOT NULL,
    divergences  INTEGER NOT NULL,
    rust_sha256  TEXT,
    python_sha256 TEXT,
    report_path  TEXT
);

CREATE TABLE IF NOT EXISTS telemetry (
    id      INTEGER PRIMARY KEY AUTOINCREMENT,
    ts      TEXT NOT NULL DEFAULT (datetime('now')),
    event   TEXT NOT NULL,
    payload TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS alerts (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    ts            TEXT NOT NULL DEFAULT (datetime('now')),
    kind          TEXT NOT NULL,
    detail        TEXT NOT NULL,
    acknowledged  INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS stage_gates (
    name        TEXT PRIMARY KEY,
    target_date TEXT NOT NULL,
    status      TEXT NOT NULL DEFAULT 'pending',
    checked_at  TEXT,
    notes       TEXT
);
