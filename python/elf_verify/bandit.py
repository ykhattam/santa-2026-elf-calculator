"""Stage 2 stratified bandit allocator.

85% of each allocation round goes to the highest absolute-regret puzzles;
15% is exploration quota split across pseudo-families so hard puzzles do not
starve. Families with no recent improvement are throttled by half.
"""

import sqlite3
from collections import defaultdict

EXPLOIT_FRACTION = 0.85
EXPLORE_FRACTION = 0.15


class BanditAllocator:
    def __init__(self, db_path: str):
        self.db_path = db_path

    def _rows(self):
        with sqlite3.connect(self.db_path) as connection:
            return connection.execute(
                "SELECT id, pseudo_family, regret FROM puzzles "
                "WHERE regret IS NOT NULL ORDER BY regret DESC"
            ).fetchall()

    def _stalled_families(self) -> set[str]:
        with sqlite3.connect(self.db_path) as connection:
            rows = connection.execute(
                "SELECT payload FROM telemetry WHERE event = 'stage2_stall' "
                "ORDER BY id DESC LIMIT 20"
            ).fetchall()
        import json

        stalled = set()
        for (payload,) in rows:
            stalled.add(json.loads(payload)["family"])
        return stalled

    def select(self, budget: int) -> list[str]:
        rows = self._rows()
        if budget <= 0 or not rows:
            return []

        stalled = self._stalled_families()
        by_family: dict[str, list[tuple[str, int]]] = defaultdict(list)
        for puzzle_id, family, regret in rows:
            by_family[family].append((puzzle_id, regret))

        # Exploration: round-robin across families, throttling stalled ones.
        families = sorted(by_family)
        explore_count = max(1, round(budget * EXPLORE_FRACTION))
        quota = {family: 1 for family in families}
        for family in stalled:
            quota[family] = 0.5
        weights = {family: max(quota[family], 0.01) for family in families}
        total_weight = sum(weights.values())

        explore = []
        for family in families:
            share = max(1, round(explore_count * weights[family] / total_weight))
            # Highest-regret unexplored puzzle from this family first.
            for puzzle_id, _ in by_family[family][:share]:
                explore.append(puzzle_id)

        # Exploitation: pure absolute-regret ordering.
        exploit_count = budget - len(explore)
        selected = [puzzle_id for puzzle_id, _, _ in rows[:exploit_count]]
        seen = set(selected)
        for puzzle_id in explore:
            if puzzle_id not in seen:
                selected.append(puzzle_id)
                seen.add(puzzle_id)

        return selected[:budget]
