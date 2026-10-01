"""BibleWorks legacy fonts -> Unicode. BWHEBB for Hebrew, BWGRKL for Greek.

Stipp's Textkritische Synopse is set in the two BibleWorks display fonts, which
encode their scripts as ASCII. Nothing in the file is Hebrew or Greek as far as
any text tool is concerned, which is why parse_stipp.py could only ever count
brackets: `[` in that file is an ayin 3,345 times and a markup bracket 1,658
times, and only the font tells them apart. To SHOW the Synopse rather than
measure it, both encodings have to be inverted.

    BWHEBB is pointed Hebrew in VISUAL order. Each consonant is followed by
    its own points, and the string runs left to right across the page, so it is
    the reverse of the logical order: `rmoale` is LE-A-MO-R backwards, i.e.
    lamed+tsere, aleph, mem+holam, resh. Capitals are the with-dagesh glyphs
    (`L` is lamed with dagesh) because a dagesh changes the shape of the letter;
    the font also carries two or three glyph variants of most vowels, cut for
    different letter widths, which is why `'` and `"` are both qamats and `>`
    and `.` are both sheva.

    BWGRKL is Greek with the diacritics as ASCII following their vowel:
    `eva,n` is epsilon + smooth breathing + alpha + acute + nu. Breathing and
    accent combine into single characters where Greek combines them: `;` is
    smooth-and-acute, `[` is rough-and-acute.

THE HEBREW MAP WAS NOT GUESSED. bwhebb_learn.py derives it from the file itself:
every BWHEBB word is reduced to a consonantal skeleton, looked up in a
skeleton -> pointed index built from BHSA, and where the skeleton has exactly one
pointed form in the Hebrew Bible the pair is unambiguous and votes on what each
ASCII mark stands for. Every mark below was accepted at 95% purity or better over
5,513 such pairs. Only the 27 consonants were taken on trust, and they are
checkable by eye. verify() below re-runs the check end to end and reports the
agreement with BHSA verse by verse.

THE GREEK MAP WAS PARTLY GUESSED and is not verifiable here, because the project
holds no Unicode text of the Old Greek to check it against. It is built from the
same evidence anyone would use - reading Stipp's own Greek against the passages
it translates - and the readings are individually obvious (`r`h/ma` is RHEMA,
`ui`ou/` is HUIOU, `e;touj` is ETOUS). Treat the Hebrew as measured and the Greek
as edited: a wrong accent in the Greek column is possible, a wrong consonant in
the Hebrew column is not.

Composition. Marks are emitted as combining characters in BHSA's own order -
base, shin/sin dot, dagesh, vowel - and the Greek is NFC-normalised at the end so
that it comes out as precomposed polytonic characters rather than as a base
letter trailing three combining marks.
"""
import re
import unicodedata

# ---------------------------------------------------------------------------
# BWHEBB
# ---------------------------------------------------------------------------
DAGESH = 'ּ'
SHIN, SIN = 'ׁ', 'ׂ'

HEB_BASE = {
    # the 22 letters
    'a': 'א', 'b': 'ב', 'g': 'ג', 'd': 'ד', 'h': 'ה', 'w': 'ו', 'z': 'ז',
    'x': 'ח', 'j': 'ט', 'y': 'י', 'k': 'כ', 'l': 'ל', 'm': 'מ', 'n': 'נ',
    's': 'ס', '[': 'ע', 'p': 'פ', 'c': 'צ', 'q': 'ק', 'r': 'ר', 't': 'ת',
    'v': 'ש' + SHIN, 'f': 'ש' + SIN,
    # final forms. `%` is the final kaf the font draws WITH its sheva - the
    # 2fs suffix and the -EKH ending - and `$` the bare letter; splitting them
    # this way lifted the agreement with BHSA from 95.1% to 97.3%.
    '%': 'ךְ', '$': 'ך', '~': 'ם', '!': 'ן', '@': 'ף', '#': 'ץ',
    # the with-dagesh glyphs
    'B': 'ב' + DAGESH, 'G': 'ג' + DAGESH, 'D': 'ד' + DAGESH, 'H': 'ה' + DAGESH,
    'W': 'ו' + DAGESH, 'Z': 'ז' + DAGESH, 'J': 'ט' + DAGESH, 'Y': 'י' + DAGESH,
    'K': 'כ' + DAGESH, 'L': 'ל' + DAGESH, 'M': 'מ' + DAGESH, 'N': 'נ' + DAGESH,
    'S': 'ס' + DAGESH, 'P': 'פ' + DAGESH, 'C': 'צ' + DAGESH, 'Q': 'ק' + DAGESH,
    'R': 'ר' + DAGESH, 'T': 'ת' + DAGESH,
    'V': 'ש' + SHIN + DAGESH, 'F': 'ש' + SIN + DAGESH,
    '&': 'ך' + DAGESH,
    # vav carrying a point, written as one glyph
    'A': 'וֹ',                       # holam male
    # the 2ms suffix, written as one glyph
    '^': 'ךָ',
}

