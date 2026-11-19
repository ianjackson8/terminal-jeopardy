"""Game flow: menus, a full three-round game vs two AIs, and practice mode."""
from __future__ import annotations

import random
import textwrap
import time

from .ai import DIFFICULTIES, AIPlayer, Difficulty, Player, make_opponents
from .clues import Board, Category, Clue, FinalClue, build_game, load_bank, make_category
from .matching import is_correct
from .stats import GameLog, career, category_table, load_stats, record_game, save_stats
from .screen import (
    ACCENT, BAD, BAD_B, BOARD, CURSOR, DIM_B, DOWN, ENTER, ESC, GOLD, GOOD, GOOD_B,
    LEFT, RIGHT, UP, VALUE, Screen, money,
)

TITLE = "TERMINAL JEOPARDY"
ANSWER_TIME = 10.0
DD_TIME = 15.0
FINAL_TIME = 30.0
PRACTICE_TIME = 15.0

LOGO = [
    "╔╦╗╔═╗╦═╗╔╦╗╦╔╗╔╔═╗╦      ╦╔═╗╔═╗╔═╗╔═╗╦═╗╔╦╗╦ ╦",
    " ║ ║╣ ╠╦╝║║║║║║║╠═╣║      ║║╣ ║ ║╠═╝╠═╣╠╦╝ ║║╚╦╝",
    " ╩ ╚═╝╩╚═╩ ╩╩╝╚╝╩ ╩╩═╝   ╚╝╚═╝╚═╝╩  ╩ ╩╩╚══╩╝ ╩",
]


class QuitGame(Exception):
    pass


