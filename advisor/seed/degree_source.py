"""
Single source of truth for degree requirements, personas and offering patterns.
build_seed_data.py turns this + the catalog PDF into every generated seed file.

Real UTA structure (2026-2027 catalog): CS and SE have NO concentrations. Career tracks are
undergraduate certificates awarded with the degree. The project's two program ids are therefore
defined as degree + certificate, flattened into plain requirement slots:

    bs_cs_cyber = BS Computer Science      + Certificate in Cybersecurity            (123 hrs)
    bs_se_ai    = BS Software Engineering  + Certificate in Fundamentals of AI       (127 hrs)

ASSUMPTION (unconfirmed with CSE advising): certificate courses may also satisfy degree slots.
Under that assumption the Cybersecurity certificate costs CS students nothing extra, and the AI
certificate costs SE students one extra course (3 hrs).  Verify: cseugadvising@uta.edu.
"""

CATALOG_YEAR = "2026"
VERIFIED_ON = "2026-10-21"
_BASE = "https://catalog.uta.edu/engineering/computer/undergraduate/"
SOURCES = {
    "bs_cs_cyber": [_BASE + "computer-science-bs/", _BASE + "cybersecurity-minor/"],
    "bs_se_ai": [_BASE + "software-engineering-bs/", _BASE + "artificial-intelligence-cert/"],
}
GEN_CORE_SOURCE = ("https://catalog.uta.edu/archives/2025-2026/academicregulations/degreerequirements/"
                   "generalcorerequirements/generalcorerequirements.pdf")

# ---------------------------------------------------------------------------
# Non-CSE courses referenced by slots / prerequisites: id -> (TITLE, credits)
# Descriptions already in seed/extra_courses.json are preserved by the builder.
# credits marked (*) are inferred, not stated in the pages we read.
# ---------------------------------------------------------------------------
NON_CSE = {
    "UNIV 1131": ("STUDENT SUCCESS", 1),
    "ENGR 1101": ("ENTRANCE TO ENGINEERING FOR TRANSFER STUDENTS", 1),
    "UNIV 1101": ("CAREER PREPARATION AND STUDENT SUCCESS", 1),               # (*) credits
    "ENGL 1301": ("RHETORIC AND COMPOSITION I", 3),
    "COMS 2302": ("PROFESSIONAL AND TECHNICAL COMMUNICATION FOR SCIENCE AND ENGINEERING", 3),
    "MATH 1426": ("CALCULUS I", 4),
    "MATH 2425": ("CALCULUS II", 4),
    "MATH 2326": ("CALCULUS III", 3),
    "MATH 3330": ("INTRODUCTION TO LINEAR ALGEBRA AND VECTOR SPACES", 3),
    "MATH 3313": ("INTRODUCTION TO PROBABILITY", 3),
    "PHYS 1443": ("GENERAL TECHNICAL PHYSICS I", 4),
    "PHYS 1444": ("GENERAL TECHNICAL PHYSICS II", 4),
    "IE 3301": ("ENGINEERING PROBABILITY", 3),
    "IE 2308": ("ECONOMICS FOR ENGINEERS", 3),
    "ECON 2305": ("PRINCIPLES OF MACROECONOMICS", 3),
    "IE 3315": ("OPERATIONS RESEARCH I", 3),
    "ENGR 4302": ("ENGINEERING ENTREPRENEURSHIP", 3),
    "BIOL 1441": ("BIOLOGY I FOR SCIENCE MAJORS: CELL AND MOLECULAR BIOLOGY", 4),   # (*) credits
    "CHEM 1441": ("GENERAL CHEMISTRY I", 4),                                        # (*) credits
    "CHEM 1465": ("CHEMISTRY FOR ENGINEERS", 4),                                    # (*) credits
    # general-core sample courses (UTA 2025-26 general core list; samples only)
    "HIST 1301": ("HISTORY OF THE UNITED STATES TO 1865", 3),
    "HIST 1302": ("HISTORY OF THE UNITED STATES, 1865 TO PRESENT", 3),
    "POLS 2311": ("GOVERNMENT OF THE UNITED STATES", 3),
    "POLS 2312": ("STATE AND LOCAL GOVERNMENT", 3),
    "PHIL 2300": ("INTRODUCTION TO PHILOSOPHY", 3),
    "LING 2371": ("LANGUAGE IN A MULTICULTURAL USA", 3),
    "HIST 2377": ("FLIGHT CULTURE AND THE HUMAN EXPERIENCE", 3),
    "ENGL 1375": ("INTRODUCTION TO CREATIVE WRITING", 3),
    "MUSI 1304": ("HISTORY OF ROCK MUSIC", 3),
}

