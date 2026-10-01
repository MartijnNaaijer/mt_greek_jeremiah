"""Derive the BWHEBB -> Unicode map from the data, rather than from memory.

Stipp's Textkritische Synopse sets its Hebrew in the legacy BibleWorks font
BWHEBB, which encodes pointed Hebrew as ASCII in VISUAL order: `rmoale` is
LEAMOR read right to left, each consonant followed by its own points. To show
the Synopse as Hebrew, that has to be inverted, and a map guessed from memory is
exactly the kind of thing this project does not trust.

It does not have to be guessed. Stipp's masoretic column IS the BHS text, and
BHSA holds the same text fully pointed, so the map can be LEARNED and then
checked against a corpus of 29,736 words that was never used to build it.

    1. The consonants are certain and are declared below - 22 letters, five
       final forms, and the capital = with-dagesh convention. Nothing else is
       assumed.
    2. Every BWHEBB word in the file is reduced to its consonantal skeleton
       with that map alone and looked up in a skeleton -> pointed index built
       from BHSA. Where a skeleton has exactly ONE pointed form in the Hebrew
       Bible, the pair is unambiguous and becomes a training example.
    3. Each pair is split into units - one consonant plus the marks that follow
       it in the ASCII, one base letter plus its combining marks in the Unicode -
       and the two unit sequences are aligned. Where they are the same length,
       every ASCII mark character is credited with the Unicode mark it stands
       against.
    4. A mark is accepted when one reading accounts for at least 95% of its
       occurrences and it occurs at least 20 times.

Run this to REDERIVE the map. bwhebb.py holds the frozen result and is what the
rest of the pipeline imports; this script exists so that the frozen map can be
reproduced and audited rather than believed.

Note on what is NOT in Stipp's Hebrew: cantillation. The Synopse prints
consonants, vowels and dagesh only, so BHSA's accents (U+0591-U+05AF) are
stripped on both sides before anything is compared.
"""
import os, re, sys, collections, unicodedata
from paths import BOOKS
from pypdf import PdfReader
from tf.fabric import Fabric

SRC = BOOKS("StippJer_Textkritische_Synopse_2021.pdf")

# ---------------------------------------------------------------- consonants
# The only thing taken on trust. Capitals are the with-dagesh forms, which the
# font distinguishes because a dagesh changes the glyph; the dagesh itself is
# recovered as a combining mark in step 3, so these map to the bare letter.
CONS = {
    'a': 'א', 'b': 'ב', 'g': 'ג', 'd': 'ד', 'h': 'ה',
    'w': 'ו', 'z': 'ז', 'x': 'ח', 'j': 'ט', 'y': 'י',
    'k': 'כ', 'l': 'ל', 'm': 'מ', 'n': 'נ', 's': 'ס',
    '[': 'ע', 'p': 'פ', 'c': 'צ', 'q': 'ק', 'r': 'ר',
    'f': 'ש', 'v': 'ש', 't': 'ת',
    '%': 'ך', '~': 'ם', '!': 'ן', '@': 'ף', '#': 'ץ',
}
DAG = 'ּ'                     # HEBREW POINT DAGESH OR MAPIQ
DAGESH = {
    'B': 'ב'+DAG, 'G': 'ג'+DAG, 'D': 'ד'+DAG, 'H': 'ה'+DAG, 'W': 'ו'+DAG,
    'Z': 'ז'+DAG, 'J': 'ט'+DAG, 'Y': 'י'+DAG, 'K': 'כ'+DAG, 'L': 'ל'+DAG,
    'M': 'מ'+DAG, 'N': 'נ'+DAG, 'S': 'ס'+DAG, 'P': 'פ'+DAG, 'C': 'צ'+DAG,
    'Q': 'ק'+DAG, 'R': 'ר'+DAG, 'T': 'ת'+DAG, 'V': 'ש'+DAG, 'F': 'ש'+DAG,
    'A': 'ו',                      # holam male, vav carrying the point
}
BASE = dict(CONS); BASE.update(DAGESH)

ACCENTS = re.compile('[֑-ֽֿ֯]')     # cantillation, not printed by Stipp
POINTS  = 'ְ-ׇּׁׂ'


def strip_accents(s):
    return ACCENTS.sub('', s)


def clusters(word):
    """Unicode word -> [base letter + its combining marks], in logical order."""
    out = []
    for ch in word:
        if 'א' <= ch <= 'ת':
            out.append([ch])
        elif out:
            out[-1].append(ch)
    return [''.join(c) for c in out]


