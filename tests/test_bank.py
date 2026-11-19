import random
import unittest
from collections import Counter

from jeopardy.clues import build_game, clue_tier, is_playable, load_bank, make_category
from jeopardy.matching import is_correct, normalize


class DepthTests(unittest.TestCase):
    def setUp(self):
        self.cats, self.finals = load_bank()

    def test_every_category_is_deep(self):
        self.assertGreaterEqual(len(self.cats), 60)
        for raw in self.cats:
            tiers = Counter(clue_tier(c, i) for i, c in enumerate(raw["clues"]))
            self.assertEqual(set(tiers), {1, 2, 3, 4, 5}, raw["name"])
            self.assertGreaterEqual(min(tiers.values()), 2, f"{raw['name']} needs 2+ clues per tier")

    def test_no_repeated_or_confusable_answers_in_a_category(self):
        for raw in self.cats:
            clues = make_category(raw).clues
            for a in clues:
                for b in clues:
                    if a is not b:
                        # Answering one clue must never be accepted as the answer to another.
                        self.assertFalse(is_correct(a.answer, b.all_answers),
                                         f"{raw['name']}: {a.answer!r} vs {b.answer!r}")

    def test_finals_unique(self):
        answers = [normalize(f["answer"]) for f in self.finals]
        self.assertEqual(len(answers), len(set(answers)))
        self.assertGreaterEqual(len(self.finals), 40)

    def test_board_column_is_one_clue_per_tier(self):
        for seed in range(20):
            r1, r2, _ = build_game(random.Random(seed))
            for board in (r1, r2):
                for cat in board.categories:
                    self.assertEqual([c.tier for c in cat.clues], [1, 2, 3, 4, 5])
                    self.assertEqual([c.value for c in cat.clues], board.values)

    def test_same_category_varies_between_games(self):
        raw = self.cats[0]
        columns = {tuple(c.answer for c in make_category(raw, 1, random.Random(s)).clues) for s in range(30)}
        self.assertGreater(len(columns), 5)

    def test_practice_gets_every_clue_in_tier_order(self):
        raw = self.cats[0]
        clues = make_category(raw, 1).clues
        self.assertEqual(len(clues), len(raw["clues"]))
        self.assertEqual([c.tier for c in clues], sorted(c.tier for c in clues))

    def test_legacy_five_clue_categories_still_work(self):
        legacy = {"name": "OLD", "clues": [{"clue": f"q{i}", "answer": f"a{i}"} for i in range(5)]}
        self.assertTrue(is_playable(legacy))
        self.assertEqual([c.tier for c in make_category(legacy, 1, random.Random(0)).clues], [1, 2, 3, 4, 5])
        self.assertFalse(is_playable({"name": "BAD", "clues": [{"clue": "q", "answer": "a", "tier": 1}]}))


if __name__ == "__main__":
    unittest.main()
