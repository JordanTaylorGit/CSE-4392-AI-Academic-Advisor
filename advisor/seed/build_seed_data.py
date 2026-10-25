#!/usr/bin/env python3
"""
Generate every derived seed file from (catalog PDF + degree_source.py).

    uv run python advisor/seed/build_seed_data.py           # validate + write
    uv run python advisor/seed/build_seed_data.py --check   # validate only

Writes into advisor/seed/:
  course_credits.json  prerequisites.json  requirement_slots.json  programs.json
  extra_courses.json   students.json       schedule.json           catalog_sequences.json
  degree_reqs/bs_cs_cyber.md  degree_reqs/bs_se_ai.md  degree_reqs/major_switch.md
db.py loads these on `python -m advisor.db`.  Never hand-edit the generated files; edit
degree_source.py / catalog_parser.py and re-run.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import catalog_parser as cp
import degree_source as ds

SEED = Path(__file__).resolve().parent
CAT_PDF = SEED / "catalog" / "cse_undergrad_courses.pdf"
CAT_JSONL = SEED / "catalog" / "course-desc.jsonl"
CURRENT_TERM = "F2026"
GRADE_RANK = {"A": 4, "B": 3, "C": 2, "D": 1, "F": 0}


def tord(term: str) -> int:
    m = re.fullmatch(r"(SU|S|F)(\d{4})", term)
    return int(m.group(2)) * 3 + {"S": 0, "SU": 1, "F": 2}[m.group(1)]


# --------------------------------------------------------------------------- data assembly
def load_all():
    jsonl = {}
    for line in CAT_JSONL.read_text(encoding="utf-8").splitlines():
        if line.strip():
            c = json.loads(line)
            jsonl[f"CSE {c['id']}"] = c
    known = set(jsonl) | set(ds.NON_CSE) | {"CSE 4362", "CSE 4363"}
    entries, prereq_rows, professional, report = cp.parse_catalog(CAT_PDF, known)
    credits = {cid: e["credits"] for cid, e in entries.items()}
    credits.update({cid: v[1] for cid, v in ds.NON_CSE.items()})
    return jsonl, entries, prereq_rows, professional, report, credits


def expand_slots(pid: str):
    rows = []
    for s in ds.SLOTS[pid]:
        t = s["type"]
        base = dict(program_id=pid, category=s["cat"])
        if t == "fixed":
            rows.append(dict(base, course_id=s["courses"][0], options=[], credits=s["hours"]))
        elif t == "one_of":
            rows.append(dict(base, course_id=None, options=s["courses"], credits=s["hours"]))
        elif t == "choose_n":
            for _ in range(s["n"]):
                rows.append(dict(base, course_id=None, options=s["courses"], credits=s["hours"] // s["n"]))
        elif t == "category":
            for _ in range(s["hours"] // 3):
                rows.append(dict(base, course_id=None, options=s["courses"], credits=3))
        else:  # free
            rows.append(dict(base, course_id=None, options=[], credits=s["hours"]))
    return rows


# --------------------------------------------------------------------------- schedule
MWF = [("08:00", "08:50"), ("09:00", "09:50"), ("10:00", "10:50"), ("11:00", "11:50"),
       ("12:00", "12:50"), ("13:00", "13:50"), ("14:00", "14:50"), ("15:00", "15:50")]
TR = [("08:00", "09:20"), ("09:30", "10:50"), ("11:00", "12:20"), ("12:30", "13:50"),
      ("14:00", "15:20"), ("15:30", "16:50")]
MTWR4 = [("09:00", "09:50"), ("10:00", "10:50"), ("11:00", "11:50"), ("13:00", "13:50"), ("15:00", "15:50")]
FRI1 = [("09:00", "09:50"), ("10:00", "10:50"), ("13:00", "13:50")]
SUM3 = [("08:30", "10:00"), ("10:00", "11:30"), ("13:00", "14:30"), ("14:30", "16:00")]
SUM4 = [("09:00", "11:00"), ("13:00", "15:00")]


def candidates(course, term, credits):
    if term.startswith("SU"):
        if credits >= 4: return [("MTWR", a, b) for a, b in SUM4]
        if credits <= 1: return [("F", a, b) for a, b in FRI1]
        return [("MTWR", a, b) for a, b in SUM3]
    if credits >= 4: return [("MTWR", a, b) for a, b in MTWR4]
    if credits <= 1: return [("F", a, b) for a, b in FRI1]
    first, second = (("MWF", MWF), ("TR", TR)) if int(course[-1]) % 2 == 0 else (("TR", TR), ("MWF", MWF))
    return [(d, a, b) for d, slots in (first, second) for a, b in slots]


def _days(d):  # 'MTWR' -> {'M','T','W','R'}
    return set(d)


def _mins(t):
    h, m = t.split(":")
    return int(h) * 60 + int(m)


def clash(a, b):  # a,b = (days,start,end)
    return bool(_days(a[0]) & _days(b[0])) and _mins(a[1]) < _mins(b[2]) and _mins(b[1]) < _mins(a[2])


def build_schedule(credits):
    groups = defaultdict(list)       # term -> list of sets of courses that must not clash
    for s in ds.STUDENTS:
        groups[CURRENT_TERM].append(set(s["current"]))
    sections, placed = [], defaultdict(dict)     # placed[term][course] = (days,start,end) of section 001
    for term in (ds.F26, ds.S27, ds.SU27):
        offered = sorted(c for c, terms in ds.OFFERINGS.items() if term in terms)
        pinned = [c for c in offered if any(c in g for g in groups[term])]
        order = pinned + [c for c in offered if c not in pinned]
        cursor = defaultdict(int)
        for course in order:
            cr = credits[course]
            cands = candidates(course, term, cr)
            mates = set().union(*[g for g in groups[term] if course in g]) - {course} if pinned and course in pinned else set()
            start = cursor[cr] % len(cands)
            ordered = cands[start:] + cands[:start]
            pick = next((c for c in ordered if not any(m in placed[term] and clash(c, placed[term][m]) for m in mates)), None)
            if pick is None:
                raise SystemExit(f"cannot place {course} {term} without clash")
            cursor[cr] += 1
            placed[term][course] = pick
            nsec = 2 if course in ds.BIG_COURSES else 1
            cap = 60 if course in ds.BIG_COURSES else (30 if course[-4] == "4" and course.startswith("CSE") else 40)
            if term.startswith("SU"): cap = min(cap, 35)
            secs = [pick] + [c for c in ordered if c != pick][1:2] if nsec == 2 else [pick]
            for i, (d, a, b) in enumerate(secs, start=1):
                sections.append(dict(section_id=f"{course}-{i:03d}-{term}", course_id=course, term=term, days=d,
                                     start_time=a, end_time=b, instructor="Staff", capacity=cap if i == 1 else cap - 15))
    return sections


# --------------------------------------------------------------------------- validation
def validate(credits, prereq_rows, sections):
    errs = []
    known = set(credits)
    # programs
    for p in ds.PROGRAMS:
        rows = expand_slots(p["id"])
        tot = sum(r["credits"] for r in rows)
        if tot != p["total"]:
            errs.append(f"{p['id']}: slots sum to {tot}, expected {p['total']}")
        for r in rows:
            for c in ([r["course_id"]] if r["course_id"] else []) + r["options"]:
                if c not in known:
                    errs.append(f"{p['id']}: unknown course {c}")
        fixed = [r["course_id"] for r in rows if r["course_id"]]
        if len(fixed) != len(set(fixed)):
            errs.append(f"{p['id']}: duplicate fixed course")
    # catalog sequences
    keyhours = {s["key"]: s["hours"] for s in ds.SHARED}
    for name, seq in ds.CATALOG_SEQUENCES.items():
        per = defaultdict(int)
        for y, t, k, h in seq:
            per[(y, t)] += h
        got = [per[(y, t)] for y in range(1, 5) for t in ("Fall", "Spring")]
        if got != ds.CATALOG_TERM_HOURS[name]:
            errs.append(f"{name}: term hours {got} != catalog {ds.CATALOG_TERM_HOURS[name]}")
    # offerings reference known courses
    for c in ds.OFFERINGS:
        if c not in known:
            errs.append(f"OFFERINGS: unknown course {c}")
    # students
    groups = defaultdict(lambda: defaultdict(list))
    for r in prereq_rows:
        groups[r["course_id"]][r["group_id"]].append(r)
    sec_ids = {s["section_id"]: s for s in sections}

    def satisfied(course, term_o, done, current_set):
        for g, alts in groups.get(course, {}).items():
            ok = False
            for a in alts:
                for (c, t, gr) in done:
                    if c == a["prereq_id"] and GRADE_RANK.get(gr, -1) >= GRADE_RANK[a["min_grade"]]:
                        if tord(t) < term_o or (a["concurrent_ok"] and tord(t) <= term_o):
                            ok = True
                if a["concurrent_ok"] and a["prereq_id"] in current_set and term_o >= tord(CURRENT_TERM):
                    ok = True
            if not ok:
                return False
        return True

    for s in ds.STUDENTS:
        done = [(c["course_id"], c["term"], c["grade"]) for c in s["completed"]]
        cur_set = set(s["current"])
        for cid in [c for c, _, _ in done] + s["current"]:
            if cid not in known:
                errs.append(f"{s['student_id']}: unknown course {cid}")
        if len({c for c, _, _ in done}) != len(done):
            errs.append(f"{s['student_id']}: course completed twice")
        for (c, t, g) in done:
            if not satisfied(c, tord(t), [d for d in done if d != (c, t, g)], set()):
                errs.append(f"{s['student_id']}: {c} in {t} has unmet prerequisites")
        for c in s["current"]:
            if not satisfied(c, tord(CURRENT_TERM), done, cur_set - {c}):
                errs.append(f"{s['student_id']}: current {c} has unmet prerequisites")
            if f"{c}-001-{CURRENT_TERM}" not in sec_ids:
                errs.append(f"{s['student_id']}: no {CURRENT_TERM} section for {c}")
        # term loads vs cap
        load = defaultdict(int)
        for c, t, _ in done:
            load[t] += credits[c]
        load[CURRENT_TERM] += sum(credits[c] for c in s["current"])
        for t, h in load.items():
            if h > s["max_credits_per_semester"] + (3 if t.startswith("SU") else 0) and t != "SU2026":
                errs.append(f"{s['student_id']}: {t} load {h} > cap {s['max_credits_per_semester']}")
        # clash-free current schedule
        secs = [sec_ids[f"{c}-001-{CURRENT_TERM}"] for c in s["current"] if f"{c}-001-{CURRENT_TERM}" in sec_ids]
        for i in range(len(secs)):
            for j in range(i + 1, len(secs)):
                a, b = secs[i], secs[j]
                if clash((a["days"], a["start_time"], a["end_time"]), (b["days"], b["start_time"], b["end_time"])):
                    errs.append(f"{s['student_id']}: {a['course_id']} clashes with {b['course_id']}")
    return errs


# --------------------------------------------------------------------------- markdown
_SMALL = {"and", "of", "to", "for", "in", "the", "a", "an", "on"}


def smart_title(t: str) -> str:
    t = t.strip().rstrip(".")
    out = []
    for i, w in enumerate(t.split()):
        lw = w.lower()
        if w in ("I", "II", "III", "IV") or w.startswith("&"):
            out.append(w)
        elif i and lw in _SMALL:
            out.append(lw)
        else:
            out.append("-".join(x[:1].upper() + x[1:].lower() for x in lw.split("-")))
    return " ".join(out)


def cname(cid, titles):
    t = smart_title(titles.get(cid, ""))
    return f"{cid} — {t}" if t else cid


def prereq_text(cid, groups):
    g = groups.get(cid)
    if not g:
        return "none listed"
    parts = []
    for _, alts in sorted(g.items()):
        s = " or ".join(a["prereq_id"] + (" (may be concurrent)" if a["concurrent_ok"] else "") for a in alts)
        parts.append(f"({s})" if len(alts) > 1 else s)
    return " AND ".join(parts) + f" — minimum grade {alts[0]['min_grade']} or better"


def program_md(p, titles, groups, professional):
    pid = p["id"]
    slots = ds.SLOTS[pid]
    cats = [("core", "University core and first-year requirements"),
            ("math_science", "Mathematics and science"),
            ("cse_core", "CSE foundations and professional-program courses"),
            ("concentration", "Certificate courses (the 'concentration')"),
            ("elective", "Technical and open electives")]
    out = [f"# {p['short']}\n\n",
           f"**Program ID:** `{pid}` | **Total degree credits:** {p['total']} | **Catalog year:** {ds.CATALOG_YEAR}\n\n",
           "## Overview\n\n", p["overview"] + "\n\n"]
    for cat, heading in cats:
        ss = [s for s in slots if s["cat"] == cat]
        if not ss:
            continue
        out.append(f"## {heading}\n\n")
        for s in ss:
            h = s["hours"]
            if s["type"] == "fixed":
                c = s["courses"][0]
                out.append(f"- {cname(c, titles)} ({h})"
                           + (" — professional program" if c in professional else "") + "\n")
            elif s["type"] == "one_of":
                out.append(f"- {s['label']}: " + " or ".join(s["courses"]) + f" ({h})\n")
            elif s["type"] == "choose_n":
                out.append(f"- {s['label']}: choose {s['n']} ({h} hrs) from: " +
                           ", ".join(s["courses"]) + "\n")
            elif s["type"] == "category":
                out.append(f"- {s['label']} ({h} hrs) — e.g. " + ", ".join(s["courses"]) + "\n")
            else:
                out.append(f"- {s['label']} ({h} hrs)\n")
            if s["notes"]:
                out.append(f"  - {s['notes']}\n")
        out.append("\n")
    cert_courses = [s["courses"][0] for s in slots if s["cat"] == "concentration"]
    out.append("## Prerequisites for the certificate courses\n\n")
    for c in cert_courses:
        out.append(f"- {c}: {prereq_text(c, groups)}\n")
    out.append("\n## Advising notes\n\n")
    out += [f"- {r}\n" for r in ds.RULES]
    out.append("- Sample courses shown for general-core buckets come from UTA's 2025-26 general core list; "
               "any course on the current approved list counts.\n")
    out.append("- UNCONFIRMED: this plan assumes certificate courses also count toward degree requirements. "
               "Confirm with the CSE undergraduate advisors (cseugadvising@uta.edu).\n\n")
    out.append("## Sources\n\n" + "".join(f"- {u}\n" for u in ds.SOURCES[pid]) +
               f"- General core: {ds.GEN_CORE_SOURCE}\n- Verified {ds.VERIFIED_ON}\n")
    return "".join(out)


def switch_md(titles):
    a, b = "bs_se_ai", "bs_cs_cyber"
    fx = lambda pid: {s["courses"][0] for s in ds.SLOTS[pid] if s["type"] == "fixed"}
    te = lambda pid: {c for s in ds.SLOTS[pid] if s["type"] == "choose_n" and s["cat"] == "elective" for c in s["courses"]}
    out = ["# Switching between BS Software Engineering (AI certificate) and BS Computer Science (Cybersecurity certificate)\n\n",
           "**Program IDs:** `bs_se_ai`, `bs_cs_cyber` | **Catalog year:** " + ds.CATALOG_YEAR + "\n\n",
           "The two degrees share all general-core, math/science and CSE foundation courses, and the catalog's "
           "recommended four-year plans are identical for the first four semesters (first two years), so a switch "
           "after sophomore year loses no first- or second-year credit. Totals: BS SE + AI certificate = 127 hrs; "
           "BS CS + Cybersecurity certificate = 123 hrs.\n\n"]
    for src, dst, title in ((a, b, "From BS SE + AI certificate to BS CS + Cybersecurity certificate"),
                            (b, a, "From BS CS + Cybersecurity certificate to BS SE + AI certificate")):
        out.append(f"## {title}\n\n")
        only = sorted(fx(src) - fx(dst))
        carry = [c for c in only if c in te(dst)]
        lost = [c for c in only if c not in te(dst)]
        need = sorted(fx(dst) - fx(src))
        if carry:
            n_te = sum(1 for r in expand_slots(dst) if r["category"] == "elective" and r["course_id"] is None)
            out.append("- Completed courses that stop being required but can count as technical electives: "
                       + ", ".join(carry) + f" (only {n_te - 1} technical-elective slots plus 1 open elective are "
                       "available, so not all of them can be used).\n")
        if lost:
            out.append("- Completed courses with no matching slot in the new program: " + ", ".join(lost) +
                       " (the new program has no free technical-elective slots because its certificate uses them; "
                       "an advisor may still allow them as open electives).\n")
        out.append("- Newly required courses: " + (", ".join(need) if need else "none") + ".\n")
        if dst == b:
            out.append("- Gains 4 free technical-elective slots and 1 open elective; loses the 4-hr science elective "
                       "(how a completed science elective is credited should be confirmed with an advisor).\n\n")
        else:
            out.append("- Gains the 4-hr science elective; the four technical electives and the open elective are "
                       "replaced by the AI certificate courses, and one AI course is an extra 3 hrs.\n\n")
    out.append("UNCONFIRMED: these comparisons assume certificate courses may double-count toward degree "
               "requirements; confirm with cseugadvising@uta.edu.\n")
    return "".join(out)


# --------------------------------------------------------------------------- main
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true")
    a = ap.parse_args()

    jsonl, entries, prereq_rows, professional, report, credits = load_all()
    sections = build_schedule(credits)
    errs = validate(credits, prereq_rows, sections)
    if errs:
        print("VALIDATION FAILED:", *errs, sep="\n  - ")
        return 1
    print(f"validation OK — {len(entries)} catalog entries, {len(prereq_rows)} prerequisite rows, "
          f"{len(professional)} professional courses, {len(sections)} sections")
    print("programs:", ", ".join(f"{p['id']}={p['total']}h" for p in ds.PROGRAMS))
    if report["dropped"]:
        print("dropped prereq codes (not in courses):", report["dropped"])
    if a.check:
        return 0

    titles = {k: v["title"] for k, v in jsonl.items()}
    titles.update({k: v[0] for k, v in ds.NON_CSE.items()})
    titles.update({k: e["title"] for k, e in entries.items() if k not in titles})
    groups = defaultdict(lambda: defaultdict(list))
    for r in prereq_rows:
        groups[r["course_id"]][r["group_id"]].append(r)

    def dump(name, obj):
        (SEED / name).write_text(json.dumps(obj, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    dump("course_credits.json", {k: v for k, v in sorted(credits.items()) if k.startswith("CSE")})
    dump("prerequisites.json", dict(prerequisites=prereq_rows, professional_courses=professional,
                                    notes=report["notes"]))
    dump("programs.json", [dict(program_id=p["id"], name=p["name"], total_credits=p["total"]) for p in ds.PROGRAMS])
    dump("requirement_slots.json", [r for p in ds.PROGRAMS for r in expand_slots(p["id"])])

    old = {c["course_id"]: c for c in json.loads((SEED / "extra_courses.json").read_text(encoding="utf-8"))} \
        if (SEED / "extra_courses.json").exists() else {}
    extra = []
    for cid, (title, cr) in ds.NON_CSE.items():
        dept, num = cid.split(" ")
        extra.append(dict(course_id=cid, dept=dept, number=num, title=title, credits=cr,
                          description=old.get(cid, {}).get("description", "")))
    for cid in ("CSE 4362", "CSE 4363"):
        e = entries[cid]
        extra.append(dict(course_id=cid, dept="CSE", number=e["number"], title=e["title"].upper(),
                          credits=e["credits"], description=e["description"]))
    dump("extra_courses.json", extra)

    dump("students.json", [dict(student_id=s["student_id"], name=s["name"], program_id=s["program_id"],
                                start_term=s["start_term"], max_credits_per_semester=s["max_credits_per_semester"],
                                completed_courses=s["completed"],
                                current_enrollments=[f"{c}-001-{CURRENT_TERM}" for c in s["current"]],
                                note=s["note"]) for s in ds.STUDENTS])
    dump("schedule.json", sections)

    seqs = {}
    skeys = {s["key"]: s for s in ds.SHARED}
    for name, seq in ds.CATALOG_SEQUENCES.items():
        terms = []
        for y in range(1, 5):
            for t in ("Fall", "Spring"):
                rows = [(k, h) for yy, tt, k, h in seq if (yy, tt) == (y, t)]
                terms.append(dict(year=y, term=t, hours=sum(h for _, h in rows), items=[
                    dict(slot=k, hours=h, courses=skeys[k]["courses"] if k in skeys and skeys[k]["type"] in ("fixed", "one_of") else [])
                    for k, h in rows]))
        seqs[name] = dict(term_hours=ds.CATALOG_TERM_HOURS[name], terms=terms,
                          note="Catalog-verbatim sequence for the plain degree (no certificate). Test fixture only.")
    dump("catalog_sequences.json", seqs)

    prof = set(professional)
    (SEED / "degree_reqs").mkdir(exist_ok=True)
    for p in ds.PROGRAMS:
        (SEED / "degree_reqs" / f"{p['id']}.md").write_text(program_md(p, titles, groups, prof), encoding="utf-8")
    (SEED / "degree_reqs" / "major_switch.md").write_text(switch_md(titles), encoding="utf-8")
    print("wrote seed JSON files + degree_reqs/*.md")
    return 0


if __name__ == "__main__":
    sys.exit(main())
