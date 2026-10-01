"""Read Stipp's Textkritische Synopse as TEXT, not as bracket counts.

parse_stipp.py extracts one number per verse - how many words the masoretic
edition has in excess of the alexandrian - and throws the text away. This script
keeps everything: both texts, both sets of brackets, the qualitative variants,
Stipp's marginal cross-references, his parenthetical apparatus, his idiolect
references and his own unretroverted Greek. It is the input to
build_synopse_pages.py, which sets one HTML page per chapter of Jeremiah.

WHAT IS ON A PAGE. The Synopse is landscape, and each printed line is one clause
of the text, laid out in three columns:

     x < 170        the margin: cross-references (-> 14,6a), grammatical notes
                    ((Vb), (Q)), remarks (keine Sgr), and the lemma being
                    discussed, which is itself in Hebrew
     170 - 400      the text, set right-aligned and ending in a clause label
                    (' a 1 ', ' b ') that gives the clause letter and, when it
                    changes, the verse number
     x > 440        Stipp's Greek: the Old Greek as it stands, unretroverted,
                    which is the text his Hebrew retroversion was made from

Y IS UNUSABLE AND X IS ONLY MOSTLY TRUSTWORTHY. The two panels of a page are set
in different coordinate spaces - on the page for Jer 22,1-9 the Greek reports
y = 545 and the Hebrew y = -4279 - so sorting spans by y interleaves the panels
and puts v. 8 above v. 1. Composing the text matrix with the CTM does not help;
the CTM is the identity and the offset is inside the text object. So lines are
NOT reconstructed geometrically. Spans are read in DOCUMENT order, which is
reading order, and a clause ends where its label is emitted - the same thing
parse_stipp.py relies on.

X survives because it is only ever asked which COLUMN a span is in, and the three
are far apart. It is still not exact: pypdf reports the position of the text
object, so where a line sets a margin note and the text in one object, the text
inherits the note's x and looks like margin. Three lines of Jer 3 do this. The
LOOKAHEAD in split_columns() resolves them: a span belongs to the margin only if
the NEXT span is also in the margin, so a run at x=30 ends as soon as the line
jumps to the text column, whatever x the spans themselves claim.

THE MARKUP, and what each piece means for the two columns:

    [ ... ]     masoretic plus       - in the MT column only
    < ... >     alexandrian plus     - in the OG column only

A PLUS DOES NOT NEST, so both are binary and not depths. Material the other
edition lacks cannot contain more of the same, and a bracket that runs over a
line break is RE-OPENED at the head of the next line, so a clause can carry two
']' and one '['. Counted as a depth that made 2, and the single '[' brought it
back to 1, so the plus never closed and swallowed everything after it: at Jer
28,1a the alexandrian column kept WAJHI alone where the Greek has the whole
date. 45 clauses ended with a plus still open.
    # A \ B §   qualitative variant  - A is the MT reading, B the alexandrian
    # A §       a marked stretch with no alternative: the two editions have the
                same consonants and the difference is described in the note
    ( ... )     apparatus, including any Hebrew or Greek inside it. Everything
                between parentheses in the apparatus font belongs to neither
                column and is carried as a note on the clause.

A BARE \ IS THE COMMON CASE and it is not scoped by # ... §. Where Stipp marks
only part of a clause he brackets it with # and §; where the whole clause differs
he writes the masoretic reading, a \, and the alexandrian reading, with no
scope markers at all. Reading \ only inside a scope finds 118 variants in the
book; reading a bare one as splitting the whole clause finds them all. The scope
markers are also not reliably in the text column - a # can open at the end of a
MARGIN note and close in the text - so markup is read from the whole line while
only the text column contributes text.

THE CLAUSE LABEL IS TAKEN FROM THE RIGHT EDGE (x >= 340), not from whatever
apparatus text is left over once the markup is removed. Stipp sets sigla like *
and (root) in the middle of a line, and treating those as part of the label made
the label unparsable and lost a third of the verse numbers.

Only the font can tell markup from text - in BWHEBB `[` is an ayin and `\` is a
hataf qamats - so every character is classified by font before it is read, which
is the same guard parse_stipp.py needs and for the same reason.

ORDER. BWHEBB runs in visual order, so a clause's segments come off the page
backwards as well as each segment's letters. bwfonts.to_hebrew() reverses within
a segment; this script reverses the sequence OF segments, so what it stores is in
logical order and an HTML renderer needs no further tricks.

Output: results/synopse.json - one record per clause, in reading order:
    ch, verse, clause letter, page,
    mt   [{cls, text}]   logical order, cls in common|plus|var|scope
    og   [{cls, text}]   the same for the alexandrian text
    notes[{kind, text}]  apparatus, margin, cross-reference, idiolect
    greek                Stipp's Greek for the verse, where the page prints it
"""
import json
import re
import collections

from paths import BOOKS, R
from pypdf import PdfReader
import pymupdf
import bwfonts

SRC = BOOKS("StippJer_Textkritische_Synopse_2021.pdf")

# The PDF breaks Greek words across a justification gap - IEREMI AN, HEMER AIS -
# and lxx_greek.repair() rejoins them against the word list of LXX Jeremiah.
# Optional: without it the Greek is still extracted, just with 784 split words.
try:
    from lxx_greek import repair as _repair
    LXX_VOCAB = set(json.load(open(R("lxx_vocab.json"), encoding="utf-8")))
except Exception:
    LXX_VOCAB = None

    def _repair(toks, vocab):
        return toks

HEAD = re.compile(r"^(Jer|2\s*K[oö]n)\s+(\d{1,2}),(\d{1,3})\s*[–-]\s*(\d{1,3})")
# ONE PAGE OF THE 181 IS NOT A PAGE OF THE TEXT. p. 141 is headed "Jer 43,3-9
# mit 4Q72a (4QJer d)" and reprints a passage the book has already set, this
# time with the Qumran scroll beside it. Read as text it gives every clause of
# 43,3-9 a second time, so each of those seven verses carried its own words
# twice - 107 extra letters at 43,6, and more than half of all the extra text
# in the book. It is the only heading in the Synopse that names a scroll, and
# the passage loses nothing by the skip: the same verses are set in full on
# p. 139-140, and this project reads the scrolls from the ETCBC DSS corpus,
# not from here.
SUPPLEMENT = re.compile(r"\bmit\s+4Q")
GHEAD = re.compile(r"Jer\s*G\s*(\d{1,2}),(\d{1,3})\s*[–-]\s*(\d{1,3})")
ID = re.compile(r"Id\s+\d+\.\d+\w*")
LABEL = re.compile(r"^[\s\d a-z]*$")
# The same, with room for a raised D, P or Q; see labelish().
LABEL_SIGLUM = re.compile(r"^[\s\d a-zDPQ]*$")
# Every sign the Zeichenerklaerung lists as markup, as a plain set: a
# character class is the wrong tool here, since half of these are regex
# metacharacters and one of them is the class terminator.
MARKUP = set(chr(c) for c in (0x5b, 0x5d, 0x3c, 0x3e, 0x23, 0xa7, 0x5c))
BAR = chr(0x5c)                 # the qualitative-variant bar
TIGHT_LOG = []                  # every bar set hard against the text, and
                                # what the abbreviation rule made of it
SIGLA = re.compile(r"[«»→√≈≙*|~–’…]")

MARGIN_X = 170.0
# The text column is set flush right at x = 400 and normally starts after
# MARGIN_X, but a long line overflows to the left of it. A span at or beyond
# OVERFLOW_X that is within OVERFLOW_STEP of the span after it is part of that
# overflow and not margin: a glyph step in this setting is 3-6 units, while a
# margin lemma is tens of units clear of the text.
# HOW FAR LEFT THE COLUMN IS ALLOWED TO REACH. The printed frame begins at
# x = 30 and Stipp's margin notes start there, so a floor is needed or a lemma
# is taken for text; but the column overflows much further than MARGIN_X = 170
# suggests, and 33,21 sets MI-HJOT-LO BEN MOLEK 'AL-KIS'O at x = 54.
#
# SWEPT AGAINST BHSA, TWICE, and the second sweep is the one that counts.
# Before split lines were rejoined (fault 18, retired with step 4) the trade
# turned at 80: 140 -> 80 recovered 51
# verses and cost 4, 80 -> 60 recovered 4 and cost 2, 60 -> 40 recovered 2 and
# cost 5. Much of that cost was not this rule's at all - it was halves of a
# printed line counted as extra where they landed - and once those were put
# back the floor could come down. Verses reproducing BHSA exactly, now:
# 140 -> 1,180, 120 -> 1,198, 100 -> 1,224, 80 -> 1,231, 60 -> 1,233,
# 50 -> 1,236, 45 -> 1,236, 40 -> 1,236, 36 -> 1,232, 25 -> 1,225. The
# plateau is 40-50 and 45 sits in the middle of it, which is where a threshold
# belongs; below 40 the margin lemmas at x = 30-38 start coming in.
OVERFLOW_X = 45.0
# A SPAN'S RIGHT EDGE IS WHAT SAYS WHETHER IT IS MARGIN OR TEXT, and pypdf hands
# back only its origin, so the width is estimated from the glyphs: measured over
# the book from consecutive one-glyph spans, a BWHEBB base letter advances 5.7
# units, a point 3.4 and a space 4.1. A printed line of the text column is a
# continuous run, so a piece that overflowed it ENDS where the next span begins;
# a lemma set in the margin stops well short. At Jer 2,34a the line runs
# NEQIJIM ] 'EBJONIM [ ... and NEQIJIM sits at x = 141.5 with the bracket at
# 166.1, so both fell into the margin run and the word was lost from the verse.
W_LETTER, W_POINT, W_SPACE = 5.7, 3.4, 4.1
OVERFLOW_STEP, OVERFLOW_MAXLEN = 12.0, 3


def _right(sp):
    """The estimated right edge of a span."""
    t = sp[4]
    base = sum(1 for c in t if c in bwfonts.HEB_BASE)
    spc = sum(1 for c in t if c == " ")
    return (sp[0] + base * W_LETTER + spc * W_SPACE
            + (len(t) - base - spc) * W_POINT)
GREEK_X = 430.0
LABEL_X = 340.0


def kind(font):
    f = font.lower()
    if "bwhebb" in f:
        return "HEB"
    if "bwgrkl" in f:
        return "GRK"
    if "bold" in f:
        return "BOLD"
    return "APP"


def page_spans(page):
    """Every span of a page in DOCUMENT order: (x, y, kind, size, text)."""
    out = []
    page.extract_text(visitor_text=lambda t, cm, tm, fd, fs: out.append(
        (round(tm[4], 1), round(tm[5], 1),
         kind(str((fd or {}).get("/BaseFont", ""))), fs, t)))
    out = _true_spaces_greek(_true_spaces(out, page.page_number), page.page_number)
    return _true_geometry(out, page.page_number)


# STEP 4 (2026-10-01): WHERE A SPAN IS, FROM PYMUPDF. pypdf takes a span's
# position from its text object, and that origin is wrong in several ways this
# file has spent a dozen faults compensating for - x = 0 for orphan glyphs (6,
# 20), lines collapsed to the frame's edge (7), lines returned in two halves
# (18, 32), heads of lines shifted by -4825 after a bold reference (the failed
# 45). PyMuPDF has every glyph's real origin, and over all 181 pages its fill
# pass and pypdf's text are the same glyph sequence, Hebrew and non-Hebrew
# alike, so each span's first glyph is known by index. The span boundaries and
# the text stay pypdf's - every reading rule here is written against them - and
# only (x, y) are replaced: x is the glyph's origin, y the page height less its
# baseline, which is pypdf's own convention wherever pypdf is right.
#
# THE COMPENSATIONS FOR PYPDF'S COORDINATES WERE REMOVED WITH IT, each after
# measuring that it no longer did anything under true geometry, and with the
# output byte-identical before and after: on_page()'s placement of the orphan
# glyphs and its frame filter (6, 20), the collapsed-line rule in label_span()
# and split_columns() (7), _rejoin_split_lines() (18, 32) and the reading of
# lines in document order. The faults they record are in CLAUDE.md.


def _true_geometry(spans, pno):
    global _MU
    if _MU is None:
        _MU = pymupdf.open(str(SRC))
    page = _MU[pno]
    height = page.rect.height
    heb, oth = [], []
    for s_ in page.get_texttrace():
        if s_["type"] != 0:
            continue
        into = heb if "bwhebb" in s_["font"].lower() else oth
        for c in s_["chars"]:
            if not chr(c[0]).isspace():
                into.append((c[2], c[3]))       # origin, box
    kh = ko = 0
    out, last = [], None                # last: (right edge, baseline) so far
    for x, y, k, fs, t in spans:
        seq, i = (heb, kh) if k == "HEB" else (oth, ko)
        n = sum(1 for c in t if not c.isspace())
        if n and i < len(seq):
            (ox, oy), _ = seq[i]
            # pypdf's x for a span includes its LEADING SPACE, and every
            # distance threshold here was tuned on that convention: measured
            # from the first glyph instead, the walk could no longer bridge
            # '(!)' at 7,8 to the text 14 units on. A space is 4.1 units in the
            # Hebrew at 12.72pt and about 2.5 in Times at 9.88.
            lead = len(t) - len(t.lstrip())
            x = round(ox - lead * (W_SPACE if k == "HEB" else 2.5), 1)
            y = round(height - oy, 1)
            box = seq[min(i + n, len(seq)) - 1][1]
            last = (round(box[2], 1), y)
        elif not t:
            # AN EMPTY SPAN IS NOT TEXT: it is how pypdf reports a glyph of the
            # stroke pass it cannot decode, two to every letter of a faked-bold
            # line. Positioned, it stopped the overflow walk, which needs a
            # span's width to reach the next one: at 27,20 MIRUSHALAIM BABELAH
            # was left in the margin behind one.
            continue
        elif k == "HEB" and t and not t.strip() and chr(10) in t                 and " " not in t:
            # (HEBREW only: in the Greek panel a newline span is how a printed
            # line ends, and greek_clauses() splits the sentences on it - the
            # first draft dropped those too and ran a verse's Greek into one
            # sentence, 3,8 and 4,4 among them)
            # pypdf's own marker for a jump in position, not a glyph: it stands
            # before every orphan of faults (6) and (20), and given a place it
            # was read as a word space and cut the final letter off its word -
            # TSEVA'O T at 2,19, JISRA'E L at 19,15, 86 words in all. Under the
            # old geometry it sat at x = 0 and on_page() dropped it.
            continue
        elif last is not None:
            # A SPAN OF NOTHING BUT SPACE stands right after the glyph before it
            # in the stream, whatever its font. Placed at the NEXT glyph of its
            # own font it could land past a bar set in Times, and a bar that is
            # tight against its letters stopped looking tight: the abbreviated
            # masoretic word at 3,23, 5,18 and 6,8 was left unfinished.
            x, y = last
        out.append((x, y, k, fs, t))
        if k == "HEB":
            kh += n
        else:
            ko += n
    return out




# HOW MANY SPACES _true_spaces() TOOK OUT, by reason; parse() prints it.
FALSE_SPACES = collections.Counter()
_MU = None