# ---------------------------------------------------------------------------
# slot helpers.  db category vocabulary (frozen): core | math_science | cse_core | concentration | elective
# type: fixed | one_of | choose_n | category | free
# ---------------------------------------------------------------------------
def S(key, stype, hours, courses=(), cat="cse_core", label="", n=None, notes=""):
    return dict(key=key, type=stype, hours=hours, courses=list(courses), cat=cat, label=label, n=n, notes=notes)

def F(key, course, cat="cse_core", hours=3):
    return S(key, "fixed", hours, [course], cat)

def O(key, courses, hours, label, cat="cse_core"):
    return S(key, "one_of", hours, courses, cat, label)

_HIST = ["HIST 1301", "HIST 1302"]
_POLS = ["POLS 2311", "POLS 2312"]
_LPC = ["PHIL 2300", "LING 2371", "HIST 2377"]
_ARTS = ["ENGL 1375", "MUSI 1304"]

SHARED = [
    O("student_success", ["UNIV 1131", "ENGR 1101", "UNIV 1101"], 1, "Student success course", "core"),
    F("engl1301", "ENGL 1301", "core"), F("coms2302", "COMS 2302", "core"),
    F("math1426", "MATH 1426", "math_science", 4), F("math2425", "MATH 2425", "math_science", 4),
    F("math2326", "MATH 2326", "math_science"),
    F("phys1443", "PHYS 1443", "math_science", 4), F("phys1444", "PHYS 1444", "math_science", 4),
    O("econ", ["IE 2308", "ECON 2305"], 3, "Social & behavioral science (economics)", "core"),
    S("us_history", "category", 6, _HIST, "core", "U.S. History",
      notes="Two 3-hr U.S. history courses (general core)."),
    S("government", "category", 6, _POLS, "core", "Government / Political Science",
      notes="Two 3-hr political science courses (general core)."),
    S("lpc", "category", 3, _LPC, "core", "Language, Philosophy & Culture",
      notes="One course from the general-core Language, Philosophy & Culture list (samples shown)."),
    S("creative_arts", "category", 3, _ARTS, "core", "Creative Arts",
      notes="One course from the general-core Creative Arts list (samples shown)."),
    F("cse1106", "CSE 1106", hours=1), F("cse1310", "CSE 1310"), F("cse1320", "CSE 1320"),
    F("cse1325", "CSE 1325"), F("cse2312", "CSE 2312"), F("cse2315", "CSE 2315"), F("cse3318", "CSE 3318"),
    O("prob", ["IE 3301", "MATH 3313"], 3, "Probability"),
    F("cse3302", "CSE 3302"), F("cse3310", "CSE 3310"), F("cse3314", "CSE 3314"),
    F("cse3315", "CSE 3315"), F("cse3320", "CSE 3320"), F("cse3330", "CSE 3330"),
    O("linalg", ["CSE 3380", "MATH 3330"], 3, "Linear algebra"),
    F("cse4316", "CSE 4316"), F("cse4317", "CSE 4317"),
]

