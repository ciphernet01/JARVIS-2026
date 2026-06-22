#!/bin/bash
# A.S.T.R.A First-Boot Setup Wizard
# Runs on first system boot to configure A.S.T.R.A OS.

set -e

JARVIS_HOME=${JARVIS_HOME:-/opt/jarvis}
JARVIS_CONFIG_DIR="/etc/jarvis"
JARVIS_DATA_DIR="/var/lib/jarvis"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

log_info() {
    echo -e "${BLUE}ℹ${NC} $1"
}

log_success() {
    echo -e "${GREEN}✓${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}⚠${NC} $1"
}

log_error() {
    echo -e "${RED}✗${NC} $1"
}

main() {
    clear
    
    echo -e "${BLUE}"
    echo "╔════════════════════════════════════════════════════╗"
    echo "║    A.S.T.R.A Operating System                     ║"
    echo "║    First-Boot Setup & Configuration               ║"
    echo "╚════════════════════════════════════════════════════╝"
    echo -e "${NC}"
    
    # 1. System Updates
    log_info "Checking for system updates..."
    apt-get update -qq
    apt-get upgrade -y -qq
    log_success "System packages updated"
    
    # 2. Create directories
    log_info "Creating A.S.T.R.A directories..."
    if ! getent group astra >/dev/null; then
        groupadd --system astra
    fi
    if ! id astra >/dev/null 2>&1; then
        useradd --system --gid astra --home-dir /var/lib/astra --create-home --shell /usr/sbin/nologin astra
    fi
    for group in audio video input dialout; do
        if getent group "$group" >/dev/null; then
            usermod --append --groups "$group" astra
        fi
    done
    mkdir -p "$JARVIS_CONFIG_DIR"
    mkdir -p "$JARVIS_DATA_DIR"
    mkdir -p /var/log/jarvis
    mkdir -p /var/lib/astra/workspace
    chown -R astra:astra /var/lib/astra
    log_success "Directories created"
    
    # 3. Python & Node dependencies
    log_info "Installing system dependencies..."
    cd "$JARVIS_HOME" || exit 1
    pip3 install -q -r requirements.txt
    pip3 install -q openai-whisper ollama mediapipe pyautogui

    log_info "Installing Neural Shell (Electron) dependencies..."
    if [ -d "$JARVIS_HOME/desktop-overlay" ]; then
        cd "$JARVIS_HOME/desktop-overlay"
        npm install --quiet
    fi
    log_success "Dependencies installed (including AI/Vision/HUD layers)"
    
    # 4. Database initialization
    log_info "Initializing A.S.T.R.A database..."
    mkdir -p "$JARVIS_DATA_DIR"
    log_success "Database directory ready"
    
    # 5. Audio system configuration
    log_info "Configuring audio system..."
    systemctl daemon-reload
    systemctl enable alsa-utils.service 2>/dev/null || true
    systemctl enable pulseaudio.service 2>/dev/null || true
    log_success "Audio system configured"
    
    # 6. Set timezone
    log_info "Configure timezone"
    echo -e "${YELLOW}Select your timezone (or press Enter for UTC):${NC}"
    read -r TZ_INPUT
    if [ -z "$TZ_INPUT" ]; then
        TZ_INPUT="UTC"
    fi
    timedatectl set-timezone "$TZ_INPUT"
    log_success "Timezone set to $TZ_INPUT"
    
    # 7. Network configuration
    log_info "Configure network"
    echo -e "${YELLOW}Enable WiFi (y/n)?${NC}"
    read -r ENABLE_WIFI
    if [[ "$ENABLE_WIFI" == "y" || "$ENABLE_WIFI" == "Y" ]]; then
        systemctl enable network-manager.service
        log_success "WiFi enabled"
    fi
    
    # 8. User setup
    log_info "User enrollment"
    echo -e "${YELLOW}Create system user (username):${NC}"
    read -r USERNAME
    
    if id "$USERNAME" &>/dev/null; then
        log_warn "User $USERNAME already exists"
    else
        useradd -m -s /bin/bash "$USERNAME" || true
        usermod -aG sudo "$USERNAME" 2>/dev/null || true
        log_success "User $USERNAME created"
    fi
    
    # 9. A.S.T.R.A service setup
    log_info "Setting up A.S.T.R.A service..."
    cp "$JARVIS_HOME/os-distribution/config/jarvis.service" /etc/systemd/system/
    cp "$JARVIS_HOME/os-distribution/config/astra-shell.service" /etc/systemd/system/
    cp "$JARVIS_HOME/os-distribution/config/astra-control-broker.service" /etc/systemd/system/
    systemctl daemon-reload
    systemctl enable astra-control-broker.service jarvis.service astra-shell.service
    log_success "A.S.T.R.A control broker, backend, and spatial shell services installed"
    
    # 10. Voice & Vision setup
    log_info "Voice & Vision system setup"
    echo -e "${YELLOW}"
    echo "A.S.T.R.A uses voice recognition and hand gestures for interaction."
    echo "Downloading Whisper base model for offline speech recognition..."
    # Pre-download Whisper model to avoid delay on first use
    python3 -c "import whisper; whisper.load_model('base')"
    echo "Local AI Core (Ollama) will be configured for optimal performance."
    echo -e "${NC}"
    
    # 11. Completion
    echo -e "\n${GREEN}"
    echo "╔════════════════════════════════════════════════════╗"
    echo "║    Setup Complete! ✓                              ║"
    echo "╚════════════════════════════════════════════════════╝"
    echo -e "${NC}"
    
    echo -e "${BLUE}Next steps:${NC}"
    echo "1. Reboot the system: reboot"
    echo "2. Login as $USERNAME"
    echo "3. A.S.T.R.A will start automatically"
    echo "4. Access web interface: http://localhost:3000"
    echo ""
    
    # 12. Mark first-boot as complete
    touch "$JARVIS_CONFIG_DIR/.first-boot-completed"
    log_success "First-boot setup complete"
    
    echo -e "${YELLOW}Reboot now (y/n)?${NC}"
    read -r REBOOT
    if [[ "$REBOOT" == "y" || "$REBOOT" == "Y" ]]; then
        log_info "Rebooting system..."
        sleep 2
        reboot
    else
        log_info "Please reboot manually when ready"
    fi
}

# Run setup
main
