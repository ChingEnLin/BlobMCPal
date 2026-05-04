"""Azure Blob Storage operations: containers, blobs, content preview."""
from __future__ import annotations

import base64
from typing import Any, Optional

from .context import Session
from .errors import NoContainerError, NotConnectedError

_TEXT_TYPES = {
    "text/",
    "application/json",
    "application/xml",
    "application/csv",
    "application/x-ndjson",
    "application/ld+json",
    "application/x-yaml",
    "application/toml",
}

_DEFAULT_MAX_BYTES = 32 * 1024  # 32 KB
_HARD_MAX_BYTES = 5 * 1024 * 1024  # 5 MB


def _is_text(content_type: Optional[str]) -> bool:
    if not content_type:
        return False
    ct = content_type.lower().split(";")[0].strip()
    return any(ct.startswith(t) if t.endswith("/") else ct == t for t in _TEXT_TYPES)


def _require_connected(session: Session) -> None:
    if not session.is_connected() or session.blob_client is None:
        raise NotConnectedError()


def _resolve_container(session: Session, container: Optional[str]) -> str:
    name = container or session.container_name
    if not name:
        raise NoContainerError()
    return name


def list_containers(session: Session) -> list[dict[str, Any]]:
    _require_connected(session)
    assert session.blob_client is not None
    result = []
    for c in session.blob_client.list_containers(include_metadata=True):
        result.append(
            {
                "name": c["name"],
                "public_access": c.get("properties", {}).get("public_access"),
                "last_modified": (
                    c["properties"]["last_modified"].isoformat()
                    if c.get("properties", {}).get("last_modified")
                    else None
                ),
                "metadata": c.get("metadata"),
            }
        )
    return result


def list_blobs(
    session: Session,
    container: Optional[str] = None,
    prefix: Optional[str] = None,
    limit: int = 100,
) -> list[dict[str, Any]]:
    _require_connected(session)
    assert session.blob_client is not None
    container_name = _resolve_container(session, container)
    limit = min(limit, 500)

    cc = session.blob_client.get_container_client(container_name)
    result = []
    for blob in cc.list_blobs(name_starts_with=prefix):
        result.append(
            {
                "name": blob.name,
                "size_bytes": blob.size,
                "content_type": (
                    blob.content_settings.content_type
                    if blob.content_settings
                    else None
                ),
                "last_modified": (
                    blob.last_modified.isoformat() if blob.last_modified else None
                ),
                "etag": blob.etag,
            }
        )
        if len(result) >= limit:
            break

    return result


def get_blob_metadata(
    session: Session, blob_name: str, container: Optional[str] = None
) -> dict[str, Any]:
    _require_connected(session)
    assert session.blob_client is not None
    container_name = _resolve_container(session, container)
    bc = session.blob_client.get_blob_client(container=container_name, blob=blob_name)
    props = bc.get_blob_properties()

    return {
        "name": props.name,
        "container": container_name,
        "size_bytes": props.size,
        "content_type": (
            props.content_settings.content_type if props.content_settings else None
        ),
        "content_encoding": (
            props.content_settings.content_encoding if props.content_settings else None
        ),
        "last_modified": props.last_modified.isoformat() if props.last_modified else None,
        "created_on": props.creation_time.isoformat() if props.creation_time else None,
        "etag": props.etag,
        "lease_status": props.lease.status if props.lease else None,
        "tier": props.blob_tier,
        "metadata": props.metadata,
    }


def get_blob_content(
    session: Session,
    blob_name: str,
    container: Optional[str] = None,
    max_bytes: int = _DEFAULT_MAX_BYTES,
) -> dict[str, Any]:
    _require_connected(session)
    assert session.blob_client is not None
    container_name = _resolve_container(session, container)
    max_bytes = min(max_bytes, _HARD_MAX_BYTES)

    bc = session.blob_client.get_blob_client(container=container_name, blob=blob_name)
    props = bc.get_blob_properties()
    content_type = (
        props.content_settings.content_type if props.content_settings else None
    ) or ""
    size = props.size or 0

    # For large binary types (images, PDFs, videos) don't download — return metadata.
    ct_lower = content_type.lower()
    is_large_binary = any(
        ct_lower.startswith(p) for p in ("image/", "video/", "audio/")
    ) or ct_lower == "application/pdf"

    if is_large_binary:
        return {
            "blob_name": blob_name,
            "container": container_name,
            "content_type": content_type,
            "size_bytes": size,
            "content": None,
            "encoding": None,
            "note": (
                f"Binary content ({content_type}) is not returned inline. "
                "Use the Azure Portal or Azure Storage Explorer to download this blob."
            ),
        }

    stream = bc.download_blob(offset=0, length=max_bytes)
    raw: bytes = stream.readall()
    truncated = size > max_bytes

    if _is_text(content_type):
        try:
            text = raw.decode("utf-8", errors="replace")
            return {
                "blob_name": blob_name,
                "container": container_name,
                "content_type": content_type,
                "size_bytes": size,
                "content": text,
                "encoding": "utf-8",
                "truncated": truncated,
                "truncated_at_bytes": max_bytes if truncated else None,
                "note": (
                    f"Content truncated at {max_bytes:,} bytes. "
                    "Increase max_bytes (up to 5 MB) to read more."
                    if truncated
                    else None
                ),
            }
        except Exception:
            pass  # fall through to base64

    b64 = base64.b64encode(raw).decode("ascii")
    return {
        "blob_name": blob_name,
        "container": container_name,
        "content_type": content_type,
        "size_bytes": size,
        "content": b64,
        "encoding": "base64",
        "truncated": truncated,
        "truncated_at_bytes": max_bytes if truncated else None,
        "note": (
            f"Content truncated at {max_bytes:,} bytes. "
            "Increase max_bytes (up to 5 MB) to read more."
            if truncated
            else None
        ),
    }


def search_blobs(
    session: Session,
    prefix: Optional[str] = None,
    tag_filter: Optional[str] = None,
    container: Optional[str] = None,
    limit: int = 100,
) -> list[dict[str, Any]]:
    """Search blobs by name prefix and/or Blob Index Tag filter expression."""
    _require_connected(session)
    assert session.blob_client is not None
    limit = min(limit, 200)

    if tag_filter:
        # Blob Index Tag search requires 'Storage Blob Index Tags Reader' RBAC role.
        # Wrap in try/except so a missing role returns a clear message instead of a crash.
        try:
            filter_expr = tag_filter
            if container:
                filter_expr = f"@container = '{container}' AND {tag_filter}"

            result = []
            for item in session.blob_client.find_blobs_by_tags(filter_expression=filter_expr):
                result.append(
                    {
                        "name": item["name"],
                        "container": item["container_name"],
                    }
                )
                if len(result) >= limit:
                    break
            return result
        except Exception as e:
            from .errors import friendly
            raise RuntimeError(
                friendly(e).get("error", str(e))
                + " Note: tag-based search requires the 'Storage Blob Index Tags Reader' RBAC role."
            ) from e

    # Prefix-only search — fall back to list_blobs.
    return list_blobs(session, container=container, prefix=prefix, limit=limit)
