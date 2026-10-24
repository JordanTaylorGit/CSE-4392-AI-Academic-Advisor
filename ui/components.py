"""Reusable renderers (Person E) for the frozen data contracts:
DegreePlan.to_dict(), CheckResult rows, and compare.diff_plans() output.
Styling lives in ui/theme.py; these functions emit its `adv-*` classes."""

from html import escape

import streamlit as st

from advisor.planner import term_key

SEASONS = {"F": "Fall", "S": "Spring", "SU": "Summer"}

CHECKS = {  # spec §2 req 4, in the spec's own (a)-(f) order
    "prerequisites_met": ("a", "Prerequisites met"),
    "not_already_passed": ("b", "Not already passed"),
    "fulfills_degree_requirement": ("c", "Counts toward the degree"),
    "no_schedule_conflict": ("d", "No schedule conflict"),
    "within_semester_credit_cap": ("e", "Within the semester credit limit"),
    "within_degree_credit_cap": ("f", "Within the degree credit total"),
}

ROMAN = {"I", "II", "III", "IV", "V"}
SMALL = {"and", "of", "the", "to", "for", "in", "a", "an", "on", "with"}


# st.html sanitizes inline SVG away, so icons are text glyphs styled by ui/theme.py.
GLYPH = {"pass": "✓", "fail": "✕", "wait": "–", "info": "i", "caution": "!"}
ICON = {k: f'<i class="ic" aria-hidden="true">{g}</i>' for k, g in GLYPH.items()}

WORDMARK = ('<div class="adv-wordmark"><span class="adv-mark" aria-hidden="true">'
            '<i></i><i></i></span>Advisor</div>')


def course_title(raw: str) -> str:
    """Catalog titles are ALL CAPS; make them readable ('Calculus II', 'Theory of Computation')."""
    words = raw.strip().rstrip(".").split()
    out = []
    for i, w in enumerate(words):
        lw = w.lower()
        if w.upper() in ROMAN:
            out.append(w.upper())
        elif i and lw in SMALL:
            out.append(lw)
        else:
            out.append(lw[:1].upper() + lw[1:])
    return " ".join(out)


def term_label(term: str) -> str:
    season = "SU" if term.startswith("SU") else term[0]
    return f"{SEASONS[season]} {term[len(season):]}"


def _count(n: int) -> str:
    """A number that counts up from 0 on load (CSS only); screen readers get the plain value."""
    return f'<span class="adv-count" style="--n:{int(n)}" aria-hidden="true"></span><span class="adv-sr">{n}</span>'


def _plural(n: int, word: str) -> str:
    return f"{n} {word}{'' if n == 1 else 's'}"


def wordmark() -> None:
    st.html(WORDMARK)


def note(text: str, kind: str = "info") -> None:
    st.html(f'<div class="adv-note {kind}"><span class="ic" aria-hidden="true">{GLYPH[kind]}</span>'
            f'<div>{text}</div></div>')


def preview_banner(source: str) -> None:
    if source == "preview":
        note("<b>Preview data.</b> The planner isn't built yet, so courses are ordered by number "
             "without checking prerequisites, schedules, or requirements. Don't use this in demo "
             "screenshots.", kind="caution")


# --------------------------------------------------------------------- hero

def hero(student: dict, program_line: str, completed: list[dict], plan: dict | None,
         total: int) -> None:
    """Student name, program, and one progress bar toward the degree total."""
    done = sum(r["credits"] for r in completed)
    planned = plan["total_credits_planned"] if plan else 0
    left = max(total - done - planned, 0)
    def pct(n):
        return f"{min(n / total * 100, 100):.2f}%" if total else "0%"
    stats = [f'<span><i class="adv-dot" style="background:var(--green)"></i>'
             f'<b>{_count(done)}</b> of {total} credits completed</span>']
    if plan:
        stats.append(f'<span><i class="adv-dot" style="background:var(--blue)"></i>'
                     f'<b>{_count(planned)}</b> planned</span>')
        if plan["semesters"]:
            stats.append(f'<span>Graduating <b>{term_label(plan["semesters"][-1]["term"])}</b></span>')
    if left:
        stats.append(f'<span><i class="adv-dot ring"></i><b>{_count(left)}</b> still to plan</span>')
    st.html(f"""
      <header class="adv-hero">
        <h1>{escape(student['name'])}</h1>
        <p class="sub">{escape(program_line)}</p>
        <div class="adv-progress" role="img"
             aria-label="{done} of {total} credits completed, {planned} planned">
          <span class="done" style="width:{pct(done)}"></span>
          <span class="planned" style="width:{pct(planned)}"></span>
        </div>
        <div class="adv-stats">{''.join(stats)}</div>
      </header>""")


# -------------------------------------------------------------------- route

