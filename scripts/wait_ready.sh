#!/usr/bin/env bash
set -euo pipefail
URL="${1:-http://127.0.0.1:19530/readyz}"
TIMEOUT="${2:-120}"
start=$(date +%s)
while true; do
  if curl -fsS "$URL" >/dev/null 2>&1; then
    echo "ready: $URL"
    exit 0
  fi
  now=$(date +%s)
  if (( now - start > TIMEOUT )); then
    echo "timeout waiting for $URL" >&2
    exit 1
  fi
  sleep 2
done
