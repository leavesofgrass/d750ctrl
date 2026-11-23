"""keymap-test: the keymap of d750ctrl's screen: default keys in two families, the operator's
changes, the skipped lines and the words for help, the hint and the key row.

Run as python3 -I tests/keymap-test.py. Standard library only. One line for each failure,
then "Pass: keymap-test, N tests." or "Fail: keymap-test, F of N tests."; exit 0 or 1.

GPL-2.0-or-later.
"""

import os
import re
import sys
import unittest

TOP = os.path.dirname(os.path.dirname(os.path.realpath(__file__)))
sys.path.insert(0, TOP)

from d750ui import lines  # noqa: E402
from d750ui import keymap as km  # noqa: E402
from d750ui.keymap import ACTIONS, DEFAULTS, Keymap, key_words  # noqa: E402

NAME = "keymap-test"
NAMED = ["tab", "space", "enter", "up", "down", "left", "right", "pgup", "pgdn", "home", "end", "backspace"]
NAMED += [f"f{n}" for n in range(1, 13)]
SINGLE = [chr(c) for c in range(33, 127) if not chr(c).isdigit() and chr(c) not in ".,"]
REMAPPABLE = [(name, name) for name in NAMED] + [(ch, ch) for ch in SINGLE] + [("comma", ",")]
FIXED = ["esc", "Escape", "ctrl-c", "ctrl-l", "Ctrl+C", "period", "."] + [str(d) for d in range(10)]
EVERY_ACTION = sorted(set(ACTIONS["list"]) | set(ACTIONS["face"]))
DEFAULT_ROW_ORDER = (
    "Tab band. Up, Down tune. ? help. u unkey. L lock. V view. q quit. s step. m mode. p power. "
    "b control. v source. M memory. t TNC. g GPS. c frame. k clock."
)


def keeps_40(row):
    return bool(row) and len(row) <= 40 and not lines.problems(row, 40)


def keeps_80(line):
    return bool(line) and not lines.problems(line, 80)


class Rules(unittest.TestCase):
    def all_words_keep_the_rules(self, keymap, why=""):
        for view in ("list", "face", "compact"):
            for row in keymap.help_rows(view):
                self.assertTrue(keeps_40(row), (why, view, row, lines.problems(row, 40)))
            hint = keymap.hint(view)
            self.assertTrue(hint == "" or keeps_40(hint), (why, hint))
        row = keymap.key_row()
        self.assertTrue(row == "" or (len(row) <= 79 and keeps_80(row)), (why, row))
        for line in keymap.check_lines():
            self.assertTrue(keeps_80(line), (why, line))
        for line in keymap.skipped:
            self.assertTrue(keeps_80(line), (why, line))