HEB_MARK = {
    "'": 'ָ', '"': 'ָ',         # qamats      (two glyph widths)
    ';': 'ַ', ':': 'ַ',         # patah
    ',': 'ֶ', '<': 'ֶ',         # segol
    'e': 'ֵ', 'E': 'ֵ',         # tsere
    'i': 'ִ', 'I': 'ִ',         # hiriq
    'o': 'ֹ', 'O': 'ֹ', '{': 'ֹ',   # holam
    'u': 'ֻ', 'U': 'ֻ',         # qubuts
    '>': 'ְ', '.': 'ְ',         # sheva
    ']': 'ֲ',                        # hataf patah
    '/': 'ֱ',                        # hataf segol
    '\\': 'ֳ',                       # hataf qamats
}

HEB_PUNCT = {'-': '־', '`': '׃'}   # maqqef, sof pasuq


def to_hebrew(vis):
    """A run of BWHEBB text in visual order -> Unicode Hebrew in logical order.

    The whole run is reversed, spaces included, so the word order comes out
    right without a separate pass: a unit is a base letter with the marks that
    follow it, and everything else - space, maqqef, sof pasuq - is a unit of its
    own. Characters the font does not use for text (the apparatus asterisk, a
    stray bracket) are dropped rather than passed through, so that a caller
    cannot mistake markup for text.
    """
    units, cur = [], None
    for ch in vis:
        if ch in HEB_BASE:
            cur = [HEB_BASE[ch]]
            units.append(cur)
        elif ch in HEB_MARK and cur is not None:
            cur.append(HEB_MARK[ch])
        elif ch in HEB_PUNCT:
            units.append([HEB_PUNCT[ch]]); cur = None
        elif ch.isspace():
            units.append([' ']); cur = None
        # anything else is markup or an apparatus symbol, and is dropped
    out = ''.join(''.join(u) for u in reversed(units))
    return re.sub(r' +', ' ', out).strip()


# ---------------------------------------------------------------------------
# BWGRKL
# ---------------------------------------------------------------------------
SMOOTH, ROUGH = '̓', '̔'
ACUTE, GRAVE, CIRC = '́', '̀', '͂'
IOTA, DIAER = 'ͅ', '̈'

GRK_BASE = {
    'a': 'α', 'b': 'β', 'g': 'γ', 'd': 'δ', 'e': 'ε', 'z': 'ζ', 'h': 'η',
    'q': 'θ', 'i': 'ι', 'k': 'κ', 'l': 'λ', 'm': 'μ', 'n': 'ν', 'x': 'ξ',
    'o': 'ο', 'p': 'π', 'r': 'ρ', 's': 'σ', 'j': 'ς', 't': 'τ', 'u': 'υ',
    'f': 'φ', 'c': 'χ', 'y': 'ψ', 'w': 'ω',
    'A': 'Α', 'B': 'Β', 'G': 'Γ', 'D': 'Δ', 'E': 'Ε', 'Z': 'Ζ', 'H': 'Η',
    'Q': 'Θ', 'I': 'Ι', 'K': 'Κ', 'L': 'Λ', 'M': 'Μ', 'N': 'Ν', 'X': 'Ξ',
    'O': 'Ο', 'P': 'Π', 'R': 'Ρ', 'S': 'Σ', 'T': 'Τ', 'U': 'Υ', 'F': 'Φ',
    'C': 'Χ', 'Y': 'Ψ', 'W': 'Ω',
}

