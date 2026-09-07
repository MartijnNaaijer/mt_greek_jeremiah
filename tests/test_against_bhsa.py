"""The masoretic column against BHSA, the one external check it has.

The other two columns have none. The alexandrian column is Stipp's retroversion
of the Greek, and his Greek panel is his own text; there is nothing to score
either against, so nothing here tries.

THESE TESTS SKIP THEMSELVES where text-fabric or the BHSA 2021 corpus is not
installed, because the repository is meant to be clonable and testable on its
own. Everything they check is a floor: the pages are extraction from a PDF and
about a sixth of the verses still deviate, so a test that demanded agreement
everywhere would only be deleted. What these guard is a FALL - the extraction
getting worse without anyone noticing.

To run them:

    pip install text-fabric
    python -c "from tf.app import use; use('etcbc/bhsa:clone', version='2021')"

Set BHSA_TF if the corpus is not under ~/text-fabric-data.
"""
import json
import os
import re
import unittest

import synopse as S

BASE = json.load(open(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                   "baseline.json"), encoding="utf-8"))["bhsa"]

# Overridable, so the corpus can live anywhere and so the skip path itself can
# be exercised:  BHSA_TF=/nonexistent python -m unittest discover -s tests
BHSA = os.environ.get(
    "BHSA_TF", os.path.expanduser("~/text-fabric-data/etcbc/bhsa/tf/2021"))


def load_bhsa():
    """{'1:1': 'DBRJ...'} - the consonants of every verse of Jeremiah and of
    2 Kings 25, or None where the corpus is not on this machine."""
    if not os.path.isdir(BHSA):
        return None
    try:
        from tf.fabric import Fabric
    except ImportError:
        return None
    api = Fabric(locations=[BHSA], silent="deep").load(
        "otype g_cons_utf8", silent="deep")
    F, L, T = api.F, api.L, api.T
    out = {}
    for vn in F.otype.s("verse"):
        # T.sectionFromNode gives ENGLISH names - 2_Kings, not the Latin
        # Reges_II of the book feature and not Kings_II, which is no name at
        # all and silently matches nothing.
        b, c, v = T.sectionFromNode(vn)
        if b == "Jeremiah":
            key = f"{c}:{v}"
        elif b == "2_Kings" and c == 25:
            key = f"K{c}:{v}"
        else:
            continue
        out[key] = "".join(
            "".join(S.HEB.findall(F.g_cons_utf8.v(w) or "")) for w in L.d(vn, "word"))
    return out


def load_units():
    """{'1:1': ['DBRJ', 'JRMJHW', ...]} - the same verses cut into GRAPHICAL
    UNITS: what stands between spaces, with the maqqef counting as a break,
    because that is how the pages set the column and how BHSA divides it.

    The consonant test above is blind to where a space falls; this is the
    ground truth for the other axis.
    """
    if not os.path.isdir(BHSA):
        return None
    try:
        from tf.fabric import Fabric
    except ImportError:
        return None
    api = Fabric(locations=[BHSA], silent="deep").load(
        "otype g_cons_utf8 trailer", silent="deep")
    F, L, T = api.F, api.L, api.T
    out = {}
    for vn in F.otype.s("verse"):
        b, c, v = T.sectionFromNode(vn)
        if b == "Jeremiah":
            key = f"{c}:{v}"
        elif b == "2_Kings" and c == 25:
            key = f"K{c}:{v}"
        else:
            continue
        units, buf = [], ""
        for w in L.d(vn, "word"):
            buf += "".join(S.HEB.findall(F.g_cons_utf8.v(w) or ""))
            if F.trailer.v(w):
                if buf:
                    units.append(buf)
                buf = ""
        if buf:
            units.append(buf)
        out[key] = units
    return out


_BH = [None]
_BU = [None]


def bhsa():
    if _BH[0] is None:
        _BH[0] = load_bhsa() or {}
    return _BH[0]


def units():
    if _BU[0] is None:
        _BU[0] = load_units() or {}
    return _BU[0]


def fold(t):
    return t.replace("שׁ", "ש").replace("שׂ", "ש")


def in_order_recall(want, got):
    i = 0
    for c in got:
        if i < len(want) and c == want[i]:
            i += 1
    return i / max(len(want), 1)


