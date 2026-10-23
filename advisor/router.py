"""Intent router (Kyle).

Classifies each student message into exactly one Intent, which the orchestrator
maps to a handler. Deliberately a narrow LLM classification task — small local
models handle this reliably where free-form tool-calling agents do not.
"""

import re
from enum import Enum


class Intent(str, Enum):
    EXACT_QUERY = "exact_query"          # prereqs, record, schedule lookups -> SQL chain
    SEMANTIC_QUERY = "semantic_query"    # course content / policy questions -> RAG chain
    GENERATE_PLAN = "generate_plan"      # "build my degree plan"
    MODIFY_PLAN = "modify_plan"          # add/drop classes, change credit load
    SWITCH_MAJOR = "switch_major"        # advising dialog + plan comparison
    STATUS_QUERY = "status_query"        # "how far along is my plan?" (exact-ish)
    CHECK_ELIGIBILITY = "check_eligibility"  # "can I take X next semester?" -> 6-check verifier
    OTHER = "other"                      # fallback -> general advising chat


_PROMPT = """You classify messages to an academic advising assistant into exactly one intent.

Intents:
- exact_query: factual lookups in the database — prerequisites for a course, class schedule/section times, the student's record or completed courses
- semantic_query: open-ended questions about course content/topics, degree requirements, or policies that need document search
- generate_plan: asking for a degree plan to be built or generated
- modify_plan: changing an existing plan — add/drop/replace a course, change credit load or number of classes
- switch_major: considering switching major/program/concentration, or asking what would change
- status_query: progress/status of the current degree plan or degree completion
- check_eligibility: asking whether they can/should take a specific course (prerequisite + schedule check)
- other: greetings, thanks, or anything else

Examples:
Message: "prereqs for CSE 3310" -> exact_query
Message: "when is CSE 3310 offered" -> exact_query
Message: "what is machine learning" -> semantic_query
Message: "which classes teach security" -> semantic_query
Message: "make me a degree plan" -> generate_plan
Message: "drop CSE 3310" -> modify_plan
Message: "can I take 3 classes instead" -> modify_plan
Message: "I want to switch to software engineering" -> switch_major
Message: "am I on track to graduate" -> status_query
Message: "can I take CSE 4344 next semester" -> check_eligibility
Message: "hello" -> other

Classify ONLY the final Message below. Use the recent conversation solely to
resolve ambiguous follow-ups (e.g. "what about 3 classes instead?") — do not
let it change the topic of the new message.

Recent conversation (may be empty):
{history}

Message: {message}

Reply with ONLY the intent name, nothing else."""


def _strip_think(text: str) -> str:
    """Remove <think>...</think> blocks emitted by reasoning models."""
    return re.sub(r"<think>.*?</think>", "", text, flags=re.S).strip()


# --- deterministic pre-pass -------------------------------------------------
# Cheap keyword rules catch the unambiguous cases before any LLM call — most
# demo-script queries never hit the model at all. Rules are checked in order;
# most specific intents first.

_COURSE = r"[A-Z]{2,4}\s*\d{4}"

