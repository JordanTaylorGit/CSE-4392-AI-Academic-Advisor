"""Build the final presentation deck (Person E, deliverable).

    uv run --with python-pptx python scripts/build_slides.py
    uv run --with python-pptx python scripts/build_slides.py --shots /path/to/screenshots

Writes deliverables/AI_Advisor_Presentation.pptx: architecture, components and
their inputs/outputs, design decisions, code segments, and the demo screenshots
from scripts/take_screenshots.py, with speaker notes on every slide. Re-run it
after taking the final screenshots; edit the text in SLIDES-building code below
or in PowerPoint afterwards. python-pptx is not a project dependency.
"""

import argparse
from pathlib import Path

from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.enum.shapes import MSO_CONNECTOR, MSO_SHAPE
from pptx.enum.text import MSO_ANCHOR, PP_ALIGN
from pptx.oxml.ns import qn
from pptx.util import Emu, Inches, Pt

REPO_ROOT = Path(__file__).resolve().parent.parent

# Same palette as the app (ui/theme.py, light mode).
INK = RGBColor(0x1D, 0x1D, 0x1F)
MUTED = RGBColor(0x6E, 0x6E, 0x73)
BLUE = RGBColor(0x00, 0x71, 0xE3)
GREEN = RGBColor(0x1E, 0x7B, 0x34)
AMBER = RGBColor(0xB2, 0x50, 0x00)
SURFACE = RGBColor(0xF5, 0xF5, 0xF7)
LINE = RGBColor(0xD2, 0xD2, 0xD7)
WHITE = RGBColor(0xFF, 0xFF, 0xFF)
BLUE_TINT = RGBColor(0xE8, 0xF1, 0xFC)
GREEN_TINT = RGBColor(0xE8, 0xF5, 0xEC)
AMBER_TINT = RGBColor(0xFD, 0xF0, 0xE4)

SANS = "Arial"      # present on every Windows/Mac PowerPoint
MONO = "Consolas"   # ships with Office on both

W, H = Inches(13.333), Inches(7.5)
MARGIN = Inches(0.7)


# ------------------------------------------------------------------ helpers

def text(slide, x, y, w, h, runs, size=18, color=INK, bold=False, font=SANS,
         align=PP_ALIGN.LEFT, anchor=MSO_ANCHOR.TOP, spacing=1.15):
    """A text box. `runs` is a string, or a list of paragraphs; a paragraph is a
    string or a list of (text, {bold, color, size}) pieces."""
    box = slide.shapes.add_textbox(x, y, w, h)
    tf = box.text_frame
    tf.word_wrap = True
    tf.vertical_anchor = anchor
    for side in ("margin_left", "margin_right", "margin_top", "margin_bottom"):
        setattr(tf, side, 0)
    paras = runs if isinstance(runs, list) else [runs]
    for i, para in enumerate(paras):
        p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        p.alignment = align
        p.line_spacing = spacing
        pieces = para if isinstance(para, list) else [(para, {})]
        for piece, style in pieces:
            r = p.add_run()
            r.text = piece
            r.font.name = style.get("font", font)
            r.font.size = Pt(style.get("size", size))
            r.font.bold = style.get("bold", bold)
            r.font.color.rgb = style.get("color", color)
    return box


def rect(slide, x, y, w, h, fill=SURFACE, line=None, radius=0.08, shape=MSO_SHAPE.ROUNDED_RECTANGLE):
    s = slide.shapes.add_shape(shape, x, y, w, h)
    s.shadow.inherit = False
    if shape == MSO_SHAPE.ROUNDED_RECTANGLE:
        s.adjustments[0] = radius
    s.fill.solid()
    s.fill.fore_color.rgb = fill
    if line is None:
        s.line.fill.background()
    else:
        s.line.color.rgb = line
        s.line.width = Pt(1)
    s.text_frame.text = ""
    return s


def label_box(slide, x, y, w, h, title, sub="", fill=WHITE, line=LINE, title_color=INK, size=14):
    rect(slide, x, y, w, h, fill=fill, line=line, radius=0.12)
    paras = [[(title, {"bold": True, "color": title_color, "size": size})]]
    if sub:
        paras.append([(sub, {"color": MUTED, "size": size - 3})])
    text(slide, x + Inches(0.12), y, w - Inches(0.24), h, paras, align=PP_ALIGN.CENTER,
         anchor=MSO_ANCHOR.MIDDLE, spacing=1.05)


def arrow(slide, x1, y1, x2, y2, color=MUTED):
    c = slide.shapes.add_connector(MSO_CONNECTOR.STRAIGHT, x1, y1, x2, y2)
    c.line.color.rgb = color
    c.line.width = Pt(1.5)
    ln = c.line._get_or_add_ln()
    tail = ln.makeelement(qn("a:tailEnd"), {"type": "triangle", "w": "med", "len": "med"})
    ln.append(tail)
    return c


