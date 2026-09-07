"""The text on the pages is text, and it is the right text.

These tests need nothing but the repository. The ones that need BHSA - the only
external check the masoretic column has - are in test_against_bhsa.py and skip
themselves where the database is not installed.
"""
import json
import os
import re
import unicodedata
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

    def test_the_greek_column_is_words_and_not_letters(self):
        """Stipp letter-spaces a short Greek colon to fill its measure - a space
        between every character, two between words - on 247 spans over 129 of
        the 181 pages. Read as written it puts eight words on the page where
        there are two: Jer 4,30b came out 'τί π οι ήσ εις' for τί ποιήσεις. What
        is asserted here is that the debris of that has not come back, since a
        Greek word of one letter is almost always a piece of one.
        """
        # A BARE letter: one character with no breathing and no accent on it.
        # Every genuine one-letter Greek word carries a breathing - ὁ, ἡ, ὃ, ᾧ -
        # and those are single codepoints, so the test is on the DECOMPOSED
        # form. It was 565 before 2026-09-07 and is 32 now.
        n = 0
        for v in S.verses():
            for w in v.greek_words():
                d = unicodedata.normalize("NFD", w.text.strip())
                if len(d) == 1 and S.GRK.match(d):
                    n += 1
        self.assertLessEqual(
            n, BASELINE["greek_single_letter_ceiling"],
            f"{n} Greek words are a single letter, was "
            f"{BASELINE['greek_single_letter_ceiling']}")

    def test_the_letter_spaced_verse_that_showed_it(self):
        # Jer 4,30b, and the ὡραϊσμός of 4,30f, whose diaeresis was written '?'
        # in the source font and had no mapping, so a literal question mark
        # stood on the page. Neither fault could be seen by the attested-form
        # count: the broken pieces οι and εις are themselves Greek words, and
        # the '?' drops out of the comparison as punctuation.
        v = next(v for v in S.pages()[3].verses if v.number == 30)
        greek = " ".join(w.text for w in v.greek_words())
        self.assertIn("ποιήσεις", greek)
        self.assertIn("ὡραϊσμός", greek)
        self.assertNotIn("?", greek)

    def test_the_marks_the_greek_map_had_wrong(self):
        """Four entries of bwfonts.GRK_MARK, one verse each.

        None of them could be seen by the attested-form count, which strips
        accent and breathing before comparing; the measure that shows them is
        exact agreement with a Rahlfs form, and that moved 91.4% to 96.9% when
        they were fixed.
        """
        def greek(page, number):
            v = next(v for v in S.pages()[int(page[3:5]) - 1].verses
                     if v.number == number)
            return unicodedata.normalize(
                "NFC", " ".join(w.text for w in v.greek_words()))
        # '-' was printing as a literal hyphen: 'ω-ν' for ὧν, 184 places.
        self.assertIn("ὧν", greek("jer02.html", 32))
        self.assertIn("οὗτος", greek("jer08.html", 5))
        self.assertNotIn("-", greek("jer02.html", 32))
        # "'" was unmapped and simply lost: 'η' for ἢ, 57 places.
        self.assertIn("ἢ", greek("jer02.html", 14))
        # 'V' inside a word is the elision apostrophe, not a breathing on the
        # next word's vowel: ἐφ᾿ ὕδατα at 2,24, 298 places.
        self.assertIn("ἐφ᾿ ὕδατα", greek("jer02.html", 24))

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


