# Terminal Jeopardy

A quiz-show game for the terminal. Play a full game against two AI contestants, or drill in practice mode.
It's pure Python standard library (`curses`), so there's nothing to install.

## Run

```sh
python3 -m jeopardy
# or install the `jeopardy` command:
uv tool install .      # or: pip install .
```

You need a terminal of at least 70x22. The board gets bigger when the window is bigger.

## Modes

**Play a full game.** You play against two AIs through Round 1 ($200-$1,000, 1 Daily Double), the Double Round ($400-$2,000, 2 Daily Doubles) and a Final Round with wagers.

| Difficulty | The AIs... |
|---|---|
| Easy | know the top rows, fade fast on pricey clues, buzz slowly (~1-2s), sometimes guess, wager on gut feeling |
| Medium | have solid knowledge with gaps on $1,000+ clues, buzz in ~0.4-1.3s, wager sensibly |
| Hard | know almost everything, buzz in ~0.15-0.7s, rarely miss, hunt Daily Doubles, use game-theory Final wagers |

Each AI also gets random strong and weak categories, so opponents play differently from game to game.

**Practice.** Choose from Random mix, Pick a category, Weak spots (the categories you miss most come first) or Final Round clues. There's an optional 15s timer, and your lifetime accuracy is tracked.

## Controls

- Arrows / `hjkl`: move. Enter: pick a clue.
- **Space**: buzz once "BUZZERS OPEN" appears. If you buzz early you're locked out for 0.5s.
- Type your response and press Enter. You don't need to say "What is". Small typos are forgiven.
- `O` on a result screen overrides a wrong judgement.
- Esc: quit to the menu.

Stats are saved to `~/.terminal-jeopardy/stats.json`.

## Adding clues

Edit `jeopardy/data/clues.json`. Each category needs exactly 5 clues, ordered easiest to hardest. Use `accept` to list other answers that should count as correct.

## Tests

```sh
python3 -m unittest discover -s tests
```