GREEK_FALSE_SPACES = collections.Counter()


def _true_spaces_greek(spans, pno):
    """(54) The same as _true_spaces() for Stipp's Greek font: a space pypdf
    puts between two Greek glyphs that touch, with no space glyph between them
    in the PDF, is taken out.

    THE GREEK HAD 2,811 OF THEM, against 33,883 real space glyphs and nothing in
    between. They broke words that lxx_greek.repair() could not put back
    because the joined form is not in Rahlfs' Jeremiah - EK L EI PS OUSIN for
    EKLEIPSOUSIN at 51,58, EN EP L ES A for ENEPLESA at 31,25, TRI BOUSI at
    7,18 - and they are also what made the Greek panel look letter-spaced: the
    SPERRT setting of fault (11), a space between every character, is pypdf's
    reading of glyphs that sit hard against each other. A run that contains a
    NEWLINE is never touched, because greek_clauses() splits the panel's
    sentences on it.
    """
    global _MU
    if _MU is None:
        _MU = pymupdf.open(str(SRC))
    G = []
    for s_ in _MU[pno].get_texttrace():
        if "bwgrk" not in s_["font"].lower() or s_["type"] != 0:
            continue
        for c in s_["chars"]:
            if chr(c[0]).isspace():
                if G:
                    G[-1][1].append(s_["size"])
            else:
                G.append((c[3], []))
    out, k = [], 0
    for sp in spans:
        if sp[2] != "GRK":
            out.append(sp)
            continue
        t, keep, i = sp[4], [], 0
        while i < len(t):
            if not t[i].isspace():
                keep.append(t[i]); k += 1; i += 1
                continue
            j = i
            while j < len(t) and t[j].isspace():
                j += 1
            drop = False
            if chr(10) not in t[i:j] and 0 < k < len(G):
                (a, follows), (z, _) = G[k - 1], G[k]
                if follows and all(x < 5 for x in follows):
                    drop = True
                elif not follows and abs(a[1] - z[1]) < 2 and                         abs(a[3] - z[3]) < 2 and -1 < z[0] - a[2] < 1.5:
                    drop = True
            if drop:
                GREEK_FALSE_SPACES["removed"] += 1
            else:
                keep.append(t[i:j])
            i = j
        out.append(sp[:4] + ("".join(keep),))
    return out


def _glyph_trace(pno):
    """PyMuPDF's view of one page's Hebrew: the non-space glyphs of the FILL
    pass in content-stream order, as (bbox, [sizes of the space glyphs that
    follow it before the next one])."""
    global _MU
    if _MU is None:
        _MU = pymupdf.open(str(SRC))
    G = []
    for s in _MU[pno].get_texttrace():
        # Type 1 is a stroke pass laid over the fill at the same position - a
        # faked bold, 5,652 glyphs of the book - and pypdf never reports it.
        if "bwhebb" not in s["font"].lower() or s["type"] != 0:
            continue
        for c in s["chars"]:
            if chr(c[0]).isspace():
                if G:
                    G[-1][1].append(s["size"])
            else:
                G.append((c[3], []))
    return G


def _true_spaces(spans, pno):
    """Take out the spaces pypdf puts INSIDE a Hebrew word.

    A WORD BROKEN IN TWO ON THESE PAGES WAS NEVER THE SOURCE'S TYPESETTING. The
    project took הַדָּבָ ר at 21,1, בִּשְׁלֹ שׁ at 1,2 and some thirty more for
    justification gaps, which could only be closed by consulting BHSA and so were
    left open. They have two causes, and both are visible in the PDF itself once
    it is read glyph by glyph - which pypdf does not do and PyMuPDF does:

    - pypdf DECIDES WHERE A SPACE GOES. The 15th edition sets much of its Hebrew
      one glyph per Tj, positioned by Td, and pypdf joins those into a string,
      putting a space wherever the jump between two glyphs looks large to it. At
      21,1 the glyphs of HA-DABAR touch to within 0.07 units and pypdf put a
      space between bet and resh all the same. 27 places.
    - THE SOURCE HAS A HAIR SPACE. At 1,2 the PDF does carry a space glyph inside
      B-SLS, but it is set at 1.78pt and is 0.2 units wide, a filler left by the
      justification. Of the book's 17,320 Hebrew space glyphs, 17,284 are set at
      the body's 12.72pt and are 4.1 units wide; 16 are set below 5pt. 14 places.

    THE TWO READINGS ARE ALIGNED BY INDEX, AND THEY CAN BE: over all 181 pages
    pypdf's Hebrew and PyMuPDF's fill-pass Hebrew are the same 172,779 non-space
    glyphs in the same order. So each whitespace run pypdf emits is known to sit
    between glyphs k-1 and k of the trace, and is kept unless the trace says
    there is no word break there - a hair space only, or no space glyph at all
    with the two glyphs on one baseline and touching. Every other run is kept,
    and must be: 629 fall between glyphs on different lines, where the line
    break IS the space, and 32 between glyphs on one line with a clear gap
    between them, an apparatus or a margin note set in between.

    Nothing is ever ADDED here and no glyph is moved; the masoretic column is
    still Stipp's text and BHSA still only checks it.
    """
    G = _glyph_trace(pno)
    other = [c[3] for s in _MU[pno].get_texttrace()
             if "bwhebb" not in s["font"].lower() and s["type"] == 0
             for c in s["chars"] if not chr(c[0]).isspace()]
    out, k, ended_ws = [], 0, True
    for sp in spans:
        if sp[2] != "HEB":
            out.append(sp)
            continue
        t, keep, i = sp[4], [], 0
        # (42) AND ONE THING IT ADDS: A WORD SPACE DRAWN AS A GAP. Where two
        # pypdf strings meet with no space in either, the jump between them is
        # ambiguous, because a bracket or siglum in the Times font can stand in
        # it - 1,024 of the book's 1,030 such gaps hold one. The other SIX hold
        # nothing at all, are all 2.4-2.5 units wide, a space compressed on a
        # justified line and drawn by position rather than by a glyph, and they
        # are the words the page ran together: HA-'ARETS BIGLAL at 15,4, KULLOH
        # 'EZ'AQ at 48,31, NE'UM-JHWH LO' at 50,40.
        if t and not t[0].isspace() and not ended_ws and 0 < k < len(G):
            (a, follows), (z, _) = G[k - 1], G[k]
            if not follows and abs(a[1] - z[1]) < 2 and abs(a[3] - z[3]) < 2 \
                    and z[0] - a[2] >= 2 and not any(
                        o[0] < z[0] - .3 and o[2] > a[2] + .3 and
                        o[1] < a[3] and o[3] > a[1] for o in other):
                keep.append(" ")
                FALSE_SPACES["gap with nothing in it (added)"] += 1
        if t:
            ended_ws = t[-1].isspace()
        while i < len(t):
            if not t[i].isspace():
                keep.append(t[i])
                k += 1
                i += 1
                continue
            j = i
            while j < len(t) and t[j].isspace():
                j += 1
            why = None
            if 0 < k < len(G):
                (a, follows), (z, _) = G[k - 1], G[k]
                if follows and all(s < 5 for s in follows):
                    why = "hair space"
                elif not follows and abs(a[1] - z[1]) < 2 and \
                        abs(a[3] - z[3]) < 2 and -1 < z[0] - a[2] < 1.5:
                    why = "glyphs touching"
            if why:
                FALSE_SPACES[why] += 1
            else:
                keep.append(t[i:j])
            i = j
        t = "".join(keep)
        if t:
            out.append(sp[:4] + (t,))
    return out




def lines_of(spans):
    """Spans -> printed lines, top to bottom, under true geometry.

    WITH TRUE COORDINATES A LINE IS A BASELINE, and the page's own order is top
    to bottom. The pypdf reading this replaced had to keep the DOCUMENT order of lines,
    because pypdf's y was not comparable across text objects (a running number
    at y = -4802, heads of lines at -4300), and then had to repair the order in
    _rejoin_split_lines(); ordered by height instead, the lines come out in
    print order and that repair has nothing left to do (measured: 1,382 exact
    with it and without it).

    A GLYPH SET SMALL BESIDE THE LINE BELONGS TO IT. A Klammerkonstruktion index
    sits 1.4 units below its label, a raised Q, P or D or a footnote mark about
    4.5 above its word; pypdf reported them on lines of their own and the
    reading compensated (5,23; 22; 32). Grouped by exact baseline they became
    lines of their own again, and FOLLOWED the label instead of riding on it:
    a1/a2 came back as a, and 172 records opened with no label. So a span under
    8pt joins the full-size line nearest it within 6 units.
    """
    # Only a full-size span WITH TEXT founds a line; a span of nothing but
    # space takes its position from the glyph before it (see _true_geometry),
    # and at 25,29 that glyph was the index 2, so the space founded a line of
    # its own and captured the index: a2 came back as a.
    full = [s_ for s_ in spans if s_[3] >= 8 and s_[4].strip()]
    small = [s_ for s_ in spans if not (s_[3] >= 8 and s_[4].strip())]
    byy = {}
    for s_ in full:
        byy.setdefault(round(s_[1] * 2) / 2, []).append(s_)
    keys = sorted(byy)
    for s_ in small:
        near = min(keys, key=lambda k: abs(k - s_[1]), default=None)
        if near is not None and abs(near - s_[1]) <= 6:
            byy[near].append(s_)
        else:
            byy.setdefault(round(s_[1] * 2) / 2, []).append(s_)
    # (52) A POINT STAYS WITH ITS LETTER. In the font's stream a vowel follows
    # the letter it belongs to, but its ORIGIN lies a little to the right of
    # the letter's, and sorted on x alone it can cross a span set between them:
    # at 41,2 the patah of the line's first waw is at x = 352.6, just right of
    # the label at 352.5, and at 33,10 the tsere of a mem just right of the
    # bracket that closes the plus. Read right to left, the mark then fell on
    # the far side of the label or bracket, detached from its letter, and was
    # lost: WAYYAMET came out W-YYAMET, U-ME'EN as U-M'EN. A Hebrew span that
    # is only marks therefore sorts with the Hebrew span before it in the
    # stream, when the two are within 7 units: a point's origin can sit a full
    # advance from its letter's - 5.9 at 33,10, against a letter's 5.7.
    eff, prev = {}, None
    for s_ in spans:
        if s_[2] != "HEB":
            continue
        t_ = s_[4].strip()
        if t_ and prev is not None and not any(c in bwfonts.HEB_BASE for c in t_)                 and abs(prev[0] - s_[0]) <= 7.0 and abs(prev[1] - s_[1]) < 6:
            eff[id(s_)] = (prev[0], 1)
        elif t_:
            prev = s_
    return [sorted(byy[k], key=lambda s_: eff.get(id(s_), (s_[0], 0)))
            for k in sorted(byy, reverse=True)]


def labelish(t):
    """Is this span's text a clause label once the markup is taken out of it?

    A RAISED SIGLUM CAN RIDE ON THE LABEL, and rejecting the label because of it
    is how eight verses went missing from the book. Stipp raises a P for
    Parablepsis and a D for Dittographie, and where the sign qualifies the sentence
    it is set inside the label span: ']_aP_10' at Jer 13,9, and the same at 8,
    9, 11, 12, 16, 20, 27, 34. The number is right there and was being thrown
    away with the letter, so the verse was never opened and its text ran on into
    the verse before - which is why 13,9 carries 100 letters of 13,10.

    The siglum is allowed ONLY WHEN A LETTER OR A NUMBER IS THERE TOO. That is
    what keeps the other 40 out: a bare 'P' or 'D' at the right edge is the sign
    alone, on a line of its own, and admitting it would open a clause where
    there is none.
    """
    flat = "".join(c for c in t if c not in MARKUP)
    if not flat.strip():
        return False
    if LABEL.match(flat):
        return True
    return bool(LABEL_SIGLUM.match(flat)) and any(
        c.islower() or c.isdigit() for c in flat)


def label_span(line):
    """The index of the span carrying this line's clause label, or None.

    THE LABEL IS AT THE RIGHT EDGE, WHICH IN A RIGHT-TO-LEFT COLUMN IS WHERE THE
    CLAUSE BEGINS, NOT WHERE IT ENDS. Jer 1,1a runs over three printed lines and
    only the first carries its label, the span '§ a 1'. Closing a clause at its
    label instead of opening one - which is what this script did until
    2026-09-05 - cut every clause that wraps after its first line and left the
    remainder as label-less fragments: 1,1a came out holding DBRJ alone, and
    JRMJHW BN-XLQJHW MN-HKHNJM was stranded in a row of its own.
    """
    right = [i for i, sp in enumerate(line)
             if sp[0] >= LABEL_X and sp[2] not in ("HEB", "GRK")
             and labelish(sp[4])]
    # A SMALL DIGIT ALONE IS NEVER A LABEL. A label always carries a full-size
    # letter or verse number, and the index rides on it; under true geometry a
    # long margin line can reach the label column with the subscript of its
    # last reference - '24,8a₂' at 1,15, x = 340 - and that alone opened a
    # sentence labelled '2'.
    if right and all(line[i][3] < 8 for i in right):
        return None
    if right:
        return right[-1]
    return None


def label_spans(line):
    """EVERY span at the right edge that belongs to this line's label.

    A label can be set in two spans, because Stipp counts the parts of a
    Klammerkonstruktion with an index figure and gives it a size of its own:
    at Jer 28,1 the sentence is ' b' at 9.88pt followed by ' 1' at 6.36pt, and
    the same at 186 clauses of the book. label_span() returns the LAST of them
    - the index - and read_clause() then refused it for its size, so the label
    came out empty and the clause letter column was blank. The size guard is
    right and stays; what was missing is that the letter is in the other span.
    """
    out = [i for i, sp in enumerate(line)
           if sp[0] >= LABEL_X and sp[2] not in ("HEB", "GRK")
           and labelish(sp[4])]
    if out:
        return out
    i = label_span(line)
    return [] if i is None else [i]


def has_label(line):
    return label_span(line) is not None


FOOT_SIZES = (8.48, 6.70, 5.64)     # body, small capitals, number
FOOT_HEB = 11.32                    # the Hebrew a footnote quotes
FOOT_UNMARKED = []                  # (page, n) placed without finding the mark


def _is_size(fs, sizes):
    return any(abs(fs - s) < 0.05 for s in sizes)


