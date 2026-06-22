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
    
    # 1. Release integrity
    log_info "Using the package set embedded in this signed image."
    log_info "System updates are handled after enrollment by the A.S.T.R.A update workflow."
    
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
    
    # 3. Verify the image-local runtime. First boot must not download code.
    log_info "Verifying the image-local A.S.T.R.A runtime..."
    if [ ! -x /opt/astra/venv/bin/python ]; then
        log_error "Missing /opt/astra/venv; the image runtime is incomplete"
        exit 1
    fi
    /opt/astra/venv/bin/python -c "import fastapi, uvicorn, cv2, mediapipe, openai"
    log_success "Offline runtime verified"
    
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
    cp "$JARVIS_HOME/os-distribution/config/astra-boot-ready.service" /etc/systemd/system/
    systemctl daemon-reload
    systemctl enable astra-control-broker.service jarvis.service astra-shell.service astra-boot-ready.service
    log_success "A.S.T.R.A control broker, backend, spatial shell, and boot marker installed"
    
    # 10. Voice & Vision setup
    log_info "Voice & Vision system setup"
    echo -e "${YELLOW}"
    echo "A.S.T.R.A uses voice recognition and hand gestures for interaction."
    echo "Optional speech and local-model assets can be installed later from signed A.S.T.R.A packages."
    echo "First boot performs no network code or model downloads."
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
