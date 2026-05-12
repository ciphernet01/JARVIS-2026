# JARVIS Desktop Overlay

This is a desktop shell for the existing JARVIS React UI.

## Behavior
- Loads the same web UI without changing the interface markup or styling.
- Uses a frameless, always-on-top Electron window.
- Starts as a HUD-style transparent overlay at 50% window opacity.
- Auto-launches with the operating system on supported platforms.
- Falls back to the local React build if the development server is not running.

## Run
1. Start the backend on port 8001.
2. Start the React app on port 3000, or build it with `npm run build` inside `frontend/`.
3. From this folder, install dependencies and launch the overlay.