def plain(slide, x1, y1, x2, y2, color=MUTED):
    c = slide.shapes.add_connector(MSO_CONNECTOR.STRAIGHT, x1, y1, x2, y2)
    c.line.color.rgb = color
    c.line.width = Pt(1.5)
    return c


def header(slide, title, takeaway=""):
    text(slide, MARGIN, Inches(0.55), W - 2 * MARGIN, Inches(0.7), title, size=32, bold=True)
    if takeaway:
        text(slide, MARGIN, Inches(1.25), W - 2 * MARGIN, Inches(0.5), takeaway, size=16, color=MUTED)


def footer(slide, n):
    text(slide, W - MARGIN - Inches(3), H - Inches(0.45), Inches(3), Inches(0.3),
         f"Academic AI Advisor  ·  {n}", size=10, color=MUTED, align=PP_ALIGN.RIGHT)


def notes(slide, body):
    slide.notes_slide.notes_text_frame.text = body.strip()


def table(slide, x, y, w, rows, col_w, size=13, row_h=0.42, head_fill=SURFACE):
    """Simple ruled table built from text boxes (keeps full control of the look)."""
    cy = y
    for r, row in enumerate(rows):
        hgt = Inches(row_h)
        if r == 0:
            rect(slide, x, cy, w, hgt, fill=head_fill, radius=0.15)
        cx = x
        for c, cell in enumerate(row):
            cw = Inches(col_w[c])
            text(slide, cx + Inches(0.12), cy, cw - Inches(0.2), hgt, cell, size=size,
                 bold=(r == 0), color=INK if r else MUTED, anchor=MSO_ANCHOR.MIDDLE, spacing=1.0)
            cx += cw
        cy += hgt
        if r:
            ln = slide.shapes.add_connector(MSO_CONNECTOR.STRAIGHT, x, cy, x + w, cy)
            ln.line.color.rgb = LINE
            ln.line.width = Pt(0.75)
    return cy


def picture(slide, path: Path, x, y, w, h, crop=(0.0, 0.0, 0.0), border=True):
    """Fit a screenshot into the box. crop = (left, top, right) fractions to trim the
    app's empty side margins and start at the part that matters; the bottom is then
    cropped to fit the box."""
    if not path.exists():
        rect(slide, x, y, w, h, fill=AMBER_TINT)
        text(slide, x, y, w, h, f"Missing screenshot: {path.name}\nRun scripts/take_screenshots.py",
             size=14, color=AMBER, align=PP_ALIGN.CENTER, anchor=MSO_ANCHOR.MIDDLE)
        return
    pic = slide.shapes.add_picture(str(path), x, y)
    nat_w, nat_h = pic.image.size
    left, top, right = crop
    scale = w / (nat_w * (1 - left - right))          # EMU per source pixel
    shown_h = min(nat_h * (1 - top), h / scale)       # source pixels that fit
    pic.crop_left, pic.crop_right, pic.crop_top = left, right, top
    pic.crop_bottom = max(0.0, 1 - top - shown_h / nat_h)
    pic.left, pic.width = x, w
    pic.height = int(shown_h * scale)
    pic.top = int(y + (h - pic.height) / 2) if pic.height < h else y
    if border:
        pic.line.color.rgb = LINE
        pic.line.width = Pt(0.75)


def code(slide, x, y, w, h, source: str, size=12):
    rect(slide, x, y, w, h, fill=SURFACE, radius=0.04)
    text(slide, x + Inches(0.25), y + Inches(0.2), w - Inches(0.5), h - Inches(0.4),
         source.strip("\n").split("\n"), size=size, font=MONO, spacing=1.08)


def bullets(slide, x, y, w, h, items, size=16, gap=0.12):
    paras = []
    for item in items:
        if isinstance(item, tuple):  # (bold lead, rest)
            paras.append([(item[0], {"bold": True}), (item[1], {})])
        else:
            paras.append(item)
    box = text(slide, x, y, w, h, paras, size=size, spacing=1.2)
    for p in box.text_frame.paragraphs:
        p.space_after = Pt(size * gap * 4)
    return box


# ------------------------------------------------------------------- slides