# Breathing and accent are one character where Greek writes them as one.
GRK_MARK = {
    'v': SMOOTH, '`': ROUGH,
    ';': SMOOTH + ACUTE, '[': ROUGH + ACUTE,
    ']': ROUGH + GRAVE,
    '=': SMOOTH + CIRC,  '~': ROUGH + CIRC,
    ',': ACUTE, '.': GRAVE, '/': CIRC,
    # THREE OF THESE MARKS HAVE A SECOND SPELLING IN THIS FILE, and each was
    # found by asking what word the map produced and whether Rahlfs has it.
    #   '-'  ROUGH + CIRC, 184 occurrences and the largest of them - w-n, ou-,
    #        h-j, ou-toj, oi-j, ai-j. It was falling through to the punctuation
    #        below and printing as a literal hyphen: 'ω-ν' for ὧν, which LXX
    #        Jeremiah has 36 times against 0 for the hyphenated form. None of
    #        the 184 begins a token and none carries a digit, so no real dash
    #        is caught by this.
    #   "'"  SMOOTH + GRAVE, 57 occurrences, and unmapped until 2026-09-07 so
    #        the mark was simply lost: h' for ἢ (36), a'n for ἂν (14), w' for
    #        ὢ. Rahlfs has ἂν in Jeremiah exactly 14 times.
    #   '<'  DIAERESIS, not the SMOOTH + GRAVE it was read as. Twice in the
    #        book, karui<nhn and boi<dia, which Rahlfs writes καρυΐνην and
    #        βοΐδια; the accented readings are attested nowhere.
    '-': ROUGH + CIRC, "'": SMOOTH + GRAVE,
    '|': IOTA, '+': DIAER, '<': DIAER,
    # '?' IS A SECOND SPELLING OF THE DIAERESIS in this file. It occurs
    # twice in the book, both times in W`RAI?SMO,J at Jer 4,30 - HORAISMOS,
    # which LXX Jeremiah attests with the dialytika on the iota - and
    # without the mapping a literal question mark stood in the Greek
    # column. It is read as a mark only after a letter; a '?' with no
    # letter before it still falls through to the punctuation below,
    # though Greek writes its question mark as ';' and none occurs.
    '?': DIAER,
}
# A smooth breathing on a capital is written BEFORE the letter, not after it:
# VIerousalhm is IEROUSALEM with the breathing on the iota. `B` is NOT the rough
# equivalent - it is capital beta, and reading it as a breathing turned every
# Babylon and Benjamin in the book into a rough-breathed vowel. Measured against
# the word list of LXX Jeremiah, beta gives 95.3% of tokens as attested forms
# and the breathing reading 94.7%.
GRK_PRE = {'V': SMOOTH, '+': SMOOTH + CIRC}
# '+' word-initial is a smooth breathing AND a circumflex: the book's one
# occurrence is +Apij at Jer 26,15, which Rahlfs writes Ἆπις. Inside a word
# the same character is the diaeresis, which is why it stands in both maps
# and to_greek() decides by position.
# The SAME 'V' is the elision apostrophe when it stands inside a word, and
# that is 298 of the book's 326: EVPV, EVFV, AVPV, KATV, METV, AVLLV. Read
# as a breathing it was dropped and its mark thrown forward onto the next
# word's first vowel, so EVFV U[DATA at Jer 2,24 came out as a smooth and a
# rough breathing on one upsilon. Rahlfs writes these with GREEK PSILI, and
# his counts in Jeremiah agree with Stipp's almost one for one - 117 EPI to
# 121, 42 EPHI to 42, 33 API to 33 - which is what identifies the sign.
ELISION = '᾿'


