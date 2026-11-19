"""Plausible wrong answers for AI contestants that never leak answers from the current game.

A wrong guess is drawn from (a) a built-in vocabulary of decoys for that kind of
answer and (b) answers to clues that are NOT in play this game. Anything that is an
answer (or accepted alternative) anywhere on this game's boards or Final is excluded,
so an AI's miss can never reveal a response you might still need.
"""
from __future__ import annotations

import random
import re

from .clues import load_bank
from .matching import is_correct, normalize

# kind -> nouns a clue uses when asking for that kind of answer
_KINDS = [
    ("person", "author|writer|poet|playwright|novelist|composer|artist|painter|sculptor|scientist|"
               "physicist|mathematician|inventor|explorer|astronaut|king|queen|prince|princess|pharaoh|"
               "emperor|president|director|actor|actress|singer|teacher|grouch|man|woman|girl|boy|maiden|"
               "hero|heroine|god|sprinter|swimmer|character|detective|surrealist|impressionist|"
               "post-impressionist|philosopher|leader|monarch|ruler|brothers|doctor|captains|friend|neighbor"),
    ("country", "country|nation"),
    ("city", "city|capital|town"),
    ("state", "state"),
    ("planet", "planet"),
    ("language", "language"),
    ("river", "river|tributary"),
    ("sea", "sea|ocean|lake"),
    ("dinosaur", "dinosaur|plant-eater"),
    ("animal", "animal|bird|mammal|insect|amphibian|creature|beetle|parrot|dog"),
    ("element", "element|noble gas|metal"),
    ("currency", "currency"),
    ("color", "color|colour|dye"),
    ("food", "fruit|dish|sauce|spice|vegetable|crop|ingredient|leafy green"),
    ("body", "organ|bone|cells?|muscle"),
    ("unit", "unit"),
    ("work", "play|novel|book|film|musical|opera|poem|painting|mural|series|show|tragedy|sonata|saga"),
]
_ASKED = [(k, re.compile(rf"\b(?:this|these|the only|the first|the largest|the smallest) (?:[\w'-]+ ){{0,2}}(?:{n})s?\b", re.I))
          for k, n in _KINDS]
_LOOSE = [(k, re.compile(rf"\b(?:{n})s?\b", re.I)) for k, n in _KINDS if k != "person"]
_PRONOUN = re.compile(r"\b(he|she|his|him)\b|^her\b", re.I)

# Category-name keywords -> kind, used when the clue text itself isn't telling.
_CATEGORY_KINDS = [
    ("CURRENC", "currency"), ("COLOR", "color"), ("FOOD", "food"), ("FRUIT", "food"), ("VEGG", "food"),
    ("BODY", "body"), ("ANATOMY", "body"), ("WEATHER", "weather"), ("GAME", "game"),
    ("PRESIDENT", "person"), ("ROYALTY", "person"), ("SCIENTIST", "person"), ("WHO WROTE", "person"),
    ("ART", "person"), ("POET", "person"), ("COMPOSER", "person"), ("INVENTOR", "person"),
    ("CARTOON", "popculture"), ("TV", "popculture"), ("MOVIE", "popculture"), ("MUSICAL", "work"),
    ("SHAKESPEARE", "work"), ("LITERATURE", "work"), ("FAIRY", "popculture"),
    ("PHYSICS", "science"), ("SCIENCE", "science"), ("COMPUT", "science"), ("INVENTION", "science"),
    ("SPACE", "science"), ("ELEMENT", "element"), ("WORD", "word"), ("LANGUAGE", "language"),
    ("SPORT", "sports"), ("OLYMPIC", "sports"), ("MUSIC", "music"), ("LANDMARK", "landmark"),
    ("HISTORY", "history"), ("EGYPT", "history"), ("DOCUMENT", "history"), ("SHIP", "history"),
    ("ANIMAL", "animal"), ("BIRD", "animal"), ("INSECT", "animal"), ("DINOSAUR", "dinosaur"),
    ("MYTHOLOGY", "person"), ("FLAG", "country"), ("GEOGRAPHY", "place"), ("CAPITAL", "city"),
    ("RIVER", "river"), ("OCEAN", "sea"), ("STATES", "state"), ("NUMBER", "number"),
]