def build(shots: Path, out: Path) -> None:
    prs = Presentation()
    prs.slide_width, prs.slide_height = W, H
    blank = prs.slide_layouts[6]
    n = 0

    def new():
        nonlocal n
        n += 1
        s = prs.slides.add_slide(blank)
        s.background.fill.solid()
        s.background.fill.fore_color.rgb = WHITE
        if n > 1:
            footer(s, n)
        return s

    # 1. Title
    s = new()
    rect(s, 0, 0, W, H, fill=SURFACE, shape=MSO_SHAPE.RECTANGLE)
    dot_y = Inches(2.35)
    rect(s, MARGIN, dot_y, Inches(0.28), Inches(0.28), fill=GREEN, shape=MSO_SHAPE.OVAL)
    o = rect(s, MARGIN, dot_y + Inches(0.38), Inches(0.28), Inches(0.28), fill=SURFACE, shape=MSO_SHAPE.OVAL)
    o.line.color.rgb = BLUE
    o.line.width = Pt(3.5)
    text(s, MARGIN + Inches(0.55), Inches(2.1), Inches(11), Inches(1.2), "Academic AI Advisor",
         size=54, bold=True)
    text(s, MARGIN + Inches(0.55), Inches(3.2), Inches(11), Inches(0.6),
         "Degree plans, course checks, and answers about UTA CSE, built on LangChain",
         size=22, color=MUTED)
    text(s, MARGIN + Inches(0.55), Inches(4.6), Inches(11), Inches(1.2), [
        "CSE 4392  ·  Team Assignment 2  ·  October 2026",
        "Jordan (data)  ·  Loc (planner)  ·  Miguel (RAG)  ·  Kyle (agent)  ·  Talha (UI, logging, demo)"],
        size=16, color=MUTED, spacing=1.5)
    notes(s, """
Presenter: Talha. 30 seconds.
"We built an academic advisor for UTA CSE students. It plans a degree semester by semester,
checks whether a course can be taken, answers questions from the catalog, and keeps a full
trace of how it reached every answer. Each of us owned one layer; we'll walk the architecture,
show the code that matters, then the demo."
""")

    # 2. What it does
    s = new()
    header(s, "What the advisor does", "Every requirement in the assignment, and where it lives in the system.")
    table(s, MARGIN, Inches(2.0), W - 2 * MARGIN, [
        ["Requirement", "How we meet it", "Shown in demo"],
        ["1  User interface", "Streamlit web app: chat, plan timeline, dialogs for add / drop", "Every screen"],
        ["2  Multi-year degree plan", "Deterministic planner orders the prerequisite graph into semesters", "Plan → Build plan"],
        ["3  Exact and semantic queries", "Intent router sends facts to SQL, open questions to RAG", "Ask: prereqs, ML courses"],
        ["4  Six checks before recommending", "Verification engine returns checks (a)–(f) with reasons", "Check a course"],
        ["5  Change plan, switch major, compare", "Add / drop with undo; new plan side by side with a diff", "Plan, Switch major"],
        ["6  Conversation state", "Session history passed into every turn; chat history in SQLite", "Follow-up question"],
        ["7–8  Structural + unstructured data, two DBMSs", "SQLite for records, Chroma for catalog text and degree docs", "Architecture"],
    ], [3.4, 6.4, 2.13], size=14, row_h=0.56)
    notes(s, """
Presenter: Talha. 1 minute.
Walk the table top to bottom. Point out that every requirement maps to a specific component
and a specific demo moment, so the rest of the talk follows this table.
""")

    # 3. Architecture
    s = new()
    header(s, "Architecture", "One entry point, one router, specialised handlers, two databases, and a trace of every step.")
    bx = lambda col: MARGIN + Inches(col)
    label_box(s, bx(0), Inches(2.0), Inches(2.2), Inches(0.8), "Student", "signed in (given)")
    label_box(s, bx(3.0), Inches(2.0), Inches(3.2), Inches(0.8), "Streamlit UI", "app.py, ui/  ·  Talha",
              fill=BLUE_TINT, line=BLUE)
    label_box(s, bx(7.0), Inches(2.0), Inches(4.9), Inches(0.8), "Orchestrator",
              "memory + intent router (keywords → small LLM)  ·  Kyle", fill=BLUE_TINT, line=BLUE)
    arrow(s, bx(2.2), Inches(2.4), bx(3.0), Inches(2.4))
    arrow(s, bx(6.2), Inches(2.4), bx(7.0), Inches(2.4))
    # Handlers, ordered so each sits above the store it reads.
    handlers = [("Exact query chain", "SQL lookups  ·  Kyle"), ("Degree planner", "plan + six checks  ·  Loc"),
                ("Plan compare", "diff of two plans  ·  Loc"), ("RAG chain", "Chroma + LLM  ·  Miguel"),
                ("General chat", "LLM fallback  ·  Kyle")]
    hw, hg = Inches(2.22), Inches(0.2)
    centers = [MARGIN + i * (hw + hg) + hw // 2 for i in range(len(handlers))]
    bus = Inches(3.2)
    plain(s, bx(9.45), Inches(2.8), bx(9.45), bus)          # orchestrator down to the bus
    plain(s, centers[0], bus, centers[-1], bus)              # bus across all handlers
    for i, (t, sub) in enumerate(handlers):
        x = MARGIN + i * (hw + hg)
        label_box(s, x, Inches(3.55), hw, Inches(0.85), t, sub, size=13)
        arrow(s, centers[i], bus, centers[i], Inches(3.55))
        arrow(s, centers[i], Inches(4.4), centers[i], Inches(5.15))
    label_box(s, MARGIN, Inches(5.15), 3 * hw + 2 * hg, Inches(1.0), "SQLite",
              "courses, prerequisites, sections, students, records, requirement slots, plans, chat history  ·  Jordan",
              fill=GREEN_TINT, line=GREEN, size=13)
    label_box(s, MARGIN + 3 * (hw + hg), Inches(5.15), hw, Inches(1.0), "Chroma",
              "155 docs: catalog, descriptions, degree reqs", fill=GREEN_TINT, line=GREEN, size=13)
    label_box(s, MARGIN + 4 * (hw + hg), Inches(5.15), hw, Inches(1.0), "Ollama (local)",
              "qwen3:4b · qwen3:0.6b · nomic-embed-text", fill=AMBER_TINT, line=AMBER, size=13)
    text(s, MARGIN, Inches(6.4), W - 2 * MARGIN, Inches(0.4),
         [[("Every step ", {}), ("→ logs/traces.jsonl", {"bold": True}),
           (" → Traces screen in the app and the rendered execution log in the zip.", {})]],
         size=13, color=MUTED)
    notes(s, """
Presenter: Talha (overview), each owner adds one line about their box.
Flow: the student types or clicks in the UI. The UI only talks to the backend through one file,
ui/services.py. Chat goes to the orchestrator, which routes the message by intent to exactly one
handler. Facts come from SQLite; open-ended questions are answered from Chroma documents by the LLM;
plans and the six checks come from a deterministic planner that never calls an LLM.
Every step writes a trace record, which is how we produce the execution log.
""")

    # 4. Components: function + I/O
    s = new()
    header(s, "Components: what each one does, its input and output")
    table(s, MARGIN, Inches(1.65), W - 2 * MARGIN, [
        ["Component", "Function", "Input", "Output"],
        ["UI (Streamlit)", "Screens, dialogs, chat; calls the backend via ui/services.py", "Clicks, typed questions", "Rendered answers, plans, checks"],
        ["Orchestrator", "Keeps the conversation, routes each turn", "student_id, message, history", "Reply text"],
        ["Intent router", "Keyword rules first, small LLM for the rest", "Message + last turns", "One of 8 intents"],
        ["Exact query chain", "Answers facts with SQL", "Course id / student id", "Prereqs, schedule, record"],
        ["RAG chain", "Retrieves catalog passages, grounded LLM answer", "Question", "Answer from the documents"],
        ["Degree planner", "Orders the prerequisite graph into terms", "Student, program, load, summer", "DegreePlan JSON"],
        ["Verification engine", "Six checks (a)–(f) before recommending", "Course, term, plan", "Pass / fail + reason ×6"],
        ["Plan compare", "Diffs two plans after a change or switch", "Old plan, new plan", "Added, removed, moved"],
        ["Trace logger", "Appends one JSON line per step", "Event + fields", "logs/traces.jsonl"],
    ], [2.4, 4.5, 2.6, 2.43], size=13, row_h=0.5)
    notes(s, """
Presenter: Talha. The spec asks for "functions of each component and input/output" on the slides;
this is that slide. Don't read it; point at two rows and move on.
""")

    # 5. One chat turn, step by step
    s = new()
    header(s, "One question, step by step",
           "“Which courses cover machine learning or AI topics?”, as recorded in the trace log.")
    steps = [("1", "user_msg", "The question arrives with the student id and session"),
             ("2", "router_keyword", "A keyword rule matches “courses … cover” → semantic_query (no LLM call)"),
             ("3", "retrieval", "Chroma returns the 5 closest passages: CSE 4309, CSE 4308, CSE 4311 …"),
             ("4", "llm_response", "qwen3:4b answers using only those passages"),
             ("5", "assistant_msg", "Reply shown in the chat and stored in history for follow-ups")]
    y = Inches(2.1)
    for num, ev, desc in steps:
        rect(s, MARGIN, y, Inches(0.55), Inches(0.55), fill=BLUE, shape=MSO_SHAPE.OVAL)
        text(s, MARGIN, y, Inches(0.55), Inches(0.55), num, size=16, bold=True, color=WHITE,
             align=PP_ALIGN.CENTER, anchor=MSO_ANCHOR.MIDDLE)
        text(s, MARGIN + Inches(0.85), y, Inches(2.6), Inches(0.55), ev, size=15, font=MONO,
             anchor=MSO_ANCHOR.MIDDLE)
        text(s, MARGIN + Inches(3.5), y, Inches(8.4), Inches(0.55), desc, size=16, anchor=MSO_ANCHOR.MIDDLE)
        y += Inches(0.78)
    text(s, MARGIN, Inches(6.15), W - 2 * MARGIN, Inches(0.5),
         "Exact questions take the same path but step 3 is a SQL query and there is no LLM call: they answer in milliseconds.",
         size=14, color=MUTED)
    notes(s, """
Presenter: Kyle (router) + Miguel (retrieval).
This is a real turn from our trace log (screenshot later). Emphasise that routing is cheap:
keyword rules catch most phrasing so the LLM is only used where it adds value.
""")

    # 6. Data
    s = new()
    header(s, "Two databases, two kinds of data",
           "Structured records go to SQL; text the LLM must read goes to a vector store.")
    col = (W - 2 * MARGIN - Inches(0.5)) / 2
    for i, (title, fill, line, items) in enumerate([
        ("SQLite: structural data", GREEN_TINT, GREEN, [
            ("106 courses", " with real catalog credit hours"),
            ("132 prerequisite rules", " (OR groups, minimum grades, same-term allowed)"),
            ("165 class sections", " for Fall 2026, Spring 2027, Summer 2027"),
            ("4 student personas", " with transcripts and current enrollment"),
            ("83 requirement slots", " for 2 programs (123 and 127 credits)"),
            ("Plans and chat history", " saved per student")]),
        ("Chroma: unstructured data", BLUE_TINT, BLUE, [
            ("77 catalog entries", " parsed from the UTA CSE course PDF"),
            ("75 course descriptions", " (course-desc.jsonl)"),
            ("3 degree documents", ": BS CS + Cybersecurity, BS SE + AI, major switch"),
            ("Embedded with", " nomic-embed-text via Ollama, stored locally"),
            ("Used by", " the RAG chain for open-ended questions")]),
    ]):
        x = MARGIN + i * (col + Inches(0.5))
        rect(s, x, Inches(2.0), col, Inches(4.5), fill=fill, radius=0.05)
        text(s, x + Inches(0.35), Inches(2.25), col - Inches(0.7), Inches(0.5), title, size=20,
             bold=True, color=line)
        bullets(s, x + Inches(0.35), Inches(2.95), col - Inches(0.7), Inches(3.4), items, size=15)
    notes(s, """
Presenter: Jordan.
Data comes from the real UTA 2026-27 catalog (degree plans parsed from it); class sections and
students are fabricated but consistent with the prerequisites. Documents used to build the embeddings
are included in the zip under advisor/seed/.
""")

    # 7. Design decisions
    s = new()
    header(s, "Design decisions", "What we considered, what we chose, and why.")
    table(s, MARGIN, Inches(1.9), W - 2 * MARGIN, [
        ["Decision", "Options considered", "Chosen", "Why"],
        ["LLM", "OpenAI API · local Ollama", "Ollama, qwen3", "Free, offline demo, no keys; OpenAI kept as a switch in .env"],
        ["Vector DB", "Pinecone · Chroma", "Chroma (local)", "No account or cost; LangChain integration"],
        ["Routing", "LLM only · keywords only · hybrid", "Hybrid", "Keywords are instant and predictable; LLM only for ambiguous phrasing"],
        ["Degree planning", "LLM writes the plan · algorithm", "Deterministic", "Plans must be correct: an LLM can't be trusted with prerequisites"],
        ["UI", "CLI · desktop · web", "Streamlit web", "Dialog boxes and prompts in one app, quick to build in Python"],
        ["Layering", "UI calls modules directly · one boundary", "ui/services.py", "UI never depends on backend internals; stubs show “not built yet”"],
        ["Prompts", "In code · template files (Jinja)", "In code (for now)", "Next step: move to template files, per the professor’s tip"],
    ], [1.9, 3.3, 1.9, 4.83], size=13, row_h=0.56)
    notes(s, """
Presenter: Talha, with Kyle for routing and Loc for the planner.
The assignment asks for the design decisions considered and why we chose ours; this is that slide.
Strongest point: plans and the six checks are deterministic code, so the LLM can't invent a
prerequisite or a section that doesn't exist.
""")

    # 8-13. Code segments
    code_slides = [
        ("Code: requirement data (Jordan)", "advisor/seed/schema.sql", """
-- A program is a set of requirement slots. Fixed slots name one
-- course; elective slots list allowed courses in `options`.
CREATE TABLE requirement_slots (
    slot_id    INTEGER PRIMARY KEY AUTOINCREMENT,
    program_id TEXT NOT NULL REFERENCES degree_programs(program_id),
    category   TEXT NOT NULL,   -- core, math_science, cse_core, ...
    course_id  TEXT REFERENCES courses(course_id),  -- NULL = elective
    options    TEXT NOT NULL DEFAULT '[]',          -- JSON course ids
    credits    INTEGER NOT NULL
);
-- Prerequisites that may be taken in the same term (co-requisites).
CREATE TABLE prereq_concurrent (
    course_id TEXT NOT NULL REFERENCES courses(course_id),
    prereq_id TEXT NOT NULL REFERENCES courses(course_id),
    PRIMARY KEY (course_id, prereq_id)
);""",
         ["Turns the catalog’s degree plans into rows the planner can reason over",
          "One table drives the planner, the six checks, and the progress rings",
          "Generated from the real catalog by build_seed_data.py, not typed by hand"],
         "Presenter: Jordan. Why it's needed: without structured requirement slots, nothing can\n"
         "decide whether a course “counts” (check c) or what's left to graduate."),
        ("Code: intent router (Kyle)", "advisor/router.py", """
def route(message, history=None) -> Intent:
    # 1. Deterministic keyword pass: zero latency, predictable
    if (kw := _keyword_route(message)) is not None:
        trace("router_keyword", intent=kw.value)
        return kw
    # 2. Ambiguous phrasing: ask a small, fast LLM
    recent = "\\n".join(f"{m['role']}: {m['content'][:200]}"
                       for m in (history or [])[-4:])
    try:
        resp = get_router_model().invoke(
            _PROMPT.format(history=recent, message=message))
        text = _strip_think(resp.content).lower()
    except Exception as e:      # backend down -> safe fallback
        trace("router_error", error=str(e))
        return Intent.OTHER
    return next((i for i in Intent if i.value in text), Intent.OTHER)""",
         ["Decides which handler answers each message (spec req 3)",
          "Keywords catch clear phrasing instantly; qwen3:0.6b handles the rest",
          "Recent turns let follow-ups like “what about 3 classes?” resolve",
          "Never crashes a turn: any failure falls back to general chat"],
         "Presenter: Kyle."),
        ("Code: orchestrator dispatch (Kyle)", "advisor/orchestrator.py", """
def _dispatch(student_id, message, intent, history) -> str:
    if intent in (Intent.EXACT_QUERY, Intent.STATUS_QUERY):
        return chains.answer_exact(message, student_id)      # SQL
    if intent == Intent.SEMANTIC_QUERY:
        return chains.answer_semantic(message, student_id)   # RAG
    if intent == Intent.GENERATE_PLAN:
        plan = tools.generate_degree_plan.invoke({
            "student_id": student_id,
            "include_summer": _wants_summer(message)})
        return _format_plan(plan)
    if intent == Intent.MODIFY_PLAN:
        plan = tools.modify_plan.invoke({
            "student_id": student_id, **_extract_modify_args(message)})
        return _format_plan(plan)
    if intent == Intent.SWITCH_MAJOR:
        return _handle_switch_major(student_id, message)
    if intent == Intent.CHECK_ELIGIBILITY:
        return _handle_eligibility(student_id, message)
    return _general_answer(message, history)""",
         ["One place maps each intent to exactly one handler",
          "Planner calls go through LangChain tools (tool.invoke), so the same operations are ready for an agent",
          "Conversation history is passed in every turn (spec req 6)"],
         "Presenter: Kyle."),
        ("Code: retrieval and grounded answers (Miguel)", "advisor/chains.py", """
def answer_semantic(query, student_id=None, k=5) -> str:
    if OVERRIDE_REQUEST.search(query):     # prompt-injection guard
        return "I can help with academic advising questions, ..."
    matches = search_documents(query, k=k)  # Chroma + exact course ids
    if not matches:
        return "I couldn't find that in the indexed documents."
    references = [{"name": _source_name(h), "text": h["text"][:4000]}
                  for h in matches]
    system_message = (
        "You are an academic course and degree information assistant. "
        "Use ONLY facts explicitly stated in the supplied "
        "reference_documents ... If the sources do not answer the "
        "question, say what cannot be confirmed. ...")
    # JSON keeps the student's text separate from the documents
    payload = json.dumps({"student_question": query,
                          "reference_documents": references})
    response = get_chat_model(temperature=0).invoke([
        ("system", system_message), ("human", payload)])""",
         ["Answers open-ended questions from the catalog and degree documents",
          "Named courses are fetched directly, then semantic matches fill in",
          "The model may only use retrieved text, so answers stay factual",
          "Question and documents are treated as untrusted data: injection attempts are refused"],
         "Presenter: Miguel."),
        ("Code: the six verification checks (Loc)", "advisor/planner.py", """
def _verify(context, cid, term, plan) -> list[CheckResult]:
    prereqs = _prerequisite_failures(context, cid, term, plan)
    fulfills = _coverage(context, after) > _coverage(context, before)
    schedule_ok = _section_assignment(context, semester_ids, term) is not None
    return [
        CheckResult("prerequisites_met", not prereqs, ...),          # (a)
        CheckResult("not_already_passed",
                    cid not in passed and not scheduled_elsewhere, ...),  # (b)
        CheckResult("fulfills_degree_requirement", fulfills, ...),   # (c)
        CheckResult("no_schedule_conflict", schedule_ok, ...),       # (d)
        CheckResult("within_semester_credit_cap",
                    semester_credits <= semester_cap, ...),          # (e)
        CheckResult("within_degree_credit_cap",
                    degree_credits <= degree_cap, ...),              # (f)
    ]""",
         ["Runs before any course is recommended or added (spec req 4)",
          "Each check returns pass/fail and a human-readable reason",
          "Schedule check searches for a conflict-free set of real sections",
          "Pure Python over SQLite: no LLM, so results are exact and repeatable"],
         "Presenter: Loc."),
        ("Code: UI boundary and execution traces (Talha)", "ui/services.py, advisor/tracing.py", """
def _call(action, student_id, live, fallback, use_preview, **fields):
    try:
        result, source = live(), "live"
    except NotImplementedError as e:      # teammate's module not merged
        if not use_preview:
            raise NotReady(str(e)) from e  # UI shows "not built yet"
        result, source = fallback(), "preview"
    tracing.trace("ui_action", student_id=student_id, action=action,
                  source=source, **fields)
    return result, source

def trace(event: str, **fields) -> None:   # one JSON line per step
    record = {"ts": datetime.now(timezone.utc).isoformat(),
              "event": event,
              **({"session": s} if (s := _session.get()) else {}),
              **fields}
    with TRACE_LOG.open("a") as f:
        f.write(json.dumps(record, default=str) + "\\n")""",
         ["The UI touches the backend in one file, so each layer was built in parallel",
          "Every UI action and chat step lands in logs/traces.jsonl, tagged by session",
          "The Traces screen and scripts/render_traces.py turn it into the execution log"],
         "Presenter: Talha."),
    ]
    for title, path, src, why, who in code_slides:
        s = new()
        header(s, title)
        text(s, MARGIN, Inches(1.25), Inches(8), Inches(0.4), path, size=13, font=MONO, color=MUTED)
        code(s, MARGIN, Inches(1.8), Inches(7.6), Inches(5.0), src, size=11)
        text(s, MARGIN + Inches(7.95), Inches(1.85), Inches(4.0), Inches(0.4), "What it does and why",
             size=16, bold=True)
        bullets(s, MARGIN + Inches(7.95), Inches(2.4), Inches(4.0), Inches(4.4), why, size=15)
        notes(s, who + "\nExplain what the segment does (left) and why the system needs it (right).")

    # 14-20. Demo screenshots
    demo = [
        ("01_overview_rings.png", "Demo: Sam’s progress at a glance",
         "Pick a student", "Credits done, in progress, and per-area requirement rings from SQLite",
         "Sam has 32 of 123 credits; blue is this fall’s 4 classes. The certificate ring is empty: still to plan."),
        ("03_plan_years.png", "Demo: a multi-year degree plan",
         "Plan → Build plan (auto load, no summer) → Years",
         "Completed terms (green), then planned semesters (blue), year by year",
         "The planner fills semesters in prerequisite order within the 15-credit cap; the rings show what each area still needs."),
        ("05_six_checks.png", "Demo: six checks before recommending",
         "Check a course: CSE 4344, Spring 2027", "Checks (a)–(f), each with pass/fail and the reason",
         "A course is only recommended if all six pass; the reasons tell the student exactly what to fix."),
        ("07_ask_semantic_rag.png", "Demo: exact vs. semantic questions",
         "“Prerequisites for CSE 3310?” then “Which courses cover machine learning?”",
         "SQL answer in milliseconds; RAG answer grounded in the catalog",
         "Same chat, two paths: the router sent the first to SQL and the second to Chroma + the LLM."),
        ("08_ask_followup_memory.png", "Demo: the conversation remembers",
         "“Generate my degree plan”, then “What about only 3 classes next semester?”",
         "A new plan with 3 classes in Spring 2027",
         "The follow-up has no subject of its own; the history passed into the turn makes it resolvable."),
        ("09_switch_major_compare.png", "Demo: switching major, compared",
         "Switch major → Software Engineering + AI → Compare plans",
         "Current plan and the new one side by side, plus what changes",
         "Lets a student see the cost of switching before committing to it."),
        ("10_execution_traces.png", "Demo: the execution trace",
         "More → Show execution traces → Traces", "Every turn and action, step by step, with timings",
         "This is the required log of execution traces; the zip has the same data as JSONL and as a readable report."),
    ]
    crops = {"01_overview_rings.png": (0.13, 0.2, 0.13), "03_plan_years.png": (0.13, 0.47, 0.13),
             "05_six_checks.png": (0.13, 0.12, 0.13), "07_ask_semantic_rag.png": (0.13, 0.03, 0.13),
             "08_ask_followup_memory.png": (0.13, 0.0, 0.13), "09_switch_major_compare.png": (0.13, 0.17, 0.13),
             "10_execution_traces.png": (0.13, 0.12, 0.13)}
    for img, title, inp, outp, meaning in demo:
        s = new()
        header(s, title)
        picture(s, shots / img, MARGIN, Inches(1.5), Inches(8.3), Inches(5.35), crop=crops.get(img, (0, 0, 0)))
        tx = MARGIN + Inches(8.65)
        y = Inches(1.55)
        for head, body in (("Input", inp), ("Output", outp), ("What it means", meaning)):
            text(s, tx, y, Inches(3.3), Inches(0.35), head, size=13, bold=True, color=BLUE)
            box = text(s, tx, y + Inches(0.38), Inches(3.3), Inches(1.4), body, size=15)
            y += Inches(1.75)
        notes(s, f"Input: {inp}\nOutput: {outp}\nWhat it means: {meaning}")

    # 21. Testing
    s = new()
    header(s, "How we know it works")
    bullets(s, MARGIN, Inches(1.8), Inches(6.0), Inches(4.8), [
        ("89 automated tests", " across planner, router, RAG retrieval, data schema, UI services, and tracing"),
        ("Scripted demo", " (scripts/run_demo.py) replays the 7 demo questions end to end and renders the trace log"),
        ("Scripted screenshots", " (scripts/take_screenshots.py) drive the real app in a browser"),
        ("Every branch merged and tested together", " before merging into main"),
    ], size=17)
    rect(s, MARGIN + Inches(6.6), Inches(1.8), Inches(5.3), Inches(4.3), fill=SURFACE, radius=0.05)
    text(s, MARGIN + Inches(6.95), Inches(2.05), Inches(4.6), Inches(0.4), "Response time on a laptop (M5, 16 GB)",
         size=15, bold=True)
    table(s, MARGIN + Inches(6.95), Inches(2.6), Inches(4.6), [
        ["Question type", "Time"],
        ["Exact (SQL)", "< 0.1 s"],
        ["Plan / checks / modify", "< 0.1 s"],
        ["Semantic (RAG + qwen3:4b)", "20–50 s"],
        ["General chat (qwen3:4b)", "≈ 20 s"],
    ], [3.1, 1.5], size=14, row_h=0.55, head_fill=WHITE)
    notes(s, "Presenter: Talha. Mention that slow answers are local-model speed; OpenAI is a one-line switch.")

    # 22. Limitations
    s = new()
    header(s, "Limitations and next steps")
    bullets(s, MARGIN, Inches(1.8), W - 2 * MARGIN, Inches(4.8), [
        ("Schedule horizon:", " sections exist for three terms only; plans beyond them assume courses repeat"),
        ("Local model speed:", " 20–50 s per LLM answer on a laptop; a GPU or the OpenAI switch fixes it"),
        ("Prompts in code:", " move them to template files (Jinja) so they can be tuned without code changes"),
        ("Layer folders:", " split database, backend, and AI logic into separate packages"),
        ("Real data:", " student records are fabricated personas; a real deployment would read the registrar"),
    ], size=18)
    notes(s, "Update this slide after the final run: drop anything the team fixed before the deadline.")

    # 23. Questions
    s = new()
    rect(s, 0, 0, W, H, fill=SURFACE, shape=MSO_SHAPE.RECTANGLE)
    text(s, MARGIN, Inches(2.8), W - 2 * MARGIN, Inches(1.2), "Questions", size=54, bold=True)
    text(s, MARGIN, Inches(4.0), W - 2 * MARGIN, Inches(0.6),
         "github.com/JordanTaylorGit/CSE-4392-AI-Academic-Advisor", size=18, color=MUTED)
    notes(s, "Keep the app open on the Traces screen for questions about how an answer was produced.")

    out.parent.mkdir(parents=True, exist_ok=True)
    prs.save(out)
    print(f"Wrote {out} ({n} slides)")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--shots", type=Path, default=REPO_ROOT / "deliverables" / "screenshots")
    ap.add_argument("--out", type=Path, default=REPO_ROOT / "deliverables" / "AI_Advisor_Presentation.pptx")
    args = ap.parse_args(argv)
    build(args.shots, args.out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
