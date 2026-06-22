#!/bin/bash
set -e

# A.S.T.R.A OS - Spatial Shell Session Wrapper
# Starts the X server and launches the local A.S.T.R.A UI.

JARVIS_HOME="${JARVIS_HOME:-/opt/jarvis}"
BACKEND_URL="http://localhost:${JARVIS_BACKEND_PORT:-8001}"
LOCAL_UI="$JARVIS_HOME/frontend/build/index.html"
ELECTRON_BIN="$JARVIS_HOME/desktop-overlay/node_modules/.bin/electron"

# 1. Start X server if not running
if ! pidof X > /dev/null; then
    X &
    sleep 2
    export DISPLAY=:0
fi

# 2. Start basic Window Manager (optional, openbox is lightweight)
if command -v openbox > /dev/null; then
    openbox --startup "echo Window Manager Ready" &
fi

# 3. Disable screen blanking and power management
xset s off || true
xset -dpms || true
xset s noblank || true

# 4. Wait for the separately supervised backend service.
attempt=0
until curl -fsS "$BACKEND_URL/health" > /dev/null; do
    attempt=$((attempt + 1))
    if [ "$attempt" -ge 60 ]; then
        echo "A.S.T.R.A backend did not become ready at $BACKEND_URL" >&2
        exit 1
    fi
    sleep 1
done

# 5. Ensure the writable biometric directory exists.
mkdir -p "${ASTRA_STATE_DIR:-/var/lib/astra}/imagedata"

# 6. Launch the UI. Prefer Electron if a Linux build is bundled; otherwise use Firefox kiosk.
if [ -x "$ELECTRON_BIN" ]; then
    cd "$JARVIS_HOME/desktop-overlay"
    "$ELECTRON_BIN" . --no-sandbox --kiosk
elif command -v firefox-esr > /dev/null || command -v firefox > /dev/null; then
    FIREFOX_BIN="$(command -v firefox-esr || command -v firefox)"
    if [ -f "$LOCAL_UI" ]; then
        "$FIREFOX_BIN" --kiosk "file://$LOCAL_UI"
    else
        "$FIREFOX_BIN" --kiosk "$BACKEND_URL/docs"
    fi
else
    xterm -hold -e "echo 'A.S.T.R.A backend is running at $BACKEND_URL'; journalctl -u jarvis.service -f"
fi
