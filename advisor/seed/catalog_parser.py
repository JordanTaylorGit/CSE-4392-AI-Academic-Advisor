"""
Parse seed/catalog/cse_undergrad_courses.pdf into structured data.

Produces, per CSE course:
  credits               -- from the "N Hours." in the entry header
  professional          -- prereq text requires admission to an Engineering Professional Program
  prereqs               -- rows (group_id, prereq_id, min_grade, concurrent_ok)
                           same group_id = OR alternatives, different group_id = AND
  notes                 -- prerequisite conditions we could NOT represent (consent, ALEKS, ...)

Grammar handled: "C or better in A, B or C, and D", "(X or Y)", "X (or Y)", "either X or Y",
"(or concurrently)", "(or concurrent enrollment in ...)", "Co-requisite: X", "or consent of instructor".
A few entries are too irregular for the grammar (CSE 1310/1311/1320 placement-test clauses, CSE 4316's
per-plan branches); they are hand-written in OVERRIDES and flagged in `notes`.
"""
from __future__ import annotations

import re

from pypdf import PdfReader

ENTRY_RE = re.compile(r"^CSE (\d{4})\. ", re.MULTILINE)
CODE_RE = r"[A-Z]{2,5}(?:-[A-Z]{2})? \d{4}"
TOKEN_RE = re.compile(rf"@G_[A-D]|@CONCPREV|@CONCNEXT|{CODE_RE}|\bor\b|\band\b|[(),]")

# Catalog says "completed with a C or better" only sometimes; when no grade is stated the
# literal catalog rule is "any passing grade". Professional-program courses always need C
# (catalog: all prerequisites for professional courses must be completed with a C or better).
UNSTATED_GRADE = "D"
PROFESSIONAL_GRADE = "C"

_MATH_ENTRY = ["MATH 1426", "MATH 2425", "MATH 2326", "MATH 3330"]

OVERRIDES = {
    # catalog: C or better in MATH 1302/1402, or (concurrently) a subsequent math course, or an ALEKS score
    "CSE 1310": dict(groups=[(_MATH_ENTRY, "C", True)],
                     notes="Catalog also accepts MATH 1302/1402/1421, HONR-SC math, or a qualifying ALEKS PPL score "
                           "(with UNIV 1131 or ENGR 1101); only the in-degree math courses are modelled."),
    "CSE 1311": dict(groups=[(_MATH_ENTRY, "C", True)],
                     notes="Catalog also accepts MATH 1421 and HONR-SC math courses."),
    "CSE 1320": dict(groups=[(["CSE 1310"], "C", False), (_MATH_ENTRY, "C", True)],
                     notes="Catalog also accepts MATH 1421, HONR-SC math, or a qualifying ALEKS PPL score "
                           "(with UNIV 1131 or ENGR 1101)."),
    # catalog gives separate branches for academic plans CS/SE vs CSE CP; we model CS/SE
    "CSE 4316": dict(groups=[(["CSE 3310"], "C", False), (["CSE 3320"], "C", False), (["CSE 3314"], "C", True)],
                     professional=True,
                     notes="Modelled for academic plans CS and SE (the Computer Engineering branch differs)."),
}

# Non-CSE prerequisite chains the catalog PDF does not contain. UNVERIFIED: inferred from the order of the
# catalog's 4-year plans. Needed so the planner does not schedule Calculus III in semester one.
ASSUMED_NON_CSE_PREREQS = [
    ("MATH 2425", 1, "MATH 1426", "C", False),
    ("MATH 2326", 1, "MATH 2425", "C", False),
    ("PHYS 1444", 1, "PHYS 1443", "C", False),
]


def load_entries(pdf_path) -> dict[str, dict]:
    text = "\n".join(p.extract_text() for p in PdfReader(str(pdf_path)).pages)
    text = re.sub(r"^\s*\d{1,2}\s*$", "", text, flags=re.MULTILINE)          # lone page numbers
    starts = [(m.start(), m.group(1)) for m in ENTRY_RE.finditer(text)]
    out = {}
    for i, (s, num) in enumerate(starts):
        e = starts[i + 1][0] if i + 1 < len(starts) else len(text)
        body = " ".join(text[s:e].split())
        m = re.search(r"(\d+) Hours?\.", body)
        title = body[len(f"CSE {num}. "):m.start()].rstrip(". ").strip() if m else ""
        # description = everything between the header (incl. optional TCCN note) and "Prerequisite"
        rest = body[m.end():] if m else body
        rest = re.sub(r"^\s*\(TCCN[^)]*\)\s*", "", rest)
        pm = re.search(r"Pre-?requisites?:|Co-?requisites?:", rest)
        desc = (rest[:pm.start()] if pm else rest).strip()
        out[f"CSE {num}"] = dict(number=num, title=title, credits=int(m.group(1)) if m else None,
                                 description=desc, prereq_text=rest[pm.start():].strip() if pm else "")
    return out


