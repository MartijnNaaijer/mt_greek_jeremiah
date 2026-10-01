"""Set Stipp's Textkritische Synopse as HTML, one page per chapter of Jeremiah.

Reads results/synopse.json (parse_synopse.py) and writes 53 pages into
mt_greek_jeremiah/docs/: jer01.html to jer52.html, 2kings25.html for the three
pages of the parallel, and index.html. That folder is a git repository of its
own and is served as a website from GitHub Pages, which is why the pages sit in
docs/ and not at its top level - Pages serves /docs at the site root. The path
comes from paths.MTG() and is not spelled out here. Each page is self-contained - the data is
embedded, the CSS is inline, nothing is fetched - so a page can be opened from
the file system or mailed to someone.

WHAT IS ON A PAGE. Each verse is a block; each clause of the verse is a row of
three columns - the masoretic text, the retroverted alexandrian text, and Stipp's
own unretroverted Greek at the right - with his clause letter between the two
Hebrew columns and his apparatus beneath. Colour marks what the two editions do
not share:

    masoretic plus        text the alexandrian edition does not have
    alexandrian plus      text the masoretic edition does not have
    variant               the two readings of a qualitative variant, each in
                          its own column
    marked                a stretch Stipp brackets without giving an
                          alternative: the difference is in the note

EVERY VERSE CARRIES ITS OWN VERIFICATION, AND NOTHING IS WRITTEN INTO IT. The
masoretic column is the BHS text, so it has a ground truth and can be scored
against it: the badge on each verse says whether the column reproduces BHSA's
consonants exactly and in order. 1,299 of 1,394 verses do (93.2%), and the rest
carry BHSA ? and are named as unverified.

BHSA IS THE CHECK AND NOT THE SOURCE, and that is a decision, not an oversight.
A repair that aligned the column to BHSA and spliced in the words it was missing
stood here for part of 2026-09-05 and was taken out again. It read well and it
was wrong in principle: at Jer 1,1 it marked MN-HKHNJM as supplied from the
database when Stipp prints it plainly - the parser had merely put it in the
wrong place - and a repair of that kind will always mislabel a misplaced word as
an absent one. The text is all in the Synopse; what was needed was to read it
correctly, which is what parse_synopse.py now does. The score above is 65.2%
before that reading was fixed and 93.2% after.

EVERY HEBREW WORD CARRIES A HOVER with its BHSA analysis: lex, sp, vt, vs, ps,
nu, gn, plus the vocalised lexeme so the code is readable. The two columns get it
from different places and say so. A masoretic word is matched to the graphical
units of its own verse in BHSA - a longest-common-subsequence alignment on the
consonantal skeleton, so a word Stipp spells differently simply goes unmatched
rather than borrowing its neighbour's analysis - and the hover is then the
database's own reading of that word in that verse. An alexandrian word has no
node to link to: it is a retroversion of the Greek, and some of its forms are not
in the Hebrew Bible at all. Those are looked up in an index of forms that have
exactly ONE analysis anywhere in BHSA (33,208 of 39,852 skeletons); an ambiguous
form gets nothing rather than a guess, and what is shown is marked as coming from
the form index, not from the verse.

The unit is the graphical unit, so one hover can hold several BHSA words:
HA-DABAR shows H as article and DBR/ as noun, because that is how BHSA cuts it.

KETIV/QERE IS MARKED WITH A SUPERSCRIPT K, and only in the masoretic column.
BHSA holds 194 of them in Jeremiah and 2 Kings 25, of which those falling in a
word the alignment matched can be marked. The marker goes on the masoretic side alone
because ketiv/qere is an apparatus of that text: the alexandrian column is a
retroversion of the Greek and has no masoretic reading tradition to report, so
marking a word there - even one common to both editions - would assert something
about a text that does not have it. The hover gives both forms.

THE GREEK WORDS CARRY A HOVER TOO, from the Rahlfs LXX in Text-Fabric
(lxx_greek.py). Each clause knows its reference in GREEK versification, so its
words are matched to the words of that verse in Rahlfs - a longest-common-
subsequence alignment on the accent-stripped form - and the hover gives the
lemma, sp, case, tense, voice, mood, ps, nu, gn and the gloss. The lemma is set
in GREEK, not in the Latin transliteration this corpus also carries:
lxx_greek.py reads `lex_utf8` and not `lex`, so a Greek word is analysed in its
own script the way a Hebrew word is. Where the alignment misses,
a form with exactly one analysis in LXX Jeremiah is read from a form index and
labelled as such, on the same rule as the Hebrew.

THE GREEK COLUMN IS PLACED BY LENGTH, not dealt out in order. Stipp sets one
Greek colon per line, and parse_synopse._place_greek() puts each beside the
Hebrew colon whose own text falls at the same point in the verse, keeping the
order - so a long Hebrew colon may take two Greek ones and a short one none.
Dealing them one per clause, which is what this did until 2026-09-07, is right
only while the two colometries agree, and at Jer 28,1 the Greek has five cola to
the Hebrew's four, so every row after the first came out one place low. Scored
on transliterated proper names - an independent check, since the placement is
made on length and knows nothing of names - the verses with Greek beside the
wrong colon fell from 47 of 430 to 7, and none of the 7 is badged "Gr ✓".

SINCE 2026-10-01 THE GREEK IS PLACED BY POSITION, NOT BY LENGTH, and the
paragraph above is history. Stipp sets the Greek panel row by row beside the
Hebrew, and with the page geometry read by PyMuPDF each Greek line goes to the
Hebrew sentence it stands level with (parse_synopse.place_greek_by_position):
5,181 of the book's 5,182 Greek lines do. "Gr ✓" means every Greek line of the
verse was placed that way - read off the page, not inferred - and holds for
1,312 verses of 1,313; "Gr ≈" marks the one where a line was level with no
Hebrew sentence and had to be put with the sentence above it. Before, the badge
meant one Greek line to one Hebrew sentence (696, later 747 verses), which a
Greek sentence wrapped over two lines could never meet and a pairing one
sentence off could.
"""
import html
import json
import os
import re
import collections

from paths import R, MTG