def units(vis):
    """BWHEBB word in VISUAL order -> [consonant + its marks], LOGICAL order."""
    out = []
    for ch in vis:
        if ch in BASE:
            out.append([ch])
        elif out:
            out[-1].append(ch)
        # a mark before any consonant is dropped: it belongs to the previous word
    return [''.join(u) for u in reversed(out)]


def skeleton(vis):
    return ''.join(BASE[c][0] for c in reversed(vis) if c in BASE)


# ------------------------------------------------------------------ the data
def stipp_words():
    """Every BWHEBB word in the Synopse, as visual-order ASCII."""
    r = PdfReader(SRC)
    words = []
    for page in r.pages:
        spans = []
        page.extract_text(visitor_text=lambda t, cm, tm, fd, fs:
                          spans.append((str((fd or {}).get("/BaseFont", "")).lower(), t)))
        buf = []
        for f, t in spans:
            if "bwhebb" in f:
                buf.append(t)
            else:
                buf.append(' ')
        for w in re.split(r'[\s\-]+', ''.join(buf)):
            w = w.strip('`.,;:!?()*')
            if w and any(c in BASE for c in w):
                words.append(w)
    return words


def bhsa_index():
    """skeleton -> set of pointed graphical units, over the whole Hebrew Bible."""
    api = Fabric(locations=[os.path.expanduser("~/text-fabric-data/etcbc") + "/bhsa/tf/2021"],
                 silent="deep").load("otype g_word_utf8 g_cons_utf8 trailer_utf8", silent="deep")
    F = api.F
    idx = collections.defaultdict(collections.Counter)
    cur, curc = [], []
    for w in F.otype.s("word"):
        g = strip_accents(F.g_word_utf8.v(w) or '')
        cur.append(g); curc.append(F.g_cons_utf8.v(w) or '')
        if (F.trailer_utf8.v(w) or '').strip() or (F.trailer_utf8.v(w) or '') != '':
            # a graphical unit ends where the trailer is non-empty
            unit = ''.join(cur); cons = ''.join(curc)
            if cons:
                idx[cons][unit] += 1
            cur, curc = [], []
    if cur:
        idx[''.join(curc)][''.join(cur)] += 1
    return idx


def main():
    idx = bhsa_index()
    print(f"BHSA index: {len(idx):,} distinct consonantal skeletons")
    sw = stipp_words()
    print(f"Synopse   : {len(sw):,} BWHEBB word tokens, {len(set(sw)):,} distinct")

    pairs, amb, miss = [], 0, 0
    for w in sw:
        sk = skeleton(w)
        forms = idx.get(sk)
        if not forms:
            miss += 1; continue
        if len(forms) > 1:
            amb += 1; continue
        pairs.append((w, next(iter(forms))))
    print(f"unambiguous pairs: {len(pairs):,}   ambiguous skeleton: {amb:,}   "
          f"no skeleton in BHSA: {miss:,}")

    # ----------------------------------------------------------- learn marks
    votes = collections.defaultdict(collections.Counter)
    used = 0
    for vis, uni in pairs:
        U, C = units(vis), clusters(uni)
        if len(U) != len(C):
            continue
        used += 1
        for u, c in zip(U, C):
            am = u[1:]                     # ascii marks after the consonant
            um = c[1:]                     # unicode combining marks
            if BASE[u[0]][1:] and um.startswith(DAG):
                um = um[1:]                # the dagesh is in the base letter
            if len(am) == 1 and len(um) == 1:
                votes[am][um] += 1
            elif len(am) == 1 and len(um) == 0:
                votes[am][''] += 1
            elif len(am) == 0 and len(um) == 1:
                votes['<none>'][um] += 1
            elif am or um:
                votes['?' + str(len(am)) + str(len(um))][am + '|' + um] += 1
    print(f"aligned words: {used:,} of {len(pairs):,}\n")

    print(f"{'ascii':<8}{'n':>7}  reading                       purity")
    rows = sorted(votes.items(), key=lambda kv: -sum(kv[1].values()))
    for a, cnt in rows:
        n = sum(cnt.values())
        top, k = cnt.most_common(1)[0]
        if n < 5:
            continue
        name = ' + '.join(unicodedata.name(ch, '?') for ch in top) if top else '(nothing)'
        print(f"{a!r:<8}{n:>7}  {name:<30}{k/n:6.1%}"
              f"{'' if k/n >= .95 else '   <-- impure: ' + str(cnt.most_common(3))}")


if __name__ == "__main__":
    main()