class Defaults(Rules):
    def test_the_default_keys(self):
        k = Keymap()
        self.assertEqual(k.skipped, ())
        self.assertEqual(k.action("list", "up"), "row_up")
        self.assertEqual(k.action("face", "up"), "tune_up")
        self.assertEqual(k.action("list", "tab"), "other_band")
        self.assertEqual(k.action("face", "tab"), "other_band")
        self.assertEqual(k.keys("list", "step_down"), ("left", "-"))
        self.assertEqual(k.keys("list", "step_up"), ("right", "+", "="))
        self.assertEqual(k.keys("list", "next_step"), ())
        for family in ("list", "face"):
            for letter, action in zip("QULCMSRV", ("quit", "unkey", "lock", "memory", "memory", "sstv", "rtty", "view_next")):
                self.assertEqual(k.action(family, letter), action, (family, letter))
            self.assertEqual(k.action(family, "?"), "help")
            self.assertEqual(k.action(family, ":"), "raw")
            for answer in ("y", "n", "Y", "N"):
                self.assertIsNone(k.action(family, answer))
            self.assertIsNone(k.action(family, "ctrl-c"))

    def test_quit_and_unkey_have_a_small_letter_in_the_face_only(self):
        k = Keymap()
        self.assertEqual(k.action("face", "q"), "quit")
        self.assertEqual(k.action("face", "u"), "unkey")
        self.assertIsNone(k.action("list", "q"))
        self.assertIsNone(k.action("list", "u"))
        self.assertEqual(k.keys("list", "quit"), ("Q",))
        self.assertEqual(set(k.keys("face", "quit")), {"Q", "q"})

    def test_the_face_letters(self):
        k = Keymap()
        face = {
            "s": "next_step", "[": "squelch_down", "]": "squelch_up", "p": "act_power", "m": "act_mode",
            "b": "act_control", "v": "act_source", "t": "act_tnc", "g": "act_gps", "k": "set_clock",
            "c": "send_frame", "x": "chat", "o": "varac_chat", "r": "radiogram", "pgup": "tune_up_big",
            "pgdn": "tune_down_big", "down": "tune_down",
        }
        for key, action in face.items():
            self.assertEqual(k.action("face", key), action, key)

    def test_no_key_is_held_by_two_actions_of_a_family(self):
        for family, pairs in DEFAULTS.items():
            keys = [key for _, held in pairs for key in held]
            self.assertEqual(len(keys), len(set(keys)), family)

    def test_face_and_compact_have_the_same_help_rows(self):
        k = Keymap()
        self.assertEqual(k.help_rows("face"), k.help_rows("compact"))
        rows = k.help_rows("face")
        for row in ("Tab: the other band.", "Up, Down: tune one step.", "c: send a CQ or beacon frame. Asks."):
            self.assertIn(row, rows)
        self.assertNotIn("Up, Down: one row.", rows)
        self.assertIn("Capital Q, q: quit.", rows)
        self.assertIn("Capital U, u: unkey now.", rows)
        listed = k.help_rows("list")
        self.assertIn("Up, Down: one row.", listed)
        self.assertIn("Left, Minus: one step down.", listed)
        self.assertIn("Right, Plus: one step up.", listed)
        self.assertIn("Capital Q: quit.", listed)
        self.assertIn("Capital C, capital M: memory channels.", listed)
        self.assertEqual(k.hint("face"), "Tab band. Up, Down tune. V view. ? help", "the hint keeps the bare letter")
        self.assertIn("u unkey. L lock.", k.key_row(), "the key row keeps the bare letter")
        self.all_words_keep_the_rules(k)

    def test_the_default_hints_and_key_row(self):
        k = Keymap()
        self.assertEqual(k.hint("list"), "Letters jump. Arrows change. ? help")
        self.assertEqual(k.hint("face"), "Tab band. Up, Down tune. V view. ? help")
        self.assertEqual(k.hint("compact"), k.hint("face"))
        row = k.key_row()
        self.assertTrue(DEFAULT_ROW_ORDER.startswith(row), row)
        self.assertIn("u unkey.", row)
        self.assertIn("L lock.", row)
        self.assertLessEqual(len(row), 79)
        self.assertTrue(keeps_80(row))

    def test_the_key_row_fits_the_width(self):
        k = Keymap()
        self.assertEqual(k.key_row(80), k.key_row())
        wide = k.key_row(132)
        self.assertTrue(wide.startswith(k.key_row()), wide)
        self.assertIn("m mode.", wide)
        self.assertIn("M memory.", wide)
        self.assertLessEqual(len(wide), 131)
        self.assertEqual(km.row_problems(wide), [])
        full = k.key_row(400)
        self.assertTrue(full.startswith(DEFAULT_ROW_ORDER), full)
        self.assertTrue(full.endswith("RTTY."), full)
        for width in (20, 30, 40, 60, 100):
            row = k.key_row(width)
            self.assertLessEqual(len(row), width - 1)
            self.assertIn("u unkey.", row)
            self.assertIn("L lock.", row)
            self.assertEqual(km.row_problems(row), [])
        self.assertEqual(km.row_problems("x" * 50 + " " + "y" * 50), [lines.NO_CLAUSE])

    def test_check_lines_name_every_action_and_say_nothing_was_skipped(self):
        out = Keymap().check_lines()
        self.assertEqual(out[0], "No settings line was skipped.")
        self.assertEqual(out[1], "Keys in every view:")
        self.assertIn("Keys in the list view:", out)
        self.assertIn("Keys in the face and compact views:", out)
        self.assertIn("quit in the list: capital Q.", out)
        self.assertIn("quit in the face: capital Q, q.", out)
        self.assertIn("memory: capital C, capital M.", out)
        self.assertIn("other-band: Tab.", out)
        self.assertIn("step-up: Right, Plus, Equals.", out)
        self.assertEqual(out[-1], "radiogram: r.")
        for line in out:
            self.assertTrue(keeps_80(line), line)


