"""Score the masoretic column OF THE BUILT PAGES against BHSA, consonant by
consonant, and write every deviation out.

check_synopse.py asks the same question of results/synopse.json and answers it
with one boolean per verse, which is what the badge needs. This script asks it
of mt_greek_jeremiah/docs/*.html - the artefact a reader actually sees, glue and
all - and answers it with the DIFFERENCE: for each verse, what BHSA has that the
page does not, and what the page has that BHSA does not.

The comparison is on consonants only. Vowels, accents, maqqef and sof pasuq are
dropped, and sin and shin are folded together, because the dot is a pointing
decision and not a letter. Two verses can therefore agree here and still differ
in where the spaces fall; that axis is the word-for-word figure that
build_synopse_pages.py prints, and it is not what this script measures.

THE DIRECTION MATTERS AND THE TWO ARE REPORTED SEPARATELY.

    MISSING   BHSA has a letter the page does not. The page has lost text -
              a word swallowed by the margin, a clause never reached.
    EXTRA     the page has a letter BHSA does not have in that verse. Almost
              always Stipp's apparatus or a margin lemma read as text, since
              he sets both at the same indent as the column.

A verse can be in both lists at once, and 31 of them are: a lemma read as text
usually displaces something.

EVERY MISSING RUN IS THEN LOOKED FOR ELSEWHERE ON THE SAME VERSE'S PAGE, which
is what says whether the text was lost or merely misfiled, and the two want
different repairs:

    misordered    the run IS in the masoretic column, elsewhere in the verse.
                  Nothing is lost; the clauses of the verse were emitted out of
                  sequence, so the letters do not come in BHSA's order.
    alexandrian   the run stands in the OG column and not in the MT one. This
                  row was SIXTEEN verses and is now three, and the thirteen that
                  left it were never a fault of this extraction: where the two
                  forms differ only in their first letter Stipp prints the
                  masoretic head, the bar, and the alexandrian word in full, so
                  the letters they share are set once and set on the alexandrian
                  side. At 23,20b the line is B-'AHRIT HA-JAMIM TI, the bar,
                  then JITBONNU BAH: the masoretic column had TI and no more of
                  that word, and the reader is expected to finish TITBONNU from
                  the form opposite. RIBLATA against DIBLATA is the same thing
                  seven times over (52,9; 52,10; 52,26; 52,27; 2 Kgs 25,6;
                  25,20; 25,21). parse_synopse.py now finishes those words from
                  the page they are printed on and marks the letters it carries
                  across; see the note on the abbreviated masoretic word there.
                  7,9 needed a scoped bar read the same way. The three that
                  remain are text genuinely standing in the wrong column.
    margin        it stands in the verse's notes, and every one of them is a
                  MARGIN note rather than the parenthetical apparatus: the
                  text column overflows its left edge on a long line and the
                  overflow is read as margin. split_columns() recovers what it
                  can down to OVERFLOW_X; what is left is further left still.
    parsed        it is in results/synopse.json but not on the page, which
                  means the clause was filed under a different verse.
    lost          it is nowhere: the span was never taken into the text at all.
                  The long margin-lemma spans that split_columns() leaves out
                  (see OVERFLOW_MAXLEN) are here, and some of them are text.
    short         a run of one or two letters, almost always the last glyph of
                  a word that overflowed the left edge of the column.

Output: results/mt_vs_bhsa.csv, one row per deviating verse, and a summary on
stdout. Nothing is written back into the pages.
"""
import collections
import csv
import difflib
import glob
import html
import json
import os
import re

from paths import R, MTG
from tf.fabric import Fabric

CONS = re.compile('[\u05d0-\u05ea]')
SECTION = re.compile(r'<section class="v" id="v(\d+)">(.*?)</section>', re.S)
ROW = re.compile(r'<tr><td class="heb">(.*?)</td>', re.S)
ROW_OG = re.compile(r'<tr><td class="heb">.*?</td><td class="cl">.*?</td>'
                    r'<td class="heb">(.*?)</td>', re.S)