CONS = re.compile('[א-ת]')
FEATORDER = ["sp", "vs", "vt", "ps", "nu", "gn"]
GK = __import__("unicodedata")

CSS = """
:root{--bg:#fbfaf7;--fg:#1a1a1a;--rule:#d8d4cb;--mut:#6b665c;
 --plus:#c8102e;--minus:#1d6fb8;--var:#8a6d1f;--mark:#5b8c5a;--panel:#fff;
 --sup:#7a5ea8}
@media(prefers-color-scheme:dark){:root{--bg:#14150f;--fg:#e8e6df;--rule:#39372f;
 --mut:#9a958a;--plus:#ff8b8b;--minus:#7cb8f0;--var:#dcc07a;--mark:#93c191;
 --panel:#1c1d16;--sup:#b9a2e0}}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--fg);
 font:15px/1.55 "Iowan Old Style",Palatino,Georgia,serif}
header{position:sticky;top:0;background:var(--bg);border-bottom:1px solid var(--rule);
 padding:.7rem 1.2rem;z-index:5}
h1{margin:0;font-size:1.15rem;font-weight:600;letter-spacing:.01em}
h2.oracle{font-size:1rem;font-weight:600;margin:1.6rem 0 .3rem}
.sub{color:var(--mut);font-size:.8rem;margin-top:.15rem}
nav{margin-top:.5rem;font-size:.82rem}
nav a{color:inherit;text-decoration:none;border-bottom:1px solid var(--rule);margin-right:.7rem}
nav a:hover{border-color:var(--fg)}
.toggles{float:right;font-size:.78rem;color:var(--mut)}
.toggles label{margin-left:.9rem;cursor:pointer;user-select:none}
main{padding:1rem 1.2rem 4rem;max-width:1400px}
.v{border-top:1px solid var(--rule);padding:.8rem 0;scroll-margin-top:9rem}
.colhead td{hyphens:auto;overflow-wrap:normal}
@media(max-width:640px){header{position:static}.v{scroll-margin-top:0}}
.vh{display:flex;align-items:baseline;gap:.6rem;margin-bottom:.35rem}
.vn{font-weight:700;font-size:.95rem;min-width:3.2rem}
.badge{font-size:.68rem;letter-spacing:.04em;text-transform:uppercase;
 border:1px solid var(--rule);border-radius:2px;padding:.05rem .35rem;color:var(--mut)}
.badge.ok{color:var(--mark);border-color:var(--mark)}
.badge.no{color:var(--mut);border-style:dashed}
.badge.src{color:var(--mut);border-style:dotted}
/* EVERY VERSE IS ITS OWN TABLE, so the column widths have to be stated rather
   than computed, or each verse sizes its columns to its own content and the
   columns wander from verse to verse down the page. Jer 1,1 was the visible
   case: its Greek is the longest line of the chapter, which widened that column
   and pushed the masoretic column's right edge - and with it the text, which is
   set flush right - away from where every other verse of the chapter had it.
   table-layout:fixed with a colgroup makes all 54 pages align. */
table{width:100%;border-collapse:collapse;table-layout:fixed}
col.mt,col.og{width:30%}
col.cl{width:2.2rem}
col.grk{width:36%}
td{vertical-align:top;padding:.18rem .5rem;overflow-wrap:break-word}
td.heb{direction:rtl;text-align:right;font-size:1.3rem;line-height:1.85;
 font-family:"SBL Hebrew","Ezra SIL","Taamey Frank CLM","Times New Roman",serif}
td.cl{text-align:center;color:var(--mut);font-size:.75rem;padding-top:.6rem}
td.grk{font-size:.98rem;line-height:1.6;color:var(--fg);
 border-left:1px solid var(--rule);padding-left:.8rem;
 font-family:"GFS Didot","New Athena Unicode","Palatino Linotype",Georgia,serif}
td.grk:empty::after{content:"—";color:var(--rule)}
.hide-grk td.grk{display:none}
.hide-grk col.grk{width:0}
.hide-grk col.mt,.hide-grk col.og{width:48%}
.colhead td{font-size:.7rem;letter-spacing:.05em;text-transform:uppercase;
 color:var(--mut);border-bottom:1px solid var(--rule);padding-bottom:.2rem}
tr:hover{background:var(--panel)}
.hl .plus{color:var(--plus)}
.hl .minus{color:var(--minus)}
.hl .mtvar,.hl .ogvar{color:var(--var)}
.mtsup{border-bottom:1px dotted var(--rule)}
.hl .mtsup{color:var(--var);border-bottom:1px dotted var(--var)}
.ogabbr{border-bottom:1px dashed var(--rule)}
.hl .ogabbr{color:var(--var);border-bottom:1px dashed var(--var)}
sup.ab{font-size:.62em;color:var(--mut);vertical-align:super;padding:0 .1em}
.hl .scope{border-bottom:1px dotted var(--mark)}
.notes{font-size:.8rem;color:var(--mut);padding:.1rem .5rem .4rem 1.6rem}
.notes .n{margin-right:.9rem;display:inline-block;max-width:100%}
.notes .n.id{font-weight:600}
.notes .n.foot{display:block;margin:.3rem 0 0;font-style:italic}
.notes .heb{direction:rtl;unicode-bidi:isolate;font-size:1rem;font-style:normal}
.hide-notes .notes{display:none}
.legend{font-size:.75rem;color:var(--mut);margin-top:.5rem}
.legend b{font-weight:400}
.idx{columns:4;column-gap:2rem;font-size:.9rem;margin-top:1rem}
.idx a{display:block;text-decoration:none;color:inherit;padding:.12rem 0}
.idx a:hover{text-decoration:underline}
.kq{font-size:.58em;vertical-align:super;color:var(--mut);
 font-family:Georgia,serif;margin:0 .06em;user-select:none;letter-spacing:0}
#tip .kq2{margin-top:.25rem;font-size:.78rem}
#tip .kq2 b{font-weight:600;font-size:.7rem;color:var(--mut)}
#tip .kq2 span{direction:rtl;unicode-bidi:isolate;
 font-family:"SBL Hebrew","Ezra SIL",serif;font-size:1.05rem}
.w{cursor:help;border-radius:2px}
.w:hover{background:rgba(127,127,127,.22)}
.w.nolink{cursor:default}
#tip{position:fixed;z-index:99;max-width:22rem;display:none;pointer-events:none;
 background:var(--panel);border:1px solid var(--rule);box-shadow:0 2px 10px rgba(0,0,0,.18);
 padding:.5rem .6rem;font-size:.8rem;line-height:1.45;border-radius:3px}
#tip .hw{font-size:1.15rem;direction:rtl;text-align:right;display:block;
 font-family:"SBL Hebrew","Ezra SIL",serif;margin-bottom:.25rem}
#tip .r{white-space:nowrap}
#tip .lx{font-weight:600}
#tip .cd{color:var(--mut);font-size:.72rem}
#tip .gl{color:var(--mut);font-size:.75rem;margin:-.1rem 0 .2rem .2rem}
#tip .hw.gk{direction:ltr;text-align:left;font-family:"GFS Didot","New Athena Unicode",Georgia,serif}
#tip .lx.gk{font-family:"GFS Didot","New Athena Unicode","Palatino Linotype",Georgia,serif}
#tip .src{color:var(--mut);font-size:.68rem;margin-top:.3rem;
 border-top:1px solid var(--rule);padding-top:.25rem;font-style:italic}
.note-b{background:var(--panel);border:1px solid var(--rule);padding:.7rem .9rem;
 font-size:.83rem;color:var(--mut);margin:.8rem 0;line-height:1.5;max-width:60rem}
"""

