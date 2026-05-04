"""Human-readable error mapping for Azure SDK exceptions."""
from __future__ import annotations

from typing import Any


def friendly(e: Exception) -> dict[str, Any]:
    """Convert an Azure SDK exception into a plain-English error dict."""
    # Import lazily so this module can be imported before azure packages load.
    try:
        from azure.core.exceptions import (
            HttpResponseError,
            ResourceNotFoundError,
            ServiceRequestError,
        )
        from azure.identity import (
            ClientAuthenticationError,
            CredentialUnavailableError,
        )

        if isinstance(e, CredentialUnavailableError):
            return {
                "error": (
                    "Azure credentials not found. Please run 'az login' in a terminal "
                    "and try again. If you are using Docker, ensure your ~/.azure folder "
                    "is mounted with: -v ~/.azure:/home/mcpuser/.azure:ro"
                )
            }

        if isinstance(e, ClientAuthenticationError):
            return {
                "error": (
                    "Azure authentication failed — your session may have expired. "
                    "Please run 'az login' in a terminal and try again."
                )
            }

        if isinstance(e, ResourceNotFoundError):
            return {"error": f"Resource not found: {_msg(e)}"}

        if isinstance(e, HttpResponseError):
            if e.status_code == 403:
                return {
                    "error": (
                        "Permission denied. You may be missing an Azure RBAC role on "
                        "this resource (e.g. 'Storage Blob Data Reader'). Contact your "
                        f"Azure administrator. Details: {_msg(e)}"
                    )
                }
            if e.status_code == 404:
                return {"error": f"Resource not found: {_msg(e)}"}
            return {"error": f"Azure API error ({e.status_code}): {_msg(e)}"}

        if isinstance(e, ServiceRequestError):
            return {
                "error": (
                    "Could not reach Azure. Check your internet connection and try again. "
                    f"Details: {e}"
                )
            }

    except ImportError:
        pass

    return {"error": str(e)}


def _msg(e: HttpResponseError) -> str:  # type: ignore[name-defined]
    return e.message or str(e)


class NotConnectedError(RuntimeError):
    """Raised when a tool is called before connect_account."""

    def __init__(self) -> None:
        super().__init__(
            "Not connected to any storage account. Call 'connect_account' first."
        )


class NoContainerError(RuntimeError):
    """Raised when a blob operation needs a container but none is set."""

    def __init__(self) -> None:
        super().__init__(
            "No container specified. Either call 'connect_account' with a container "
            "name or provide the 'container' parameter."
        )