def footnotes(pno):
    """The footnotes of one page, read whole by PyMuPDF: {number: text}.

    THE FOOTNOTES WERE READ AS MARGIN NOTES OF THE PAGE'S LAST SENTENCE, IN
    PIECES. Stipp sets 24 of them on 22 pages, at the foot of the page in 8.48pt
    with names in small capitals at 6.70pt, and pypdf hands them back in an
    order of its own: footnote 1 on p. 11 came out as '1', ', The Book of Jere-',
    'ANGLOIS', 'L', 'ICHAEL', 'Das Manuskript ... : M', ... - Michael Langlois's
    name in four places and the sentence in five. PyMuPDF reads them line by
    line and left to right as printed, so a small capital rejoins its capital
    (M + ICHAEL), a word hyphenated at a line end is joined (Jere- / miah's),
    and the Hebrew a footnote quotes - set at 11.32pt in BWHEBB, as at 4,2 - is
    converted where it stands. Every non-space span the book sets at 8.48pt lies
    in a footnote, so the sizes identify them.
    """
    global _MU
    if _MU is None:
        _MU = pymupdf.open(str(SRC))
    lines = [l for b in _MU[pno].get_text("dict")["blocks"]
             for l in b.get("lines", [])]
    nums = [l["bbox"][1] for l in lines for s in l["spans"]
            if _is_size(s["size"], FOOT_SIZES[2:])]
    if not nums:
        return {}
    top = min(nums) - 3
    lines = [l for l in lines if l["bbox"][1] >= top and
             any(_is_size(s["size"], FOOT_SIZES) and s["text"].strip()
                 for s in l["spans"])]
    lines.sort(key=lambda l: (round(l["bbox"][1]), l["bbox"][0]))
    out, cur = {}, None
    for l in lines:
        for s in l["spans"]:
            t, f = s["text"], s["font"].lower()
            if _is_size(s["size"], FOOT_SIZES[2:]) and t.strip().isdigit():
                cur = int(t)
                out[cur] = []
                continue
            if cur is None:
                continue
            if "bwhebb" in f:
                t = bwfonts.to_hebrew(t)
            elif "bwgrk" in f:
                t = bwfonts.to_greek(t)
            out[cur].append(t)
        if cur is not None:
            out[cur].append("\n")
    for n, parts in out.items():
        t = re.sub(r"-\n(?=[a-zäöüß])", "", "".join(parts))
        out[n] = " ".join(t.split()).replace("ё", "ë")
    return out


def _take_footnotes(spans):
    """Split pypdf's spans into (body, {id(span): n} for each footnote MARK).

    A footnote is one run of the content stream, from its number at 5.64pt to
    its last word, and the whole run is taken out: left in, it was filed as the
    margin of the page's last sentence. The Hebrew inside it is set at 11.32pt,
    so it is taken with the run rather than by size.

    THE MARK IN THE TEXT IS A RAISED DIGIT, at 6.36pt - the same size as a
    Klammerkonstruktion index, which is how a mark and an index can be confused.
    They are told apart by direction: a footnote mark stands ABOVE its line
    (1 at p. 11, y = 486.0 against the line's 481.4) and an index BELOW it (1 at
    the same page, 352.8 against 354.2). Every mark of the book is 4.4 to 4.6
    units up; no index is above its line.
    """
    body, marks, run = [], {}, False
    for i, sp in enumerate(spans):
        x, y, k, fs, t = sp
        if _is_size(fs, FOOT_SIZES[2:]) and t.strip().isdigit():
            run = True
        elif run and not (_is_size(fs, FOOT_SIZES) or not t.strip() or
                          (k == "HEB" and _is_size(fs, (FOOT_HEB,)))):
            run = False
        if run:
            continue
        body.append(sp)
        if _is_size(fs, (6.36,)) and t.strip().isdigit():
            near = [s[1] for s in spans[max(0, i - 3):i + 4]
                    if s[3] > 9 and s[4].strip() and abs(s[1] - y) < 6]
            if near and y - near[0] >= 3:
                marks[id(sp)] = int(t)
    return body, marks


def clauses_of(page):
    """A page -> (heading spans, [clause], greek spans, footnote marks).

    A clause is a run of printed lines beginning at the line that carries its
    label; a line without one continues the clause before it, which is how a
    clause that wraps - or that has margin notes set beneath its first line - is
    held together.
    """
    spans, marks = _take_footnotes(page_spans(page))
    head = [s for s in spans if s[2] == "BOLD"]
    greek = [s for s in spans if s[0] >= GREEK_X and s[2] != "BOLD"]
    body = [s for s in spans if s[0] < GREEK_X and s[2] != "BOLD"]
    out, cur = [], []
    for ln in lines_of(body):
        if has_label(ln) and cur:
            out.append(cur)
            cur = []
        cur.append(ln)
    if cur:
        out.append(cur)
    return head, out, greek, marks


def _apparatus_opens_left(text):
    """Does this run of spans CLOSE an apparatus it never opened?

    Stipp sets his parenthetical apparatus inline, in the text column, and a
    long one pushes what follows it out past the left edge of the column and
    into the margin zone - where the leading-margin loop swallows it, apparatus
    and all. At 2,25a he sets MIN'I RAGLEK MI-JAHEF (avpo. o`dou/ tracei,aj)
    U-GRONEK (AlT = U-GRONEK) MI-TSIM'AH, and the second apparatus runs from
    x = 113 to x = 170 with MI-TSIM'AH beyond it at x = 80: the walk cannot
    reach the word because an apparatus, unlike a bracket, is not markup and
    stops it dead.

    The parentheses say where the line begins. Read visually, an apparatus is
    ( ... ), so a ')' with no '(' before it in the text column means the '('
    is further left, on the same printed line, and everything back to it
    belongs to the line rather than to the margin. Parentheses inside a Hebrew
    or Greek span are letters and are not counted, the same guard the markup
    needs everywhere else.
    """
    depth = 0
    for x, y, k, fs, t in text:
        if k in ("HEB", "GRK"):
            continue
        for c in t:
            if c == "(":
                depth += 1
            elif c == ")":
                if not depth:
                    return True
                depth -= 1
    return False


def _apparatus_reach(margin, text):
    """How many spans at the right of the margin run belong to the line.

    THE CONCESSION IS BOUNDED AT BOTH ENDS, and it has to be, because reaching
    into the margin for any parenthesis at all puts back the two faults this
    file was built to avoid. At 8,1 the margin reads `7,30-8,3 > 4Q70* (4QJer`
    with its `)` on the far side of the column, and taking that span into the
    text makes the `>` a bracket again - fault (17), 89 letters, the largest
    single loss in the book. At 25,38 it reads `46,16e; 50,16b; Zef 3,1 (` and
    taking it lets the overflow walk on to the lemma HNJ beyond, which then
    prints as text.

    Both are refused by the same test: the `(` MUST OPEN ITS SPAN. Stipp sets
    an apparatus that stands in the text as a parenthesis of its own - at 2,25a
    the span is `(` and nothing else - while a margin note that happens to
    contain one carries its cross-reference in front of it. And nothing is
    taken from further left than OVERFLOW_X, which is where the margin's own
    lemmas begin. If either test fails the line is left exactly as it was;
    there is no partial reach.
    """
    take, run = 0, list(text)
    while _apparatus_opens_left(run):
        if take >= len(margin):
            return 0
        sp = margin[-1 - take]
        if sp[0] < OVERFLOW_X:
            return 0
        if sp[2] not in ("HEB", "GRK") and "(" in sp[4]                 and sp[4][:sp[4].index("(")].strip():
            return 0
        take += 1
        run.insert(0, sp)
    return take


def _bracket_closes_left(text):
    """Does this run of spans CLOSE a bracket it never opened?

    (36) The same question _apparatus_opens_left() asks of a parenthesis, and
    the answer means the same thing: the opener is further left, on the same
    printed line, so everything back to it belongs to the line. (31) asked it
    only of the FIRST span of the text column, which is where the closer stands
    when the plus is the whole of the wrapped line. It need not be. At 52,29
    Stipp brackets the entire line, so the '[' and the bracketed SHIM U-SHENAJIM
    are at the far left and the ']' is at the far right, past the text; at 34,10
    the ']' comes after the first Hebrew of the column, not before it.

    Brackets inside a Hebrew or Greek span are letters, the same guard the
    markup needs everywhere else - in BWHEBB '[' is an ayin and ']' a segol.
    """
    mt = og = 0
    for x, y, k, fs, t in text:
        if k in ("HEB", "GRK"):
            continue
        for c in t:
            if c == "[":
                mt += 1
            elif c == "]":
                if not mt:
                    return True
                mt -= 1
            elif c == "<":
                og += 1
            elif c == ">":
                if not og:
                    return True
                og -= 1
    return False


def _bracket_reach(margin, text):
    """How many spans at the right of the margin run a closing bracket claims.

    (31) A PLUS CANNOT OPEN IN THE MARGIN AND CLOSE IN THE TEXT WITH ITS WORD
    THROWN AWAY. Stipp brackets a plus that wraps to the left end of a printed
    line; the closing bracket lands in the text column and the opening bracket
    and the bracketed word land beyond MARGIN_X, so the word was dropped and
    only its closer survived. At 26,11 the line closes with a ']' at x = 139
    and LE'MOR stands at x = 40 behind a '[' that shares its span with the
    cross-reference '7'.

    THE TEST IS STRUCTURAL AND USES NO GEOMETRY AT ALL, which is why it can go
    where OVERFLOW_X cannot: twelve of these words sit at x = 30.2, the
    leftmost printed position, where the margin's own lemmas also live, so no
    threshold separates them. A bracket does. The text column must OPEN with
    the closer, and the margin must yield the matching opener at the END of one
    of its spans - the same positional guard fault (17) needs, since a '>' with
    a reference after it is Stipp's siglum for "fehlt in" and not a bracket -
    with Hebrew between the two and nothing but markup or space besides.

    19 printed lines in the book are of that shape and every one is a real
    plus. They carry 13 of the 20 verses the diagnostic files under `margin`,
    and five more it had filed elsewhere: 8,3, 15,11, 20,5, 29,2 and 38,9.
    """
    if not margin or not text or not _bracket_closes_left(text):
        return 0
    take, saw_hebrew = 0, False
    while take < len(margin):
        sp = margin[-1 - take]
        take += 1
        if sp[2] == "HEB":
            saw_hebrew = saw_hebrew or bool(sp[4].strip())
            continue
        if sp[2] == "GRK":
            return 0
        t = sp[4].strip()
        if t.endswith("[") or t.endswith("<"):
            return take if saw_hebrew else 0
        if not t or set(t) <= MARKUP:
            continue
        return 0                    # a margin note, so the bracket is not here
    return 0


REFERENCE = re.compile(r"^(?=.*(\d|→))[\d\s,;.:a-g–→+]+$")
# A reference that names a book - 'Zef 3,1', 'Jes 65,1', '2 Kön 25,15' - is a
# reference too: Latin letters, digits and punctuation only, with a
# chapter-and-verse in it. Under true geometry the lookahead handed '46,16e;
# 50,16b; Zef 3,1 (' to the text at 25,38 and the walk took the lemma JNH.
BOOK_REFERENCE = re.compile(r"^[A-Za-zÄÖÜäöüß\d\s,;.:–→+|]*\d+,\d+[A-Za-zÄÖÜäöüß\d\s,;.:–→+|]*$")


def _is_reference(t):
    """A margin cross-reference: '19,3b; 25,18; ', '→', ' 21,3b <', and one
    naming a book, '46,16e; 50,16b; Zef 3,1 ('. Bracket markup and an opening
    parenthesis may end it - the margin applies the first, and the second
    opens the apparatus of the text column."""
    t = t.strip()
    while t and (t[-1] in MARKUP or t[-1] == "("):
        t = t[:-1].rstrip()
    return bool(REFERENCE.match(t) or BOOK_REFERENCE.match(t))


def split_columns(line):
    """One printed line -> (margin spans, text spans).

    The margin is the leading run of the line, and a span stays in it only while
    the NEXT span is also to the left of MARGIN_X. That lookahead is what stops a
    text span from being swallowed by the margin when pypdf hands back the
    margin's x for both (see the note in the module docstring).
    """
    margin, i = [], 0
    while i < len(line):
        x = line[i][0]
        nxt = line[i + 1][0] if i + 1 < len(line) else 10 ** 6
        if x < MARGIN_X and nxt < MARGIN_X:
            margin.append(line[i])
            i += 1
        else:
            break
    text = line[i:]

    # (43) A TEXT COLUMN NEVER OPENS WITH A CROSS-REFERENCE. A margin note can
    # run past MARGIN_X - at 13,13c it reads 'AlT + JEHUDAH 19,3b; 25,18; 34,1c;
    # 40,5d; → 21,3b' and ends at x = 225 - and then the lookahead above stops
    # at the reference and hands it to the text. Worse follows: with a
    # reference at the head of the text, the overflow walk below takes the
    # margin's Hebrew lemma for the column's own overflow, and JEHUDAH was
    # printed in the masoretic column. So a leading text span that is plainly a
    # reference - digits and verse letters with ; , . → + and nothing else,
    # bracket markup allowed at its end, since the margin applies that - goes
    # back to the margin first.
    # Never in the label column and never a raised glyph: a verse number or a
    # Klammerkonstruktion index is a bare digit too, and the first draft of
    # this guard moved the index 2 at 1,15 into the margin as a note.
    while text and text[0][2] == "APP" and text[0][0] < LABEL_X and \
            text[0][3] >= 8 and _is_reference(text[0][4]):
        margin.append(text.pop(0))

    # AN APPARATUS THAT CLOSES IN THE TEXT COLUMN OPENED ON THE SAME LINE, so
    # the text reaches back at least as far as its '('. See the note above.
    for _ in range(_apparatus_reach(margin, text)):
        text.insert(0, margin.pop())

    # THE TEXT COLUMN OVERFLOWS ITS LEFT EDGE ON A LONG LINE, and MARGIN_X is a
    # threshold, so the overflow falls into the margin and is lost. Two shapes
    # of it, and both are in Jer 4,3a and 2,34a: at 4,3a the last three glyphs
    # of JERUSHALAIM sit at x = 161-167 and the word came out cut short; at
    # 2,34a the whole of NEQIJIM sits at x = 141.5 with the bracket that closes
    # the plus at 166.1, so the word was dropped and its bracket with it.
    #
    # The column is set flush right and a printed line of it is a CONTINUOUS
    # run, which is what tells the two apart: an overflowed piece ends where the
    # next span begins, while a lemma set in the margin stops well short of it.
    # So the text is grown LEFTWARDS through the margin run, taking a span when
    # it is either within one glyph-width of what follows or wide enough to
    # reach it. Markup is carried along, because the bracket at 2,34a is part of
    # the line and reading it as margin loses the plus as well as the word.
    while margin:
        sp = margin[-1]
        t = sp[4].strip()
        # (37) AND TWO MORE THINGS THAT BELONG TO THE LINE AND ARE NOT MARKUP.
        # An apparatus complete inside its own span - Stipp's '(!)' - is set in
        # the text column like any other, and (28) does not reach it, because
        # (28) fires on a ')' that opens no parenthesis and this one closes its
        # own. At 7,8 it stands at x = 128 with HO'IL beyond it at 97. And the
        # transposition star is text too: at 14,17 it stands at x = 137 between
        # the column and WE-JOMAM. Both stopped the walk dead where a bracket
        # would have been carried along.
        # (46) and the stroke '|', Stipp's third in-line sign: at 9,5a it
        # stands at x = 162 between the column and MIRMAH, the last word of
        # the line, which the walk then left in the margin.
        if not (sp[2] == "HEB" or not t or set(t) <= MARKUP
                or (len(t) > 1 and t.startswith("(") and t.endswith(")"))
                or set(t) == {"*"} or set(t) == {"|"}
                # a raised siglum - P, D, Q at 6.36pt - rides on its line under
                # true geometry, and at 2,13 it stood between the column and
                # NISHBARIM [BO'ROT], which the walk then left in the margin
                or sp[3] < 8):
            break
        if sp[0] < OVERFLOW_X or not text:
            break
        # A piece belongs to the line either because it sits one glyph-width
        # from what follows it, or because its own width carries it there.
        near = len(t) <= OVERFLOW_MAXLEN and text[0][0] - sp[0] <= OVERFLOW_STEP
        if not (near or _right(sp) >= text[0][0]):
            break
        text.insert(0, margin.pop())

    # AND LAST, THE STRUCTURAL CONCESSION: a bracket that closes at the head of
    # the text column opened on the same printed line, so the plus it closes is
    # in the line too, however far left the margin threshold puts it. This runs
    # after the geometric walk and not before, because the walk may already have
    # taken part of the run and the opener is then nearer than it looks.
    for _ in range(_bracket_reach(margin, text)):
        text.insert(0, margin.pop())
    return margin, text


