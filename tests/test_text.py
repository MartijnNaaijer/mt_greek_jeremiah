"""The text on the pages is text, and it is the right text.

These tests need nothing but the repository. The ones that need BHSA - the only
external check the masoretic column has - are in test_against_bhsa.py and skip
themselves where the database is not installed.
"""
import json
import os
import re
import unittest

import synopse as S

BASELINE = json.load(open(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                       "baseline.json"), encoding="utf-8"))

# Read off Stipp's Synopse by hand, against his Einleitung. Four of the five are
# verses that were wrong at some point on 2026-09-05 and each was wrong for a
# different reason; the fifth, 1,2, is the one that showed the backslash reaches
# a single word and not the whole clause.
GOLDEN = {
    # § DBRJ \ DBR-JHWH 'SR HJH 'L # JRMJHW ... - the notation ends at the #,
    # so JRMJHW BN-XLQJHW MN-HKHNJM is common to both editions. It is printed
    # in Stipp and must never be marked as coming from anywhere else.
    ("jer01.html", 1): "דברי ירמיהו בן חלקיהו מן הכהנים אשר בענתות בארץ בנימן",
    # The H that used to open this verse was an orphan glyph at x = 0.
    ("jer01.html", 11): "ויהי דבר יהוה אלי לאמר מה אתה ראה ירמיהו ואמר מקל שקד אני ראה",
    # A bare backslash marks BN-'AMON against 'AMOTS and nothing else. The page
    # sets BI-SHLO SH-'ESREH, because the PDF breaks that word across a
    # justification gap; see test_the_justification_gaps_are_the_source_s_own.
    ("jer01.html", 2): ("אשר היה דבר יהוה אליו בימי יאשיהו בן אמון מלך יהודה "
                        "בשלש עשרה שנה למלכו"),
    # The # that closes this notation stands out in the margin at x = 30.
    ("jer02.html", 3): ("קדש ישראל ליהוה ראשית תבואתה כל אכליו יאשמו רעה תבא "
                        "אליהם נאם יהוה"),
    # Here the backslash itself is in the margin.
    ("jer10.html", 17): "אספי מארץ כנעתך ישבתי במצור",
}

# Of those, the ones the source itself sets with a broken word.
JUSTIFIED = {("jer01.html", 2)}


def cons(words):
    """The consonantal skeleton of a list of words, one word per element.

    Word by word, never over the joined string: the vowels have to come out of
    each word separately or the word boundaries go with them.
    """
    out = ["".join(S.HEB.findall(w.text)) for w in words]
    return " ".join(w for w in out if w)


class TestTheTextIsText(unittest.TestCase):

    def test_the_hebrew_columns_hold_only_hebrew(self):
        # Stipp's sigla are [ ] < > \ # § * and his apparatus is set in Latin.
        # Any of it in a text cell means a siglum was read as a word, which is
        # the failure mode this extraction has.
        for v in S.verses():
            for w in v.mt_words() + v.og_words():
                with self.subTest(page=v.page, verse=v.ref, word=w.text):
                    self.assertTrue(S.is_hebrew_text(w.text),
                                    f"{v.ref}: {w.text!r} is not Hebrew")

    def test_the_greek_column_holds_only_greek(self):
        for v in S.verses():
            for w in v.greek_words():
                t = w.text.strip()
                with self.subTest(page=v.page, verse=v.ref, word=t):
                    self.assertTrue(S.GRK.search(t), f"{v.ref}: {t!r} has no Greek")
                    self.assertFalse(re.search(r"[A-Za-z]", t),
                                     f"{v.ref}: {t!r} has Latin letters")

    def test_no_verse_is_empty(self):
        for v in S.verses():
            with self.subTest(page=v.page, verse=v.ref):
                self.assertTrue(v.mt_words() or v.og_words(),
                                "a verse with no Hebrew in either column")

    def test_nothing_on_the_page_comes_from_bhsa(self):
        # BHSA is the check, not the source. A repair that supplied the column's
        # missing words from the database was built and removed on 2026-09-05:
        # it marked MN-HKHNJM at Jer 1,1 as supplied although Stipp prints it,
        # which is what such a repair does to any word merely misplaced.
        for p in S.pages():
            with self.subTest(page=p.name):
                self.assertNotIn('class="w sup"', p.html)
                self.assertNotIn("BHSA ✎", p.html)


