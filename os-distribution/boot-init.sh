#!/bin/bash
# JARVIS OS Boot Configuration
# Runs after kernel loads, before login

set -e

JARVIS_HOME=${JARVIS_HOME:-/opt/jarvis}

# Display boot banner
clear
cat << 'EOF'

     ██╗ █████╗ ██████╗ ██╗   ██╗██╗███████╗
     ██║██╔══██╗██╔══██╗██║   ██║██║██╔════╝
     ██║███████║██████╔╝██║   ██║██║███████╗
██   ██║██╔══██║██╔══██╗╚██╗ ██╔╝██║╚════██║
╚█████╔╝██║  ██║██║  ██║ ╚████╔╝ ██║███████║
 ╚════╝ ╚═╝  ╚═╝╚═╝  ╚═╝  ╚═══╝  ╚═╝╚══════╝

        Neural Operating System v2.0
        
        🎤 Voice-First Architecture
        🧠 AI-Driven Core Intelligence
        
EOF

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

# Wait for system to be ready
sleep 2

# Check JARVIS backend
echo "⏳ Initializing JARVIS core..."
for i in {1..30}; do
    if curl -s http://localhost:8001/api/health -H "X-JARVIS-TOKEN: system-boot" > /dev/null 2>&1; then
        echo "✓ JARVIS core online"
        break
    fi
    
    if [ $i -eq 30 ]; then
        echo "⚠  JARVIS core is loading (this may take a moment)"
        echo "   Continuing with fallback mode..."
    else
        echo -n "."
        sleep 1
    fi
done

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

# Display boot messages
echo "📊 System Status:"
echo ""

# CPU Count
CPU_COUNT=$(nproc)
echo "   • CPU Cores: $CPU_COUNT"

# Memory
TOTAL_MEM=$(free -h | grep "^Mem:" | awk '{print $2}')
echo "   • Memory: $TOTAL_MEM"

# Network Status
echo -n "   • Network: "
if ping -c 1 8.8.8.8 > /dev/null 2>&1; then
    echo "✓ Online"
else
    echo "⚠ Offline"
fi

# Disk Space
DISK_USAGE=$(df -h / | tail -1 | awk '{print $5}')
echo "   • Disk Usage: $DISK_USAGE"

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

# Show audio status
echo "🎤 Voice System:"

if command -v pactl &> /dev/null; then
    AUDIO_STATUS=$(pactl info 2>/dev/null | grep "^Server Name" | cut -d: -f2 | xargs)
    if [ -n "$AUDIO_STATUS" ]; then
        echo "   • Audio Server: $AUDIO_STATUS"
    fi
fi

if pactl list short sources 2>/dev/null | grep -q "alsa_input"; then
    echo "   • Microphone: Ready"
fi

if pactl list short sinks 2>/dev/null | grep -q "alsa_output"; then
    echo "   • Speaker: Ready"
fi

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

# Interactive prompt
echo "🎯 Ready for voice interaction"
echo ""
echo "Available interfaces:"
echo "  • Voice Shell: jarvis-shell"
echo "  • Web Dashboard: http://localhost:3000"
echo "  • REST API: http://localhost:8001"
echo ""

# Launch voice shell if TTY
if [ -t 0 ]; then
    echo "Starting voice shell..."
    sleep 1
    exec "$JARVIS_HOME/os-distribution/jarvis-shell"
fi
