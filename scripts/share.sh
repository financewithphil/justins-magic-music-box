#!/usr/bin/env bash
# Start a Cloudflare quick tunnel exposing the local API publicly.
#
# Generates a fresh https://<random>.trycloudflare.com URL each run.
# No Cloudflare account or domain required. Tunnel lives only as long
# as this process — Ctrl+C stops it.
set -euo pipefail

PORT="${PORT:-8768}"
LOG="/tmp/jmb-tunnel.log"

if ! command -v cloudflared >/dev/null 2>&1; then
  echo "cloudflared not installed. Run: brew install cloudflared" >&2
  exit 1
fi

if ! curl -s -m 2 "http://127.0.0.1:${PORT}/api/health" >/dev/null 2>&1; then
  echo "Local API not responding at http://127.0.0.1:${PORT}" >&2
  echo "Start it first with:   just dev" >&2
  exit 1
fi

if pgrep -f "cloudflared tunnel --url http://localhost:${PORT}" >/dev/null 2>&1; then
  EXISTING=$(grep -oE "https://[a-z0-9-]+\.trycloudflare\.com" "$LOG" 2>/dev/null | tail -1 || true)
  if [ -n "$EXISTING" ]; then
    echo "Tunnel already running."
    echo "URL: $EXISTING"
    exit 0
  fi
fi

: > "$LOG"
cloudflared tunnel --url "http://localhost:${PORT}" --no-autoupdate > "$LOG" 2>&1 &
TUNNEL_PID=$!

cleanup() {
  echo ""
  echo "Stopping tunnel..."
  kill "$TUNNEL_PID" 2>/dev/null || true
  wait "$TUNNEL_PID" 2>/dev/null || true
  echo "Stopped. (The local app at 127.0.0.1:${PORT} keeps running.)"
}
trap cleanup INT TERM

echo "Starting Cloudflare Tunnel for http://localhost:${PORT} ..."
URL=""
for i in $(seq 1 30); do
  sleep 1
  URL=$(grep -oE "https://[a-z0-9-]+\.trycloudflare\.com" "$LOG" 2>/dev/null | head -1 || true)
  [ -n "$URL" ] && break
done

if [ -z "$URL" ]; then
  echo "Tunnel failed to come up within 30 s. Last log lines:" >&2
  tail -10 "$LOG" >&2
  kill "$TUNNEL_PID" 2>/dev/null || true
  exit 1
fi

cat <<EOF

  ┌──────────────────────────────────────────────────────────────────┐
  │                                                                  │
  │   Tunnel is live. Send Justin this URL:                          │
  │                                                                  │
  │     ${URL}
  │                                                                  │
  │   • URL changes every restart (Cloudflare quick-tunnel).         │
  │   • Press Ctrl+C to stop sharing — local app keeps running.      │
  │                                                                  │
  └──────────────────────────────────────────────────────────────────┘

EOF

wait "$TUNNEL_PID" || true
