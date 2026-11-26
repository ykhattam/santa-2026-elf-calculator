# Competition data drop site

Place the Kaggle files here (they are gitignored):

```
data/puzzles.csv
data/practice_puzzles.csv
data/sample_submission.csv
data/submission.csv
```

The Kaggle CLI is working (`six` installed into the uv tool env; credentials are available
as `yassineelkhattam` via access token). The files below are already downloaded here and
are gitignored.

To refresh them:

```bash
kaggle competitions download -c santa-2026 -p data --force
cd data && unzip -o santa-2026.zip && rm santa-2026.zip
```

Then run the Stage 0 gates:

```bash
target/release/elf-verify check --puzzles data/puzzles.csv --submission data/sample_submission.csv
PYTHONPATH=python python3 -m elf_verify.cli check --puzzles data/puzzles.csv --submission data/sample_submission.csv
```

If the two totals differ, halt and diagnose before any solver work.