class TestTheRightText(unittest.TestCase):

    def test_the_verses_read_by_hand_off_the_synopse(self):
        """The letters, and their order.

        Compared without the spaces, because where a space falls is the source's
        business and not this extraction's - see the test below.
        """
        by_ref = {(v.page, v.number): v for v in S.verses()}
        for key, want in GOLDEN.items():
            with self.subTest(verse=key):
                v = by_ref.get(key)
                self.assertIsNotNone(v, f"{key} is not on the page")
                self.assertEqual(cons(v.mt_words()).replace(" ", ""),
                                 want.replace(" ", ""))

    def test_the_word_boundaries_too_where_the_source_sets_them_cleanly(self):
        by_ref = {(v.page, v.number): v for v in S.verses()}
        for key, want in GOLDEN.items():
            if key in JUSTIFIED:
                continue
            with self.subTest(verse=key):
                self.assertEqual(cons(by_ref[key].mt_words()), want)

    def test_the_justification_gaps_are_the_source_s_own(self):
        """Stipp's PDF breaks a word across a justification gap and sets a real
        space in it, so the word arrives split and there is nothing in the file
        to say it should not be. Jer 1,2 has BI-SHLO SH-'ESREH for BI-SHLOSH
        'ESREH. This is pinned rather than fixed: closing the gap would mean
        guessing, and a guess in the text is worse than a visible seam. About a
        sixth of the verses have one somewhere.
        """
        v = next(v for v in S.pages()[0].verses if v.number == 2)
        words = cons(v.mt_words()).split()
        self.assertIn("בשל", words)
        self.assertIn("ש", words)
        self.assertNotIn("בשלש", words)

    def test_the_alexandrian_column_of_jer_1_1(self):
        # The retroversion of tò rhēma toû theoû hò egéneto epì Ieremian: the
        # two editions share everything after the notation closes.
        v = next(v for v in S.pages()[0].verses if v.number == 1)
        self.assertEqual(cons(v.og_words()),
                         "דבר יהוה אשר היה על ירמיהו בן חלקיהו מן הכהנים "
                         "אשר ישב בענתות בארץ בנימן")


class TestMarkup(unittest.TestCase):

    def test_ketiv_qere_is_marked_in_the_masoretic_column_only(self):
        # The qere is an apparatus of the masoretic text. The alexandrian column
        # is a retroversion of the Greek and has no reading tradition to report,
        # so a K there would assert something about a text that does not have it.
        for v in S.verses():
            for r in v.rows:
                with self.subTest(page=v.page, verse=v.ref):
                    self.assertEqual(r.og_kq, 0, "a K in the alexandrian column")

    def test_every_word_class_is_one_the_stylesheet_knows(self):
        known = {"common", "plus", "minus", "mtvar", "ogvar", "scope", "nolink", ""}
        for v in S.verses():
            for w in v.mt_words() + v.og_words() + v.greek_words():
                for c in w.cls.split():
                    with self.subTest(page=v.page, verse=v.ref, cls=c):
                        self.assertIn(c, known)

    def test_a_word_read_from_the_form_index_says_so(self):
        # data-x means the analysis is not this verse's but a form that has
        # exactly one analysis in the whole database. The hover labels it, and
        # it must never appear on a masoretic word, which always has a node.
        for v in S.verses():
            for w in v.mt_words() + v.og_words() + v.greek_words():
                if w.from_index:
                    with self.subTest(page=v.page, verse=v.ref, word=w.text):
                        self.assertIsNotNone(w.pool_id)


class TestBaseline(unittest.TestCase):
    """Counts recorded when the tests were written.

    They are not targets. They are here so that a change in the pipeline shows
    up as a number to be explained rather than passing unnoticed; raise the
    floors when the extraction improves.
    """

    def test_the_book_is_all_there(self):
        self.assertEqual(len(S.verses()), BASELINE["verses"])
        self.assertEqual(sum(len(p.pool) for p in S.pages()),
                         BASELINE["pool_entries"])

    def test_the_share_confirmed_against_bhsa_has_not_fallen(self):
        ok = sum(1 for v in S.verses() if v.confirmed())
        self.assertGreaterEqual(
            ok, BASELINE["confirmed_floor"],
            f"{ok} verses agree with BHSA, was {BASELINE['confirmed_floor']}")

    def test_the_verses_known_to_be_missing_have_not_multiplied(self):
        present = {(v.chapter, v.number) for v in S.verses()
                   if v.page.startswith("jer")}
        missing = [ref for ref in BASELINE["expected_missing"]
                   if tuple(ref) not in present]
        self.assertEqual([list(m) for m in missing], BASELINE["expected_missing"],
                         "a verse that used to be present has gone")
        self.assertEqual(len(present), BASELINE["jeremiah_verses"])

    def test_the_ketiv_qere_marks_have_not_been_lost(self):
        kq = sum(r.mt_kq for v in S.verses() for r in v.rows)
        self.assertGreaterEqual(kq, BASELINE["ketiv_qere_floor"])


if __name__ == "__main__":
    unittest.main()