# technical-elective menus from the catalog (CSE 4392 omitted: advisor-approved sections only)
_CS_TECH = ["CSE 4303", "CSE 4304", "CSE 4305", "CSE 4308", "CSE 4309", "CSE 4310", "CSE 4311",
            "CSE 4321", "CSE 4322", "CSE 4323", "CSE 4331", "CSE 4333", "CSE 4334", "CSE 4345",
            "CSE 4351", "CSE 4360", "CSE 4361", "CSE 4373", "CSE 4376", "CSE 4378", "CSE 4379",
            "CSE 3311", "CSE 3313", "CSE 3340", "ENGR 4302", "IE 3315"]       # + 4380/4381/4382 (used by the cert)

SLOTS = {
    "bs_cs_cyber": SHARED + [
        F("cse4344", "CSE 4344", "concentration"),
        F("cse4380", "CSE 4380", "concentration"),
        F("cse4381", "CSE 4381", "concentration"),
        F("cse4382", "CSE 4382", "concentration"),
        S("tech_electives", "choose_n", 12, _CS_TECH, "elective", "Technical elective", n=4,
          notes="BS CS requires 6 technical electives; two are CSE 4381 and CSE 4382 (certificate), "
                "leaving 4 free choices."),
        S("free_elective", "free", 3, [], "elective", "Open elective", notes="Any course; brings the total to 123 hrs."),
    ],
    "bs_se_ai": SHARED + [
        F("cse3311", "CSE 3311"), F("cse4321", "CSE 4321"), F("cse4322", "CSE 4322"),
        F("cse4361", "CSE 4361"), F("cse4380", "CSE 4380"),
        S("science_elective", "choose_n", 4, ["BIOL 1441", "CHEM 1441", "CHEM 1465"], "math_science",
          "Science elective", n=1,
          notes="Catalog also allows PHYS 3313 + PHYS 3183 together (not modelled as a single slot). Advisor approval."),
        F("cse4308", "CSE 4308", "concentration"), F("cse4309", "CSE 4309", "concentration"),
        F("cse4310", "CSE 4310", "concentration"), F("cse4311", "CSE 4311", "concentration"),
    ],
}

PROGRAMS = [
    dict(id="bs_cs_cyber", total=123,
         name="BS in Computer Science + Certificate in Cybersecurity",
         short="BS in Computer Science — Cybersecurity certificate",
         overview=("UTA's BS in Computer Science (ABET-accredited) combined with the undergraduate Certificate in "
                   "Cybersecurity, which UTA awards concurrently with the degree. UTA does not offer a formal "
                   "'concentration'; the certificate is the cybersecurity track. The certificate needs CSE 4344 "
                   "(or 4352), 4380, 4381 and 4382 (12 hrs, 3.0 GPA on those courses). In the BS CS, CSE 4344 and "
                   "one security course are required and there are six technical electives, so the certificate fits "
                   "inside the degree with no extra hours when certificate courses may double-count (unconfirmed).")),
    dict(id="bs_se_ai", total=127,
         name="BS in Software Engineering + Certificate in Fundamentals of Artificial Intelligence",
         short="BS in Software Engineering — AI certificate",
         overview=("UTA's BS in Software Engineering (ABET-accredited) combined with the undergraduate Certificate in "
                   "the Fundamentals of Artificial Intelligence, awarded concurrently with the degree. UTA does not "
                   "offer a formal 'concentration'; the certificate is the AI track. The certificate needs CSE 4308, "
                   "4309, 4310 and 4311 (12 hrs, 3.0 GPA). The BS SE has only three technical electives, so three "
                   "certificate courses fit inside the degree and the fourth is an extra 3-hour course "
                   "(124 + 3 = 127 hrs), assuming certificate courses may double-count (unconfirmed).")),
]

