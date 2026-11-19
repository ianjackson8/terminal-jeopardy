"""Headless end-to-end runs using a fake curses window and a fake clock."""
import itertools
import random
import tempfile
import types
import unittest
from pathlib import Path
from unittest import mock

from jeopardy import app as app_mod
from jeopardy import screen as screen_mod
from jeopardy import stats as stats_mod
from jeopardy.ai import DIFFICULTIES


class FakeClock:
    def __init__(self):
        self.t = 0.0

    def monotonic(self):
        self.t += 0.001
        return self.t


class FakeWindow:
    def __init__(self, clock, keys, h=24, w=80):
        self.clock, self.keys, self.h, self.w = clock, keys, h, w
        self._timeout = -1
        self.calls = 0

    def keypad(self, flag): pass
    def getmaxyx(self): return self.h, self.w
    def bkgd(self, *a): pass
    def erase(self): pass
    def refresh(self): pass
    def timeout(self, ms): self._timeout = ms

    def addstr(self, y, x, text, attr=0):
        assert 0 <= y < self.h and 0 <= x < self.w, (y, x, text)
        assert x + len(text) <= self.w, (y, x, text)

    def get_wch(self):
        self.calls += 1
        if self.calls > 500_000:
            raise RuntimeError("game did not finish")
        self.clock.t += max(self._timeout, 50) / 1000 if self._timeout >= 0 else 0.05
        k = next(self.keys)
        if k is None:
            raise screen_mod.curses.error()
        return k


def run_with(fn, keys, h=24, w=80):
    clock = FakeClock()
    fake_time = types.SimpleNamespace(monotonic=clock.monotonic)
    win = FakeWindow(clock, keys, h, w)
    with tempfile.TemporaryDirectory() as tmp, \
            mock.patch.object(app_mod, "time", fake_time), \
            mock.patch.object(screen_mod, "time", fake_time), \
            mock.patch.object(stats_mod, "STATS_FILE", Path(tmp) / "stats.json"), \
            mock.patch.object(screen_mod.curses, "curs_set", lambda *a: None), \
            mock.patch.object(screen_mod.curses, "has_colors", lambda: False), \
            mock.patch.object(screen_mod.curses, "flushinp", lambda: None):
        a = app_mod.App(win)
        fn(a)
        return a


def key_stream(seed):
    rng = random.Random(seed)
    # A mix of idling, buzzing, answering, navigating and wagering.
    pool = [None, None, None, " ", "\n", "5", "l", "j", "\n", "o"]
    return iter(lambda: rng.choice(pool), object())


class SmokeTests(unittest.TestCase):
    def test_full_games(self):
        for i, diff in enumerate(DIFFICULTIES):
            for seed in range(3):
                a = run_with(lambda a: (setattr(a, "rng", random.Random(seed)), a.play_game(diff)),
                             key_stream(seed * 10 + i))
                g = a.stats["games"][diff.key]
                self.assertEqual(g["played"], 1)
                self.assertTrue(all(isinstance(p.score, int) for p in a.players))

    def test_practice(self):
        cats, _ = app_mod.load_bank()
        clues = [c for raw in cats[:3] for c in app_mod.make_category(raw, 1).clues]
        keys = itertools.chain(["P", "a", "r", "i", "s", "\n"], key_stream(99))
        a = run_with(lambda a: a.practice_session(clues, "TEST", timed=True), keys)
        self.assertGreater(a.stats["practice"]["answered"], 0)

    def test_stats_page(self):
        browse = [None, "l", *["j"] * 60, "k", "l", *["j"] * 60, "l", "h"]

        def play_then_browse(a, extra):
            a.rng = random.Random(4)
            for d in DIFFICULTIES * 2:
                a.play_game(d)
            a.s.scr.keys = iter(browse + extra + ["\x1b"])
            a.stats_page()

        for h, w in [(22, 70), (24, 80), (50, 200)]:
            a = run_with(lambda a: play_then_browse(a, []), key_stream(h), h=h, w=w)
            c = a.stats["career"]
            self.assertEqual(c["played"], 6)
            self.assertEqual(len(a.stats["history"]), 6)
            self.assertGreaterEqual(c["best_streak"], c["current_streak"])

        # R then y wipes everything.
        a = run_with(lambda a: play_then_browse(a, ["r", "y"]), key_stream(1))
        self.assertEqual(a.stats.get("career", {}).get("played", 0), 0)
        self.assertNotIn("history", a.stats)
        self.assertNotIn("games", a.stats)

    def test_stats_page_empty(self):
        a = run_with(lambda a: a.stats_page(), iter([None, "l", "l", "l", "\x1b"]))
        self.assertEqual(a.stats.get("career", {}).get("played", 0), 0)

    def test_big_terminal(self):
        a = run_with(lambda a: a.play_game(DIFFICULTIES[2]), key_stream(7), h=50, w=200)
        self.assertEqual(a.stats["games"]["hard"]["played"], 1)


if __name__ == "__main__":
    unittest.main()