SEP = " -"


def first_token(t):
    """ASCII -> (its visually FIRST word, the rest). The first word visually is
    the last word in reading order, so this is what a backslash met just after
    it refers back to."""
    i = 0
    while i < len(t) and t[i] in SEP:
        i += 1
    j = i
    while j < len(t) and t[j] not in SEP:
        j += 1
    return t[:j], t[j:]


def last_token(t):
    """ASCII -> (the head, its visually LAST word). The last word visually is the
    first in reading order, so this is what a backslash met just before it
    refers forward to."""
    j = len(t)
    while j and t[j - 1] in SEP:
        j -= 1
    i = j
    while i and t[i - 1] not in SEP:
        i -= 1
    return t[:i], t[i:]


# ---------------------------------------------------------------------------
# THE ABBREVIATED MASORETIC WORD
# ---------------------------------------------------------------------------
# (26) WHERE THE TWO FORMS DIFFER ONLY IN THEIR FIRST LETTER, STIPP PRINTS THE
# MASORETIC HEAD AND THE ALEXANDRIAN WORD IN FULL, and the letters they share
# are set once, inside the alexandrian form. Jer 52,9 is the plain case:
#
#     ... BABEL MELEKH-'EL 'OTO WA-JA'ALU  \  RI  DIBLATAH
#                        the masoretic head ^        ^ the whole alexandrian word
#
# so the masoretic column was left holding RI and nothing more, and the reader
# is expected to carry his eye across the bar and finish the word from the
# other side: RI + BLATAH. Sixteen verses of the book are short for this
# reason and this reason only, and until 2026-09-09 all sixteen were left as
# they stood, on the ground that composing the word would write into the column
# something Stipp does not print there. He does print it. It stands once
# instead of twice, which is a saving of ink and not a statement about the
# text, and the letters come from his page and from nowhere else - the repair
# that was built and removed on 2026-09-05 took them from BHSA, which is a
# different thing and still forbidden. What is supplied is carried as its own
# class, `mtsup`, so that the page can show it for what it is and no count can
# mistake it for something Stipp sets twice.
#
# THE SETTING IS WHAT MARKS THE CLASS, not the reading. A bar between two whole
# words is set with a space on each side; a bar inside one word is set hard
# against the text on both sides. The book has 820 bars, 754 loose and 66
# tight, and every abbreviation is in the tight 66.
#
# Tightness alone is not enough, because the same setting is used when the
# ALEXANDRIAN form is the abbreviated one - MAR'ITI \ TAM at 23,1, where the
# shared head stands in the masoretic column and the masoretic word is already
# whole - and for a handful of short whole-word variants bound by maqqef. Three
# tests together pick out the seventeen places, and each was measured against
# all 66:
#
#   * the masoretic piece has FEWER consonants than the alexandrian one. This
#     is what puts MAR'ITI \ TAM out, and KIS'O \ 'AM at 13,13, and 'AL \ LO
#     at 31,2 where the two are equal.
#   * it does not end in a maqqef, which is a word boundary in Stipp's own
#     terms - "ein Makkef wird wie ein Spatium behandelt". This is what puts
#     RAB- \ NEBU at 39,3 out, the one place where the masoretic side is both
#     shorter and complete.
#   * it cannot stand as a word: its last letter carries a point. A word ends
#     on a bare letter or on a mater; RI, BE-RI, 'E, HI, HA, TI, MI, WA and B
#     do not end at all. The exceptions are the four ways a word CAN end on a
#     pointed letter - a final form, a mappiq in HE, a furtive patah under HET
#     or AYIN - and they are named rather than discovered, since BAH at 8,19 is
#     a whole word and HA at 3,23 is half of one.
POINTS = set(bwfonts.HEB_MARK.values()) | {bwfonts.DAGESH,
                                           bwfonts.SHIN, bwfonts.SIN}
PATAH = bwfonts.HEB_MARK[";"]
SHEVA = bwfonts.HEB_MARK["."]
FINAL_FORM = set("ךםןףץ")     # K M N P TS
LETTER = set(chr(c) for c in range(0x5d0, 0x5eb))
MAQQEF = "־"


def _last_letter(heb):
    """The last base letter of a Hebrew string and the points on it."""
    i, marks = len(heb), []
    while i and heb[i - 1] in POINTS:
        marks.append(heb[i - 1])
        i -= 1
    if not i or heb[i - 1] not in LETTER:
        return "", []
    return heb[i - 1], marks


def _open_head(vis):
    """Is this piece unable to stand as a word - a head with no word behind it?

    Two ways of failing to be a word, and the second is here because the 15th
    edition sets much of its Hebrew one glyph per span. A piece ends on a bare
    letter or on a mater; where it ends on a POINTED letter it is unfinished,
    and the four ways a word can end on a pointed letter after all - a final
    form, a mappiq in he, a furtive patah under het or ayin - are named below
    rather than discovered, since BAH at 8,19 is a whole word and HA at 3,23 is
    half of one. But a piece can also lose its point to a span break: at 25,11
    the HE of HA-GOJIM arrives as a span of one glyph and its patah at the head
    of the next, so the piece reads as a bare letter. A SINGLE LETTER IS NEVER A
    WORD whatever it carries, which covers that case without appealing to the
    pointing at all.
    """
    heb = bwfonts.to_hebrew(vis)
    if heb.endswith(MAQQEF):
        return False
    base, marks = _last_letter(heb)
    if not base:
        return False
    if len(HEBCONS.findall(heb)) == 1:
        return True
    if not marks:
        return False
    if base in FINAL_FORM:
        return False
    if base == "ה" and bwfonts.DAGESH in marks:       # mappiq
        return False
    if base in "חע" and PATAH in marks:          # furtive patah
        return False
    return True


def _drop_letter(vis):
    """Visual ASCII of a word -> the same word without its FIRST letter in
    reading order, which is the LAST base letter of the visual string. The
    points on that letter are written to the right of it and go with it."""
    for i in range(len(vis) - 1, -1, -1):
        if vis[i] in bwfonts.HEB_BASE:
            return vis[:i]
    return ""


def _first_unit(vis):
    """The word's FIRST letter in reading order, with the points on it."""
    for i in range(len(vis) - 1, -1, -1):
        if vis[i] in bwfonts.HEB_BASE:
            return bwfonts.to_hebrew(vis[i:])
    return ""


def _supplied(mt_vis, og_vis):
    """The letters that complete an abbreviated masoretic word, or None.

    The alexandrian word gives up its own first letter and hands over the rest.
    ONE LETTER, except where the masoretic head ends in a silent sheva: there
    the letter it closes on cannot be followed by another letter under a sheva,
    so what the alexandrian form offers next is the head's own last consonant
    over again, and that goes too. It happens once in the book, at 5,18, where
    'ITTE \\ 'ETKHEM gives 'ITTEKHEM and not 'ITTETKHEM. THE TEST IS ON THE
    POINTS, NOT ON THE LETTERS, which is what keeps 23,20 out of it: TI \\
    JITBONENU repeats the taw as well, but the head's taw carries a hiriq, its
    syllable is open, and TITBONENU is right.
    """
    if _cons(mt_vis) >= _cons(og_vis) or not _open_head(mt_vis):
        return None
    tail = _drop_letter(og_vis)
    if not tail.strip():
        return None
    if bwfonts.to_hebrew(mt_vis).endswith(SHEVA) and SHEVA in _first_unit(tail):
        tail = _drop_letter(tail)
    return tail if tail.strip() else None


def _cons(vis):
    return len(HEBCONS.findall(bwfonts.to_hebrew(vis)))


def _og_abbreviated(mt_vis, og_vis):
    """(35) Is the ALEXANDRIAN piece of a tight bar the abbreviated one?

    The abbreviation runs both ways. Where the two forms differ only in their
    FIRST letters Stipp prints the masoretic head and the alexandrian word in
    full, and _supplied() completes the masoretic side from his page - 17
    places, every one of them checked against BHSA exactly. Where they differ
    only at the END he does the reverse: the masoretic word entire, and of the
    alexandrian form only its tail. 42 places, and THEY ARE NOT COMPLETED.

    Two reasons, and the second is the binding one. The cut is not mechanical -
    SARAJW against HEM drops one masoretic letter and 'ABIKEM against HEM drops
    two, and both tails are two consonants; at 27,11d the tail is a single waw
    and the masoretic word already opens with one. AND NOTHING COULD CHECK THE
    RESULT: the seventeen completions on the masoretic side were allowed
    because BHSA verified every one of them, and this column has no verifier at
    all. That is the objection that keeps the justification gaps open, and it
    holds here. So the fragment is MARKED instead, and the page says it is a
    fragment rather than printing it as a reading.

    The bar is already known to be set INSIDE A WORD, which is what tightness
    means. What is left is to say which side is the fragment: the masoretic one
    if _supplied() can finish it, otherwise the alexandrian one, provided it is
    the shorter piece and neither side closes on a maqqef - a maqqef is a word
    boundary in Stipp's own terms and marks the third class of tight bar, a
    short whole-word variant bound by one. 62 bare tight bars, 17 masoretic
    abbreviations, 42 alexandrian, 3 left alone.
    """
    if _supplied(mt_vis, og_vis) or _cons(og_vis) >= _cons(mt_vis):
        return False
    mt_h = bwfonts.to_hebrew(mt_vis).strip()
    og_h = bwfonts.to_hebrew(og_vis).strip()
    if mt_h.endswith(MAQQEF) or og_h.endswith(MAQQEF):
        return False
    # A PROCLITIC IS A HEAD, NOT A TAIL. One letter under a sheva that is not a
    # final form can only open a word, so it is a variant of its own and not
    # the end of the masoretic one. 7,5b is the only place: Stipp sets 'IM \ WE
    # and the Greek has KAI POIOUNTES for the masoretic 'IM 'ASO. The test has
    # to be on the POINTS and on the form together - the 2fs suffix at 31,32 is
    # a KAF under a sheva too, and it is a tail, but it is the FINAL kaf.
    base, marks = _last_letter(og_h)
    if (_cons(og_vis) == 1 and base not in FINAL_FORM and SHEVA in marks):
        return False
    return True


SPACED_MIN = 3


def unspace(t):
    """Undo the letter-spacing Stipp uses to justify a short Greek line.

    247 spans of the Greek panel, on 129 of the 181 pages, are set SPERRT: a
    space between every character and TWO spaces between words, so that a short
    sentence fills its measure. Jer 4,30b is one -

        ' t i ,  p o i h , s e i j '   for   ti, poih,seij

    - and read as written it puts eight words on the page where there are two.
    The word boundary is the double space and the letter boundary the single
    one, so a group between double spaces whose parts are ALL single characters
    is a word, and its spaces are typography rather than text.

    Three or more parts are required. That is what keeps a real sequence of
    short words out of it: in this transliteration every one-letter Greek word
    carries a breathing or an accent and so is at least two characters (o` h`
    w-|), and a genuine one-character token is a fragment, not a word. The rule
    is applied to the GREEK ONLY - no Hebrew span in the book is set this way,
    and the Hebrew column has its own reason for single-character spans, the
    one-glyph-per-span setting of the 15th edition, where the spans carry no
    spacing at all.

    What is left to lxx_greek.repair() is the other kind of break, the word
    split across a justification gap - 'k ai.' at Jer 4,29 - where the pieces
    are not single characters and only the word list can say they belong
    together.
    """
    if "  " not in t:
        return t
    parts = re.split(r"(\s{2,})", t)
    for i in range(0, len(parts), 2):
        core = parts[i].strip(" ")
        toks = core.split(" ")
        if len(toks) >= SPACED_MIN and all(len(x) == 1 for x in toks):
            lead = parts[i][:len(parts[i]) - len(parts[i].lstrip(" "))]
            tail = parts[i][len(parts[i].rstrip(" ")):]
            parts[i] = lead + "".join(toks) + tail
    return "".join(parts)


SUB = str.maketrans("0123456789", "₀₁₂₃₄₅₆₇₈₉")
# The advance of a Times character at 9.88pt, measured at 1,1a, where
# '25,1b; Hos 1,1; Jo' runs from x = 30.2 to the e-diaeresis at 102.5.
W_APP = 4.0
SUP = str.maketrans("0123456789", "⁰¹²³⁴⁵⁶⁷⁸⁹")