JS = """
var A=window.__A||[];
var TIP=document.createElement('div');TIP.id='tip';document.body.appendChild(TIP);
var LBL={sp:'',vs:'',vt:'',ps:'',nu:'',gn:''};
function fmt(i,approx){var u=A[i];if(!u)return'';
 var h='<span class="hw'+(u.g?' gk':'')+'">'+u.f+'</span>';
 u.w.forEach(function(w){
  var bits=[];
  ['sp','vs','vt','case','tense','voice','mood','ps','nu','gn','degree']
    .forEach(function(k){if(w[k])bits.push(w[k])});
  h+='<div class="r"><span class="lx'+(u.g?' gk':'')+'">'+(w.vlex||w.lex||'')+'</span> '+
     (w.vlex?'<span class="cd">'+(w.lex||'')+'</span>':'')+
     (bits.length?' &middot; '+bits.join(' &middot; '):'')+'</div>';
  if(w.gloss)h+='<div class="gl">'+w.gloss+'</div>';
  if(w.q)h+='<div class="kq2"><b>K</b> <span>'+w.k+'</span> &nbsp;<b>Q</b> <span>'+w.q+'</span></div>';});
 if(approx)h+='<div class="src">aus dem Formenindex (nicht aus diesem Vers)</div>';
 return h;}
document.addEventListener('mouseover',function(e){
 var t=e.target;if(!t.classList||!t.classList.contains('w'))return;
 var i=t.getAttribute('data-a');if(i===null)return;
 TIP.innerHTML=fmt(+i,t.hasAttribute('data-x'));TIP.style.display='block';
 var r=t.getBoundingClientRect();
 var x=Math.min(r.left,window.innerWidth-TIP.offsetWidth-12);
 var y=r.bottom+6;if(y+TIP.offsetHeight>window.innerHeight)y=r.top-TIP.offsetHeight-6;
 TIP.style.left=Math.max(6,x)+'px';TIP.style.top=Math.max(6,y)+'px';});
document.addEventListener('mouseout',function(e){
 if(e.target.classList&&e.target.classList.contains('w'))TIP.style.display='none';});

function t(k,c){var b=document.body;b.classList.toggle(c);
 try{localStorage.setItem(k,b.classList.contains(c)?'1':'0')}catch(e){}}
['hl','hide-notes','hide-grk'].forEach(function(c){
 try{var v=localStorage.getItem(c);
  if(v==='1')document.body.classList.add(c);
  if(v==='0')document.body.classList.remove(c);}catch(e){}});
document.querySelectorAll('input[data-c]').forEach(function(i){
 var c=i.dataset.c;i.checked=(c==='hl')?document.body.classList.contains(c)
   :!document.body.classList.contains(c);
 i.onchange=function(){t(c,c)};});
"""

CHNAMES = {}


def esc(s):
    return html.escape(s or "")


def sentences(rs):
    """How many SENTENCES a chapter has, counted as Stipp counts them.

    His lettered segments are Saetze - sentences - and not cola; a colon is a
    part of a stichus and Hebrew prose has no stichometry at all. The pages
    have said Satz since 2026-09-09; this function is the count that goes with
    the word, and it was wrong until 2026-09-11 in two ways, both of which
    inflated it.

    A LABEL WITH A SUBSCRIPT INDEX MARKS THE PARTS OF ONE SENTENCE, split by an
    embedded sentence, so the parts count once. The author's instruction, and
    it also confirms the reading this project had to reconstruct: the small
    figure is an index of the Klammerkonstruktion and not a verse number, which
    cost sixty-one verses at 4,23a before it was understood. 252 labels of the
    book carry one - 123 a first part, 122 a second, 7 a third - and they
    inflated 41 of the 53 chapters.

    Twelve verses repeat a letter with NO index. Those are the ones where a
    raised P or D rides on the label and one sentence is set in two pieces, so
    they collapse here too, for the same reason and not by accident.

    AND A RECORD THAT CARRIES NO HEBREW IS NOT A SENTENCE. 180 of the book's
    5,326 hold a marginal note or an apparatus and nothing else. Jer 1 printed
    63 where it has 59; the book printed 5,326 where it has 5,004.
    """
    seen, n = set(), 0
    for r in rs:
        if not any(HEBLET.search(g["text"]) for g in r["mt"]) and            not any(HEBLET.search(g["text"]) for g in r["og"]):
            continue
        base = re.sub(r"\d+$", "", r["clause"] or "")
        if not base:
            n += 1                      # no letter, so it stands on its own
            continue
        if (r["v"], base) not in seen:
            seen.add((r["v"], base))
            n += 1
    return n


HEBLET = re.compile("[א-ת]")


def cons(t):
    return ''.join(CONS.findall(t or '')).replace('שׁ', 'ש').replace('שׂ', 'ש')