RULES = [
    "Admission to the Engineering Professional Program is required before taking most 3000/4000-level CSE "
    "courses (see the `professional_courses` table). Requires a 2.5 GPA overall, in required science/math/engineering "
    "courses, and in required CSE courses, with no more than four unsuccessful engineering attempts.",
    "All prerequisites for professional-program courses must be completed with a C or better.",
    "Certificate courses need a combined 3.0 GPA. Certificate course substitutions need advance approval from "
    "the certificate coordinator.",
    "Course offerings: 1000/2000-level CSE courses are offered every term including summer; 3000-level and "
    "required 4000-level courses at least twice a year; other 4000-level electives about once a year.",
]

# ---------------------------------------------------------------------------
# Catalog-verbatim 4-year sequences for the PLAIN degrees (test fixtures for Loc; not loaded into SQLite).
# (year, term, slot_key, hours) -- keys refer to SHARED slot keys plus the ones below.
# ---------------------------------------------------------------------------
_Y12 = [
    (1, "Fall", "student_success", 1), (1, "Fall", "cse1310", 3), (1, "Fall", "math1426", 4),
    (1, "Fall", "engl1301", 3), (1, "Fall", "us_history", 3), (1, "Fall", "lpc", 3),
    (1, "Spring", "cse1106", 1), (1, "Spring", "cse1320", 3), (1, "Spring", "math2425", 4),
    (1, "Spring", "phys1443", 4), (1, "Spring", "cse2315", 3),
    (2, "Fall", "cse1325", 3), (2, "Fall", "cse2312", 3), (2, "Fall", "cse3318", 3),
    (2, "Fall", "phys1444", 4), (2, "Fall", "us_history", 3),
    (2, "Spring", "linalg", 3), (2, "Spring", "cse3310", 3), (2, "Spring", "cse3320", 3),
    (2, "Spring", "math2326", 3), (2, "Spring", "coms2302", 3),
]
CATALOG_SEQUENCES = {
    "BS Computer Science (no certificate)": _Y12 + [
        (3, "Fall", "cse3302", 3), (3, "Fall", "cse3330", 3), (3, "Fall", "cse3315", 3), (3, "Fall", "prob", 3),
        (3, "Fall", "government", 3),
        (3, "Spring", "cse4344", 3), (3, "Spring", "government", 3), (3, "Spring", "technical_elective", 3),
        (3, "Spring", "technical_elective", 3), (3, "Spring", "technical_elective", 3),
        (4, "Fall", "cse3314", 3), (4, "Fall", "cse4316", 3), (4, "Fall", "econ", 3),
        (4, "Fall", "technical_elective", 3), (4, "Fall", "technical_elective", 3),
        (4, "Spring", "cse4317", 3), (4, "Spring", "security_course", 3), (4, "Spring", "technical_elective", 3),
        (4, "Spring", "free_elective", 3), (4, "Spring", "creative_arts", 3)],
    "BS Software Engineering (no certificate)": _Y12 + [
        (3, "Fall", "cse3302", 3), (3, "Fall", "cse3330", 3), (3, "Fall", "prob", 3), (3, "Fall", "cse3311", 3),
        (3, "Fall", "government", 3),
        (3, "Spring", "cse4321", 3), (3, "Spring", "cse4380", 3), (3, "Spring", "cse3315", 3),
        (3, "Spring", "government", 3), (3, "Spring", "technical_elective", 3),
        (4, "Fall", "cse3314", 3), (4, "Fall", "cse4316", 3), (4, "Fall", "cse4361", 3),
        (4, "Fall", "technical_elective", 3), (4, "Fall", "science_elective", 4),
        (4, "Spring", "cse4317", 3), (4, "Spring", "cse4322", 3), (4, "Spring", "econ", 3),
        (4, "Spring", "creative_arts", 3), (4, "Spring", "technical_elective", 3)],
}
CATALOG_TERM_HOURS = {  # printed in the catalog; build-time check
    "BS Computer Science (no certificate)": [17, 15, 16, 15, 15, 15, 15, 15],
    "BS Software Engineering (no certificate)": [17, 15, 16, 15, 15, 15, 16, 15],
}

