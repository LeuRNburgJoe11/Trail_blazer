#!/bin/sh
set -eu
exec python -m uvicorn backend.cloud:create_app --factory --host 0.0.0.0 --port "${PORT:-8080}" --workers 1 --no-access-log --no-proxy-headers
