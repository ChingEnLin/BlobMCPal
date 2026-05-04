"""In-process session state shared across all service modules."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from azure.data.tables import TableServiceClient
    from azure.storage.blob import BlobServiceClient
    from azure.storage.fileshare import ShareServiceClient
    from azure.storage.queue import QueueServiceClient


@dataclass
class Session:
    account_name: Optional[str] = None
    container_name: Optional[str] = None
    blob_client: Optional["BlobServiceClient"] = field(default=None, repr=False)
    queue_client: Optional["QueueServiceClient"] = field(default=None, repr=False)
    share_client: Optional["ShareServiceClient"] = field(default=None, repr=False)
    table_client: Optional["TableServiceClient"] = field(default=None, repr=False)

    def is_connected(self) -> bool:
        return self.account_name is not None

    def clear(self) -> None:
        self.account_name = None
        self.container_name = None
        self.blob_client = None
        self.queue_client = None
        self.share_client = None
        self.table_client = None


_session = Session()


def get() -> Session:
    return _session
