import unittest

from jeopardy.stats import HISTORY_LEN, GameLog, career, category_table, record_game


def log(responses=0, correct=0, best=0, **kw):
    g = GameLog(responses=responses, correct=correct, best_streak=best, **kw)
    return g


class StreakTests(unittest.TestCase):
    def test_win_streak_and_winnings(self):
        stats = {}
        record_game(stats, "medium", 10000, True, 1, log())
        record_game(stats, "hard", 15000, True, 1, log())
        c = record_game(stats, "easy", 5000, True, 1, log())
        self.assertEqual((c["current_streak"], c["current_streak_winnings"]), (3, 30000))
        self.assertEqual((c["best_streak"], c["best_streak_winnings"]), (3, 30000))

        c = record_game(stats, "hard", 8000, False, 2, log())
        self.assertEqual((c["current_streak"], c["current_streak_winnings"]), (0, 0))
        self.assertEqual((c["best_streak"], c["best_streak_winnings"]), (3, 30000))

        # A shorter streak never replaces the record, even with more money.
        record_game(stats, "hard", 90000, True, 1, log())
        c = record_game(stats, "hard", 1000, False, 3, log())
        self.assertEqual((c["best_streak"], c["best_streak_winnings"]), (3, 30000))
        self.assertEqual(c["total_winnings"], 10000 + 15000 + 5000 + 90000)
        self.assertEqual((c["played"], c["wins"]), (6, 4))
        self.assertEqual((c["highest_score"], c["lowest_score"]), (90000, 1000))

    def test_equal_length_streak_with_more_money_wins_tiebreak(self):
        stats = {}
        record_game(stats, "easy", 1000, True, 1, log())
        record_game(stats, "easy", 0, False, 2, log())
        c = record_game(stats, "easy", 5000, True, 1, log())
        self.assertEqual((c["best_streak"], c["best_streak_winnings"]), (1, 5000))

    def test_gameplay_totals_and_categories(self):
        stats = {}
        g = GameLog()
        for ok in (True, True, False, True, True, True):
            g.answer(ok, "SCIENCE")
        g.answer(False, "ART")
        g.dd_played, g.dd_correct, g.dd_net = 2, 1, 600
        g.final_played, g.final_correct = True, True
        c = record_game(stats, "medium", -400, False, 3, g)
        self.assertEqual((c["responses"], c["correct"], c["best_answer_streak"]), (7, 5, 3))
        self.assertEqual((c["dd_played"], c["dd_correct"], c["dd_net"]), (2, 1, 600))
        self.assertEqual((c["final_played"], c["final_correct"]), (1, 1))
        self.assertEqual(c["by_category"], {"SCIENCE": [5, 6], "ART": [0, 1]})
        self.assertEqual(c["lowest_score"], -400)

    def test_history_and_difficulty_records(self):
        stats = {}
        for i in range(HISTORY_LEN + 5):
            record_game(stats, "easy", i, True, 1, log())
        self.assertEqual(len(stats["history"]), HISTORY_LEN)
        self.assertEqual(stats["history"][0]["score"], HISTORY_LEN + 4)  # newest first
        self.assertEqual(stats["games"]["easy"]["played"], HISTORY_LEN + 5)

    def test_seeds_from_old_stats_format(self):
        stats = {"games": {"easy": {"played": 4, "wins": 3, "best": 9000}}}
        c = career(stats)
        self.assertEqual((c["played"], c["wins"]), (4, 3))

    def test_category_table_merges_practice(self):
        stats = {"practice": {"by_category": {"ART": [4, 5], "MUSIC": [0, 2]}}}
        g = GameLog()
        g.answer(True, "ART")
        record_game(stats, "easy", 100, True, 1, g)
        rows = {r[0]: r for r in category_table(stats)}
        self.assertEqual(rows["ART"], ("ART", 1, 1, 4, 5))
        self.assertEqual(category_table(stats)[-1][0], "MUSIC")


if __name__ == "__main__":
    unittest.main()