def _margin_lines(pieces):
    """The margin of one sentence -> one note per printed line, as Stipp sets it.

    THE MARGIN WAS PRINTED AS A HEAP OF PIECES IN THE WRONG ORDER. At 1,2 Stipp
    sets two lines, '→ 1a' and '25,3a₁; 46,25b', and the page said
    '1a → ; 46,25b 25,3a 1'. Three things did it, and none touches the Hebrew:

    - split_columns() keeps a span in the margin only while the span AFTER it is
      also left of MARGIN_X - a lookahead that protects the lines whose x
      coordinates collapse - so the LAST piece of every margin line is handed to
      the text column, filed as 'sigla' and printed before the rest. That is
      where '1a' and '; 46,25b' went.
    - every span was a note of its own, so a reference set as several spans
      came apart into several items.
    - the Klammerkonstruktion index on a reference - the subscript 1 of 25,3a₁,
      set at 6.36pt - has a y of its own, so it arrived as a printed line of its
      own and was printed after everything else.

    So the pieces are gathered with their position - (line, y, x, size, kind,
    text) - from both places, a raised piece alone on its line rejoins the
    margin line nearest it in y, and each line is read left to right. Hebrew in
    the margin is a lemma set right to left, so a run of Hebrew pieces is joined
    in its raw left-to-right form and converted as one, which is what reverses
    it. The index is written as a subscript digit where it sits below the line
    and a superscript where it sits above, which is how Stipp prints it.
    """
    full = [p for p in pieces if p[3] >= 8]
    lines = collections.defaultdict(list)
    for p in pieces:
        key = p[0]
        if p[3] < 8 and not any(q[0] == p[0] for q in full):
            near = min(full, key=lambda q: abs(q[1] - p[1]), default=None)
            if near is not None and abs(near[1] - p[1]) < 4:
                key = near[0]
        lines[key].append(p)
    out = []
    for key in sorted(lines):
        ps = sorted(lines[key], key=lambda p: p[2])
        base = [p[1] for p in ps if p[3] >= 8]
        base = base[0] if base else None
        # THE SPACES ARE THE PDF'S OWN. A span carries the space that follows
        # it - ' 1a ', 'l 1,1; Mi 1,1' - and Joël at 1,1a is set as three
        # spans, Jo + ë + l, which a joiner that adds spaces prints 'Jo ë l'.
        # Position decides only where two spans meet with no space in either
        # and a clear gap between them.
        # Where the script changes - a Hebrew lemma and the German after it -
        # there is always a space; the width of Hebrew is only an estimate.
        words, heb, end, prev_heb = [], "", 0.0, False

        def put(t, x, w, is_heb=False):
            nonlocal end, prev_heb
            if words and t[:1] and not t[:1].isspace() and \
                    not words[-1][-1:].isspace() and \
                    (x - end > 2.5 or is_heb != prev_heb):
                t = " " + t
            words.append(t)
            end, prev_heb = x + w, is_heb

        for li_, y, x, fs, k, t in ps:
            if k == "HEB":
                if not heb:
                    hx = x
                heb += t
                hend = _right((x, y, k, fs, t))
                continue
            if heb:
                put(bwfonts.to_hebrew(heb), hx, hend - hx, True)
                heb = ""
            if k == "GRK":
                t = bwfonts.to_greek(t)
            elif fs < 8 and base is not None and t.strip().isdigit():
                t = t.strip().translate(SUB if y < base else SUP)
                if words:
                    words[-1] = words[-1].rstrip() + t
                    end = x + W_APP
                    continue
            put(t, x, W_APP * len(t))
        if heb:
            put(bwfonts.to_hebrew(heb), hx, hend - hx, True)
        # U+0451, Cyrillic yo, is how the font's e-diaeresis comes back.
        s = " ".join("".join(words).replace("ё", "ë").split())
        # A '(' that ENDS the margin line is not the margin's. pypdf can hand
        # back a whole printed line as one Times span from x = 30, and the '('
        # at its end then opens the apparatus of the text column: '| (' before
        # TOU THEOU at 1,1a. One that ends only its span is the margin's own -
        # '≙ (' + 'ὁ' + ')' two lines further down.
        s = s.rstrip("( ")
        if s:
            out.append(("margin", s))
    return out


def read_clause(lines, carry=(0, False)):
    """One clause -> (segments in READING order, notes, label, carry).

    THE TEXT COLUMN IS READ RIGHT TO LEFT AND THE MARKUP IS MIRRORED WITH IT.
    pypdf hands back the spans of a line left to right, which for Hebrew is
    backwards, so each line's text spans are walked in reverse and the characters
    inside a span with them. Every paired sign then swaps its role, because what
    the author typed as an opener is printed on the left and so is met last:

        in reading order    ] opens a masoretic plus       [ closes it
                            > opens an alexandrian plus    < closes it
                            § opens a notation             # closes it
                            ) opens an apparatus           ( closes it

    § and # are the pair that matters, and the Einleitung is explicit about them:
    "§ markiert den Beginn und # das Ende". Reading them the other way round -
    which the character stream invites, since # is met first when a clause is
    flattened left to right - leaves the notation of Jer 1,1a open at the § that
    ends its first line and never closes it at the # on its third.

    Only a NON-HEBREW span can carry markup. In BWHEBB these same characters are
    letters: # is a final tsade, [ an ayin, \\ a hataf qamats. Jer 1,2 sets
    AMOTS as #Ama' inside a Hebrew span, and reading that # as a boundary mark
    would close a notation that was never open.

    Text left over once the markup is taken out is reversed back before it is
    used, so the label span '§ a 1' still yields 'a 1' and '<(Impf)' still
    yields 'Impf'.

    THE STATE CARRIES ACROSS THE LINES OF A CLAUSE - the two bracket depths, the
    notation depth, and whether a backslash has been passed - because Stipp's
    notations do. In 1,1a the §, the masoretic reading and the backslash are on
    line one and the alexandrian reading runs on to line two.

    AND THE NOTATION DEPTH CARRIES ACROSS THE CLAUSES TOO, which is what `carry`
    is for. A § ... # states the reach of the bar inside it, and the reach is
    Stipp's, not the sentence division's: at 6,6 the § rides on the label of sentence d,
    the bar stands in sentence e and the # at its left edge, so read sentence by sentence
    the bar was bare, reached one word on each side, and the surplus of the
    ALEXANDRIAN reading stayed common - HOJ 'IR HA-SHEQER printed in the
    masoretic column, where BHS has only HI' HA-'IR HAPQAD. 17 verses carried an
    alexandrian reading that way, which is the one thing these pages must never
    do. See the two guards at the end of the function for how far it may run.

    A LINE BREAK IS A WORD BREAK UNLESS THE SPANS SAY OTHERWISE. Where a clause
    wraps, the two sides of the join carry no space between them - 1,1a ends its
    second line with BN-XLQJHW and opens its third with MN-HKHNJM - so one is
    inserted, but only where neither side already has one. (The space that once
    stood inside BI-SHLOSH at 1,2 was a hair space and is gone before this runs;
    see _true_spaces().)

    The margin is not reversed. It is set left to right and read that way; only
    the text column is Hebrew.
    """
    segs, notes, label, index = [], [], "", ""
    marg = []                       # margin pieces; see _margin_lines()
    # A NOTATION CAN RUN PAST THE END OF ITS SENTENCE, so it is handed in from the
    # sentence before and handed on to the sentence after. The two bracket depths are
    # NOT carried - a plus is re-opened at the head of every line and closes on
    # the same one.
    scope, bar = carry
    # WHICH NOTATION, not merely whether there is one. A sentence can carry two,
    # and only one of them may hold a bar; see split_variant(). A notation
    # inherited from the sentence before is numbered 1 here, its own number in the
    # sentence that opened it having gone with that sentence.
    notation = 1 if scope else 0
    n_notations = notation
    mt = og = 0
    pending_og = False
    newline = False
    pending_tight = None            # index of an mtvar cut by a TIGHT bar
    bare_span = None                # what the last bare bar marked, in case
                                    # nothing turns up on the other side
    tight_pairs = []                # (mtvar index, ogvar index) for those
    scope_tight = []                # index where a TIGHT scoped bar handed over

    def cls():
        if mt > 0:
            return "plus"
        if og > 0:
            return "minus"
        if scope > 0:
            return "scope"
        return "common"

    def add(t):
        """Append one Hebrew span as a segment, in reading order.

        A span of nothing but space is spacing, not a word. It must not consume
        the backslash's forward reference: at Jer 2,36a Stipp sets MH-TZLJ, the
        backslash, a bare space, an apparatus, and only then the alexandrian
        TAZELLJ, and letting the space take the reference left the whole of
        TAZELLJ M'D L-SHNWT 'T-DRKK in the masoretic column as common text.
        """
        nonlocal pending_og, newline, pending_tight
        if not t.strip():
            # A spacing span already supplies the break, so the line-break rule
            # below has nothing left to do on this line.
            newline = False
            segs.append((cls(), t, bar, notation))
            return
        # THE LINE-BREAK RULE FIRES ONCE, ON THE LINE'S FIRST SPAN OF TEXT, AND
        # THE FLAG MUST BE CLEARED EVEN WHEN THERE IS NOTHING BEFORE IT TO JOIN
        # TO. Clearing it only inside the `segs` test left it standing through
        # the whole first line of a clause, so the line's SECOND span was
        # treated as the far side of a line break and a space was inserted
        # inside a word. That is what separated the bracketed conjunction from
        # its noun at 4,5b and the bracketed T' from its verb at 4,2 - the two
        # pieces stopped being written hard against each other, so to_logical()
        # no longer set `j` and the page set them as two words. It also cut
        # words that carry no bracket at all wherever the 15th edition emits
        # them one glyph per span: B-JHWDH at 4,5a came out as two spans and so
        # lost the hiriq under its bet.
        if newline:
            if segs:
                prev = segs[-1][1]
                if not (t[-1:].isspace() or prev[:1].isspace()):
                    t += " "
            newline = False
        c = cls()
        if pending_og and c == "common":
            head, tok = last_token(t)
            pending_og = False
            mi, pending_tight = pending_tight, None
            if tok.strip() and head.strip():
                segs.append(("ogvar", tok, bar, notation))
                if mi is not None:
                    tight_pairs.append((mi, len(segs) - 1))
                segs.append((c, head, bar, notation))
                return
            if tok.strip():
                segs.append(("ogvar", t, bar, notation))
                if mi is not None:
                    tight_pairs.append((mi, len(segs) - 1))
                return
        pending_og = False
        pending_tight = None
        segs.append((c, t, bar, notation))

    def bare_slash(tight=False):
        """A backslash outside a notation refers to ONE WORD on each side.

        The Einleitung: "Schrägstrich \\ und Stern * betreffen beiderseits den
        kleinstmöglichen Verweisrahmen. Dabei wird ein Makkef, wann immer
        möglich, wie ein Spatium behandelt." Only where the frame is in doubt
        does Stipp mark it with § ... #, and then the notation says how far it
        reaches.

        Reading a bare backslash as dividing the WHOLE clause - which this
        script did until 2026-09-05 - wrecked exactly the verses it was meant to
        describe. Jer 1,2 marks one word, BN-'AMON against 'AMOTS; the old
        reading gave the masoretic column four words and handed MLK JHWDH
        B-SHLOSH 'ESREH SHANH L-MOLKW to the alexandrian column alone.

        (34) AND THE BACKWARD REFERENCE MUST NOT BE SWALLOWED BY A SPACE, which
        is the rule add() has kept for the FORWARD one since 2,36a and this
        function never had. Stipp sets his apparatus inline, and the gap around
        it arrives as a Hebrew span of nothing but space; standing between the
        masoretic word and the bar it left this function looking at spacing,
        finding no word to mark, and giving up. The masoretic reading then
        stayed `common` and printed in the ALEXANDRIAN column as well: 13,16f
        read JASHIT JUSHAT LA-'ARAFEL where only the second word is
        alexandrian. 20 sentences of the book, and no figure here can see them,
        since `common` and `mtvar` both stand in the masoretic column.

        So the last segment CARRYING TEXT is the one the bar reaches back to,
        and the spacing that follows it stays where it is.

        AND A WORD IS NOT A SEGMENT. The 15th edition emits much of its Hebrew
        one glyph per span, so the word nearest the bar can arrive as several
        segments of which the last is a single letter or a bare point: marking
        that alone cut LO' JE'ASFU into LO' JE'ASF and a lone WAW at 8,2g, and
        left the tsere of the JOD behind with LO'. The run that makes one word
        is gathered by the INNER edges of its segments - the left edge of the
        right-hand one against the right edge of the left-hand one, since the
        column runs right to left while a segment's ASCII does not - and the
        whole of it is marked.
        """
        nonlocal pending_og, pending_tight, bare_span
        bare_span = None
        i = next((k for k in range(len(segs) - 1, -1, -1)
                  if segs[k][1].strip()), None)
        at = None
        if i is not None and segs[i][0] == "common":
            j = i
            while (j > 0 and segs[j - 1][0] == "common"
                   and segs[j - 1][1]
                   and not segs[j - 1][1][:1].isspace()
                   and not segs[j][1][-1:].isspace()):
                j -= 1
            c, t, b, sc = segs[j]
            tok, rest = first_token(t)
            if tok.strip() and rest.strip():
                segs[j] = (c, rest, b, sc)
                segs.insert(j + 1, ("mtvar", tok, b, sc))
                first, i = j + 1, i + 1
            elif tok.strip():
                segs[j] = ("mtvar", t, b, sc)
                first = j
            else:
                first = None
            if first is not None:
                for k in range(first, i + 1):
                    if segs[k][0] == "common":
                        segs[k] = ("mtvar",) + tuple(segs[k][1:])
                at, bare_span = i, (first, i)
        pending_og = True
        pending_tight = at if tight else None

    for li, line in enumerate(lines):
        margin, text = split_columns(line)
        labsps = {id(line[i]) for i in label_spans(line)} if li == 0 else set()
        newline = True
        # A BAR INSIDE A WORD IS SET HARD AGAINST THE TEXT ON BOTH SIDES, and
        # that is read off the printed line, before it is taken apart. See the
        # note on the abbreviated masoretic word above.
        tight_at, flat, owner = set(), [], []
        for sp_ in text:
            for ci_, ch_ in enumerate(sp_[4]):
                flat.append(ch_)
                owner.append((id(sp_), ci_))
        for i_, ch_ in enumerate(flat):
            if ch_ != BAR or not 0 < i_ < len(flat) - 1:
                continue
            if not (flat[i_ - 1].isspace() or flat[i_ + 1].isspace()):
                tight_at.add(owner[i_])

        paren, note_buf = 0, []
        for sp in reversed(text):
            x, y, k, fs, t = sp
            if k in ("HEB", "GRK"):
                if paren:
                    note_buf.append(("heb" if k == "HEB" else "grk",
                                     t if k == "HEB" else unspace(t)))
                elif k == "HEB":
                    add(t)
                else:
                    notes.append(("grk", bwfonts.to_greek(unspace(t))))
                continue
            if k == "BOLD":
                for m in ID.findall(t):
                    notes.append(("id", m))
                continue
            # ONLY THE CLAUSE'S FIRST LINE CARRIES ITS LABEL, and that is where
            # has_label() found it. Later lines put things in the same zone that
            # are not labels: Stipp raises a D for Dittographie or a P for
            # Parablepsis after the bracket it qualifies, and at Jer 2,17 that D
            # sits at x = 351 on the clause's last line. Taken into the label it
            # made the label '17 D', which LABEL rejects, and the verse number
            # was never read - so 2,17 was filed under 2,16 and vanished. It is
            # 73 verses across the book that go that way.
            islabel = id(sp) in labsps
            buf = ""
            for ci in range(len(t) - 1, -1, -1):
                c = t[ci]
                if paren:
                    if c == "(":
                        paren -= 1
                        if not paren:
                            note_buf.append(("txt", buf[::-1]))
                            buf = ""
                            notes.append(("app", note_buf))
                            note_buf = []
                        continue
                    if c == ")":
                        paren += 1
                    buf += c
                    continue
                if c == ")":
                    paren = 1
                    buf = ""
                elif c == "]":
                    mt = 1
                elif c == "[":
                    mt = 0
                elif c == ">":
                    og = 1
                elif c == "<":
                    og = 0
                elif c == "§":
                    scope += 1
                    if scope == 1:
                        n_notations += 1
                        notation = n_notations
                elif c == BAR:
                    if scope > 0:
                        bar = True
                        if (id(sp), ci) in tight_at:
                            scope_tight.append(len(segs))
                    else:
                        bare_slash((id(sp), ci) in tight_at)
                elif c == "#":
                    scope = max(0, scope - 1)
                    if not scope:
                        bar = False
                        notation = 0
                else:
                    buf += c
            if paren:
                note_buf.append(("txt", buf[::-1]))
            elif islabel and fs < 8:
                # THE KLAMMERKONSTRUKTION INDEX, kept apart from the label so
                # that it can never be read as a verse number. That is the trap
                # the size guard was put here for: Jer 4,23a is labelled 'a1 23'
                # and reading its last number flat filed the verse under 4,22,
                # which cost 61 verses. It belongs to the LETTER - b1, b2 - and
                # is given back to it in parse().
                index += buf[::-1]
            elif islabel:
                # THE SMALL DIGIT IN A LABEL IS NOT A VERSE NUMBER. Stipp counts
                # the parts of a Klammerkonstruktion with index figures - a1,
                # a2, a3 - and sets them at 6.36pt beside a label at 9.88pt.
                # Jer 4,23a is labelled 'a1 23'; read flat, its last number is
                # the 1, which is below the verse already reached, so the 23 was
                # thrown away and the whole verse was filed under 4,22. Sixty-one
                # verses of the book go missing that way.
                label += buf[::-1]
            elif buf.strip() and x < MARGIN_X and \
                    buf.strip() not in ("|", "*"):
                # Margin text the lookahead in split_columns() handed to the
                # text column; see _margin_lines().
                marg.append((li, y, x, fs, "APP", buf[::-1]))
            elif buf.strip():
                notes.append(("sigla", buf[::-1].strip()))
        # THE MARGIN IS READ LAST, BECAUSE IT IS ON THE LEFT. Its text is
        # German and Latin and stays in its own direction, but the markup in it
        # is the line's markup and has to be applied, at the point in the
        # reading where it stands - after everything in the text column. A
        # notation that reaches to the end of a line closes with its # out
        # there in the margin: Jer 2,3a sets the whole of KODESH JISRAEL
        # L-YHWH \ KEDOSH JISRAEL NE'UM-YHWH between a § at the right edge and
        # a # at x = 30, and ignoring that # left the notation open into the
        # next line, so R'SHIT TBW'TH was read as alexandrian and the masoretic
        # column lost it.
        for x, y, k, fs, t in margin:
            if k in ("HEB", "GRK"):
                marg.append((li, y, x, fs, k, t))
                continue
            if k == "BOLD":
                for m in ID.findall(t):
                    notes.append(("id", m))
                continue
            # A BRACKET IN THE MARGIN IS ONLY MARKUP AT THE END OF THE SPAN.
            # The margin holds Stipp's own sigla as well as the line's markup,
            # and '>' is both: between the readings it opens an alexandrian
            # plus, but in a margin note it means "fehlt in" and is followed by
            # the witness - '7,30-8,3 > 4Q70* (4QJer a*)' at Jer 8,1, where
            # reading it as a bracket opened a plus that never closed and
            # handed the whole of 8,1b to the alexandrian column, 89 letters,
            # the largest single loss in the book. The two are told apart by
            # position: real markup is the LEFTMOST thing on the printed line,
            # so nothing but space follows it in the span, while a siglum has
            # its reference after it. Of the 636 bracket characters in margin
            # spans, 623 end their span and 13 do not.
            tail = len(t.rstrip())
            while tail and t[tail - 1] in MARKUP:
                tail -= 1
            buf = ""
            for i, c in enumerate(t):
                if c in MARKUP and i < tail:
                    buf += c
                    continue
                if c == "(":
                    # Counted for the line's apparatus AND kept for the reader:
                    # the margin's own parentheses are part of its text, as in
                    # '7,30-8,3 > 4Q70* (4QJer a*)' at 8,1. One that ends the
                    # whole margin line is dropped in _margin_lines().
                    paren = max(0, paren - 1)
                    buf += c
                elif c == ")":
                    paren += 1
                    buf += c
                elif c == "]":
                    mt = 1
                elif c == "[":
                    mt = 0
                elif c == ">":
                    og = 1
                elif c == "<":
                    og = 0
                elif c == "§":
                    scope += 1
                    if scope == 1:
                        n_notations += 1
                        notation = n_notations
                elif c == "#":
                    scope = max(0, scope - 1)
                    if not scope:
                        bar = False
                        notation = 0
                elif c == "\\":
                    # A BACKSLASH CAN END UP OUT HERE TOO. It marks the join
                    # between the two readings, so on a long line it falls at
                    # the far left, which is where the margin is. Jer 10,17 sets
                    # it at x = 30.2 with BA-MATSOR beside it; ignoring it left
                    # the alexandrian 'SP MI-XWTS KIN'ATEK JOSHEBET BA-MIBXAR
                    # standing in the masoretic column as well.
                    if scope > 0:
                        bar = True
                    else:
                        bare_slash()
                else:
                    buf += c
            if buf.strip():
                marg.append((li, y, x, fs, "APP", buf))

        if paren:                       # an apparatus that never closed
            note_buf = [n for n in note_buf if n[1] and n[1].strip()]
            if note_buf:
                notes.append(("app", note_buf))
            paren = 0

    # A BAR WITH NOTHING AFTER IT IN THE SENTENCE MARKS NOTHING BEFORE IT. The
    # backward reference is only warranted once the forward one has been
    # answered: a bar divides two readings, so if the alexandrian side never
    # arrives the parser has not found a variant and has no ground for taking
    # the masoretic word out of the shared text. At 36,1a the bar stands at
    # the end of the sentence and JEHUDAH would have left the alexandrian column,
    # where the Greek has BASILEOS IOUDA.
    if pending_og and bare_span:
        for k in range(bare_span[0], bare_span[1] + 1):
            if segs[k][0] == "mtvar":
                segs[k] = ("common",) + tuple(segs[k][1:])

    # THE SAME THING INSIDE A SCOPED NOTATION. A bare bar reaches one word on
    # each side, so where the letters the two forms share run over MORE than one
    # word Stipp has to mark the reach with § ... # - and then the whole of the
    # alexandrian side, not just its first word, is what completes the masoretic
    # head. 7,9 is the only place in the book: he sets HA \ WE-GANOB * <WE>-
    # RATSOAH WE-NA'OF, and the masoretic reading is HA-GANOB RATSOAH WE-NA'OF -
    # the alexandrian side entire, less its own first letter, and less the WE
    # his brackets already mark as alexandrian. The star is his sign for the
    # transposition: the Greek has the three verbs in another order, murder,
    # adultery, theft.
    for bi in sorted(scope_tight, reverse=True):
        if not 0 < bi <= len(segs) or not segs[bi - 1][3] or segs[bi - 1][2]:
            continue
        og = [i for i in range(bi, len(segs)) if segs[i][3] and segs[i][2]]
        og = [i for i in og if segs[i][0] not in ("plus", "minus")]
        if not og:
            continue
        tail = _supplied(segs[bi - 1][1], segs[og[0]][1])
        if not tail:
            continue
        b, sc = segs[bi - 1][2], segs[bi - 1][3]
        carry = [tail] + [segs[i][1] for i in og[1:]]
        for t in reversed(carry):
            segs.insert(bi, ("mtsup", t, b, sc))

    # THE ABBREVIATED MASORETIC WORD, FINISHED FROM THE OTHER COLUMN. Highest
    # index first, so that an insertion cannot move a pair not yet done.
    for mi, oi in sorted(tight_pairs, reverse=True):
        if segs[mi][0] != "mtvar" or segs[oi][0] != "ogvar":
            continue
        tail = _supplied(segs[mi][1], segs[oi][1])
        TIGHT_LOG.append((segs[mi][1], segs[oi][1], tail))
        if tail:
            segs.insert(mi + 1, ("mtsup", tail, segs[mi][2], segs[mi][3]))
        elif _og_abbreviated(segs[mi][1], segs[oi][1]):
            segs[oi] = ("ogabbr",) + tuple(segs[oi][1:])
    # THE NOTATION MAY CROSS A SENTENCE BOUNDARY BUT THE BAR MAY NOT. What follows
    # the bar is the alexandrian reading, and Stipp does not run one past the
    # end of the sentence it belongs to; a '#' that turns up on the next sentence
    # closes a notation whose business is already done. Carrying the bar as well
    # costs 33,6 and 48,9, where the whole of the next sentence goes to the
    # alexandrian column and out of the masoretic one, and gains nothing.
    #
    # THE OTHER HALF OF THE CONDITION IS bar_inside(), ON THE SENTENCE THAT FOLLOWS,
    # and parse() applies it: a notation reaches only where the next sentence puts
    # a bar in it. Two further bounds were tried and are not here because they
    # measured as inert once that lookahead was in place - a ceiling on how many
    # sentences a notation may cross, and a refusal to hand one on from a sentence
    # that has already resolved a bare bar. With the lookahead only five sentences
    # in the book inherit a notation at all and none inherits it twice, so a
    # ceiling has nothing to bound and the book's one reversed pair, at 21,8c,
    # is stopped by the lookahead instead.
    notes.extend(_margin_lines(marg))
    return segs, notes, label, index, (scope, bar) if scope and not bar else (0, False)


