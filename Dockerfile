# Stage 1: Build the wheel
FROM python:3.12-slim AS builder

WORKDIR /build
COPY pyproject.toml README.md ./
COPY src/ src/

RUN pip install --no-cache-dir build \
    && python -m build --wheel --outdir /build/dist

# Stage 2: Minimal runtime image
FROM python:3.12-slim

# Install Azure CLI — required by AzureCliCredential inside DefaultAzureCredential.
# Uses the official Microsoft install script to get the latest stable release.
RUN apt-get update \
    && apt-get install -y --no-install-recommends curl ca-certificates \
    && curl -sL https://aka.ms/InstallAzureCLIDeb | bash \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Create a non-root user (uid 1000) that will run the server.
RUN useradd --create-home --shell /bin/bash --uid 1000 mcpuser

# Install the built wheel and its dependencies.
COPY --from=builder /build/dist/*.whl /tmp/
RUN pip install --no-cache-dir /tmp/*.whl \
    && rm /tmp/*.whl

# Tell DefaultAzureCredential / AzureCliCredential where to find the CLI token
# cache. The ~/.azure directory from the host is mounted read-only here.
ENV AZURE_CONFIG_DIR=/home/mcpuser/.azure

USER mcpuser
WORKDIR /home/mcpuser

# MCP stdio transport: Claude Desktop pipes stdin/stdout directly.
ENTRYPOINT ["blobmcpal"]
