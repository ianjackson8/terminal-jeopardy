import random
import unittest

from jeopardy.clues import build_game
from jeopardy.decoys import DecoyPool, classify
from jeopardy.matching import is_correct, normalize


class DecoyTests(unittest.TestCase):
    def test_decoys_never_leak_answers_in_play(self):
        for seed in range(25):
            rng = random.Random(seed)
            r1, r2, final = build_game(rng)
            clues = [c for b in (r1, r2) for cat in b.categories for c in cat.clues]
            in_play = [c.all_answers for c in clues] + [final.all_answers]
            in_play_norm = {normalize(a) for answers in in_play for a in answers}
            pool = DecoyPool(in_play, rng)
            targets = [(c.text, c.all_answers) for c in clues] + [(final.text, final.all_answers)]
            for text, answers in targets:
                for _ in range(5):
                    guess = pool.pick(text, answers)
                    self.assertFalse(is_correct(guess, answers), (text, guess))
                    if not guess.isdigit():
                        self.assertNotIn(normalize(guess), in_play_norm, (text, guess))

    def test_decoys_match_the_kind_of_answer(self):
        rng = random.Random(1)
        r1, r2, final = build_game(rng)
        in_play = [c.all_answers for b in (r1, r2) for cat in b.categories for c in cat.clues]
        pool = DecoyPool(in_play + [final.all_answers], rng)
        year = pool.pick("The Berlin Wall fell in this year", ["1989"])
        self.assertTrue(year.isdigit() and year != "1989" and abs(int(year) - 1989) <= 15)
        num = pool.pick("The number of keys on a standard piano", ["88"])
        self.assertTrue(num.isdigit() and num != "88")
        self.assertEqual(classify("He wrote \"The Raven\"", "Edgar Allan Poe"), "person")
        self.assertEqual(classify("Kathmandu is the capital of this Himalayan nation", "Nepal"), "country")
        self.assertEqual(classify("This river flows through London", "Thames"), "river")

    def test_avoid_list_is_respected(self):
        rng = random.Random(2)
        pool = DecoyPool([], rng)
        first = pool.pick("He wrote \"The Raven\"", ["Edgar Allan Poe"])
        for _ in range(30):
            self.assertNotEqual(pool.pick("He wrote \"The Raven\"", ["Edgar Allan Poe"], {first}), first)


if __name__ == "__main__":
    unittest.main()
