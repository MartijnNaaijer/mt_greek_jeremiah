"""Read the published pages back, so the tests can make claims about them.

The pages are generated, self-contained HTML - inline CSS, inline JS, the word
analyses embedded as a JSON array - and machine-regular, so they are parsed here
with regular expressions rather than a DOM. That is a deliberate choice: the
tests should fail when the SHAPE of the output changes, and a forgiving parser
would hide exactly that.

Nothing here imports anything outside the standard library, so the suite runs on
a clone of this repository with no installation:

    python -m unittest discover -s tests -v
"""
import json
import os
import re
import unicodedata

DOCS = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                    "docs")

HEB = re.compile("[א-ת]")
GRK = re.compile("[Ͱ-Ͽἀ-῿]")

SECTION = re.compile(r'<section class="v" id="v(\d+)">(.*?)</section>', re.S)
VN = re.compile(r'<span class="vn">([^<]*)</span>')
BADGE = re.compile(r'<span class="badge([^"]*)"[^>]*>([^<]*)</span>')
ROW = re.compile(r'<tr>(.*?)</tr>', re.S)
CELL = re.compile(r'<td([^>]*)>(.*?)</td>', re.S)
# A Greek word carries no second class, so the space after w is optional:
# <span class="w" data-a="2"> beside <span class="w common" data-a="1">.
WORD = re.compile(r'<span class="w ?([^"]*)"([^>]*)>(.*?)</span>')
POOL = re.compile(r'window\.__A=(\[.*?\]);', re.S)
KQ = re.compile(r'<sup class="kq"')


def chapter_files():
    """Every page that sets text, in reading order. index.html is not one."""
    jer = sorted(f for f in os.listdir(DOCS) if re.fullmatch(r"jer\d\d\.html", f))
    return jer + ["2kings25.html"]


def read(name):
    with open(os.path.join(DOCS, name), encoding="utf-8") as fh:
        return fh.read()


def unescape(t):
    return (t.replace("&amp;", "&").replace("&lt;", "<").replace("&gt;", ">")
             .replace("&quot;", '"').replace("&#39;", "'").replace("&nbsp;", " "))


class Word:
    __slots__ = ("cls", "text", "pool_id", "from_index")

    def __init__(self, cls, attrs, text):
        self.cls = cls
        self.text = unescape(text)
        m = re.search(r'data-a="(\d+)"', attrs)
        self.pool_id = int(m.group(1)) if m else None
        self.from_index = "data-x" in attrs

    def __repr__(self):
        return f"Word({self.cls!r}, {self.text!r})"


class Row:
    """One clause: the masoretic cell, the clause letter, the alexandrian cell
    and Stipp's Greek. A notes row is not a Row; it is kept as `note`."""

    def __init__(self, cells):
        self.mt = [Word(*m.groups()) for m in WORD.finditer(cells[0][1])]
        self.letter = re.sub(r"<[^>]+>", "", cells[1][1]).strip()
        self.og = [Word(*m.groups()) for m in WORD.finditer(cells[2][1])]
        self.greek = [Word(*m.groups()) for m in WORD.finditer(cells[3][1])]
        self.mt_kq = len(KQ.findall(cells[0][1]))
        self.og_kq = len(KQ.findall(cells[2][1]))
        self.raw = cells

    def mt_text(self):
        return " ".join(w.text for w in self.mt)


class Verse:
    def __init__(self, page, vid, body):
        self.page = page
        self.id = vid
        self.ref = VN.search(body).group(1) if VN.search(body) else ""
        self.badges = [(c.strip(), t.strip()) for c, t in BADGE.findall(body)]
        self.rows, self.notes = [], []
        for r in ROW.findall(body):
            cells = CELL.findall(r)
            if len(cells) == 4:
                self.rows.append(Row(cells))
            elif len(cells) == 1 and 'colspan="4"' in cells[0][0]:
                self.notes.append(cells[0][1])
        self.body = body

    @property
    def chapter(self):
        return int(self.ref.split(",")[0]) if "," in self.ref else None

    @property
    def number(self):
        return int(self.id)

    def confirmed(self):
        return any(t == "BHSA ✓" for _, t in self.badges)

    def unconfirmed(self):
        return any(t == "BHSA ?" for _, t in self.badges)

    def mt_words(self):
        return [w for r in self.rows for w in r.mt]

    def og_words(self):
        return [w for r in self.rows for w in r.og]

    def greek_words(self):
        return [w for r in self.rows for w in r.greek]

    def mt_text(self):
        return " ".join(r.mt_text() for r in self.rows if r.mt).strip()

    def consonants(self):
        return "".join(HEB.findall(self.mt_text()))


class Page:
    def __init__(self, name):
        self.name = name
        self.html = read(name)
        self.pool = json.loads(POOL.search(self.html).group(1))
        self.verses = [Verse(name, vid, body)
                       for vid, body in SECTION.findall(self.html)]

    @property
    def title(self):
        m = re.search(r"<title>(.*?)</title>", self.html, re.S)
        return m.group(1).strip() if m else ""


_CACHE = {}


def pages():
    """Every chapter page, parsed once for the whole suite."""
    if not _CACHE:
        for name in chapter_files():
            _CACHE[name] = Page(name)
    return [_CACHE[n] for n in chapter_files()]


def verses():
    return [v for p in pages() for v in p.verses]


def is_hebrew_text(t):
    """Hebrew letters, points, maqqef, sof pasuq and space - nothing else.

    What this rules out is markup leaking into the text: a bracket, an angle,
    a backslash or a Latin letter in the masoretic column means a siglum was
    read as a word.
    """
    for c in t:
        if c.isspace() or c in "־׃":
            continue
        if unicodedata.category(c) == "Mn" and "֑" <= c <= "ׇ":
            continue
        if "א" <= c <= "ת":
            continue
        return False
    return True