def _row(c: dict, grade: str = "") -> str:
    g = f'<span class="adv-grade" aria-label="grade {escape(grade)}">{escape(grade)}</span>' if grade else ""
    return (f'<li class="adv-row"><span class="adv-code">{escape(c["course_id"])}</span>'
            f'<span class="adv-title">{escape(course_title(c["title"]))}</span>'
            f'<span class="adv-meta">{g}{c["credits"]} cr</span></li>')


def _semester(term: str, rows: str, meta: str, done: bool, i: int) -> str:
    return (f'<section class="adv-sem{" done" if done else ""}" style="--i:{i}">'
            f'<div class="adv-sem-head"><span class="adv-sem-title" role="heading" aria-level="3">'
            f'{term_label(term)}</span><span class="adv-sem-meta">{meta}</span></div>'
            f'<ul class="adv-list">{rows}</ul></section>')


def route(plan: dict | None, completed: list[dict], animate: bool = False) -> None:
    """The degree route: completed semesters (solid) then planned ones (ring).
    animate=True lays the semesters out one after another (used right after Build plan)."""
    parts = []
    by_term: dict[str, list[dict]] = {}
    for r in completed:
        by_term.setdefault(r["term"], []).append(r)
    for term, rows in sorted(by_term.items(), key=lambda kv: term_key(kv[0])):
        parts.append(_semester(term, "".join(_row(r, r["grade"]) for r in rows),
                               f'Completed · {sum(r["credits"] for r in rows)} credits', True,
                               len(parts)))
    for sem in (plan or {}).get("semesters", []):
        parts.append(_semester(sem["term"], "".join(_row(c) for c in sem["courses"]),
                               f'{_plural(len(sem["courses"]), "course")} · {sem["credits"]} credits',
                               False, len(parts)))
    if parts:
        st.html(f'<div class="adv-route{" enter" if animate else ""}">{"".join(parts)}</div>')


def plan_warnings(plan: dict) -> None:
    for w in plan.get("warnings", []):
        note(escape(w), kind="caution")


def transcript(completed: list[dict]) -> None:
    if not completed:
        st.html('<p class="adv-muted">No completed courses yet.</p>')
        return
    rows = "".join(f'<tr><td>{escape(r["course_id"])}</td><td>{term_label(r["term"])}</td>'
                   f'<td>{escape(r["grade"])}</td></tr>'
                   for r in sorted(completed, key=lambda r: term_key(r["term"])))
    st.html(f'<table class="adv-mini">{rows}</table>')


def plan_table(plan: dict, title: str) -> str:
    """Compact one-row-per-semester table, returned as HTML for the comparison grid."""
    rows = "".join(
        f'<tr><td>{term_label(s["term"])}</td>'
        f'<td>{escape(", ".join(c["course_id"] for c in s["courses"]))}</td>'
        f'<td>{s["credits"]}</td></tr>' for s in plan["semesters"])
    return (f'<div><h4>{escape(title)}</h4><table class="adv-mini">{rows}</table>'
            f'<p class="adv-muted">{_plural(len(plan["semesters"]), "semester")} · '
            f'{plan["total_credits_planned"]} credits</p></div>')


def compare(old: dict, old_title: str, new: dict, new_title: str) -> None:
    st.html(f'<div class="adv-compare">{plan_table(old, old_title)}{plan_table(new, new_title)}</div>')


# ------------------------------------------------------------------- checks

def checks_table(results: list[dict]) -> None:
    """The six verification checks (spec req 4), with an overall verdict."""
    state = {True: ("pass", "Pass"), False: ("fail", "Fails"), None: ("wait", "Not checked yet")}
    rows = []
    for i, r in enumerate(results):
        letter, label = CHECKS.get(r["name"], ("?", r["name"]))
        cls, word = state[r["passed"]]
        detail = (f'<span class="adv-check-detail">{escape(r["detail"])}</span>'
                  if r.get("detail") else "")
        rows.append(f'<li class="adv-check" style="--i:{i}"><span class="ic {cls}" aria-hidden="true">{GLYPH[cls]}</span>'
                    f'<span class="adv-check-name"><span class="adv-check-letter">({letter})</span>'
                    f'{label}</span><span class="adv-check-state {cls}">{word}</span>{detail}</li>')
    verdict = ""
    if all(r["passed"] is True for r in results):
        verdict = (f'<div class="adv-verdict pass">{ICON["pass"]}All six checks pass. '
                   f'You can take this course.</div>')
    elif any(r["passed"] is False for r in results):
        failed = sum(r["passed"] is False for r in results)
        verdict = (f'<div class="adv-verdict fail">{ICON["fail"]}{_plural(failed, "check")} failed, '
                   f'so the advisor won\'t recommend this course.</div>')
    # Rows appear (a) to (f) in order, then the verdict, as if the checks are running.
    st.html(f'<div class="adv-checks-run"><ul class="adv-list">{"".join(rows)}</ul>{verdict}</div>')


