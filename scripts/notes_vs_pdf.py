"""The notes against the page: a diagnostic, not part of the build.

Every Latin token PyMuPDF reads outside the Hebrew and Greek fonts, left of the
label column, is compared page by page with the tokens of the notes in
synopse.json. PyMuPDF and not pypdf, because pypdf is where the parser gets its
text and a check must not share the reader it checks.

What is left when the notes are right, so as not to chase it: footnote marks
and the small capitals of footnote names (the footnotes are read whole by
parse_synopse.footnotes()), the supplement page p. 141, the title page, the
raised G of a siglum such as Ez^G (printed run together as EzG), and the raised
P and D that ride on a label (the label column is not read here). See CLAUDE.md,
"The notes, checked", for the faults this found.

    python notes_vs_pdf.py          the totals and the commonest tokens
    python notes_vs_pdf.py -v       every page that differs, with positions
"""
import collections
import json
import re
import sys

import pymupdf

from paths import BOOKS, R

TOK = re.compile(r"[A-Za-zÄÖÜäöüßéëÉё]+|\d+")
LABEL_X = 345              # labels and verse numbers stand right of this
FOOT = (7.0, 9.0)          # footnote body and small capitals
FOOT_NUM = 5.64            # footnote numbers


def toks(t):
    return TOK.findall(t.replace("ё", "ë"))


def on_page():
    """{page as synopse.json counts it: Counter of tokens}, and where each is."""
    doc = pymupdf.open(str(BOOKS("StippJer_Textkritische_Synopse_2021.pdf")))
    pdf, where = collections.defaultdict(collections.Counter), collections.defaultdict(list)
    for pno in range(len(doc)):
        for b in doc[pno].get_text("dict")["blocks"]:
            for l in b.get("lines", []):
                for s in l["spans"]:
                    f = s["font"].lower()
                    if "bwhebb" in f or "bwgrk" in f:
                        continue
                    x0, y = s["bbox"][0], s["origin"][1]
                    if y < 40 or y > 565 or x0 >= LABEL_X:
                        continue        # running head, page number, labels
                    if FOOT[0] < s["size"] < FOOT[1] or abs(s["size"] - FOOT_NUM) < .05:
                        continue
                    for t in toks(s["text"]):
                        pdf[pno + 1][t] += 1
                        where[(pno + 1, t)].append((round(x0), round(y), s["text"]))
    return pdf, where


def in_notes():
    notes = collections.defaultdict(collections.Counter)
    for r in json.load(open(R("synopse.json"), encoding="utf-8")):
        for n in r["notes"]:
            t = n["text"].strip()
            if n["kind"] == "foot" or (t.isdigit() and len(t) <= 3):
                continue                # footnotes; the running page number
            for w in toks(t):
                notes[r["page"]][w] += 1
    return notes


def main():
    pdf, where = on_page()
    notes = in_notes()
    missing, extra, pages = collections.Counter(), collections.Counter(), []
    for p in sorted(set(pdf) | set(notes)):
        m, e = pdf[p] - notes[p], notes[p] - pdf[p]
        missing += m
        extra += e
        if m or e:
            pages.append((p, m, e))
    print(f"tokens on the page {sum(map(sum, (c.values() for c in pdf.values()))):,}, "
          f"in the notes {sum(map(sum, (c.values() for c in notes.values()))):,}")
    print(f"pages differing {len(pages)}; on the page but not in the notes "
          f"{sum(missing.values())}, in the notes but not on the page {sum(extra.values())}")
    print("missing, commonest:", missing.most_common(20))
    print("extra, commonest:  ", extra.most_common(12))
    if "-v" in sys.argv:
        for p, m, e in pages:
            print(p, "MISSING", dict(m), "EXTRA", dict(e))
            for t in m:
                for w in where[(p, t)][:3]:
                    print("     ", t, w)


if __name__ == "__main__":
    main()
