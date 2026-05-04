"""Azure File Share operations: list shares, directories, files."""
from __future__ import annotations

from typing import Any, Optional

from .context import Session
from .errors import NotConnectedError


def _require_connected(session: Session) -> None:
    if not session.is_connected() or session.share_client is None:
        raise NotConnectedError()


def list_file_shares(session: Session) -> list[dict[str, Any]]:
    _require_connected(session)
    assert session.share_client is not None
    result = []
    for share in session.share_client.list_shares(include_metadata=True):
        quota = None
        usage = None
        if share.get("properties"):
            quota = share["properties"].get("quota")
        result.append(
            {
                "name": share["name"],
                "quota_gb": quota,
                "metadata": share.get("metadata"),
            }
        )
    return result


def list_share_contents(
    session: Session,
    share_name: str,
    directory_path: Optional[str] = None,
    limit: int = 200,
) -> list[dict[str, Any]]:
    """List files and subdirectories at a path within a file share."""
    _require_connected(session)
    assert session.share_client is not None
    limit = min(limit, 500)

    share_client = session.share_client.get_share_client(share_name)
    dir_client = (
        share_client.get_directory_client(directory_path)
        if directory_path
        else share_client.get_directory_client("")
    )

    result = []
    for item in dir_client.list_directories_and_files():
        entry: dict[str, Any] = {
            "name": item["name"],
            "type": "directory" if item["is_directory"] else "file",
        }
        if not item["is_directory"]:
            entry["size_bytes"] = item.get("size")
            props = item.get("file_attributes")
            entry["last_modified"] = (
                item["last_modified"].isoformat()
                if item.get("last_modified")
                else None
            )
        result.append(entry)
        if len(result) >= limit:
            break

    return result


def get_file_metadata(
    session: Session, share_name: str, file_path: str
) -> dict[str, Any]:
    _require_connected(session)
    assert session.share_client is not None

    share_client = session.share_client.get_share_client(share_name)
    file_client = share_client.get_file_client(file_path)
    props = file_client.get_file_properties()

    return {
        "name": props.name,
        "path": file_path,
        "share": share_name,
        "size_bytes": props.size,
        "content_type": (
            props.content_settings.content_type if props.content_settings else None
        ),
        "last_modified": props.last_modified.isoformat() if props.last_modified else None,
        "etag": props.etag,
        "metadata": props.metadata,
    }
