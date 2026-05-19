#!/bin/bash
# JARVIS OS - Neural Shell Session Wrapper
# Starts the X server and launches Electron HUD as the primary compositor

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
xset s off
xset -dpms
xset s noblank

# 4. Start JARVIS Backend
cd /opt/jarvis
python3 backend/server.py &
BACKEND_PID=$!

# 5. Wait for Backend to be ready
while ! curl -s http://localhost:8001/health > /dev/null; do
    sleep 1
done

# 6. Ensure Biometric Reference Directory exists
mkdir -p /opt/jarvis/imagedata

# 7. Launch Electron HUD (The Neural Shell)
cd /opt/jarvis/desktop-overlay
# Note: npm start in production usually translates to electron .
# We use --no-sandbox because we are running as root in some live environments
./node_modules/.bin/electron . --no-sandbox --kiosk

# Cleanup if Electron exits
kill $BACKEND_PID
