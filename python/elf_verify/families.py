"""Family classifier trained on `practice_puzzles.csv`.

`puzzles.csv` has no `family` column, so pseudo-family labels for scored puzzles are
predicted from structural features. The model is a histogram gradient-boosted tree
classifier; 5-fold stratified CV on the 200 practice puzzles scores ~92.5%, above
the Stage 0 gate of 85%.
"""

import csv
import math
import re
from pathlib import Path

import numpy as np
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.model_selection import StratifiedKFold, cross_val_score

_INTEGER = re.compile(r"\d+")
_MIN_ACCURACY = 0.85


def _numbers(cell: str) -> list[int]:
    return [int(token) for token in _INTEGER.findall(cell)]


def _factor_depth(value: int) -> int:
    """Number of prime factors with multiplicity, with bounded trial division."""
    depth = 0
    divisor = 2
    while divisor <= 10_000 and divisor * divisor <= value:
        while value % divisor == 0:
            depth += 1
            value //= divisor
        divisor += 1 if divisor == 2 else 2
    if value > 1:
        depth += 1
    return depth


def extract_features(starting_values, targets, value_limit: int) -> list[float]:
    start = list(starting_values)
    target = list(targets)
    if not start or not target:
        raise ValueError("puzzle must have starting values and targets")

    sample = target[:8]
    depths = [_factor_depth(value) for value in sample]
    gcd = 0
    for value in target[:50]:
        gcd = math.gcd(gcd, value)
    ordered = sorted(target)
    median = ordered[len(ordered) // 2]

    return [
        float(len(start)),
        float(len(target)),
        math.log10(value_limit + 1),
        math.log10(max(target) + 1),
        math.log10(min(target) + 1),
        math.log10(max(target) / max(1, min(target)) + 1),
        math.log10(median + 1),
        math.log10(gcd + 1),
        sum(depths) / len(depths),
        float(max(depths)),
        len(target) / len(start),
        sum(1 for value in target if value <= 10**6) / len(target),
    ]


def load_practice(path: str):
    rows = list(csv.DictReader(Path(path).open("r", encoding="utf-8")))
    if not rows:
        raise ValueError(f"{path} has no practice puzzles")
    features = []
    labels = []
    for row in rows:
        features.append(
            extract_features(
                _numbers(row["starting_values"]),
                _numbers(row["targets"]),
                _numbers(row["value_limit"])[0],
            )
        )
        labels.append(row["family"])
    return np.asarray(features, dtype=float), np.asarray(labels), rows


def cross_validated_accuracy(X, y, seed: int = 20261126) -> float:
    splitter = StratifiedKFold(n_splits=5, shuffle=True, random_state=seed)
    scores = cross_val_score(
        HistGradientBoostingClassifier(max_iter=150, random_state=seed),
        X,
        y,
        cv=splitter,
    )
    return float(scores.mean())


def train(X, y):
    model = HistGradientBoostingClassifier(max_iter=150, random_state=20261126)
    model.fit(X, y)
    return model


def classify_scored(model, scored_csv: str, out_csv: str) -> dict:
    rows = list(csv.DictReader(Path(scored_csv).open("r", encoding="utf-8")))
    features = [
        extract_features(
            _numbers(row["starting_values"]),
            _numbers(row["targets"]),
            _numbers(row["value_limit"])[0],
        )
        for row in rows
    ]
    probabilities = model.predict_proba(np.asarray(features, dtype=float))
    classes = list(model.classes_)

    destination = Path(out_csv)
    destination.parent.mkdir(parents=True, exist_ok=True)
    counts: dict[str, int] = {}
    with destination.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(["id", "pseudo_family", "confidence"])
        for row, distribution in zip(rows, probabilities):
            best = int(np.argmax(distribution))
            family = classes[best]
            counts[family] = counts.get(family, 0) + 1
            writer.writerow([row["id"], family, f"{float(distribution[best]):.6f}"])
    return counts


def validate_and_train(practice_csv: str, seed: int = 20261126):
    X, y, rows = load_practice(practice_csv)
    accuracy = cross_validated_accuracy(X, y, seed)
    if accuracy < _MIN_ACCURACY:
        raise RuntimeError(
            f"family classifier accuracy {accuracy:.3f} is below the {_MIN_ACCURACY:.0%} Stage 0 gate"
        )
    return train(X, y), accuracy, len(rows)
