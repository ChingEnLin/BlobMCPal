"""Azure Queue Storage operations: list queues, peek messages."""
from __future__ import annotations

from typing import Any

from .context import Session
from .errors import NotConnectedError


def _require_connected(session: Session) -> None:
    if not session.is_connected() or session.queue_client is None:
        raise NotConnectedError()


def list_queues(session: Session) -> list[dict[str, Any]]:
    _require_connected(session)
    assert session.queue_client is not None
    result = []
    for q in session.queue_client.list_queues(include_metadata=True):
        result.append(
            {
                "name": q["name"],
                "metadata": q.get("metadata"),
            }
        )
    return result


def get_queue_properties(session: Session, queue_name: str) -> dict[str, Any]:
    _require_connected(session)
    assert session.queue_client is not None
    qc = session.queue_client.get_queue_client(queue_name)
    props = qc.get_queue_properties()
    return {
        "name": queue_name,
        "approximate_message_count": props.approximate_message_count,
        "metadata": props.metadata,
    }


def peek_messages(
    session: Session, queue_name: str, max_messages: int = 10
) -> list[dict[str, Any]]:
    """Non-destructively peek up to 32 messages from the front of a queue."""
    _require_connected(session)
    assert session.queue_client is not None
    max_messages = min(max_messages, 32)
    qc = session.queue_client.get_queue_client(queue_name)
    result = []
    for msg in qc.peek_messages(max_messages=max_messages):
        result.append(
            {
                "id": msg.id,
                "body": msg.content,
                "inserted_on": msg.inserted_on.isoformat() if msg.inserted_on else None,
                "expires_on": msg.expires_on.isoformat() if msg.expires_on else None,
                "dequeue_count": msg.dequeue_count,
            }
        )
    return result
