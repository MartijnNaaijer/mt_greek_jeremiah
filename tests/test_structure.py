"""The pages hold together: files, tables, rows, links, hovers.

Every assertion here guards a fault that actually occurred. The comment on each
says which, because a test whose reason is forgotten is a test that gets deleted
the first time it is inconvenient.
"""
import json
import os
import re
import unittest

import synopse as S


class TestFiles(unittest.TestCase):

    def test_every_chapter_of_jeremiah_is_present(self):
        names = {f for f in os.listdir(S.DOCS) if f.endswith(".html")}
        for ch in range(1, 53):
            self.assertIn(f"jer{ch:02d}.html", names, f"Jeremiah {ch} is missing")
        self.assertIn("2kings25.html", names)
        self.assertIn("index.html", names)
        self.assertEqual(len(names), 54, "54 pages: 52 chapters, 2 Kings 25, index")

    def test_every_page_has_a_title_and_is_self_contained(self):
        for p in S.pages():
            with self.subTest(page=p.name):
                self.assertTrue(p.title, "no <title>")
                # Self-contained: the pages must open from a file system and
                # from a mailbox, so nothing may be fetched.
                self.assertNotIn("<link rel=\"stylesheet\"", p.html)
                self.assertNotIn("<script src=", p.html)
                self.assertIn("<style>", p.html)

    def test_the_index_links_to_every_page_exactly_once(self):
        idx = S.read("index.html")
        for name in S.chapter_files():
            self.assertEqual(idx.count(f'href="{name}"'), 1,
                             f"{name} should be linked once from the index")

    def test_the_index_has_no_navigation_of_its_own(self):
        # It used to carry a lone link to Jeremia 1, which read as a second and
        # stranger entry beside the Jeremia 1 of the chapter list below it.
        idx = S.read("index.html")
        self.assertNotIn("<nav>", idx)
        self.assertEqual(idx.count(">Jeremia 1 "), 1)

    def test_chapter_pages_can_be_walked_forwards_and_backwards(self):
        names = S.chapter_files()
        for i, p in enumerate(S.pages()):
            with self.subTest(page=p.name):
                nav = re.search(r"<nav>(.*?)</nav>", p.html, re.S).group(1)
                self.assertIn('href="index.html"', nav)
                if i:
                    self.assertIn(f'href="{names[i-1]}"', nav)
                if i + 1 < len(names):
                    self.assertIn(f'href="{names[i+1]}"', nav)


class TestTables(unittest.TestCase):

    def test_every_table_states_its_column_widths(self):
        # Each verse is its own table. Left to the default auto layout, every
        # verse sized its columns to its own content and the columns wandered
        # down the page: Jer 1,1 has the longest Greek line of its chapter, so
        # its masoretic column narrowed and its text - set flush right - stood
        # further right than every other verse of the chapter.
        for p in S.pages():
            with self.subTest(page=p.name):
                self.assertIn("table-layout:fixed", p.html)
                tables = re.findall(r"<table>(.*?)</table>", p.html, re.S)
                self.assertTrue(tables)
                for t in tables:
                    self.assertTrue(
                        t.startswith('<colgroup><col class="mt"><col class="cl">'
                                     '<col class="og"><col class="grk"></colgroup>'),
                        "a table without a colgroup sizes itself")

    def test_no_row_is_blank(self):
        # A row used to be skipped on what its record HELD rather than on what
        # it rendered, so a clause whose only note was a page number - dropped
        # on the way out - left an empty row and an empty note strip. Two of
        # them stood at the head of Jer 1,1.
        for p in S.pages():
            for v in p.verses:
                for r in v.rows:
                    with self.subTest(page=p.name, verse=v.ref):
                        self.assertTrue(
                            r.mt or r.og or r.greek,
                            f"{v.ref}: a row with nothing in any column")
                for n in v.notes:
                    with self.subTest(page=p.name, verse=v.ref):
                        self.assertTrue(re.sub(r"<[^>]+>", "", n).strip(),
                                        f"{v.ref}: an empty note strip")

    def test_every_row_has_the_same_four_columns(self):
        for p in S.pages():
            for v in p.verses:
                for r in v.rows:
                    cls = [c[0] for c in r.raw]
                    with self.subTest(verse=v.ref):
                        self.assertIn("heb", cls[0])
                        self.assertIn("cl", cls[1])
                        self.assertIn("heb", cls[2])
                        self.assertIn("grk", cls[3])