def bar_inside(lines):
    """Does this sentence put a bar inside a notation that is already open?

    The lookahead the carry needs, and it reads the markup in the same order
    read_clause() does - the text column right to left, then the margin, which
    is on the left and keeps its own direction.

    STIPP HAS TWO NOTATIONS AND ONLY ONE OF THEM MAY REACH. A § ... # with a bar
    in it states the reach of that bar; a § ... # with no bar is the marked
    stretch where the two editions have the SAME consonants and the difference
    is described in the note. Carried into the second kind, the whole of the
    next sentence goes to the masoretic column and the alexandrian cell empties:
    48,38 sets K-KLI, then 'EN-XEFETS BW, a '*' and NE'UM-YHWH inside one
    notation with no bar anywhere in it, where the star is the transposition
    sign and the Greek has all of it - hos aggeion hou ouk estin chreia autou -
    in another order. It also stops the book's one REVERSED pair from running
    away: at 21,8c the '#' rides on the label and the '§' stands at x = 187
    after the bar, so the pair brackets the bar but the opener is met last, and
    the notation the trailing § opens has no close anywhere. Carried, it ran
    nine sentences to 21,10c and emptied the alexandrian cell of every one.
    """
    for line in lines:
        margin, text = split_columns(line)
        for sp in reversed(text):
            if sp[2] in ("HEB", "GRK"):
                continue
            for c in reversed(sp[4]):
                if c == BAR:
                    return True
                if c == "#":
                    return False
        for sp in margin:
            if sp[2] in ("HEB", "GRK"):
                continue
            for c in sp[4]:
                if c == BAR:
                    return True
                if c == "#":
                    return False
    return False


def split_variant(segs, handed_on=False):
    """Resolve the notations: decide which column each segment belongs to.

    The Einleitung: "Entsprechend der linksläufigen Schreibrichtung steht rechts
    vor dem Schrägstrich die tiberische Lesart; links danach folgt die
    alexandrinische." The segments arrive in READING order, so the tiberian
    reading is the one met BEFORE the backslash and the alexandrian the one met
    after.

    A BARE backslash has already been resolved word by word in read_clause, and
    those segments arrive here labelled. What is left to do is the SCOPED case,
    § ... #, where the notation states its own reach: inside it the backslash
    divides the two editions, and everything outside is common to both.

    (33) A NOTATION WITH NO BAR IN IT IS NOT A VARIANT. Stipp has two, and the
    module docstring has always said so: `§ A \ B #` states the reach of the
    bar, while `§ A #` is a marked stretch with no alternative, where the two
    editions have THE SAME CONSONANTS and the difference is described in the
    note - a transposition, marked with his `*`, or a matter of pointing. Read
    as a variant it went to the masoretic column alone and the alexandrian cell
    emptied. 71 sentences of the book, 809 consonants, of which 33 carry the star.

    The evidence is Stipp's own Greek, printed beside 44 of them: at 1,19c the
    alexandrian cell held nothing while the Greek reads TOU EXAIRESTHAI SE
    LEGEI KYRIOS, which is both of the marked words in the other order. Nothing
    here can be seen by the BHSA check, which reads the masoretic column only
    and to which `common` and `mtvar` look alike - so this fault stood behind
    (30), which had exactly the same cause on the other side of the page.

    WHICH notation, not whether there is one: a sentence can carry two of which
    only one holds a bar, and 41,6a is the single place in the book where that
    happens - the first marks the transposition of JISHMA'EL BEN-NETANJAH
    LIQRA'TAM, which the Greek has entire in the other order, and the second is
    a real variant. `handed_on` says
    the still-open notation reaches into the next sentence, where parse() has
    already established by lookahead that the bar is; without it the sentence that
    opens a notation and passes it on would read as common, and 6,6d would put
    HI' HA-'IR into the alexandrian column, where the Greek has HOJ.
    """
    barred = set(sc for _, _, b, sc in segs if sc and b)
    if handed_on:
        still_open = next((sc for _, _, _, sc in reversed(segs) if sc), 0)
        if still_open:
            barred.add(still_open)
    out = []
    for c, t, b, sc in segs:
        if c in ("plus", "minus", "mtvar", "ogvar", "ogabbr", "mtsup"):
            out.append((c, t))
        elif sc in barred:
            out.append(("ogvar" if b else "mtvar", t))
        else:
            out.append(("common", t))
    return out


# (44) BARE BARS WHOSE REACH IS WIDER THAN ONE WORD, BY NAME. The Einleitung
# makes one word on each side the default - "den kleinstmöglichen
# Verweisrahmen", with a maqqef treated as a space "wann immer möglich" - and
# the default is right at all but these four places, where the sense, and the
# Greek beside it, show a frame Stipp did not mark with § ... #. Nothing in the
# print tells them apart from the six bars where the same shape IS one word,
# so they are listed here, each confirmed by the author against the PDF on
# 2026-10-01, and not inferred. (back, fwd) = how many MORE words than one the
# masoretic side reaches before the bar and the alexandrian side after it; a
# maqqef ends a word here, as it does for the bar itself.
WIDE_BARS = {
    # 'L-HM \ 'L-H'M: the Greek PROS TON LAON TOUTON; the maqqef pair is the
    # alexandrian reading, and MT has no H'M.
    ("Jeremiah", 13, 12, "a"): (0, 1),
    # WE-HEHARASH \ WE-KOL-HOR: MT has no HOR.
    ("Jeremiah", 29, 2, ""): (0, 1),
    # WE-SHATAH \ WE-LO' JISHTU: KAI OU PIONTAI, two words.
    ("Jeremiah", 22, 15, "d"): (0, 1),
    # 'ANSHEJ HA-MILHAMAH \ HA-'ANASHIM HA-NILHAMIM: two words on each side,
    # the Greek TON ANTHROPON TON POLEMOUNTON.
    ("Jeremiah", 38, 4, "c"): (1, 1),
    # THE REVERSED PAIR. HINNENI NOTEN \ HINNEH 'ANI NATATTI, the one place
    # in the book where Stipp sets '#' before '§'. Read in his order the
    # notation never closes, and changing the order rule for one verse would
    # break the 87 that set it the usual way; the reach the pair states is
    # given here instead.
    ("Jeremiah", 21, 8, "c"): (1, 2),
}