_RULES: list[tuple[re.Pattern, Intent]] = [
    # modify_plan: add/drop/replace courses or change course load
    (re.compile(rf"\b(?:add|drop|remove|replace|swap)\b.*{_COURSE}|\b{_COURSE}.*\b(?:add|drop|remove|replace|swap)\b", re.I), Intent.MODIFY_PLAN),
    (re.compile(r"\b\d+\s*(?:classes|courses)\b.*\b(?:instead|per semester|each semester|next semester)\b|\b(?:instead|change).*\b\d+\s*(?:classes|courses)\b", re.I), Intent.MODIFY_PLAN),
    # switch_major: talking about changing program/major/concentration
    (re.compile(r"\b(?:switch|change|transfer)\b.*\b(?:major|program|concentration|degree)\b|\b(?:major|program|concentration)\b.*\b(?:switch|change|transfer)\b|thinking of switching|switching to", re.I), Intent.SWITCH_MAJOR),
    # generate_plan: asking for a plan to be built
    (re.compile(r"\b(?:generate|build|create|make|plan out|design)\b.*\b(?:degree\s*)?plan\b|\bdegree plan\b.*\b(?:generate|build|create|make|for me)\b", re.I), Intent.GENERATE_PLAN),
    (re.compile(r"\b(?:what|which)\b.*\b(?:should|do|need to|must)\s+(?:i\s+)?take\b|\b(?:take|needed?|required)\b.*\bgraduat|\bclasses? to take\b", re.I), Intent.GENERATE_PLAN),
    # check_eligibility: "can I take X?"
    (re.compile(rf"\b(?:can|could|should|am i (?:able|eligible|allowed) to|may i)\b.*\b(?:take|enroll in|register for|add)\b.*{_COURSE}|\b(?:eligible|prerequisites? (?:met|satisfied))\b.*{_COURSE}", re.I), Intent.CHECK_ELIGIBILITY),
    # semantic_query: degree requirements / program / policy questions
    (re.compile(r"\b(?:degree\s+)?requirements?\b|\bconcentration\b|\belectives?\b|\bpolicy\b|\bcatalog\b|\bhow does\b.*\b(?:program|degree|concentration|major)\b", re.I), Intent.SEMANTIC_QUERY),
    # exact_query: structured lookups
    (re.compile(r"\bprereq|\bschedule\b|\bsection\b|offered|what time|meeting time", re.I), Intent.EXACT_QUERY),
    (re.compile(r"\b(?:my|show)\b.*\b(?:record|transcript|completed|enrolled|enrollment)\b|\bwhat.*\b(?:have i|i've)\s+(?:taken|completed)\b", re.I), Intent.EXACT_QUERY),
    # status_query: progress toward degree / plan status
    (re.compile(r"\b(?:how far|progress|status|on track|remaining|left to take|graduat)", re.I), Intent.STATUS_QUERY),
    # semantic_query: open-ended "which courses cover X" questions
    (re.compile(r"\b(?:which|what)\b.*\b(?:courses?|classes?)\b.*\b(?:cover|about|teach|learn|topics?|involv|focus)\b", re.I), Intent.SEMANTIC_QUERY),
]


def _keyword_route(message: str) -> Intent | None:
    """Deterministic intent match.

    Args:
        message: Raw student text.

    Returns:
        The Intent for the first matching rule in `_RULES` order (rules are
        arranged most-specific first, e.g. MODIFY_PLAN before GENERATE_PLAN),
        or None when no rule fires — meaning the message is ambiguous and the
        LLM fallback should classify it.
    """
    for pattern, intent in _RULES:
        if pattern.search(message):
            return intent
    return None


def route(message: str, history: list[dict] | None = None) -> Intent:
    """Classify `message` into an Intent (spec req 3's query dispatch).

    Two stages: (1) a deterministic keyword pass catches unambiguous phrasing
    with zero latency; (2) anything left goes to a small fast LLM
    (get_router_model — tiny by default because routing latency is
    user-visible on every message).

    Args:
        message: Raw student text for this turn.
        history: Prior turns as [{'role', 'content'}], newest last. Only the
            last ~4 are sent to the LLM, and the prompt tells it to use them
            solely to resolve ambiguous follow-ups like "what about 3 classes
            instead?" — never to reclassify the old topic.

    Returns:
        An Intent. The LLM's single-token reply is matched by substring over
        Intent values (first match wins, in enum order). Unparseable answers
        and any backend failure fall back to Intent.OTHER, which always has
        a working handler — routing can degrade but never crash the turn.
    """
    from .config import get_router_model
    from .tracing import trace

    if (kw := _keyword_route(message)) is not None:
        trace("router_keyword", intent=kw.value)
        return kw

    recent = "\n".join(
        f"{m['role']}: {m['content'][:200]}" for m in (history or [])[-4:]
    ) or "(none)"
    try:
        resp = get_router_model().invoke(
            _PROMPT.format(history=recent, message=message)
        )
        text = _strip_think(resp.content if hasattr(resp, "content") else str(resp)).lower()
        trace("router_raw", response=text[:300])
    except Exception as e:  # backend down / model missing -> safe fallback
        trace("router_error", error=str(e))
        return Intent.OTHER
    for intent in Intent:
        if intent.value in text:
            return intent
    return Intent.OTHER
