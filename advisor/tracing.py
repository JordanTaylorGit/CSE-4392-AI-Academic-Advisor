"""Execution-trace logger -> logs/traces.jsonl (required deliverable).

Every significant event — user message, routed intent, tool call, retrieval
hits, LLM prompt/response — is appended as one JSON line. Person E owns the
rendering of this log for the final zip.
"""

import json
from datetime import datetime, timezone
from typing import Any

from .paths import LOGS_DIR, TRACE_LOG


def trace(event: str, **fields: Any) -> None:
    """Append one trace record. `event` names the kind: 'user_msg',
    'intent', 'tool_call', 'retrieval', 'llm_response', 'error', ..."""
    LOGS_DIR.mkdir(exist_ok=True)
    record = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "event": event,
        **fields,
    }
    with TRACE_LOG.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False, default=str) + "\n")