def align(words, units):
    """Longest common subsequence on consonantal skeletons.

    Returns one BHSA unit (or None) per word. Order is preserved and nothing is
    matched out of order, so where Stipp's text and BHSA diverge the words in
    between are simply left unmatched instead of being paired with whatever
    happens to be at the same index.
    """
    # A unit matches on either skeleton where the two differ: Stipp prints the
    # ketiv consonants in some ketiv/qere words and the qere consonants in
    # others, and matching on the writing alone loses the second kind.
    return _lcs([cons(w) for w in words],
                [{u["c"], u.get("c2", u["c"])} for u in units], units)


def _lcs(W, U, units):
    n, m = len(W), len(U)
    if not n or not m:
        return [None] * n
    dp = [[0] * (m + 1) for _ in range(n + 1)]
    for i in range(n - 1, -1, -1):
        for j in range(m - 1, -1, -1):
            dp[i][j] = (dp[i + 1][j + 1] + 1) if (W[i] and W[i] in U[j]) \
                else max(dp[i + 1][j], dp[i][j + 1])
    out, i, j = [], 0, 0
    while i < n:
        if j < m and W[i] and W[i] in U[j]:
            out.append(units[j]); i += 1; j += 1
        elif j < m and dp[i + 1][j] >= dp[i][j + 1]:
            out.append(None); i += 1
        elif j < m:
            j += 1
        else:
            out.append(None); i += 1
    return out


class Pool:
    """Per-page store of analyses, so a page carries each one once."""

    def __init__(self):
        self.items, self.idx = [], {}

    def add(self, form, unit, greek=False):
        key = (form, json.dumps(unit["w"], ensure_ascii=False, sort_keys=True))
        if key not in self.idx:
            self.idx[key] = len(self.items)
            e = {"f": form, "w": unit["w"]}
            if greek:
                e["g"] = 1
            self.items.append(e)
        return self.idx[key]


# Which classes may be linked to a BHSA node of this verse. Text COMMON to the
# two editions is the same text, so the alexandrian column may use the verse's
# own analysis for it; a genuine alexandrian reading may not, because it is a
# retroversion of the Greek and BHSA holds nothing about it. Those fall back to
# the form index and are labelled as such in the hover.
VERSE_OK = {"common", "plus", "mtvar", "mtsup", "scope"}
VERSE_OK_OG = {"common", "scope"}


def gnorm(t):
    t = GK.normalize("NFD", (t or "").lower())
    t = ''.join(c for c in t if '\u03b1' <= c <= '\u03c9' or c in '\u03c2\u03f2')
    return t.replace('\u03c2', '\u03c3').replace('\u03f2', '\u03c3')


def greek_html(text, verse_words, pool, form_index):
    """Render the Greek cell, wrapping every word in a hoverable span."""
    if not text:
        return ""
    words = text.split()
    units = [{"c": gnorm(w["f"]), "w": [w]} for w in verse_words]
    matched = align_g(words, units)
    out = []
    for w, u in zip(words, matched):
        src, ap = u, False
        if src is None:
            fi = form_index.get(gnorm(w))
            if fi is not None:
                src, ap = {"c": gnorm(w), "w": [fi]}, True
        if src is None:
            out.append(f'<span class="w nolink">{esc(w)}</span>')
        else:
            i = pool.add(w, src, greek=True)
            out.append(f'<span class="w" data-a="{i}"'
                       f'{" data-x=1" if ap else ""}>{esc(w)}</span>')
    return " ".join(out)


def align_g(words, units):
    return _lcs([gnorm(w) for w in words], [{u["c"]} for u in units], units)


def tokenise(segs):
    """Segments -> [(text, cls, glue, mid)] in logical order.

    glue  no space is printed before this token
    mid   the glue is a segment boundary inside a word, not a maqqef

    Two things are being fixed here at once, and they pull in opposite
    directions. A maqqef binds its two words on the page, so no space is printed
    after it - but BHSA ends a graphical unit at a maqqef, so the two parts must
    stay separate TOKENS or they will not align. A bracket inside a word is the
    reverse: the pieces are separate segments but one word, so they are glued for
    display AND merged for alignment.

    A MAQQEF CAN OPEN A SEGMENT AS WELL AS CLOSE ONE, and until 2026-09-07 the
    pattern here could not match one that did: it demanded a letter before the
    maqqef, so a segment beginning with one had that maqqef silently dropped
    from the page. Stipp brackets the two halves of a maqqef pair separately
    wherever only one half is a plus - KJ / -KH at 4,27, 'T / -SPR at 3,8 - and
    both came out with the maqqef gone and the halves run together as one word.
    A leading maqqef glues its piece to the piece before it for DISPLAY, exactly
    as a trailing one does, and for the same reason does not merge it for
    alignment: BHSA ends a graphical unit at the maqqef whichever side of the
    bracket it is written on.

    THE SOF PASUQ IS THE OTHER SIGN THAT NEVER BEGINS A WORD, and it is here
    for a different reason. Stipp sets his parenthetical apparatus inline, in
    the text column, and the gap around it arrives as a Hebrew span of nothing
    but space - which parse_synopse.py keeps on purpose, since a bare space
    must not consume a backslash's forward reference. That spacing segment
    then stands between the last word of a verse and its sof pasuq, so the two
    are no longer written hard against each other: the page set WE-LO TANUD
    with the sign floating off on its own at Jer 4,1d, and 339 clauses did
    that, 115 in the masoretic column and 224 in the alexandrian. It glues
    like a leading maqqef and, like it, does not merge for alignment - BHSA
    carries the sof pasuq in the trailer of the last word, so it belongs to
    that graphical unit's text but contributes no consonant to match on.
    """
    NOSTART = '\u05be\u05c3'                # maqqef, sof pasuq
    out = []
    for si, seg in enumerate(segs):
        pieces = re.findall(r'\u05be*[^\s\u05be]+\u05be?|\u05be+', seg["text"])
        for k, w in enumerate(pieces):
            maq = w[:1] in NOSTART
            mid = False if k else (bool(seg.get("j")) and bool(out) and not maq)
            glue = mid or maq or bool(out and out[-1][0].endswith('\u05be'))
            out.append((w, seg["cls"], bool(glue), bool(mid)))
    return out


