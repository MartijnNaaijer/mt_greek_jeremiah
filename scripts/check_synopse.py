"""Score the masoretic column of the parsed Synopse against BHSA, verse by verse.

Writes results/synopse_check.json, {"7:2": true, ...}, which build_synopse_pages.py
prints as a badge on every verse. A verse is true only when the consonants of its
masoretic column reproduce BHSA's consonants for that verse exactly and in order.

The test is one-sided on purpose. It cannot catch a wrong vowel, and it cannot
catch material that BHSA also has in a different place; what it does catch is the
failure mode this extraction actually has, which is Stipp's footnote apparatus
being read as text, and that always shows up as extra or misplaced letters.
"""
import json
import os
import re
import collections

from paths import R
from tf.fabric import Fabric

CONS = re.compile('[א-ת]')


def cons(t):
    return ''.join(CONS.findall(t or ''))


def main():
    rows = json.load(open(R("synopse.json"), encoding="utf-8"))
    api = Fabric(locations=[os.path.expanduser("~/text-fabric-data/etcbc") + "/bhsa/tf/2021"],
                 silent="deep").load("otype g_cons_utf8", silent="deep")
    F, L, T = api.F, api.L, api.T
    bh = {}
    for vn in F.otype.s("verse"):
        b, c, v = T.sectionFromNode(vn)
        # ENGLISH names from T.sectionFromNode: "2_Kings". The Latin "Reges_II"
        # is the book feature, and "Kings_II" is nothing at all - it stood here
        # until 2026-09-05 and silently excluded 2 Kings 25 from the scoring.
        if b in ("Jeremiah", "2_Kings"):
            key = f"{c}:{v}" if b == "Jeremiah" else f"K{c}:{v}"
            bh[key] = cons(''.join(F.g_cons_utf8.v(w) or '' for w in L.d(vn, "word")))

    mt = collections.defaultdict(str)
    for r in rows:
        key = f"{r['ch']}:{r['v']}" if r["book"] == "Jeremiah" else f"K{r['ch']}:{r['v']}"
        for s in r["mt"]:
            mt[key] += s["text"]

    out, ok, tot, recall = {}, 0, 0, 0.0
    for key, txt in mt.items():
        want = bh.get(key)
        if want is None:
            continue
        got = cons(txt).replace('שׁ', 'ש').replace('שׂ', 'ש')
        w = want.replace('שׁ', 'ש').replace('שׂ', 'ש')
        i = 0
        for ch in got:
            if i < len(w) and ch == w[i]:
                i += 1
        exact = (i == len(w) and len(got) == len(w))
        out[key] = bool(exact)
        tot += 1; ok += exact; recall += i / max(len(w), 1)

    json.dump(out, open(R("synopse_check.json"), "w", encoding="utf-8"))
    print(f"verses scored          : {tot:,}")
    print(f"masoretic column exact : {ok:,} ({ok/max(tot,1):.1%})")
    print(f"mean in-order recall   : {recall/max(tot,1):.3f}")
    print(f"wrote {R('synopse_check.json')}")


if __name__ == "__main__":
    main()