class Words(Rules):
    def test_key_words_keep_the_rules(self):
        for _file_name, key in REMAPPABLE:
            words = key_words(key)
            self.assertTrue(keeps_40(words), (key, words))
            self.assertLessEqual(len(words), 17)

    def test_key_words_samples(self):
        samples = {"up": "Up", "pgup": "Page Up", "tab": "Tab", "space": "Space", "?": "Question mark",
                   ":": "Colon", "[": "Left bracket", "f5": "F5", "k": "k", "K": "K", "_": "Underscore"}
        for key, words in samples.items():
            self.assertEqual(key_words(key), words)

    def test_every_key_on_every_action_keeps_every_row_to_the_rules(self):
        for file_name, key in REMAPPABLE:
            for action in EVERY_ACTION:
                k = Keymap([(1, action, file_name)])
                takes_last_unkey = key == "U" and action != "unkey" and action in ACTIONS["list"]
                takes_last_lock = key == "L" and action != "lock"
                if takes_last_unkey or takes_last_lock or key in ("y", "n", "Y", "N"):
                    self.assertEqual(len(k.skipped), 1, (action, key))
                    self.assertTrue(keeps_80(k.skipped[0]))
                    self.assertEqual(k.keys("list", "unkey"), ("U",))
                    self.assertEqual(k.keys("face", "lock"), ("L",))
                    continue
                self.assertEqual(k.skipped, (), (action, file_name, k.skipped))
                for family in ("list", "face"):
                    if action in ACTIONS[family]:
                        self.assertEqual(k.action(family, key), action)
                        self.assertEqual(k.keys(family, action), (key,))
                    self.assertTrue(k.keys(family, "unkey"), (action, key))
                    self.assertTrue(k.keys(family, "lock"), (action, key))
                self.all_words_keep_the_rules(k, (action, key))
                self.assertIn("lock.", k.key_row(), (action, key))
                self.assertIn("unkey.", k.key_row(), (action, key))

    def test_four_long_keys_on_one_action_keep_the_rules(self):
        for action in EVERY_ACTION:
            k = Keymap([(1, action, '(, ), !, "')])
            self.assertEqual(k.skipped, (), action)
            self.all_words_keep_the_rules(k, action)
            k = Keymap([(1, action, "backspace, pgup, pgdn, f12")])
            self.assertEqual(k.skipped, (), action)
            self.all_words_keep_the_rules(k, action)

    def test_long_keys_on_the_first_entries_keep_unkey_and_lock_in_the_key_row(self):
        k = Keymap([(1, "other_band", "backspace"), (2, "tune_up", "pgup"), (3, "tune_down", "pgdn"),
                    (4, "help", "f12"), (5, "unkey", "f11"), (6, "lock", "f10")])
        self.assertEqual(k.skipped, ())
        row = k.key_row()
        self.assertIn("F11 unkey.", row)
        self.assertIn("F10 lock.", row)
        self.assertLessEqual(len(row), 79)


