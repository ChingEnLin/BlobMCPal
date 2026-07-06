"""BlobMCPal MCP server — entry point and all tool definitions."""
from __future__ import annotations

import json
from typing import Any, Optional

from mcp.server.fastmcp import FastMCP

from . import azure_service, blob_service, file_service, queue_service, table_service
from . import context as ctx
from .errors import NotConnectedError, NoContainerError, friendly

mcp = FastMCP(
    "BlobMCPal",
    instructions=(
        "BlobMCPal gives you read-only access to Azure Storage Accounts "
        "(Blob, Queue, File Share, Table) via the user's 'az login' credential. "
        "Typical flow: call 'list_storage_accounts', then 'connect_account', "
        "then explore containers/blobs/queues/shares/tables. "
        "Call 'show_context' at any time to see the active account and container."
    ),
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _ok(data: Any) -> str:
    return json.dumps(data, ensure_ascii=False, default=str)


def _err(msg: str) -> str:
    return json.dumps({"error": msg})


def _run(fn: Any, *args: Any, **kwargs: Any) -> str:
    try:
        return _ok(fn(*args, **kwargs))
    except (NotConnectedError, NoContainerError) as e:
        return _err(str(e))
    except Exception as e:
        return _ok(friendly(e))


# ---------------------------------------------------------------------------
# Discovery tools
# ---------------------------------------------------------------------------


@mcp.tool()
def list_storage_accounts() -> str:
    """
    List all Azure Storage accounts visible to the current credential.

    Returns name, ARM ID, subscription, location, kind, and SKU for each account.
    Results are cached for 5 minutes.
    """
    return _run(azure_service.list_storage_accounts)


@mcp.tool()
def connect_account(account_name: str, container: Optional[str] = None) -> str:
    """
    Connect to an Azure Storage account and initialise all service clients.

    Must be called before any blob, queue, file, or table operation.
    Optionally sets a default container so later blob calls don't need
    to specify 'container' every time.

    Args:
        account_name: The storage account name (e.g. 'prodstoragewe').
        container: Optional default blob container name.
    """
    try:
        cred = azure_service.get_credential()
        session = ctx.get()

        from azure.data.tables import TableServiceClient
        from azure.storage.blob import BlobServiceClient
        from azure.storage.fileshare import ShareServiceClient
        from azure.storage.queue import QueueServiceClient

        session.blob_client = BlobServiceClient(
            account_url=f"https://{account_name}.blob.core.windows.net",
            credential=cred,
            token_intent="storage",
        )
        session.queue_client = QueueServiceClient(
            account_url=f"https://{account_name}.queue.core.windows.net",
            credential=cred,
            token_intent="storage",
        )
        # token_intent="backup" is required by ShareServiceClient when using a TokenCredential.
        # It grants access via the 'Storage File Data Privileged Reader' RBAC role,
        # which bypasses file/directory ACLs in favour of Azure RBAC.
        session.share_client = ShareServiceClient(
            account_url=f"https://{account_name}.file.core.windows.net",
            credential=cred,
            token_intent="backup",
        )
        session.table_client = TableServiceClient(
            endpoint=f"https://{account_name}.table.core.windows.net",
            credential=cred,
        )
        session.account_name = account_name
        session.container_name = container

        return _ok(
            {
                "connected": True,
                "account_name": account_name,
                "default_container": container,
                "message": (
                    f"Connected to '{account_name}'."
                    + (f" Default container set to '{container}'." if container else "")
                ),
            }
        )
    except Exception as e:
        return _ok(friendly(e))


@mcp.tool()
def list_containers() -> str:
    """
    List all blob containers in the active storage account.

    Shows container name, public access level, and last modified time.
    Requires connect_account to be called first.
    """
    return _run(blob_service.list_containers, ctx.get())


@mcp.tool()
def list_queues() -> str:
    """
    List all queues in the active storage account.

    Requires connect_account to be called first.
    """
    return _run(queue_service.list_queues, ctx.get())


@mcp.tool()
def list_file_shares() -> str:
    """
    List all file shares in the active storage account with quota information.

    Requires connect_account to be called first.
    """
    return _run(file_service.list_file_shares, ctx.get())


@mcp.tool()
def list_tables() -> str:
    """
    List all tables in the active storage account.

    Requires connect_account to be called first.
    """
    return _run(table_service.list_tables, ctx.get())


# ---------------------------------------------------------------------------
# Blob inspection tools
# ---------------------------------------------------------------------------


@mcp.tool()
def list_blobs(
    container: Optional[str] = None,
    prefix: Optional[str] = None,
    limit: int = 100,
) -> str:
    """
    List blobs in a container, optionally filtered by name prefix.

    Returns blob name, size, content type, last modified timestamp, and tags.
    Limit is capped at 500.

    Args:
        container: Container name. Uses session default if omitted.
        prefix: Name prefix filter (e.g. 'exports/2026-04-').
        limit: Maximum number of blobs to return (default 100, max 500).
    """
    return _run(blob_service.list_blobs, ctx.get(), container, prefix, limit)


@mcp.tool()
def get_blob_metadata(blob_name: str, container: Optional[str] = None) -> str:
    """
    Get full metadata and properties for a specific blob.

    Returns content type, size, ETag, last modified, custom metadata key-value
    pairs, tags, lease status, and storage tier.

    Args:
        blob_name: Full blob name including any virtual directory path.
        container: Container name. Uses session default if omitted.
    """
    return _run(blob_service.get_blob_metadata, ctx.get(), blob_name, container)


@mcp.tool()
def get_blob_content(
    blob_name: str,
    container: Optional[str] = None,
    max_bytes: int = 32768,
) -> str:
    """
    Download and return blob content.

    Text blobs (text/*, application/json, etc.) are returned as UTF-8 strings.
    Binary blobs are returned as base64. Images, PDFs, and audio/video return
    metadata only (no binary download). Content is truncated at max_bytes
    (default 32 KB, configurable up to 5 MB).

    Args:
        blob_name: Full blob name including any virtual directory path.
        container: Container name. Uses session default if omitted.
        max_bytes: Maximum bytes to download (default 32768, max 5242880).
    """
    return _run(blob_service.get_blob_content, ctx.get(), blob_name, container, max_bytes)


@mcp.tool()
def search_blobs(
    prefix: Optional[str] = None,
    tag_filter: Optional[str] = None,
    container: Optional[str] = None,
    limit: int = 100,
) -> str:
    """
    Search blobs by name prefix and/or Blob Index Tag filter expression.

    When tag_filter is provided, uses Azure Blob Index Tags search
    (requires the storage account to have blob index tags enabled).
    Example tag_filter: "environment = 'production' AND department = 'ops'"
    Without tag_filter, performs a prefix search equivalent to list_blobs.
    Limit is capped at 200.

    Args:
        prefix: Name prefix filter.
        tag_filter: OData-style tag filter expression.
        container: Scope search to this container. Uses session default if omitted.
        limit: Maximum results (default 100, max 200).
    """
    return _run(
        blob_service.search_blobs, ctx.get(), prefix, tag_filter, container, limit
    )


# ---------------------------------------------------------------------------
# Queue inspection tools
# ---------------------------------------------------------------------------


@mcp.tool()
def peek_messages(queue_name: str, max_messages: int = 10) -> str:
    """
    Non-destructively peek at messages in a queue (does not dequeue them).

    Returns message body, insertion time, expiry time, and dequeue count.
    Maximum 32 messages per call.

    Args:
        queue_name: Name of the queue.
        max_messages: Number of messages to peek (default 10, max 32).
    """
    return _run(queue_service.peek_messages, ctx.get(), queue_name, max_messages)


@mcp.tool()
def get_queue_properties(queue_name: str) -> str:
    """
    Get properties of a queue, including approximate message count.

    Args:
        queue_name: Name of the queue.
    """
    return _run(queue_service.get_queue_properties, ctx.get(), queue_name)


# ---------------------------------------------------------------------------
# File Share inspection tools
# ---------------------------------------------------------------------------


@mcp.tool()
def list_share_contents(
    share_name: str,
    directory_path: Optional[str] = None,
    limit: int = 200,
) -> str:
    """
    List files and subdirectories at a path within a file share.

    Returns item name, type (file/directory), size, and last modified time.
    Limit is capped at 500.

    Args:
        share_name: Name of the file share.
        directory_path: Path within the share (e.g. 'reports/2026'). Root if omitted.
        limit: Maximum items to return (default 200, max 500).
    """
    return _run(
        file_service.list_share_contents, ctx.get(), share_name, directory_path, limit
    )


@mcp.tool()
def get_file_metadata(share_name: str, file_path: str) -> str:
    """
    Get properties and metadata for a specific file in a file share.

    Returns size, content type, last modified time, ETag, and custom metadata.

    Args:
        share_name: Name of the file share.
        file_path: Full path to the file (e.g. 'reports/2026/summary.csv').
    """
    return _run(file_service.get_file_metadata, ctx.get(), share_name, file_path)


# ---------------------------------------------------------------------------
# Table inspection tools
# ---------------------------------------------------------------------------


@mcp.tool()
def query_table(
    table_name: str,
    filter: Optional[str] = None,
    select: Optional[str] = None,
    limit: int = 100,
) -> str:
    """
    Query entities in an Azure Table with an optional OData filter.

    Returns entities as a JSON array. Limit is capped at 200.
    Example filter: "PartitionKey eq 'device-001' and Status eq 'active'"
    Example select (comma-separated fields): "PartitionKey,RowKey,Status,Timestamp"

    Args:
        table_name: Name of the table.
        filter: OData filter expression.
        select: Comma-separated list of property names to return.
        limit: Maximum entities to return (default 100, max 200).
    """
    select_list = [s.strip() for s in select.split(",")] if select else None
    return _run(
        table_service.query_table, ctx.get(), table_name, filter, select_list, limit
    )


@mcp.tool()
def get_table_entity(table_name: str, partition_key: str, row_key: str) -> str:
    """
    Retrieve a single entity from a table by its partition key and row key.

    Args:
        table_name: Name of the table.
        partition_key: The entity's PartitionKey.
        row_key: The entity's RowKey.
    """
    return _run(
        table_service.get_table_entity, ctx.get(), table_name, partition_key, row_key
    )


# ---------------------------------------------------------------------------
# Auth check tool
# ---------------------------------------------------------------------------


@mcp.tool()
def check_auth() -> str:
    """
    Check whether the Azure CLI credential is available and working for Azure Storage access.

    Attempts to list subscriptions using the current az login session.
    Call this first if you are getting authentication errors, or to confirm
    the server started correctly.
    """
    try:
        cred = azure_service.get_credential()
        from azure.mgmt.subscription import SubscriptionClient

        subs = list(SubscriptionClient(cred).subscriptions.list())
        return _ok(
            {
                "ok": True,
                "subscription_count": len(subs),
                "subscriptions": [
                    {"id": s.subscription_id, "name": s.display_name} for s in subs
                ],
                "message": (
                    f"Azure credential is working. Found {len(subs)} subscription(s)."
                ),
            }
        )
    except Exception as e:
        result = friendly(e)
        result["ok"] = False
        return _ok(result)


# ---------------------------------------------------------------------------
# Session tools
# ---------------------------------------------------------------------------


@mcp.tool()
def show_context() -> str:
    """
    Show the currently active storage account and default container.

    Use this to confirm which account you are connected to before running
    blob, queue, file, or table operations.
    """
    session = ctx.get()
    return _ok(
        {
            "connected": session.is_connected(),
            "account_name": session.account_name,
            "default_container": session.container_name,
        }
    )


@mcp.tool()
def set_context(container: Optional[str] = None) -> str:
    """
    Update Azure Storage session settings without reconnecting to the account.

    Args:
        container: New default container name. Pass null to clear.
    """
    session = ctx.get()
    if not session.is_connected():
        return _err("Not connected to any storage account. Call 'connect_account' first.")
    session.container_name = container
    return _ok(
        {
            "account_name": session.account_name,
            "default_container": session.container_name,
        }
    )


@mcp.tool()
def clear_context() -> str:
    """
    Disconnect from the current storage account and clear all session state.

    After calling this, you must call 'connect_account' again before running
    any storage operations.
    """
    ctx.get().clear()
    return _ok({"cleared": True, "message": "Disconnected. Session state cleared."})


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def main() -> None:
    mcp.run()


if __name__ == "__main__":
    main()
