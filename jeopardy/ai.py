"""Simulated AI contestants.

Each AI has a difficulty profile that controls how often it knows an answer,
how fast it buzzes, how often it bluffs, and how smartly it wagers. Each AI
also gets random strong/weak categories so opponents feel different.
"""
from __future__ import annotations

import random
from dataclasses import dataclass, field

from .clues import Board, Clue


@dataclass(frozen=True)
class Difficulty:
    key: str
    label: str
    description: str
    know_base: float       # chance of knowing a $200-tier clue
    know_drop: float       # knowledge lost per tier step
    accuracy: float        # chance a "known" answer is actually right
    bluff: float           # chance of buzzing without knowing
    react: tuple[float, float]  # buzz reaction window (seconds after buzzers open)
    strategy: str          # "casual" | "solid" | "shark"


EASY = Difficulty(
    "easy", "Easy",
    "Casual trivia fans. They know the top rows, fade fast on the pricey clues, "
    "buzz slowly (~1-2s), sometimes buzz on a hunch, and wager on gut feeling.",
    know_base=0.55, know_drop=0.08, accuracy=0.80, bluff=0.10,
    react=(0.9, 2.2), strategy="casual",
)
MEDIUM = Difficulty(
    "medium", "Medium",
    "Solid regulars. Good general knowledge with real gaps on $1,000+ clues, "
    "decent buzzer timing (~0.4-1.3s), and sensible wagers.",
    know_base=0.80, know_drop=0.08, accuracy=0.90, bluff=0.05,
    react=(0.4, 1.3), strategy="solid",
)
HARD = Difficulty(
    "hard", "Hard",
    "Champions. They know almost everything, buzz lightning-fast (~0.15-0.7s), "
    "rarely miss, hunt Daily Doubles, and wager like game-theory sharks.",
    know_base=0.96, know_drop=0.05, accuracy=0.97, bluff=0.02,
    react=(0.15, 0.7), strategy="shark",
)
DIFFICULTIES = [EASY, MEDIUM, HARD]

AI_NAMES = ["Ada", "Hal", "Pixel", "Watt", "Turing", "Ziggy", "Bolt", "Nova"]


@dataclass(eq=False)
class Player:
    name: str
    is_human: bool = False
    score: int = 0


@dataclass(eq=False)
class AIPlayer(Player):
    difficulty: Difficulty = MEDIUM
    rng: random.Random = field(default_factory=random.Random)
    affinity: dict[str, float] = field(default_factory=dict)

    def _affinity(self, category: str) -> float:
        if category not in self.affinity:
            self.affinity[category] = self.rng.uniform(-0.12, 0.12)
        return self.affinity[category]

    def p_know(self, category: str, tier: int) -> float:
        d = self.difficulty
        p = d.know_base - d.know_drop * (tier - 1) + self._affinity(category)
        return max(0.03, min(0.99, p))

    def decide(self, clue: Clue) -> tuple[bool, bool, float]:
        """Return (buzzes, will_be_correct, reaction_seconds)."""
        knows = self.rng.random() < self.p_know(clue.category, clue.tier)
        react = self.rng.uniform(*self.difficulty.react)
        if knows:
            return True, self.rng.random() < self.difficulty.accuracy, react
        if self.rng.random() < self.difficulty.bluff:
            # Bluffs come a beat slower and are usually wrong.
            return True, self.rng.random() < 0.15, react + 0.3
        return False, False, 0.0

    def answer_correct(self, category: str, tier: int) -> bool:
        """Used when only this AI answers (Daily Double / Final)."""
        p = self.p_know(category, tier) * self.difficulty.accuracy
        return self.rng.random() < p

    # ---- board selection ---------------------------------------------------
    def pick_clue(self, board: Board) -> tuple[int, int]:
        avail = board.available()
        strat = self.difficulty.strategy
        if strat == "casual":
            return self.rng.choice(avail)
        if strat == "solid":
            # Work top-down through a favoured category.
            best = max(
                {c for c, _ in avail},
                key=lambda c: self._affinity(board.categories[c].name) + self.rng.uniform(0, 0.1),
            )
            rows = sorted(r for c, r in avail if c == best)
            return best, rows[0]
        # Shark: hunt the bottom rows where Daily Doubles live, then clean up.
        deep = [(c, r) for c, r in avail if r >= 2]
        if deep:
            maxrow = max(r for _, r in deep)
            candidates = [(c, r) for c, r in deep if r >= maxrow - 1]
            return self.rng.choice(candidates)
        return self.rng.choice(avail)

    # ---- wagering ------------------------------------------------------------
    def daily_double_wager(self, clue: Clue, round_max: int, others: list[int]) -> int:
        max_bet = max(self.score, round_max)
        p = self.p_know(clue.category, clue.tier)
        strat = self.difficulty.strategy
        if strat == "casual":
            frac = self.rng.uniform(0.05, 0.35)
        elif strat == "solid":
            frac = 0.15 + 0.4 * p + self.rng.uniform(-0.05, 0.05)
        else:
            leader = max(others) if others else 0
            frac = 0.25 + 0.6 * p
            if self.score < leader:
                frac += 0.2
            if self.score > 0 and p > 0.85:
                frac = max(frac, 0.9)
        wager = int(max_bet * max(0.0, min(1.0, frac)))
        wager = max(5, min(max_bet, round(wager / 100) * 100 or wager))
        return wager

    def final_wager(self, others: list[int]) -> int:
        if self.score <= 0:
            return 0
        s = self.score
        rivals = sorted((o for o in others if o > 0), reverse=True)
        top_rival = rivals[0] if rivals else 0
        strat = self.difficulty.strategy
        if strat == "casual":
            return self.rng.randint(0, s)
        if strat == "solid":
            if s > top_rival:
                cover = 2 * top_rival - s + 1
                return max(0, min(s, cover + self.rng.randint(0, 400)))
            return min(s, int(s * self.rng.uniform(0.5, 1.0)))
        # Shark
        if s > 2 * top_rival:
            return max(0, s - 2 * top_rival - 1)     # locked game: never risk it
        if s >= top_rival:
            return max(0, min(s, 2 * top_rival - s + 1))  # cover the runner-up doubling
        if 2 * s > top_rival:
            return s                                  # need to double up
        return 0                                      # can't catch up; play for 2nd


def make_opponents(difficulty: Difficulty, rng: random.Random) -> list[AIPlayer]:
    names = rng.sample(AI_NAMES, 2)
    return [AIPlayer(n, difficulty=difficulty, rng=random.Random(rng.random())) for n in names]