def _tokenize(txt: str):
    txt = re.sub(r"\(\s*or concurrently\s*\)", " @CONCPREV ", txt)
    txt = re.sub(r"\(?\s*or concurrent enrollment in\s*\)?", " @CONCNEXT ", txt)
    txt = re.sub(r"\b(?:or\s+)?consent of (?:the )?(?:instructor|advisor)(?: and department chairperson)?", " ", txt)
    return TOKEN_RE.findall(txt)


def _parse_tokens(tokens):
    """-> list of elements; element = list of (code, grade, concurrent)."""
    elements, cur, join = [], None, None
    grade, pend = None, False
    for t in tokens:
        if t.startswith("@G_"):
            grade = t[-1]
        elif t == "@CONCNEXT":
            pend = True
        elif t == "@CONCPREV":
            if cur:
                c, g, _ = cur[-1]
                cur[-1] = (c, g, True)
        elif t == "or":
            join = "or"
        elif t in ("and", ","):
            join = "and"
        elif t in ("(", ")"):
            continue
        else:  # a course code
            alt = (t, grade, pend)
            pend = False
            if cur is not None and join == "or":
                cur.append(alt)
            else:
                cur = [alt]
                elements.append(cur)
            join = None
    return elements


def parse_prereq_text(text: str):
    """-> (professional: bool, elements, notes: list[str])"""
    if re.search(r"Co-?requisites?:", text):          # co-requisite = may be taken in the same term
        main, co = re.split(r"Co-?requisites?:", text, maxsplit=1)
        prof, el1, n1 = parse_prereq_text(main)
        _, el2, n2 = parse_prereq_text(co)
        el2 = [[(c, g, True) for c, g, _ in el] for el in el2]
        return prof, el1 + el2, n1 + n2
    notes = []
    professional = bool(re.search(r"Professional Program|professional engineering", text, re.IGNORECASE))
    t = re.sub(r"Pre-?requisites?:|Co-?requisites?:", " ", text)
    # admission sentences
    t = re.sub(r"Admitted into an? (?:Engineering|CSE) Professional Program\.?", " ", t)
    t = re.sub(r"Admission to a professional engineering or science program\.?", " ", t)
    t = re.sub(r"and admission to the UVS certificate program\.?", " ", t)
    if "UVS certificate" in text:
        notes.append("Also requires admission to the UVS certificate program (not modelled).")
    if re.search(r"consent of (?:the )?(?:instructor|advisor)", text):
        notes.append("Consent of instructor/advisor may be required.")
    if "good standing" in text:
        notes.append("Requires departmental good standing and permission of instructor.")
    t = re.sub(r"\b(?:Grade )?([A-D]) or better(?: in)?", lambda m: f" @G_{m.group(1)} ", t, flags=re.IGNORECASE)
    return professional, _parse_tokens(_tokenize(t)), notes


def parse_catalog(pdf_path, known_courses: set[str]):
    """Return (courses, prereq_rows, professional_ids, report).

    prereq_rows: dicts(course_id, group_id, prereq_id, min_grade, concurrent_ok, source)
    Codes not in `known_courses` are dropped (prerequisites.prereq_id has an FK to courses) and reported.
    """
    entries = load_entries(pdf_path)
    rows, professional, report = [], [], dict(dropped=[], notes={}, overridden=[])
    for cid, e in entries.items():
        spec = OVERRIDES.get(cid)
        if spec:
            prof = spec.get("professional", False) or bool(re.search(r"Professional Program", e["prereq_text"]))
            groups = [(alts, g, conc) for alts, g, conc in spec["groups"]]
            report["overridden"].append(cid)
            report["notes"].setdefault(cid, []).append(spec["notes"])
            parsed = [([(a, g, c) for a in alts]) for alts, g, c in groups]
            elements = parsed
            notes = []
        else:
            prof, elements, notes = parse_prereq_text(e["prereq_text"]) if e["prereq_text"] else (False, [], [])
        if notes:
            report["notes"].setdefault(cid, []).extend(notes)
        if prof:
            professional.append(cid)
        gno = 0
        for el in elements:
            kept = []
            for code, g, conc in el:
                if code not in known_courses:
                    report["dropped"].append((cid, code))
                    continue
                kept.append((code, g, conc))
            if not kept:
                continue
            gno += 1
            for code, g, conc in kept:
                grade = g or (PROFESSIONAL_GRADE if prof else UNSTATED_GRADE)
                if prof and grade in ("D",):
                    grade = PROFESSIONAL_GRADE
                rows.append(dict(course_id=cid, group_id=gno, prereq_id=code, min_grade=grade,
                                 concurrent_ok=bool(conc), source="catalog"))
    for cid, gno, pre, grade, conc in ASSUMED_NON_CSE_PREREQS:
        rows.append(dict(course_id=cid, group_id=gno, prereq_id=pre, min_grade=grade,
                         concurrent_ok=conc, source="assumed"))
    return entries, rows, sorted(set(professional)), report
