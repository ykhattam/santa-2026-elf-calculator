# Competition data drop site

Place the Kaggle files here (they are gitignored):

```
data/puzzles.csv
data/practice_puzzles.csv
data/sample_submission.csv
data/submission.csv
```

The Kaggle CLI is currently unavailable in this environment (missing `six`, and no
`~/.kaggle/kaggle.json`). Once credentials are installed:

```bash
kaggle competitions download -c <competition-slug> -p data
cd data && unzip -o <archive>.zip
```

Then run the Stage 0 gates:

```bash
target/release/elf-verify check --puzzles data/puzzles.csv --submission data/sample_submission.csv
PYTHONPATH=python python3 -m elf_verify.cli check --puzzles data/puzzles.csv --submission data/sample_submission.csv
```

If the two totals differ, halt and diagnose before any solver work.