# --------------------------------------------------------------------- diff

def diff_view(diff: dict) -> None:
    """Old-vs-new plan comparison (spec req 5c)."""
    chips = ([f'<span class="adv-chip add">+ {escape(a["course_id"])}</span>' for a in diff["added"]]
             + [f'<span class="adv-chip rem">{escape(r["course_id"])}</span>' for r in diff["removed"]]
             + [f'<span class="adv-chip mov">{escape(m["course_id"])}: {term_label(m["from"])} → '
                f'{term_label(m["to"])}</span>' for m in diff["moved"]])
    sem, cr = diff["semesters_added"], diff["credits_delta"]
    st.html(f"""
      <p>{escape(diff['summary'])}</p>
      <p class="adv-muted">{sem:+d} semesters and {cr:+d} credits compared with the current plan.</p>
      <div class="adv-chips">{''.join(chips) or '<span class="adv-muted">No course changes.</span>'}</div>""")


# -------------------------------------------------------- requirement rings

CATEGORY_LABELS = {"core": "University core", "math_science": "Math & science",
                   "cse_core": "CSE core", "concentration": "Concentration", "elective": "Electives"}


def rings(progress: list[dict]) -> None:
    """One ring per requirement category: green = completed, blue = planned."""
    items = []
    for r in progress:
        req = max(r["required"], 1)
        d = min(r["completed"] / req * 100, 100)
        p = min(r["planned"] / req * 100, 100 - d)
        label = CATEGORY_LABELS.get(r["category"], r["category"].replace("_", " ").title())
        pct = round(d + p)
        items.append(
            f'<figure class="adv-ring-item" role="img" aria-label="{label}: {r["completed"]} of '
            f'{r["required"]} credits completed, {r["planned"]} planned">'
            f'<div class="adv-ring-wrap"><div class="adv-ring" style="--d:{d:.1f};--p:{p:.1f}"></div>'
            f'<span class="adv-ring-pct" aria-hidden="true">{pct}%</span></div>'
            f'<figcaption><b>{label}</b><span>{r["completed"]} done · {r["planned"]} planned '
            f'of {r["required"]}</span></figcaption></figure>')
    st.html(f'<div class="adv-rings">{"".join(items)}</div>')


# ---------------------------------------------------------------- year view

def year_view(plan: dict | None, completed: list[dict]) -> None:
    """The whole degree at a glance: one column per academic year (Fall to Summer)."""
    terms: dict[str, dict] = {}
    for r in completed:
        t = terms.setdefault(r["term"], {"done": True, "courses": []})
        t["courses"].append(r)
    for s in (plan or {}).get("semesters", []):
        terms.setdefault(s["term"], {"done": False, "courses": []})["courses"] += s["courses"]
    if not terms:
        return

    def academic_year(term: str) -> int:  # Fall 2026, Spring 2027, Summer 2027 -> 2026
        year, order = term_key(term)
        return year if order == 2 else year - 1

    years: dict[int, list[str]] = {}
    for t in sorted(terms, key=term_key):
        years.setdefault(academic_year(t), []).append(t)
    cols = []
    for n, (y, ts) in enumerate(sorted(years.items()), start=1):
        blocks = "".join(
            f'<div class="adv-yterm{" done" if terms[t]["done"] else ""}">'
            f'<div class="adv-yterm-head"><span>{term_label(t).split()[0]}</span>'
            f'<span>{sum(c["credits"] for c in terms[t]["courses"])} cr</span></div>'
            f'<div class="adv-ychips">{"".join("<span>{}</span>".format(escape(c["course_id"])) for c in terms[t]["courses"])}</div>'
            f'</div>' for t in ts)
        cols.append(f'<section class="adv-year" style="--i:{n - 1}"><h4>Year {n}</h4>'
                    f'<p class="adv-muted">{y}–{str(y + 1)[2:]}</p>{blocks}</section>')
    st.html(f'<div class="adv-years">{"".join(cols)}</div>')


# --------------------------------------------------------------- chat cards