class TestVerses(unittest.TestCase):

    def test_verse_numbers_ascend_and_never_repeat(self):
        for p in S.pages():
            nums = [v.number for v in p.verses]
            with self.subTest(page=p.name):
                self.assertEqual(nums, sorted(nums), "verses out of order")
                self.assertEqual(len(nums), len(set(nums)), "a verse appears twice")

    def test_the_anchor_agrees_with_the_printed_reference(self):
        for v in S.verses():
            with self.subTest(page=v.page, id=v.id):
                self.assertTrue(v.ref, "no printed reference")
                self.assertEqual(int(v.ref.split(",")[1]), v.number)

    def test_the_chapter_matches_the_file_it_is_in(self):
        for p in S.pages():
            if not p.name.startswith("jer"):
                continue
            ch = int(p.name[3:5])
            for v in p.verses:
                with self.subTest(page=p.name, verse=v.ref):
                    self.assertEqual(v.chapter, ch)

    def test_every_verse_says_whether_it_agrees_with_bhsa(self):
        # The pages are extraction from a PDF and are not uniformly reliable.
        # A verse that did not say which it was would have to be trusted like
        # every other, which is the one thing they must not invite.
        for v in S.verses():
            with self.subTest(page=v.page, verse=v.ref):
                self.assertTrue(v.confirmed() or v.unconfirmed(),
                                "neither BHSA ✓ nor BHSA ?")
                self.assertFalse(v.confirmed() and v.unconfirmed())


class TestTheSentenceCount(unittest.TestCase):
    """Stipp counts his lettered segments as SENTENCES, and so must the page.

    They are not cola. A colon is part of a stichus, a verse line built of two
    or three of them, and Hebrew prose has no stichometry and therefore no cola
    at all. The author's instruction, and with it a rule for the arithmetic:
    a label with a subscript index - a1 a2 a3 - marks the parts of ONE sentence
    split by an embedded sentence, and counts once.
    """

    def _by_hand(self, page):
        """The sentences the page itself shows, counted off the page."""
        n, seen = 0, set()
        for v in page.verses:
            for r in v.rows:
                if not any(S.HEB.search(w.text) for w in r.mt + r.og):
                    continue        # a note or an apparatus, not a sentence
                base = re.sub(r"\d+$", "", r.letter)
                if not base:
                    n += 1          # no letter, so it stands on its own
                elif (v.number, base) not in seen:
                    seen.add((v.number, base))
                    n += 1
        return n

    def test_the_printed_count_is_the_one_the_page_shows(self):
        for p in S.pages():
            with self.subTest(page=p.name):
                self.assertIsNotNone(p.sentences_printed,
                                     "the page prints no sentence count")
                self.assertEqual(p.sentences_printed, self._by_hand(p))

    def test_the_indexed_parts_are_counted_once(self):
        """Jer 1 printed 63 until 2026-09-11 and has 59.

        Two of its labels carry an index and two of its records carry no Hebrew
        at all. The book as a whole printed 5,326 where it has 5,004.
        """
        p = next(x for x in S.pages() if x.name == "jer01.html")
        self.assertEqual(p.sentences_printed, 59)
        rows = sum(len(v.rows) for v in p.verses)
        self.assertGreater(rows, p.sentences_printed,
                           "no label was merged, so the rule did not fire")
        # and the indexed labels really are on the page
        idx = [r.letter for v in S.verses() for r in v.rows
               if re.search(r"\d$", r.letter)]
        self.assertGreater(len(idx), 200)

    def test_no_page_calls_a_sentence_a_colon(self):
        """The German wording lives in build_synopse_pages.py alone, so it can
        only drift back by an edit to the script. This is the guard."""
        for p in S.pages():
            with self.subTest(page=p.name):
                self.assertNotIn("Kolon", p.html)
                self.assertNotIn("Kola", p.html)

    def test_the_legend_is_German(self):
        """It was the last English furniture on the page, under the heading,
        beside a subtitle and column headers that had always been German."""
        for p in S.pages():
            with self.subTest(page=p.name):
                m = re.search(r'<div class="legend">(.*?)</div>', p.html, re.S)
                self.assertIsNotNone(m, "the page has no legend")
                leg = m.group(1)
                self.assertIn("masoretisches Plus", leg)
                self.assertIn("qualitative Variante", leg)
                for w in ("masoretic", "alexandrian", "variant", "marked",
                          "completed", "abbreviated", "the "):
                    self.assertNotIn(w, leg)


class TestHovers(unittest.TestCase):

    def test_every_hover_resolves_into_the_page_pool(self):
        for p in S.pages():
            n = len(p.pool)
            for v in p.verses:
                for w in v.mt_words() + v.og_words() + v.greek_words():
                    if w.pool_id is None:
                        continue
                    with self.subTest(page=p.name, verse=v.ref, word=w.text):
                        self.assertLess(w.pool_id, n, "data-a points past the pool")

    def test_every_pool_entry_carries_an_analysis(self):
        for p in S.pages():
            for i, e in enumerate(p.pool):
                with self.subTest(page=p.name, entry=i):
                    self.assertTrue(e.get("f"), "no surface form")
                    self.assertTrue(e.get("w"), "no analysis")
                    self.assertTrue(any(a.get("lex") for a in e["w"]),
                                    "no lexeme in any of its words")

    def test_the_pool_is_reached(self):
        # An entry nothing points at is dead weight in a file that is served
        # over the wire; it also means a word lost its hover.
        for p in S.pages():
            used = {w.pool_id for v in p.verses
                    for w in v.mt_words() + v.og_words() + v.greek_words()
                    if w.pool_id is not None}
            with self.subTest(page=p.name):
                self.assertEqual(set(range(len(p.pool))) - used, set(),
                                 "pool entries nothing refers to")


if __name__ == "__main__":
    unittest.main()
