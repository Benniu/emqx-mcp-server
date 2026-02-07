# ---- Build stage ----
FROM ghcr.io/astral-sh/uv:python3.12-alpine AS builder

WORKDIR /app

# Enable bytecode compilation for performance
ENV UV_COMPILE_BYTECODE=1

# Install build dependencies required for native extensions
RUN apk add --no-cache build-base libffi-dev

# Copy dependency manifests first for layer caching
COPY pyproject.toml uv.lock /app/

# Install dependencies (cached unless manifests change)
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-install-project --no-dev --no-editable

# Copy source and install the project itself
COPY src /app/src
COPY LICENSE README.md /app/
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev --no-editable

# ---- Runtime stage ----
FROM python:3.12-alpine AS runtime

LABEL org.opencontainers.image.title="emqx-mcp-server" \
      org.opencontainers.image.description="MCP server for EMQX MQTT broker interaction" \
      org.opencontainers.image.source="https://github.com/Benniu/emqx-mcp-server" \
      org.opencontainers.image.licenses="Apache-2.0"

# Create non-root user for security
RUN addgroup -S mcp && adduser -S mcp -G mcp

WORKDIR /app

# Copy only the virtualenv from builder (no build toolchain)
COPY --from=builder /app/.venv /app/.venv

ENV PATH="/app/.venv/bin:$PATH"

# Switch to non-root user
USER mcp

# Verify the server process is alive
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD pgrep -f emqx-mcp-server || exit 1

# Default command to run the EMQX MCP server
ENTRYPOINT ["emqx-mcp-server"]
