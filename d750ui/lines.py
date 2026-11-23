"""d750ui.lines: the line rules, as code.

A line is one line of plain ASCII words, with the meaning in the first 40 cells, so that
it reads well by ear and on a 40-cell Braille display. problems() says what breaks the
rules; clean() makes text from outside safe to put in a line.

GPL-2.0-or-later.
"""

import re

MARKS = frozenset(".,:;?!'\"()/%+-=")
CLAUSE_ENDS = frozenset(".:;?!")
CELLS = 40  # the meaning fits in this many cells
LONGEST = 80  # no line is longer than this

# The words problems() gives, one for each rule. Tests compare against these.
EMPTY = "the line is empty"
CONTROL = "a line break, tab or control character"
SPACE_START = "a space at the start"
SPACE_END = "a space at the end"
NOT_ALLOWED = "a character that is not allowed"
RULER = "three or more of the same mark in a row"
ARROW = "an arrow"
TWO_HYPHENS = "two hyphens that are not an option name"
NO_CLAUSE = "the meaning does not end by cell 40"


def too_long(limit):
    """The words for a line longer than limit."""
    return f"longer than {limit} characters"


def _allowed(ch):
    return ch == " " or ch in MARKS or ("a" <= ch <= "z") or ("A" <= ch <= "Z") or ("0" <= ch <= "9")


def _is_control(ch):
    return ord(ch) < 0x20 or ord(ch) == 0x7F


def _hyphen_pairs_ok(line):
    """Two hyphens pass only at the start of a word, before a small letter: --user."""
    for match in re.finditer(r"(?<!-)--(?!-)", line):
        start, end = match.start(), match.end()
        at_word_start = start == 0 or line[start - 1] == " "
        before_small = end < len(line) and "a" <= line[end] <= "z"
        if not (at_word_start and before_small):
            return False
    return True


def _is_label(text):
    """One or two words, as before the colon in "Fail:" or "Would send:"."""
    words = text.split(" ")
    return 1 <= len(words) <= 2 and all(w and all(c.isalnum() or c in "-'" for c in w) for w in words)


def _clause_ends_by_cell_40(line):
    for i in range(min(len(line) - 1, CELLS)):
        if line[i] in CLAUSE_ENDS and line[i + 1] == " ":
            if line[i] == ":" and _is_label(line[:i]):
                continue
            return True
    return False


def problems(line, limit=LONGEST):
    """A list of words saying what breaks the line rules; empty when the line is fine.

    With limit=40 the line must be 40 characters or fewer: the check for screen rows.
    With a larger limit a line longer than 40 passes only when a clause ends by cell 40.
    No line passes above 80, whatever the limit.
    """
    if not isinstance(line, str):
        return ["not text"]
    if line.strip(" ") == "":
        return [EMPTY]
    found = []

    def say(words):
        if words not in found:
            found.append(words)

    for ch in line:
        if _is_control(ch):
            say(CONTROL)
        elif not _allowed(ch):
            say(NOT_ALLOWED)
    if line.startswith(" "):
        say(SPACE_START)
    if line.endswith(" "):
        say(SPACE_END)
    if re.search(r"([.,:;?!'\"()/%+\-=])\1\1", line):
        say(RULER)
    if re.search(r"[-=][<>]|[<>][-=]", line):
        say(ARROW)
    if not _hyphen_pairs_ok(line):
        say(TWO_HYPHENS)
    most = min(limit, LONGEST)
    if len(line) > most:
        say(too_long(most))
    elif len(line) > CELLS and not _clause_ends_by_cell_40(line):
        say(NO_CLAUSE)
    return found


def _tame(text):
    """Shorten what would read as a ruler: runs of a mark to two, stray double hyphens to one."""
    text = re.sub(r"([.,:;?!'\"()/%+\-=])\1{2,}", r"\1\1", text)
    out = []
    i = 0
    while i < len(text):
        if text.startswith("--", i):
            at_word_start = i == 0 or text[i - 1] == " "
            before_small = i + 2 < len(text) and "a" <= text[i + 2] <= "z"
            out.append("--" if at_word_start and before_small else "-")
            i += 2
        else:
            out.append(text[i])
            i += 1
    return "".join(out)


def clean(text, limit=LONGEST, also=""):
    """Text from outside made safe for a line.

    Bytes are read as Latin-1. Control characters and anything the rules do not allow
    become a question mark, runs of spaces become one, the ends are trimmed, and it is
    cut to limit. Runs of three or more of one mark are cut to two and a stray double
    hyphen to one, so the result never reads as a ruler. The result may be empty.

    also names printable ASCII characters to keep as well, for a place the rules make an
    exception for.
    """
    if isinstance(text, (bytes, bytearray)):
        text = bytes(text).decode("latin-1")
    elif not isinstance(text, str):
        text = str(text)
    keep = frozenset(ch for ch in also if " " < ch < "\x7f")
    text = "".join(ch if _allowed(ch) or ch in keep else "?" for ch in text)
    text = re.sub(" {2,}", " ", text).strip(" ")
    text = text[: max(0, limit)].strip(" ")
    return _tame(text).strip(" ")
