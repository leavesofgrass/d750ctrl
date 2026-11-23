"""screen-model-test: d750ctrl's screen model, driven by key names and a pretend clock.

Each test carries out the model's things to do against the pretend daemon of
tests/fakedaemon.py, in this process, and checks the rows, the cursor, the marks, the
things to do and what the pretend radio then holds. Nothing transmits: SendFrame and
Tool are only recorded.

Run as python3 -I tests/screen-model-test.py. Standard library only. One line for each
failure, then "Pass: screen-model-test, N tests." or "Fail: ..., F of N tests."; exit 0 or 1.

GPL-2.0-or-later.
"""

import os
import random
import re
import sys
import unittest

HERE = os.path.dirname(os.path.realpath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
sys.path.insert(0, HERE)

from fakedaemon import Runner  # noqa: E402

from d750ui import keymap as km  # noqa: E402
from d750ui import lines  # noqa: E402
from d750ui import screen_model as sm  # noqa: E402

NAME = "screen-model-test"
SIZES = ((40, 6), (40, 8), (40, 10), (40, 12), (79, 24), (80, 12), (80, 17), (80, 24), (132, 50))
STYLES = ("focus", "head_a", "head_b", "alarm", "busy", "digits", "bar", "history", "log", "keys")
SPANS = ("digits", "bar", "history")  # marks over cells no line rule applies to
UNSAFE_HEADS = ("TX", "RX", "UP", "DW", "SR", "PS", "0M", "0G", "BE")
# Keys that take each mode from main mode, in either family.
MODE_KEYS = {
    "main": (),
    "typing": ("1", "4"),
    "raw": (":", "F", "V"),
    "help": ("?", "down"),
    "memory": ("C",),
    "asking": ("R",),
    "unlock": ("L", "L"),
}


def keeps_40(row):
    return row == "" or (len(row) <= 40 and not lines.problems(row, 40))


def sized(view="face", width=80, height=24, **kw):
    r = Runner(view=view, **kw)
    r.model.size(width, height)
    return r


def sets(todos):
    return [t.line for t in todos if isinstance(t, sm.Set)]


def asks(todos, why=None):
    return [t for t in todos if isinstance(t, sm.Ask) and (why is None or t.why == why)]


def differs_only_in_message(before, after, height):
    """Two frames the same but for the message row, the second from the bottom."""
    if (before.cursor, before.focus_row, before.marks) != (after.cursor, after.focus_row, after.marks):
        return False
    if len(before.rows) != len(after.rows):
        return False
    return all(b == a for i, (b, a) in enumerate(zip(before.rows, after.rows)) if i != height - 2)


class Frames(unittest.TestCase):
    """The rules every frame keeps."""

    def check_frame(self, model, width, height):
        frame = model.frame(width, height)
        self.assertEqual(frame, model.frame(width, height), "the same state gave another frame")
        self.assertEqual(len(frame.rows), height)
        for row, column, length, style in frame.marks:
            self.assertIn(style, STYLES)
            self.assertTrue(0 <= row < height and column >= 0 and length > 0, (row, column, length, style))
            self.assertLessEqual(column + length, width, ("a mark reaches out of the frame", style))
            if style not in ("bar", "history"):
                self.assertLessEqual(column + length, len(frame.rows[row]), ("past its row's text", style, frame.rows[row]))
        shown = sm.shows(model.view, width, height)
        if shown is None:
            if height:
                self.assertEqual(frame.rows[0], sm.TOO_SMALL if model.view == "list" else sm.TOO_SMALL_COMPACT)
                self.assertEqual(frame.rows[1:], ("",) * (height - 1))
            self.assertEqual((frame.cursor, frame.marks), ((0, 0), ()))
            return frame
        listish = shown == "list" or model.mode in (sm.HELP, sm.MEMORY)
        if shown == "wide" and not listish:
            self.check_wide_rows(frame, width, height)
        else:
            for row in frame.rows:
                self.assertTrue(keeps_40(row), (shown, row, lines.problems(row, 40)))
        row, column = frame.cursor
        if model.mode == sm.TYPING:
            self.assertEqual(row, height - 1)
            self.assertEqual(column, len(frame.rows[-1]))
            self.assertLessEqual(column, 39)
        elif model.mode == sm.ASKING:
            self.assertEqual((row, column), (height - 1, len(frame.rows[-1])))
            self.assertLessEqual(column, 39)
        if listish:
            self.assertEqual(frame.marks, ())
            self.assertTrue(1 <= frame.focus_row <= height - 3)
            if model.mode not in (sm.TYPING, sm.ASKING):
                self.assertEqual(frame.cursor, (frame.focus_row, 0))
            return frame
        active = model.active
        if shown == "compact":
            self.assertEqual(frame.focus_row, 1 + active)
            self.assertEqual(frame.marks, ())
            if model.mode not in (sm.TYPING, sm.ASKING):
                self.assertEqual(frame.cursor, (1 + active, 0))
        elif shown == "stacked":
            self.assertIsNone(frame.focus_row)
            first = 1 if active == 0 else 4
            self.assertTrue(any(m[0] == first and m[3] == "focus" for m in frame.marks))
            if model.mode not in (sm.TYPING, sm.ASKING):
                self.assertEqual(frame.cursor, (first, 0))
        else:
            self.assertIsNone(frame.focus_row)
            column = 0 if active == 0 else sm.RIGHT
            self.assertTrue(any(m[:2] == (2, column) and m[3] == "focus" for m in frame.marks))
            if model.mode not in (sm.TYPING, sm.ASKING):
                self.assertEqual(frame.cursor, (2, column))
        return frame

    def check_wide_rows(self, frame, width, height):
        rows = list(frame.rows)
        digit_rows = {m[0] for m in frame.marks if m[3] == "digits"}
        log_rows = set()
        for m in frame.marks:
            if m[3] == "log":
                log_rows = set(range(m[0] + 1, height - 3))
        for m in frame.marks:
            if m[3] in SPANS:
                r, c, n = m[0], m[1], m[2]
                span = rows[r][c : c + n]
                self.assertTrue(set(span) <= {"#", " ", "."}, (m, rows[r]))
                rows[r] = rows[r][:c] + " " * len(span) + rows[r][c + n :]
        for r, row in enumerate(rows):
            self.assertLessEqual(len(frame.rows[r]), width)
            if r in digit_rows:
                self.assertTrue(set(frame.rows[r]) <= {"#", " "}, frame.rows[r])
            elif r in log_rows:
                continue
            elif r == height - 3:
                self.assertTrue(row == "" or (len(row) <= width - 1 and not km.row_problems(row)), row)
            elif r >= height - 2:
                self.assertTrue(keeps_40(row), (row, lines.problems(row, 40)))
            else:
                left, gap, right = row[:39].rstrip(" "), row[39:41], row[41:].rstrip(" ")
                self.assertEqual(gap.strip(" "), "", row)
                self.assertTrue(keeps_40(left), (left, lines.problems(left, 40)))
                self.assertLessEqual(len(right), 39, row)
                self.assertTrue(keeps_40(right), (right, lines.problems(right, 40)))


class Start(Frames):
    def test_start_is_one_read_state_first_with_id_and_firmware(self):
        r = Runner(start=False)
        todos = r.model.start()
        self.assertEqual(len(asks(todos)), 1)
        ask = todos[0]
        self.assertEqual(ask.why, "start")
        self.assertEqual(ask.lines[0], "state")
        for line in ("ID", "FV", "BC", "FQ 0", "MD 1", "BY 0", "BY 1", "TN", "GP", "VX"):
            self.assertIn(line, ask.lines)

    def test_the_first_look(self):
        r = sized("list", 40, 40)
        m = r.model
        self.assertEqual(m.status(), "d750ctrl. Receiving. Unlocked.")
        frame = r.frame(40, 40)
        self.assertEqual(frame.rows[0], "d750ctrl. Receiving. Unlocked.")
        for line in ("Daemon port open", "PTT unlocked", "Radio TM-D750", "Firmware 1.03", "Control band B",
                     "Transmit band B", "Step 10 kHz", "A frequency 147.040 MHz", "A mode FM", "A squelch 6",
                     "A power high", "A source VFO", "A channel none", "A quiet", "B frequency 144.390 MHz",
                     "B power mid", "TNC mode KISS", "TNC band B", "GPS output off", "VOX off", "Memory channels"):
            self.assertIn(line, [m.row_line(row) for row in sm.ROWS], line)
        self.assertEqual(frame.rows[-2], "")
        self.check_frame(m, 40, 40)

    def test_id_and_firmware_go_until_answered_once(self):
        r = sized("face")
        sweep = asks(r.tick(2.5), "sweep")[0]
        self.assertNotIn("ID", sweep.lines)
        self.assertNotIn("FV", sweep.lines)

    def test_the_status_row(self):
        r = sized("face")
        d = r.daemon
        d.locked = True
        r.tick(0.6)
        self.assertEqual(r.model.status(), "d750ctrl. Receiving. PTT locked.")
        d.keyed = True
        r.tick(0.6)
        self.assertEqual(r.model.status(), "d750ctrl. TRANSMITTING.")
        frame = r.frame(80, 24)
        self.assertIn((0, 10, 12, "alarm"), frame.marks)
        d.keyed = False
        d.port_open = False
        r.tick(0.6)
        self.assertEqual(r.model.status(), "d750ctrl. No radio.")
        d.answering = False
        r.tick(0.6)
        self.assertEqual(r.model.status(), "d750ctrl. No daemon.")
        d.answering = True
        d.port_open = True
        r.tick(0.6)
        self.assertEqual(r.model.status(), "d750ctrl. Receiving. PTT locked.")
        self.assertNotIn("port", r.model.message)


class Reading(Frames):
    def held(self, view="face", width=80, height=24, **kw):
        """A model with no carrier: the test hands results back itself."""
        r = Runner(start=False, view=view, **kw)
        r.model.size(width, height)
        return r

    def test_never_two_reads_at_once(self):
        r = self.held()
        m = r.model
        ask = m.start()[0]
        for i in range(100):
            self.assertEqual(asks(m.tick(1000 + i * 0.1)), [], "a read went while another was out")
        self.assertEqual(asks(m.key("p")), [])
        out = r.carrier.carry(ask)
        more = m.finished(ask, out, None, "12:00:00")
        self.assertLessEqual(len(asks(more)), 1)
        if not more:
            more = m.tick(1010.1)
        self.assertEqual(len(asks(more)), 1)
        for i in range(30):
            self.assertEqual(asks(m.tick(1011 + i * 0.1)), [])

    def test_a_memory_read_also_holds_the_reads(self):
        r = sized("face")
        m = r.model
        todos = m.key("C")
        self.assertEqual(todos, [sm.MemoryRead(0, 9)])
        for i in range(50):
            self.assertEqual(asks(m.tick(r.now + 0.1 * i)), [])

    def rates(self, view, width, height, **kw):
        r = sized(view, width, height, **kw)
        r.tick(0.1)
        start = len(r.done)
        r.tick(10)
        todos = r.done[start:]
        return asks(todos, "sweep"), asks(todos, "busy"), asks(todos, "state")

    def test_the_rates_with_the_defaults(self):
        sweeps, busy, state = self.rates("face", 80, 24)
        self.assertIn(len(sweeps), (4, 5, 6))
        self.assertIn(len(busy), (4, 5, 6))
        self.assertGreaterEqual(len(state), 6)
        for a in sweeps:
            self.assertIn("BY 0", a.lines)
            self.assertIn("BY 1", a.lines)

    def test_status_seconds_and_busy_seconds(self):
        sweeps, busy, _ = self.rates("face", 80, 24, status_seconds=5, busy_seconds=0.25)
        self.assertIn(len(sweeps), (1, 2, 3))
        self.assertGreaterEqual(len(busy), 30)
        sweeps, busy, _ = self.rates("face", 80, 24, status_seconds=0.1)
        self.assertLessEqual(len(sweeps), 21, "the least is 0.5 seconds")
        _, busy, _ = self.rates("face", 80, 24, busy_seconds=0)
        self.assertEqual(busy, [], "0 reads busy with the sweep only")

    def test_live_meters_in_each_view_and_face_form(self):
        cases = {
            ("auto", "list", 80, 24): False,
            ("auto", "face", 80, 24): True,
            ("auto", "face", 60, 24): False,
            ("auto", "face", 80, 11): False,
            ("auto", "face", 60, 8): False,
            ("auto", "compact", 80, 24): False,
            ("yes", "list", 80, 24): True,
            ("yes", "face", 60, 24): True,
            ("yes", "face", 60, 8): True,
            ("yes", "compact", 80, 24): True,
            ("no", "face", 80, 24): False,
            ("no", "list", 80, 24): False,
            ("no", "compact", 40, 6): False,
        }
        for (live, view, width, height), fast in cases.items():
            _, busy, _ = self.rates(view, width, height, live_meters=live)
            self.assertEqual(bool(busy), fast, (live, view, width, height))

    def test_the_older_words_for_live_meters(self):
        for word, means in (("on", "yes"), ("true", "yes"), ("1", "yes"), (True, "yes"), ("off", "no"),
                            ("false", "no"), ("0", "no"), (False, "no"), ("red", "auto"), ("", "auto")):
            self.assertEqual(sm.ScreenModel(live_meters=word).live_meters, means, word)

    def test_no_busy_read_by_itself_in_help_memory_typing_or_asking(self):
        for keys in (("?",), ("C",), ("1",), ("R",), (":",)):
            r = sized("face", 80, 24, live_meters="yes")
            r.press(*keys)
            start = len(r.done)
            r.tick(6)
            todos = r.done[start:]
            self.assertEqual(asks(todos, "busy"), [], keys)
            self.assertTrue(asks(todos, "sweep"), keys)

    def test_a_set_takes_the_echo_and_a_sweep_follows_at_once(self):
        r = sized("face")
        todos = r.press("p")
        self.assertEqual(sets(todos), ["PC 0,1"])
        at = todos.index(sm.Set("PC 0,1"))
        self.assertIsInstance(todos[at + 1], sm.Ask)
        self.assertEqual(todos[at + 1].why, "sweep")
        r.press("p")
        self.assertEqual(r.daemon.sim.pc[0], 2, "two presses of p step twice")
        self.assertEqual(r.model.bands[0].power, 2)
        self.assertEqual(r.model.message, "Band A power low.")

    def test_the_echo_is_taken_before_the_sweep(self):
        r = self.held()
        m = r.model
        ask = m.start()[0]
        m.finished(ask, r.carrier.carry(ask), None, "")
        m.tick(1000.0)
        todo = m.key("p")[0]
        m.finished(todo, "PC 0,1", None, "")
        self.assertEqual(m.bands[0].power, 1)
        todo = m.key("p")[0]
        self.assertEqual(todo, sm.Set("PC 0,2"))

    def test_a_key_on_a_value_not_read_sends_nothing(self):
        r = self.held()
        m = r.model
        for key, words in (("t", "TNC not read."), ("[", "A squelch not read."), ("p", "A power not read."),
                           ("up", "A frequency not read."), ("g", "GPS output not read."), ("m", "A mode not read.")):
            self.assertEqual(m.key(key), [], key)
            self.assertEqual(m.message, words)

    def test_mr_follows_only_for_a_band_in_memory_mode(self):
        r = sized("face")
        r.daemon.sim.vm[1] = 1
        r.daemon.sim.mr[1] = 1
        todos = r.tick(2.5)
        channel = asks(todos, "channel")
        self.assertEqual([a.lines for a in channel], [("MR 1",)])
        self.assertEqual(r.model.row_line(sm.ROWS[[x.rid for x in sm.ROWS].index("channel") + 7]), "B channel 001")

    def test_windows_go_with_each_sweep_in_the_workspace(self):
        r = sized("face", workspace=True, windows=("chat",))
        todos = r.tick(2.5)
        self.assertTrue(any(isinstance(t, sm.Windows) for t in todos))
        self.assertEqual(r.model.windows, ("chat",))
        r = sized("face")
        self.assertFalse(any(isinstance(t, sm.Windows) for t in r.tick(2.5)))

    def test_an_answer_that_does_not_start_with_its_letters_leaves_the_old_value(self):
        r = self.held()
        m = r.model
        ask = m.start()[0]
        answers = list(r.carrier.carry(ask))
        m.finished(ask, tuple(answers), None, "")
        self.assertEqual(m.bands[0].hz, 147040000)
        bad = ["?" if line.startswith(("FQ", "SQ", "TN")) else a for line, a in zip(ask.lines, answers)]
        bad = ["ERR radio" if line.startswith("BY") else a for line, a in zip(ask.lines, bad)]
        m.bands[0].busy = 1
        m.finished(ask, tuple(bad), None, "")
        self.assertEqual(m.bands[0].hz, 147040000)
        self.assertEqual(m.bands[0].sq, 6)
        self.assertEqual(m.tnc, (2, 1))
        self.assertEqual(m.bands[0].busy, 0, "a busy read that fails counts as quiet")

    def test_the_command_log(self):
        r = sized("face")
        r.press("p")
        self.assertEqual(r.model.log[-1][1:], ("PC 0,1", "PC 0,1"))
        r.press("U")
        self.assertEqual(r.model.log[-1][1:], ("T 0", "RPRT 0"))
        r.press("k", "y")
        self.assertEqual(r.model.log[-1][1], "RT")
        count = len(r.model.log)
        r.tick(5)
        self.assertEqual(len(r.model.log), count, "quiet reads answered are not logged")
        r.daemon.port_open = False
        r.tick(2.5)
        self.assertTrue(any(a.startswith("ERR") for _, _, a in r.model.log[count:]))
        count = len(r.model.log)
        r.press("C")
        r.tick(1)
        r.press("esc")
        self.assertFalse(any(line.startswith("ME") for _, line, _ in r.model.log), "memory reads are never logged")
        for _ in range(120):
            r.press("p")
        self.assertEqual(len(r.model.log), sm.LOG_MOST)


class Views(Frames):
    def test_what_shows(self):
        cases = {
            ("list", 40, 8): "list", ("list", 39, 24): None, ("list", 80, 7): None,
            ("face", 80, 12): "wide", ("face", 80, 11): "stacked", ("face", 79, 24): "stacked",
            ("face", 40, 10): "stacked", ("face", 40, 9): "compact", ("face", 40, 6): "compact",
            ("face", 40, 5): None, ("compact", 40, 6): "compact", ("compact", 39, 6): None,
            ("compact", 132, 50): "compact",
        }
        for (view, w, h), shown in cases.items():
            self.assertEqual(sm.shows(view, w, h), shown, (view, w, h))

    def test_frames_of_every_view_at_every_size_in_every_mode(self):
        for view in sm.VIEWS:
            for width, height in SIZES:
                for mode, keys in MODE_KEYS.items():
                    for active in (0, 1):
                        r = sized(view, 80, 24)
                        r.model.active = active
                        if keys:
                            r.press(*keys)
                        r.model.size(width, height)
                        with self.subTest(view=view, size=(width, height), mode=mode, active=active):
                            self.check_frame(r.model, width, height)
                if view == "list":
                    r = sized(view, 80, 24)
                    r.press("V")
                    with self.subTest(view=view, size=(width, height), mode="view question"):
                        r.model.size(width, height)
                        self.check_frame(r.model, width, height)

    def test_a_frame_has_height_rows_from_height_0(self):
        for view in sm.VIEWS:
            r = sized(view)
            for height in range(0, 8):
                self.assertEqual(len(r.model.frame(40, height).rows), height)

    def test_the_size_messages_are_said_once_at_each_change(self):
        r = sized("face", 80, 24)
        r.model.size(60, 24)
        self.assertEqual(r.model.message, "")
        r.model.size(60, 8)
        self.assertEqual(r.model.message, sm.TOO_SMALL_FACE)
        r.model.message = ""
        r.model.size(60, 7)
        self.assertEqual(r.model.message, "")
        r.model.size(80, 24)
        self.assertEqual(r.model.message, sm.FACE_AGAIN)
        r.model.message = ""
        r.model.size(80, 24)
        self.assertEqual(r.model.message, "")

    def test_keys_follow_the_wanted_view_when_compact_shows(self):
        r = sized("face", 60, 8)
        todos = r.press("up")
        self.assertEqual(sets(todos), ["FQ 0,0147050000"])

    def test_capital_v_goes_round_with_its_question(self):
        r = sized("list", 80, 24)
        r.press("V")
        self.assertEqual(r.model.frame(80, 24).rows[-1], sm.VIEW_QUESTION)
        r.press("y")
        self.assertEqual((r.model.view, r.model.message), ("face", sm.TO_THE_FACE))
        r.press("V")
        self.assertEqual((r.model.view, r.model.message), ("compact", "View: compact."))
        r.press("V")
        self.assertEqual((r.model.view, r.model.message), ("list", "View: list."))

    def test_from_the_list_to_where_only_compact_shows(self):
        r = sized("list", 60, 9)
        r.press("V", "y")
        self.assertEqual((r.model.view, r.model.message), ("face", sm.TO_COMPACT))

    def test_the_stacked_and_compact_rows(self):
        r = sized("face", 60, 12)
        rows = r.frame(60, 12).rows
        self.assertEqual(rows[1:8], (
            "A 147.040 MHz", "A FM, power high, VFO. Active.", "A squelch 6, quiet",
            "B 144.390 MHz. Control. Transmit.", "B FM, power mid, VFO", "B squelch 3, quiet",
            "TNC KISS on B. GPS out off. VOX off.",
        ))
        self.assertEqual(r.frame(60, 12).cursor, (1, 0))
        r = sized("compact", 40, 6)
        rows = r.frame(40, 6).rows
        self.assertEqual(rows[1:4], ("A 147.040 MHz FM, high, quiet. Active.", "B 144.390 MHz FM, mid, quiet",
                                     "Control B. Transmit B. TNC KISS on B."))

    def test_the_wide_face(self):
        r = sized("face", 80, 24)
        frame = r.frame(80, 24)
        rows = frame.rows
        self.assertTrue(rows[0].startswith("d750ctrl. Receiving. Unlocked."))
        self.assertEqual(rows[0][41:], "Step 10 kHz. TNC KISS on B.")
        self.assertEqual(rows[1][:41].rstrip(), "Band A. Active.")
        self.assertEqual(rows[1][41:], "Band B. Control. Transmit.")
        self.assertEqual(rows[2], "147.040 MHz".ljust(41) + "144.390 MHz")
        for i in range(5):
            self.assertTrue(set(rows[3 + i]) <= {"#", " "})
        self.assertEqual(rows[8][:41].rstrip(), "FM, power high, VFO")
        self.assertEqual(rows[9][:21], "Squelch 6   ######   ")
        self.assertTrue(rows[10].startswith("quiet   ."))
        self.assertTrue(rows[11].startswith("TM-D750. GPS out off. VOX off."))
        self.assertEqual(rows[13], "Command log")
        self.assertEqual(rows[-3], km.Keymap().key_row())
        self.assertEqual(frame.cursor, (2, 0))
        r.press("tab")
        self.assertEqual(r.frame(80, 24).cursor, (2, 41))
        digit_row = r.frame(80, 24).rows[3]
        self.assertEqual(digit_row[:41].strip(), "")
        self.assertIn("#", digit_row[41:])
        r.press("p")
        log = [row for row in r.frame(80, 24).rows if " sent PC 1,2. Answer: PC 1,2" in row]
        self.assertEqual(len(log), 1)

    def test_big_digits_show_only_when_they_should(self):
        self.assertEqual(sum(m[3] == "digits" for m in sized("face", 80, 17).frame(80, 17).marks), 5)
        self.assertEqual(sum(m[3] == "digits" for m in sized("face", 80, 16).frame(80, 16).marks), 0)
        r = sized("face", 80, 24, digits="plain")
        self.assertEqual(sum(m[3] == "digits" for m in r.frame(80, 24).marks), 0)
        r = Runner(start=False, view="face")
        self.assertEqual(sum(m[3] == "digits" for m in r.model.frame(80, 24).marks), 0)

    def test_the_longest_values_fit_without_a_cut(self):
        r = sized("face", 80, 24)
        m = r.model
        for b in (0, 1):
            band = m.bands[b]
            band.hz, band.mode, band.power, band.vm, band.mr, band.busy = 446_006_250, 1, 0, 1, "199", 1
            band.history = [1, 0] * 15
        m.ctrl = m.tx = 0
        m.tnc, m.gps, m.vox = (2, 1), 1, 1
        m.windows = ("chat", "varac", "radiogram", "sstv", "rtty")
        expected = {
            "stacked": ["A 446.00625 MHz. Control. Transmit.", "A NFM, power high, memory 199. Active.",
                        "A squelch 6, BUSY"],
            "compact": ["A 446.00625 MHz NFM, high, BUSY. Active."],
        }
        rows = m.frame(60, 12).rows
        self.assertEqual(list(rows[1:4]), expected["stacked"])
        m.view = "compact"
        self.assertEqual(m.frame(60, 12).rows[1], expected["compact"][0])
        m.view = "list"
        for row in sm.ROWS:
            line = m.row_line(row)
            self.assertEqual(sm._safe(line), line, line)
        m.view = "face"
        for width, height in SIZES:
            self.check_frame(m, width, height)

    def test_marks_in_the_stacked_face(self):
        r = sized("face", 60, 12)
        r.daemon.sim.busy[1] = 1
        r.tick(2.5)
        marks = r.frame(60, 12).marks
        self.assertIn((1, 0, 1, "head_a"), marks)
        self.assertIn((4, 0, 1, "head_b"), marks)
        self.assertIn((1, 2, 11, "focus"), marks)
        self.assertIn((6, 13, 4, "busy"), marks)


class Keys(Frames):
    def test_tab_in_the_face_says_the_new_band(self):
        for announce in sm.ANNOUNCE:
            r = sized("face", announce=announce)
            r.press("tab")
            self.assertEqual(r.model.active, 1)
            self.assertEqual(r.model.message, "Band B. 144.390 MHz FM, power mid.")

    def test_tab_in_the_list(self):
        r = sized("list")
        r.press("tab")
        self.assertEqual(r.model.message, "Tab works on a band's row.")
        r.press("a")
        self.assertEqual(r.model.focused().name, "A frequency")
        r.press("down", "tab")
        self.assertEqual(r.model.focused().name, "B mode")
        self.assertEqual(r.model.active, 1)
        r.press("enter")
        self.assertEqual(r.model.typing_prompt(), "B mode")

    def test_tuning_follows_announce_and_other_changes_are_told(self):
        r = sized("face", announce="cursor")
        r.press("up")
        self.assertEqual(r.model.message, "")
        self.assertEqual(r.daemon.sim.freq[0], 147050000)
        for key, words in (("]", "Band A squelch 7."), ("p", "Band A power mid."), ("m", "Band A mode NFM."),
                           ("v", "Band A source memory."), ("b", "Band A controls and transmits."),
                           ("g", "GPS output on."), ("s", "Step 12.5 kHz.")):
            r.press(key)
            self.assertEqual(r.model.message, words, key)
        r = sized("face", announce="message")
        r.press("pgup")
        self.assertEqual(r.model.message, "Band A 147.140 MHz.")

    def test_the_list_says_the_row_with_announce_message_only(self):
        r = sized("list")
        r.press("down")
        self.assertEqual(r.model.message, "PTT unlocked")
        r.press("s")
        self.assertEqual(r.model.message, "Step 10 kHz")
        r.press("right")
        self.assertEqual(r.model.message, "Step 12.5 kHz")
        r = sized("list", announce="cursor")
        r.press("down", "s", "right")
        self.assertEqual(r.model.message, "")
        r.press("x")
        self.assertEqual(r.model.message, "No control starts with x.")

    def test_list_steps_and_ends(self):
        r = sized("list")
        r.press("a", "right")
        self.assertEqual(r.model.focused().name, "A frequency")
        self.assertEqual(r.daemon.sim.freq[0], 147050000)
        r.press("]")
        self.assertEqual(r.daemon.sim.freq[0], 147150000)
        r.press("down", "down")
        self.assertEqual(r.model.focused().name, "A squelch")
        r.press("right")
        self.assertEqual(r.daemon.sim.sq[0], 7)
        r.press("s")
        self.assertEqual(r.model.focused().name, "Set the radio clock")
        r.press("right")
        self.assertEqual(r.model.message, "Enter does what this row says.")
        r.press("v", "v")
        self.assertEqual(r.model.message, "VOX off")
        r.press("right")
        self.assertEqual(r.model.message, sm.VOX_WORDS)
        r.press("g", "right")
        self.assertEqual(r.daemon.sim.gp, [1, 1])
        r.press("right")
        self.assertEqual(r.model.message, "GPS output is already on.")
        r.press("space")
        self.assertEqual(r.daemon.sim.gp, [1, 0])
        r.press("d", "enter")
        self.assertEqual(r.model.message, "Daemon cannot be set here.")

    def test_typing_a_frequency(self):
        r = sized("face")
        r.press(*"146.52", "enter")
        self.assertEqual(r.daemon.sim.freq[0], 146520000)
        r.press("tab", *"145", "esc")
        self.assertEqual(r.daemon.sim.freq[1], 144390000)
        r.press(*"1x5", "enter")
        self.assertEqual(r.model.mode, sm.TYPING)
        self.assertTrue(r.model.message.startswith("Not a frequency"))

    def test_unbound_letters(self):
        r = sized("face")
        r.press("z")
        self.assertEqual(r.model.message, "Nothing on z. ? lists the keys.")
        r.press("Z")
        self.assertEqual(r.model.message, "Nothing on capital Z. Is Caps Lock on?")

    def test_help(self):
        for view in sm.VIEWS:
            r = sized(view)
            r.press("?")
            self.assertEqual(r.model.mode, sm.HELP)
            frame = r.frame(80, 24)
            self.assertEqual(frame.rows[1], r.model.help_rows()[0])
            r.press("down")
            self.assertEqual(r.frame(80, 24).cursor, (2, 0))
            r.press("esc")
            self.assertEqual(r.model.mode, sm.MAIN)
            r.press("?", "?")
            self.assertEqual(r.model.mode, sm.MAIN)

    def test_memory(self):
        r = sized("face")
        todos = r.press("M")
        reads = [t for t in todos if isinstance(t, sm.MemoryRead)]
        self.assertEqual(reads[0], sm.MemoryRead(0, 9))
        r.tick(3)
        reads = [t for t in r.done if isinstance(t, sm.MemoryRead)]
        self.assertEqual(len(reads), 20)
        self.assertTrue(all(t.last - t.first == 9 for t in reads))
        self.assertEqual(r.model.message, "2 memory channels in 000 to 199.")
        frame = r.frame(80, 24)
        self.assertEqual(frame.rows[1], "000 146.520 MHz FM, offset 0.000 MHz")
        self.assertEqual(frame.rows[-1], sm.MEMORY_HINT)
        r.press("down", "enter")
        self.assertEqual(r.model.mode, sm.MAIN)
        self.assertEqual(r.model.message, "Band A on channel 001.")
        self.assertEqual(r.daemon.sim.freq[0], 144390000)
        self.assertEqual(r.model.bands[0].vm, 1)
        r.press("C")
        self.assertEqual(r.model.mode, sm.MEMORY)
        todos = r.press("R")
        self.assertIn(sm.MemoryRead(0, 9), todos)
        r.tick(3)
        self.assertEqual(len(r.model.channels), 2)
        self.assertEqual(r.model.message, "2 memory channels in 000 to 199.")
        r.press("M")
        self.assertEqual(r.model.mode, sm.MAIN)

    def test_memory_none_found(self):
        r = sized("face")
        r.daemon.sim.mem.clear()
        r.press("C")
        r.tick(3)
        self.assertEqual(r.model.message, sm.NO_MEMORY)
        self.assertEqual(r.frame(80, 24).rows[1], sm.NO_MEMORY)

    def test_tools(self):
        r = sized("face", workspace=True)
        r.press("x")
        self.assertEqual(r.carrier.tools[-1], sm.Tool("chat", ("xarachat", "--tui"), False, "varac"))
        self.assertEqual(r.model.message, "Chat opened. F9 comes back here.")
        r.press("x")
        self.assertEqual(r.model.message, "Chat window. F9 comes back here.")
        r.press("o")
        self.assertEqual(r.model.message, "Xarachat is in chat. /varac on there.")
        r.press("r")
        self.assertEqual(r.carrier.tools[-1].argv, ("radiogram", "new"))
        r = sized("face", installed=())
        r.press("x")
        self.assertEqual(r.model.message, "Chat is not installed.")
        r = sized("face")
        r.press("o")
        self.assertEqual(r.carrier.tools[-1].argv, ("xarachat", "--tui", "--varac", "yes"))
        self.assertEqual(r.model.message, "VarAC chat ended.")
        r = sized("face", varac="openslot")
        r.press("o")
        self.assertEqual(r.carrier.tools[-1].argv, ("openslot", "--tui"))

    def test_sstv_and_rtty_receive(self):
        r = sized("face")
        r.press("S", "r", "enter")
        self.assertEqual(r.carrier.tools[-1].argv, ("d750-sstv", "rx", "150"))
        r.press("R", "r", *"30", "enter")
        self.assertEqual(r.carrier.tools[-1].argv, ("d750-rtty", "rx", "30"))
        r.press("S", "r", "esc")
        self.assertEqual(r.model.mode, sm.MAIN)

    def test_a_typed_value_reaches_the_tool_whole(self):
        r = sized("face")
        r.press("S", "s", *"~/pic_1.png", "enter")
        self.assertEqual(r.model.frame(80, 24).rows[-1], "SSTV mode, ROBOT 36:")
        r.press(*"martin 1", "enter")
        self.assertEqual(r.model.message, "Picture pic?1.png, mode MARTIN 1.")
        self.assertEqual(r.model.question_text(), "Send the picture on band B? y or n")
        r.press("y")
        self.assertEqual(r.carrier.tools[-1].argv, ("d750-sstv", "tx", "~/pic_1.png", "MARTIN_1"))


class Questions(Frames):
    def question(self, keys, text, view="face", **kw):
        r = sized(view, **kw)
        r.press(*keys)
        self.assertEqual(r.model.mode, sm.ASKING, keys)
        frame = r.frame(80, 24)
        self.assertEqual(frame.rows[-1], text)
        self.assertEqual(frame.cursor, (23, len(text)))
        return r

    def cases(self):
        """(keys that ask, the question, the no words, what y gives)."""
        return (
            (("L", "L"), "Unlock PTT? y or n", "Still locked.", lambda t: sets(t) == ["unlock"]),
            (("t",), "TNC to off on band B? y or n", "TNC unchanged.", lambda t: sets(t) == ["TN 0,1"]),
            (("k",), "Set the radio clock from here? y or n", "Clock unchanged.",
             lambda t: any(isinstance(x, sm.Clock) for x in t)),
            (("c", "c"), "Send one CQ frame on band B? y or n", "Nothing sent.",
             lambda t: sm.SendFrame(False) in t),
            (("c", "b"), "Send one beacon on band B? y or n", "Nothing sent.", lambda t: sm.SendFrame(True) in t),
            (("S", "s", *"a.png", "enter", "enter"), "Send the picture on band B? y or n", "Nothing sent.",
             lambda t: any(isinstance(x, sm.Tool) and "tx" in x.argv for x in t)),
            (("R", "s", *"cq", "enter"), "Send this text on band B? y or n", "Nothing sent.",
             lambda t: any(isinstance(x, sm.Tool) and "tx" in x.argv for x in t)),
        )

    def test_only_small_y_says_yes(self):
        for keys, text, no, yes in self.cases():
            for answer in ("Y", "n", "N", "x", "enter", "esc", "space", "1", "c", "s"):
                r = self.question(keys, text)
                start = len(r.done)
                r.press(answer)
                after = r.done[start:]
                self.assertFalse(yes(after), (keys, answer))
                self.assertFalse(any(isinstance(x, (sm.SendFrame, sm.Clock)) for x in after), (keys, answer))
                self.assertEqual(sets(after), [], (keys, answer))
                self.assertEqual(r.model.message, no, (keys, answer))
                self.assertEqual(r.model.mode, sm.MAIN)
            r = self.question(keys, text)
            start = len(r.done)
            r.press("y")
            self.assertTrue(yes(r.done[start:]), keys)

    def test_each_question_is_cancelled_by_a_too_small_window(self):
        for keys, text, no, _yes in self.cases():
            r = self.question(keys, text)
            r.model.size(30, 5)
            self.assertEqual((r.model.mode, r.model.message), (sm.MAIN, no), keys)
            start = len(r.done)
            r.press("y")
            self.assertEqual(r.done[start:], [])

    def test_the_view_question(self):
        r = self.question(("V",), sm.VIEW_QUESTION, view="list")
        r.press("Y")
        self.assertEqual((r.model.view, r.model.message), ("list", sm.STILL_THE_LIST))
        r = self.question(("V",), sm.VIEW_QUESTION, view="list")
        r.model.size(30, 5)
        self.assertEqual(r.model.message, sm.STILL_THE_LIST)

    def test_the_frame_takes_two_steps_and_c_twice_sends_nothing(self):
        r = self.question(("c",), sm.FRAME_QUESTION)
        r.press("c")
        self.assertEqual(r.carrier.frames, [])
        r.press("c")
        self.assertEqual(r.carrier.frames, [])
        self.assertEqual(r.model.message, "Nothing sent.")
        r.press("c", "x")
        self.assertEqual(r.model.message, "Nothing sent.")
        r.press("c", "c", "y")
        self.assertEqual(r.carrier.frames, [sm.SendFrame(False)])
        self.assertEqual(r.model.message, "CQ frame handed to xara.")
        r = sized("face", xara_answers=False)
        r.press("c", "b", "y")
        self.assertEqual(r.model.message, "Xara does not answer on port 8300.")

    def test_the_frame_and_sends_are_refused_while_locked_and_the_frame_without_mycall(self):
        r = sized("face")
        r.press("L")
        self.assertTrue(r.model.locked)
        for keys in (("c",), ("S", "s"), ("R", "s")):
            r.press(*keys)
            self.assertEqual((r.model.mode, r.model.message), (sm.MAIN, sm.LOCKED_NOTHING_SENT), keys)
        for call in ("", "N0CALL", "n0call"):
            r = sized("face", mycall=call)
            r.press("c")
            self.assertEqual((r.model.mode, r.model.message), (sm.MAIN, sm.NO_MYCALL))

    def test_a_send_question_is_refused_if_locked_before_y(self):
        r = self.question(("c", "c"), "Send one CQ frame on band B? y or n")
        r.model.locked = True
        r.press("y")
        self.assertEqual(r.carrier.frames, [])

    def test_the_quit_question(self):
        r = sized("face", workspace=True, windows=("chat", "varac"))
        r.tick(2.5)
        r.press("q")
        self.assertEqual(r.model.message, "Windows open: chat, varac.")
        self.assertEqual(r.model.question_text(), sm.QUIT_QUESTION)
        r.press("x")
        self.assertEqual(r.model.message, "Still here.")
        todos = r.press("q", "n")
        self.assertEqual([t for t in todos if isinstance(t, (sm.Quit, sm.CloseWorkspace))], [sm.Quit()])
        todos = r.press("Q", "y")
        self.assertEqual([t for t in todos if isinstance(t, (sm.Quit, sm.CloseWorkspace))],
                         [sm.Quit(), sm.CloseWorkspace()])
        r = sized("face")
        self.assertEqual(r.press("q"), [sm.Quit()])

    def test_a_state_answer_sent_before_a_lock_answer_never_undoes_it(self):
        for before, keys, after in ((False, ("L",), True), (True, ("L", "y"), False)):
            r = Runner(start=False, view="face")
            m = r.model
            m.size(80, 24)
            r.daemon.locked = before
            ask = m.start()[0]
            m.finished(ask, r.carrier.carry(ask), None, "")
            self.assertEqual(m.locked, before)
            m.tick(1000.0)
            state = asks(m.tick(1000.6), "state")[0]
            old = r.carrier.carry(state)  # read before the lock word, answered after it
            todos = []
            for key in keys:
                todos = m.key(key)
            lock = [t for t in todos if isinstance(t, sm.Set)][0]
            self.assertEqual(lock.line, "lock" if after else "unlock")
            m.finished(lock, r.carrier.carry(lock), None, "")
            self.assertEqual(m.locked, after)
            waited = asks(m.finished(state, old, None, ""))
            self.assertEqual(m.locked, after, "a state answer from before undid the lock")
            self.assertEqual(m.status(), "d750ctrl. Receiving. PTT locked." if after else "d750ctrl. Receiving. Unlocked.")
            if after:
                self.assertEqual(m.key("L"), [], "L asks to unlock, and does not lock twice")
                self.assertEqual(m.asked, "unlock")
                m.key("esc")
                self.assertEqual(m.key("c"), [])
                self.assertEqual(m.message, sm.LOCKED_NOTHING_SENT)
            self.assertEqual([a.why for a in waited], ["sweep"], "the sweep after the lock waited its turn")
            m.finished(waited[0], r.carrier.carry(waited[0]), None, "")
            self.assertEqual(m.locked, after, "a state read sent after the lock answer is taken")
            r.daemon.locked = before
            later = []
            for i in range(1, 60):
                later = asks(m.tick(1000.6 + i * 0.1))
                if later:
                    break
            self.assertIn("state", later[0].lines)
            m.finished(later[0], r.carrier.carry(later[0]), None, "")
            self.assertEqual(m.locked, before, "a later state read still changes the lock")

    def test_lock_locks_at_once_and_unlock_asks(self):
        r = sized("face")
        todos = r.press("L")
        self.assertEqual(sets(todos), ["lock"])
        self.assertEqual(r.model.message, "PTT locked.")
        self.assertTrue(r.daemon.locked)
        r.press("L", "y")
        self.assertFalse(r.daemon.locked)
        self.assertEqual(r.model.message, "PTT unlocked.")


class Safety(Frames):
    """The safety rules for keys, each with a test."""

    def test_a_too_small_window_lets_only_these_keys_act(self):
        for view in sm.VIEWS:
            r = sized(view, 30, 5)
            for key in ("up", "down", "p", "m", "c", "y", "enter", "space", ":", "?", "C", "S", "R", "V", "1",
                        "tab", "k", "t", "g", "x", "o", "r", "[", "]", "esc", "s"):
                self.assertEqual(r.press(key), [], (view, key))
            m = r.model
            self.assertEqual(m.key("U"), [sm.Unkey()])
            self.assertEqual(m.key("L"), [sm.Set("lock")])
            m.locked = True
            self.assertEqual(m.key("L"), [], "lock does nothing when locked")
            self.assertEqual(m.key("ctrl-l"), [sm.Redraw()])
            self.assertEqual(m.key("Q"), [sm.Quit()])
            self.assertEqual(m.key("ctrl-c"), [sm.Quit()])

    def test_a_letter_typed_in_a_value_never_quits_when_the_window_shrinks(self):
        for view in sm.VIEWS:
            r = sized(view)
            r.press(":")
            r.model.size(30, 5)
            for key in ("Q", "q", "U", "L", "y"):
                self.assertEqual(r.press(key), [], (view, key))
            r.model.size(80, 24)
            self.assertEqual(r.model.mode, sm.TYPING)

    def test_a_raw_command_that_can_key_or_move_is_refused(self):
        for head in UNSAFE_HEADS:
            for typed in (head, head.lower(), head[0] + head[1].lower(), f"{head} 1", f"{head.lower()}x,1", f"  {head}"):
                r = sized("face")
                r.press(":")
                r.type(typed)
                todos = r.press("enter")
                self.assertEqual(sets(todos), [], typed)
                self.assertEqual(r.model.message, f"Refused: {head} can key or move the radio.", typed)

    def test_a_raw_command_with_a_daemon_word_is_refused(self):
        for typed, words in (("lock", "Refused. Capital L locks and unlocks."),
                             ("UNLOCK", "Refused. Capital L locks and unlocks."),
                             ("Lock now", "Refused. Capital L locks and unlocks."),
                             ("quit", "Refused: quit is the daemon's own word."),
                             ("Reconnect", "Refused: reconnect is a daemon word.")):
            r = sized("face")
            r.press(":")
            r.type(typed)
            self.assertEqual(sets(r.press("enter")), [], typed)
            self.assertEqual(r.model.message, words)
        r = sized("face", keymap=km.Keymap([(1, "lock", "F7")]))
        r.press(":")
        r.type("lock")
        r.press("enter")
        self.assertEqual(r.model.message, "Refused. F7 locks and unlocks.")

    def test_every_other_raw_line_goes_as_typed(self):
        r = sized("face")
        r.press(":")
        r.type("fv")
        todos = r.press("enter")
        self.assertEqual(sets(todos), ["fv"])
        self.assertEqual(r.model.message, "Answer: FV 1.03")
        self.assertEqual(r.model.log[-1][1:], ("fv", "FV 1.03"))

    def test_unkey_and_lock_never_wait_behind_a_read(self):
        r = Runner(start=False, view="face")
        m = r.model
        m.start()
        self.assertIsNotNone(m._out)
        self.assertEqual(m.key("U"), [sm.Unkey()])
        self.assertEqual(m.key("L"), [sm.Set("lock")])
        m.key("C")
        self.assertEqual(m.key("esc"), [])
        self.assertEqual(m.key("u"), [sm.Unkey()])

    def test_unkey_words(self):
        r = sized("face")
        r.press("u")
        self.assertEqual(r.model.message, "Unkey sent.")
        r.daemon.answering = False
        r.press("u")
        self.assertTrue(r.model.message.startswith("Unkey failed: ERR"), r.model.message)

    def walk_checks(self, r, key, before_mode, before_question, todos, small):
        for t in todos:
            if isinstance(t, sm.SendFrame):
                self.assertEqual((before_mode, before_question, key), (sm.ASKING, "frame_send", "y"), "SendFrame")
            if isinstance(t, sm.Tool) and "tx" in t.argv:
                self.assertIn(before_question, ("sstv_send", "rtty_send"))
                self.assertEqual((before_mode, key), (sm.ASKING, "y"))
            if isinstance(t, sm.Set):
                self.assertNotIn(t.line.strip()[:2].upper(), UNSAFE_HEADS, t.line)
                word = t.line.strip().split()[0].lower() if t.line.strip() else ""
                self.assertNotIn(word, ("quit", "reconnect"), t.line)
                if word in ("lock", "unlock"):
                    self.assertEqual(t.line, word, "a lock word only as the program's own")
                if word == "unlock":
                    self.assertEqual((before_mode, before_question, key), (sm.ASKING, "unlock", "y"))
        if small:
            allowed = (sm.Quit, sm.Unkey, sm.Redraw)
            first = todos[:1]
            for t in first:
                self.assertTrue(isinstance(t, allowed) or t == sm.Set("lock"), (key, t))

    def walk_paste(self, r, rng, width, height):
        """A paste in the walk: no thing to do ever; outside typing, nothing but the message changes."""
        m = r.model
        text = "".join(rng.choice("yYnNcbrsLUuqQ1. :\x01~_") for _ in range(rng.randint(0, 12)))
        typing = m.mode == sm.TYPING and sm.shows(m.view, width, height) is not None
        state = (m.mode, m.question, m.asked, m.focus, m.active, m.view, m.typed, m.help_focus, m.mem_focus)
        frame = m.frame(width, height)
        self.assertEqual(m.paste(text, rng.random() < 0.3), [], "a paste returned a thing to do")
        if typing:
            self.assertEqual((m.mode, m.question), (sm.TYPING, 0))
            self.assertTrue(m.typed.startswith(state[6]))
        else:
            after = (m.mode, m.question, m.asked, m.focus, m.active, m.view, m.typed, m.help_focus, m.mem_focus)
            self.assertEqual(after, state, "a paste changed something outside typing mode")
            self.assertEqual(m.message, sm.PASTE_DROPPED)
            self.assertEqual(differs_only_in_message(frame, m.frame(width, height), height), True)
        self.check_frame(m, width, height)

    def walk(self, view, keymap, seed):
        rng = random.Random(seed)
        pool = ["up", "down", "left", "right", "pgup", "pgdn", "home", "end", "enter", "esc", "space", "tab",
                "backspace", "y", "y", "y", "n", "c", "b", "s", "r", "t", "k", "q", "Q", "L", "U", "u", "V", "?",
                ":", "C", "M", "S", "R", "p", "m", "v", "g", "x", "o", "[", "]", "-", "+", "=", "1", ".", "a",
                "T", "X", "f12", "ctrl-l", "~", "_", "/"]
        sizes = ((80, 24), (60, 12), (40, 6), (30, 5), (40, 8), (132, 50), (80, 12))
        r = sized(view, 80, 24, keymap=keymap, workspace=rng.random() < 0.5, windows=("chat",))
        width, height = 80, 24
        for step in range(600):
            if rng.random() < 0.05:
                width, height = rng.choice(sizes)
                r.model.size(width, height)
            if rng.random() < 0.1:
                r.tick(rng.choice((0.1, 0.5, 1.0)))
                continue
            key = rng.choice(pool)
            if key == "ctrl-c":
                continue
            if rng.random() < 0.08:
                self.walk_paste(r, rng, width, height)
                continue
            before = (r.model.mode, r.model.asked)
            small = sm.shows(r.model.view, width, height) is None
            out_before = r.model._out
            number = r.model.question
            early = rng.random() < 0.2
            todos = r.model.key(key, early=early)
            if out_before is not None:
                self.assertEqual(asks(todos), [], "a read while one was out")
            keeps = r.model.keymap.action(r.model.family, key) in ("unkey", "lock") or key == "ctrl-l"
            if early and before[0] == sm.ASKING and not small and not keeps:
                self.assertEqual(todos, [], ("an early key acted in a question", key))
                self.assertEqual((r.model.mode, r.model.question), (sm.ASKING, number), "an early key ended it")
            self.assertEqual(r.model.question != 0, r.model.mode == sm.ASKING, "question is 0 outside a question")
            self.walk_checks(r, key, before[0], before[1], todos, small)
            start = len(r.done)
            r.run([t for t in todos if not isinstance(t, sm.Quit)])
            for t in r.done[start:]:
                if isinstance(t, sm.SendFrame) or (isinstance(t, sm.Tool) and "tx" in t.argv):
                    self.assertIn(t, todos, "a transmit came from a result, not from a key")
            r.model.size(width, height)
            self.check_frame(r.model, width, height)

    def test_a_random_walk_in_every_view_keeps_every_rule(self):
        for view in sm.VIEWS:
            for seed in range(3):
                with self.subTest(view=view, seed=seed):
                    self.walk(view, None, seed)

    def test_a_random_walk_with_a_remapped_keymap(self):
        rng = random.Random(7)
        actions = sorted(set(km.ACTIONS["list"]) | set(km.ACTIONS["face"]))
        names = ["k", "j", "h", "y", "n", "Y", "c", "b", "r", "s", "enter", "space", "tab", "up", "f5", "L", "U", "u"]
        for view in sm.VIEWS:
            for seed in range(3):
                changes = [(i, rng.choice(actions), ", ".join(rng.sample(names, rng.randint(1, 3))))
                           for i in range(12)]
                keymap = km.Keymap(changes)
                for family in ("list", "face"):
                    self.assertTrue(keymap.keys(family, "unkey"))
                    self.assertTrue(keymap.keys(family, "lock"))
                    for answer in ("y", "n", "Y", "N"):
                        self.assertIsNone(keymap.action(family, answer))
                with self.subTest(view=view, seed=seed):
                    self.walk(view, keymap, 100 + seed)


class Review(Frames):
    """The rulings after the first safety review."""

    def test_an_early_key_answers_nothing_in_a_question(self):
        for keys in (("c",), ("c", "c"), ("k",), ("L", "L"), ("t",), ("S",), ("S", "s", *"a.png", "enter", "enter"),
                     ("R", "s", *"cq", "enter")):
            r = sized("face")
            r.press(*keys)
            self.assertEqual(r.model.mode, sm.ASKING, keys)
            number = r.model.question
            for answer in ("y", "c", "b", "r", "s", "n", "enter"):
                self.assertEqual(r.model.key(answer, early=True), [], (keys, answer))
                self.assertEqual((r.model.mode, r.model.question), (sm.ASKING, number), (keys, answer))
            self.assertEqual(r.model.message, sm.TOO_FAST)
            r.model.message = ""
            r.model.key("y", early=True)
            self.assertEqual(r.model.message, "", "Too fast is said once a question")
            self.assertEqual(r.carrier.frames, [])
            self.assertFalse(any(isinstance(t, sm.Tool) and "tx" in t.argv for t in r.carrier.tools))
            self.assertEqual(r.model.key("ctrl-c", early=True), [sm.Quit()])

    def test_early_unkey_and_lock_are_never_dropped(self):
        r = sized("face")
        r.press("c", "c")
        self.assertEqual(r.model.key("u", early=True), [sm.Unkey()])
        self.assertEqual((r.model.mode, r.model.message), (sm.MAIN, sm.NOTHING_SENT))
        r.press("k")
        self.assertEqual(r.model.key("L", early=True), [sm.Set("lock")])
        self.assertEqual(r.model.mode, sm.MAIN)

    def test_urgent_names_the_keys_of_unkey_and_lock(self):
        face, listed = sized("face").model, sized("list").model
        for key in ("U", "u", "L"):
            self.assertTrue(face.urgent(key), key)
        for key in ("U", "L"):
            self.assertTrue(listed.urgent(key), key)
        for key in ("u", "q", "Q", "y", "c", "enter", "ctrl-c", "esc", "1", "tab"):
            self.assertFalse(listed.urgent(key), key)
        for key in ("q", "Q", "y", "n", "c", "enter", "ctrl-c", "esc", "1", "tab", "x"):
            self.assertFalse(face.urgent(key), key)
        keymap = km.Keymap([(1, "unkey", "F5, k"), (2, "lock", "j")])
        for view in ("face", "list", "compact"):
            r = sized(view, keymap=keymap)
            m = r.model
            for mode_keys in ((), ("?",), (":",)):
                if mode_keys:
                    r.press(*mode_keys)
                self.assertTrue(m.urgent("f5") and m.urgent("k") and m.urgent("j"), (view, mode_keys))
                self.assertFalse(m.urgent("U") or m.urgent("L") or m.urgent("u"), (view, mode_keys))
                r.press("esc")
        r = sized("face", keymap=keymap)
        r.press("c", "c")
        self.assertTrue(r.model.urgent("k"))
        self.assertEqual(r.model.key("k", early=True), [sm.Unkey()])
        self.assertEqual((r.model.mode, r.model.message), (sm.MAIN, sm.NOTHING_SENT))
        r.press("t")
        self.assertEqual(r.model.key("j", early=True), [sm.Set("lock")])
        self.assertEqual((r.model.mode, r.model.message), (sm.MAIN, "TNC unchanged."))

    def test_each_question_has_a_new_larger_number(self):
        r = sized("face")
        self.assertEqual(r.model.question, 0)
        seen = []
        for keys in (("c",), ("c",), ("k",), ("t",)):
            r.press(*keys)
            seen.append(r.model.question)
            if keys == ("c",) and len(seen) == 2:
                r.press("c")
                seen.append(r.model.question)
            r.press("esc")
            self.assertEqual(r.model.question, 0)
        self.assertEqual(seen, sorted(set(seen)), "each question, the second frame question too, is new and larger")
        self.assertGreater(seen[0], 0)

    def test_unkey_and_lock_act_in_help_memory_and_questions_but_not_typing(self):
        for keys in (("?",), ("C",)):
            r = sized("face")
            r.press(*keys)
            mode = r.model.mode
            self.assertEqual(r.model.key("U"), [sm.Unkey()], keys)
            self.assertEqual(r.model.key("L"), [sm.Set("lock")], keys)
            self.assertEqual(r.model.mode, mode, "help and memory stay")
            r.model.locked = True
            self.assertEqual(r.model.key("L"), [], "lock does nothing when locked")
        r = sized("list")
        r.press("?")
        self.assertEqual(r.model.key("U"), [sm.Unkey()])
        self.assertEqual(r.model.key("u"), [], "u is not unkey in the list")
        for keys, no in ((("k",), "Clock unchanged."), (("t",), "TNC unchanged."), (("c",), sm.NOTHING_SENT)):
            r = sized("face")
            r.press(*keys)
            self.assertEqual(r.model.key("U"), [sm.Unkey()], keys)
            self.assertEqual((r.model.mode, r.model.message), (sm.MAIN, no), keys)
        r = sized("face")
        r.press("L", "L")
        self.assertEqual(r.model.key("L"), [], "lock in the unlock question answers no")
        self.assertEqual((r.model.mode, r.model.message, r.daemon.locked), (sm.MAIN, sm.STILL_LOCKED, True))
        r = sized("face")
        r.press(":")
        self.assertEqual(r.model.key("U"), [])
        self.assertEqual(r.model.key("L"), [])
        self.assertEqual(r.model.typed, "UL", "in typing they are text")

    def test_sends_are_refused_while_the_lock_is_not_known(self):
        r = Runner(start=False, view="face")
        m = r.model
        m.size(80, 24)
        for keys in (("c",), ("S", "s"), ("R", "s")):
            for key in keys:
                m.key(key)
            self.assertEqual((m.mode, m.message), (sm.MAIN, sm.UNKNOWN_NOTHING_SENT), keys)
        r = sized("face")
        r.press("c", "c")
        r.daemon.answering = False
        r.tick(0.6)
        self.assertTrue(r.model.no_daemon)
        r.press("y")
        self.assertEqual(r.carrier.frames, [])
        self.assertEqual(r.model.message, sm.UNKNOWN_NOTHING_SENT)
        for keys in (("c",), ("S", "s"), ("R", "s")):
            r.press(*keys)
            self.assertEqual((r.model.mode, r.model.message), (sm.MAIN, sm.UNKNOWN_NOTHING_SENT), keys)

    def test_raw_vox_and_tnc_sets_are_refused(self):
        for typed in ("VX 1", "vx 2", "VX1", " vx 9", "VX 00"):
            r = sized("face")
            r.press(":")
            r.type(typed)
            self.assertEqual(sets(r.press("enter")), [], typed)
            self.assertEqual(r.model.message, sm.VOX_REFUSED)
        for typed in ("VX", "VX 0", "vx"):
            r = sized("face")
            r.press(":")
            r.type(typed)
            self.assertEqual(sets(r.press("enter")), [typed], typed)
        for typed in ("TN 1,0", "tn 0,0", "TN2,1", "TN 0"):
            r = sized("face")
            r.press(":")
            r.type(typed)
            self.assertEqual(sets(r.press("enter")), [], typed)
            self.assertEqual(r.model.message, "Refused. The t key changes the TNC.")
        r = sized("face")
        r.press(":")
        r.type("TN")
        self.assertEqual(sets(r.press("enter")), ["TN"])
        r = sized("face", keymap=km.Keymap([(1, "act_tnc", "T")]))
        r.press(":")
        r.type("TN 1,1")
        r.press("enter")
        self.assertEqual(r.model.message, "Refused. The T key changes the TNC.", "capital T would pass 40 cells")
        for keymap, view in ((km.Keymap([(1, "act_tnc", "none")]), "face"), (None, "list")):
            r = sized(view, keymap=keymap)
            r.press(":")
            r.type("TN 1,1")
            r.press("enter")
            self.assertEqual(r.model.message, "Refused. The TNC mode row changes it.")

    def test_a_frame_port_that_is_not_a_number_refuses_the_frame(self):
        r = sized("face", xara_port=None)
        self.assertEqual(r.press("c"), [])
        self.assertEqual((r.model.mode, r.model.message), (sm.MAIN, sm.NO_XARA_PORT))
        self.assertEqual(r.carrier.frames, [])
        r = sized("face", xara_port=8301, xara_answers=False)
        r.press("c", "c", "y")
        self.assertEqual(r.model.message, "Xara does not answer on port 8301.")

    def test_a_family_only_key_in_a_too_small_list_window(self):
        r = sized("list", 30, 5)
        for key in ("q", "u"):
            self.assertEqual(r.model.key(key), [], key)
        self.assertEqual(r.model.key("Q"), [sm.Quit()])
        self.assertEqual(r.model.key("U"), [sm.Unkey()])
        r = sized("face", 30, 5)
        self.assertEqual(r.model.key("q"), [sm.Quit()])
        self.assertEqual(r.model.key("u"), [sm.Unkey()])

    def test_enter_on_the_unkey_now_row_returns_unkey_and_nothing_else(self):
        r = sized("list")
        r.model.focus = [row.name for row in sm.ROWS].index("Unkey now")
        self.assertEqual(r.model.key("enter"), [sm.Unkey()])
        self.assertEqual(r.model.mode, sm.MAIN)


class Pastes(Frames):
    """A paste, known by its marks: text in a typing line, dropped everywhere else."""

    def test_a_paste_in_typing_mode_in_each_view(self):
        for view in sm.VIEWS:
            for width, height in ((80, 24), (60, 12), (40, 6)):
                if sm.shows(view, width, height) is None:
                    continue
                r = sized(view, width, height)
                r.press(":", "F")
                self.assertEqual(r.press("paste:V 1.03, y"), [])
                self.assertEqual((r.model.mode, r.model.typed, r.model.question), (sm.TYPING, "FV 1.03, y", 0))
                self.assertEqual(r.model.message, "Pasted 9 characters. Enter applies.")
                self.check_frame(r.model, width, height)
                todos = r.press("enter")
                self.assertEqual(sets(todos), ["FV 1.03, y"], "Enter still applies what was pasted")

    def test_the_paste_words(self):
        r = sized("face")
        r.press(":")
        r.model.paste("x")
        self.assertEqual(r.model.message, "Pasted 1 character. Enter applies.")
        r.model.paste("abc", left_out=True)
        self.assertEqual(r.model.message, "Pasted 3 characters, some left out.")
        r.model.paste("a\x01bé")
        self.assertEqual(r.model.message, "Pasted 2 characters, some left out.")
        r.model.paste("")
        self.assertEqual(r.model.message, "Nothing in the paste.")
        r.model.paste("\x02", left_out=True)
        self.assertEqual(r.model.message, "Nothing in the paste.")
        self.assertEqual(r.model.typed, "xabcab")

    def test_a_paste_at_a_typing_lines_limit(self):
        r = sized("face")
        r.press("R", "s")
        r.model.typed = "x" * (sm.TYPED_MOST - 2)
        r.model.paste("abcd")
        self.assertEqual(len(r.model.typed), sm.TYPED_MOST)
        self.assertEqual(r.model.message, "Pasted 2 characters, some left out.")
        r.model.paste("e")
        self.assertEqual(r.model.message, "Nothing in the paste.")
        self.assertEqual(r.model.mode, sm.TYPING, "nothing applied, no question asked")
        self.assertEqual(r.carrier.tools, [])

    def dropped(self, r, width=80, height=24):
        m = r.model
        m.size(width, height)
        state = (m.mode, m.question, m.asked, m.focus, m.active, m.view, m.typed, m.help_focus, m.mem_focus)
        frame = m.frame(width, height)
        start = len(r.done)
        self.assertEqual(m.paste("y\n y c b r s U L q Q 1 enter"), [])
        self.assertEqual(r.done[start:], [])
        after = (m.mode, m.question, m.asked, m.focus, m.active, m.view, m.typed, m.help_focus, m.mem_focus)
        self.assertEqual(after, state)
        self.assertEqual(m.message, sm.PASTE_DROPPED)
        self.assertTrue(differs_only_in_message(frame, m.frame(width, height), height))

    def test_a_paste_is_dropped_in_main_help_memory_and_too_small(self):
        for view in sm.VIEWS:
            for keys in ((), ("?",), ("C",), ("down",)):
                r = sized(view)
                r.press(*keys)
                self.dropped(r)
            r = sized(view)
            r.press(":", "F")
            self.dropped(r, 30, 5)
            self.assertEqual(r.model.typed, "F", "too small: not even a typing line takes it")

    def test_a_paste_never_answers_a_question(self):
        asks_of = [keys for keys, *_ in Questions.cases(Questions())]
        asks_of += [("S",), ("R",), ("c",)]
        for keys in asks_of:
            r = sized("face")
            r.press(*keys)
            self.assertEqual(r.model.mode, sm.ASKING, keys)
            self.dropped(r)
            self.assertEqual(r.carrier.frames, [])
        r = sized("list")
        r.press("V")
        self.dropped(r)
        r = sized("face", workspace=True, windows=("chat",))
        r.tick(2.5)
        r.press("q")
        self.dropped(r)

    def test_unkeys_and_unkey_now(self):
        face, listed = sized("face").model, sized("list").model
        self.assertTrue(face.unkeys("U") and face.unkeys("u") and listed.unkeys("U"))
        for key in ("L", "q", "y", "enter"):
            self.assertFalse(face.unkeys(key) or listed.unkeys(key), key)
        self.assertFalse(listed.unkeys("u"))
        remapped = sized("face", keymap=km.Keymap([(1, "unkey", "F5")])).model
        self.assertTrue(remapped.unkeys("f5"))
        self.assertFalse(remapped.unkeys("U"))
        for keys in ((":", "A", "B"), ("c", "c"), ("?",), ("C",), ()):
            r = sized("face")
            r.press(*keys)
            m = r.model
            state = (m.mode, m.question, m.asked, m.typed)
            self.assertEqual(m.unkey_now(), [sm.Unkey()], keys)
            self.assertEqual((m.mode, m.question, m.asked, m.typed), state, keys)


def why(trace):
    """A failure in one line: the test file's line number and the error's first words."""
    found = re.findall(r'File "[^"]*screen-model-test\.py", line (\d+)', trace)
    text = trace.strip().splitlines()
    error = next((i for i in range(len(text) - 1, -1, -1) if re.match(r"^[A-Za-z.]*(Error|Exception)\b", text[i])), None)
    words = " / ".join(t.strip() for t in text[error : error + 4]) if error is not None else (text[-1] if text else "")
    return f"line {found[-1] if found else '?'}: " + lines.clean(words.replace("_", "-"), 300)


def main():
    suite = unittest.defaultTestLoader.loadTestsFromModule(sys.modules[__name__])
    result = unittest.TestResult()
    suite.run(result)
    failed = {}
    for test, trace in result.failures + result.errors:
        case = getattr(test, "test_case", test)
        failed.setdefault(case.id().rsplit(".", 1)[-1].replace("_", "-"), why(trace))
    for name, words in failed.items():
        print(f"Fail: {name}: {words}")
    if failed:
        print(f"Fail: {NAME}, {len(failed)} of {result.testsRun} tests.")
        return 1
    print(f"Pass: {NAME}, {result.testsRun} tests.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
