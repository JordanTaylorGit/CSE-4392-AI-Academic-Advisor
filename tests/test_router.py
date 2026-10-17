"""Router keyword pre-pass tests — deterministic, no LLM required."""

import pytest

from advisor.router import Intent, _keyword_route

CASES = [
    ("What are the prerequisites for CSE 3310?", Intent.EXACT_QUERY),
    ("when is CSE 4344 offered?", Intent.EXACT_QUERY),
    ("show my record", Intent.EXACT_QUERY),
    ("Which courses cover machine learning?", Intent.SEMANTIC_QUERY),
    ("how does the cybersecurity concentration work?", Intent.SEMANTIC_QUERY),
    ("Build my degree plan", Intent.GENERATE_PLAN),
    ("what should I take to graduate?", Intent.GENERATE_PLAN),
    ("classes to take for this and next semester", Intent.GENERATE_PLAN),
    ("Drop CSE 3310 and add CSE 3302", Intent.MODIFY_PLAN),
    ("what about taking 3 classes next semester instead?", Intent.MODIFY_PLAN),
    ("I am thinking of switching to software engineering", Intent.SWITCH_MAJOR),
    ("can I take CSE 4344 next semester?", Intent.CHECK_ELIGIBILITY),
    ("How far along is my plan?", Intent.STATUS_QUERY),
]


@pytest.mark.parametrize("message,expected", CASES)
def test_keyword_route(message, expected):
    assert _keyword_route(message) == expected


def test_keyword_route_returns_none_for_ambiguous():
    assert _keyword_route("hey there") is None
    assert _keyword_route("what is machine learning?") is None