class Changes(Rules):
    def test_a_key_moved_to_another_action(self):
        k = Keymap([(3, "tune_up", "j")])
        self.assertEqual(k.skipped, ())
        self.assertEqual(k.action("face", "j"), "tune_up")
        self.assertIsNone(k.action("face", "up"))
        self.assertEqual(k.action("list", "up"), "row_up")
        self.assertIn("j, Down: tune one step.", k.help_rows("face"))
        self.assertEqual(k.hint("face"), "Tab band. j, Down tune. V view. ? help")

    def test_a_change_replaces_the_keys_in_every_family(self):
        k = Keymap([(1, "quit", "F5")])
        self.assertEqual(k.skipped, ())
        self.assertEqual(k.keys("list", "quit"), ("f5",))
        self.assertEqual(k.keys("face", "quit"), ("f5",))
        self.assertIsNone(k.action("face", "q"))
        k = Keymap([(1, "unkey", "u")])
        self.assertEqual(k.keys("list", "unkey"), ("u",))
        self.assertEqual(k.keys("face", "unkey"), ("u",))

    def test_a_key_given_is_taken_from_the_default_action_in_each_family(self):
        k = Keymap([(1, "quit", "up")])
        self.assertEqual(k.action("list", "up"), "quit")
        self.assertEqual(k.action("face", "up"), "quit")
        self.assertEqual(k.keys("list", "row_up"), ())
        self.assertEqual(k.keys("face", "tune_up"), ())
        self.all_words_keep_the_rules(k)

    def test_names_with_hyphens_and_any_case(self):
        k = Keymap([(1, "tune-up", "K"), (2, "other-band", "TAB, F5"), (3, "act_mode", "comma")])
        self.assertEqual(k.skipped, ())
        self.assertEqual(k.keys("face", "tune_up"), ("K",))
        self.assertEqual(k.keys("face", "other_band"), ("tab", "f5"))
        self.assertEqual(k.keys("face", "act_mode"), (",",))

    def test_every_action_but_unkey_and_lock_may_be_left_with_no_key(self):
        for action in EVERY_ACTION:
            k = Keymap([(1, action, "none")])
            if action in ("unkey", "lock"):
                self.assertEqual(k.skipped, (f"Line 1 skipped: {action} must keep a key.",))
                continue
            self.assertEqual(k.skipped, ())
            for family in ("list", "face"):
                self.assertEqual(k.keys(family, action), ())
            self.all_words_keep_the_rules(k, action)

    def test_actions_left_with_no_key_leave_the_hint(self):
        k = Keymap([(1, "view_next", "none"), (2, "other_band", "None"), (3, "help", "none")])
        self.assertEqual(k.hint("face"), "Up, Down tune.")
        self.assertEqual(k.hint("list"), "Letters jump. Arrows change.")
        gone = ("tune_up", "tune_down", "view_next", "help", "step_up", "step_down", "other_band")
        k = Keymap([(1, a, "none") for a in gone])
        self.assertEqual(k.hint("face"), "")
        self.assertEqual(k.hint("list"), "Letters jump.")