def printed_words(seglists):
    """The masoretic column of one verse as the READER sees it: the list of
    words the page actually sets, glue applied, maqqef split off again.

    The badge on a verse is a test on letters and cannot see spacing at all, so
    a word broken in two - or two run together - passes it. This is the second
    test, on the same column, and it is what the README reports as word-for-word
    agreement. The maqqef is split back out because BHSA ends a graphical unit
    there, so KL-H'RTS is two units in the database and must be two here.
    """
    words = []
    for segs in seglists:
        for w, _cls, glue, _mid in tokenise(segs):
            if words and glue:
                words[-1] += w
            else:
                words.append(w)
    out = []
    for w in words:
        for part in w.split('\u05be'):
            if cons(part):
                out.append(cons(part))
    return out


def spans_html(segs, units, pool, form_index, eligible=VERSE_OK, qere=False):
    """Render one column, wrapping every word in a hoverable span."""
    toks = tokenise(segs)
    if not toks:
        return ""
    # Alignment units: tokens glued mid-word are one word for BHSA, so
    # MISHPEH + O + T is looked up as MISHPEHOT and each of the three pieces
    # gets that analysis. Maqqef glue does NOT merge, because BHSA splits there.
    groups, cur = [], [0]
    for i in range(1, len(toks)):
        if toks[i][3]:
            cur.append(i)
        else:
            groups.append(cur); cur = [i]
    groups.append(cur)
    joined = [''.join(toks[i][0] for i in g) for g in groups]
    gmatch = align(joined, units)
    gmatch = [u if all(toks[i][1] in eligible for i in g) else None
              for u, g in zip(gmatch, groups)]
    per = [None] * len(toks)
    for g, u in zip(groups, gmatch):
        for i in g:
            per[i] = u

    lastof = {}
    for g in groups:
        lastof[g[-1]] = g
    out = []
    for i, (w, cls_, glue, mid) in enumerate(toks):
        src, ap = per[i], False
        if src is None:
            fi = form_index.get(cons(w))
            if fi is not None:
                src, ap = {"c": cons(w), "w": fi}, True
        if src is None:
            span = f'<span class="w nolink {cls_}">{esc(w)}</span>'
        else:
            key = ''.join(toks[j][0] for j in
                          next(g for g in groups if i in g))
            n = pool.add(key, src)
            span = (f'<span class="w {cls_}" data-a="{n}"'
                    f'{" data-x=1" if ap else ""}>{esc(w)}</span>')
        # The K goes after the LAST piece of the display word, so a word split
        # by a bracket - MISHPEH[O]T - is marked once, not three times.
        if qere and i in lastof and src is not None and not ap \
                and any(x.get("q") for x in src["w"]):
            span += '<sup class="kq" title="Ketiv/Qere">K</sup>'
        # (35) THE ABBREVIATED ALEXANDRIAN FORM IS MARKED, NOT COMPLETED.
        # Stipp prints the masoretic word whole and only the tail of the
        # alexandrian one, so what stands here is a fragment. The dagger says
        # so; the letters are not supplied, because the cut is not mechanical
        # and this column has nothing that could check a guess.
        if "ogabbr" in cls_ and i in lastof:
            span += ('<sup class="ab" title="Stipp setzt nur den '
                     'abweichenden Schluss; der gemeinsame Anfang steht '
                     'einmal, in der masoretischen Spalte">†</sup>')
        if out and not glue:
            out.append(' ')
        out.append(span)
    return ''.join(out)


HEB_RUN = re.compile(r"[֐-׿][֐-׿\s]*[֐-׿]|[֐-׿]")


def heb_runs(t):
    """Escape t, isolating each run of Hebrew as right-to-left."""
    out, i = [], 0
    for m in HEB_RUN.finditer(t):
        out.append(esc(t[i:m.start()]))
        out.append(f'<bdi class="heb">{esc(m.group())}</bdi>')
        i = m.end()
    out.append(esc(t[i:]))
    return "".join(out)


def notes_html(notes):
    out = []
    for n in notes:
        t = (n.get("text") or "").strip()
        if not t:
            continue
        # A bare one- to three-digit note is the running page number of the
        # Synopse, which sits in the same column as the apparatus; it is not a
        # note and printing it puts a stray numeral under the first clause of
        # every page.
        if t.isdigit() and len(t) <= 3:
            continue
        if n.get("kind") == "title":
            continue                # set above the verse, not as a note
        heb = any('א' <= c <= 'ת' for c in t)
        latin = any(c.isalpha() and c.isascii() for c in t)
        if n.get("kind") == "id":
            # (55) Stipp's reference to a section of his idiolect study, set in
            # bold in the margin, as he sets it.
            out.append(f'<span class="n id">{esc(t)}</span>')
        elif n.get("kind") == "foot":
            # A FOOTNOTE is German prose with Hebrew and Greek in it: it reads
            # left to right, on a line of its own, and each Hebrew run is
            # isolated so that it does not turn the sentence round it.
            out.append(f'<span class="n foot">{heb_runs(t)}</span>')
        elif heb and latin:
            # A MARGIN LINE can hold a Hebrew lemma and the references after
            # it - 'DBR-JHWH AlT: 5,13b; 9,11c' at 1,1a. Since 2026-10-01 a
            # printed line is one note, so the line is left to right and only
            # the lemma is set right to left; as a whole it would be reversed.
            out.append(f'<span class="n">{heb_runs(t)}</span>')
        else:
            cls = "n heb" if heb else "n"
            out.append(f'<span class="{cls}">{esc(t)}</span>')
    return f'<div class="notes">{"".join(out)}</div>' if out else ""


