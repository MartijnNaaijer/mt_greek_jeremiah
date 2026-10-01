"""Where the Synopse scripts find their inputs and put their outputs.

The scripts that build these pages live in this repository; what they read
does not, and two things never will:

- STIPP'S PDF, the Textkritische Synopse zum Jeremiabuch, 15. korrigierte
  interne Auflage (2021). It is an internal edition and is not distributed
  here. BOOKS() looks for it in the research project this repository sits in,
  deuteronomistic/paper/books_for paper/, or in SYNOPSE_BOOKS if that is set.
- THE INTERMEDIATE FILES - synopse.json, the BHSA and LXX word lists, the
  per-verse check - which other analyses of the project also read. R() keeps
  them in deuteronomistic/results/, or in SYNOPSE_RESULTS if that is set.

BHSA and the Rahlfs LXX are read through text-fabric, from ~/text-fabric-data.
The pages are written to docs/ (MTG), which GitHub Pages serves at the site
root.

Every path is absolute and keyed off __file__, so a script runs from any
working directory.
"""
import os

SCRIPTS = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(SCRIPTS)                  # mt_greek_jeremiah/
PROJECT = os.path.dirname(REPO)                  # deuteronomistic/, when the
                                                 # repository sits in it
RESULTS = os.environ.get("SYNOPSE_RESULTS", os.path.join(PROJECT, "results"))
BOOKSDIR = os.environ.get("SYNOPSE_BOOKS",
                          os.path.join(PROJECT, "paper", "books_for paper"))


def R(name=""):
    """An intermediate file: synopse.json, the word lists, the checks."""
    return os.path.join(RESULTS, name)


def BOOKS(name=""):
    """Stipp's PDF and its Einleitung; never part of this repository."""
    return os.path.join(BOOKSDIR, name)


def MTG(name=""):
    """The built pages, docs/ of this repository."""
    return os.path.join(REPO, "docs", name)