def chat_card(card: dict) -> None:
    """Rich content inside an advisor reply (the reply format is in ui/README.md)."""
    kind = card.get("type")
    if kind == "plan":
        p = card["plan"]
        sems = p["semesters"]
        rows = "".join(f'<tr><td>{term_label(s["term"])}</td>'
                       f'<td>{escape(", ".join(c["course_id"] for c in s["courses"]))}</td>'
                       f'<td>{s["credits"]}</td></tr>' for s in sems[:3])
        more = f'<p class="adv-muted">and {len(sems) - 3} more semesters</p>' if len(sems) > 3 else ""
        grad = f' · graduating {term_label(sems[-1]["term"])}' if sems else ""
        st.html(f'<div class="adv-chatcard"><div class="adv-chatcard-head"><b>Degree plan</b>'
                f'<span>{_plural(len(sems), "semester")} · {p["total_credits_planned"]} credits{grad}'
                f'</span></div><table class="adv-mini">{rows}</table>{more}</div>')
    elif kind == "courses":
        rows = "".join(
            f'<li class="adv-row"><span class="adv-code">{escape(c["course_id"])}</span>'
            f'<span class="adv-title">{escape(course_title(c["title"]))}'
            + (f'<br><span class="adv-muted">{escape(c["description"][:140])}'
               f'{"…" if len(c["description"]) > 140 else ""}</span>' if c.get("description") else "")
            + f'</span><span class="adv-meta">{c["credits"]} cr</span></li>'
            for c in card["courses"])
        st.html(f'<ul class="adv-list adv-chatcard">{rows}</ul>')
    elif kind == "checks":
        st.html(f'<div class="adv-chatcard-head"><b>{escape(card["course_id"])}</b>'
                f'<span>{term_label(card["term"])}</span></div>')
        checks_table(card["checks"])
    elif kind == "diff":
        st.html(f'<div class="adv-chatcard">{plan_table(card["old"], "Now")}'
                f'{plan_table(card["new"], "After switching")}</div>')
        diff_view(card["diff"])


# ------------------------------------------------------------------- traces

TRACE_HIDDEN = {"ts", "event", "session", "student_id"}
SOURCE_LABEL = {"live": "Live", "preview": "Preview", "not_ready": "Not built"}


def _local_time(ts: str) -> str:
    from datetime import datetime
    return datetime.fromisoformat(ts).astimezone().strftime("%b %d, %H:%M:%S")


def _fields(r: dict) -> str:
    parts = []
    for k, v in r.items():
        if k in TRACE_HIDDEN or v in (None, "", []):
            continue
        text = ", ".join(map(str, v)) if isinstance(v, list) else str(v)
        text = text if len(text) <= 160 else text[:160] + "…"
        parts.append(f'<span><i>{escape(k.replace("_", " "))}</i> {escape(text)}</span>')
    return "".join(parts)


def _source(r: dict) -> str:
    s = r.get("source")
    return f'<span class="adv-src {escape(s)}">{SOURCE_LABEL.get(s, escape(s))}</span>' if s else ""


def trace_summary(groups: list[dict], duration_ms) -> None:
    turns = [g for g in groups if g["kind"] == "turn"]
    actions = len(groups) - len(turns)
    events = sum(len(g["events"]) for g in groups)
    avg = (f'{sum(duration_ms(g) for g in turns) // len(turns)} ms' if turns else "—")
    st.html(f'<div class="adv-stats adv-trace-stats"><span><b>{len(turns)}</b> chat turns</span>'
            f'<span><b>{actions}</b> actions</span><span><b>{events}</b> events</span>'
            f'<span>Average turn <b>{avg}</b></span></div>')


def trace_list(groups: list[dict], names: dict[str, str], duration_ms) -> None:
    """Newest first: chat turns as step-by-step cards, UI actions as compact rows."""
    items = []
    for g in reversed(groups):
        who = escape(names.get(g["student_id"], g["student_id"] or "unknown"))
        when = _local_time(g["start"])
        if g["kind"] == "turn":
            steps = "".join(
                f'<li><span class="adv-ev">{escape(r["event"].replace("_", " "))}</span>'
                f'<span class="adv-kv">{_source(r)}{_fields(r)}</span></li>' for r in g["events"])
            intent = (f'<span class="adv-src intent">{escape(str(g["intent"]).replace("_", " "))}</span>'
                      if g["intent"] else "")
            pending = "" if g["reply"] is not None else '<span class="adv-src not_ready">No reply logged</span>'
            items.append(
                f'<article class="adv-trace"><header><span class="adv-trace-kind">Chat turn</span>'
                f'{intent}{pending}<span class="adv-trace-meta">{who} · {when} · {duration_ms(g)} ms</span>'
                f'</header><p class="adv-trace-q">{escape(g["message"])}</p>'
                f'<ol class="adv-trace-steps">{steps}</ol></article>')
        else:
            r = g["events"][0]
            name = r.get("action") or r["event"]
            items.append(
                f'<article class="adv-trace action"><header><span class="adv-trace-kind">'
                f'{escape(name.replace("_", " ").capitalize())}</span>{_source(r)}'
                f'<span class="adv-trace-meta">{who} · {when}</span></header>'
                f'<div class="adv-kv">{_fields(r)}</div></article>')
    st.html(f'<div class="adv-traces">{"".join(items)}</div>')