def page(title, sub, nav, body, legend=True, pool=None):
    leg = ('<div class="legend"><b><span style="color:var(--plus)">masoretisches Plus</span> · '
           '<span style="color:var(--minus)">alexandrinisches Plus</span> · '
           '<span style="color:var(--var)">qualitative Variante</span> · '
           '<span style="border-bottom:1px dotted var(--mark)">markierter Abschnitt</span> · '
           '<span style="border-bottom:1px dotted var(--rule)">aus der '
           'alexandrinischen Form ergänzt, wo Stipp die gemeinsamen '
           'Buchstaben nur einmal setzt</span>'
           ' &nbsp;·&nbsp; <sup class="kq">K</sup> Ketiv/Qere'
           ' &nbsp;·&nbsp; <span style="border-bottom:1px dashed var(--rule)">'
           'alexandrinische Form abgekürzt; der gemeinsame Anfang steht in '
           'der masoretischen Spalte</span><sup class="ab">†</sup>'
           '</b></div>') if legend else ""
    return f"""<!doctype html><html lang="de"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{esc(title)}</title><style>{CSS}</style></head>
<body class="hl">
<header><div class="toggles">
<label><input type="checkbox" data-c="hl"> Varianten farbig</label>
<label><input type="checkbox" data-c="hide-notes"> Apparat</label>
<label><input type="checkbox" data-c="hide-grk"> Griechisch</label>
</div>
<h1>{esc(title)}</h1><div class="sub">{sub}</div>
{f"<nav>{nav}</nav>" if nav else ""}{leg}</header>
<main>{body}</main>
<script>window.__A={json.dumps(pool.items if pool else [], ensure_ascii=False)};</script>
<script>{JS}</script></body></html>"""


# VERSES WHERE STIPP'S OWN TEXT DIFFERS FROM BHS, BY NAME. Each was read
# against a rendered crop of the PDF on 2026-10-01 and confirmed by the author:
# the masoretic column reproduces what Stipp prints, and what he prints is not
# what BHSA has. 'BHSA ?' would say the parser may be wrong, which here it is
# not. Nothing is written into the column; only the badge changes.
SOURCE_DIFFS = {
    "17:26": "Stipp druckt וּלְבוֹנָה מְבִאֵי ohne das Waw von BHS וּמְבִאֵי",
    "23:9": "Stipp druckt כְּגֶבֶר ohne das Waw von BHS וּכְגֶבֶר",
    "25:18": "Stipp druckt וְאֶת־שָׂרֶיהָ, BHS אֶת־שָׂרֶיהָ ohne Waw",
    "18:3": "Ketiv וְהִנֵּהוּ, das BHSA anders kodiert",
    "3:25": "Stipp druckt כִּי לַיהוָה חָטָאנוּ ohne das אֱלֹהֵינוּ von BHS",
}