class TestABracketDoesNotBreakAWord(unittest.TestCase):
    """Stipp brackets INSIDE a word wherever the two editions differ only in a
    prefix, a suffix or a letter, and the page has to set those pieces as one
    word while still colouring the bracketed part. Both faults below were on the
    pages until 2026-09-07 and neither could be seen by the BHSA badge, which
    tests the letters and their order and is blind to where a space falls.
    """

    def words(self, page, number):
        """The printed words of one verse, canonically ordered.

        The points come off the page in the order BWHEBB writes them, which is
        not always the canonical one - dagesh before vowel here, after it there
        - so a literal typed into this file would compare unequal to a word
        that is right. NFC settles the order on both sides.
        """
        v = next((v for v in S.pages()[int(page[3:5]) - 1].verses
                  if v.number == number), None)
        self.assertIsNotNone(v, f"{page} {number} is not on the page")
        return [unicodedata.normalize("NFC", w) for w in v.mt_printed()]

    def assertPrinted(self, word, page, number):
        self.assertIn(unicodedata.normalize("NFC", word), self.words(page, number))

    def test_a_bracketed_prefix_stays_on_its_word(self):
        # Jer 4,5b: the conjunction of U-BIRUSHALAIM is a masoretic plus, so
        # Stipp sets ] W [ BIRUSHALAIM and the waw is its own span. A line-break
        # rule in parse_synopse.py fired inside the line and put a space after
        # it, and the page read WU BIRUSHALAIM.
        self.assertPrinted("וּבִירוּשָׁלַםִ", "jer04.html", 5)

    def test_a_bracketed_suffix_stays_on_its_word(self):
        # Jer 4,2a: the same fault at the other end of a word. The T' of
        # WE-NISHBA'TA is a masoretic plus and came out as a word of its own.
        self.assertPrinted("וְנִשְׁבַּעְתָּ", "jer04.html", 2)

    def test_the_sof_pasuq_is_written_against_its_word(self):
        """It never begins a word, so it may not stand off from one.

        Stipp sets his parenthetical apparatus inline in the text column, and
        the gap around it arrives as a Hebrew span of nothing but space. Where
        that fell between the last word of a verse and its sof pasuq the sign
        was set adrift - 339 clauses, 115 masoretic and 224 alexandrian, of
        which Jer 4,1d was one.
        """
        self.assertPrinted("תָנוּד׃", "jer04.html", 1)

        # The exception is a clause whose text is ENTIRELY a masoretic plus:
        # the alexandrian cell then holds the verse-end sign and nothing else,
        # which is the structure of the verse and not a spacing fault.
        adrift, alone = 0, 0
        for v in S.verses():
            for r in v.rows:
                for cell in (r.mt_printed(), r.og_printed()):
                    if cell == ["׃"]:
                        alone += 1
                    else:
                        adrift += sum(1 for w in cell if w.startswith("׃"))
        self.assertEqual(adrift, 0, f"{adrift} words begin with a sof pasuq")
        self.assertLessEqual(alone, BASELINE["lone_sof_pasuq_ceiling"])

    def test_a_bracket_between_a_prefix_and_its_noun(self):
        """Jer 4,3a: WE-LI <JOSHBEJ> JERUSHALAIM.

        Stipp's space stands on the far side of the bracket, where it is the
        alexandrian reading's word-space; the masoretic reading is one word.
        The page had WE-LI and JERUSHA as two, and the last three glyphs of
        JERUSHALAIM were missing besides, having overflowed the left edge of
        the text column into the margin.
        """
        self.assertPrinted("וְלִירוּשָׁלַםִ", "jer04.html", 3)
        self.assertPrinted("מִצָּפוֹן", "jer01.html", 14)
        self.assertPrinted("לְמַלְכֵי", "jer01.html", 18)
        self.assertPrinted("וִירוּשָׁלַםִ", "jer19.html", 7)
        # and the words that are NOT fragments stay apart, though they too are
        # spelled with nothing but proclitic letters
        self.assertPrinted("כֹּה", "jer19.html", 1)
        self.assertPrinted("שֵׁב", "jer36.html", 15)
        self.assertPrinted("כָּל־הַשָּׂדֶה", "jer12.html", 4)

    def test_the_left_end_of_a_long_line_is_text_and_not_margin(self):
        """Jer 2,34a, and the fault it showed.

        The text column is set flush right and overflows MARGIN_X on a long
        line, so its left end fell into the leading margin run and was dropped.
        Here NEQIJIM stands at x = 141.5 with the bracket that closes the plus
        on 'EBJONIM at 166.1, and BOTH were being read as margin - so the verse
        lost a word AND the masoretic plus beside it. 80 verses of the book had
        text sitting in a margin note that way; 41 of them are recovered, and
        what is left is further left than the floor `OVERFLOW_X` allows.
        """
        v = next(v for v in S.pages()[1].verses if v.number == 34)
        self.assertIn(unicodedata.normalize("NFC", "נְקִיִּים"),
                      [unicodedata.normalize("NFC", w) for w in v.mt_printed()])
        # the bracket travels with the word: 'EBJONIM is still marked a plus
        self.assertTrue(
            any("plus" in w.cls and "אֶבְיוֹנִים" in unicodedata.normalize("NFC", w.text)
                for w in v.mt_words()),
            "the masoretic plus of 2,34a was lost with the margin run")

    def test_a_siglum_in_the_margin_is_not_a_bracket(self):
        """Jer 8,1, the largest single loss in the book.

        The margin note reads '7,30-8,3 > 4Q70* (4QJer a*)' - Stipp's siglum
        for "absent from", with the witness after it. Read as the bracket that
        opens an alexandrian plus it opened one that never closed, and the
        whole of 8,1b went to the alexandrian column: 89 letters. Real markup
        in the margin is the LEFTMOST thing on the printed line, so nothing
        but space follows it in its span.
        """
        v = next(v for v in S.pages()[7].verses if v.number == 1)
        mt = unicodedata.normalize("NFC", " ".join(v.mt_printed()))
        self.assertIn("וְיֹצִיאוּ", mt)
        self.assertIn("מִקִּבְרֵיהֶם", mt)

    def test_a_printed_line_set_in_two_pieces_is_read_right_to_left(self):
        """Jer 10,16 and 44,1: the halves came back in the wrong order.

        Where Stipp's typesetter sets one printed line as two text objects,
        pypdf hands back the LEFT half first, and the column runs right to
        left. At 10,16 the label 'c' sits on the right half with WE-JISRAEL
        SHEBET while NAHALATO, the left half of the same line, was handed to
        the clause before it - so the verse read HU NAHALATO WE-JISRAEL SHEBET
        for BHSA's HU WE-JISRAEL SHEBET NAHALATO. Nothing was ever lost here;
        only the order was wrong, which is why no earlier check caught it.
        """
        def mt(page, number):
            v = next(v for v in S.pages()[int(page[3:5]) - 1].verses
                     if v.number == number)
            return unicodedata.normalize("NFC", " ".join(v.mt_printed()))
        self.assertIn("הוּא וְיִשְׂרָאֵל שֵׁבֶט נַחֲלָתוֹ", mt("jer10.html", 16))
        self.assertIn("בְּאֶרֶץ מִצְרָיִם הַיֹּשְׁבִים", mt("jer44.html", 1))

    def test_a_maqqef_that_opens_a_segment_is_still_printed(self):
        # Jer 4,27a and 3,8: Stipp brackets one half of a maqqef pair, so the
        # maqqef itself opens the segment that follows - KJ / -KH, 'T / -SPR.
        # tokenise() could not match a leading maqqef and dropped it, and the
        # two halves were printed run together as KJKH and 'TSPR.
        self.assertPrinted("כִּי־כֹה", "jer04.html", 27)
        self.assertPrinted("אֶת־סֵפֶר", "jer03.html", 8)

    def test_no_masoretic_word_is_a_bare_point_or_a_lone_letter_beside_one(self):
        """The general form of the two faults above, over the whole book.

        A printed word of a single Hebrew letter is legitimate - the
        prepositions, the conjunction before a shewa - but one that carries no
        vowel of its own next to a word that begins with a vowel point is the
        signature of a word cut in two. What is asserted here is only that the
        count has not risen; the source itself breaks words across its
        justification gaps and some of these are its own.
        """
        n = 0
        for v in S.verses():
            for w in v.mt_printed():
                if len(S.HEB.findall(w)) == 1 and len(w) == 1:
                    n += 1
        self.assertLessEqual(n, BASELINE["bare_letter_ceiling"],
                             f"{n} masoretic words are a single unpointed letter, "
                             f"was {BASELINE['bare_letter_ceiling']}")


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