NOTE = re.compile(r'<tr><td colspan="4">(.*?)</td></tr>', re.S)
SPAN = re.compile(r'<span class="w[^"]*"[^>]*>(.*?)</span>')
SUP = re.compile(r'<sup.*?</sup>', re.S)
TAG = re.compile(r'<[^>]+>')


def cons(t):
    """Consonants only, sin and shin folded."""
    return ''.join(CONS.findall(t or '')).replace('\u05e9\u05c1', '\u05e9') \
                                         .replace('\u05e9\u05c2', '\u05e9')


def _cell(cell):
    cell = SUP.sub("", cell)
    cell = SPAN.sub(lambda m: html.unescape(m.group(1)), cell)
    return TAG.sub("", cell)


def page_text(rx=ROW):
    """{'4:3': 'the masoretic consonants of that verse as the page sets them'}.

    `rx` picks the column: ROW for the masoretic, ROW_OG for the alexandrian,
    NOTE for the apparatus strip under a clause.
    """
    out = {}
    files = sorted(glob.glob(MTG("jer*.html"))) + [MTG("2kings25.html")]
    for f in files:
        base = os.path.basename(f)
        pre, ch = ("", int(base[3:5])) if base.startswith("jer") else ("K", 25)
        txt = open(f, encoding="utf-8").read()
        for vnum, body in SECTION.findall(txt):
            out["%s%d:%s" % (pre, ch, vnum)] = cons(
                " ".join(_cell(c) for c in rx.findall(body)))
    return out


def bhsa_text():
    api = Fabric(locations=[os.path.expanduser("~/text-fabric-data/etcbc")
                            + "/bhsa/tf/2021"],
                 silent="deep").load("otype g_cons_utf8", silent="deep")
    F, L, T = api.F, api.L, api.T
    out = {}
    for vn in F.otype.s("verse"):
        b, c, v = T.sectionFromNode(vn)
        if b == "Jeremiah":
            key = "%d:%d" % (c, v)
        elif b == "2_Kings" and c == 25:
            key = "K25:%d" % v
        else:
            continue
        out[key] = cons(''.join(F.g_cons_utf8.v(w) or '' for w in L.d(vn, "word")))
    return out


def runs(want, got):
    """(missing, extra) - the stretches of each that the other does not have."""
    miss, plus = [], []
    for tag, i1, i2, j1, j2 in difflib.SequenceMatcher(
            None, want, got, autojunk=False).get_opcodes():
        if tag in ("delete", "replace") and want[i1:i2]:
            miss.append((i1, want[i1:i2]))
        if tag in ("insert", "replace") and got[j1:j2]:
            plus.append((j1, got[j1:j2]))
    return miss, plus


def context(s, i, n, width=12):
    a = max(0, i - width)
    return "%s[%s]%s" % (s[a:i], s[i:i + n], s[i + n:i + n + width])


def _mostly(run, other):
    """Is `other` the same stretch of text as `run`, give or take an end?

    Containment alone is not enough and was giving the wrong cause twice over.
    NE'UM-JHWH and JERUSHALAIM are among the commonest strings in the book, so
    a margin note that happens to hold one will "contain" a missing run of that
    shape whether or not it has anything to do with it. Requiring the two to be
    within a factor of two in length keeps the real cases - a note that IS the
    missing words - and drops the coincidences.
    """
    if not run or not other:
        return False
    if run not in other and other not in run:
        return False
    return 2 * min(len(run), len(other)) >= max(len(run), len(other))


