import curses
import locale
import os


def main() -> None:
    locale.setlocale(locale.LC_ALL, "")
    os.environ.setdefault("ESCDELAY", "25")
    from .app import App

    curses.wrapper(lambda scr: App(scr).run())


if __name__ == "__main__":
    main()
