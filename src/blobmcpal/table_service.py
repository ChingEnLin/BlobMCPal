"""Azure Table Storage operations: list tables, query entities."""
from __future__ import annotations

from typing import Any, Optional

from .context import Session
from .errors import NotConnectedError


def _require_connected(session: Session) -> None:
    if not session.is_connected() or session.table_client is None:
        raise NotConnectedError()


def _serialise_entity(entity: dict[str, Any]) -> dict[str, Any]:
    """Convert an Azure Table entity to a JSON-safe dict."""
    result: dict[str, Any] = {}
    for k, v in entity.items():
        if hasattr(v, "isoformat"):
            result[k] = v.isoformat()
        else:
            result[k] = v
    return result


def list_tables(session: Session) -> list[dict[str, Any]]:
    _require_connected(session)
    assert session.table_client is not None
    return [{"name": t["name"]} for t in session.table_client.list_tables()]


def query_table(
    session: Session,
    table_name: str,
    filter: Optional[str] = None,
    select: Optional[list[str]] = None,
    limit: int = 100,
) -> list[dict[str, Any]]:
    """Query table entities with an optional OData filter expression."""
    _require_connected(session)
    assert session.table_client is not None
    limit = min(limit, 200)

    tc = session.table_client.get_table_client(table_name)
    results = []
    for entity in tc.list_entities(
        query_filter=filter,
        select=select,
        results_per_page=limit,
    ):
        results.append(_serialise_entity(dict(entity)))
        if len(results) >= limit:
            break

    return results


def get_table_entity(
    session: Session, table_name: str, partition_key: str, row_key: str
) -> dict[str, Any]:
    _require_connected(session)
    assert session.table_client is not None

    tc = session.table_client.get_table_client(table_name)
    entity = tc.get_entity(partition_key=partition_key, row_key=row_key)
    return _serialise_entity(dict(entity))