# BARS WHOSE ALEXANDRIAN SIDE IS ONLY AN APPARATUS, BY NAME: Stipp gives the
# Greek and its root instead of a retroverted word, and the Hebrew after the
# apparatus is common to both editions. Read as a bar, that word was taken for
# the alternative and the masoretic column lost it. At 2,36a the same shape
# has the alexandrian word AFTER the apparatus, so this is the author's
# judgement case by case (2026-10-01), not a rule.
APPARATUS_ONLY = {
    # WE-NAS'U \ (KAI ARTHESETAI √ NS') BA-'EDER: BA-'EDER is shared.
    ("Jeremiah", 31, 24, "b"),
}


def _apparatus_only(row):
    i = next(k for k, s_ in enumerate(row["og"]) if s_["cls"] == "ogvar")
    shared = row["og"][i]["text"]
    row["og"][i]["cls"] = "common"
    m = next(k for k, s_ in enumerate(row["mt"]) if s_["cls"] == "mtvar")
    row["mt"].insert(m + 1, {"cls": "common", "text": shared})


WIDENED = []


def _words(t):
    """Logical Hebrew -> its whitespace-separated words, spacing kept, so that
    nothing is lost in joining them again: a pattern that split at the maqqef
    dropped the one in KI- HU' at 38,4c. A word opening with a maqqef - -HA'AM
    at 13,12 - is the second half of a pair whose first half is the variant."""
    return re.findall(r"\s*\S+", t)


def _widen(row, back, fwd):
    """Move words across the bar of a WIDE_BARS sentence, in both columns."""
    def shift(segs, var):
        i = next(k for k, s in enumerate(segs) if s["cls"] == var)
        if fwd:
            nx = segs[i + 1]
            assert nx["cls"] == "common", (row["ch"], row["v"], nx)
            ws = _words(nx["text"])
            moved, rest = "".join(ws[:fwd]), "".join(ws[fwd:]).strip()
            if var == "ogvar":          # the alexandrian reading takes them
                segs[i]["text"] += moved if moved.lstrip()[:1] == "־" \
                    else " " + moved.strip()
            if rest:                    # the masoretic column drops them
                nx["text"] = rest
                nx.pop("j", None)
            else:
                del segs[i + 1]
        if back:
            pv = segs[i - 1]
            assert pv["cls"] == "common", (row["ch"], row["v"], pv)
            ws = _words(pv["text"])
            moved, rest = "".join(ws[-back:]).strip(), "".join(ws[:-back])
            if var == "mtvar":
                segs[i]["text"] = moved + " " + segs[i]["text"]
            if rest.strip():
                pv["text"] = rest.strip()
            else:
                del segs[i - 1]
    shift(row["mt"], "mtvar")
    shift(row["og"], "ogvar")


DOUBLE_MARK = re.compile(r"([\u0591-\u05c7])\1+")


def to_logical(segs):
    """Visual-order ASCII segments -> logical-order Unicode, merged by class.

    Consecutive segments of the same class are concatenated AS ASCII and
    converted once, never converted separately and joined with a space. The 15th
    edition emits much of its Hebrew one glyph per span, so a joining space makes
    every glyph a word: it inflated the masoretic plus from 3,464 words to 4,993.
    The spans carry their own spacing, and whitespace-only Hebrew spans are kept
    upstream for that reason - the same guard parse_stipp.py needs.

    Each segment also records `j`, whether it is written hard against the segment
    before it with no space between. Stipp brackets INSIDE a word wherever the
    two editions differ only in spelling - MISHPEH[O]T at 2,4, where the plene
    waw is a masoretic plus - and that arrives as three segments of one word. The
    flag is what lets the page set them as one word while still colouring the
    waw. It is read off the ASCII before conversion, because to_hebrew() strips
    the spacing it is derived from: the segments are in VISUAL order, so the gap
    between two logically adjacent segments is the junction between them the
    other way round.
    """
    groups = []
    for c, t in segs:
        if groups and groups[-1][0] == c:
            groups[-1][1] += t
        else:
            groups.append([c, t])
    rev = list(reversed(groups))
    out, last = [], None
    for i, (c, t) in enumerate(rev):
        # (53) A POINT PRINTED TWICE IS ONE POINT. Stipp's PDF draws a few marks
        # twice on the same letter, one over the other, invisible on paper:
        # at 4,16 the raw text is H;; - two patahs on the he of HAZKIRU - and
        # the page printed both. Two identical points on one letter are never
        # a reading.
        u = DOUBLE_MARK.sub(r"\1", bwfonts.to_hebrew(t))
        if not u:
            continue
        seg = {"cls": c, "text": u}
        if out and last == i - 1:
            prev_raw = rev[i - 1][1]
            if not (t[-1:].isspace() or prev_raw[:1].isspace()):
                seg["j"] = 1
        out.append(seg)
        last = i
    return _bind_lone_proclitics(out)


# One consonant of the proclitic set with its points, standing as a word.
# Maqqef (05BE) and sof pasuq (05C3) are not points and end the match, and so
# does a holam (05B9, 05BA): a waw with holam is the suffix -O, never a prefix,
# and the 3ms suffix left behind by the plus [LIBB]O at 23,17 was bound
# forward to 'AMRU by the first draft.
LONE = "[ובלכמהש][֑-ָֻ-ֽֿ-ׂׄ-ׇ]*"
LONE_INSIDE = re.compile(r"(?:(?<=\s)|^)(" + LONE + r")\s+(?=[א-ת])")
LONE_WHOLE = re.compile(r"^\s*" + LONE + r"\s*$")
LONE_INSIDE_MID = re.compile(r"(?<=\s)(" + LONE + r")\s+(?=[א-ת])")


def _bind_lone_proclitics(segs):
    """(41) A SINGLE PROCLITIC CONSONANT IS NEVER A WORD. WE, BE, LE, KE, ME, HA
    and SHE are prefixes, and one standing alone in a column was cut from its
    word by Stipp's typography, never by his text. Three ways it happened, all in
    the masoretic column and all with a space Stipp sets for the OTHER reading or
    for a sign: 46,5d WE \\ KI GIBBOREHEM, where the masoretic side of the bar is
    the waw alone and the space belongs to the Greek's KI; 17,27a WE<HAJAH> |
    'IM, with the plus and a siglum between; 52,22b WE§ QOMAT, a notation opened
    inside the word with a space after its sign.

    ONE CONSONANT AND NOT TWO: MAH, LO, BO, KOH, BAH are words spelled only with
    proclitic letters. The abbreviated alexandrian tail is exempt, because at
    27,11d Stipp's tail is a single waw that ENDS a word.
    """
    # A SEGMENT JOINED TO THE ONE BEFORE IT IS THE END OF A WORD, not a word:
    # Stipp brackets a plene waw or a suffix inside its word, SHUDDEDU at 4,20
    # and LIBBO at 23,17, and the first draft of this rule bound those letters
    # to the NEXT word as well and cost 17 verses their word division.
    for i, s in enumerate(segs):
        if s["cls"] == "ogabbr":
            continue
        joined = bool(s.get("j"))
        s["text"] = (LONE_INSIDE_MID if joined else LONE_INSIDE).sub(
            lambda m: m.group(1), s["text"])
        if not joined and LONE_WHOLE.match(s["text"]) and \
                i + 1 < len(segs) and segs[i + 1]["cls"] != "ogabbr":
            s["text"] = s["text"].strip()
            segs[i + 1]["j"] = 1
    return segs


def note_text(n):
    kind_, payload = n
    if kind_ in ("grk", "id", "margin", "sigla"):
        return {"kind": kind_, "text": payload}
    parts = []
    for k, t in payload:
        if k == "heb":
            t = bwfonts.to_hebrew(t)
        elif k == "grk":
            t = bwfonts.to_greek(t)
        if t and t.strip():
            parts.append(t.strip())
    return {"kind": "app", "text": " ".join(parts)}


def margin_text(spans):
    parts = []
    for x, y, k, fs, t in spans:
        if k == "HEB":
            t = bwfonts.to_hebrew(t)
        elif k == "GRK":
            t = bwfonts.to_greek(t)
        if t and t.strip():
            parts.append(t.strip())
    return " ".join(parts)


def greek_clauses(spans, glo, ghi, marks=None, gmarks=None, ys=None):
    """The Greek panel -> [(verse, clause)], one clause per printed line.

    `glo/ghi` is the verse range the panel's own numbers belong to: the Greek one
    where the heading gives a separate reference, the masoretic one otherwise.

    A FOOTNOTE MARK IS NOT A VERSE NUMBER. Three of the book's footnotes are on
    the Greek - 17 on p. 83, 18 on p. 86, 19 on p. 119 - and their marks stand in
    the panel after the word they qualify, where any digits were read as the
    number of the next Greek verse. They are recognised by _take_footnotes(),
    skipped here, and recorded in `gmarks` as (footnote, index of the clause that
    carries it), so that parse() can put the footnote beside that Greek.
    """
    marks = marks or {}
    out = []
    gv, buf, buf_y = None, "", None

    def flush():
        # `ys`, if given, receives the height of each clause's printed line, in
        # step with `out`: the first span that starts in the clause, or the
        # next one where the clause began after a newline inside a span.
        nonlocal buf, buf_y
        if gv is not None and buf.strip():
            g = bwfonts.to_greek(buf)
            if g:
                if LXX_VOCAB:
                    g = " ".join(_repair(g.split(), LXX_VOCAB))
                out.append((gv, g))
                if ys is not None:
                    ys.append(buf_y)
        buf, buf_y = "", None

    for sp in spans:
        x, y, k, fs, t = sp
        if k == "GRK":
            # A SPAN BOUNDARY IS A WORD BOUNDARY UNLESS THE SPANS SAY OTHERWISE
            # - the same rule read_clause() applies to a line break, and needed
            # here for the same reason. The Greek panel sometimes sets a sentence
            # as several spans with no space at the seam, and concatenating
            # them ran whole phrases into one word: EIPEIN TW SARAIA HUIW
            # NERIOU HUIOU MAASAIOU at 51,59c came out as a single token, and
            # four other clauses with it. Splitting a word that the PDF broke
            # across a seam is the safe direction, because lxx_greek.repair()
            # puts those back from the word list; running two words together is
            # not, because nothing downstream can undo it.
            parts = unspace(t).split(chr(10))
            head = parts[0]
            if buf and head and not buf[-1:].isspace() and not head[:1].isspace():
                buf += " "
            if head.strip() and buf_y is None:
                buf_y = y
            buf += head
            for pc in parts[1:]:
                flush(); buf = pc
        elif id(sp) in marks:
            if gmarks is not None:
                gmarks.append((marks[id(sp)],
                               len(out) if buf.strip() else len(out) - 1))
        else:
            if chr(10) in t:
                flush()
            for n in re.findall(r"\d+", t):
                n = int(n)
                if glo <= n <= ghi:
                    flush(); gv = n
                elif x < GREEK_NUM_X and t.strip().isdigit():
                    # (49) A VERSE NUMBER OUTSIDE THE HEADING'S RANGE STILL
                    # STARTS A VERSE. Stipp sets a Greek verse the heading does
                    # not name where the Greek order puts it - the Kedar oracle,
                    # G 30,6-11, on the page headed G 30,12-16 - and its lines
                    # were appended to the verse before, so 49,27 carried
                    # Kedar's camels. The numbers stand at x = 451: 1,316 in
                    # range, 32 out of it; the page numbers sit at x = 794-804.
                    flush(); gv = n
    flush()
    return out


GREEK_NUM_X = 460.0        # a Greek verse number stands at x = 451


GREEK_GEOMETRIC = []       # (verse key, all lines placed by position?) per verse


def place_greek_by_position(rows, row_of, cls_, greek, gys, gch):
    """(51) Each Greek line goes beside the Hebrew sentence it is printed level
    with - read off the page, not inferred.

    STIPP SETS THE GREEK PANEL ROW BY ROW BESIDE THE HEBREW: of the book's
    5,182 Greek lines, 5,181 stand at the height of a printed line of exactly
    one Hebrew sentence, and none is level with two. Until step 4 that could not
    be used, because pypdf's heights were not comparable across a page, and the
    Greek was placed by inference instead: verses dealt out in order or aligned
    by length (48)-(50), sentences within a verse matched on length (24). A
    Greek sentence wrapped over two printed lines also became two "sentences"
    that way, which alone kept 359 verses from being one to one.

    A line level with no sentence - one in the book - continues the sentence
    above it, and its verse is marked as inferred. `galign` is now "exact" for
    a verse every one of whose Greek lines was placed by position, "approx"
    otherwise.
    """
    heights = []                    # (y, row index) for every printed line
    for ci, cl in enumerate(cls_):
        if ci in row_of:
            for ln in cl:
                heights.append((ln[0][1], row_of[ci]))
    placed = collections.defaultdict(list)
    inferred = set()
    for (gv, text), y in zip(greek, gys):
        hit = {r for h, r in heights if y is not None and abs(h - y) <= 1.0}
        if len(hit) == 1:
            r = hit.pop()
        else:
            above = [r for h, r in heights if y is not None and h > y]
            r = (max(above) if above else
                 (min(r_ for _, r_ in heights) if heights else None))
            if r is None:
                continue
            inferred.add(r)
        placed[r].append((gv, text))
    verses = collections.OrderedDict()
    for r in sorted({r for _, r in heights}):
        verses.setdefault((rows[r]["book"], rows[r]["ch"], rows[r]["v"]), []).append(r)
    for key, rs in verses.items():
        has = [r for r in rs if placed.get(r)]
        for r in rs:
            if placed.get(r):
                rows[r]["greek"] = " ".join(t for _, t in placed[r])
                rows[r]["gverse"] = "%d:%d" % (gch, placed[r][0][0])
        if has:
            exact = not any(r in inferred for r in has)
            for r in rs:
                rows[r]["galign"] = "exact" if exact else "approx"
            GREEK_GEOMETRIC.append((key, exact))


PROCLITIC = set('\u05d5\u05d1\u05dc\u05db\u05de\u05d4\u05e9')   # W B L K M H C
CONS_HEB = re.compile("[א-ת]")
HEBCONS = re.compile('[\u05d0-\u05ea]')


def _bound_fragment(run):
    """Does this run of kept segments END in a piece that cannot stand alone?

    `run` is a list of raws in READING order. A fragment of one or two
    consonants, all of them proclitic, is a prefix left dangling by the
    bracket beside it - WE-LI at Jer 4,3a, MI at 1,14, LE at 1,18.

    TWO IS THE CEILING AND THE BRACKET MUST BE GLUED TO IT, and both halves of
    that were measured rather than guessed. The book has 25 such junctions;
    BHSA makes 17 of them one graphical unit and NONE of them two. Allow three
    consonants and a counter-example appears; drop the glue test and three
    appear at two - KOL-, KOH and SHEB, real words made only of proclitic
    letters, and Stipp sets a space before the bracket in each.
    """
    heb = bwfonts.to_hebrew("".join(reversed(run))).split()
    if not heb:
        return False
    c = "".join(HEBCONS.findall(heb[-1]))
    return bool(c) and len(c) <= 2 and all(x in PROCLITIC for x in c)


