"""Intent router (Kyle).

Classifies each student message into exactly one Intent, which the orchestrator
maps to a handler. Deliberately a narrow LLM classification task — small local
models handle this reliably where free-form tool-calling agents do not.
"""

from enum import Enum


class Intent(str, Enum):
    EXACT_QUERY = "exact_query"          # prereqs, record, schedule lookups -> SQL chain
    SEMANTIC_QUERY = "semantic_query"    # course content / policy questions -> RAG chain
    GENERATE_PLAN = "generate_plan"      # "build my degree plan"
    MODIFY_PLAN = "modify_plan"          # add/drop classes, change credit load
    SWITCH_MAJOR = "switch_major"        # advising dialog + plan comparison
    STATUS_QUERY = "status_query"        # "how far along is my plan?" (exact-ish)
    OTHER = "other"                      # fallback -> general advising chat


def route(message: str, history: list[dict] | None = None) -> Intent:
    """Classify `message` into an Intent using the configured chat model.

    Prompt the model with the Intent values + 1-line descriptions + the last
    couple of history turns (so follow-ups like "what about 3 classes instead?"
    still route to MODIFY_PLAN). Parse the single-token response back to Intent;
    unparseable answers => Intent.OTHER.

    TODO (Kyle): implement.
    """
    raise NotImplementedError("TODO Kyle: implement route")
