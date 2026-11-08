#!/bin/sh
set -eu

# Keep the environment and the server's relative log in this checkout.
cd "$(dirname "$0")"

uv_bin="${UV_BIN:-uv}"
if ! command -v "$uv_bin" >/dev/null 2>&1; then
    echo "uv was not found. Install uv or set UV_BIN to its absolute path." >&2
    exit 127
fi

exec "$uv_bin" run --locked --managed-python --no-progress python -u mcp_server.py