# ---------------------------------------------------------------------------
# Personas.  Convention: Fall 2026 (F2026) is the CURRENT term -> `current_enrollments`
# (-> enrollments table); `completed` ends at S2026/SU2026; planning starts S2027.
# ---------------------------------------------------------------------------
def C(course, term, grade):
    return {"course_id": course, "term": term, "grade": grade}

STUDENTS = [
    dict(student_id="s_freshman", name="Alex Freshman", program_id="bs_cs_cyber", start_term="F2026",
         max_credits_per_semester=15, completed=[],
         current=["UNIV 1131", "CSE 1310", "MATH 1426", "ENGL 1301", "HIST 1301"],
         note="First-semester student (enrolled Fall 2026) — plan the remaining ~3.5 years from scratch."),
    dict(student_id="s_sophomore", name="Sam Martinez", program_id="bs_cs_cyber", start_term="F2025",
         max_credits_per_semester=15,
         completed=[C("UNIV 1131", "F2025", "A"), C("CSE 1310", "F2025", "B"), C("MATH 1426", "F2025", "B"),
                    C("ENGL 1301", "F2025", "B"), C("HIST 1301", "F2025", "B"),
                    C("CSE 1106", "S2026", "A"), C("CSE 1320", "S2026", "A"), C("MATH 2425", "S2026", "C"),
                    C("PHYS 1443", "S2026", "B"), C("CSE 2315", "S2026", "B"), C("PHIL 2300", "SU2026", "A")],
         current=["CSE 1325", "CSE 2312", "CSE 3318", "PHYS 1444"],
         note="Mid-degree CS/cybersecurity student — primary demo persona."),
    dict(student_id="s_switcher", name="Jordan Lee", program_id="bs_se_ai", start_term="F2025",
         max_credits_per_semester=15,
         completed=[C("UNIV 1131", "F2025", "A"), C("CSE 1310", "F2025", "A"), C("MATH 1426", "F2025", "B"),
                    C("ENGL 1301", "F2025", "A"), C("HIST 1301", "F2025", "B"), C("CSE 1106", "S2026", "B"), C("CSE 1320", "S2026", "B"), C("MATH 2425", "S2026", "B"),
                    C("PHYS 1443", "S2026", "A"), C("CSE 2315", "S2026", "B"), C("CSE 1325", "SU2026", "A"), C("PHIL 2300", "SU2026", "B")],
         current=["CSE 3310", "CSE 2312", "CSE 3318", "PHYS 1444"],
         note="SE/AI student considering a switch to CS — drives the major-switch demo."),
    dict(student_id="s_senior", name="Pat Nguyen", program_id="bs_cs_cyber", start_term="F2023",
         max_credits_per_semester=18,
         completed=[C("UNIV 1131", "F2023", "A"), C("CSE 1310", "F2023", "A"), C("MATH 1426", "F2023", "B"),
                    C("ENGL 1301", "F2023", "A"), C("HIST 1301", "F2023", "A"), C("PHIL 2300", "F2023", "B"),
                    C("CSE 1106", "S2024", "A"), C("CSE 1320", "S2024", "B"), C("MATH 2425", "S2024", "A"),
                    C("PHYS 1443", "S2024", "B"), C("CSE 2315", "S2024", "A"),
                    C("CSE 1325", "F2024", "A"), C("CSE 2312", "F2024", "B"), C("CSE 3318", "F2024", "B"),
                    C("PHYS 1444", "F2024", "B"), C("HIST 1302", "F2024", "A"),
                    C("CSE 3380", "S2025", "A"), C("CSE 3310", "S2025", "A"), C("CSE 3320", "S2025", "A"),
                    C("MATH 2326", "S2025", "B"), C("COMS 2302", "S2025", "A"),
                    C("CSE 3302", "F2025", "B"), C("CSE 3330", "F2025", "A"), C("CSE 3315", "F2025", "B"),
                    C("IE 3301", "F2025", "B"), C("POLS 2311", "F2025", "A"),
                    C("CSE 4344", "S2026", "B"), C("POLS 2312", "S2026", "A"), C("CSE 4380", "S2026", "A"),
                    C("CSE 4303", "S2026", "A"), C("CSE 4351", "S2026", "B")],
         current=["CSE 3314", "CSE 4316", "ECON 2305", "CSE 4381", "CSE 4331"],
         note="Near-grad senior — exactly one semester (S2027, 15 hrs) remaining after Fall 2026; "
              "edge cases for credit caps and capstone sequencing (CSE 4316 -> 4317)."),
]