class App:
    def __init__(self, scr):
        self.s = Screen(scr)
        self.stats = load_stats()
        self.rng = random.Random()
        self._scroll_max = 0

    # ======================================================================
    # Menus
    # ======================================================================
    def header(self, s: Screen) -> int:
        _, w = s.size
        if w >= len(LOGO[0]) + 2:
            lw = max(len(line) for line in LOGO)
            for i, line in enumerate(LOGO):
                s.put(1 + i, (w - lw) // 2, line, s.a(GOLD, True))
            y = 1 + len(LOGO)
        else:
            s.center(1, TITLE, s.a(GOLD, True))
            y = 2
        s.center(y, "a terminal quiz show  ·  you vs. two AIs", s.a(ACCENT))
        rec = self.record_line()
        if rec:
            s.center(y + 1, rec, s.a())
        return y + 3

    def record_line(self) -> str:
        games = self.stats.get("games", {})
        parts = [
            f"{d.label}: {games[d.key]['wins']}-{games[d.key]['played'] - games[d.key]['wins']}"
            for d in DIFFICULTIES if d.key in games
        ]
        return ("Record (W-L)  " + "   ".join(parts)) if parts else ""

    def run(self) -> None:
        options = [
            ("Play a full game", "Three rounds against two AI contestants: Round 1, the Double Round, and the Final Round."),
            ("Practice", "Untimed (or timed) drills with instant feedback. Pick a category or mix it up."),
            ("Stats", "Win streaks, winnings, accuracy, categories and game history."),
            ("How to play", "Rules, controls and answer tips."),
            ("Quit", ""),
        ]
        sel = 0
        while True:
            choice = self.s.menu("MAIN MENU", options, sel, header=self.header,
                                 footer="↑/↓ move · Enter select · q quit")
            if choice is None or choice == 4:
                return
            sel = choice
            if choice == 0:
                diff = self.pick_difficulty()
                if diff:
                    try:
                        self.play_game(diff)
                    except QuitGame:
                        pass
            elif choice == 1:
                self.practice_menu()
            elif choice == 2:
                self.stats_page()
            elif choice == 3:
                self.how_to_play()

    def pick_difficulty(self) -> Difficulty | None:
        opts = [(d.label, d.description) for d in DIFFICULTIES]
        i = self.s.menu("CHOOSE YOUR OPPONENTS", opts, 1, header=self.header)
        return None if i is None else DIFFICULTIES[i]

    def how_to_play(self) -> None:
        text = [
            ("THE GAME", GOLD),
            ("Round 1 ($200-$1,000) and the Double Round ($400-$2,000) each have 6 categories.", 0),
            ("Then a Final Round: wager any amount of your score on one last clue.", 0),
            ("", 0),
            ("BUZZING", GOLD),
            ("The clue is read first. When 'BUZZERS OPEN' appears, press SPACE.", 0),
            ("Buzz too early and you're locked out for half a second.", 0),
            (f"You then have {ANSWER_TIME:.0f}s to type a response. Wrong answers cost the clue's value,", 0),
            ("and the other players can then buzz in on the rebound.", 0),
            ("", 0),
            ("DAILY DOUBLES", GOLD),
            ("1 hidden in Round 1, 2 in the Double Round. Only the picker plays; wager up to", 0),
            ("your score (or the round's top value if that's higher).", 0),
            ("", 0),
            ("ANSWERS", GOLD),
            ("No need for 'What is...'. Spelling is forgiven a little; last names usually work.", 0),
            ("If the checker gets it wrong, press O on the result screen to override.", 0),
            ("", 0),
            ("CONTROLS", GOLD),
            ("Arrows / hjkl move · Enter choose · Space buzz · Esc quit to menu", 0),
        ]

        def draw():
            h, w = self.s.size
            self.s.fill()
            self.s.center(0, "HOW TO PLAY", self.s.a(GOLD, True))
            for i, (line, pair) in enumerate(text):
                self.s.center(2 + i, line, self.s.a(pair, bool(pair)))
            self.s.center(h - 1, "Press any key", self.s.a(ACCENT))

        self.s.wait_key(draw)

    # ======================================================================
    # Board rendering
    # ======================================================================
    def draw_scores(self, y: int, players: list[Player], control: Player | None = None,
                    on_blue: bool = False) -> None:
        _, w = self.s.size
        slot = w // len(players)
        for i, p in enumerate(players):
            cx = i * slot + slot // 2
            name = ("▶ " if p is control else "") + p.name
            npair = VALUE if on_blue else GOLD
            self.s.put(y, cx - len(name) // 2, name, self.s.a(npair if p.is_human else (BOARD if on_blue else 0), True))
            sc = money(p.score)
            if p.score < 0:
                pair = BAD_B if on_blue else BAD
            else:
                pair = BOARD if on_blue else 0
            self.s.put(y + 1, cx - len(sc) // 2, sc, self.s.a(pair, True))

    def draw_board(self, board: Board, players: list[Player], control: Player | None,
                   cursor: tuple[int, int] | None = None, msg: str = "", msg_pair: int = ACCENT) -> None:
        s = self.s
        h, w = s.size
        s.fill()
        title = "ROUND 1" if board.round_no == 1 else "DOUBLE ROUND"
        s.center(0, f"{TITLE}  ·  {title}", s.a(GOLD, True))
        ncol = len(board.categories)
        cell_w = min(20, (w - 1) // ncol - 1)
        total = ncol * (cell_w + 1) - 1
        x0 = (w - total) // 2
        header_h = 3
        cell_h = max(1, min(3, (h - 7 - header_h - 1 - 4) // 5))
        by = 2
        for c, cat in enumerate(board.categories):
            x = x0 + c * (cell_w + 1)
            for dy in range(header_h):
                s.put(by + dy, x, " " * cell_w, s.a(BOARD))
            lines = textwrap.wrap(cat.name, cell_w)[:header_h]
            off = (header_h - len(lines)) // 2
            for i, line in enumerate(lines):
                s.put(by + off + i, x + (cell_w - len(line)) // 2, line, s.a(BOARD, True))
            for r, clue in enumerate(cat.clues):
                y = by + header_h + 1 + r * (cell_h + 1)
                is_cur = cursor == (c, r)
                pair = CURSOR if is_cur else (VALUE if not clue.used else BOARD)
                for dy in range(cell_h):
                    s.put(y + dy, x, " " * cell_w, s.a(pair))
                if not clue.used:
                    txt = money(clue.value)
                    s.put(y + (cell_h - 1) // 2, x + (cell_w - len(txt)) // 2, txt, s.a(pair, True))
        self.draw_scores(h - 3, players, control)
        if msg:
            s.center(h - 1, msg, s.a(msg_pair, True))

    def draw_clue(self, header: str, text: str, lines: list[tuple[str, int]] = (),
                  frac: float | None = None, players: list[Player] | None = None,
                  control: Player | None = None, big_pair: int = BOARD) -> None:
        s = self.s
        h, w = s.size
        s.fill(BOARD)
        s.center(1, header, s.a(VALUE, True))
        width = min(w - 8, 60)
        body = textwrap.wrap(text.upper(), width)
        footer_h = len(lines) + (3 if players else 0) + (2 if frac is not None else 0)
        area_top, area_bot = 3, h - footer_h - 2
        y = max(area_top, area_top + (area_bot - area_top - len(body)) // 2)
        for i, line in enumerate(body):
            s.center(y + i, line, s.a(big_pair, True))
        y = h - footer_h - 1
        for text_line, pair in lines:
            s.center(y, text_line, s.a(pair or BOARD, True))
            y += 1
        if frac is not None:
            s.bar(y + 1, frac)
            y += 2
        if players:
            self.draw_scores(h - 2, players, control, on_blue=True)

    # ======================================================================
    # Full game
    # ======================================================================
    def play_game(self, diff: Difficulty) -> None:
        r1, r2, final = build_game(self.rng)
        human = Player("You", is_human=True)
        players: list[Player] = [human, *make_opponents(diff, self.rng)]
        self.players = players
        self.log = GameLog()
        control: Player = human

        self.intro(diff)
        for board in (r1, r2):
            if board.round_no == 2:
                control = min(players, key=lambda p: p.score)
            self.round_intro(board, control)
            control = self.play_round(board, control)
        self.final_round(final)
        self.game_over(diff)

    def intro(self, diff: Difficulty) -> None:
        ais = self.players[1:]

        def draw():
            h, _ = self.s.size
            self.s.fill(BOARD)
            self.s.center(h // 2 - 4, "TONIGHT'S CONTESTANTS", self.s.a(VALUE, True))
            self.s.center(h // 2 - 2, f"{ais[0].name}  ·  {ais[1].name}  ·  and YOU", self.s.a(BOARD, True))
            self.s.center(h // 2, f"Difficulty: {diff.label}", self.s.a(VALUE, True))
            self.s.wrapped(h // 2 + 2, diff.description, 60, self.s.a(DIM_B))
            self.s.center(h - 2, "Press any key to begin", self.s.a(BOARD))

        self.s.wait_key(draw)

    def round_intro(self, board: Board, control: Player) -> None:
        name = "ROUND 1" if board.round_no == 1 else "THE DOUBLE ROUND"
        dds = "one Daily Double" if board.round_no == 1 else "two Daily Doubles"
        lo, hi = board.values[0], board.values[-1]

        def draw():
            h, _ = self.s.size
            self.s.fill(BOARD)
            self.s.center(h // 2 - 5, name, self.s.a(VALUE, True))
            self.s.center(h // 2 - 4, f"{money(lo)} - {money(hi)} · {dds} hidden on the board", self.s.a(DIM_B))
            for i, cat in enumerate(board.categories):
                self.s.center(h // 2 - 2 + i, cat.name, self.s.a(BOARD, True))
            who = "You have" if control.is_human else f"{control.name} has"
            self.s.center(h // 2 + 5, f"{who} control of the board", self.s.a(VALUE))
            self.draw_scores(h - 3, self.players, control, on_blue=True)
            self.s.center(h - 1, "Press any key", self.s.a(BOARD))

        self.s.wait_key(draw)

    def play_round(self, board: Board, control: Player) -> Player:
        cursor = board.available()[0]
        while not board.done:
            if control.is_human:
                col, row = self.human_pick(board, control, cursor)
                cursor = (col, row)
            else:
                col, row = control.pick_clue(board)
                cat = board.categories[col]
                self.s.hold(1.6, lambda: self.draw_board(
                    board, self.players, control, (col, row),
                    f"{control.name}: \"{cat.name.title()} for {money(board.values[row])}\""))
            clue = board.clue(col, row)
            clue.used = True
            cat = board.categories[col]
            if clue.daily_double:
                control = self.daily_double(clue, board, cat, control)
            else:
                control = self.play_clue(clue, cat, control)
            avail = board.available()
            if avail and cursor not in avail:
                cursor = min(avail, key=lambda p: (abs(p[0] - cursor[0]) + abs(p[1] - cursor[1])))
        return control

    def human_pick(self, board: Board, control: Player, cursor: tuple[int, int]) -> tuple[int, int]:
        c, r = cursor
        msg = "Your pick!  Arrows/hjkl move · Enter select · Esc quit"
        while True:
            if not self.s.too_small():
                self.draw_board(board, self.players, control, (c, r), msg)
                self.s.refresh()
            k = self.s.read(200)
            if k is None:
                continue
            if k in UP:
                r = (r - 1) % 5
            elif k in DOWN:
                r = (r + 1) % 5
            elif k in LEFT:
                c = (c - 1) % len(board.categories)
            elif k in RIGHT:
                c = (c + 1) % len(board.categories)
            elif k in ENTER or k == " ":
                if board.clue(c, r).used:
                    msg = "That clue's already been played - pick another."
                else:
                    return c, r
            elif k == ESC or k == "q":
                if self.confirm_quit():
                    raise QuitGame

    def confirm_quit(self) -> bool:
        return self.confirm("Quit this game and return to the menu? (y/n)")

    # ---- a regular clue ---------------------------------------------------------
    def buzz_phase(self, header: str, clue: Clue, human_ok: bool, ai_times: dict[AIPlayer, float],
                   open_delay: float, window: float, lines: list[tuple[str, int]]) -> Player | None:
        human = self.players[0]
        self.s.flush()
        start = time.monotonic()
        open_at = start + open_delay
        close_at = open_at + window
        lock_until = 0.0
        first_ai = min(((open_at + t, ai) for ai, t in ai_times.items()), key=lambda x: x[0], default=None)
        while True:
            k = self.s.read(25)
            now = time.monotonic()
            if k == " " and human_ok:
                if now < open_at:
                    lock_until = now + 0.5
                elif now >= lock_until:
                    if first_ai and first_ai[0] < now:
                        return first_ai[1]
                    return human
            if first_ai and first_ai[0] <= now:
                return first_ai[1]
            if now >= close_at:
                return None
            status = list(lines)
            if now < lock_until:
                status.append(("TOO EARLY - locked out!", BAD_B))
            elif now < open_at:
                status.append(("· · ·", DIM_B))
            elif human_ok:
                status.append(("▶ BUZZERS OPEN - press SPACE! ◀", VALUE))
            else:
                status.append(("Buzzers open for the others...", DIM_B))
            frac = 1.0 if now < open_at else max(0.0, (close_at - now) / window)
            if not self.s.too_small():
                self.draw_clue(header, clue.text, status, frac, self.players)
                self.s.refresh()

    def play_clue(self, clue: Clue, cat: Category, control: Player) -> Player:
        human = self.players[0]
        ais = [p for p in self.players if not p.is_human]
        header = f"{clue.category}  ·  {money(clue.value)}"
        decisions = {ai: ai.decide(clue) for ai in ais}
        pool = [c.answer for c in cat.clues if c is not clue]
        attempted: set[Player] = set()
        events: list[list] = []
        words = len(clue.text.split())
        open_delay = max(1.2, min(4.5, 0.17 * words))
        window = 5.0
        while True:
            ai_times = {ai: d[2] for ai, d in decisions.items() if d[0] and ai not in attempted}
            human_ok = human not in attempted
            if not ai_times and not human_ok:
                break
            lines = self.event_lines(events)
            winner = self.buzz_phase(header, clue, human_ok, ai_times, open_delay, window, lines)
            if winner is None:
                break
            attempted.add(winner)
            if winner.is_human:
                resp, _ = self.s.text_input(
                    lambda buf, frac: self.draw_clue(
                        header, clue.text, lines + [("You buzzed in!", VALUE), (f"Your response: {buf}▌", BOARD)],
                        frac, self.players),
                    limit=ANSWER_TIME)
                resp = (resp or "").strip()
                correct = is_correct(resp, clue.all_answers)
            else:
                self.s.hold(0.8, lambda: self.draw_clue(
                    header, clue.text, lines + [(f"{winner.name} buzzes in!", VALUE)], None, self.players),
                    skippable=False)
                correct = decisions[winner][1]
                given = {e[1] for e in events}
                resp = clue.answer if correct else winner.wrong_guess(clue, [p for p in pool if p not in given])
                self.s.hold(1.4, lambda: self.draw_clue(
                    header, clue.text, lines + [(f"{winner.name}: \"{resp}\"", BOARD)], None, self.players),
                    skippable=False)
            delta = clue.value if correct else -clue.value
            winner.score += delta
            events.append([winner, resp, correct, delta])
            if correct:
                control = winner
                break
            open_delay, window = 0.6, 4.0
        control = self.show_result(header, clue.text, clue.answer, events, control)
        for p, _, correct, _ in events:
            if p is human:
                self.log.answer(correct, clue.category)
        return control

    def event_lines(self, events: list[list]) -> list[tuple[str, int]]:
        out = []
        for p, resp, correct, delta in events:
            mark = "✓" if correct else "✗"
            shown = resp if resp else "(no response)"
            out.append((f"{p.name}: {shown}  {mark} {'+' if delta >= 0 else ''}{money(delta)}",
                        GOOD_B if correct else BAD_B))
        return out

    def show_result(self, header: str, text: str, answer: str, events: list[list],
                    control: Player) -> Player:
        """Show outcome; allow human to override a wrong judgement. Returns control."""
        human = self.players[0]
        overridden = False
        while True:
            lines = self.event_lines(events) or [("Nobody buzzed in.", DIM_B)]
            lines = lines + [("", 0), (f"Correct response: {answer}", VALUE)]
            can_override = not overridden and any(e[0] is human and not e[2] for e in events)
            hint = "Enter continue" + ("  ·  O override (I was right)" if can_override else "")
            lines.append((hint, DIM_B))
            k = self.s.wait_key(lambda: self.draw_clue(header, text, lines, None, self.players, control))
            if k in ("o", "O") and can_override:
                for e in events:
                    if e[0] is human and not e[2]:
                        human.score += -2 * e[3]
                        e[2], e[3] = True, -e[3]
                control = human
                overridden = True
            elif k in ENTER or k == " ":
                return control
            elif k == ESC:
                if self.confirm_quit():
                    raise QuitGame

    # ---- Daily Double --------------------------------------------------------------
    def daily_double(self, clue: Clue, board: Board, cat: Category, control: Player) -> Player:
        s = self.s
        for i in range(8):
            def flash(i=i):
                h, _ = s.size
                s.fill(CURSOR if i % 2 == 0 else BOARD)
                s.center(h // 2 - 1, "★  D A I L Y   D O U B L E  ★", s.a(CURSOR if i % 2 == 0 else VALUE, True))
            s.hold(0.18, flash, skippable=False)
        header = f"{clue.category}  ·  DAILY DOUBLE"
        max_bet = max(control.score, board.values[-1])
        others = [p.score for p in self.players if p is not control]
        if control.is_human:
            msg = f"Your score: {money(control.score)}.  Wager $5 - {money(max_bet)}"
            while True:
                buf, _ = s.text_input(lambda b, f: self.draw_clue(
                    header, f"Category: {clue.category}", [(msg, VALUE), (f"Wager: ${b}▌", BOARD)],
                    None, self.players, control), numeric=True, maxlen=7)
                if buf and 5 <= int(buf) <= max_bet:
                    wager = int(buf)
                    break
                msg = f"Enter a whole number from $5 to {money(max_bet)}"
        else:
            wager = control.daily_double_wager(clue, board.values[-1], others)
            s.hold(2.0, lambda: self.draw_clue(
                header, f"Category: {clue.category}",
                [(f"{control.name} wagers {money(wager)}", VALUE)], None, self.players, control))
        if control.is_human:
            resp, _ = s.text_input(lambda b, f: self.draw_clue(
                header, clue.text, [(f"Wager {money(wager)}", DIM_B), (f"Your response: {b}▌", BOARD)],
                f, self.players, control), limit=DD_TIME)
            resp = (resp or "").strip()
            correct = is_correct(resp, clue.all_answers)
        else:
            correct = control.answer_correct(clue.category, clue.tier)
            pool = [c.answer for c in cat.clues if c is not clue]
            resp = clue.answer if correct else control.wrong_guess(clue, pool)
            s.hold(2.0, lambda: self.draw_clue(
                header, clue.text, [(f"{control.name} is thinking...", DIM_B)], None, self.players, control),
                skippable=False)
            s.hold(1.4, lambda: self.draw_clue(
                header, clue.text, [(f"{control.name}: \"{resp}\"", BOARD)], None, self.players, control),
                skippable=False)
        delta = wager if correct else -wager
        control.score += delta
        picker = control
        event = [control, resp, correct, delta]
        self.show_result(header, clue.text, clue.answer, [event], control)
        if picker.is_human:
            self.log.answer(event[2], clue.category)
            self.log.dd_played += 1
            self.log.dd_correct += int(event[2])
            self.log.dd_net += event[3]
        return picker

    # ---- Final Round ------------------------------------------------------------------
    def final_round(self, final: FinalClue) -> None:
        s = self.s
        human = self.players[0]
        eligible = [p for p in self.players if p.score > 0]
        header = "FINAL ROUND"

        def cat_screen(extra: list[tuple[str, int]]):
            self.draw_clue(header, f"Category: {final.category}", extra, None, self.players)

        if not eligible:
            s.wait_key(lambda: cat_screen([("Nobody finished in the black - no Final Round!", VALUE),
                                           ("Press any key", DIM_B)]))
            return
        note = [] if human in eligible else [("You finished at $0 or below and sit this one out.", BAD_B)]
        s.wait_key(lambda: cat_screen(note + [("Players with positive scores will wager.", BOARD),
                                              ("Press any key", DIM_B)]))

        wagers: dict[Player, int] = {}
        for p in eligible:
            if not p.is_human:
                wagers[p] = p.final_wager([o.score for o in self.players if o is not p])
        if human in eligible:
            msg = f"Your score: {money(human.score)}.  Wager $0 - {money(human.score)}"
            while True:
                buf, _ = s.text_input(lambda b, f: cat_screen([(msg, VALUE), (f"Wager: ${b}▌", BOARD)]),
                                      numeric=True, maxlen=7)
                if buf and 0 <= int(buf) <= human.score:
                    wagers[human] = int(buf)
                    break
                msg = f"Enter a whole number from $0 to {money(human.score)}"

        responses: dict[Player, str] = {}
        if human in eligible:
            resp, _ = s.text_input(lambda b, f: self.draw_clue(
                f"FINAL ROUND  ·  {final.category}", final.text,
                [(f"Your response: {b}▌", BOARD)], f, self.players), limit=FINAL_TIME)
            responses[human] = (resp or "").strip()
        else:
            s.hold(12, lambda: self.draw_clue(
                f"FINAL ROUND  ·  {final.category}", final.text,
                [("The others are writing... (Enter to skip)", DIM_B)], None, self.players))

        _, finals = load_bank()
        pool = [f["answer"] for f in finals if f["answer"] != final.answer]
        correct_map: dict[Player, bool] = {}
        for p in eligible:
            if p.is_human:
                correct_map[p] = is_correct(responses[p], final.all_answers)
            else:
                ok = p.answer_correct(final.category, 5)
                correct_map[p] = ok
                responses[p] = final.answer if ok else self.rng.choice(pool + ["(blank)"])

        # Reveal from lowest to highest score.
        for p in sorted(eligible, key=lambda p: p.score):
            who = "Your" if p.is_human else f"{p.name}'s"
            resp = responses[p] or "(no response)"
            s.wait_key(lambda: self.draw_clue(
                header, final.text, [(f"{who} response:", BOARD), (f"\"{resp}\"", VALUE),
                                     ("Press any key", DIM_B)], None, self.players))
            while True:
                ok = correct_map[p]
                delta = wagers[p] if ok else -wagers[p]
                verdict = ("CORRECT" if ok else "INCORRECT") + f"  ·  wagered {money(wagers[p])}"
                p.score += delta
                can_override = p.is_human and not ok
                tail = "Enter continue" + ("  ·  O override (I was right)" if can_override else "")
                k = s.wait_key(lambda: self.draw_clue(
                    header, final.text,
                    [(f"{who} response: \"{resp}\"", BOARD), (verdict, GOOD_B if ok else BAD_B),
                     (f"Correct response: {final.answer}", VALUE), (tail, DIM_B)], None, self.players))
                if k in ("o", "O") and can_override:
                    p.score -= delta  # undo and re-apply as correct
                    correct_map[p] = True
                    continue
                break
        if human in eligible:
            self.log.final_played = True
            self.log.final_correct = correct_map[human]

    def game_over(self, diff: Difficulty) -> None:
        human = self.players[0]
        top = max(p.score for p in self.players)
        winners = [p for p in self.players if p.score == top]
        won = human in winners and top > 0
        place = 1 + sum(p.score > human.score for p in self.players)
        c = record_game(self.stats, diff.key, human.score, won, place, self.log)
        g = self.stats["games"][diff.key]
        save_stats(self.stats)
        if won:
            streak_line = f"Win streak: {c['current_streak']} · {money(c['current_streak_winnings'])} won"
            if c["current_streak"] == c["best_streak"] and c["current_streak"] > 1:
                streak_line += "  ·  NEW RECORD!"
        else:
            streak_line = f"Longest win streak: {c['best_streak']} · {money(c['best_streak_winnings'])}"

        if top <= 0:
            headline = "Nobody wins tonight!"
        elif won and len(winners) > 1:
            headline = "IT'S A TIE - you're a co-champion!"
        elif won:
            headline = "YOU WIN!"
        else:
            headline = f"{' & '.join(p.name for p in winners)} wins."

        def draw():
            h, _ = self.s.size
            self.s.fill(BOARD)
            self.s.center(h // 2 - 5, "FINAL SCORES", self.s.a(VALUE, True))
            for i, p in enumerate(sorted(self.players, key=lambda p: -p.score)):
                pair = VALUE if p.is_human else BOARD
                self.s.center(h // 2 - 3 + i, f"{p.name:<8} {money(p.score):>10}", self.s.a(pair, True))
            self.s.center(h // 2 + 1, headline, self.s.a(GOOD_B if won else VALUE, True))
            self.s.center(h // 2 + 3, streak_line, self.s.a(VALUE if won else DIM_B))
            self.s.center(h // 2 + 4, f"Your best on {diff.label}: {money(g['best'])}   "
                                      f"Record: {g['wins']}-{g['played'] - g['wins']}", self.s.a(DIM_B))
            self.s.center(h - 2, "Press Enter to return to the menu", self.s.a(BOARD))

        while self.s.wait_key(draw) not in ENTER:
            pass

    # ======================================================================
    # Stats page
    # ======================================================================
    STAT_TABS = ["Overview", "Categories", "History"]

    def stats_page(self) -> None:
        tab, scroll = 0, 0
        while True:
            k = self.s.wait_key(lambda: self.draw_stats(tab, scroll))
            if k in LEFT:
                tab, scroll = (tab - 1) % len(self.STAT_TABS), 0
            elif k in RIGHT or k == "\t":
                tab, scroll = (tab + 1) % len(self.STAT_TABS), 0
            elif k in UP:
                scroll = max(0, scroll - 1)
            elif k in DOWN:
                scroll = min(scroll + 1, self._scroll_max)
            elif k in ("r", "R"):
                if self.confirm("Reset ALL stats? This can't be undone. (y/n)"):
                    self.stats = {}
                    save_stats(self.stats)
            elif k in ENTER or k in (ESC, "q"):
                return

    def confirm(self, question: str) -> bool:
        def draw():
            h, _ = self.s.size
            self.s.fill()
            self.s.center(h // 2, question, self.s.a(GOLD, True))
        while True:
            k = self.s.wait_key(draw)
            if k in ("y", "Y"):
                return True
            if k in ("n", "N", ESC) or k in ENTER:
                return False

    def draw_stats(self, tab: int, scroll: int) -> None:
        s = self.s
        h, w = s.size
        s.fill()
        s.center(0, "YOUR STATS", s.a(GOLD, True))
        labels = [f" {t} " for t in self.STAT_TABS]
        x = (w - sum(len(l) for l in labels) - 2 * (len(labels) - 1)) // 2
        for i, label in enumerate(labels):
            s.put(1, x, label, s.a(CURSOR, True) if i == tab else s.a(ACCENT))
            x += len(label) + 2
        c = career(self.stats)
        self._scroll_max = 0
        if tab == 0:
            self.draw_stats_overview(c)
        elif tab == 1:
            self.draw_stats_categories(scroll)
        else:
            self.draw_stats_history(scroll)
        s.center(h - 1, "←/→ switch tab · ↑/↓ scroll · R reset · Esc back", s.a(ACCENT))

    @staticmethod
    def _pct(n: int, d: int) -> str:
        return f"{100 * n / d:.0f}%" if d else "-"

    def draw_stats_overview(self, c: dict) -> None:
        s = self.s
        h, w = s.size
        colw = 32
        lx = max(0, (w - 2 * colw - 6) // 2)
        rx = lx + colw + 6

        def section(x, y, title):
            s.put(y, x, title, s.a(GOLD, True))

        def row(x, y, label, value, pair=0, bold=False):
            s.put(y, x, label, s.a())
            s.put(y, x + colw - len(value), value, s.a(pair, bold))

        def signed(n):
            return ("+" if n > 0 else "") + money(n)

        played = c["played"]
        avg = c["total_score"] // played if played else 0
        hi = money(c["highest_score"]) if c["highest_score"] is not None else "-"
        lo = money(c["lowest_score"]) if c["lowest_score"] is not None else "-"

        y = 3
        section(lx, y, "CHAMPION'S RECORD")
        row(lx, y + 1, "Longest win streak", f"{c['best_streak']} game{'s' * (c['best_streak'] != 1)}", GOLD, True)
        row(lx, y + 2, "  won during it", money(c["best_streak_winnings"]), GOLD, True)
        row(lx, y + 3, "Current win streak", f"{c['current_streak']} game{'s' * (c['current_streak'] != 1)}")
        row(lx, y + 4, "  won during it", money(c["current_streak_winnings"]))
        section(lx, y + 6, "CAREER")
        row(lx, y + 7, "Games played", str(played))
        row(lx, y + 8, "Wins", f"{c['wins']} ({self._pct(c['wins'], played)})")
        row(lx, y + 9, "Total winnings", money(c["total_winnings"]), GOOD, True)
        row(lx, y + 10, "Average final score", money(avg), BAD if avg < 0 else 0)
        row(lx, y + 11, "Highest final score", hi)
        row(lx, y + 12, "Lowest final score", lo,
            BAD if c["lowest_score"] is not None and c["lowest_score"] < 0 else 0)

        section(rx, y, "ON THE BUZZER")
        row(rx, y + 1, "Responses", str(c["responses"]))
        row(rx, y + 2, "Accuracy", self._pct(c["correct"], c["responses"]))
        row(rx, y + 3, "Best run in a game", f"{c['best_answer_streak']} in a row")
        row(rx, y + 4, "Daily Doubles", f"{c['dd_correct']}/{c['dd_played']}")
        row(rx, y + 5, "  net from wagers", signed(c["dd_net"]),
            GOOD if c["dd_net"] > 0 else (BAD if c["dd_net"] < 0 else 0))
        row(rx, y + 6, "Final Round", f"{c['final_correct']}/{c['final_played']}")
        p = self.stats.get("practice", {})
        section(rx, y + 8, "PRACTICE")
        row(rx, y + 9, "Answered", str(p.get("answered", 0)))
        row(rx, y + 10, "Accuracy", self._pct(p.get("correct", 0), p.get("answered", 0)))
        row(rx, y + 11, "Best streak", str(p.get("best_streak", 0)))

        games = self.stats.get("games", {})
        lines = []
        for d in DIFFICULTIES:
            g = games.get(d.key)
            if g:
                rec = f"{g['wins']}-{g['played'] - g['wins']}"
                lines.append(f"{d.label:<8}{rec:>7} W-L    best {money(g.get('best', 0)):>9}"
                             f"    winnings {money(g.get('winnings', 0)):>10}")
        lines = lines or ["No games yet - go play one!"]
        if y + 14 + len(lines) < h - 1:
            section(lx, y + 14, "BY DIFFICULTY")
            for i, line in enumerate(lines):
                s.put(y + 15 + i, lx, line, s.a())

    def draw_stats_categories(self, scroll: int) -> None:
        s = self.s
        h, w = s.size
        rows = category_table(self.stats)
        if not rows:
            s.center(h // 2, "No category data yet. Play a game or some practice!", s.a(ACCENT))
            return
        tw = 58
        x = max(0, (w - tw) // 2)
        s.put(3, x, f"{'CATEGORY':<24}{'IN GAMES':>12}{'PRACTICE':>12}{'OVERALL':>10}", s.a(GOLD, True))
        room = h - 6
        self._scroll_max = max(0, len(rows) - room)
        scroll = min(scroll, self._scroll_max)
        for i, (cat, gc, gn, pc, pn) in enumerate(rows[scroll: scroll + room]):
            tot_c, tot_n = gc + pc, gn + pn
            frac = tot_c / tot_n if tot_n else 0
            pair = GOOD if frac >= 0.8 else (BAD if frac < 0.5 else 0)
            gtxt = f"{gc}/{gn}" if gn else "-"
            ptxt = f"{pc}/{pn}" if pn else "-"
            s.put(4 + i, x, f"{cat[:23]:<24}{gtxt:>12}{ptxt:>12}", s.a())
            s.put(4 + i, x + 48, f"{self._pct(tot_c, tot_n):>10}", s.a(pair, True))
        if len(rows) > room:
            s.center(h - 2, f"{scroll + 1}-{min(len(rows), scroll + room)} of {len(rows)}", s.a(ACCENT))

    def draw_stats_history(self, scroll: int) -> None:
        s = self.s
        h, w = s.size
        hist = self.stats.get("history", [])
        if not hist:
            s.center(h // 2, "No games played yet.", s.a(ACCENT))
            return
        labels = {d.key: d.label for d in DIFFICULTIES}
        places = {1: "WIN", 2: "2nd", 3: "3rd"}
        tw = 61
        x = max(0, (w - tw) // 2)
        s.put(3, x, f"{'DATE':<12}{'LEVEL':<9}{'SCORE':>12}{'RESULT':>9}{'ANSWERS':>11}{'ACC':>8}", s.a(GOLD, True))
        room = h - 6
        self._scroll_max = max(0, len(hist) - room)
        scroll = min(scroll, self._scroll_max)
        for i, g in enumerate(hist[scroll: scroll + room]):
            result = "WIN" if g["won"] else places.get(g["place"], "-")
            s.put(4 + i, x, f"{g['date']:<12}{labels.get(g['difficulty'], g['difficulty']):<9}"
                            f"{money(g['score']):>12}", s.a(BAD if g["score"] < 0 else 0))
            s.put(4 + i, x + 33, f"{result:>9}", s.a(GOOD if g["won"] else 0, g["won"]))
            s.put(4 + i, x + 42, f"{g['correct']}/{g['responses']}".rjust(11)
                                 + f"{self._pct(g['correct'], g['responses']):>8}", s.a())
        if len(hist) > room:
            s.center(h - 2, f"{scroll + 1}-{min(len(hist), scroll + room)} of {len(hist)}", s.a(ACCENT))

    # ======================================================================
    # Practice mode
    # ======================================================================
    def practice_menu(self) -> None:
        timed = False
        sel = 0
        while True:
            opts = [
                ("Random mix", "Every clue in the bank, shuffled. Go as long as you like."),
                ("Pick a category", "Work through one category from $200 to $1,000."),
                ("Weak spots", "Categories you've missed the most in past practice come first."),
                ("Final Round clues", "The tougher, Final-style clues."),
                (f"Timer: {'ON (15s)' if timed else 'OFF'}", "Toggle a 15-second answer clock."),
                ("Back", ""),
            ]
            choice = self.s.menu("PRACTICE", opts, sel, header=self.header)
            if choice is None or choice == 5:
                return
            sel = choice
            cats, finals = load_bank()
            if choice == 0:
                clues = [c for raw in cats for c in make_category(raw, 1).clues]
                self.rng.shuffle(clues)
                self.practice_session(clues, "RANDOM MIX", timed)
            elif choice == 1:
                names = sorted(c["name"] for c in cats)
                i = self.s.menu("PICK A CATEGORY", [(n, "") for n in names], 0)
                if i is not None:
                    raw = next(c for c in cats if c["name"] == names[i])
                    self.practice_session(make_category(raw, 1).clues, names[i], timed)
            elif choice == 2:
                hist = self.stats.get("practice", {}).get("by_category", {})

                def miss_rate(raw):
                    c, n = hist.get(raw["name"], [0, 0])
                    return -((n - c) / n if n else 0.5)
                ordered = sorted(cats, key=miss_rate)
                clues = []
                for raw in ordered[:6]:
                    clues += make_category(raw, 1).clues
                self.practice_session(clues, "WEAK SPOTS", timed)
            elif choice == 3:
                clues = [Clue(f["category"], f["clue"], f["answer"], list(f.get("accept", [])), tier=5)
                         for f in finals]
                self.rng.shuffle(clues)
                self.practice_session(clues, "FINAL ROUND CLUES", timed)
            elif choice == 4:
                timed = not timed

    def practice_session(self, clues: list[Clue], title: str, timed: bool) -> None:
        s = self.s
        answered = correct_n = streak = best = 0
        by_cat: dict[str, list[int]] = {}
        missed: list[Clue] = []
        for i, clue in enumerate(clues):
            label = money(clue.value) if clue.value else "FINAL"
            header = f"PRACTICE  ·  {clue.category}  ·  {label}"
            status = f"{title}  ·  Clue {i + 1}/{len(clues)}  ·  Score {correct_n}/{answered}  ·  Streak {streak}"
            resp, _ = s.text_input(lambda b, f: self.draw_clue(
                header, clue.text,
                [(status, DIM_B), ("", 0), (f"Your response: {b}▌", BOARD),
                 ("Enter submit (blank = pass)  ·  Esc finish", DIM_B)], f),
                limit=PRACTICE_TIME if timed else None)
            if resp is None:
                break
            resp = resp.strip()
            ok = bool(resp) and is_correct(resp, clue.all_answers)
            overridden = False
            while True:
                if ok:
                    verdict = ("✓ Correct!" + (" (override)" if overridden else ""), GOOD_B)
                elif resp:
                    verdict = (f"✗ \"{resp}\" is incorrect", BAD_B)
                else:
                    verdict = ("Passed", DIM_B)
                can_override = not ok and bool(resp)
                hint = "Enter next  ·  Esc finish" + ("  ·  O override" if can_override else "")
                k = s.wait_key(lambda: self.draw_clue(
                    header, clue.text,
                    [verdict, (f"Correct response: {clue.answer}", VALUE), ("", 0), (hint, DIM_B)]))
                if k in ("o", "O") and can_override:
                    ok, overridden = True, True
                    continue
                if k in ENTER or k == " " or k == ESC:
                    break
            answered += 1
            rec = by_cat.setdefault(clue.category, [0, 0])
            rec[1] += 1
            if ok:
                correct_n += 1
                rec[0] += 1
                streak += 1
                best = max(best, streak)
            else:
                streak = 0
                missed.append(clue)
            if k == ESC:
                break
        self.save_practice(answered, correct_n, best, by_cat)
        self.practice_summary(title, answered, correct_n, best, by_cat, missed)

    def save_practice(self, answered: int, correct: int, best: int, by_cat: dict) -> None:
        p = self.stats.setdefault("practice", {"answered": 0, "correct": 0, "best_streak": 0, "by_category": {}})
        p["answered"] += answered
        p["correct"] += correct
        p["best_streak"] = max(p.get("best_streak", 0), best)
        for cat, (c, n) in by_cat.items():
            tot = p["by_category"].setdefault(cat, [0, 0])
            tot[0] += c
            tot[1] += n
        save_stats(self.stats)

    def practice_summary(self, title, answered, correct, best, by_cat, missed) -> None:
        life = self.stats.get("practice", {})

        def draw():
            s = self.s
            h, w = s.size
            s.fill()
            s.center(0, f"PRACTICE SUMMARY  ·  {title}", s.a(GOLD, True))
            pct = f"{100 * correct / answered:.0f}%" if answered else "-"
            s.center(2, f"Correct {correct}/{answered} ({pct})   Best streak {best}", s.a(0, True))
            if life.get("answered"):
                lp = 100 * life["correct"] / life["answered"]
                s.center(3, f"Lifetime: {life['correct']}/{life['answered']} ({lp:.0f}%) · best streak {life['best_streak']}",
                         s.a(ACCENT))
            y = 5
            if by_cat:
                s.center(y, "BY CATEGORY", s.a(GOLD, True))
                y += 1
                for cat, (c, n) in sorted(by_cat.items(), key=lambda kv: kv[1][0] / kv[1][1])[:6]:
                    s.center(y, f"{cat:<22} {c}/{n}", s.a(GOOD if c == n else (BAD if c == 0 else 0)))
                    y += 1
            if missed:
                y += 1
                s.center(y, "REVIEW THESE", s.a(GOLD, True))
                y += 1
                room = h - y - 2
                for clue in missed[:max(0, room)]:
                    line = f"{clue.answer}  ←  {clue.text}"
                    s.center(y, line[: w - 4], s.a())
                    y += 1
            s.center(h - 1, "Press Enter", s.a(ACCENT))

        while self.s.wait_key(draw) not in ENTER:
            pass
