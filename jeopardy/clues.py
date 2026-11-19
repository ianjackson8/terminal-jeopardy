"""Clue bank loading and board construction."""
from __future__ import annotations

import json
import random
from dataclasses import dataclass, field
from pathlib import Path

DATA_FILE = Path(__file__).parent / "data" / "clues.json"

ROUND_VALUES = {
    1: [200, 400, 600, 800, 1000],
    2: [400, 800, 1200, 1600, 2000],
}


@dataclass
class Clue:
    category: str
    text: str
    answer: str
    accept: list[str] = field(default_factory=list)
    tier: int = 1          # 1 (easiest) .. 5 (hardest)
    value: int = 0
    used: bool = False
    daily_double: bool = False

    @property
    def all_answers(self) -> list[str]:
        return [self.answer, *self.accept]


@dataclass
class Category:
    name: str
    clues: list[Clue]

    @property
    def remaining(self) -> int:
        return sum(not c.used for c in self.clues)


@dataclass
class Board:
    round_no: int
    categories: list[Category]

    @property
    def values(self) -> list[int]:
        return ROUND_VALUES[self.round_no]

    def clue(self, col: int, row: int) -> Clue:
        return self.categories[col].clues[row]

    def available(self) -> list[tuple[int, int]]:
        return [
            (c, r)
            for c, cat in enumerate(self.categories)
            for r, clue in enumerate(cat.clues)
            if not clue.used
        ]

    @property
    def done(self) -> bool:
        return not self.available()


@dataclass
class FinalClue:
    category: str
    text: str
    answer: str
    accept: list[str] = field(default_factory=list)

    @property
    def all_answers(self) -> list[str]:
        return [self.answer, *self.accept]


def clue_tier(raw_clue: dict, index: int) -> int:
    """A clue's difficulty tier (1-5). Untiered clues use their position (legacy 5-clue categories)."""
    return int(raw_clue.get("tier", index + 1))


def is_playable(raw: dict) -> bool:
    """A category needs at least one clue for every tier 1-5."""
    tiers = {clue_tier(c, i) for i, c in enumerate(raw["clues"])}
    return tiers >= {1, 2, 3, 4, 5}


def load_bank(path: Path = DATA_FILE) -> tuple[list[dict], list[dict]]:
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    cats = [c for c in data["categories"] if is_playable(c)]
    return cats, data["finals"]


def _make_clue(name: str, c: dict, tier: int, values: list[int]) -> Clue:
    return Clue(category=name, text=c["clue"], answer=c["answer"], accept=list(c.get("accept", [])),
                tier=tier, value=values[tier - 1])


def make_category(raw: dict, round_no: int | None = None, rng: random.Random | None = None) -> Category:
    """Build a category.

    With `rng`, deal a board column: one random clue per tier, easiest first.
    Without it (practice), return every clue in the category, ordered by tier.
    """
    values = ROUND_VALUES[round_no] if round_no else [0] * 5
    by_tier: dict[int, list[dict]] = {}
    for i, c in enumerate(raw["clues"]):
        by_tier.setdefault(clue_tier(c, i), []).append(c)
    if rng is not None:
        clues = [_make_clue(raw["name"], rng.choice(by_tier[t]), t, values) for t in range(1, 6)]
    else:
        clues = [_make_clue(raw["name"], c, t, values) for t in sorted(by_tier) for c in by_tier[t]]
    return Category(raw["name"], clues)


def _place_daily_doubles(board: Board, count: int, rng: random.Random) -> None:
    # Daily Doubles tend to hide in the lower (pricier) rows.
    weights = [0, 1, 3, 4, 3]
    spots: set[tuple[int, int]] = set()
    cols_used: set[int] = set()
    while len(spots) < count:
        col = rng.randrange(len(board.categories))
        if col in cols_used:
            continue
        row = rng.choices(range(5), weights=weights)[0]
        spots.add((col, row))
        cols_used.add(col)
    for col, row in spots:
        board.clue(col, row).daily_double = True


def build_game(rng: random.Random | None = None) -> tuple[Board, Board, FinalClue]:
    rng = rng or random.Random()
    cats, finals = load_bank()
    if len(cats) < 12:
        raise ValueError("Need at least 12 complete categories in the clue bank")
    chosen = rng.sample(cats, 12)
    r1 = Board(1, [make_category(c, 1, rng) for c in chosen[:6]])
    r2 = Board(2, [make_category(c, 2, rng) for c in chosen[6:]])
    _place_daily_doubles(r1, 1, rng)
    _place_daily_doubles(r2, 2, rng)
    f = rng.choice(finals)
    final = FinalClue(f["category"], f["clue"], f["answer"], list(f.get("accept", [])))
    return r1, r2, final
