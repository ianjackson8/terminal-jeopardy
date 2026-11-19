import io
import random
import shutil
import unittest
import wave

from jeopardy.sound import RATE, SOUNDS, Sound, synth


class SynthTests(unittest.TestCase):
    def test_every_sound_renders_valid_wav(self):
        for name, spec in SOUNDS.items():
            data = synth(spec)
            with wave.open(io.BytesIO(data)) as w:
                self.assertEqual((w.getnchannels(), w.getsampwidth(), w.getframerate()), (1, 2, RATE), name)
                expected = sum(int(RATE * seg[1]) for seg in spec)
                self.assertEqual(w.getnframes(), expected, name)
                self.assertLess(w.getnframes() / RATE, 2.0, f"{name} is too long for a game effect")

    def test_no_clipping_and_silent_edges(self):
        data = synth(SOUNDS["win"])
        with wave.open(io.BytesIO(data)) as w:
            frames = w.readframes(w.getnframes())
        samples = [int.from_bytes(frames[i:i + 2], "little", signed=True) for i in range(0, len(frames), 2)]
        self.assertLess(max(abs(x) for x in samples), 32767)
        self.assertLess(abs(samples[0]), 500)    # envelope starts quiet (no click)
        self.assertLess(abs(samples[-1]), 500)   # and ends quiet


class PlayerTests(unittest.TestCase):
    def test_no_player_is_a_silent_noop(self):
        snd = Sound(enabled=True, player=[])
        self.assertFalse(snd.available)
        snd.play("correct")   # must not raise
        snd.stop()

    def test_disabled_never_spawns(self):
        snd = Sound(enabled=False, player=["true"])
        snd.play("correct")
        self.assertEqual(snd._procs, [])

    @unittest.skipUnless(shutil.which("true"), "needs `true`")
    def test_plays_through_external_command(self):
        snd = Sound(enabled=True, player=["true"])
        snd.play("buzz")
        self.assertEqual(len(snd._procs), 1)
        self.assertTrue(snd._file("buzz").exists())
        snd._procs[0].wait(timeout=5)
        snd.stop()

    def test_unknown_sound_and_broken_player_are_ignored(self):
        Sound(enabled=True, player=["true"]).play("nope")
        Sound(enabled=True, player=["/definitely/not/a/player"]).play("buzz")  # swallowed


class GameSoundTests(unittest.TestCase):
    def test_game_triggers_expected_sounds(self):
        from tests.test_smoke import key_stream, run_with
        from jeopardy.ai import DIFFICULTIES

        class Spy:
            enabled = available = True

            def __init__(self):
                self.played = []

            def play(self, name):
                assert name in SOUNDS, name
                self.played.append(name)

            def stop(self):
                pass

        spy = Spy()

        def go(a):
            a.sfx = spy
            a.rng = random.Random(3)
            a.play_game(DIFFICULTIES[1])

        run_with(go, key_stream(3))
        played = set(spy.played)
        for name in ("round", "select", "buzz", "dd", "final"):
            self.assertIn(name, played)
        self.assertTrue({"correct", "wrong"} & played)
        self.assertTrue({"win", "lose"} & played)


if __name__ == "__main__":
    unittest.main()
