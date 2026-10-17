"""Orchestrator (Kyle): the LangChain glue.

handle_message() is the single entry point the UI calls per chat turn:
  1. persist + trace the user message (memory, tracing)
  2. route -> Intent (router)
  3. dispatch to a handler (chains / planner tools / advising dialog)
  4. persist + trace the assistant reply and return it

Handlers are intentionally thin over tools.py so the same operations are also
exposed as LangChain tools for a future agent executor.
"""

from . import chains, compare, memory, planner, router, tools, tracing


def handle_message(student_id: str, message: str, history: list[dict] | None = None) -> str:
    """Process one chat turn and return the assistant's reply text."""
    tracing.trace("user_msg", student_id=student_id, message=message)
    memory.add_message(student_id, "user", message)

    try:
        intent = router.route(message, history)
    except NotImplementedError:
        reply = ("Router isn't implemented yet (Kyle). Once `route()` works, "
                 "this message will be dispatched to a handler.")
        return _finish(student_id, reply, intent="unrouted")

    tracing.trace("intent", student_id=student_id, intent=intent.value)

    try:
        reply = _dispatch(student_id, message, intent, history)
    except NotImplementedError as e:
        reply = f"That request routes to **{intent.value}**, which isn't implemented yet.\n\n`{e}`"
    return _finish(student_id, reply, intent=intent.value)


def _dispatch(student_id: str, message: str, intent: router.Intent, history) -> str:
    if intent == router.Intent.EXACT_QUERY or intent == router.Intent.STATUS_QUERY:
        return chains.answer_exact(message, student_id)
    if intent == router.Intent.SEMANTIC_QUERY:
        return chains.answer_semantic(message, student_id)
    if intent == router.Intent.GENERATE_PLAN:
        raise NotImplementedError("TODO Kyle: call tools.generate_degree_plan and format the plan")
    if intent == router.Intent.MODIFY_PLAN:
        raise NotImplementedError("TODO Kyle: parse add/drop/load change -> tools.modify_plan")
    if intent == router.Intent.SWITCH_MAJOR:
        raise NotImplementedError("TODO Kyle: multi-turn advising dialog -> tools.switch_major + diff")
    raise NotImplementedError("TODO Kyle: OTHER fallback — general advising answer via chat model")


def _finish(student_id: str, reply: str, intent: str) -> str:
    memory.add_message(student_id, "assistant", reply)
    tracing.trace("assistant_msg", student_id=student_id, intent=intent, reply=reply[:2000])
    return reply
