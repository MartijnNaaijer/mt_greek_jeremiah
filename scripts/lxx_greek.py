"""The Rahlfs LXX as a check on, and an analysis for, Stipp's Greek panel.

Stipp prints the Old Greek down the right-hand side of every page of the
Synopse, in the BibleWorks font BWGRKL. Until 2026-09-05 this project had no
Unicode Greek to set beside it, so bwfonts.to_greek() was written from the
readings themselves and marked as edited rather than measured. That was wrong:
a morphologically annotated Rahlfs LXX has been on this machine all along, at

    ~/text-fabric-data/CenterBLC/lxx/tf/1935

with 30,371 verses over 57 books, of which Jeremiah is 52 chapters, 1,298 verses
and 28,948 words, carrying the lemma (twice: transliterated in `lex`, in
Greek script in `lex_utf8`), sp, gn, nu, ps, case, tense, mood, voice and a
gloss. An SBLGNT sits beside it. Neither is in CLAUDE.md's data table, which is
why neither was used.

Two things are written here.

    results/lxx_vocab.json      every word form attested in LXX Jeremiah,
                                normalised (lowercased, accents stripped, final
                                sigma folded). parse_synopse.py uses it to repair
                                words the PDF breaks across a justification gap -
                                IEREMI AN, HEMER AIS, B ABULONOS - by rejoining a
                                fragment with its neighbour where the join is an
                                attested form and at least one part is not.
    results/lxx_jer_words.json  per Greek verse, the words with their analyses,
                                for the hover on the Greek column.

A NOTE ON THE VERSIFICATION, because it is the thing that goes wrong. This
corpus is in GREEK versification: its Jer 32 is the Hebrew Jer 25. Stipp's page
headings carry the correspondence where the two diverge ('Jer 25,11-22 / Jer G
32,1-8'), and his Greek panel numbers its verses in Greek numbers on exactly
those pages - so a number in that panel is not an MT verse number and must not
be read as one.

AND A TRAP THIS CORPUS SHARES WITH BHSA: chapter and verse are features of
CHAPTER and VERSE nodes, not of words or of each other. F.chapter.v() on a verse
node returns None, silently, and a dictionary keyed on it collapses - which is
how LXX Jeremiah first came out of this script with 62 verses instead of 1,298.
Go up with L.u(), or iterate down from the book with L.d().
"""
import collections
import json
import os
import unicodedata

from paths import R
from tf.fabric import Fabric

LOC = os.path.expanduser("~/text-fabric-data/CenterBLC/lxx/tf/1935")
# THE LEMMA IS CARRIED TWICE BY THIS CORPUS AND ONLY ONE OF THE TWO IS GREEK.
# `lex` is a Latin transliteration - theos, ginomai, Rema, o - and `lex_utf8`,
# whose own description reads "normalized word", is the lemma in Greek script:
# theos, ginomai, rhema, ho. The hover on the Greek column sets the lemma in
# the same script as the text it analyses, so lex_utf8 is what is read here and
# it is stored under the key `lex` that the page already looks for.
FEATS = ["lex_utf8", "sp", "case", "tense", "voice", "mood", "ps", "nu", "gn",
         "degree"]
EXTRA = ["gloss"]
OUTKEY = {"lex_utf8": "lex"}
EMPTY = {"", None, "NA", "unknown", "none"}


def norm(s):
    """Fold a Greek word for comparison: no accents, no case, one sigma."""
    s = unicodedata.normalize("NFD", (s or "").lower())
    s = ''.join(c for c in s if 'α' <= c <= 'ω' or c in 'ςϲ')
    return s.replace('ς', 'σ').replace('ϲ', 'σ')


def repair(tokens, vocab):
    """Rejoin words the PDF broke across a justification gap.

    At each position the LONGEST run of up to five tokens whose concatenation is
    an attested form is taken, provided at least one token in the run is not
    itself an attested form. That proviso is what stops two genuine words from
    being merged; the run length is what recovers a word the PDF split into three
    or four pieces, which a pairwise join cannot reach because the intermediate
    join is not a word either.
    """
    out, i, n = [], 0, len(tokens)
    while i < n:
        best = None
        for j in range(min(i + 5, n), i + 1, -1):
            run = tokens[i:j]
            if any(norm(x) not in vocab for x in run) and norm(''.join(run)) in vocab:
                best = j
                break
        if best:
            out.append(''.join(tokens[i:best])); i = best
        else:
            out.append(tokens[i]); i += 1
    return out


def main():
    api = Fabric(locations=[LOC], silent="deep").load(
        "otype book chapter verse word " + " ".join(FEATS + EXTRA), silent="deep")
    F, L = api.F, api.L

    jb = next(b for b in F.otype.s("book") if F.book.v(b) == "Jer")
    verses = {}
    vocab = set()
    for vn in L.d(jb, "verse"):
        ch = F.chapter.v(L.u(vn, "chapter")[0])     # NOT F.chapter.v(vn)
        v = F.verse.v(vn)
        ws = []
        for w in L.d(vn, "word"):
            form = F.word.v(w) or ''
            d = {"f": form}
            for f in FEATS + EXTRA:
                val = getattr(F, f).v(w)
                if val not in EMPTY:
                    d[OUTKEY.get(f, f)] = val
            ws.append(d)
            if norm(form):
                vocab.add(norm(form))
        verses[f"{ch}:{v}"] = ws

    # A form index for words the verse alignment misses, on the same rule as the
    # Hebrew one: a form gets an entry only where it has exactly ONE analysis
    # anywhere in LXX Jeremiah, so an ambiguous form yields nothing rather than
    # a guess.
    seen, store = collections.defaultdict(set), {}
    for ws in verses.values():
        for d in ws:
            k = norm(d["f"])
            if not k:
                continue
            sig = tuple(sorted((x, y) for x, y in d.items() if x != "f"))
            seen[k].add(sig)
            store.setdefault(k, d)
    findex = {k: store[k] for k, v in seen.items() if len(v) == 1}
    json.dump(findex, open(R("lxx_form_index.json"), "w", encoding="utf-8"),
              ensure_ascii=False)

    json.dump(sorted(vocab), open(R("lxx_vocab.json"), "w", encoding="utf-8"),
              ensure_ascii=False)
    json.dump(verses, open(R("lxx_jer_words.json"), "w", encoding="utf-8"),
              ensure_ascii=False)
    print(f"LXX Jeremiah (Rahlfs 1935, Greek versification)")
    print(f"  chapters {len(L.d(jb,'chapter'))}  verses {len(verses):,}  "
          f"words {sum(len(v) for v in verses.values()):,}")
    print(f"  distinct normalised forms: {len(vocab):,}")
    print(f"  form index: {len(findex):,} unambiguous of {len(seen):,} "
          f"({len(findex)/len(seen):.0%})")
    print(f"wrote {R('lxx_vocab.json')}\n      {R('lxx_jer_words.json')}")


if __name__ == "__main__":
    main()
