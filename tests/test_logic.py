import random
import unittest

from trivia.ai import DIFFICULTIES, EASY, HARD, AIPlayer, make_opponents
from trivia.clues import build_game, load_bank, make_category
from trivia.matching import is_correct, normalize


class MatchingTests(unittest.TestCase):
    def test_question_form_and_articles(self):
        self.assertTrue(is_correct("What is the Tempest?", ["The Tempest"]))
        self.assertTrue(is_correct("who is lincoln", ["Abraham Lincoln", "lincoln"]))
        self.assertTrue(is_correct("tempest", ["The Tempest"]))

    def test_accents_and_punctuation(self):
        self.assertTrue(is_correct("salvador dali", ["Salvador Dalí"]))
        self.assertTrue(is_correct("moby dick", ["Moby-Dick"]))
        self.assertTrue(is_correct("Romeo & Juliet", ["Romeo and Juliet"]))

    def test_typos(self):
        self.assertTrue(is_correct("Machu Pichu", ["Machu Picchu"]))
        self.assertTrue(is_correct("jupitor", ["Jupiter"]))
        self.assertFalse(is_correct("Austria", ["Australia"]))
        self.assertFalse(is_correct("mary", ["Mars"]))

    def test_numbers_exact(self):
        self.assertTrue(is_correct("88", ["88"]))
        self.assertFalse(is_correct("89", ["88"]))
        self.assertFalse(is_correct("1", ["11"]))

    def test_empty(self):
        self.assertFalse(is_correct("", ["Paris"]))
        self.assertFalse(is_correct("what is", ["Paris"]))
        self.assertEqual(normalize("What's the Nile?"), "nile")


class BankTests(unittest.TestCase):
    def test_bank_integrity(self):
        cats, finals = load_bank()
        self.assertGreaterEqual(len(cats), 12)
        self.assertGreaterEqual(len(finals), 1)
        names = [c["name"] for c in cats]
        self.assertEqual(len(names), len(set(names)))
        for raw in cats:
            for clue in make_category(raw, 1).clues:
                self.assertTrue(clue.text and clue.answer)
                # Every answer must match itself.
                self.assertTrue(is_correct(clue.answer, clue.all_answers), clue.answer)

    def test_build_game(self):
        r1, r2, final = build_game(random.Random(1))
        self.assertEqual(len(r1.categories), 6)
        self.assertEqual(len(r2.categories), 6)
        self.assertFalse({c.name for c in r1.categories} & {c.name for c in r2.categories})
        self.assertEqual(sum(c.daily_double for cat in r1.categories for c in cat.clues), 1)
        self.assertEqual(sum(c.daily_double for cat in r2.categories for c in cat.clues), 2)
        self.assertEqual([c.value for c in r2.categories[0].clues], [400, 800, 1200, 1600, 2000])
        self.assertTrue(final.answer)


class AITests(unittest.TestCase):
    def accuracy(self, diff, tier, n=3000):
        ai = AIPlayer("t", difficulty=diff, rng=random.Random(5))
        r1, _, _ = build_game(random.Random(2))
        clue = r1.categories[0].clues[tier - 1]
        hits = sum(1 for _ in range(n) if (d := ai.decide(clue))[0] and d[1])
        return hits / n

    def test_difficulty_ordering(self):
        for tier in (1, 5):
            e, m, h = (self.accuracy(d, tier) for d in DIFFICULTIES)
            self.assertLess(e, m)
            self.assertLess(m, h)
        self.assertGreater(self.accuracy(HARD, 5), 0.6)
        self.assertLess(self.accuracy(EASY, 5), 0.35)

    def test_pick_and_wagers_valid(self):
        rng = random.Random(3)
        for diff in DIFFICULTIES:
            r1, _, _ = build_game(rng)
            ai = make_opponents(diff, rng)[0]
            while not r1.done:
                c, r = ai.pick_clue(r1)
                clue = r1.clue(c, r)
                self.assertFalse(clue.used)
                clue.used = True
                for score in (-400, 0, 3000):
                    ai.score = score
                    w = ai.daily_double_wager(clue, 1000, [1200, 800])
                    self.assertTrue(5 <= w <= max(score, 1000))
            for score, others in [(10000, [3000, 2000]), (5000, [4000, 100]), (3000, [8000, 0]), (100, [9000, 50])]:
                ai.score = score
                w = ai.final_wager(others)
                self.assertTrue(0 <= w <= score, (diff.key, score, w))

    def test_shark_final_strategy(self):
        ai = AIPlayer("t", difficulty=HARD, rng=random.Random(0))
        ai.score = 10000
        self.assertEqual(ai.final_wager([4000, 1000]), 1999)   # locked: keep > 2x rival
        ai.score = 6000
        self.assertEqual(ai.final_wager([5000, 1000]), 4001)   # cover the double-up


if __name__ == "__main__":
    unittest.main()