class BHSATest(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        if not bhsa():
            raise unittest.SkipTest(
                "BHSA 2021 not installed at ~/text-fabric-data/etcbc/bhsa/tf/2021")

    def column(self, verse):
        return fold(verse.consonants())

    def key(self, verse):
        return (f"{verse.chapter}:{verse.number}" if verse.page.startswith("jer")
                else f"K25:{verse.number}")


class TestTheColumnAgreesWithBHSA(BHSATest):

    def test_enough_verses_reproduce_bhsa_exactly(self):
        ok = sum(1 for v in S.verses()
                 if self.column(v) == fold(bhsa().get(self.key(v), "\0")))
        self.assertGreaterEqual(
            ok, BASE["exact_floor"],
            f"{ok} verses reproduce BHSA exactly; the floor is "
            f"{BASE['exact_floor']}. If the extraction improved, raise it.")

    def test_the_mean_recall_has_not_fallen(self):
        rs = [in_order_recall(fold(bhsa()[self.key(v)]), self.column(v))
              for v in S.verses() if self.key(v) in bhsa()]
        mean = sum(rs) / len(rs)
        self.assertGreaterEqual(mean, BASE["recall_floor"],
                                f"mean in-order recall {mean:.3f}")

    def test_the_column_is_divided_into_words_as_bhsa_divides_it(self):
        """Word-for-word agreement: the second axis, and the one the badge is
        blind to.

        The badge tests the letters and their order, so a word broken in two -
        or two run together - passes it unseen. That is how a line-break rule
        firing inside a line went unnoticed until 2026-09-07: it put a space
        inside a word in 149 verses and no test moved. This floor is the one
        that would have caught it, and it rose from 923 to 1,072 when the rule
        was fixed and the leading maqqef was no longer dropped.
        """
        same = 0
        for v in S.verses():
            want = units().get(self.key(v))
            if not want:
                continue
            got = [fold(w) for w in
                   " ".join(v.mt_printed()).replace("־", " ").split()
                   if S.HEB.search(w)]
            got = ["".join(S.HEB.findall(w)) for w in got]
            if got == [fold(w) for w in want]:
                same += 1
        self.assertGreaterEqual(
            same, BASE["word_exact_floor"],
            f"{same} verses are divided into words as BHSA divides them; "
            f"the floor is {BASE['word_exact_floor']}.")

    def test_the_badge_tells_the_truth(self):
        """A verse marked BHSA ✓ really does reproduce BHSA.

        The badge is what a reader is asked to trust, so it may not be
        optimistic. The reverse is allowed: a verse may be marked ? and happen
        to agree, since the badge is computed before the page is set.
        """
        for v in S.verses():
            if not v.confirmed():
                continue
            want = bhsa().get(self.key(v))
            if want is None:
                continue
            with self.subTest(page=v.page, verse=v.ref):
                self.assertEqual(self.column(v), fold(want),
                                 f"{v.ref} is badged ✓ but differs from BHSA")

    def test_no_verse_has_text_bhsa_does_not_have_at_all(self):
        """Every letter of the column is somewhere in BHSA's verse, in order.

        This is the weaker half of the check and the one that catches the
        failure this extraction actually has: apparatus read as text shows up as
        letters BHSA does not have, wherever they land. The floor is set below
        the current figure so that a handful of verses may still fail it.
        """
        bad = [v.ref for v in S.verses()
               if self.key(v) in bhsa()
               and in_order_recall(self.column(v), fold(bhsa()[self.key(v)])) < 1.0]
        self.assertLessEqual(
            len(bad), BASE["with_extra_text_ceiling"],
            f"{len(bad)} verses carry letters BHSA does not have here: "
            f"{bad[:8]}")


class TestTheGreekIsBesideTheRightColon(unittest.TestCase):
    """The Greek panel's placement, scored on transliterated proper names.

    A name is the same word in both columns, so it can be matched with no
    lexicon at all: where a Greek colon names Babylon and the Hebrew colon
    beside it does not, but another colon of the same verse does, the Greek is
    in the wrong row. Nothing about names goes into the placement - it is made
    on LENGTH - so this is an independent check and not the training signal.

    It was 47 verses of 430 while the cola were dealt out one per clause, and
    five of those were badged Gr OK, because that badge only compared counts.
    """

    ANCHORS = [("ιερουσαλημ", "ירושלם"), ("βαβυλ", "בבל"), ("ιουδα", "יהודה"),
               ("ισραηλ", "ישראל"), ("χαλδαι", "כשדים"), ("ιερεμι", "ירמיהו"),
               ("σεδεκι", "צדקיהו"), ("ναβουχοδονοσορ", "נבוכדראצר"),
               ("αιγυπτ", "מצרים"), ("σιων", "ציון"), ("δαυιδ", "דוד"),
               ("μωαβ", "מואב"), ("εδωμ", "אדום"), ("αμμων", "עמון")]

    @staticmethod
    def _gk(t):
        import unicodedata
        d = unicodedata.normalize("NFD", (t or "").lower())
        return "".join(c for c in d if "α" <= c <= "ω" or c in "ςϲ").replace(
            "ς", "σ").replace("ϲ", "σ")

    def test_the_greek_is_not_beside_the_wrong_colon(self):
        import json as _json
        base = _json.load(open(os.path.join(os.path.dirname(
            os.path.abspath(__file__)), "baseline.json"), encoding="utf-8"))
        testable = misplaced = 0
        for v in S.verses():
            rows = [r for r in v.rows if r.greek]
            if len(rows) < 2:
                continue
            heb = ["".join(S.HEB.findall(" ".join(w.text for w in r.og)))
                   for r in v.rows]
            whole = "".join(heb)
            hit = mis = 0
            for r in rows:
                g = self._gk(" ".join(w.text for w in r.greek))
                own = "".join(S.HEB.findall(" ".join(w.text for w in r.og)))
                for ga, ha in self.ANCHORS:
                    if ga in g:
                        if ha in own:
                            hit += 1
                        elif ha in whole:
                            mis += 1
                        break
            if hit or mis:
                testable += 1
                misplaced += bool(mis)
        self.assertGreater(testable, 400)
        self.assertLessEqual(
            misplaced, base["greek_misplaced_ceiling"],
            f"{misplaced} verses of {testable} have Greek beside the wrong "
            f"colon; the ceiling is {base['greek_misplaced_ceiling']}")


class TestTheVersesThatWereWrong(BHSATest):
    """One test per fault found on 2026-09-05, each on the verse that showed it.

    They are separate from the floors because a floor can be met while any one
    of these silently regresses.
    """

    def one(self, page, num):
        v = next(v for v in S.pages() if v.name == page for v in v.verses
                 if v.number == num)
        self.assertEqual(self.column(v), fold(bhsa()[self.key(v)]),
                         f"{v.ref} no longer reproduces BHSA")

    def test_jer_1_1_the_notation_ends_at_the_hash(self):
        self.one("jer01.html", 1)

    def test_jer_1_11_the_orphan_glyph_at_x_zero(self):
        self.one("jer01.html", 11)

    def test_jer_2_3_the_hash_that_closes_out_in_the_margin(self):
        # BHSA holds the ketiv TBW'TH here and Stipp prints it, so this one is
        # exact; the qere stands in his apparatus.
        self.one("jer02.html", 3)

    def test_jer_3_6_the_line_whose_coordinates_collapsed(self):
        self.one("jer03.html", 6)

    def test_jer_10_17_the_backslash_in_the_margin(self):
        self.one("jer10.html", 17)

    def test_jer_33_11_was_missing_from_the_book(self):
        self.one("jer33.html", 11)

    def test_jer_4_23_the_small_digit_that_is_not_a_verse_number(self):
        # Labelled a1 23; read flat, its last number is the 1.
        v = next(v for v in S.pages() if v.name == "jer04.html" for v in v.verses
                 if v.number == 23)
        self.assertTrue(v.mt_words(), "4,23 is not on the page")


class TestTheHoversAreBHSAs(BHSATest):

    def test_a_masoretic_hover_names_a_lexeme_of_its_own_verse(self):
        """A word bound to a node of this verse must carry an ETCBC lexeme.

        Not which one - that is the database's business - but that the hover is
        an analysis at all and not a form-index guess dressed as one.
        """
        n = 0
        for v in S.verses():
            page = next(p for p in S.pages() if p.name == v.page)
            for r in v.rows:
                for w in r.mt:
                    if w.pool_id is None or w.from_index:
                        continue
                    entry = page.pool[w.pool_id]
                    n += 1
                    with self.subTest(page=v.page, verse=v.ref, word=w.text):
                        self.assertTrue(all(a.get("lex") for a in entry["w"]),
                                        "a word of the analysis has no lexeme")
        self.assertGreater(n, 20000, "hardly any masoretic word is bound")


if __name__ == "__main__":
    unittest.main()
