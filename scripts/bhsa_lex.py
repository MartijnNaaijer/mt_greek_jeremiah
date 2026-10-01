"""Word-level BHSA analysis for the Synopse pages, plus a form index for the
retroversion.

build_synopse_pages.py puts a hover on every Hebrew word. The masoretic column
is the BHS text, so its words can be linked to BHSA nodes directly and the
analysis is the database's own. The alexandrian column cannot: it is Stipp's
retroversion of the Greek, it has no nodes, and some of its forms are not in the
Hebrew Bible at all. So two things are written here and they are not the same
kind of object, which is why the page labels them differently.

    results/bhsa_jer_words.json
        per verse, the graphical units of the verse with the BHSA words inside
        each. Jeremiah and 2 Kings 25, the two books the Synopse sets.
    results/bhsa_form_index.json
        consonantal skeleton -> analysis, over the WHOLE Hebrew Bible, and only
        where the skeleton has exactly one analysis anywhere. An ambiguous form
        gets no entry rather than a guess: the point of the hover is to say what
        BHSA holds, and BHSA holds nothing about a retroverted form.

THE UNIT IS THE GRAPHICAL UNIT, not the BHSA word, because that is what Stipp
prints. BHSA splits a prefixed article, preposition, conjunction or relative into
a word of its own, so one printed word is one to four BHSA words and the hover
shows each of them: HA-DABAR is H (article) plus DBR/ (noun). The two counts
differ by a factor of 1.36 across Jeremiah - 29,736 words against 21,802
graphical units - so joining them is not cosmetic, it is what makes Stipp's text
and BHSA comparable at all.

Features, as asked for: lex, sp, vt, vs, ps, nu, gn. The vocalised lexeme is
carried too, since a hover showing only the ETCBC code is hard to read. Values
BHSA writes as NA or unknown are dropped rather than printed.

A UNIT CARRIES BOTH SKELETONS WHERE THEY DIFFER, `c` for the writing and `c2`
for the reading, because Stipp does not print consistently one or the other: at
Jer 2,15 he sets the ketiv consonants and at Jer 2,25 the qere ones. Matching on
`c` alone left 61 of the 193 ketiv/qere words of Jeremiah unaligned. It gains
only two of them back: the marker rides on the alignment, and these words are
precisely where Stipp's print and BHSA's consonants diverge most, so most of the
shortfall is the alignment itself and not the choice of skeleton.

EACH UNIT ALSO CARRIES ITS POINTED TEXT on `t`, with the te`amim and the meteg
stripped, because Stipp sets his Hebrew with vowels but without accents - 3,424
maqqefs and 1,128 sof pasuqs in his masoretic column and not one cantillation
sign. build_synopse_pages.py needs it to repair a verse whose column has lost a
word: the supplied word has to be set in the same style as the words around it or
the repair is visible as a change of typography rather than as what it is.

KETIV/QERE is carried as well, on `k` and `q`. BHSA puts the written form in
g_word_utf8, unpointed because the pointing belongs to the reading, and the
pointed reading in qere_utf8; a word has a qere only where the two differ. 193
words of Jeremiah do. The pages mark them with a superscript K.
"""
import collections
import json
import os
import re

from paths import R
from tf.fabric import Fabric

FEATS = ["lex", "sp", "vt", "vs", "ps", "nu", "gn"]
# T.sectionFromNode gives ENGLISH names - "2_Kings", not the Latin "Reges_II"
# of the book feature and not the "Kings_II" this file carried until 2026-09-05.
# The wrong name matched nothing and cost nothing visible: 2 Kings 25 simply
# came out of here with no units at all, so its page had no hovers, no badge and
# no repair, and every count printed below was Jeremiah's alone.
BOOKS = {"Jeremiah": "", "2_Kings": "K"}
CONS = re.compile('[א-ת]')
ACC = re.compile('[֑-ֽ֯]')     # te`amim and meteg: Stipp has none
EMPTY = {"NA", "unknown", "none", "", None}


def cons(t):
    return ''.join(CONS.findall(t or '')).replace('שׁ', 'ש').replace('שׂ', 'ש')


