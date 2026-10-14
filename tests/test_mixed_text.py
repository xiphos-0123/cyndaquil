import random
import unittest

from project.mixed_text import MixedText


class MixedTextTests(unittest.TestCase):
    def test_shared_multiline_text_and_mixed_sections_roundtrip(self):
        values = [
            "🌱 Focus: Alice\n\nWork completed\n",
            "🌱 Focus: Bob\n\nWork completed\n",
            "🌱 Focus: Carol\n\nWork completed\n",
        ]
        mixed = MixedText.from_values(values)
        self.assertIn("🌱 Focus: ", mixed.template)
        self.assertIn("\n\nWork completed\n", mixed.template)
        self.assertTrue(mixed.sections)
        for index, value in enumerate(values):
            self.assertEqual(mixed.expand(mixed.template, index), value)
            edited = mixed.template.replace("Work completed", "Work reviewed")
            self.assertEqual(
                mixed.expand(edited, index), value.replace("Work completed", "Work reviewed")
            )

    def test_identical_text_is_shown_without_markers(self):
        note = "Same\n\n  whitespace stays\n"
        mixed = MixedText.from_values([note, note])
        self.assertEqual(mixed.template, note)
        self.assertFalse(mixed.sections)

    def test_whole_marker_can_be_replaced_for_every_record(self):
        mixed = MixedText.from_values(["Worked on Alice\nDone", "Worked on Bob\nDone"])
        token = next(iter(mixed.sections))
        edited = mixed.template.replace(token, "the shared task")
        for index in range(2):
            self.assertEqual(mixed.expand(edited, index), "Worked on the shared task\nDone")

    def test_broken_and_unknown_markers_are_rejected(self):
        mixed = MixedText.from_values(["a", "b"])
        token = next(iter(mixed.sections))
        with self.assertRaises(ValueError):
            mixed.expand(mixed.template.replace(token, token[:-1]), 0)
        with self.assertRaises(ValueError):
            mixed.expand(f"{mixed.opener}999{mixed.closer}", 0)

    def test_original_marker_like_text_is_preserved(self):
        values = ["Literal ⟦1⟧\nAlice", "Literal ⟦1⟧\nBob"]
        mixed = MixedText.from_values(values)
        self.assertNotEqual(mixed.opener, "⟦")
        self.assertEqual([mixed.expand(mixed.template, i) for i in range(2)], values)

    def test_empty_and_repeated_unicode_text_roundtrips(self):
        rng = random.Random(42)
        cases = [["", "Long\ntext", ""], ["aaa\naaa", "aaaa\na", "a\naaaa"]]
        alphabet = "ab \n🌱日本"
        cases += [
            ["".join(rng.choice(alphabet) for _ in range(rng.randrange(40))) for _ in range(3)]
            for _ in range(150)
        ]
        for values in cases:
            mixed = MixedText.from_values(values)
            self.assertEqual([mixed.expand(mixed.template, i) for i in range(len(values))], values)

    def test_long_repetitive_notes_keep_common_lines_without_quadratic_matching(self):
        values = [
            ("same text\n" * 600) + name + "\n" + ("shared ending\n" * 400)
            for name in ("Alice", "Bob", "Carol")
        ]
        mixed = MixedText.from_values(values)
        self.assertTrue(mixed.template.startswith("same text\n" * 600))
        self.assertTrue(mixed.template.endswith("shared ending\n" * 400))
        self.assertEqual([mixed.expand(mixed.template, i) for i in range(3)], values)