MAQQEF_TAIL = re.compile(r'-(\s*)$')


def column(segs, keep, strip_orphan_maqqef=False):
    """The segments one edition has, in reading order, ASCII still visual.

    A MAQQEF BELONGS TO THE WORD ON ITS LEFT AS PRINTED, so when Stipp's
    bracket closes between that word and the maqqef, the sign falls into the
    segment that FOLLOWS the bracket. Filter the bracketed word out and the
    maqqef is left at the head of a word, in front of nothing. Jer 4,27
    brackets KJ of KJ-KH, so the alexandrian column began '-KH; Jer 3,8
    brackets 'T of 'T-SPR, so it read WA-'ETTEN-SEPHER and joined two words the
    Greek has apart. The ASCII is in VISUAL order here, which is why a maqqef
    at the head of a word is looked for at the END of the string.

    IT IS STRIPPED IN THE ALEXANDRIAN COLUMN ONLY, and that is the asymmetry
    the sign itself calls for. The maqqef is Masoretic pointing, not a reading:
    Stipp sets it once and it serves both editions, so where a bracket falls
    across a maqqef pair the printed sign is ambiguous and each column has to
    be given the reading its own text supports. The masoretic column is the
    pointed text and keeps it - all three places where an alexandrian plus is
    lifted out of a maqqef pair are places BHS points with a maqqef anyway
    (7,20 WE-'AL-'ETS, 9,25 WE-'AL-MO'AB, 51,33 BAT-BABEL), because the word
    the sign binds on the masoretic side is the one that survives the deletion.
    The alexandrian column is a retroversion and has no pointing of its own, so
    a maqqef there that binds a word the edition does not have is an artefact
    of the deletion and nothing else. 84 of the 87 places are that.

    A DROPPED VARIANT READING IS NOT A GAP. The two sides of a qualitative
    variant are alternatives, so where one is filtered out the other stands in
    its place and the maqqef still has a word to bind to; only a plus -
    material the other edition does not have at all - leaves nothing behind it.
    """
    out, gap, close, run = [], False, False, []
    prev_kept = None
    spaced = False          # did what was just removed contain a word space?
    for c, t in segs:
        if c not in keep:
            if c not in ("mtvar", "ogvar", "mtsup"):
                gap = True
            if any(ch.isspace() for ch in t):
                spaced = True
            # THE BRACKET STOOD INSIDE A WORD, so the two pieces it separated
            # close up when it goes. The space Stipp prints on the far side of
            # it is the word-space of the OTHER edition's reading: at 4,3a he
            # sets WE-LI <JOSHBEJ> JERUSHALAIM, and that space belongs to the
            # alexandrian JOSHBEJ JERUSHALAIM, not to the masoretic
            # WE-LIJERUSHALAIM, which is one word. What says the bracket stood
            # inside a word is that it is written hard against the piece before
            # it AND that piece cannot stand alone.
            if (prev_kept is not None and run
                    and not (t[-1:].isspace() or prev_kept[:1].isspace())
                    and _bound_fragment(run)):
                close = True
            continue
        if gap and strip_orphan_maqqef:
            # A SPACE GOES IN ITS PLACE, because the maqqef was the only
            # thing holding the two words together: to_logical() reads
            # its `j` flag off this spacing, so taking the sign out
            # without leaving a gap glues the words instead of parting
            # them - WU-BA'AH 'ET HA-QATSIR at 51,33 came out
            # WU-BA'AHA-QATSIR.
            t = MAQQEF_TAIL.sub(lambda m: ' ' + m.group(1), t)
        if close:
            t = t.rstrip()        # visual ASCII: a trailing space here is the
            close = False         # junction with the piece before it
        elif spaced and prev_kept is not None and t and \
                not (t[-1:].isspace() or prev_kept[:1].isspace()) and \
                t[-1:] not in "-`" and prev_kept[:1] != "-":
            # (never before a sof pasuq or on either side of a maqqef: those
            # are signs that join, and the first draft put 'ISH ׃ at 34,9
            # and BAT -BABEL at 51,33)
            # (40) TAKING THE OTHER EDITION'S TEXT OUT MUST NOT JOIN TWO WORDS.
            # Where what was removed held a word space, the two kept pieces
            # were two words, and the space is the junction between them -
            # unless the bracket stood inside a word, which is the branch
            # above. Two shapes, and both glued a word pair in the masoretic
            # column: a plus that STRADDLES the boundary, NKTM<T B->'WNK at
            # 2,22 (the Greek's NKTMT B'WNK), and the space that followed an
            # alexandrian-only reading, XRPT\H <M>N'WRJ at 31,19.
            t = t + " "
        spaced = False
        if gap:
            run = []
        out.append((c, t))
        run.append(t)
        prev_kept = t
        gap = False
    return out


def parse():
    reader = PdfReader(SRC)
    rows, skipped, supplement = [], [], []
    for pno, page in enumerate(reader.pages):
        head_spans, cls_, greek_spans, marks = clauses_of(page)
        fns, placed = footnotes(pno), set()
        head = " ".join(t for x, y, k, fs, t in head_spans)
        m = HEAD.match(head.strip())
        if not m:
            if head.strip():
                skipped.append((pno, head.strip()[:40]))
            continue
        if SUPPLEMENT.search(head):
            supplement.append((pno, m.group(0)))
            continue
        book = "2Kings" if m.group(1).startswith("2") else "Jeremiah"
        ch, vlo, vhi = int(m.group(2)), int(m.group(3)), int(m.group(4))
        g = GHEAD.search(head)
        gref = f"Jer G {g.group(1)},{g.group(2)}-{g.group(3)}" if g else ""

        if g:
            gch, glo, ghi = int(g.group(1)), int(g.group(2)), int(g.group(3))
        else:
            gch, glo, ghi = ch, vlo, vhi
        gmarks, gys = [], []
        greek = greek_clauses(greek_spans, glo, ghi, marks, gmarks, gys)
        row_of = {}                 # clause index -> the row it became

        v = None
        carry = (0, False)
        for ci, cl in enumerate(cls_):
            segs, notes, label, index, carry = read_clause(cl, carry)
            if carry[0] and not bar_inside(
                    cls_[ci + 1] if ci + 1 < len(cls_) else []):
                carry = (0, False)
            segs = split_variant(segs, bool(carry[0]))
            flat = SIGLA.sub(" ", re.sub(r"[#§\
]", " ", label))
            letter = ""
            if labelish(flat) or not flat.strip():
                toks = re.findall(r"[a-z]|\d+", flat)
                nums = [int(x) for x in toks if x.isdigit()]
                lets = [x for x in toks if not x.isdigit()]
                if nums:
                    n = nums[-1]
                    if vlo <= n <= vhi and (v is None or n >= v):
                        v = n
                letter = (lets[0] if lets else "") + index.strip()
            if not any(t.strip() for _, t in segs) and not notes:
                continue
            row_of[ci] = len(rows)
            rows.append(dict(
                book=book, ch=ch, v=v if v is not None else vlo, clause=letter,
                page=pno + 1, gref=gref,
                mt=to_logical(list(reversed(column(
                    segs, ("common", "plus", "mtvar", "mtsup", "scope"))))),
                og=to_logical(list(reversed(column(
                    segs, ("common", "minus", "ogvar", "ogabbr", "scope"),
                    True)))),
                notes=[n for n in (note_text(x) for x in notes)
                       if (n["text"] or "").strip()],
                greek="", galign="", gverse=""))
            if (book, ch, rows[-1]["v"], letter) in APPARATUS_ONLY:
                _apparatus_only(rows[-1])
                WIDENED.append((ch, rows[-1]["v"], letter))
            wide = WIDE_BARS.get((book, ch, rows[-1]["v"], letter))
            if wide:
                _widen(rows[-1], *wide)
                WIDENED.append((ch, rows[-1]["v"], letter))
            # A FOOTNOTE GOES WITH THE SENTENCE THAT CARRIES ITS MARK.
            for n in sorted({marks[id(s_)] for ln in cl for s_ in ln
                             if id(s_) in marks}):
                if n in fns and n not in placed:
                    rows[-1]["notes"].append(dict(
                        kind="foot", text=f"{str(n).translate(SUP)} {fns[n]}"))
                    placed.add(n)
        place_greek_by_position(rows, row_of, cls_, greek, gys, gch)
        # A MARK IN THE GREEK PANEL goes with the row that received that Greek.
        here = [r_ for r_ in rows if r_["page"] == pno + 1]
        for n, gi in gmarks:
            if n in fns and n not in placed and 0 <= gi < len(greek):
                hit = [r_ for r_ in here if greek[gi][1] in r_["greek"]]
                if hit:
                    hit[0]["notes"].append(dict(
                        kind="foot", text=f"{str(n).translate(SUP)} {fns[n]}"))
                    placed.add(n)
        # A footnote whose mark was not found stays on the page, with the last
        # sentence, which is where it used to land in pieces.
        for n in sorted(set(fns) - placed):
            if here:
                here[-1]["notes"].append(dict(
                    kind="foot", text=f"{str(n).translate(SUP)} {fns[n]}"))
                FOOT_UNMARKED.append((pno + 1, n))
    if skipped:
        print("pages without a parsable heading:",
              "; ".join(f"p{p} {h!r}" for p, h in skipped))
    if supplement:
        print("supplement pages skipped:",
              "; ".join(f"p{p + 1} {h}" for p, h in supplement),
              "- already set in full elsewhere")
    return rows


if __name__ == "__main__":
    rows = parse()
    jer = [r for r in rows if r["book"] == "Jeremiah"]
    kgs = [r for r in rows if r["book"] == "2Kings"]
    # ONE RECORD IS NOT ONE SENTENCE. Stipp splits a sentence around an
    # embedded one and labels the parts a1 a2 a3; those are one sentence,
    # and 180 records of the book carry only a note and no text at all.
    # build_synopse_pages.sentences() does that arithmetic for the pages.
    print(f"records parsed : {len(rows):,}  ({len(jer):,} Jeremiah, {len(kgs):,} 2 Kings 25)")
    print(f"chapters       : {len(set(r['ch'] for r in jer))} of 52")
    print(f"verses reached : {len(set((r['ch'], r['v']) for r in jer)):,} of 1,364")
    print(f"records with a masoretic plus  : "
          f"{sum(any(s['cls'] == 'plus' for s in r['mt']) for r in rows):,}")
    print(f"records with an alexandrian plus: "
          f"{sum(any(s['cls'] == 'minus' for s in r['og']) for r in rows):,}")
    print(f"records with a qualitative variant: "
          f"{sum(any(s['cls'] == 'mtvar' for s in r['mt']) for r in rows):,}")
    # THE BAR SET HARD AGAINST THE TEXT ON BOTH SIDES, and how many of those
    # are a word Stipp has abbreviated. 66 bars in the book are set that way,
    # 62 of them bare; the other four are inside a scoped notation and are not
    # reached, which is why 7,9 is still short.
    print(f"bars set inside a word         : {len(TIGHT_LOG):,} bare, "
          f"{sum(1 for _, _, t in TIGHT_LOG if t):,} of them an abbreviated "
          f"masoretic word")
    print(f"bars read by name (WIDE_BARS, APPARATUS_ONLY): {len(WIDENED)} of "
          f"{len(WIDE_BARS) + len(APPARATUS_ONLY)}")
    print(f"verses with Greek placed by position (Gr ✓): "
          f"{sum(1 for _, e in GREEK_GEOMETRIC if e)} of {len(GREEK_GEOMETRIC)}")
    print(f"footnotes                      : "
          f"{sum(1 for r in rows for n in r['notes'] if n['kind'] == 'foot')}, "
          f"{len(FOOT_UNMARKED)} placed on their page without their mark "
          f"{FOOT_UNMARKED or ''}")
    print(f"spaces inside a Greek word     : {GREEK_FALSE_SPACES['removed']:,} removed")
    added = FALSE_SPACES["gap with nothing in it (added)"]
    print(f"spaces inside a Hebrew word    : {sum(FALSE_SPACES.values()) - added:,} removed "
          f"({', '.join(f'{n} {w}' for w, n in sorted(FALSE_SPACES.items()) if 'added' not in w)}); "
          f"{added} word spaces added where a gap holds nothing")
    print(f"records completed from the other column: "
          f"{sum(any(s['cls'] == 'mtsup' for s in r['mt']) for r in rows):,}")
    print(f"records carrying a note        : {sum(bool(r['notes']) for r in rows):,}")
    print(f"records with Stipp's Greek     : {sum(bool(r['greek']) for r in rows):,}")
    print(f"records with a Greek reference : {sum(bool(r.get('gverse')) for r in rows):,}")
    # THE ONE CHECK THE GREEK HAS. Stipp's Greek panel has no ground truth the
    # way the masoretic column does, but a token that is not a form attested
    # anywhere in LXX Jeremiah is either his own spelling or a word this script
    # has broken. The rate is what the README quotes; it was 96.6% until
    # 2026-09-07, when the letter-spacing of the Greek panel was undone.
    if LXX_VOCAB is not None:
        from lxx_greek import norm as _gnorm
        gk = [_gnorm(t) for r in rows for t in (r.get("greek") or "").split()]
        gk = [t for t in gk if t]
        att = sum(1 for t in gk if t in LXX_VOCAB)
        print(f"greek tokens                   : {len(gk):,}")
        print(f"  attested in LXX Jeremiah     : {att:,} ({att/max(len(gk),1):.1%})")
        # AND THE SAME COMPARISON WITH THE ACCENTS LEFT ON, which is the only
        # one that can see a wrong breathing. lxx_greek.norm() strips accent,
        # breathing and case before comparing, so a mark read wrongly - or lost
        # - passes the count above untouched. That is how four entries of the
        # Greek map went unnoticed until 2026-09-07: '-' printing as a literal
        # hyphen in 184 places, "'" dropped in 57, '<' read as an accent rather
        # than a diaeresis, and 'V' inside a word taken for a breathing and its
        # mark thrown onto the next word. This figure moved 91.4% -> 96.9% when
        # they were fixed while the one above did not move at all.
        try:
            import unicodedata as _ud
            _forms = set()
            for _ws in json.load(open(R("lxx_jer_words.json"),
                                      encoding="utf-8")).values():
                for _w in _ws:
                    _forms.add(_ud.normalize("NFC", _w["f"]))
        except Exception:
            _forms = None
        if _forms:
            gt = [_ud.normalize("NFC", t) for r in rows
                  for t in (r.get("greek") or "").split() if _gnorm(t)]
            ex = sum(1 for t in gt if t in _forms)
            print(f"  exact Rahlfs form            : {ex:,} ({ex/max(len(gt),1):.1%})"
                  f"   the rest is Stipp's own spelling")
    with open(R("synopse.json"), "w", encoding="utf-8") as f:
        json.dump(rows, f, ensure_ascii=False)
    print(f"\nwrote {R('synopse.json')}")