# Built-in decoys that aren't answers in the clue bank (anything that is gets filtered anyway).
VOCAB = {
    "person": ["Thomas Jefferson", "Charles Dickens", "Isaac Newton", "Napoleon", "Julius Caesar",
               "Mozart", "Pablo Picasso", "Winston Churchill", "Nikola Tesla", "Galileo",
               "Theodore Roosevelt", "Queen Victoria", "Plato", "Rembrandt", "Benjamin Franklin",
               "Mark Twain", "Homer", "Johann Sebastian Bach", "Amelia Earhart", "Aristotle"],
    "country": ["Argentina", "Portugal", "Norway", "Egypt", "Chile", "Peru", "Turkey", "Vietnam",
                "Morocco", "Iceland", "Kenya", "Thailand", "Poland", "Sweden", "Indonesia"],
    "city": ["Rome", "Madrid", "Vienna", "Buenos Aires", "Cairo", "Lisbon", "Oslo", "Bangkok",
             "Istanbul", "Nairobi", "Lima", "Dublin", "Prague", "Seoul", "Toronto"],
    "state": ["Texas", "Ohio", "Oregon", "Vermont", "Florida", "Nevada", "Montana", "Delaware",
              "Wyoming", "Georgia", "Idaho", "Kansas"],
    "planet": ["Venus", "Neptune", "Mercury", "Earth", "Mars", "Saturn", "Jupiter", "Uranus"],
    "language": ["Spanish", "German", "Italian", "Japanese", "Arabic", "Dutch", "Greek", "Korean",
                 "Bengali", "Turkish"],
    "river": ["Mississippi", "Danube", "Rhine", "Yangtze", "Ganges", "Mekong", "Seine", "Congo",
              "Euphrates", "Zambezi"],
    "sea": ["Red Sea", "Black Sea", "Baltic Sea", "Arabian Sea", "Lake Superior", "Atlantic Ocean",
            "Indian Ocean", "Caribbean Sea", "Coral Sea", "Lake Victoria"],
    "animal": ["Lion", "Elephant", "Giraffe", "Dolphin", "Penguin", "Eagle", "Kangaroo", "Frog",
               "Shark", "Tortoise", "Owl", "Wolf", "Crocodile", "Parrot", "Moth"],
    "dinosaur": ["Velociraptor", "Brachiosaurus", "Ankylosaurus", "Diplodocus", "Spinosaurus",
                 "Allosaurus", "Pterodactyl", "Jurassic", "Triassic", "Iguanodon"],
    "element": ["Silver", "Copper", "Helium", "Carbon", "Nitrogen", "Sodium", "Mercury", "Argon",
                "Platinum", "Radium", "Uranium", "Zinc"],
    "currency": ["Dollar", "Pound", "Krona", "Real", "Won", "Dinar", "Baht", "Ruble", "Lira", "Rand"],
    "color": ["Red", "Orange", "Indigo", "Violet", "Turquoise", "Crimson", "Teal", "Scarlet", "Cyan"],
    "food": ["Mango", "Broccoli", "Risotto", "Paprika", "Bechamel", "Carrot", "Ravioli", "Cinnamon",
             "Eggplant", "Papaya", "Paella", "Pesto"],
    "body": ["Liver", "Heart", "Femur", "Lungs", "Kidney", "Rods", "Spleen", "Tibia", "Cornea"],
    "weather": ["Monsoon", "Tornado", "Sleet", "Cirrus", "Thermometer", "Hygrometer", "Beaufort scale",
                "Blizzard", "Hurricane"],
    "game": ["Bishop", "Rook", "Checkers", "Scrabble", "Park Place", "En passant", "Backgammon",
             "Mahjong", "Risk"],
    "unit": ["Volt", "Ampere", "Joule", "Hertz", "Pascal", "Kelvin", "Coulomb"],
    "science": ["Proton", "Neutron", "Photosynthesis", "Friction", "Inertia", "Ribosome", "Volt",
                "Momentum", "Telegraph", "RAM", "Kilobyte", "Java", "Nucleus"],
    "word": ["Homonym", "Anagram", "Synonym", "Oxymoron", "Onomatopoeia", "Italian", "Abbreviation"],
    "sports": ["Golf", "Basketball", "Eagle", "Spare", "Rome", "Swimming", "Cricket", "Badminton"],
    "music": ["Mozart", "Bach", "The Rolling Stones", "Allegro", "Diminuendo", "Viola", "Cello",
              "Fortissimo", "Queen"],
    "landmark": ["Colosseum", "Taj Mahal", "Stonehenge", "Petra", "Parthenon", "Great Wall of China",
                 "Leaning Tower of Pisa", "Chichen Itza"],
    "history": ["Treaty of Versailles", "Declaration of Independence", "Constitution",
                "Emancipation Proclamation", "Ramses II", "Nefertiti", "Santa Maria",
                "Treaty of Paris", "Domesday Book"],
    "popculture": ["Snoopy", "Garfield", "Bedrock", "Elmo", "Shelby", "The Batmobile", "Sleeping Beauty",
                   "Hansel and Gretel", "Gotham", "Big Bird", "Shaggy"],
    "work": ["Othello", "King Lear", "Les Miserables", "War and Peace", "Cats", "Rent", "Oklahoma!",
             "Twelfth Night", "Great Expectations", "The Odyssey", "Jane Eyre"],
    "place": ["Gobi", "Amazon", "Andes", "Greenland", "Monaco", "Atlantic", "Russia", "Kalahari"],
    "other": ["Atlantis", "Pegasus", "Phoenix", "Excalibur", "Rosetta"],
}

