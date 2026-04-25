#!/usr/bin/env bash
# Start a Cloudflare quick tunnel + publish the live URL to GitHub Pages
# at /share/ so Justin always uses one stable bookmark.
#
# Free path: the tunnel is still ephemeral (URL changes per run), but the
# /share/ page is updated on every start/stop so Justin sees the right URL.
set -euo pipefail

PORT="${PORT:-8768}"
LOG="/tmp/jmb-tunnel.log"
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
TUNNEL_JSON="$ROOT/docs/share/tunnel.json"

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

write_status() {
  local status="$1" url="$2"
  local now
  now=$(date -u +%Y-%m-%dT%H:%M:%SZ)
  cat > "$TUNNEL_JSON" <<EOF
{"status": "${status}", "url": ${url}, "updated_at": "${now}"}
EOF
}

publish_status() {
  local why="$1"
  cd "$ROOT"
  if ! git diff --quiet -- docs/share/tunnel.json 2>/dev/null; then
    git add docs/share/tunnel.json >/dev/null 2>&1 || true
    if git -c commit.gpgsign=false commit -m "share: ${why}" >/dev/null 2>&1; then
      git push origin main >/dev/null 2>&1 \
        && echo "  · /share/ updated on GitHub Pages" \
        || echo "  · git push failed (network?) — page won't refresh until next push" >&2
    fi
  fi
}

cleanup() {
  echo ""
  echo "Stopping tunnel..."
  kill "$TUNNEL_PID" 2>/dev/null || true
  wait "$TUNNEL_PID" 2>/dev/null || true
  write_status "offline" "null"
  publish_status "tunnel offline"
  echo "Stopped. (The local app at 127.0.0.1:${PORT} keeps running.)"
}
trap cleanup INT TERM

: > "$LOG"
cloudflared tunnel --url "http://localhost:${PORT}" --no-autoupdate > "$LOG" 2>&1 &
TUNNEL_PID=$!

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

write_status "live" "\"${URL}\""
publish_status "tunnel live"

cat <<EOF

  ┌──────────────────────────────────────────────────────────────────┐
  │                                                                  │
  │   Tunnel is live. Two ways to share with Justin:                 │
  │                                                                  │
  │   STABLE BOOKMARK (he uses this every time):                     │
  │     https://financewithphil.github.io/justins-magic-music-box/share/
  │                                                                  │
  │   DIRECT URL (this session only):                                │
  │     ${URL}
  │                                                                  │
  │   • The /share/ page updates within a minute of this banner.     │
  │   • Press Ctrl+C to stop sharing — local app keeps running.      │
  │                                                                  │
  └──────────────────────────────────────────────────────────────────┘

EOF

wait "$TUNNEL_PID" || true