class Skipped(Rules):
    def test_each_kind_of_skipped_line(self):
        cases = (
            ((12, "tune_upp", "k"), "Line 12 skipped: no such action, tune-upp."),
            ((4, "tune_up", "zap"), "Line 4 skipped: no such key, zap."),
            ((4, "tune_up", "k, j, h, g, l"), "Line 4 skipped: more than 4 keys."),
            ((4, "tune_up", "k,,j"), "Line 4 skipped: a key name is missing."),
            ((4, "tune_up", "esc"), "Line 4 skipped: that key cannot be changed, esc."),
            ((4, "quit", "ctrl-c"), "Line 4 skipped: that key cannot be changed, ctrl-c."),
            ((4, "quit", "5"), "Line 4 skipped: that key cannot be changed, 5."),
            ((7, "tune up", None), "Line 7 skipped: no equals sign."),
        )
        for change, words in cases:
            k = Keymap([change])
            self.assertEqual(k.skipped, (words,), change)
            self.assertTrue(keeps_80(words))
            self.assertEqual(k.check_lines()[0], words)
            self.assertEqual(k.action("face", "up"), "tune_up")

    def test_no_action_ever_gets_y_or_n(self):
        for action in EVERY_ACTION:
            for answer in ("y", "n", "Y", "N", "k, y", "N, j"):
                k = Keymap([(3, action, answer)])
                self.assertEqual(
                    k.skipped, (f"Line 3 skipped: y and n answer questions. Not for {action.replace('_', '-')}.",),
                    (action, answer),
                )
                for family in ("list", "face"):
                    for key in ("y", "n", "Y", "N"):
                        self.assertIsNone(k.action(family, key), (action, answer))

    def test_unkey_and_lock_keep_a_key_in_each_family(self):
        cases = (
            ((3, "quit", "U"), "Line 3 skipped: it would leave unkey with no key."),
            ((3, "act_tnc", "L"), "Line 3 skipped: it would leave lock with no key."),
            ((3, "unkey", "none"), "Line 3 skipped: unkey must keep a key."),
            ((3, "lock", "None"), "Line 3 skipped: lock must keep a key."),
        )
        for change, words in cases:
            k = Keymap([change])
            self.assertEqual(k.skipped, (words,), change)
            for family in ("list", "face"):
                self.assertTrue(k.keys(family, "unkey"))
                self.assertEqual(k.keys(family, "lock"), ("L",))

    def test_a_key_already_given_by_an_earlier_change_is_skipped(self):
        k = Keymap([(5, "tune_up", "j"), (8, "tune_down", "j"), (9, "act_mode", "h")])
        self.assertEqual(k.skipped, ("Line 8 skipped: j is already given to tune-up on line 5.",))
        self.assertEqual(k.keys("face", "tune_down"), ("down",))
        self.assertEqual(k.keys("face", "act_mode"), ("h",))

    def test_odd_typed_names_are_made_safe(self):
        odd = (("tune_up#", "k"), ("tune_up", "<->"), ("x" * 90, "k"), ("tune_up", "ab_cd"), ("é", "k"))
        for name, value in odd:
            k = Keymap([(7, name, value)])
            self.assertEqual(len(k.skipped), 1)
            self.assertTrue(k.skipped[0].startswith("Line 7 skipped:"))
            self.assertTrue(keeps_80(k.skipped[0]), k.skipped[0])

    def test_fixed_keys_cannot_be_changed_by_any_line(self):
        for fixed in FIXED:
            for action in ("quit", "tune_up", "help", "flip", "edit", "send_frame", "unkey"):
                k = Keymap([(1, action, fixed)])
                self.assertEqual(len(k.skipped), 1, (fixed, action))
                family = "list" if action in ACTIONS["list"] else "face"
                self.assertEqual(k.keys(family, action), Keymap().keys(family, action))

    def test_a_line_that_cannot_be_read(self):
        k = Keymap([("x", "quit", "Q")])
        self.assertEqual(k.skipped, ("A settings line was skipped: it could not be read.",))


def main():
    suite = unittest.defaultTestLoader.loadTestsFromModule(sys.modules[__name__])
    result = unittest.TestResult()
    suite.run(result)
    failed = {}
    for test, trace in result.failures + result.errors:
        case = getattr(test, "test_case", test)
        found = re.findall(r'File "[^"]*keymap-test\.py", line (\d+)', trace)
        text = trace.strip().splitlines()
        error = next((i for i in range(len(text) - 1, -1, -1) if re.match(r"^[A-Za-z.]*(Error|Exception)\b", text[i])), None)
        words = " / ".join(t.strip() for t in text[error : error + 4]) if error is not None else (text[-1] if text else "")
        said = f"line {found[-1] if found else '?'}: " + lines.clean(words.replace("_", "-"), 300)
        failed.setdefault(case.id().rsplit(".", 1)[-1].replace("_", "-"), said)
    for name, words in failed.items():
        print(f"Fail: {name}: {words}")
    if failed:
        print(f"Fail: {NAME}, {len(failed)} of {result.testsRun} tests.")
        return 1
    print(f"Pass: {NAME}, {result.testsRun} tests.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
