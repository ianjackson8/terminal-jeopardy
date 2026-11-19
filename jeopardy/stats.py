"""Persistent player statistics: career totals, win streaks, history and categories."""
from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from pathlib import Path

STATS_FILE = Path.home() / ".terminal-jeopardy" / "stats.json"
HISTORY_LEN = 100


def load_stats(path: Path | None = None) -> dict:
    try:
        return json.loads((path or STATS_FILE).read_text())
    except (OSError, ValueError):
        return {}


def save_stats(stats: dict, path: Path | None = None) -> None:
    path = path or STATS_FILE
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(stats, indent=2))
    except OSError:
        pass


@dataclass
class GameLog:
    """Everything the human did during one game."""
    responses: int = 0
    correct: int = 0
    streak: int = 0
    best_streak: int = 0
    dd_played: int = 0
    dd_correct: int = 0
    dd_net: int = 0
    final_played: bool = False
    final_correct: bool = False
    by_category: dict[str, list[int]] = field(default_factory=dict)

    def answer(self, correct: bool, category: str) -> None:
        self.responses += 1
        rec = self.by_category.setdefault(category, [0, 0])
        rec[1] += 1
        if correct:
            self.correct += 1
            rec[0] += 1
            self.streak += 1
            self.best_streak = max(self.best_streak, self.streak)
        else:
            self.streak = 0


def _career_defaults() -> dict:
    return {
        "played": 0, "wins": 0,
        "total_winnings": 0, "total_score": 0,
        "highest_score": None, "lowest_score": None,
        "current_streak": 0, "current_streak_winnings": 0,
        "best_streak": 0, "best_streak_winnings": 0,
        "responses": 0, "correct": 0, "best_answer_streak": 0,
        "dd_played": 0, "dd_correct": 0, "dd_net": 0,
        "final_played": 0, "final_correct": 0,
        "by_category": {},
    }


def career(stats: dict) -> dict:
    """Return the career block, creating it (seeded from older per-difficulty records) if missing."""
    c = stats.get("career")
    if c is None:
        c = _career_defaults()
        games = stats.get("games", {})
        c["played"] = sum(g.get("played", 0) for g in games.values())
        c["wins"] = sum(g.get("wins", 0) for g in games.values())
        stats["career"] = c
    for k, v in _career_defaults().items():
        c.setdefault(k, v)
    return c


def record_game(stats: dict, difficulty: str, score: int, won: bool, place: int,
                log: GameLog, when: float | None = None) -> dict:
    """Fold one finished game into `stats`. Returns the career block."""
    c = career(stats)
    c["played"] += 1
    c["total_score"] += score
    c["highest_score"] = score if c["highest_score"] is None else max(c["highest_score"], score)
    c["lowest_score"] = score if c["lowest_score"] is None else min(c["lowest_score"], score)
    if won:
        c["wins"] += 1
        c["total_winnings"] += score
        c["current_streak"] += 1
        c["current_streak_winnings"] += score
        if (c["current_streak"], c["current_streak_winnings"]) > (c["best_streak"], c["best_streak_winnings"]):
            c["best_streak"] = c["current_streak"]
            c["best_streak_winnings"] = c["current_streak_winnings"]
    else:
        c["current_streak"] = 0
        c["current_streak_winnings"] = 0

    c["responses"] += log.responses
    c["correct"] += log.correct
    c["best_answer_streak"] = max(c["best_answer_streak"], log.best_streak)
    c["dd_played"] += log.dd_played
    c["dd_correct"] += log.dd_correct
    c["dd_net"] += log.dd_net
    c["final_played"] += int(log.final_played)
    c["final_correct"] += int(log.final_played and log.final_correct)
    for cat, (ok, n) in log.by_category.items():
        rec = c["by_category"].setdefault(cat, [0, 0])
        rec[0] += ok
        rec[1] += n

    g = stats.setdefault("games", {}).setdefault(difficulty, {"played": 0, "wins": 0, "best": 0})
    g["played"] += 1
    g["wins"] += int(won)
    g["best"] = max(g.get("best", 0), score)
    g["winnings"] = g.get("winnings", 0) + (score if won else 0)

    history = stats.setdefault("history", [])
    history.insert(0, {
        "date": time.strftime("%Y-%m-%d", time.localtime(when)),
        "difficulty": difficulty,
        "score": score,
        "won": won,
        "place": place,
        "responses": log.responses,
        "correct": log.correct,
    })
    del history[HISTORY_LEN:]
    return c


def category_table(stats: dict) -> list[tuple[str, int, int, int, int]]:
    """Rows of (category, game_correct, game_total, practice_correct, practice_total)."""
    games = career(stats)["by_category"]
    practice = stats.get("practice", {}).get("by_category", {})
    rows = []
    for cat in sorted(set(games) | set(practice)):
        gc, gn = games.get(cat, [0, 0])
        pc, pn = practice.get(cat, [0, 0])
        rows.append((cat, gc, gn, pc, pn))
    rows.sort(key=lambda r: (-(r[1] + r[3]) / max(1, r[2] + r[4]), -(r[2] + r[4]), r[0]))
    return rows


# ---- settings (kept apart from stats so resetting stats keeps your preferences) ----
SETTINGS_FILE = Path.home() / ".terminal-jeopardy" / "settings.json"


def load_settings() -> dict:
    return load_stats(SETTINGS_FILE)


def save_settings(settings: dict) -> None:
    save_stats(settings, SETTINGS_FILE)