def to_greek(s):
    """BWGRKL -> Unicode polytonic Greek, NFC-composed.

    A diacritic binds to the LAST LETTER SEEN, not to the last unit, so that it
    still finds its vowel when the PDF has broken the word across a
    justification gap: the Synopse sets IEREMI ,AN and HEMER AIS, and attaching
    the accent to the space instead left a combining mark dangling on nothing.
    lxx_greek.repair() then rejoins the halves.
    """
    out, pend, last = [], '', -1
    inword = False
    for ch in s:
        if ch in GRK_PRE and not inword:
            pend = GRK_PRE[ch]
        elif ch == 'V' and inword:
            out.append([ELISION]); last = -1
        elif ch in GRK_BASE:
            out.append([GRK_BASE[ch]]); last = len(out) - 1
            inword = True
            if pend:
                out[-1].append(pend); pend = ''
        elif ch in GRK_MARK and last >= 0:
            out[last].append(GRK_MARK[ch])
        elif ch.isspace():
            out.append([' ']); inword = False
        elif ch in '.,;:!?()-0123456789':
            out.append([ch]); last = -1; inword = False
    txt = ''.join(''.join(u) for u in out)
    return unicodedata.normalize('NFC', re.sub(r' +', ' ', txt)).strip()


# ---------------------------------------------------------------------------
def verify():
    """Convert every BWHEBB word in the Synopse and score it against BHSA.

    The check is deliberately blunt: a word counts as right only if the
    converted string is byte-identical to a pointed graphical unit that BHSA
    attests for that consonantal skeleton. Words whose skeleton BHSA does not
    have at all are counted separately - they are Stipp's retroversions and his
    apparatus lemmas, which are not in the Hebrew Bible and cannot be scored.
    """
    import os, collections
    from paths import BOOKS
    from pypdf import PdfReader
    from tf.fabric import Fabric

    api = Fabric(locations=[os.path.expanduser("~/text-fabric-data/etcbc") + "/bhsa/tf/2021"],
                 silent="deep").load("otype g_word_utf8 g_cons_utf8 trailer_utf8", silent="deep")
    F = api.F
    acc = re.compile('[֑-ֽֿ֯]')
    idx = collections.defaultdict(set)
    cur, curc = [], []
    for w in F.otype.s("word"):
        cur.append(acc.sub('', F.g_word_utf8.v(w) or ''))
        curc.append(F.g_cons_utf8.v(w) or '')
        if F.trailer_utf8.v(w):
            if ''.join(curc):
                idx[''.join(curc)].add(''.join(cur))
            cur, curc = [], []

    r = PdfReader(BOOKS("StippJer_Textkritische_Synopse_2021.pdf"))
    ok = bad = unscorable = 0
    wrong = collections.Counter()
    for page in r.pages:
        spans = []
        page.extract_text(visitor_text=lambda t, cm, tm, fd, fs:
                          spans.append((str((fd or {}).get("/BaseFont", "")).lower(), t)))
        for f, t in spans:
            if "bwhebb" not in f:
                continue
            for vis in re.split(r'\s+', t):
                if not any(c in HEB_BASE for c in vis):
                    continue
                if not any(c in HEB_MARK for c in vis):
                    continue                       # unpointed: an apparatus lemma
                uni = to_hebrew(vis).replace('־', '')
                cons = ''.join(c for c in uni if 'א' <= c <= 'ת')
                forms = idx.get(cons)
                if not forms:
                    unscorable += 1
                elif uni in forms:
                    ok += 1
                else:
                    bad += 1
                    if len(wrong) < 400:
                        wrong[(vis, uni, sorted(forms)[0])] += 1
    tot = ok + bad
    print(f"scorable words   : {tot:,}")
    print(f"exact match      : {ok:,}  ({ok / max(tot,1):.2%})")
    print(f"mismatch         : {bad:,}")
    print(f"not in BHSA      : {unscorable:,}  (retroversions and apparatus lemmas)")
    print("\nmost frequent mismatches (ascii | converted | a BHSA form of that skeleton):")
    for (vis, got, want), n in wrong.most_common(15):
        print(f"  {n:>4}  {vis:<20} {got:<18} {want}")


if __name__ == "__main__":
    verify()
