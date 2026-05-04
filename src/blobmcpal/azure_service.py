"""ARM-level operations: credential, subscription discovery, storage account listing."""
from __future__ import annotations

from typing import Any, Optional

from azure.identity import AzureCliCredential
from azure.mgmt.storage import StorageManagementClient
from azure.mgmt.subscription import SubscriptionClient
from cachetools import TTLCache

# Credential is created once per process lifetime; AzureCliCredential reads
# from the az login token cache, ensuring group membership claims are present.
_credential: Optional[AzureCliCredential] = None

# Cache ARM results for 5 minutes to avoid redundant ARM calls.
_cache: TTLCache[str, Any] = TTLCache(maxsize=32, ttl=300)


def get_credential() -> AzureCliCredential:
    global _credential
    if _credential is None:
        _credential = AzureCliCredential()
    return _credential


def list_storage_accounts() -> list[dict[str, Any]]:
    """Return all storage accounts visible to the current credential."""
    cache_key = "storage_accounts"
    if cache_key in _cache:
        return _cache[cache_key]  # type: ignore[return-value]

    cred = get_credential()
    sub_client = SubscriptionClient(cred)

    accounts: list[dict[str, Any]] = []
    for sub in sub_client.subscriptions.list():
        mgmt = StorageManagementClient(cred, sub.subscription_id)
        for acct in mgmt.storage_accounts.list():
            resource_group = ""
            if acct.id:
                parts = acct.id.split("/")
                rg_idx = next(
                    (i for i, p in enumerate(parts) if p.lower() == "resourcegroups"),
                    None,
                )
                if rg_idx is not None and rg_idx + 1 < len(parts):
                    resource_group = parts[rg_idx + 1]

            accounts.append(
                {
                    "name": acct.name,
                    "id": acct.id,
                    "subscription_id": sub.subscription_id,
                    "subscription_name": sub.display_name,
                    "location": acct.location,
                    "kind": acct.kind,
                    "sku": acct.sku.name if acct.sku else None,
                    "resource_group": resource_group,
                }
            )

    _cache[cache_key] = accounts
    return accounts
