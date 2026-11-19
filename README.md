# Terminal Jeopardy

<p>
  <img alt="Python 3.10+" src="https://img.shields.io/badge/python-3.10%2B-3776AB?logo=python&logoColor=white">
  <img alt="No dependencies" src="https://img.shields.io/badge/dependencies-none-brightgreen">
  <img alt="Platform" src="https://img.shields.io/badge/platform-macOS%20%7C%20Linux-lightgrey">
  <img alt="Clues" src="https://img.shields.io/badge/clues-600%20%2B%2040%20finals-gold">
</p>

**A full quiz show in your terminal.** Buzz in against two AI opponents, hunt for Daily Doubles, bet it all in the Final Round, or sharpen up in practice mode.

```
                         ROUND 1

   COMPUTING     MUSIC      WORLD      TV LAND     U.S.     CHEMICAL
                           CAPITALS             PRESIDENTS  ELEMENTS

     $200        $200        $200        $200        $200        $200
     $400        $400        $400        $400        $400        $400
     $600        $600        $600        $600        $600        $600
     $800        $800        $800        $800        $800        $800
    $1,000      $1,000      $1,000      $1,000      $1,000      $1,000

          ▶ You                  Hal                  Turing
           $1,200               $400                  $800
```

---

## ✨ Features

- 🎮 **A full game:** Round 1, the Double Round and the Final Round, with hidden Daily Doubles and wagering
- 🤖 **Two AI opponents** with three difficulty levels and their own strong and weak categories
- ⚡ **Real-time buzzing:** wait for the buzzers to open, and buzz too early to get locked out
- 📚 **Practice mode:** random mix, single category, weak spots or Final Round clues, with an optional timer
- 🧠 **Forgiving answer checks:** no "What is…" needed, small typos are allowed, and you can override a wrong ruling
- 📈 **Saved stats:** win/loss record per difficulty, personal bests and lifetime practice accuracy
- 🔊 **Sound effects:** original synthesized chimes, buzzers and fanfares, with a toggle in the main menu
- 📦 **Zero dependencies:** only the Python standard library (`curses`)

## 🚀 Quick start

```sh
git clone https://github.com/ianjackson8/terminal-jeopardy.git
cd terminal-jeopardy
python3 -m jeopardy
```

Or install it as a command:

```sh
uv tool install .        # or: pip install .
jeopardy
```

> [!TIP]
> Use a terminal of at least **70×22**. The board scales up in bigger windows, and a 256-color terminal looks best.

## 🎯 How a game works

| Round | Values | Daily Doubles |
|---|---|---|
| **Round 1** | $200 – $1,000 | 1 |
| **Double Round** | $400 – $2,000 | 2 |
| **Final Round** | Your wager | — |

1. **Pick a clue.** The player who last answered correctly controls the board.
2. **Wait for the buzzers.** The clue is read first. When `BUZZERS OPEN` appears, press <kbd>Space</kbd>. If you buzz early you're locked out for half a second.
3. **Answer.** You have 10 seconds to type. A right answer earns the clue's value and a wrong one costs it. After a miss, the other players can buzz in on the rebound.
4. **Daily Doubles.** Only the picker plays. Wager up to your score, or up to the round's top value if that's higher.
5. **Final Round.** Everyone with a positive score bets secretly, then gets 30 seconds to answer one last clue.

## 🤖 Difficulty

| | Knowledge | Buzz speed | Style |
|---|---|---|---|
| 🟢 **Easy** | Strong on the top rows, weak on pricey clues | ~1–2 s | Sometimes guesses and wagers on gut feeling |
| 🟡 **Medium** | Solid, with real gaps on $1,000+ clues | ~0.4–1.3 s | Bets sensibly |
| 🔴 **Hard** | Knows almost everything | ~0.15–0.7 s | Hunts Daily Doubles and makes game-theory Final wagers |

Each AI also gets random strong and weak categories, so no two games play out the same way.

## 📚 Practice mode

| Mode | What it does |
|---|---|
| **Random mix** | Every clue in the bank, shuffled |
| **Pick a category** | One category, from $200 up to $1,000 |
| **Weak spots** | The categories you've missed most come first |
| **Final Round clues** | The tougher, Final-style clues |

You can turn on a 15-second timer in the practice menu. After each session you get a summary with your accuracy, best streak and a list of the clues you missed.

## ⌨️ Controls

| Key | Action |
|---|---|
| <kbd>↑</kbd> <kbd>↓</kbd> <kbd>←</kbd> <kbd>→</kbd> or <kbd>h</kbd><kbd>j</kbd><kbd>k</kbd><kbd>l</kbd> | Move around the board and menus |
| <kbd>Enter</kbd> | Pick a clue, submit an answer, continue |
| <kbd>Space</kbd> | Buzz in |
| <kbd>O</kbd> | Override: "I was right!" (on result screens) |
| <kbd>Esc</kbd> | Back, or quit to the menu |

## 🗂️ Adding your own clues

The clues live in [`jeopardy/data/clues.json`](jeopardy/data/clues.json). Each clue has a difficulty `tier` from **1 (easiest) to 5 (hardest)**, which sets its dollar value. A category needs at least one clue per tier and can have as many as you like. Each time a category comes up, the game deals one random clue from each tier, so deeper categories play differently every game.

```json
{
  "name": "THE SOLAR SYSTEM",
  "clues": [
    { "tier": 1, "clue": "Iron oxide gives this planet its nickname, the Red Planet", "answer": "Mars" },
    { "tier": 1, "clue": "The star at the center of our solar system", "answer": "The Sun", "accept": ["sun"] },
    { "tier": 2, "clue": "The largest planet in our solar system", "answer": "Jupiter" }
  ]
}
```

Add an `accept` list for other answers that should count, for example `"accept": ["fdr", "roosevelt"]`. Final Round clues go in the `finals` array with a `category`, `clue` and `answer`.

## 🛠️ Development

```sh
python3 -m unittest discover -s tests
```

The tests cover answer matching, the integrity of the clue bank, AI difficulty and wagering, and headless full games played through a fake terminal and clock.

```
jeopardy/
├── __main__.py     # entry point
├── app.py          # menus, game flow, practice mode
├── screen.py       # curses drawing, colors, input
├── ai.py           # AI opponents and difficulty levels
├── clues.py        # clue bank and board building
├── matching.py     # forgiving answer checker
└── data/clues.json # the clue bank
```

Stats are saved to `~/.terminal-jeopardy/stats.json`.
