# BlobMCPal

An MCP server that lets any MCP-compatible AI tool talk directly to your Azure Storage accounts — no connection strings, no SAS tokens, no secrets in config files. Just `az login` and go.

Works with **Claude Desktop**, **GitHub Copilot in VS Code**, and any other tool that supports the Model Context Protocol.

**You will never paste a storage account key into a config file.** BlobMCPal authenticates using the Azure CLI session already on your machine. Nothing to rotate, nothing to leak.

**You don't need to know how Azure Storage is structured.** Just ask your AI tool *"What's in this storage account?"* and it will list your containers, blobs, queues, file shares, and tables before you even know what to look for.

## Background

This project is the sibling to [QueryMCPal](https://github.com/ChingEnLin/QueryMCPal) — the same philosophy of AI-powered Azure resource exploration via MCP stdio, applied to Azure Blob Storage, File Shares, Queues, and Tables instead of Cosmos DB.

| | [QueryMCPal](https://github.com/ChingEnLin/QueryMCPal) | BlobMCPal |
|---|---|---|
| **Storage** | Azure Cosmos DB (MongoDB API) | Azure Blob, Queue, File Share, Table |
| **Operations** | Read-only queries and aggregations | Read-only browse and inspect |
| **Auth** | `az login` (your existing CLI session) | `az login` (your existing CLI session) |
| **Infrastructure** | Docker on your Mac | Docker on your Mac |

## Features

- **Auto-discovery** — lists every storage account your Azure credential can see, across all subscriptions
- **Session context** — connect once, then browse without repeating the account name on every message
- **Full blob toolkit** — list containers, browse blobs by prefix, read content, search by Blob Index Tags
- **Queue peek** — inspect messages non-destructively (no dequeue)
- **File share browsing** — list shares, directories, and files
- **Table queries** — OData filter expressions, field selection, single entity lookup
- **Read-only** — no write operations exposed, safe to point at production

## Prerequisites

- [Docker Desktop](https://www.docker.com/products/docker-desktop/)
- [Azure CLI](https://learn.microsoft.com/en-us/cli/azure/install-azure-cli) (`brew install azure-cli`)
- An Azure account with access to at least one storage account

## Setup

**1. Log in to Azure**

```bash
az login
```

**2. Clone and build the image**

```bash
git clone https://github.com/ChingEnLin/BlobMCPal.git
cd BlobMCPal
docker build --platform linux/arm64 -t blobmcpal:dev .
```

> For Intel Macs change `linux/arm64` to `linux/amd64` in the build command and the config below.

**3. Allow Docker Desktop to access `~/.azure`**

Docker Desktop restricts which host directories containers can mount. You need to add the `.azure` directory to its allowed list before the volume mount will work.

**macOS:** Open Docker Desktop → **Settings → Resources → File Sharing** and add:
```
~/.azure
```

Apply & Restart Docker Desktop after saving.

**4. Add to your AI tool**

> **Windows users:** If you'd prefer to skip Docker entirely, see the [Windows setup](#windows-setup) section — `uvx` is simpler and avoids the file sharing step.

**Claude Desktop**

Edit `~/Library/Application Support/Claude/claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "blobmcpal": {
      "command": "docker",
      "args": [
        "run", "--rm", "-i",
        "--platform", "linux/arm64",
        "-v", "/Users/YOUR_USERNAME/.azure:/home/mcpuser/.azure",
        "blobmcpal:dev"
      ]
    }
  }
}
```

Replace `YOUR_USERNAME` with your macOS username (`echo $USER`). Use the full path — `${HOME}` does not expand in Claude Desktop's config.

**VS Code (GitHub Copilot)**

Create or edit `.vscode/mcp.json` in your workspace:

```json
{
  "servers": {
    "blobmcpal": {
      "type": "stdio",
      "command": "docker",
      "args": [
        "run", "--rm", "-i",
        "--platform", "linux/arm64",
        "-v", "/Users/YOUR_USERNAME/.azure:/home/mcpuser/.azure",
        "blobmcpal:dev"
      ]
    }
  }
}
```

**5. Restart your AI tool**

For Claude Desktop: quit and relaunch. For VS Code: reload the window or accept the prompt to start the MCP server. BlobMCPal will appear as a connected MCP server.

## Usage

Once connected, talk to your AI tool naturally:

```
"What storage accounts do I have access to?"
"Connect to prodstoragewe"
"Show me the containers"
"What blobs were uploaded to patient-exports in the last 7 days?"
"Show me the content of the most recent CSV"
"Are there any messages in the device-alerts queue?"
"Query the audit-logs table where PartitionKey is 'api' and limit to 50 rows"
```

The AI will chain the tools automatically — you don't need to know which tool does what.

## How authentication works

When the container starts, it mounts your local `~/.azure` directory (where `az login` stores its token cache). The Azure identity library inside the container reads those cached credentials — no tokens leave your machine, nothing is stored in config files, and your existing Azure RBAC permissions apply as-is.

Token refresh is handled automatically on each request. If your token has expired, BlobMCPal will tell you to run `az login` again — not show you a Python traceback.

## Azure RBAC requirements

BlobMCPal uses your Entra ID identity for both account discovery and data-plane access. No account keys or SAS tokens are needed.

| Role | Required for |
|---|---|
| `Reader` | Listing subscriptions and storage accounts |
| `Storage Blob Data Reader` | Containers, blobs, blob content and metadata |
| `Storage Queue Data Reader` | Queue list and message peek |
| `Storage File Data SMB Share Reader` | File share and file listing |
| `Storage Table Data Reader` | Table list and entity queries |

## Available tools

| Tool | Description |
|---|---|
| `check_auth` | Verify your Azure credential is working and list accessible subscriptions |
| `list_storage_accounts` | List all accessible storage accounts across all subscriptions |
| `connect_account` | Connect to an account; optionally set a default container |
| `list_containers` | List all blob containers in the active account |
| `list_blobs` | List blobs with optional name prefix filter (max 500) |
| `get_blob_metadata` | Full properties, metadata, tags, and lease status for a blob |
| `get_blob_content` | Download blob content — text as UTF-8, binary as base64 (32 KB default cap) |
| `search_blobs` | Search blobs by name prefix and/or Blob Index Tag filter expression |
| `list_queues` | List all queues in the active account |
| `peek_messages` | Non-destructively peek at up to 32 messages in a queue |
| `get_queue_properties` | Approximate message count and queue metadata |
| `list_file_shares` | List all file shares in the active account |
| `list_share_contents` | List files and subdirectories at a path within a file share |
| `get_file_metadata` | File size, content type, last modified, and custom metadata |
| `list_tables` | List all tables in the active account |
| `query_table` | Query table entities with an OData filter expression (max 200) |
| `get_table_entity` | Retrieve a single entity by PartitionKey and RowKey |
| `show_context` | Show the active account and default container |
| `set_context` | Update default container without reconnecting |
| `clear_context` | Disconnect and reset session state |

## Windows setup

Docker volume mounts for `.azure` credentials can be tricky on Windows. The simpler path is `uvx`, which runs BlobMCPal directly on the host — no Docker needed.

**1. Install prerequisites**

```powershell
winget install astral-sh.uv
winget install Microsoft.AzureCLI
```

**2. Log in to Azure**

```powershell
az login
```

**3. Add to your AI tool**

**Claude Desktop**

Edit `%APPDATA%\Claude\claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "blobmcpal": {
      "command": "uvx",
      "args": ["blobmcpal"]
    }
  }
}
```

**VS Code (GitHub Copilot)**

Create or edit `.vscode/mcp.json` in your workspace:

```json
{
  "servers": {
    "blobmcpal": {
      "type": "stdio",
      "command": "uvx",
      "args": ["blobmcpal"]
    }
  }
}
```

`uvx` fetches and runs the package in an isolated environment. `az login` credentials on the host are picked up automatically.

**4. Restart your AI tool**

For Claude Desktop: quit and relaunch. For VS Code: reload the window or accept the prompt to start the MCP server.

## For developers

If you have Python 3.12+ and the Azure CLI installed locally, you can run BlobMCPal directly without Docker using `uvx`:

```bash
uvx blobmcpal
```

To wire it into an AI tool instead of the Docker approach:

**Claude Desktop** — update `~/Library/Application Support/Claude/claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "blobmcpal": {
      "command": "uvx",
      "args": ["blobmcpal"]
    }
  }
}
```

**VS Code (GitHub Copilot)** — create `.vscode/mcp.json` in your workspace:

```json
{
  "servers": {
    "blobmcpal": {
      "type": "stdio",
      "command": "uvx",
      "args": ["blobmcpal"]
    }
  }
}
```

## Troubleshooting

**Auth error after az login**

Run `check_auth` in Claude to get a precise status. If it returns `ok: false`, re-run `az login` in your terminal and restart Claude Desktop.

**Docker Desktop file sharing error**

If the container cannot see `~/.azure`, open Docker Desktop → **Settings → Resources → File Sharing**, add `~/.azure`, and click **Apply & Restart**.

**`get_blob_content` is truncated**

By default, blob content is capped at 32 KB. Ask Claude to increase `max_bytes` — up to 5 MB is supported. Images, PDFs, audio, and video return metadata only (no binary download).

**Permission denied**

You are missing an Azure RBAC role on this resource. Contact your Azure administrator to assign the relevant role (see [RBAC requirements](#azure-rbac-requirements)).

## Limitations

- The Docker setup targets macOS. Windows users should follow the [Windows setup](#windows-setup) section, which uses `uvx` instead. Intel Mac and Linux users can use Docker with `--platform linux/amd64`.
- Read-only — no upload, delete, or copy operations in v1.0.
- Blob Index Tag search requires the storage account to have blob index tags enabled.

## License

MIT