FALLBACK = ["I'm not sure", "Pass"]


def classify(clue_text: str, answer: str, category: str = "") -> str:
    a = answer.strip()
    if re.fullmatch(r"\d{4}", a) and 1000 <= int(a) <= 2100:
        return "year"
    if re.fullmatch(r"\d+", a):
        return "number"
    # 1) What the clue explicitly asks for: "this [Himalayan] nation", "the only president"
    for kind, pat in _ASKED:
        if pat.search(clue_text):
            return kind
    # 2) Clues about a person usually use a pronoun: "He wrote...", "She left a glass slipper..."
    if _PRONOUN.search(clue_text):
        return "person"
    # 3) The category name: CURRENCIES, FOOD & DRINK, BOARD GAMES...
    cat = category.upper()
    for key, kind in _CATEGORY_KINDS:
        if key in cat:
            return kind
    # 4) Any telling keyword at all
    for kind, pat in _LOOSE:
        if pat.search(clue_text):
            return kind
    return "other"


class DecoyPool:
    def __init__(self, in_play: list[list[str]], rng: random.Random):
        """`in_play` is the answer list (answer + accepts) of every clue in this game."""
        self.rng = rng
        self.excluded = {normalize(a) for answers in in_play for a in answers}
        self.by_kind: dict[str, list[str]] = {}
        seen: set[str] = set()

        def add(kind: str, answer: str, accept=()) -> None:
            keys = {normalize(answer), *(normalize(a) for a in accept)}
            if keys & self.excluded or normalize(answer) in seen:
                return
            seen.add(normalize(answer))
            self.by_kind.setdefault(kind, []).append(answer)

        for kind, words in VOCAB.items():
            for w in words:
                add(kind, w)
        cats, finals = load_bank()
        for cat in cats:
            for c in cat["clues"]:
                add(classify(c["clue"], c["answer"], cat["name"]), c["answer"], c.get("accept", []))
        for f in finals:
            add(classify(f["clue"], f["answer"], f["category"]), f["answer"], f.get("accept", []))

    def _near_number(self, n: int, year: bool) -> str:
        if year:
            delta = self.rng.choice([-1, 1]) * self.rng.randint(1, 15)
        else:
            step = max(1, round(abs(n) * self.rng.uniform(0.05, 0.35)))
            delta = self.rng.choice([-1, 1]) * step
        guess = n + delta
        if guess <= 0 and n > 0:
            guess = n + abs(delta)
        return str(guess)

    def pick(self, clue_text: str, answers: list[str], avoid=frozenset(), category: str = "") -> str:
        """A wrong guess for a clue: same kind of answer, never in play, never correct."""
        kind = classify(clue_text, answers[0], category)
        bad = {normalize(a) for a in answers} | {normalize(a) for a in avoid}
        if kind in ("year", "number"):
            for _ in range(10):
                guess = self._near_number(int(answers[0]), kind == "year")
                if normalize(guess) not in bad:
                    return guess
        def ok(a: str) -> bool:
            return normalize(a) not in bad and not is_correct(a, answers)

        options = [a for a in self.by_kind.get(kind, []) if ok(a)]
        if not options:
            options = [a for k, v in self.by_kind.items() if k not in ("year", "number") for a in v if ok(a)]
        return self.rng.choice(options) if options else self.rng.choice(FALLBACK)