def parsed_text():
    """The same verses out of results/synopse.json, both columns and the notes -
    what the parse holds, before the page is set."""
    out = collections.defaultdict(str)
    for r in json.load(open(R("synopse.json"), encoding="utf-8")):
        key = ("K25:%d" % r["v"] if r["book"] != "Jeremiah"
               else "%d:%d" % (r["ch"], r["v"]))
        out[key] += cons("".join(s["text"] for s in r["mt"] + r["og"]))
        out[key] += cons(" ".join(n["text"] for n in r["notes"]))
    return out


def locate(run, key, mt, og, notes, parsed):
    if len(run) < 3:
        return "short"
    # THE COMMON TEXT STANDS IN BOTH COLUMNS, so finding a run in the
    # alexandrian one proves nothing until the masoretic one has been ruled
    # out. Where it is in the masoretic column too, nothing is missing at all:
    # the letters are there and the ORDER is wrong, which is a different fault
    # with a different cause - clauses of one verse emitted out of sequence.
    if run in mt.get(key, ""):
        return "misordered"
    if run in og.get(key, ""):
        return "alexandrian"
    if any(_mostly(run, n) for n in notes.get(key, [])):
        return "margin"
    if run in parsed.get(key, ""):
        return "parsed"
    return "lost"


def main():
    page, bh = page_text(), bhsa_text()
    og = page_text(ROW_OG)
    notes = collections.defaultdict(list)
    for r in json.load(open(R("synopse.json"), encoding="utf-8")):
        key = ("K25:%d" % r["v"] if r["book"] != "Jeremiah"
               else "%d:%d" % (r["ch"], r["v"]))
        for n in r["notes"]:
            c = cons(n["text"])
            if c:
                notes[key].append(c)
    parsed = parsed_text()
    rows, tally = [], collections.Counter()
    for key in sorted(bh, key=lambda k: (k.startswith("K"),
                                         int(k.split(":")[0].lstrip("K")),
                                         int(k.split(":")[1]))):
        want = bh[key]
        got = page.get(key)
        if got is None:
            tally["absent"] += 1
            rows.append((key, "ABSENT", len(want), 0, "absent", "", ""))
            continue
        if got == want:
            tally["exact"] += 1
            continue
        miss, plus = runs(want, got)
        kind = ("MISSING+EXTRA" if miss and plus else
                "MISSING" if miss else "EXTRA")
        tally[kind] += 1
        where = sorted({locate(t, key, page, og, notes, parsed)
                        for _, t in miss})
        for w in where:
            tally["where:" + w] += 1
        rows.append((key, kind, sum(len(t) for _, t in miss),
                     sum(len(t) for _, t in plus), "+".join(where),
                     " | ".join(context(want, i, len(t)) for i, t in miss[:4]),
                     " | ".join(context(got, i, len(t)) for i, t in plus[:4])))
    with open(R("mt_vs_bhsa.csv"), "w", encoding="utf-8-sig", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["verse", "kind", "letters_missing", "letters_extra",
                    "where_the_missing_text_is",
                    "missing_in_context_bhsa", "extra_in_context_page"])
        w.writerows(rows)

    tot = len(bh)
    print("verses in BHSA (Jeremiah + 2 Kings 25) : %d" % tot)
    print("  consonants identical and in order    : %d (%.1f%%)"
          % (tally["exact"], 100 * tally["exact"] / tot))
    print("  the page is MISSING letters          : %d"
          % (tally["MISSING"] + tally["MISSING+EXTRA"]))
    print("  the page has EXTRA letters           : %d"
          % (tally["EXTRA"] + tally["MISSING+EXTRA"]))
    print("     of which both at once             : %d" % tally["MISSING+EXTRA"])
    print("  verse absent from the pages entirely : %d" % tally["absent"])
    print("")
    print("where the missing text actually is (verses may count twice):")
    for w in ("misordered", "alexandrian", "margin", "parsed", "lost", "short"):
        print("  %-12s %4d verses" % (w, tally["where:" + w]))
    print("\nwrote %s  (%d rows)" % (R("mt_vs_bhsa.csv"), len(rows)))


if __name__ == "__main__":
    main()