# ---------------------------------------------------------------------------
# Fabricated schedule: which terms each course is offered (F2026 = current, S2027, SU2027).
# Patterns follow the catalog's offering policy; electives rotate so not everything is offered every term.
# ---------------------------------------------------------------------------
F26, S27, SU27 = "F2026", "S2027", "SU2027"
ALL3, FS, F_ONLY, S_ONLY, S_SU, F_SU = ([F26, S27, SU27], [F26, S27], [F26], [S27], [S27, SU27], [F26, SU27])

OFFERINGS = {
    # CSE 1000/2000 every term
    "CSE 1106": ALL3, "CSE 1310": ALL3, "CSE 1320": ALL3, "CSE 1325": ALL3, "CSE 2312": ALL3, "CSE 2315": ALL3,
    # 3000-level + required 4000
    "CSE 3318": ALL3, "CSE 3310": ALL3, "CSE 3320": FS + [SU27], "CSE 3330": FS, "CSE 3380": FS, "CSE 3302": FS,
    "CSE 3314": FS, "CSE 3315": FS, "CSE 3311": FS, "CSE 4316": FS, "CSE 4317": FS,
    "CSE 4321": FS, "CSE 4322": FS, "CSE 4361": FS, "CSE 4344": ALL3, "CSE 4380": FS, "CSE 4381": FS,
    "CSE 4382": S_SU,
    # AI certificate courses
    "CSE 4308": S_ONLY, "CSE 4309": S_ONLY, "CSE 4310": F_ONLY, "CSE 4311": F_ONLY,
    # other technical electives, ~once a year
    "CSE 4303": S_ONLY, "CSE 4304": F_ONLY, "CSE 4305": S_ONLY, "CSE 4323": F_ONLY, "CSE 4331": F_ONLY,
    "CSE 4333": S_ONLY, "CSE 4334": S_ONLY, "CSE 4345": F_ONLY, "CSE 4351": S_ONLY, "CSE 4360": S_ONLY,
    "CSE 4373": F_ONLY, "CSE 4376": S_ONLY, "CSE 4378": F_ONLY, "CSE 4379": S_ONLY,
    "CSE 3313": F_ONLY, "CSE 3340": S_ONLY,
    # non-CSE
    "UNIV 1131": [F26, S27], "ENGL 1301": ALL3, "COMS 2302": ALL3, "MATH 1426": ALL3, "MATH 2425": ALL3,
    "MATH 2326": ALL3, "MATH 3330": FS, "MATH 3313": FS, "PHYS 1443": FS + [SU27], "PHYS 1444": FS + [SU27],
    "IE 3301": FS, "IE 2308": FS, "ECON 2305": ALL3, "HIST 1301": ALL3, "HIST 1302": ALL3,
    "POLS 2311": ALL3, "POLS 2312": ALL3, "PHIL 2300": FS + [SU27], "LING 2371": F_ONLY, "ENGL 1375": FS,
    "MUSI 1304": S_ONLY, "ENGR 4302": F_ONLY, "IE 3315": S_ONLY, "CHEM 1441": FS, "BIOL 1441": FS,
    "CHEM 1465": F_ONLY,
}
BIG_COURSES = {"CSE 1310", "CSE 1320", "CSE 2315", "CSE 3318", "MATH 1426", "MATH 2425", "ENGL 1301",
               "PHYS 1443", "HIST 1301", "POLS 2311"}      # get two sections