def plain(t):
    """Pointed text in Stipp's style: vowels kept, accents and meteg dropped.

    The holam of a holam male is also moved onto its vav. BHSA follows the ETCBC
    transcription, which writes the vowel before the letter (HOLAM then VAV,
    12,013 words) and reserves the other order for a consonantal vav carrying a
    holam (VAV then HOLAM, 409 words: <WN/, MYWH/, XWH[). The two are therefore
    unambiguous and only the first should be turned round, which is what print -
    and Stipp - does: the dot sits on the vav, not on the letter before it.
    """
    return ACC.sub('', t or '').replace('ֹו', 'וֹ')


def main():
    api = Fabric(locations=[os.path.expanduser("~/text-fabric-data/etcbc") + "/bhsa/tf/2021"],
                 silent="deep").load(
        "otype g_word_utf8 g_cons_utf8 trailer_utf8 voc_lex_utf8 qere_utf8 "
        + " ".join(FEATS), silent="deep")
    F, L, T = api.F, api.L, api.T

    def analysis(w):
        d = {}
        for f in FEATS:
            v = getattr(F, f).v(w)
            if v not in EMPTY:
                d[f] = v
        vl = F.voc_lex_utf8.v(w)
        if vl:
            d["vlex"] = vl
        q = F.qere_utf8.v(w)
        if q:
            d["q"] = q                       # the reading, pointed
            d["k"] = F.g_word_utf8.v(w)      # the writing, unpointed
        return d

    # ---------------------------------------------------------------- verses
    verses = {}
    for vn in F.otype.s("verse"):
        b, c, v = T.sectionFromNode(vn)
        if b not in BOOKS:
            continue
        if b == "2_Kings" and c != 25:
            continue
        units, cur, curc, curq, curt = [], [], [], [], []

        def close():
            """Finish the graphical unit built up in cur/curc/curq/curt."""
            if not ''.join(curc):
                return
            u = {"c": cons(''.join(curc)), "t": plain(''.join(curt)), "w": list(cur)}
            q = cons(''.join(curq))
            if q and q != u["c"]:
                u["c2"] = q
            units.append(u)

        for w in L.d(vn, "word"):
            cur.append(analysis(w))
            curc.append(F.g_cons_utf8.v(w) or '')
            curq.append(F.qere_utf8.v(w) or F.g_cons_utf8.v(w) or '')
            # The reading is what a printed text sets, so a qere word contributes
            # qere_utf8 and not the unpointed writing in g_word_utf8.
            curt.append(F.qere_utf8.v(w) or F.g_word_utf8.v(w) or '')
            tr = F.trailer_utf8.v(w) or ''
            if tr:
                # Keep the maqqef and the sof pasuq, drop the space: a column
                # token is written BEN- with its maqqef attached, and the last
                # unit of a verse ends in the sof pasuq on the page.
                curt.append(''.join(ch for ch in tr if ch in '־׃'))
                close()
                cur, curc, curq, curt = [], [], [], []
        close()
        verses[f"{BOOKS[b]}{c}:{v}"] = units

    # ------------------------------------------------------------ form index
    forms = collections.defaultdict(set)
    store = {}
    cur, curc = [], []
    for w in F.otype.s("word"):
        cur.append(w)
        curc.append(F.g_cons_utf8.v(w) or '')
        if F.trailer_utf8.v(w):
            k = cons(''.join(curc))
            if k:
                sig = tuple(tuple(sorted(analysis(x).items())) for x in cur)
                forms[k].add(sig)
                store.setdefault(k, [analysis(x) for x in cur])
            cur, curc = [], []
    index = {k: store[k] for k, s in forms.items() if len(s) == 1}

    json.dump(verses, open(R("bhsa_jer_words.json"), "w", encoding="utf-8"),
              ensure_ascii=False)
    json.dump(index, open(R("bhsa_form_index.json"), "w", encoding="utf-8"),
              ensure_ascii=False)
    nq = sum(1 for us in verses.values() for u in us for w in u["w"] if w.get("q"))
    nw = sum(len(u["w"]) for us in verses.values() for u in us)
    nu = sum(len(us) for us in verses.values())
    print(f"verses            : {len(verses):,}")
    print(f"graphical units   : {nu:,}   BHSA words: {nw:,}   ratio {nw/nu:.2f}")
    print(f"ketiv/qere        : {nq:,} words")
    print(f"form index        : {len(index):,} unambiguous of {len(forms):,} "
          f"skeletons ({len(index)/len(forms):.0%})")
    print(f"wrote {R('bhsa_jer_words.json')}\n      {R('bhsa_form_index.json')}")


if __name__ == "__main__":
    main()