def build():
    rows = json.load(open(R("synopse.json"), encoding="utf-8"))
    bwords = json.load(open(R("bhsa_jer_words.json"), encoding="utf-8"))
    findex = json.load(open(R("bhsa_form_index.json"), encoding="utf-8"))
    lwords = json.load(open(R("lxx_jer_words.json"), encoding="utf-8"))
    lindex = json.load(open(R("lxx_form_index.json"), encoding="utf-8"))
    ver = json.load(open(R("synopse_check.json"), encoding="utf-8")) \
        if os.path.exists(R("synopse_check.json")) else {}

    groups = collections.OrderedDict()
    for r in rows:
        key = ("2kings25" if r["book"] == "2Kings" else f"jer{r['ch']:02d}")
        groups.setdefault(key, []).append(r)

    keys = [k for k in groups if k.startswith("jer")] + \
           [k for k in groups if not k.startswith("jer")]
    keys.sort(key=lambda k: (0, int(k[3:])) if k.startswith("jer") else (1, 0))

    os.makedirs(MTG(), exist_ok=True)
    written = []
    nsrc = 0
    wl = [0, 0, 0]                      # verses scored, word-exact, spacing-only
    for i, key in enumerate(keys):
        rs = groups[key]
        ch = rs[0]["ch"]
        book = "Jeremia" if rs[0]["book"] == "Jeremiah" else "2 Könige"
        title = f"{book} {ch} — Textkritische Synopse"
        prev = f'<a href="{keys[i-1]}.html">&larr; {keys[i-1]}</a>' if i else ""
        nxt = f'<a href="{keys[i+1]}.html">{keys[i+1]} &rarr;</a>' if i + 1 < len(keys) else ""
        nav = f'<a href="index.html">Übersicht</a>{prev}{nxt}'

        byv = collections.OrderedDict()
        for r in rs:
            byv.setdefault(r["v"], []).append(r)

        body, nok = [], 0
        pool = Pool()
        for v, cls_ in byv.items():
            vkey = f"{ch}:{v}" if book == "Jeremia" else f"K{ch}:{v}"
            vunits = bwords.get(vkey, [])
            # BHSA IS THE CHECK, NOT THE SOURCE. The masoretic column is Stipp's
            # text as extracted and nothing is written into it from the
            # database; the badge only says whether the two agree. A repair that
            # spliced BHSA's words into the column stood here for part of
            # 2026-09-05 and was taken out again: it labelled MN-HKHNJM at 1,1
            # as supplied when Stipp prints it plainly, which is what a repair
            # of this kind will always do to a word the parser has merely
            # misplaced. The fault was in the reading, and that is where it has
            # been fixed.
            ok = ver.get(vkey)
            if ok is False and vkey in SOURCE_DIFFS:
                nsrc += 1
                badge = ('<span class="badge src" title="Die masoretische Spalte '
                         'gibt Stipps Text getreu wieder; Stipp weicht hier selbst '
                         f'von BHS ab: {esc(SOURCE_DIFFS[vkey])}">Stipp ≠ BHS</span>')
            elif ok is True:
                nok += 1
                badge = ('<span class="badge ok" title="masoretische Spalte '
                         'gibt die Konsonanten von BHSA vollständig und in der '
                         'richtigen Reihenfolge wieder">BHSA ✓</span>')
            elif ok is False:
                badge = ('<span class="badge no" title="weicht von BHSA ab; '
                         'siehe Kopfnote">BHSA ?</span>')
            else:
                badge = ""
            pg = cls_[0].get("page")
            gref = cls_[0].get("gref") or ""
            galign = next((c.get("galign") for c in cls_ if c.get("galign")), "")
            gbadge = ('<span class="badge ok" title="Jede griechische Zeile '
                      'steht auf der Höhe des hebräischen Satzes, neben dem sie '
                      'hier steht — aus Stipps Satz abgelesen">Gr ✓</span>'
                      if galign == "exact" else
                      '<span class="badge no" title="Mindestens eine griechische '
                      'Zeile steht auf keiner hebräischen Zeile; sie ist dem Satz '
                      'darüber zugeordnet">Gr ≈</span>'
                      if galign == "approx" else "")
            trs = ['<colgroup><col class="mt"><col class="cl">'
                   '<col class="og"><col class="grk"></colgroup>',
                   '<tr class="colhead"><td>masoretisch</td><td></td>'
                   '<td>hebräische Rückübersetzung (Stipp)</td>'
                   '<td class="grk">Griechisch (Stipp)</td></tr>']
            for c in cls_:
                # A ROW IS SKIPPED ON WHAT IT RENDERS, NOT ON WHAT IT HOLDS. A
                # clause can carry notes that all come to nothing - a bare page
                # number is dropped by notes_html - and testing the record
                # instead of the output left a blank row and a blank note strip
                # under it at the head of Jer 1,1. The test is on the STRIPPED
                # output: spans_html gives back a lone space for a clause whose
                # only segment is Stipp's own spacing, and nine rows of the book
                # are that.
                mt = spans_html(c["mt"], vunits, pool, findex, qere=True)
                og = spans_html(c["og"], vunits, pool, findex, VERSE_OK_OG)
                gk = greek_html(c.get("greek"),
                                lwords.get(c.get("gverse"), []), pool, lindex)
                nt = notes_html(c["notes"]) if c["notes"] else ""
                if mt.strip() or og.strip() or gk.strip():
                    trs.append(
                        f'<tr><td class="heb">{mt}</td>'
                        f'<td class="cl">{esc(c["clause"])}</td>'
                        f'<td class="heb">{og}</td>'
                        f'<td class="grk">{gk}</td></tr>')
                if nt.strip():
                    # A clause can be nothing but a note - nine of them are, at
                    # 2 Kgs 25,1; Jer 27,1; 27,19; 28,1; 40,13; 46,1; 46,10;
                    # 51,41; 52,12 - and then the note stands on its own rather
                    # than under an empty row of three empty columns.
                    trs.append(f'<tr><td colspan="4">{nt}</td></tr>')
            # THE WORD-LEVEL SCORE, alongside the letter-level badge. Same
            # column, same ground truth, different unit: the badge asks whether
            # the consonants are right and in order, this asks whether they are
            # divided into the same words. They came apart badly before
            # 2026-09-07 - a line-break rule that fired inside a line put a
            # space inside 149 verses' worth of words - and nothing in the
            # letter test could see it.
            got = printed_words([c["mt"] for c in cls_])
            want = [u["c"] for u in vunits]
            if want:
                wl[0] += 1
                if got == want:
                    wl[1] += 1
                elif ''.join(got) == ''.join(want):
                    wl[2] += 1
            g = ""
            # (59) the title of an oracle against the nations stands above the
            # verse it opens, as Stipp sets it above the sentence
            for c in cls_:
                for n in c["notes"]:
                    if n.get("kind") == "title":
                        body.append(f'<h2 class="oracle">{esc(n["text"])}</h2>')
            body.append(
                f'<section class="v" id="v{v}"><div class="vh"><span class="vn">'
                f'{ch},{v}</span>{badge}{gbadge}'
                f'{f"<span class=badge>S. {pg}</span>" if pg else ""}'
                f'{f"<span class=badge>{esc(gref)}</span>" if gref else ""}</div>'
                f'<table>{"".join(trs)}</table>{g}</section>')

        sub = (f'Hermann-Josef Stipp, <i>Textkritische Synopse zum Jeremiabuch</i>, '
               f'15. korrigierte interne Auflage, 2021 &nbsp;·&nbsp; '
               f'{len(byv)} Verse, {sentences(rs)} Sätze'
               f' &nbsp;·&nbsp; masoretisch · hebräische Rückübersetzung (Stipp) · griechisch')
        open(MTG(f"{key}.html"), "w", encoding="utf-8").write(
            page(title, sub, nav, "".join(body), pool=pool))
        written.append((key, book, ch, len(byv), nok))

    links = "".join(
        f'<a href="{k}.html">{b} {c} <span style="color:var(--mut)">'
        f'({n} Verse{f", {ok}✓" if ok else ""})</span></a>'
        for k, b, c, n, ok in written)
    total = sum(n for *_, n, _ in written)
    okv = sum(o for *_, o in written)
    n_scored, n_word, n_space = wl
    n_abbr = sum(1 for r in rows if any(g["cls"] == "ogabbr" for g in r["og"]))
    n_sup = sum(1 for r in rows if any(g["cls"] == "mtsup" for g in r["mt"]))

    def de(x):
        return "{:,}".format(x).replace(",", ".")

    def pc(a, b):
        return ("%.1f" % (100.0 * a / max(b, 1))).replace(".", ",")

    # EVERY FIGURE IN THIS NOTE IS COMPUTED HERE. It carried transcribed ones
    # until 2026-09-10 and three of them were wrong: it gave the consonant
    # share as a word share, printed 1.299 where the badge count was 1.365,
    # said a sixth of the verses deviate where it is a fiftieth, and said eight
    # verses were missing when none had been since 2026-09-07.
    nopen = total - okv - nsrc
    # The note follows the count, because a transcribed explanation outlives
    # its facts: this one said for a month that long lines overflowing into the
    # margin were why some verses carry BHSA ?, and since 2026-10-01 none does.
    open_note = (
        'In der masoretischen Spalte trägt kein Vers mehr '
        '<span class="badge no">BHSA ?</span>: jeder gibt BHSA genau wieder '
        'oder weicht nur dort ab, wo Stipp selbst abweicht.'
        if nopen == 0 else
        f'{de(nopen)} Verse tragen <span class="badge no">BHSA ?</span>; dort '
        'fehlen Buchstaben oder steht Text, den BHSA in diesem Vers nicht hat.')
    intro = f"""<div class="note-b">
<b>Was hier steht.</b> Stipps Synopse (<i>Textkritische Synopse zum Jeremiabuch</i>, 15. korrigierte
interne Auflage, 2021) stellt das Jeremiabuch Satz für Satz in
zwei Ausgaben nebeneinander: den tiberischen Text und eine Rückübersetzung der
alexandrinischen Vorlage. Sie ist als PDF in der BibleWorks-Schrift BWHEBB
gesetzt, in der Hebräisch als ASCII in <i>visueller</i> Reihenfolge kodiert ist;
diese Seiten geben denselben Text in Unicode.
<br><br>
<b>Was geprüft ist — und dass nichts hinzugefügt wird.</b> Die masoretische
Spalte ist der BHS-Text; sie allein hat eine Prüfinstanz. Auf Versebene trägt
jeder Vers ein Zeichen: <span class="badge ok">BHSA ✓</span> heißt, dass die
Spalte die Konsonanten von BHSA vollständig und in der richtigen Reihenfolge
wiedergibt — <b>{de(okv)} von {de(total)} Versen ({pc(okv, total)}&nbsp;%)</b>;
<span class="badge no">BHSA ?</span> heißt, dass sie es nicht tut. Nach
graphischen Wörtern gezählt stimmen {pc(n_word, n_scored)}&nbsp;% der Verse Wort
für Wort mit BHSA überein und weitere {pc(n_space, n_scored)}&nbsp;% in allen
Buchstaben, nur nicht in den Wortabständen.
<b>In die Spalte wird nichts aus BHSA geschrieben.</b> Was hier
steht, steht so in der Synopse; BHSA ist die Kontrolle, nicht die Quelle.
<br><br>
<b>Wortinformationen.</b> Jedes hebräische Wort trägt beim Überfahren mit der
Maus seine BHSA-Analyse: <i>lex, sp, vt, vs, ps, nu, gn</i> und das vokalisierte
Lexem. Die Einheit ist das graphische Wort, deshalb zeigt הַדָּבָר zwei Einträge,
הַ als Artikel und דָּבָר als Nomen. In der masoretischen Spalte sind die Wörter
an einen BHSA-Knoten <i>dieses Verses</i> gebunden; in der
alexandrinischen gilt das für den gemeinsamen Text, während eine
eigentliche alexandrinische Lesart keinen Knoten haben kann und, wenn ihre Form
im ganzen Alten Testament eindeutig ist, aus einem Formenindex gedeutet wird —
im Fenster entsprechend gekennzeichnet.
<br><br>
<b>Ketiv/Qere.</b> Wörter mit abweichender Lesart tragen ein hochgestelltes
<sup class="kq">K</sup>; das Fenster nennt beide Formen. BHSA verzeichnet 194
solche Wörter in Jeremia und 2 Könige 25; markiert werden die, die in einem
zugeordneten Wort stehen. Die Markierung steht nur in der masoretischen Spalte,
weil das Qere ein Apparat dieses Textes ist — die alexandrinische Spalte ist eine
Rückübersetzung und kennt keine masoretische Lesetradition.
<br><br>
<b>Wo Stipp abkürzt.</b> Unterscheiden sich die beiden Formen nur im ersten
Buchstaben, druckt er den masoretischen Anfang, den Schrägstrich und das
alexandrinische Wort vollständig: die gemeinsamen Buchstaben stehen einmal, auf
der alexandrinischen Seite. Diese Seiten setzen das masoretische Wort aus seiner
eigenen Vorlage wieder zusammen und unterstreichen die übernommenen Buchstaben
gepunktet — {de(n_sup)} Stellen, jede gegen BHSA geprüft. Unterscheiden sie sich
nur am Ende, kürzt er umgekehrt ab: das masoretische Wort steht ganz, von der
alexandrinischen Form nur der abweichende Schluss. Diese {de(n_abbr)} Stellen
werden <i>nicht</i> ergänzt, sondern gestrichelt unterstrichen und mit einem
<sup class="ab">†</sup> versehen: wo zu schneiden wäre, ist nicht mechanisch zu
bestimmen, und für diese Spalte gibt es keine Prüfinstanz, die eine Vermutung
prüfen könnte.
<br><br>
<b>Wo Stipp selbst von BHS abweicht.</b> {de(nsrc)} Verse tragen
<span class="badge src">Stipp ≠ BHS</span>: die Seite gibt Stipps Druck getreu
wieder, und dieser hat oder entbehrt einen Buchstaben, den BHS anders hat, oder
setzt ein Ketiv, das BHSA anders kodiert. Jeder dieser Verse ist einzeln am PDF
geprüft; der Grund steht im Tooltip des Zeichens.
<br><br>
<b>Was noch nicht stimmt.</b> {open_note} <b>Kein Vers fehlt.</b> Wo nur die Wortabstände abweichen
und alle Buchstaben stimmen, liegt es meist an zusammengesetzten Eigennamen, die
Stipp in zwei Wörtern setzt und BHSA als eines schreibt (בן הנם, עבד מלך, בית
לחם). Die alexandrinische
Spalte ist eine Rückübersetzung und der griechische Text Stipps eigener — für
beide gibt es hier keine Prüfinstanz.
</div>"""
    open(MTG("index.html"), "w", encoding="utf-8").write(page(
        "Textkritische Synopse zum Jeremiabuch",
        f"Hermann-Josef Stipp, 15. korrigierte interne Auflage, 2021 · "
        f"{len(written)} Kapitelseiten · {total} Verse · {okv} gegen BHSA bestätigt "
        f"({okv/max(total,1):.0%})",
        # No nav on the index: it IS the nav. It used to carry a lone link to
        # Jeremia 1, which read as a second, stranger entry beside the Jeremia 1
        # of the chapter list right below it.
        "",
        intro + f'<div class="idx">{links}</div>', legend=False))

    print(f"wrote {len(written)+1} pages to {MTG()}")
    print(f"  verses {total}, masoretic column confirmed against BHSA "
          f"{okv} ({okv/max(total,1):.1%})")
    n, same, sp = wl
    print(f"  counted by word: {same} word for word ({same/max(n,1):.1%}), "
          f"{sp} right to the letter but spaced differently ({sp/max(n,1):.1%}), "
          f"{n-same-sp} differing in the letters ({(n-same-sp)/max(n,1):.1%})")


if __name__ == "__main__":
    build()
